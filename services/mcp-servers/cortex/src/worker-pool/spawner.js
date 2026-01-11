#!/usr/bin/env node

/**
 * Worker Pool Spawner
 *
 * Spawns and manages 1-10,000 worker agents for parallel task execution.
 * Integrates with existing Cortex worker infrastructure.
 */

const { spawn } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const { EventEmitter } = require('events');
const crypto = require('crypto');

class WorkerSpawner extends EventEmitter {
  constructor(config = {}) {
    super();

    this.config = {
      cortexRoot: config.cortexRoot || process.env.CORTEX_ROOT || '/Users/ryandahlberg/Projects/cortex',
      maxWorkers: config.maxWorkers || 10000,
      spawnConcurrency: config.spawnConcurrency || 50, // Spawn N workers in parallel
      workerTimeout: config.workerTimeout || 300000, // 5 minutes default
      healthCheckInterval: config.healthCheckInterval || 30000, // 30 seconds
      autoRestart: config.autoRestart !== false,
      ...config
    };

    // Active workers registry
    this.workers = new Map(); // workerId -> worker metadata
    this.workerProcesses = new Map(); // workerId -> child process

    // Metrics
    this.metrics = {
      totalSpawned: 0,
      totalCompleted: 0,
      totalFailed: 0,
      currentActive: 0,
      averageLifetime: 0
    };

    // Health check interval
    this.healthCheckTimer = null;
  }

  /**
   * Spawn a batch of workers
   * @param {Object} options - Spawn options
   * @returns {Promise<Array>} Array of spawned worker IDs
   */
  async spawnWorkers(options) {
    const {
      count = 1,
      workerType = 'feature-implementer',
      taskSpec = {},
      coordination = {},
      resources = {}
    } = options;

    if (count < 1 || count > this.config.maxWorkers) {
      throw new Error(`Worker count must be between 1 and ${this.config.maxWorkers}`);
    }

    this.emit('spawn_started', { count, workerType });

    const workerIds = [];
    const spawnPromises = [];

    // Spawn workers in batches to avoid overwhelming the system
    for (let i = 0; i < count; i++) {
      const workerId = this._generateWorkerId(workerType);
      workerIds.push(workerId);

      const workerSpec = {
        worker_id: workerId,
        worker_type: workerType,
        task_spec: taskSpec,
        coordination: coordination,
        resources: {
          token_budget: resources.tokenBudget || 50000,
          timeout_minutes: resources.timeout || 60,
          ...resources
        },
        spawned_at: new Date().toISOString()
      };

      spawnPromises.push(this._spawnSingleWorker(workerId, workerSpec));

      // Batch spawning to avoid resource exhaustion
      if (spawnPromises.length >= this.config.spawnConcurrency) {
        await Promise.allSettled(spawnPromises);
        spawnPromises.length = 0;
      }
    }

    // Wait for remaining workers
    if (spawnPromises.length > 0) {
      await Promise.allSettled(spawnPromises);
    }

    this.emit('spawn_completed', {
      count: workerIds.length,
      workerIds,
      active: this.workers.size
    });

    return workerIds;
  }

  /**
   * Spawn a single worker agent
   * @private
   */
  async _spawnSingleWorker(workerId, workerSpec) {
    try {
      // Create worker specification file
      const workerSpecPath = path.join(
        this.config.cortexRoot,
        'coordination/workers/specs',
        `${workerId}.json`
      );

      await fs.mkdir(path.dirname(workerSpecPath), { recursive: true });
      await fs.writeFile(workerSpecPath, JSON.stringify(workerSpec, null, 2));

      // Prepare worker metadata
      const workerMetadata = {
        id: workerId,
        type: workerSpec.worker_type,
        status: 'spawning',
        specPath: workerSpecPath,
        spawnedAt: new Date(),
        taskSpec: workerSpec.task_spec,
        resources: workerSpec.resources
      };

      this.workers.set(workerId, workerMetadata);

      // Spawn worker using Claude CLI (simulated for now)
      // In production, this would invoke the actual worker spawn script
      const workerProcess = await this._launchWorkerProcess(workerId, workerSpec);

      if (workerProcess) {
        this.workerProcesses.set(workerId, workerProcess);
        workerMetadata.status = 'running';
        workerMetadata.pid = workerProcess.pid;
      }

      this.metrics.totalSpawned++;
      this.metrics.currentActive = this.workers.size;

      this.emit('worker_spawned', { workerId, metadata: workerMetadata });

      return workerId;

    } catch (error) {
      this.emit('worker_spawn_failed', { workerId, error: error.message });
      this.workers.delete(workerId);
      throw error;
    }
  }

  /**
   * Launch worker process (integrates with existing Cortex infrastructure)
   * @private
   */
  async _launchWorkerProcess(workerId, workerSpec) {
    return new Promise((resolve, reject) => {
      const workerScriptPath = path.join(
        this.config.cortexRoot,
        'scripts/worker-pool-daemon.sh'
      );

      // Prepare environment
      const env = {
        ...process.env,
        WORKER_ID: workerId,
        WORKER_TYPE: workerSpec.worker_type,
        WORKER_SPEC_PATH: path.join(
          this.config.cortexRoot,
          'coordination/workers/specs',
          `${workerId}.json`
        ),
        CORTEX_ROOT: this.config.cortexRoot
      };

      // Create worker log directory
      const logDir = path.join(this.config.cortexRoot, 'logs/workers');
      const logFile = path.join(logDir, `${workerId}.log`);

      // For now, we'll track the worker without actually spawning a process
      // In production, this would be:
      // const proc = spawn(workerScriptPath, [workerId], { env, detached: true });

      // Simulated worker process for development
      const simulatedProcess = {
        pid: Math.floor(Math.random() * 100000),
        on: (event, handler) => {},
        kill: () => {},
        stdout: { on: () => {} },
        stderr: { on: () => {} }
      };

      this.emit('worker_process_launched', {
        workerId,
        pid: simulatedProcess.pid,
        logFile
      });

      resolve(simulatedProcess);
    });
  }

  /**
   * Get worker status
   */
  getWorkerStatus(workerId) {
    return this.workers.get(workerId);
  }

  /**
   * Get all workers by status
   */
  getWorkersByStatus(status) {
    return Array.from(this.workers.values()).filter(w => w.status === status);
  }

  /**
   * Terminate a worker
   */
  async terminateWorker(workerId, reason = 'manual') {
    const worker = this.workers.get(workerId);
    if (!worker) {
      throw new Error(`Worker ${workerId} not found`);
    }

    const process = this.workerProcesses.get(workerId);
    if (process) {
      process.kill('SIGTERM');
      this.workerProcesses.delete(workerId);
    }

    worker.status = 'terminated';
    worker.terminatedAt = new Date();
    worker.terminationReason = reason;

    this.emit('worker_terminated', { workerId, reason });

    // Remove from active workers after a delay
    setTimeout(() => {
      this.workers.delete(workerId);
      this.metrics.currentActive = this.workers.size;
    }, 5000);

    return true;
  }

  /**
   * Terminate all workers
   */
  async terminateAll(reason = 'shutdown') {
    const workerIds = Array.from(this.workers.keys());

    this.emit('terminating_all', { count: workerIds.length, reason });

    const terminatePromises = workerIds.map(id =>
      this.terminateWorker(id, reason).catch(err => {
        this.emit('termination_error', { workerId: id, error: err.message });
      })
    );

    await Promise.allSettled(terminatePromises);

    this.emit('all_terminated', { count: workerIds.length });
  }

  /**
   * Start health check monitoring
   */
  startHealthCheck() {
    if (this.healthCheckTimer) {
      return; // Already running
    }

    this.healthCheckTimer = setInterval(() => {
      this._performHealthCheck();
    }, this.config.healthCheckInterval);

    this.emit('health_check_started', {
      interval: this.config.healthCheckInterval
    });
  }

  /**
   * Stop health check monitoring
   */
  stopHealthCheck() {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
      this.emit('health_check_stopped');
    }
  }

  /**
   * Perform health check on all workers
   * @private
   */
  async _performHealthCheck() {
    const now = new Date();
    const unhealthyWorkers = [];

    for (const [workerId, worker] of this.workers.entries()) {
      // Check if worker has exceeded timeout
      const lifetime = now - worker.spawnedAt;

      if (lifetime > this.config.workerTimeout && worker.status === 'running') {
        worker.status = 'timeout';
        unhealthyWorkers.push({ workerId, reason: 'timeout', lifetime });

        if (this.config.autoRestart) {
          this.emit('worker_timeout_restart', { workerId });
          await this.terminateWorker(workerId, 'timeout');
          // Auto-restart logic would go here
        }
      }

      // Check if process is still alive
      const process = this.workerProcesses.get(workerId);
      if (process && worker.status === 'running') {
        // In real implementation, check if PID exists
        // For now, simulated check
      }
    }

    if (unhealthyWorkers.length > 0) {
      this.emit('unhealthy_workers_detected', {
        count: unhealthyWorkers.length,
        workers: unhealthyWorkers
      });
    }

    this.emit('health_check_completed', {
      total: this.workers.size,
      unhealthy: unhealthyWorkers.length
    });
  }

  /**
   * Get current metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      currentActive: this.workers.size,
      byStatus: this._getWorkerCountsByStatus()
    };
  }

  /**
   * Get worker counts by status
   * @private
   */
  _getWorkerCountsByStatus() {
    const counts = {};
    for (const worker of this.workers.values()) {
      counts[worker.status] = (counts[worker.status] || 0) + 1;
    }
    return counts;
  }

  /**
   * Generate unique worker ID
   * @private
   */
  _generateWorkerId(workerType) {
    const timestamp = Date.now();
    const random = crypto.randomBytes(4).toString('hex');
    return `${workerType}-${timestamp}-${random}`;
  }

  /**
   * Shutdown spawner
   */
  async shutdown() {
    this.stopHealthCheck();
    await this.terminateAll('shutdown');
    this.emit('shutdown_complete');
  }
}

module.exports = { WorkerSpawner };
