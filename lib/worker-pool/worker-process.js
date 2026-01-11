/**
 * Persistent Worker Process
 * Long-running process that receives and executes tasks via IPC
 */

const path = require('path');
const { EventEmitter } = require('events');
const v8 = require('v8');
const os = require('os');

class WorkerProcess extends EventEmitter {
  constructor(workerId, config = {}) {
    super();
    this.workerId = workerId;
    this.config = {
      heartbeatInterval: config.heartbeatInterval || 5000,
      memoryThresholdMB: config.memoryThresholdMB || 512,
      idleTimeoutMs: config.idleTimeoutMs || 300000, // 5 minutes
      ...config
    };

    this.state = 'initializing';
    this.currentTask = null;
    this.tasksExecuted = 0;
    this.startTime = Date.now();
    this.lastTaskTime = null;
    this.lastHeartbeat = Date.now();
    this.heartbeatTimer = null;
    this.shouldShutdown = false;
    this.taskHandlers = new Map();

    this._setupProcessHandlers();
    this._startHeartbeat();
  }

  /**
   * Initialize worker and wait for tasks
   */
  async start() {
    this.state = 'ready';
    this._log('info', 'Worker started and ready for tasks');

    // Send ready message to parent
    this._sendToParent({
      type: 'worker-ready',
      workerId: this.workerId,
      pid: process.pid,
      timestamp: Date.now()
    });

    // Listen for messages from parent
    process.on('message', async (message) => {
      await this._handleMessage(message);
    });
  }

  /**
   * Register a task handler
   * @param {string} taskType - Type of task (e.g., 'implementation', 'analysis')
   * @param {Function} handler - Async function to handle the task
   */
  registerTaskHandler(taskType, handler) {
    this.taskHandlers.set(taskType, handler);
    this._log('debug', `Registered handler for task type: ${taskType}`);
  }

  /**
   * Handle incoming message from parent
   */
  async _handleMessage(message) {
    try {
      switch (message.type) {
        case 'execute-task':
          await this._executeTask(message.task);
          break;

        case 'shutdown':
          await this._handleShutdown(message.graceful);
          break;

        case 'health-check':
          this._sendHealthStatus();
          break;

        case 'get-metrics':
          this._sendMetrics();
          break;

        default:
          this._log('warning', `Unknown message type: ${message.type}`);
      }
    } catch (error) {
      this._log('error', `Error handling message: ${error.message}`, error);
    }
  }

  /**
   * Execute a task
   */
  async _executeTask(task) {
    const startTime = Date.now();
    this.state = 'busy';
    this.currentTask = task;

    this._log('info', `Executing task ${task.id} of type ${task.type}`);

    try {
      // Get handler for this task type
      const handler = this.taskHandlers.get(task.type);
      if (!handler) {
        throw new Error(`No handler registered for task type: ${task.type}`);
      }

      // Execute task with timeout
      const timeoutMs = task.timeout || 300000; // 5 minutes default
      const result = await this._executeWithTimeout(
        handler(task.payload),
        timeoutMs
      );

      const duration = Date.now() - startTime;

      // Send success result
      this._sendToParent({
        type: 'task-complete',
        taskId: task.id,
        workerId: this.workerId,
        result,
        duration,
        timestamp: Date.now()
      });

      this.tasksExecuted++;
      this.lastTaskTime = Date.now();

      this._log('info', `Task ${task.id} completed in ${duration}ms`);

      // Cleanup after task
      await this._cleanupAfterTask();

    } catch (error) {
      const duration = Date.now() - startTime;

      this._log('error', `Task ${task.id} failed: ${error.message}`, error);

      // Send failure result
      this._sendToParent({
        type: 'task-failed',
        taskId: task.id,
        workerId: this.workerId,
        error: {
          message: error.message,
          stack: error.stack,
          code: error.code
        },
        duration,
        timestamp: Date.now()
      });

      // Cleanup after task
      await this._cleanupAfterTask();
    } finally {
      this.currentTask = null;
      this.state = 'ready';
    }
  }

  /**
   * Execute function with timeout
   */
  async _executeWithTimeout(promise, timeoutMs) {
    return Promise.race([
      promise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`Task timeout after ${timeoutMs}ms`)), timeoutMs)
      )
    ]);
  }

  /**
   * Cleanup memory and resources after task execution
   */
  async _cleanupAfterTask() {
    try {
      // Clear module cache for dynamic requires (if any)
      // This is aggressive but ensures clean state
      const modulesBefore = Object.keys(require.cache).length;

      // Keep core modules, remove others
      const coreModules = ['path', 'fs', 'util', 'events', 'stream', 'child_process'];
      for (const key in require.cache) {
        const moduleName = require.cache[key].id;
        const isCore = coreModules.some(core => moduleName.includes(core));
        const isSelf = moduleName.includes('worker-process.js');

        if (!isCore && !isSelf && !moduleName.includes('node_modules')) {
          delete require.cache[key];
        }
      }

      const modulesAfter = Object.keys(require.cache).length;
      if (modulesBefore !== modulesAfter) {
        this._log('debug', `Cleared ${modulesBefore - modulesAfter} modules from cache`);
      }

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
        this._log('debug', 'Forced garbage collection');
      }

      // Check memory usage
      const memUsage = process.memoryUsage();
      const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);

      if (heapUsedMB > this.config.memoryThresholdMB) {
        this._log('warning', `High memory usage: ${heapUsedMB}MB (threshold: ${this.config.memoryThresholdMB}MB)`);
        this._sendToParent({
          type: 'high-memory-warning',
          workerId: this.workerId,
          memoryMB: heapUsedMB,
          threshold: this.config.memoryThresholdMB
        });
      }

    } catch (error) {
      this._log('error', `Cleanup error: ${error.message}`, error);
    }
  }

  /**
   * Start heartbeat emission
   */
  _startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      this._sendHeartbeat();
    }, this.config.heartbeatInterval);
  }

  /**
   * Send heartbeat to parent
   */
  _sendHeartbeat() {
    const memUsage = process.memoryUsage();
    const cpuUsage = process.cpuUsage();

    this.lastHeartbeat = Date.now();

    this._sendToParent({
      type: 'heartbeat',
      workerId: this.workerId,
      pid: process.pid,
      state: this.state,
      tasksExecuted: this.tasksExecuted,
      uptime: Date.now() - this.startTime,
      memoryUsage: {
        heapUsed: memUsage.heapUsed,
        heapTotal: memUsage.heapTotal,
        rss: memUsage.rss,
        external: memUsage.external
      },
      cpuUsage: {
        user: cpuUsage.user,
        system: cpuUsage.system
      },
      currentTask: this.currentTask ? this.currentTask.id : null,
      timestamp: Date.now()
    });
  }

  /**
   * Send health status
   */
  _sendHealthStatus() {
    const memUsage = process.memoryUsage();
    const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);
    const heapTotalMB = Math.round(memUsage.heapTotal / 1024 / 1024);

    const health = {
      workerId: this.workerId,
      pid: process.pid,
      state: this.state,
      healthy: this.state !== 'error' && heapUsedMB < this.config.memoryThresholdMB,
      memoryMB: heapUsedMB,
      memoryTotalMB: heapTotalMB,
      tasksExecuted: this.tasksExecuted,
      uptime: Date.now() - this.startTime,
      lastTaskAge: this.lastTaskTime ? Date.now() - this.lastTaskTime : null
    };

    this._sendToParent({
      type: 'health-status',
      ...health,
      timestamp: Date.now()
    });
  }

  /**
   * Send detailed metrics
   */
  _sendMetrics() {
    const memUsage = process.memoryUsage();
    const cpuUsage = process.cpuUsage();
    const heapStats = v8.getHeapStatistics();

    const metrics = {
      workerId: this.workerId,
      pid: process.pid,
      tasksExecuted: this.tasksExecuted,
      uptime: Date.now() - this.startTime,
      memory: {
        heapUsed: memUsage.heapUsed,
        heapTotal: memUsage.heapTotal,
        rss: memUsage.rss,
        external: memUsage.external,
        arrayBuffers: memUsage.arrayBuffers
      },
      cpu: {
        user: cpuUsage.user,
        system: cpuUsage.system
      },
      heap: {
        totalHeapSize: heapStats.total_heap_size,
        usedHeapSize: heapStats.used_heap_size,
        heapSizeLimit: heapStats.heap_size_limit,
        mallocedMemory: heapStats.malloced_memory
      },
      loadAverage: os.loadavg()
    };

    this._sendToParent({
      type: 'worker-metrics',
      metrics,
      timestamp: Date.now()
    });
  }

  /**
   * Handle shutdown request
   */
  async _handleShutdown(graceful = true) {
    this.shouldShutdown = true;
    this._log('info', `Shutdown requested (graceful: ${graceful})`);

    if (graceful && this.currentTask) {
      // Wait for current task to complete
      this._log('info', 'Waiting for current task to complete...');
      this.state = 'shutting-down';

      // The task will finish naturally and then we can shutdown
      // Set a timeout to force shutdown if task takes too long
      setTimeout(() => {
        if (this.currentTask) {
          this._log('warning', 'Force shutdown - task did not complete in time');
          this._performShutdown();
        }
      }, 30000); // 30 second grace period

    } else {
      // Immediate shutdown
      this._performShutdown();
    }
  }

  /**
   * Perform actual shutdown
   */
  _performShutdown() {
    this._log('info', 'Shutting down worker');

    // Stop heartbeat
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }

    // Send shutdown confirmation
    this._sendToParent({
      type: 'worker-shutdown',
      workerId: this.workerId,
      tasksExecuted: this.tasksExecuted,
      uptime: Date.now() - this.startTime,
      timestamp: Date.now()
    });

    // Exit process
    setTimeout(() => {
      process.exit(0);
    }, 100);
  }

  /**
   * Setup process-level handlers
   */
  _setupProcessHandlers() {
    process.on('uncaughtException', (error) => {
      this._log('error', `Uncaught exception: ${error.message}`, error);
      this.state = 'error';

      this._sendToParent({
        type: 'worker-error',
        workerId: this.workerId,
        error: {
          message: error.message,
          stack: error.stack
        },
        fatal: true,
        timestamp: Date.now()
      });

      // Give time to send message, then exit
      setTimeout(() => process.exit(1), 1000);
    });

    process.on('unhandledRejection', (reason, promise) => {
      this._log('error', `Unhandled rejection: ${reason}`);
      this._sendToParent({
        type: 'worker-error',
        workerId: this.workerId,
        error: {
          message: String(reason),
          type: 'unhandledRejection'
        },
        fatal: false,
        timestamp: Date.now()
      });
    });

    process.on('SIGTERM', () => {
      this._handleShutdown(true);
    });

    process.on('SIGINT', () => {
      this._handleShutdown(true);
    });
  }

  /**
   * Send message to parent process
   */
  _sendToParent(message) {
    if (process.send) {
      process.send(message);
    }
  }

  /**
   * Log message
   */
  _log(level, message, error = null) {
    const logEntry = {
      level,
      workerId: this.workerId,
      pid: process.pid,
      message,
      timestamp: new Date().toISOString()
    };

    if (error) {
      logEntry.error = {
        message: error.message,
        stack: error.stack
      };
    }

    // Send to parent for centralized logging
    this._sendToParent({
      type: 'worker-log',
      ...logEntry
    });

    // Also log locally
    const prefix = `[Worker ${this.workerId}]`;
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
  }
}

module.exports = WorkerProcess;

// If this file is run directly as a worker process
if (require.main === module) {
  const workerId = process.env.WORKER_ID || 'unknown';
  const config = process.env.WORKER_CONFIG ? JSON.parse(process.env.WORKER_CONFIG) : {};

  const worker = new WorkerProcess(workerId, config);

  // Register default task handlers
  // These can be customized based on your needs
  worker.registerTaskHandler('implementation', async (payload) => {
    // Placeholder for actual implementation logic
    // This would integrate with your existing task execution code
    return { status: 'completed', result: payload };
  });

  worker.registerTaskHandler('analysis', async (payload) => {
    // Placeholder for analysis tasks
    return { status: 'completed', result: payload };
  });

  worker.registerTaskHandler('test', async (payload) => {
    // Placeholder for test tasks
    return { status: 'completed', result: payload };
  });

  // Start the worker
  worker.start().catch((error) => {
    console.error('Failed to start worker:', error);
    process.exit(1);
  });
}
