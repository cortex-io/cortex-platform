/**
 * Intelligent Scheduler with ML-Powered Prediction
 *
 * Main scheduler that integrates:
 * - ML-based resource prediction
 * - Preemptive feasibility checks
 * - SLA-aware prioritization
 * - Admission control and backpressure
 *
 * Designed to scale to 100+ agents on 16GB RAM through intelligent
 * resource management and predictive scheduling.
 */

const EventEmitter = require('events');
const { ResourcePredictor } = require('./resource-predictor');
const { FeasibilityChecker } = require('./feasibility-checker');
const { PriorityEngine } = require('./priority-engine');

/**
 * Intelligent Scheduler
 */
class IntelligentScheduler extends EventEmitter {
  constructor(options = {}) {
    super();

    // Configuration
    this.config = {
      resourceLimits: {
        maxMemoryMB: options.maxMemoryMB || 12288,
        maxConcurrentTasks: options.maxConcurrentTasks || 20,
        tokenBudgetPerHour: options.tokenBudgetPerHour || 1000000,
        tokenBudgetPerDay: options.tokenBudgetPerDay || 10000000,
        ...options.resourceLimits
      },
      sla: {
        defaultDeadlineMinutes: options.defaultDeadlineMinutes || 60,
        priorityWeights: options.priorityWeights,
        ...options.sla
      },
      prediction: {
        minSamplesForML: options.minSamplesForML || 50,
        fallbackToHeuristics: options.fallbackToHeuristics !== false,
        modelUpdateInterval: options.modelUpdateInterval || 100,
        ...options.prediction
      },
      admission: {
        enableBackpressure: options.enableBackpressure !== false,
        maxQueueDepth: options.maxQueueDepth || 100,
        rejectOnOverload: options.rejectOnOverload !== false
      }
    };

    // Initialize components
    this.predictor = new ResourcePredictor({
      minSamplesForML: this.config.prediction.minSamplesForML,
      fallbackToHeuristics: this.config.prediction.fallbackToHeuristics,
      modelUpdateInterval: this.config.prediction.modelUpdateInterval
    });

    this.feasibilityChecker = new FeasibilityChecker({
      maxMemoryMB: this.config.resourceLimits.maxMemoryMB,
      maxConcurrentTasks: this.config.resourceLimits.maxConcurrentTasks,
      tokenBudgetPerHour: this.config.resourceLimits.tokenBudgetPerHour,
      tokenBudgetPerDay: this.config.resourceLimits.tokenBudgetPerDay
    });

    this.priorityEngine = new PriorityEngine({
      priorityWeights: this.config.sla.priorityWeights,
      maxWaitTimeMs: this.config.sla.defaultDeadlineMinutes * 60000
    });

    // State
    this.scheduledTasks = new Map(); // taskId -> schedulingDecision
    this.runningTasks = new Map(); // taskId -> startTime
    this.completedTasks = new Map(); // taskId -> outcome

    // Statistics
    this.stats = {
      totalRequests: 0,
      acceptedTasks: 0,
      rejectedTasks: 0,
      completedTasks: 0,
      backpressureEvents: 0,
      rejectionReasons: {}
    };

    // Start monitoring loop
    this._startMonitoring();
  }

  /**
   * Check if a task can be accepted
   *
   * Returns:
   * - feasible: boolean
   * - reason: string (if not feasible)
   * - estimatedResources: resource predictions
   * - estimatedWaitTime: time until resources available
   */
  canAcceptTask(task) {
    this.stats.totalRequests++;

    // Check queue depth
    if (this.config.admission.enableBackpressure) {
      const queueDepth = this.priorityEngine.getQueue().length;

      if (queueDepth >= this.config.admission.maxQueueDepth) {
        this.stats.backpressureEvents++;
        this._incrementRejectionReason('queue-full');

        return {
          feasible: false,
          reason: 'queue-full',
          queueDepth,
          maxQueueDepth: this.config.admission.maxQueueDepth,
          estimatedWaitTimeMs: this._estimateQueueWaitTime(),
          backpressure: true
        };
      }
    }

    // Predict resource requirements
    const prediction = this.predictor.predict(task);

    // Check feasibility
    const feasibility = this.feasibilityChecker.calculateFeasibility({
      estimatedMemoryMB: prediction.estimatedMemoryMB,
      estimatedCpuSeconds: prediction.estimatedCpuSeconds,
      estimatedTokens: prediction.estimatedTokens,
      estimatedDurationMs: prediction.estimatedDurationMs
    });

    // Record rejection reason if not feasible
    if (!feasibility.feasible) {
      this._incrementRejectionReason(feasibility.reason);
    }

    return {
      feasible: feasibility.feasible,
      reason: feasibility.reason,
      estimatedResources: {
        memoryMB: prediction.estimatedMemoryMB,
        cpuSeconds: prediction.estimatedCpuSeconds,
        tokens: prediction.estimatedTokens,
        durationMs: prediction.estimatedDurationMs
      },
      predictionMethod: prediction.method,
      predictionConfidence: prediction.confidence,
      estimatedWaitTimeMs: feasibility.estimatedWaitTimeMs,
      systemState: feasibility.systemState,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Schedule a task for execution
   *
   * Returns scheduling decision with priority and queue position
   */
  scheduleTask(task) {
    // Ensure task has required fields
    const taskId = task.id || task.taskId || this._generateTaskId();
    const taskWithId = { ...task, id: taskId, taskId };

    // Check if we can accept the task
    const admissionCheck = this.canAcceptTask(taskWithId);

    if (!admissionCheck.feasible && this.config.admission.rejectOnOverload) {
      this.stats.rejectedTasks++;

      return {
        scheduled: false,
        rejected: true,
        reason: admissionCheck.reason,
        taskId,
        estimatedWaitTimeMs: admissionCheck.estimatedWaitTimeMs
      };
    }

    // Add estimated resources to task
    taskWithId.estimatedResources = admissionCheck.estimatedResources;

    // Get current capacity for priority calculation
    const currentCapacity = this.feasibilityChecker.getSystemCapacity();

    // Add to priority queue
    const queueResult = this.priorityEngine.addTask(
      taskWithId,
      currentCapacity.resources
    );

    // Allocate resources (reservation)
    const allocation = this.feasibilityChecker.allocateResources(
      taskId,
      admissionCheck.estimatedResources
    );

    // Create scheduling decision
    const schedulingDecision = {
      taskId,
      scheduled: true,
      priority: queueResult.priorityScore,
      queuePosition: queueResult.position,
      queueSize: queueResult.queueSize,
      estimatedResources: admissionCheck.estimatedResources,
      allocation,
      scheduledAt: new Date().toISOString()
    };

    this.scheduledTasks.set(taskId, schedulingDecision);
    this.stats.acceptedTasks++;

    // Emit event
    this.emit('task-scheduled', schedulingDecision);

    return schedulingDecision;
  }

  /**
   * Mark task as started
   */
  startTask(taskId) {
    const scheduled = this.scheduledTasks.get(taskId);

    if (!scheduled) {
      return { started: false, reason: 'task-not-scheduled' };
    }

    this.runningTasks.set(taskId, {
      taskId,
      startedAt: new Date().toISOString(),
      schedulingDecision: scheduled
    });

    // Remove from priority queue
    this.priorityEngine.removeTask(taskId);

    this.emit('task-started', { taskId });

    return {
      started: true,
      taskId,
      startedAt: this.runningTasks.get(taskId).startedAt
    };
  }

  /**
   * Report task outcome for ML learning
   *
   * Call this when a task completes to improve predictions
   */
  reportOutcome(taskId, actualResources, task = null) {
    // Get task info
    const scheduled = this.scheduledTasks.get(taskId);
    const running = this.runningTasks.get(taskId);

    if (!scheduled && !task) {
      return {
        recorded: false,
        reason: 'task-not-found'
      };
    }

    // Get task object
    const taskObj = task || scheduled?.task || {};

    // Ensure task has the taskId
    taskObj.id = taskId;
    taskObj.taskId = taskId;

    // Report to predictor for learning
    const learningResult = this.predictor.reportOutcome(
      taskId,
      taskObj,
      actualResources
    );

    // Release resources
    const releaseResult = this.feasibilityChecker.releaseResources(
      taskId,
      actualResources
    );

    // Calculate prediction accuracy
    let accuracy = null;
    if (scheduled?.estimatedResources) {
      accuracy = {
        memoryError: Math.abs(
          actualResources.memoryMB - scheduled.estimatedResources.memoryMB
        ),
        memoryErrorPercent: (
          Math.abs(actualResources.memoryMB - scheduled.estimatedResources.memoryMB) /
          actualResources.memoryMB
        ) * 100,
        tokenError: Math.abs(
          actualResources.tokens - scheduled.estimatedResources.tokens
        ),
        tokenErrorPercent: (
          Math.abs(actualResources.tokens - scheduled.estimatedResources.tokens) /
          actualResources.tokens
        ) * 100
      };
    }

    // Record completion
    this.completedTasks.set(taskId, {
      taskId,
      actualResources,
      estimatedResources: scheduled?.estimatedResources,
      accuracy,
      completedAt: new Date().toISOString()
    });

    // Cleanup
    this.scheduledTasks.delete(taskId);
    this.runningTasks.delete(taskId);
    this.stats.completedTasks++;

    // Emit event
    this.emit('task-completed', {
      taskId,
      actualResources,
      accuracy
    });

    return {
      recorded: true,
      taskId,
      learningResult,
      releaseResult,
      accuracy
    };
  }

  /**
   * Get next task to execute (highest priority feasible task)
   */
  getNextTask() {
    const currentCapacity = this.feasibilityChecker.getSystemCapacity();
    const nextTask = this.priorityEngine.getNextTask(currentCapacity.resources);

    if (!nextTask) {
      return null;
    }

    return {
      task: nextTask,
      priority: nextTask.priorityScore,
      estimatedResources: nextTask.estimatedResources
    };
  }

  /**
   * Get current schedule (prioritized task list)
   */
  getSchedule() {
    const queue = this.priorityEngine.getQueue();
    const capacity = this.feasibilityChecker.getSystemCapacity();

    return {
      queue,
      queueDepth: queue.length,
      runningTasks: Array.from(this.runningTasks.values()),
      systemCapacity: capacity,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get system capacity
   */
  getSystemCapacity() {
    return this.feasibilityChecker.getSystemCapacity();
  }

  /**
   * Set resource limits
   */
  setResourceLimits(limits) {
    // Update config
    this.config.resourceLimits = { ...this.config.resourceLimits, ...limits };

    // Update feasibility checker
    return this.feasibilityChecker.setResourceLimits(limits);
  }

  /**
   * Get scheduler statistics
   */
  getStats() {
    const predictorStats = this.predictor.getStats();
    const priorityStats = this.priorityEngine.getStats();
    const capacity = this.feasibilityChecker.getSystemCapacity();

    return {
      scheduler: this.stats,
      predictor: predictorStats,
      priority: priorityStats,
      capacity,
      configuration: this.config
    };
  }

  /**
   * Get prediction accuracy metrics
   */
  getAccuracyMetrics() {
    return this.predictor.getAccuracyMetrics();
  }

  /**
   * Force model retraining
   */
  retrainModels(epochs = 10) {
    return this.predictor.batchTrain(epochs);
  }

  /**
   * Generate task ID
   */
  _generateTaskId() {
    return `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Estimate wait time based on queue
   */
  _estimateQueueWaitTime() {
    const queue = this.priorityEngine.getQueue();

    if (queue.length === 0) {
      return 0;
    }

    // Average estimated duration of queued tasks
    const avgDuration = queue.reduce(
      (sum, task) => sum + (task.estimatedResources?.estimatedDurationMs || 180000),
      0
    ) / queue.length;

    // Estimate based on queue depth and concurrency
    const concurrency = this.config.resourceLimits.maxConcurrentTasks;
    const batchCount = Math.ceil(queue.length / concurrency);

    return avgDuration * batchCount;
  }

  /**
   * Increment rejection reason counter
   */
  _incrementRejectionReason(reason) {
    if (!this.stats.rejectionReasons[reason]) {
      this.stats.rejectionReasons[reason] = 0;
    }
    this.stats.rejectionReasons[reason]++;
  }

  /**
   * Start monitoring loop
   */
  _startMonitoring() {
    // Periodically rebalance priorities
    this.monitoringInterval = setInterval(() => {
      const capacity = this.feasibilityChecker.getSystemCapacity();
      this.priorityEngine.rebalancePriorities(capacity.resources);

      // Emit health status
      this.emit('health-check', {
        capacity,
        queueDepth: this.priorityEngine.getQueue().length,
        runningTasks: this.runningTasks.size
      });
    }, 30000); // Every 30 seconds
  }

  /**
   * Stop scheduler
   */
  stop() {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }

    this.emit('stopped');
  }
}

/**
 * Factory function to create scheduler
 */
function createIntelligentScheduler(options = {}) {
  return new IntelligentScheduler(options);
}

module.exports = {
  IntelligentScheduler,
  createIntelligentScheduler
};
