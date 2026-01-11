/**
 * Feasibility Checker
 *
 * Checks if the system can accept a new task based on:
 * - Current system resource usage (CPU, memory)
 * - Token budget availability
 * - Worker pool capacity
 * - Predicted resource requirements
 *
 * Provides admission control to prevent system overload.
 */

const os = require('os');
const fs = require('fs');
const path = require('path');

/**
 * System Resource Monitor
 */
class SystemResourceMonitor {
  constructor() {
    this.processStartMemory = process.memoryUsage().heapUsed;
    this.processStartTime = Date.now();
  }

  /**
   * Get current system resource usage
   */
  getSystemResources() {
    const totalMemoryMB = os.totalmem() / (1024 * 1024);
    const freeMemoryMB = os.freemem() / (1024 * 1024);
    const usedMemoryMB = totalMemoryMB - freeMemoryMB;

    const cpuUsage = os.loadavg(); // [1min, 5min, 15min]
    const numCpus = os.cpus().length;

    return {
      totalMemoryMB: Math.round(totalMemoryMB),
      freeMemoryMB: Math.round(freeMemoryMB),
      usedMemoryMB: Math.round(usedMemoryMB),
      usedMemoryPercent: (usedMemoryMB / totalMemoryMB) * 100,
      cpuLoadAvg1: cpuUsage[0],
      cpuLoadAvg5: cpuUsage[1],
      cpuLoadAvg15: cpuUsage[2],
      numCpus,
      cpuUtilizationPercent: (cpuUsage[0] / numCpus) * 100,
      platform: os.platform(),
      uptime: os.uptime()
    };
  }

  /**
   * Get Node.js process resource usage
   */
  getProcessResources() {
    const memUsage = process.memoryUsage();
    const cpuUsage = process.cpuUsage();
    const uptime = Date.now() - this.processStartTime;

    return {
      heapUsedMB: Math.round(memUsage.heapUsed / (1024 * 1024)),
      heapTotalMB: Math.round(memUsage.heapTotal / (1024 * 1024)),
      rssMB: Math.round(memUsage.rss / (1024 * 1024)),
      externalMB: Math.round(memUsage.external / (1024 * 1024)),
      cpuUserMs: Math.round(cpuUsage.user / 1000),
      cpuSystemMs: Math.round(cpuUsage.system / 1000),
      uptimeMs: uptime
    };
  }

  /**
   * Check if system is healthy
   * Note: On macOS, memory compression means high "used" percentages are normal.
   * We use more lenient thresholds by default for development environments.
   */
  isSystemHealthy(thresholds = {}) {
    const platform = os.platform();

    // macOS uses memory compression effectively, so higher usage is OK
    const defaults = platform === 'darwin' ? {
      maxMemoryPercent: 95,    // macOS handles 95%+ well with compression
      maxCpuPercent: 90,       // Higher threshold for development
      minFreeMemoryMB: 512     // Lower minimum due to compression
    } : {
      maxMemoryPercent: 90,    // Linux/Windows more conservative
      maxCpuPercent: 85,
      minFreeMemoryMB: 1024
    };

    const thresh = { ...defaults, ...thresholds };
    const sysRes = this.getSystemResources();

    const checks = {
      memoryOk: sysRes.usedMemoryPercent < thresh.maxMemoryPercent,
      freeMemoryOk: sysRes.freeMemoryMB > thresh.minFreeMemoryMB,
      cpuOk: sysRes.cpuUtilizationPercent < thresh.maxCpuPercent,
      overall: true
    };

    checks.overall = checks.memoryOk && checks.freeMemoryOk && checks.cpuOk;

    return {
      healthy: checks.overall,
      checks,
      resources: sysRes
    };
  }
}

/**
 * Token Budget Tracker
 */
class TokenBudgetTracker {
  constructor(options = {}) {
    this.budgetFile = options.budgetFile || path.join(
      process.cwd(),
      'coordination',
      'scheduler-data',
      'token-usage.json'
    );
    this.hourlyLimit = options.hourlyLimit || 1000000;
    this.dailyLimit = options.dailyLimit || 10000000;

    this._ensureFile();
  }

  /**
   * Ensure budget file exists
   */
  _ensureFile() {
    const dir = path.dirname(this.budgetFile);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    if (!fs.existsSync(this.budgetFile)) {
      const initialData = {
        hourlyUsage: {},
        dailyUsage: {},
        lastReset: new Date().toISOString()
      };
      fs.writeFileSync(this.budgetFile, JSON.stringify(initialData, null, 2), 'utf8');
    }
  }

  /**
   * Get current usage
   */
  _getUsage() {
    const data = JSON.parse(fs.readFileSync(this.budgetFile, 'utf8'));
    return data;
  }

  /**
   * Save usage
   */
  _saveUsage(data) {
    fs.writeFileSync(this.budgetFile, JSON.stringify(data, null, 2), 'utf8');
  }

  /**
   * Get current hour key
   */
  _getHourKey() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}`;
  }

  /**
   * Get current day key
   */
  _getDayKey() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }

  /**
   * Clean old usage records
   */
  _cleanOldRecords(data) {
    const now = new Date();
    const currentHourKey = this._getHourKey();
    const currentDayKey = this._getDayKey();

    // Keep only current hour
    const newHourlyUsage = {};
    if (data.hourlyUsage[currentHourKey]) {
      newHourlyUsage[currentHourKey] = data.hourlyUsage[currentHourKey];
    }

    // Keep only current day
    const newDailyUsage = {};
    if (data.dailyUsage[currentDayKey]) {
      newDailyUsage[currentDayKey] = data.dailyUsage[currentDayKey];
    }

    data.hourlyUsage = newHourlyUsage;
    data.dailyUsage = newDailyUsage;
  }

  /**
   * Check if tokens are available
   */
  checkAvailability(requiredTokens) {
    const data = this._getUsage();
    this._cleanOldRecords(data);

    const hourKey = this._getHourKey();
    const dayKey = this._getDayKey();

    const hourlyUsed = data.hourlyUsage[hourKey] || 0;
    const dailyUsed = data.dailyUsage[dayKey] || 0;

    const hourlyAvailable = this.hourlyLimit - hourlyUsed;
    const dailyAvailable = this.dailyLimit - dailyUsed;

    return {
      available: hourlyAvailable >= requiredTokens && dailyAvailable >= requiredTokens,
      hourlyUsed,
      hourlyLimit: this.hourlyLimit,
      hourlyAvailable,
      hourlyPercent: (hourlyUsed / this.hourlyLimit) * 100,
      dailyUsed,
      dailyLimit: this.dailyLimit,
      dailyAvailable,
      dailyPercent: (dailyUsed / this.dailyLimit) * 100,
      requiredTokens
    };
  }

  /**
   * Record token usage
   */
  recordUsage(tokens) {
    const data = this._getUsage();
    this._cleanOldRecords(data);

    const hourKey = this._getHourKey();
    const dayKey = this._getDayKey();

    data.hourlyUsage[hourKey] = (data.hourlyUsage[hourKey] || 0) + tokens;
    data.dailyUsage[dayKey] = (data.dailyUsage[dayKey] || 0) + tokens;

    this._saveUsage(data);
  }

  /**
   * Get current usage summary
   */
  getSummary() {
    const data = this._getUsage();
    const hourKey = this._getHourKey();
    const dayKey = this._getDayKey();

    return {
      hourly: {
        used: data.hourlyUsage[hourKey] || 0,
        limit: this.hourlyLimit,
        available: this.hourlyLimit - (data.hourlyUsage[hourKey] || 0),
        percent: ((data.hourlyUsage[hourKey] || 0) / this.hourlyLimit) * 100
      },
      daily: {
        used: data.dailyUsage[dayKey] || 0,
        limit: this.dailyLimit,
        available: this.dailyLimit - (data.dailyUsage[dayKey] || 0),
        percent: ((data.dailyUsage[dayKey] || 0) / this.dailyLimit) * 100
      }
    };
  }
}

/**
 * Feasibility Checker
 */
class FeasibilityChecker {
  constructor(options = {}) {
    this.resourceMonitor = new SystemResourceMonitor();
    this.tokenTracker = new TokenBudgetTracker({
      hourlyLimit: options.tokenBudgetPerHour || 1000000,
      dailyLimit: options.tokenBudgetPerDay || 10000000
    });

    this.resourceLimits = {
      maxMemoryMB: options.maxMemoryMB || 12288, // 12GB default, leave 4GB for OS
      maxConcurrentTasks: options.maxConcurrentTasks || 20,
      memoryReservePercent: options.memoryReservePercent || 20, // Keep 20% free
      cpuReservePercent: options.cpuReservePercent || 20
    };

    this.currentTasks = new Map(); // taskId -> resourceAllocation
  }

  /**
   * Check current system state
   */
  checkSystemResources() {
    const systemRes = this.resourceMonitor.getSystemResources();
    const processRes = this.resourceMonitor.getProcessResources();

    // Calculate available resources
    const totalAllocatedMemory = Array.from(this.currentTasks.values())
      .reduce((sum, task) => sum + (task.allocatedMemoryMB || 0), 0);

    const availableMemoryMB = this.resourceLimits.maxMemoryMB - totalAllocatedMemory;
    const availableTaskSlots = this.resourceLimits.maxConcurrentTasks - this.currentTasks.size;

    return {
      system: systemRes,
      process: processRes,
      allocated: {
        memoryMB: totalAllocatedMemory,
        tasks: this.currentTasks.size
      },
      available: {
        memoryMB: availableMemoryMB,
        taskSlots: availableTaskSlots
      },
      limits: this.resourceLimits,
      healthy: this.resourceMonitor.isSystemHealthy().healthy
    };
  }

  /**
   * Check token budget availability
   */
  checkTokenBudget(estimatedTokens) {
    return this.tokenTracker.checkAvailability(estimatedTokens);
  }

  /**
   * Check worker availability
   */
  checkWorkerAvailability() {
    const availableSlots = this.resourceLimits.maxConcurrentTasks - this.currentTasks.size;

    return {
      available: availableSlots > 0,
      currentTasks: this.currentTasks.size,
      maxTasks: this.resourceLimits.maxConcurrentTasks,
      availableSlots
    };
  }

  /**
   * Calculate overall feasibility for a task
   */
  calculateFeasibility(taskRequirements) {
    const systemCheck = this.checkSystemResources();
    const tokenCheck = this.checkTokenBudget(taskRequirements.estimatedTokens || 0);
    const workerCheck = this.checkWorkerAvailability();

    // Individual checks
    const checks = {
      memoryAvailable: systemCheck.available.memoryMB >= taskRequirements.estimatedMemoryMB,
      workerSlotAvailable: workerCheck.available,
      tokensAvailable: tokenCheck.available,
      systemHealthy: systemCheck.healthy
    };

    // Overall feasibility
    const feasible = checks.memoryAvailable &&
                     checks.workerSlotAvailable &&
                     checks.tokensAvailable &&
                     checks.systemHealthy;

    // Determine reason if not feasible
    let reason = null;
    let estimatedWaitTimeMs = null;

    if (!feasible) {
      if (!checks.memoryAvailable) {
        reason = 'insufficient-memory';
        // Estimate wait time based on average task duration
        estimatedWaitTimeMs = 180000; // 3 minutes default
      } else if (!checks.workerSlotAvailable) {
        reason = 'no-worker-slots';
        estimatedWaitTimeMs = 120000; // 2 minutes
      } else if (!checks.tokensAvailable) {
        reason = 'token-budget-exceeded';
        // Wait until next hour
        const now = new Date();
        const nextHour = new Date(now);
        nextHour.setHours(now.getHours() + 1, 0, 0, 0);
        estimatedWaitTimeMs = nextHour.getTime() - now.getTime();
      } else if (!checks.systemHealthy) {
        reason = 'system-unhealthy';
        estimatedWaitTimeMs = 300000; // 5 minutes
      }
    }

    return {
      feasible,
      reason,
      estimatedWaitTimeMs,
      checks,
      systemState: {
        availableMemoryMB: systemCheck.available.memoryMB,
        availableWorkerSlots: workerCheck.availableSlots,
        availableTokens: Math.min(tokenCheck.hourlyAvailable, tokenCheck.dailyAvailable),
        systemHealth: systemCheck.healthy
      },
      requirements: taskRequirements
    };
  }

  /**
   * Allocate resources for a task
   */
  allocateResources(taskId, resourceRequirements) {
    this.currentTasks.set(taskId, {
      taskId,
      allocatedMemoryMB: resourceRequirements.estimatedMemoryMB,
      allocatedTokens: resourceRequirements.estimatedTokens,
      allocatedAt: new Date().toISOString()
    });

    return {
      allocated: true,
      taskId,
      resources: this.currentTasks.get(taskId)
    };
  }

  /**
   * Release resources when task completes
   */
  releaseResources(taskId, actualUsage = {}) {
    const allocation = this.currentTasks.get(taskId);

    if (!allocation) {
      return { released: false, reason: 'task-not-found' };
    }

    // Record actual token usage
    if (actualUsage.tokens) {
      this.tokenTracker.recordUsage(actualUsage.tokens);
    }

    this.currentTasks.delete(taskId);

    return {
      released: true,
      taskId,
      allocation,
      actualUsage
    };
  }

  /**
   * Get system capacity summary
   */
  getSystemCapacity() {
    const systemCheck = this.checkSystemResources();
    const tokenSummary = this.tokenTracker.getSummary();

    return {
      resources: {
        memory: {
          totalMB: systemCheck.system.totalMemoryMB,
          freeMB: systemCheck.system.freeMemoryMB,
          allocatedMB: systemCheck.allocated.memoryMB,
          availableMB: systemCheck.available.memoryMB,
          limitMB: this.resourceLimits.maxMemoryMB
        },
        workers: {
          current: systemCheck.allocated.tasks,
          available: systemCheck.available.taskSlots,
          max: this.resourceLimits.maxConcurrentTasks
        },
        tokens: tokenSummary
      },
      health: {
        healthy: systemCheck.healthy,
        memoryPercent: systemCheck.system.usedMemoryPercent,
        cpuPercent: systemCheck.system.cpuUtilizationPercent
      },
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Update resource limits
   */
  setResourceLimits(limits) {
    this.resourceLimits = { ...this.resourceLimits, ...limits };

    if (limits.tokenBudgetPerHour) {
      this.tokenTracker.hourlyLimit = limits.tokenBudgetPerHour;
    }
    if (limits.tokenBudgetPerDay) {
      this.tokenTracker.dailyLimit = limits.tokenBudgetPerDay;
    }

    return this.resourceLimits;
  }

  /**
   * Get active tasks
   */
  getActiveTasks() {
    return Array.from(this.currentTasks.entries()).map(([taskId, allocation]) => ({
      taskId,
      ...allocation
    }));
  }
}

module.exports = {
  FeasibilityChecker,
  SystemResourceMonitor,
  TokenBudgetTracker
};
