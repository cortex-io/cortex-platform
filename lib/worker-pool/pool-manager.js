/**
 * Worker Pool Manager
 * Manages persistent worker processes with automatic zombie detection and cleanup
 */

const { fork } = require('child_process');
const path = require('path');
const { EventEmitter } = require('events');
const TaskQueue = require('./task-queue');
const HealthMonitor = require('./health-monitor');

class WorkerPoolManager extends EventEmitter {
  constructor(config = {}) {
    super();
    this.config = {
      poolSize: config.poolSize || 20,
      minWorkers: config.minWorkers || 5,
      maxWorkers: config.maxWorkers || 50,
      workerScript: config.workerScript || path.join(__dirname, 'worker-process.js'),
      fifoDir: config.fifoDir || '/tmp/cortex/workers',
      heartbeatInterval: config.heartbeatInterval || 5000,
      taskTimeout: config.taskTimeout || 300000, // 5 minutes
      loadBalancing: config.loadBalancing || 'round-robin', // round-robin, least-loaded, capability-based
      autoRestart: config.autoRestart !== false, // default true
      maxRestartAttempts: config.maxRestartAttempts || 3,
      workerMemoryLimitMB: config.workerMemoryLimitMB || 512,
      ...config
    };

    this.workers = new Map(); // workerId -> worker data
    this.taskQueue = new TaskQueue({
      maxRetries: config.maxTaskRetries || 3,
      taskTimeoutMs: this.config.taskTimeout
    });
    this.healthMonitor = new HealthMonitor({
      heartbeatTimeoutMs: this.config.heartbeatInterval * 3,
      memoryThresholdMB: this.config.workerMemoryLimitMB,
      maxRestartAttempts: this.config.maxRestartAttempts
    });

    this.nextWorkerId = 0;
    this.roundRobinIndex = 0;
    this.initialized = false;
    this.shuttingDown = false;
    this.pendingTasks = new Map(); // taskId -> { resolve, reject, timeout }

    // Statistics
    this.stats = {
      tasksSubmitted: 0,
      tasksCompleted: 0,
      tasksFailed: 0,
      workersSpawned: 0,
      workersRestarted: 0,
      workersCrashed: 0,
      totalWorkerReuse: 0,
      startTime: Date.now()
    };

    this._setupEventHandlers();
  }

  /**
   * Initialize the worker pool
   */
  async initialize(poolSize = this.config.poolSize) {
    if (this.initialized) {
      throw new Error('Pool already initialized');
    }

    this.config.poolSize = Math.max(
      this.config.minWorkers,
      Math.min(poolSize, this.config.maxWorkers)
    );

    this._log('info', `Initializing worker pool with ${this.config.poolSize} workers`);

    // Start health monitoring
    this.healthMonitor.start();

    // Spawn initial workers
    const spawnPromises = [];
    for (let i = 0; i < this.config.poolSize; i++) {
      spawnPromises.push(this._spawnWorker());
    }

    try {
      await Promise.all(spawnPromises);
      this.initialized = true;
      this._log('info', `Worker pool initialized with ${this.workers.size} workers`);
      this.emit('pool-initialized', {
        poolSize: this.workers.size,
        config: this.config
      });
    } catch (error) {
      this._log('error', `Failed to initialize pool: ${error.message}`);
      throw error;
    }
  }

  /**
   * Submit a task to the pool
   * @param {Object} task - Task object with type and payload
   * @returns {Promise<any>} Task result
   */
  async submitTask(task) {
    if (!this.initialized) {
      throw new Error('Pool not initialized');
    }

    if (this.shuttingDown) {
      throw new Error('Pool is shutting down');
    }

    this.stats.tasksSubmitted++;

    return new Promise((resolve, reject) => {
      // Enqueue task
      const taskId = this.taskQueue.enqueue(task, task.priority || 10);

      // Store promise handlers
      this.pendingTasks.set(taskId, { resolve, reject });

      // Try to assign task immediately
      this._assignTasks();

      // Set timeout
      const timeout = setTimeout(() => {
        const pending = this.pendingTasks.get(taskId);
        if (pending) {
          this.pendingTasks.delete(taskId);
          this.taskQueue.failTask(taskId, new Error('Task timeout'));
          reject(new Error(`Task ${taskId} timed out`));
        }
      }, task.timeout || this.config.taskTimeout);

      // Update timeout in pending task
      const pending = this.pendingTasks.get(taskId);
      if (pending) {
        pending.timeout = timeout;
      }
    });
  }

  /**
   * Assign queued tasks to available workers
   */
  _assignTasks() {
    // Get available workers
    const availableWorkers = this._getAvailableWorkers();

    if (availableWorkers.length === 0) {
      return; // No workers available
    }

    // Assign tasks while we have both tasks and workers
    while (this.taskQueue.getQueueDepth() > 0 && availableWorkers.length > 0) {
      const task = this.taskQueue.dequeue();
      if (!task) break;

      const worker = this._selectWorker(availableWorkers);
      if (!worker) break;

      this._assignTaskToWorker(task, worker);

      // Remove worker from available list
      const index = availableWorkers.indexOf(worker);
      if (index > -1) {
        availableWorkers.splice(index, 1);
      }
    }
  }

  /**
   * Get list of available workers
   */
  _getAvailableWorkers() {
    const available = [];
    for (const worker of this.workers.values()) {
      if (worker.state === 'ready' && worker.healthy && worker.process) {
        available.push(worker);
      }
    }
    return available;
  }

  /**
   * Select a worker based on load balancing strategy
   */
  _selectWorker(availableWorkers) {
    if (availableWorkers.length === 0) {
      return null;
    }

    switch (this.config.loadBalancing) {
      case 'round-robin':
        return this._selectRoundRobin(availableWorkers);

      case 'least-loaded':
        return this._selectLeastLoaded(availableWorkers);

      case 'capability-based':
        // For future: select based on worker capabilities
        return this._selectRoundRobin(availableWorkers);

      default:
        return availableWorkers[0];
    }
  }

  /**
   * Round-robin worker selection
   */
  _selectRoundRobin(availableWorkers) {
    const worker = availableWorkers[this.roundRobinIndex % availableWorkers.length];
    this.roundRobinIndex++;
    return worker;
  }

  /**
   * Least-loaded worker selection
   */
  _selectLeastLoaded(availableWorkers) {
    return availableWorkers.reduce((least, worker) => {
      if (!least || worker.tasksExecuted < least.tasksExecuted) {
        return worker;
      }
      return least;
    }, null);
  }

  /**
   * Assign task to specific worker
   */
  _assignTaskToWorker(task, worker) {
    worker.state = 'busy';
    worker.currentTask = task.id;

    this.emit('task-assigned', {
      taskId: task.id,
      workerId: worker.id,
      queuedTimeMs: Date.now() - task.enqueuedAt
    });

    // Send task to worker
    try {
      worker.process.send({
        type: 'execute-task',
        task: {
          id: task.id,
          type: task.task.type,
          payload: task.task.payload,
          timeout: task.timeoutMs
        }
      });

      this.stats.totalWorkerReuse++;

    } catch (error) {
      this._log('error', `Failed to send task to worker ${worker.id}: ${error.message}`);
      // Return task to queue
      worker.state = 'ready';
      worker.currentTask = null;
      this.taskQueue.failTask(task.id, error);
    }
  }

  /**
   * Spawn a new worker process
   */
  async _spawnWorker() {
    const workerId = `worker-${this.nextWorkerId++}`;

    this._log('info', `Spawning worker ${workerId}`);

    const workerProcess = fork(this.config.workerScript, [], {
      env: {
        ...process.env,
        WORKER_ID: workerId,
        WORKER_CONFIG: JSON.stringify({
          heartbeatInterval: this.config.heartbeatInterval,
          memoryThresholdMB: this.config.workerMemoryLimitMB
        })
      },
      execArgv: ['--expose-gc'] // Enable manual garbage collection
    });

    const worker = {
      id: workerId,
      process: workerProcess,
      pid: workerProcess.pid,
      state: 'initializing',
      healthy: true,
      tasksExecuted: 0,
      currentTask: null,
      spawnedAt: Date.now(),
      lastActivity: Date.now(),
      restartCount: 0
    };

    this.workers.set(workerId, worker);
    this.stats.workersSpawned++;

    // Register with health monitor
    this.healthMonitor.registerWorker(workerId, {
      pid: workerProcess.pid
    });

    // Setup process event handlers
    this._setupWorkerHandlers(worker);

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error(`Worker ${workerId} failed to start within timeout`));
      }, 10000);

      const readyHandler = (message) => {
        if (message.type === 'worker-ready' && message.workerId === workerId) {
          clearTimeout(timeout);
          worker.state = 'ready';
          this._log('info', `Worker ${workerId} ready (PID: ${worker.pid})`);
          resolve(worker);
        }
      };

      workerProcess.on('message', readyHandler);
    });
  }

  /**
   * Setup event handlers for a worker process
   */
  _setupWorkerHandlers(worker) {
    const { process: workerProcess, id: workerId } = worker;

    workerProcess.on('message', (message) => {
      this._handleWorkerMessage(workerId, message);
    });

    workerProcess.on('error', (error) => {
      this._log('error', `Worker ${workerId} error: ${error.message}`);
      this._handleWorkerError(workerId, error);
    });

    workerProcess.on('exit', (code, signal) => {
      this._log('warning', `Worker ${workerId} exited with code ${code}, signal ${signal}`);
      this._handleWorkerExit(workerId, code, signal);
    });
  }

  /**
   * Handle messages from worker
   */
  _handleWorkerMessage(workerId, message) {
    const worker = this.workers.get(workerId);
    if (!worker) return;

    worker.lastActivity = Date.now();

    switch (message.type) {
      case 'worker-ready':
        worker.state = 'ready';
        this._assignTasks(); // Try to assign tasks
        break;

      case 'heartbeat':
        this.healthMonitor.recordHeartbeat(workerId, message);
        break;

      case 'task-complete':
        this._handleTaskComplete(workerId, message);
        break;

      case 'task-failed':
        this._handleTaskFailed(workerId, message);
        break;

      case 'worker-log':
        this._handleWorkerLog(workerId, message);
        break;

      case 'high-memory-warning':
        this._log('warning', `Worker ${workerId} high memory: ${message.memoryMB}MB`);
        break;

      case 'worker-error':
        this._handleWorkerError(workerId, new Error(message.error.message));
        break;

      default:
        // Unknown message type
        break;
    }
  }

  /**
   * Handle task completion
   */
  _handleTaskComplete(workerId, message) {
    const worker = this.workers.get(workerId);
    if (worker) {
      worker.state = 'ready';
      worker.currentTask = null;
      worker.tasksExecuted++;
    }

    const { taskId, result, duration } = message;

    // Complete task in queue
    this.taskQueue.completeTask(taskId, result);

    // Resolve pending promise
    const pending = this.pendingTasks.get(taskId);
    if (pending) {
      clearTimeout(pending.timeout);
      pending.resolve(result);
      this.pendingTasks.delete(taskId);
    }

    this.stats.tasksCompleted++;

    this.emit('task-completed', {
      taskId,
      workerId,
      duration,
      workerReused: worker ? worker.tasksExecuted > 1 : false
    });

    // Try to assign more tasks
    this._assignTasks();
  }

  /**
   * Handle task failure
   */
  _handleTaskFailed(workerId, message) {
    const worker = this.workers.get(workerId);
    if (worker) {
      worker.state = 'ready';
      worker.currentTask = null;
    }

    const { taskId, error, duration } = message;
    const errorObj = new Error(error.message);
    errorObj.stack = error.stack;

    // Try to retry task
    const retried = this.taskQueue.failTask(taskId, errorObj);

    if (!retried) {
      // Task moved to DLQ, reject promise
      const pending = this.pendingTasks.get(taskId);
      if (pending) {
        clearTimeout(pending.timeout);
        pending.reject(errorObj);
        this.pendingTasks.delete(taskId);
      }

      this.stats.tasksFailed++;
    }

    this.emit('task-failed', {
      taskId,
      workerId,
      error: error.message,
      duration,
      retried
    });

    // Try to assign more tasks
    this._assignTasks();
  }

  /**
   * Handle worker log
   */
  _handleWorkerLog(workerId, message) {
    const prefix = `[Worker ${workerId}]`;
    const logMessage = `${prefix} ${message.message}`;

    switch (message.level) {
      case 'error':
        if (this.config.logWorkerErrors !== false) {
          console.error(logMessage);
        }
        break;
      case 'warning':
        if (this.config.logWorkerWarnings !== false) {
          console.warn(logMessage);
        }
        break;
      case 'info':
        if (this.config.logWorkerInfo) {
          console.log(logMessage);
        }
        break;
      case 'debug':
        if (this.config.logWorkerDebug) {
          console.log(logMessage);
        }
        break;
    }

    this.emit('worker-log', { workerId, ...message });
  }

  /**
   * Handle worker error
   */
  _handleWorkerError(workerId, error) {
    const worker = this.workers.get(workerId);
    if (!worker) return;

    worker.healthy = false;

    this.emit('worker-error', {
      workerId,
      pid: worker.pid,
      error: error.message
    });

    // Attempt restart if enabled
    if (this.config.autoRestart) {
      this._restartWorker(workerId);
    }
  }

  /**
   * Handle worker exit
   */
  _handleWorkerExit(workerId, code, signal) {
    const worker = this.workers.get(workerId);
    if (!worker) return;

    this.stats.workersCrashed++;

    // Fail current task if any
    if (worker.currentTask) {
      const error = new Error(`Worker crashed (exit code: ${code}, signal: ${signal})`);
      this.taskQueue.failTask(worker.currentTask, error);
    }

    this.healthMonitor.unregisterWorker(workerId);

    this.emit('worker-exited', {
      workerId,
      pid: worker.pid,
      code,
      signal,
      uptime: Date.now() - worker.spawnedAt
    });

    // Remove worker
    this.workers.delete(workerId);

    // Respawn if auto-restart enabled and not shutting down
    if (this.config.autoRestart && !this.shuttingDown) {
      this._log('info', `Respawning worker to maintain pool size`);
      this._spawnWorker().catch(error => {
        this._log('error', `Failed to respawn worker: ${error.message}`);
      });
    }
  }

  /**
   * Restart a worker
   */
  async _restartWorker(workerId) {
    const worker = this.workers.get(workerId);
    if (!worker) return;

    if (!this.healthMonitor.shouldRestartWorker(workerId)) {
      this._log('warning', `Not restarting worker ${workerId} - max attempts reached or cooldown active`);
      return;
    }

    this._log('info', `Restarting worker ${workerId}`);
    this.stats.workersRestarted++;
    this.healthMonitor.recordRestartAttempt(workerId);

    // Kill old process
    try {
      worker.process.kill('SIGTERM');
      // Give it 5 seconds to die gracefully
      await new Promise(resolve => setTimeout(resolve, 5000));
      if (!worker.process.killed) {
        worker.process.kill('SIGKILL');
      }
    } catch (error) {
      this._log('error', `Error killing worker ${workerId}: ${error.message}`);
    }

    // Spawn new worker
    try {
      await this._spawnWorker();
    } catch (error) {
      this._log('error', `Failed to restart worker: ${error.message}`);
    }
  }

  /**
   * Get worker status
   */
  getWorkerStatus(workerId) {
    const worker = this.workers.get(workerId);
    if (!worker) {
      return null;
    }

    const health = this.healthMonitor.getWorkerHealth(workerId);

    return {
      id: worker.id,
      pid: worker.pid,
      state: worker.state,
      healthy: worker.healthy,
      tasksExecuted: worker.tasksExecuted,
      currentTask: worker.currentTask,
      uptime: Date.now() - worker.spawnedAt,
      lastActivity: Date.now() - worker.lastActivity,
      restartCount: worker.restartCount,
      health
    };
  }

  /**
   * Get all workers status
   */
  getAllWorkersStatus() {
    const status = [];
    for (const workerId of this.workers.keys()) {
      status.push(this.getWorkerStatus(workerId));
    }
    return status;
  }

  /**
   * Get pool metrics
   */
  getPoolMetrics() {
    const queueStats = this.taskQueue.getStats();
    const healthSummary = this.healthMonitor.getHealthSummary();
    const uptime = Date.now() - this.stats.startTime;

    const workerReuseRate = this.stats.tasksCompleted > 0
      ? Math.round((this.stats.totalWorkerReuse / this.stats.tasksCompleted) * 100)
      : 0;

    return {
      pool: {
        size: this.workers.size,
        initialized: this.initialized,
        shuttingDown: this.shuttingDown,
        uptime
      },
      workers: {
        total: this.workers.size,
        ready: Array.from(this.workers.values()).filter(w => w.state === 'ready').length,
        busy: Array.from(this.workers.values()).filter(w => w.state === 'busy').length,
        unhealthy: Array.from(this.workers.values()).filter(w => !w.healthy).length
      },
      tasks: {
        submitted: this.stats.tasksSubmitted,
        completed: this.stats.tasksCompleted,
        failed: this.stats.tasksFailed,
        queued: queueStats.queueDepth,
        dlq: queueStats.dlqSize
      },
      performance: {
        workerReuseRate: `${workerReuseRate}%`,
        workersSpawned: this.stats.workersSpawned,
        workersRestarted: this.stats.workersRestarted,
        workersCrashed: this.stats.workersCrashed,
        avgTaskWaitTimeMs: queueStats.avgWaitTimeMs,
        avgTaskDurationMs: queueStats.avgDurationMs
      },
      health: healthSummary,
      queue: queueStats
    };
  }

  /**
   * Scale up the pool
   */
  async scaleUp(count) {
    const targetSize = Math.min(this.workers.size + count, this.config.maxWorkers);
    const toSpawn = targetSize - this.workers.size;

    if (toSpawn <= 0) {
      this._log('info', 'Already at maximum pool size');
      return;
    }

    this._log('info', `Scaling up pool by ${toSpawn} workers`);

    const spawnPromises = [];
    for (let i = 0; i < toSpawn; i++) {
      spawnPromises.push(this._spawnWorker());
    }

    try {
      await Promise.all(spawnPromises);
      this.emit('pool-scaled-up', { count: toSpawn, newSize: this.workers.size });
    } catch (error) {
      this._log('error', `Error scaling up pool: ${error.message}`);
      throw error;
    }
  }

  /**
   * Scale down the pool
   */
  async scaleDown(count) {
    const targetSize = Math.max(this.workers.size - count, this.config.minWorkers);
    const toRemove = this.workers.size - targetSize;

    if (toRemove <= 0) {
      this._log('info', 'Already at minimum pool size');
      return;
    }

    this._log('info', `Scaling down pool by ${toRemove} workers`);

    // Select idle workers to remove
    const workersToRemove = Array.from(this.workers.values())
      .filter(w => w.state === 'ready')
      .slice(0, toRemove);

    for (const worker of workersToRemove) {
      this._shutdownWorker(worker.id);
    }

    this.emit('pool-scaled-down', { count: workersToRemove.length, newSize: this.workers.size });
  }

  /**
   * Shutdown a specific worker
   */
  _shutdownWorker(workerId) {
    const worker = this.workers.get(workerId);
    if (!worker) return;

    try {
      worker.process.send({ type: 'shutdown', graceful: true });
      this.workers.delete(workerId);
      this.healthMonitor.unregisterWorker(workerId);
    } catch (error) {
      this._log('error', `Error shutting down worker ${workerId}: ${error.message}`);
      worker.process.kill('SIGTERM');
    }
  }

  /**
   * Shutdown the entire pool
   */
  async shutdown(graceful = true) {
    if (this.shuttingDown) {
      return;
    }

    this.shuttingDown = true;
    this._log('info', `Shutting down pool (graceful: ${graceful})`);

    // Stop accepting new tasks
    this.taskQueue.clear();

    // Stop health monitoring
    this.healthMonitor.stop();

    if (graceful) {
      // Wait for in-flight tasks to complete (with timeout)
      const timeout = 30000; // 30 seconds
      const startTime = Date.now();

      while (Date.now() - startTime < timeout) {
        const busyWorkers = Array.from(this.workers.values()).filter(w => w.state === 'busy');
        if (busyWorkers.length === 0) break;

        this._log('info', `Waiting for ${busyWorkers.length} workers to complete tasks...`);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }

    // Shutdown all workers
    const shutdownPromises = [];
    for (const workerId of this.workers.keys()) {
      shutdownPromises.push(
        new Promise((resolve) => {
          const worker = this.workers.get(workerId);
          if (worker && worker.process) {
            worker.process.once('exit', resolve);
            this._shutdownWorker(workerId);
            setTimeout(resolve, 5000); // Force timeout
          } else {
            resolve();
          }
        })
      );
    }

    await Promise.all(shutdownPromises);

    this.workers.clear();
    this.emit('pool-shutdown');
    this._log('info', 'Pool shutdown complete');
  }

  /**
   * Setup event handlers
   */
  _setupEventHandlers() {
    // Health monitor events
    this.healthMonitor.on('zombie-detected', ({ workerId }) => {
      this._log('warning', `Zombie worker detected: ${workerId}`);
      if (this.config.autoRestart) {
        this._restartWorker(workerId);
      }
    });

    this.healthMonitor.on('high-memory', ({ workerId, memoryMB }) => {
      this._log('warning', `Worker ${workerId} high memory: ${memoryMB}MB`);
    });

    // Task queue events
    this.taskQueue.on('task-retry-scheduled', ({ taskId, retries, backoffMs }) => {
      this._log('info', `Task ${taskId} scheduled for retry ${retries} after ${backoffMs}ms`);
    });

    this.taskQueue.on('task-failed', ({ taskId, error }) => {
      this._log('error', `Task ${taskId} permanently failed: ${error}`);
    });
  }

  /**
   * Log message
   */
  _log(level, message, error = null) {
    const logEntry = {
      level,
      component: 'PoolManager',
      message,
      timestamp: new Date().toISOString()
    };

    if (error) {
      logEntry.error = {
        message: error.message,
        stack: error.stack
      };
    }

    const prefix = '[PoolManager]';
    switch (level) {
      case 'error':
        console.error(prefix, message, error || '');
        break;
      case 'warning':
        console.warn(prefix, message);
        break;
      case 'info':
        console.log(prefix, message);
        break;
      case 'debug':
        if (process.env.DEBUG) {
          console.log(prefix, message);
        }
        break;
    }

    this.emit('log', logEntry);
  }
}

module.exports = WorkerPoolManager;
