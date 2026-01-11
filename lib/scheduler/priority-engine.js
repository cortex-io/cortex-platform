/**
 * SLA-Aware Priority Engine
 *
 * Prioritizes tasks based on multiple factors:
 * - SLA deadline proximity
 * - Task type priority weights
 * - Dependency chains
 * - Resource efficiency
 * - Starvation prevention
 *
 * Uses a weighted scoring system to determine execution order.
 */

const fs = require('fs');
const path = require('path');

/**
 * Default priority weights for task types
 */
const DEFAULT_PRIORITY_WEIGHTS = {
  security: 1.5,
  'critical-fix': 1.8,
  implementation: 1.0,
  fix: 1.2,
  review: 0.9,
  test: 0.9,
  documentation: 0.8,
  scan: 1.1,
  'pr-creation': 0.7,
  unknown: 1.0
};

/**
 * Priority level modifiers
 */
const PRIORITY_LEVEL_MULTIPLIERS = {
  P0: 3.0,
  P1: 2.0,
  P2: 1.0,
  P3: 0.5,
  critical: 3.0,
  high: 2.0,
  medium: 1.0,
  low: 0.5
};

/**
 * Priority Engine
 */
class PriorityEngine {
  constructor(options = {}) {
    this.priorityWeights = options.priorityWeights || DEFAULT_PRIORITY_WEIGHTS;
    this.slaConfig = this._loadSlaConfig(options.slaConfigPath);
    this.taskQueue = [];
    this.dependencyGraph = new Map(); // taskId -> [dependentTaskIds]
    this.taskMetadata = new Map(); // taskId -> metadata

    // Starvation prevention
    this.maxWaitTimeMs = options.maxWaitTimeMs || 3600000; // 1 hour
    this.starvationBoostFactor = options.starvationBoostFactor || 0.1; // Boost 10% per hour waiting

    // Performance tracking
    this.stats = {
      totalScored: 0,
      averageScore: 0,
      tasksByPriority: {}
    };
  }

  /**
   * Load SLA configuration
   */
  _loadSlaConfig(configPath) {
    const defaultPath = path.join(process.cwd(), 'coordination', 'config', 'sla-policy.json');
    const slaPath = configPath || defaultPath;

    if (fs.existsSync(slaPath)) {
      try {
        return JSON.parse(fs.readFileSync(slaPath, 'utf8'));
      } catch (error) {
        console.warn('Failed to load SLA config, using defaults:', error.message);
      }
    }

    return {
      global_settings: {
        default_timeout_ms: 300000
      },
      task_type_timeouts: {},
      priority_modifiers: {}
    };
  }

  /**
   * Calculate priority score for a task
   *
   * Score components:
   * 1. Base priority (task type weight × priority level)
   * 2. SLA urgency (deadline proximity)
   * 3. Dependency factor (tasks blocking others get boost)
   * 4. Resource efficiency (tasks that fit current capacity)
   * 5. Starvation prevention (long-waiting tasks get boost)
   */
  calculatePriority(task, currentCapacity = null) {
    this.stats.totalScored++;

    // 1. Base Priority Score (0-10 scale)
    const taskType = this._normalizeTaskType(task.type || task.taskType);
    const typeWeight = this.priorityWeights[taskType] || 1.0;
    const levelMultiplier = this._getPriorityLevelMultiplier(task.priority);
    const baseScore = typeWeight * levelMultiplier * 3; // Scale to ~0-10

    // 2. SLA Urgency Score (0-10 scale)
    const slaScore = this._calculateSlaUrgency(task);

    // 3. Dependency Score (0-5 scale)
    const dependencyScore = this._calculateDependencyScore(task.id || task.taskId);

    // 4. Resource Efficiency Score (0-5 scale)
    const efficiencyScore = currentCapacity
      ? this._calculateResourceEfficiency(task, currentCapacity)
      : 2.5;

    // 5. Starvation Prevention Score (0-10 scale)
    const starvationScore = this._calculateStarvationBoost(task);

    // Weighted combination
    const weights = {
      base: 0.25,
      sla: 0.30,
      dependency: 0.15,
      efficiency: 0.15,
      starvation: 0.15
    };

    const totalScore =
      baseScore * weights.base +
      slaScore * weights.sla +
      dependencyScore * weights.dependency +
      efficiencyScore * weights.efficiency +
      starvationScore * weights.starvation;

    // Track statistics
    this.stats.averageScore = (this.stats.averageScore * (this.stats.totalScored - 1) + totalScore) / this.stats.totalScored;

    const taskPriorityKey = task.priority || 'unknown';
    this.stats.tasksByPriority[taskPriorityKey] = (this.stats.tasksByPriority[taskPriorityKey] || 0) + 1;

    return {
      totalScore,
      components: {
        base: baseScore,
        sla: slaScore,
        dependency: dependencyScore,
        efficiency: efficiencyScore,
        starvation: starvationScore
      },
      weights,
      taskType,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Normalize task type
   */
  _normalizeTaskType(type) {
    const typeStr = String(type || 'unknown').toLowerCase();

    if (typeStr.includes('secur') || typeStr.includes('audit')) return 'security';
    if (typeStr.includes('critical') && typeStr.includes('fix')) return 'critical-fix';
    if (typeStr.includes('implement') || typeStr.includes('feature')) return 'implementation';
    if (typeStr.includes('fix') || typeStr.includes('bug')) return 'fix';
    if (typeStr.includes('review')) return 'review';
    if (typeStr.includes('test')) return 'test';
    if (typeStr.includes('doc')) return 'documentation';
    if (typeStr.includes('scan')) return 'scan';
    if (typeStr.includes('pr')) return 'pr-creation';

    return 'unknown';
  }

  /**
   * Get priority level multiplier
   */
  _getPriorityLevelMultiplier(priority) {
    if (!priority) return 1.0;

    return PRIORITY_LEVEL_MULTIPLIERS[priority] || 1.0;
  }

  /**
   * Calculate SLA urgency score based on deadline proximity
   *
   * Urgency increases exponentially as deadline approaches:
   * - >80% time remaining: low urgency (2-4)
   * - 50-80% time remaining: medium urgency (4-6)
   * - 20-50% time remaining: high urgency (6-8)
   * - <20% time remaining: critical urgency (8-10)
   */
  _calculateSlaUrgency(task) {
    const now = Date.now();
    const createdAt = task.createdAt ? new Date(task.createdAt).getTime() : now;
    const deadline = task.deadline ? new Date(task.deadline).getTime() : null;

    // If no explicit deadline, use SLA timeout
    let deadlineTime = deadline;
    if (!deadlineTime) {
      const taskType = this._normalizeTaskType(task.type);
      const slaTimeout = this.slaConfig.task_type_timeouts?.[taskType]?.timeout_ms ||
                         this.slaConfig.global_settings?.default_timeout_ms ||
                         300000;

      // Apply priority modifier
      const priorityModifier = this.slaConfig.priority_modifiers?.[task.priority]?.timeout_multiplier || 1.0;
      const adjustedTimeout = slaTimeout * priorityModifier;

      deadlineTime = createdAt + adjustedTimeout;
    }

    const totalTime = deadlineTime - createdAt;
    const remainingTime = deadlineTime - now;
    const elapsedPercent = ((totalTime - remainingTime) / totalTime) * 100;

    // Calculate urgency score
    let urgencyScore;
    if (remainingTime <= 0) {
      urgencyScore = 10; // Overdue - maximum urgency
    } else if (elapsedPercent >= 80) {
      urgencyScore = 8 + (elapsedPercent - 80) / 10; // 8-10
    } else if (elapsedPercent >= 50) {
      urgencyScore = 6 + (elapsedPercent - 50) / 15; // 6-8
    } else if (elapsedPercent >= 20) {
      urgencyScore = 4 + (elapsedPercent - 20) / 15; // 4-6
    } else {
      urgencyScore = 2 + elapsedPercent / 10; // 2-4
    }

    return Math.min(10, Math.max(0, urgencyScore));
  }

  /**
   * Calculate dependency score
   * Tasks that block other tasks get higher priority
   */
  _calculateDependencyScore(taskId) {
    if (!taskId) return 0;

    // Count how many tasks depend on this one
    const dependentCount = this.dependencyGraph.get(taskId)?.length || 0;

    // Score based on number of dependent tasks
    // 0 dependents: 0 points
    // 1-2 dependents: 2 points
    // 3-5 dependents: 4 points
    // 6+ dependents: 5 points
    if (dependentCount === 0) return 0;
    if (dependentCount <= 2) return 2;
    if (dependentCount <= 5) return 4;
    return 5;
  }

  /**
   * Calculate resource efficiency score
   * Tasks that fit well within current capacity get boost
   */
  _calculateResourceEfficiency(task, currentCapacity) {
    if (!task.estimatedResources || !currentCapacity) {
      return 2.5; // Neutral score if no data
    }

    const memoryFit = currentCapacity.availableMemoryMB > 0
      ? Math.min(task.estimatedResources.estimatedMemoryMB / currentCapacity.availableMemoryMB, 1)
      : 0;

    const workerFit = currentCapacity.availableWorkerSlots > 0 ? 1 : 0;

    // Prefer tasks that use 30-70% of available memory (good utilization, not too greedy)
    let efficiencyScore;
    if (memoryFit <= 0.3) {
      efficiencyScore = 3 + memoryFit * 6.67; // 3-5 for small tasks
    } else if (memoryFit <= 0.7) {
      efficiencyScore = 5; // Optimal range
    } else {
      efficiencyScore = 5 - (memoryFit - 0.7) * 16.67; // 5-0 for large tasks
    }

    // Apply worker availability
    efficiencyScore *= workerFit ? 1 : 0.5;

    return Math.max(0, Math.min(5, efficiencyScore));
  }

  /**
   * Calculate starvation prevention boost
   * Tasks waiting too long get progressive priority boost
   */
  _calculateStarvationBoost(task) {
    const now = Date.now();
    const createdAt = task.createdAt ? new Date(task.createdAt).getTime() : now;
    const waitTimeMs = now - createdAt;

    if (waitTimeMs <= 0) return 0;

    // Progressive boost based on wait time
    const hoursWaiting = waitTimeMs / 3600000;
    const boostScore = Math.min(10, hoursWaiting * (this.starvationBoostFactor * 10));

    return boostScore;
  }

  /**
   * Add task to queue with priority calculation
   */
  addTask(task, currentCapacity = null) {
    const priorityInfo = this.calculatePriority(task, currentCapacity);

    const queueEntry = {
      ...task,
      priorityScore: priorityInfo.totalScore,
      priorityComponents: priorityInfo.components,
      addedAt: new Date().toISOString()
    };

    this.taskQueue.push(queueEntry);
    this.taskMetadata.set(task.id || task.taskId, queueEntry);

    // Rebalance queue
    this._sortQueue();

    return {
      added: true,
      position: this.taskQueue.findIndex(t => (t.id || t.taskId) === (task.id || task.taskId)),
      priorityScore: priorityInfo.totalScore,
      queueSize: this.taskQueue.length
    };
  }

  /**
   * Remove task from queue
   */
  removeTask(taskId) {
    const index = this.taskQueue.findIndex(t => (t.id || t.taskId) === taskId);

    if (index >= 0) {
      const removed = this.taskQueue.splice(index, 1)[0];
      this.taskMetadata.delete(taskId);
      this.dependencyGraph.delete(taskId);

      return {
        removed: true,
        task: removed
      };
    }

    return { removed: false };
  }

  /**
   * Add dependency relationship
   */
  addDependency(taskId, dependsOn) {
    if (!this.dependencyGraph.has(dependsOn)) {
      this.dependencyGraph.set(dependsOn, []);
    }

    this.dependencyGraph.get(dependsOn).push(taskId);
  }

  /**
   * Get next task to execute
   */
  getNextTask(currentCapacity = null) {
    if (this.taskQueue.length === 0) {
      return null;
    }

    // Rebalance priorities based on current capacity
    if (currentCapacity) {
      this.rebalancePriorities(currentCapacity);
    }

    // Return highest priority feasible task
    return this.taskQueue[0];
  }

  /**
   * Rebalance priorities based on changing conditions
   */
  rebalancePriorities(currentCapacity = null) {
    // Recalculate priorities for all queued tasks
    for (const task of this.taskQueue) {
      const priorityInfo = this.calculatePriority(task, currentCapacity);
      task.priorityScore = priorityInfo.totalScore;
      task.priorityComponents = priorityInfo.components;
    }

    // Re-sort queue
    this._sortQueue();
  }

  /**
   * Sort queue by priority score (descending)
   */
  _sortQueue() {
    this.taskQueue.sort((a, b) => b.priorityScore - a.priorityScore);
  }

  /**
   * Get current queue state
   */
  getQueue() {
    return this.taskQueue.map(task => ({
      id: task.id || task.taskId,
      type: task.type || task.taskType,
      priority: task.priority,
      priorityScore: task.priorityScore,
      priorityComponents: task.priorityComponents,
      addedAt: task.addedAt,
      description: task.description || task.task
    }));
  }

  /**
   * Get queue statistics
   */
  getStats() {
    const queueDepth = this.taskQueue.length;
    const scoreDistribution = this.taskQueue.reduce((dist, task) => {
      const bucket = Math.floor(task.priorityScore);
      dist[bucket] = (dist[bucket] || 0) + 1;
      return dist;
    }, {});

    return {
      queueDepth,
      scoreDistribution,
      totalScored: this.stats.totalScored,
      averageScore: this.stats.averageScore,
      tasksByPriority: this.stats.tasksByPriority,
      oldestTask: this.taskQueue.length > 0 ? this.taskQueue[this.taskQueue.length - 1].addedAt : null,
      newestTask: this.taskQueue.length > 0 ? this.taskQueue[0].addedAt : null
    };
  }

  /**
   * Clear queue
   */
  clear() {
    this.taskQueue = [];
    this.taskMetadata.clear();
    this.dependencyGraph.clear();
  }
}

module.exports = {
  PriorityEngine,
  DEFAULT_PRIORITY_WEIGHTS,
  PRIORITY_LEVEL_MULTIPLIERS
};
