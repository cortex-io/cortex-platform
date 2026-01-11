/**
 * Worker Health Monitor
 * Tracks worker health, detects zombies, and manages auto-restart
 */

const { EventEmitter } = require('events');

class HealthMonitor extends EventEmitter {
  constructor(config = {}) {
    super();
    this.config = {
      heartbeatTimeoutMs: config.heartbeatTimeoutMs || 15000, // 15 seconds
      healthCheckInterval: config.healthCheckInterval || 5000, // 5 seconds
      zombieThresholdMs: config.zombieThresholdMs || 30000, // 30 seconds
      maxRestartAttempts: config.maxRestartAttempts || 3,
      restartCooldownMs: config.restartCooldownMs || 5000, // 5 seconds
      memoryThresholdMB: config.memoryThresholdMB || 512,
      cpuThresholdPercent: config.cpuThresholdPercent || 90,
      ...config
    };

    this.workers = new Map(); // workerId -> worker health data
    this.metrics = new Map(); // workerId -> historical metrics
    this.alerts = [];
    this.monitoringInterval = null;
    this.isMonitoring = false;
  }

  /**
   * Start monitoring
   */
  start() {
    if (this.isMonitoring) {
      return;
    }

    this.isMonitoring = true;
    this.monitoringInterval = setInterval(() => {
      this._performHealthChecks();
    }, this.config.healthCheckInterval);

    this.emit('monitoring-started');
  }

  /**
   * Stop monitoring
   */
  stop() {
    if (!this.isMonitoring) {
      return;
    }

    this.isMonitoring = false;
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }

    this.emit('monitoring-stopped');
  }

  /**
   * Register a worker for monitoring
   */
  registerWorker(workerId, workerInfo = {}) {
    const workerData = {
      workerId,
      pid: workerInfo.pid,
      state: 'initializing',
      lastHeartbeat: Date.now(),
      lastHealthCheck: null,
      registeredAt: Date.now(),
      restartAttempts: 0,
      lastRestartAt: null,
      healthy: true,
      tasksExecuted: 0,
      currentTask: null,
      consecutiveFailures: 0,
      metrics: {
        memory: {},
        cpu: {},
        uptime: 0
      },
      ...workerInfo
    };

    this.workers.set(workerId, workerData);
    this.metrics.set(workerId, []);

    this.emit('worker-registered', { workerId, pid: workerData.pid });
  }

  /**
   * Unregister a worker
   */
  unregisterWorker(workerId) {
    const worker = this.workers.get(workerId);
    if (worker) {
      this.workers.delete(workerId);
      this.emit('worker-unregistered', { workerId, pid: worker.pid });
    }
  }

  /**
   * Record heartbeat from worker
   */
  recordHeartbeat(workerId, heartbeatData) {
    const worker = this.workers.get(workerId);
    if (!worker) {
      this.emit('warning', {
        message: `Received heartbeat from unknown worker ${workerId}`,
        workerId
      });
      return;
    }

    const now = Date.now();
    const timeSinceLastHeartbeat = now - worker.lastHeartbeat;

    worker.lastHeartbeat = now;
    worker.state = heartbeatData.state || worker.state;
    worker.tasksExecuted = heartbeatData.tasksExecuted || worker.tasksExecuted;
    worker.currentTask = heartbeatData.currentTask || null;

    // Update metrics
    if (heartbeatData.memoryUsage) {
      worker.metrics.memory = heartbeatData.memoryUsage;
    }
    if (heartbeatData.cpuUsage) {
      worker.metrics.cpu = heartbeatData.cpuUsage;
    }
    if (heartbeatData.uptime) {
      worker.metrics.uptime = heartbeatData.uptime;
    }

    // Store historical metrics
    this._recordMetrics(workerId, {
      timestamp: now,
      memory: worker.metrics.memory,
      cpu: worker.metrics.cpu,
      state: worker.state,
      tasksExecuted: worker.tasksExecuted
    });

    // Check if heartbeat was late
    if (timeSinceLastHeartbeat > this.config.heartbeatTimeoutMs * 1.5) {
      this._createAlert('warning', workerId, 'late-heartbeat', {
        message: `Late heartbeat from worker ${workerId}`,
        delayMs: timeSinceLastHeartbeat,
        thresholdMs: this.config.heartbeatTimeoutMs
      });
    }

    // Reset consecutive failures on successful heartbeat
    if (worker.consecutiveFailures > 0) {
      worker.consecutiveFailures = 0;
    }

    this.emit('heartbeat-received', { workerId, timeSinceLastHeartbeat });
  }

  /**
   * Record worker metrics
   */
  _recordMetrics(workerId, metricsData) {
    const workerMetrics = this.metrics.get(workerId) || [];

    // Add new metrics
    workerMetrics.push(metricsData);

    // Keep only last 100 entries
    if (workerMetrics.length > 100) {
      workerMetrics.shift();
    }

    this.metrics.set(workerId, workerMetrics);
  }

  /**
   * Perform health checks on all workers
   */
  _performHealthChecks() {
    const now = Date.now();

    for (const [workerId, worker] of this.workers.entries()) {
      const timeSinceHeartbeat = now - worker.lastHeartbeat;

      // Check for zombie workers (no heartbeat)
      if (timeSinceHeartbeat > this.config.zombieThresholdMs) {
        this._handleZombieWorker(workerId, worker, timeSinceHeartbeat);
        continue;
      }

      // Check for missed heartbeats
      if (timeSinceHeartbeat > this.config.heartbeatTimeoutMs) {
        this._handleMissedHeartbeat(workerId, worker, timeSinceHeartbeat);
        continue;
      }

      // Check memory usage
      if (worker.metrics.memory.heapUsed) {
        const heapUsedMB = worker.metrics.memory.heapUsed / 1024 / 1024;
        if (heapUsedMB > this.config.memoryThresholdMB) {
          this._handleHighMemory(workerId, worker, heapUsedMB);
        }
      }

      // Check if worker is stuck
      if (worker.state === 'busy' && worker.currentTask) {
        // This would need task start time to properly detect
        // For now, we rely on task timeout in the pool manager
      }

      // Mark as healthy if all checks pass
      if (!worker.healthy) {
        worker.healthy = true;
        this.emit('worker-recovered', { workerId });
      }

      worker.lastHealthCheck = now;
    }
  }

  /**
   * Handle zombie worker detection
   */
  _handleZombieWorker(workerId, worker, timeSinceHeartbeat) {
    if (worker.healthy) {
      worker.healthy = false;
      worker.consecutiveFailures++;

      this._createAlert('critical', workerId, 'zombie-detected', {
        message: `Zombie worker detected: ${workerId}`,
        timeSinceHeartbeat,
        threshold: this.config.zombieThresholdMs,
        pid: worker.pid,
        state: worker.state
      });

      this.emit('zombie-detected', {
        workerId,
        pid: worker.pid,
        timeSinceHeartbeat,
        state: worker.state,
        currentTask: worker.currentTask
      });
    }
  }

  /**
   * Handle missed heartbeat
   */
  _handleMissedHeartbeat(workerId, worker, timeSinceHeartbeat) {
    if (worker.healthy) {
      worker.healthy = false;
      worker.consecutiveFailures++;

      this._createAlert('warning', workerId, 'missed-heartbeat', {
        message: `Missed heartbeat from worker ${workerId}`,
        timeSinceHeartbeat,
        threshold: this.config.heartbeatTimeoutMs
      });

      this.emit('missed-heartbeat', {
        workerId,
        timeSinceHeartbeat,
        threshold: this.config.heartbeatTimeoutMs
      });
    }
  }

  /**
   * Handle high memory usage
   */
  _handleHighMemory(workerId, worker, heapUsedMB) {
    this._createAlert('warning', workerId, 'high-memory', {
      message: `High memory usage in worker ${workerId}`,
      memoryMB: Math.round(heapUsedMB),
      threshold: this.config.memoryThresholdMB
    });

    this.emit('high-memory', {
      workerId,
      memoryMB: Math.round(heapUsedMB),
      threshold: this.config.memoryThresholdMB
    });
  }

  /**
   * Check if worker should be restarted
   */
  shouldRestartWorker(workerId) {
    const worker = this.workers.get(workerId);
    if (!worker) {
      return false;
    }

    // Don't restart if we've exceeded max attempts
    if (worker.restartAttempts >= this.config.maxRestartAttempts) {
      return false;
    }

    // Don't restart if we're in cooldown period
    if (worker.lastRestartAt) {
      const timeSinceRestart = Date.now() - worker.lastRestartAt;
      if (timeSinceRestart < this.config.restartCooldownMs) {
        return false;
      }
    }

    // Restart if unhealthy
    return !worker.healthy;
  }

  /**
   * Record worker restart attempt
   */
  recordRestartAttempt(workerId) {
    const worker = this.workers.get(workerId);
    if (worker) {
      worker.restartAttempts++;
      worker.lastRestartAt = Date.now();

      this.emit('restart-attempted', {
        workerId,
        attempt: worker.restartAttempts,
        maxAttempts: this.config.maxRestartAttempts
      });
    }
  }

  /**
   * Reset restart counter (call when worker is healthy for a while)
   */
  resetRestartCounter(workerId) {
    const worker = this.workers.get(workerId);
    if (worker && worker.restartAttempts > 0) {
      worker.restartAttempts = 0;
      this.emit('restart-counter-reset', { workerId });
    }
  }

  /**
   * Get worker health status
   */
  getWorkerHealth(workerId) {
    const worker = this.workers.get(workerId);
    if (!worker) {
      return null;
    }

    const now = Date.now();
    return {
      workerId,
      pid: worker.pid,
      healthy: worker.healthy,
      state: worker.state,
      tasksExecuted: worker.tasksExecuted,
      currentTask: worker.currentTask,
      timeSinceHeartbeat: now - worker.lastHeartbeat,
      uptime: now - worker.registeredAt,
      restartAttempts: worker.restartAttempts,
      consecutiveFailures: worker.consecutiveFailures,
      metrics: worker.metrics
    };
  }

  /**
   * Get all workers health status
   */
  getAllWorkersHealth() {
    const healthData = [];
    for (const workerId of this.workers.keys()) {
      healthData.push(this.getWorkerHealth(workerId));
    }
    return healthData;
  }

  /**
   * Get unhealthy workers
   */
  getUnhealthyWorkers() {
    const unhealthy = [];
    for (const [workerId, worker] of this.workers.entries()) {
      if (!worker.healthy) {
        unhealthy.push(this.getWorkerHealth(workerId));
      }
    }
    return unhealthy;
  }

  /**
   * Get pool capacity metrics
   */
  getPoolCapacity() {
    const total = this.workers.size;
    let healthy = 0;
    let busy = 0;
    let idle = 0;

    for (const worker of this.workers.values()) {
      if (worker.healthy) {
        healthy++;
        if (worker.state === 'busy') {
          busy++;
        } else if (worker.state === 'ready') {
          idle++;
        }
      }
    }

    const capacityPercent = total > 0 ? Math.round((healthy / total) * 100) : 0;
    const utilizationPercent = healthy > 0 ? Math.round((busy / healthy) * 100) : 0;

    return {
      total,
      healthy,
      unhealthy: total - healthy,
      busy,
      idle,
      capacityPercent,
      utilizationPercent,
      degraded: capacityPercent < 80
    };
  }

  /**
   * Get historical metrics for a worker
   */
  getWorkerMetrics(workerId, limit = 100) {
    const metrics = this.metrics.get(workerId) || [];
    return metrics.slice(-limit);
  }

  /**
   * Create an alert
   */
  _createAlert(severity, workerId, type, details) {
    const alert = {
      id: `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      severity, // info, warning, critical
      workerId,
      type,
      timestamp: Date.now(),
      ...details
    };

    this.alerts.push(alert);

    // Keep only last 1000 alerts
    if (this.alerts.length > 1000) {
      this.alerts.shift();
    }

    this.emit('alert', alert);
  }

  /**
   * Get recent alerts
   */
  getAlerts(limit = 50, severity = null) {
    let alerts = [...this.alerts];

    if (severity) {
      alerts = alerts.filter(a => a.severity === severity);
    }

    return alerts.slice(-limit).reverse();
  }

  /**
   * Clear old alerts
   */
  clearAlerts(olderThanMs = 3600000) { // 1 hour default
    const cutoff = Date.now() - olderThanMs;
    const before = this.alerts.length;
    this.alerts = this.alerts.filter(a => a.timestamp > cutoff);
    const cleared = before - this.alerts.length;

    if (cleared > 0) {
      this.emit('alerts-cleared', { cleared, remaining: this.alerts.length });
    }

    return cleared;
  }

  /**
   * Get overall health summary
   */
  getHealthSummary() {
    const capacity = this.getPoolCapacity();
    const recentAlerts = this.getAlerts(10);
    const criticalAlerts = this.alerts.filter(a => a.severity === 'critical' && Date.now() - a.timestamp < 300000); // Last 5 minutes

    return {
      timestamp: Date.now(),
      monitoring: this.isMonitoring,
      capacity,
      alerts: {
        total: this.alerts.length,
        recent: recentAlerts.length,
        critical: criticalAlerts.length
      },
      workers: {
        total: this.workers.size,
        healthy: capacity.healthy,
        unhealthy: capacity.unhealthy
      },
      status: this._determineOverallStatus(capacity, criticalAlerts)
    };
  }

  /**
   * Determine overall system health status
   */
  _determineOverallStatus(capacity, criticalAlerts) {
    if (criticalAlerts.length > 0 || capacity.capacityPercent < 50) {
      return 'critical';
    }
    if (capacity.capacityPercent < 80 || capacity.utilizationPercent > 90) {
      return 'degraded';
    }
    return 'healthy';
  }
}

module.exports = HealthMonitor;
