#!/usr/bin/env node

/**
 * Worker Pool Monitor
 *
 * Monitors worker health, detects failures, and implements auto-recovery.
 * Provides real-time metrics and alerting for worker pool operations.
 */

const { EventEmitter } = require('events');
const fs = require('fs').promises;
const path = require('path');

class WorkerMonitor extends EventEmitter {
  constructor(spawner, coordinator, config = {}) {
    super();

    this.spawner = spawner;
    this.coordinator = coordinator;

    this.config = {
      cortexRoot: config.cortexRoot || process.env.CORTEX_ROOT || '/Users/ryandahlberg/Projects/cortex',
      healthCheckInterval: config.healthCheckInterval || 30000, // 30 seconds
      metricsInterval: config.metricsInterval || 60000, // 1 minute
      autoRecover: config.autoRecover !== false,
      maxRecoveryAttempts: config.maxRecoveryAttempts || 3,
      alertThresholds: {
        failureRate: config.failureRateThreshold || 0.1, // 10%
        avgLifetime: config.avgLifetimeThreshold || 60000, // 1 minute
        ...config.alertThresholds
      },
      ...config
    };

    // Monitoring state
    this.monitoring = false;
    this.healthCheckTimer = null;
    this.metricsTimer = null;

    // Recovery tracking
    this.recoveryAttempts = new Map(); // workerId -> attempt count

    // Metrics history
    this.metricsHistory = [];
    this.maxHistorySize = 100;

    // Alerts
    this.activeAlerts = new Map();
  }

  /**
   * Start monitoring
   */
  start() {
    if (this.monitoring) {
      return;
    }

    this.monitoring = true;

    // Start health checks
    this.healthCheckTimer = setInterval(() => {
      this._performHealthCheck();
    }, this.config.healthCheckInterval);

    // Start metrics collection
    this.metricsTimer = setInterval(() => {
      this._collectMetrics();
    }, this.config.metricsInterval);

    // Listen to spawner events
    this._attachEventListeners();

    this.emit('monitoring_started', {
      healthCheckInterval: this.config.healthCheckInterval,
      metricsInterval: this.config.metricsInterval
    });
  }

  /**
   * Stop monitoring
   */
  stop() {
    if (!this.monitoring) {
      return;
    }

    this.monitoring = false;

    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }

    if (this.metricsTimer) {
      clearInterval(this.metricsTimer);
      this.metricsTimer = null;
    }

    this.emit('monitoring_stopped');
  }

  /**
   * Attach event listeners to spawner and coordinator
   * @private
   */
  _attachEventListeners() {
    // Spawner events
    this.spawner.on('worker_spawned', (data) => {
      this._handleWorkerSpawned(data);
    });

    this.spawner.on('worker_spawn_failed', (data) => {
      this._handleWorkerSpawnFailed(data);
    });

    this.spawner.on('worker_terminated', (data) => {
      this._handleWorkerTerminated(data);
    });

    this.spawner.on('unhealthy_workers_detected', (data) => {
      this._handleUnhealthyWorkers(data);
    });

    // Coordinator events
    this.coordinator.on('coordination_failed', (data) => {
      this._handleCoordinationFailed(data);
    });

    this.coordinator.on('task_failed', (data) => {
      this._handleTaskFailed(data);
    });
  }

  /**
   * Perform health check
   * @private
   */
  async _performHealthCheck() {
    const timestamp = new Date();

    // Get spawner metrics
    const spawnerMetrics = this.spawner.getMetrics();
    const coordinatorMetrics = this.coordinator.getMetrics();

    // Calculate health indicators
    const health = {
      timestamp,
      spawner: {
        ...spawnerMetrics,
        failureRate: spawnerMetrics.totalSpawned > 0
          ? spawnerMetrics.totalFailed / spawnerMetrics.totalSpawned
          : 0
      },
      coordinator: coordinatorMetrics,
      overall: 'healthy'
    };

    // Check against thresholds
    if (health.spawner.failureRate > this.config.alertThresholds.failureRate) {
      this._raiseAlert('high_failure_rate', {
        current: health.spawner.failureRate,
        threshold: this.config.alertThresholds.failureRate
      });
      health.overall = 'degraded';
    }

    // Check worker statuses
    const workersByStatus = spawnerMetrics.byStatus || {};
    if (workersByStatus.timeout || workersByStatus.failed) {
      health.overall = 'degraded';
    }

    this.emit('health_check_completed', health);

    return health;
  }

  /**
   * Collect metrics
   * @private
   */
  async _collectMetrics() {
    const metrics = {
      timestamp: new Date(),
      spawner: this.spawner.getMetrics(),
      coordinator: this.coordinator.getMetrics(),
      recovery: {
        activeRecoveries: this.recoveryAttempts.size,
        totalRecoveryAttempts: Array.from(this.recoveryAttempts.values())
          .reduce((sum, count) => sum + count, 0)
      },
      alerts: {
        active: this.activeAlerts.size,
        byType: this._getAlertsByType()
      }
    };

    // Add to history
    this.metricsHistory.push(metrics);

    // Trim history if needed
    if (this.metricsHistory.length > this.maxHistorySize) {
      this.metricsHistory.shift();
    }

    this.emit('metrics_collected', metrics);

    // Optionally persist metrics
    if (this.config.persistMetrics) {
      await this._persistMetrics(metrics);
    }

    return metrics;
  }

  /**
   * Persist metrics to disk
   * @private
   */
  async _persistMetrics(metrics) {
    try {
      const metricsDir = path.join(this.config.cortexRoot, 'logs/worker-pool-metrics');
      await fs.mkdir(metricsDir, { recursive: true });

      const filename = `metrics-${metrics.timestamp.toISOString().replace(/:/g, '-')}.json`;
      const filepath = path.join(metricsDir, filename);

      await fs.writeFile(filepath, JSON.stringify(metrics, null, 2));

      this.emit('metrics_persisted', { filepath });
    } catch (error) {
      this.emit('metrics_persistence_error', { error: error.message });
    }
  }

  /**
   * Handle worker spawned event
   * @private
   */
  _handleWorkerSpawned(data) {
    const { workerId } = data;

    // Clear any previous recovery attempts
    if (this.recoveryAttempts.has(workerId)) {
      this.recoveryAttempts.delete(workerId);
      this._clearAlert(`recovery_${workerId}`);
    }

    this.emit('worker_healthy', { workerId });
  }

  /**
   * Handle worker spawn failed event
   * @private
   */
  _handleWorkerSpawnFailed(data) {
    const { workerId, error } = data;

    this.emit('worker_spawn_failure_detected', { workerId, error });

    // Attempt recovery if enabled
    if (this.config.autoRecover) {
      this._attemptRecovery(workerId, 'spawn_failed', { error });
    }
  }

  /**
   * Handle worker terminated event
   * @private
   */
  _handleWorkerTerminated(data) {
    const { workerId, reason } = data;

    // Only attempt recovery for unexpected terminations
    if (reason !== 'manual' && reason !== 'shutdown' && this.config.autoRecover) {
      this._attemptRecovery(workerId, 'terminated', { reason });
    }
  }

  /**
   * Handle unhealthy workers detected
   * @private
   */
  _handleUnhealthyWorkers(data) {
    const { workers } = data;

    for (const worker of workers) {
      if (this.config.autoRecover) {
        this._attemptRecovery(worker.workerId, 'unhealthy', worker);
      }
    }
  }

  /**
   * Handle coordination failed event
   * @private
   */
  _handleCoordinationFailed(data) {
    const { coordinationId, error } = data;

    this._raiseAlert('coordination_failed', {
      coordinationId,
      error
    });
  }

  /**
   * Handle task failed event
   * @private
   */
  _handleTaskFailed(data) {
    const { taskId, error } = data;

    this.emit('task_failure_detected', { taskId, error });
  }

  /**
   * Attempt to recover a failed worker
   * @private
   */
  async _attemptRecovery(workerId, failureType, details) {
    const attempts = this.recoveryAttempts.get(workerId) || 0;

    if (attempts >= this.config.maxRecoveryAttempts) {
      this._raiseAlert(`recovery_max_attempts_${workerId}`, {
        workerId,
        attempts,
        failureType,
        details
      });

      this.emit('recovery_abandoned', {
        workerId,
        attempts,
        failureType,
        reason: 'max_attempts_reached'
      });

      return;
    }

    this.recoveryAttempts.set(workerId, attempts + 1);

    this.emit('recovery_attempt_started', {
      workerId,
      attempt: attempts + 1,
      failureType,
      details
    });

    try {
      // Get original worker spec
      const worker = this.spawner.getWorkerStatus(workerId);

      if (!worker) {
        throw new Error(`Worker ${workerId} not found for recovery`);
      }

      // Terminate existing worker if still alive
      try {
        await this.spawner.terminateWorker(workerId, 'recovery');
      } catch (err) {
        // Ignore termination errors
      }

      // Respawn worker with same spec
      const newWorkerIds = await this.spawner.spawnWorkers({
        count: 1,
        workerType: worker.type,
        taskSpec: worker.taskSpec,
        resources: worker.resources
      });

      const newWorkerId = newWorkerIds[0];

      this.emit('recovery_successful', {
        originalWorkerId: workerId,
        newWorkerId,
        attempt: attempts + 1,
        failureType
      });

      // Clear recovery attempts for new worker
      this.recoveryAttempts.delete(workerId);

      return newWorkerId;

    } catch (error) {
      this.emit('recovery_failed', {
        workerId,
        attempt: attempts + 1,
        failureType,
        error: error.message
      });

      // Will retry on next health check if under max attempts
    }
  }

  /**
   * Raise an alert
   * @private
   */
  _raiseAlert(alertType, details) {
    const alert = {
      type: alertType,
      details,
      raisedAt: new Date(),
      status: 'active'
    };

    this.activeAlerts.set(alertType, alert);

    this.emit('alert_raised', alert);

    return alert;
  }

  /**
   * Clear an alert
   * @private
   */
  _clearAlert(alertType) {
    const alert = this.activeAlerts.get(alertType);

    if (alert) {
      alert.status = 'cleared';
      alert.clearedAt = new Date();

      this.activeAlerts.delete(alertType);

      this.emit('alert_cleared', alert);

      return alert;
    }

    return null;
  }

  /**
   * Get alerts by type
   * @private
   */
  _getAlertsByType() {
    const byType = {};

    for (const [type, alert] of this.activeAlerts.entries()) {
      byType[type] = alert;
    }

    return byType;
  }

  /**
   * Get current health status
   */
  async getHealthStatus() {
    return this._performHealthCheck();
  }

  /**
   * Get metrics history
   */
  getMetricsHistory(limit = null) {
    if (limit) {
      return this.metricsHistory.slice(-limit);
    }
    return this.metricsHistory;
  }

  /**
   * Get active alerts
   */
  getActiveAlerts() {
    return Array.from(this.activeAlerts.values());
  }

  /**
   * Get recovery status
   */
  getRecoveryStatus() {
    return {
      activeRecoveries: this.recoveryAttempts.size,
      workers: Array.from(this.recoveryAttempts.entries()).map(([workerId, attempts]) => ({
        workerId,
        attempts,
        maxAttempts: this.config.maxRecoveryAttempts
      }))
    };
  }

  /**
   * Manual recovery trigger
   */
  async triggerRecovery(workerId, reason = 'manual') {
    return this._attemptRecovery(workerId, 'manual', { reason });
  }

  /**
   * Clear all alerts
   */
  clearAllAlerts() {
    const cleared = [];

    for (const alertType of this.activeAlerts.keys()) {
      const alert = this._clearAlert(alertType);
      if (alert) {
        cleared.push(alert);
      }
    }

    this.emit('all_alerts_cleared', { count: cleared.length });

    return cleared;
  }

  /**
   * Generate health report
   */
  async generateHealthReport() {
    const health = await this.getHealthStatus();
    const recovery = this.getRecoveryStatus();
    const alerts = this.getActiveAlerts();
    const recentMetrics = this.getMetricsHistory(10);

    return {
      timestamp: new Date(),
      health,
      recovery,
      alerts,
      recentMetrics,
      summary: {
        overall: health.overall,
        activeWorkers: health.spawner.currentActive,
        failureRate: health.spawner.failureRate,
        activeAlerts: alerts.length,
        activeRecoveries: recovery.activeRecoveries
      }
    };
  }

  /**
   * Shutdown monitor
   */
  async shutdown() {
    this.stop();

    this.recoveryAttempts.clear();
    this.activeAlerts.clear();
    this.metricsHistory = [];

    this.emit('shutdown_complete');
  }
}

module.exports = { WorkerMonitor };
