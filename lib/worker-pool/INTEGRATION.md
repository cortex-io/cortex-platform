# Worker Pool Integration Guide

This guide explains how to integrate the Worker Pool Manager with your existing Cortex task execution system.

## Overview

The Worker Pool Manager replaces per-task process spawning with a persistent pool of worker processes, achieving 95%+ worker reuse and eliminating spawn overhead.

## Before Integration

**Current approach (0% reuse):**
```javascript
// Spawns a new process for each task
async function executeTask(task) {
  const worker = spawn('./worker.js');  // Expensive
  const result = await worker.execute(task);
  worker.kill();  // Wasted
  return result;
}
```

## After Integration

**Worker pool approach (95% reuse):**
```javascript
// Uses persistent worker pool
async function executeTask(task) {
  return await workerPool.submitTask(task);  // Fast
}
```

## Step-by-Step Integration

### Step 1: Initialize the Worker Pool

Add this to your main Cortex initialization code:

```javascript
const { createWorkerPool } = require('./lib/worker-pool');

// During startup
async function initializeCortex() {
  // ... existing initialization code ...

  // Initialize worker pool
  console.log('Initializing worker pool...');
  global.cortexWorkerPool = await createWorkerPool({
    poolSize: 20,
    minWorkers: 5,
    maxWorkers: 50,
    heartbeatInterval: 5000,
    taskTimeout: 300000, // 5 minutes
    loadBalancing: 'least-loaded',
    autoRestart: true,
    maxRestartAttempts: 3
  });

  console.log('Worker pool initialized with', global.cortexWorkerPool.getPoolMetrics().pool.size, 'workers');

  // ... rest of initialization ...
}
```

### Step 2: Register Task Handlers in Workers

Modify `lib/worker-pool/worker-process.js` to register your existing task handlers:

```javascript
// In worker-process.js, at the bottom where handlers are registered:

if (require.main === module) {
  const workerId = process.env.WORKER_ID || 'unknown';
  const config = process.env.WORKER_CONFIG ? JSON.parse(process.env.WORKER_CONFIG) : {};
  const worker = new WorkerProcess(workerId, config);

  // Import your existing task execution logic
  const { executeImplementationTask } = require('../task-handlers/implementation');
  const { executeAnalysisTask } = require('../task-handlers/analysis');
  const { executeTestTask } = require('../task-handlers/test');

  // Register handlers
  worker.registerTaskHandler('implementation', async (payload) => {
    return await executeImplementationTask(payload);
  });

  worker.registerTaskHandler('analysis', async (payload) => {
    return await executeAnalysisTask(payload);
  });

  worker.registerTaskHandler('test', async (payload) => {
    return await executeTestTask(payload);
  });

  worker.start();
}
```

### Step 3: Replace Task Execution Calls

Replace your existing task execution with pool submission:

**Before:**
```javascript
async function handleUserRequest(request) {
  const worker = spawn('./task-executor.js', {
    env: { TASK_TYPE: request.type }
  });

  return new Promise((resolve, reject) => {
    worker.on('message', (result) => resolve(result));
    worker.on('error', (error) => reject(error));
    worker.send(request.data);
  });
}
```

**After:**
```javascript
async function handleUserRequest(request) {
  return await global.cortexWorkerPool.submitTask({
    type: request.type,
    payload: request.data,
    priority: request.priority || 10,
    timeout: request.timeout || 300000
  });
}
```

### Step 4: Add Monitoring

Add pool metrics to your existing monitoring/dashboard:

```javascript
// In your metrics/monitoring code
function collectMetrics() {
  const poolMetrics = global.cortexWorkerPool.getPoolMetrics();

  return {
    // ... existing metrics ...

    workerPool: {
      size: poolMetrics.workers.total,
      healthy: poolMetrics.workers.ready,
      busy: poolMetrics.workers.busy,
      tasksQueued: poolMetrics.tasks.queued,
      tasksCompleted: poolMetrics.tasks.completed,
      workerReuseRate: poolMetrics.performance.workerReuseRate,
      healthStatus: poolMetrics.health.status
    }
  };
}

// Expose metrics endpoint
app.get('/metrics/worker-pool', (req, res) => {
  res.json(global.cortexWorkerPool.getPoolMetrics());
});
```

### Step 5: Handle Shutdown

Ensure graceful shutdown of the worker pool:

```javascript
// Add to your shutdown handlers
async function shutdownCortex() {
  console.log('Shutting down Cortex...');

  // ... existing shutdown code ...

  // Shutdown worker pool gracefully
  if (global.cortexWorkerPool) {
    console.log('Shutting down worker pool...');
    await global.cortexWorkerPool.shutdown(true);  // Wait for in-flight tasks
    console.log('Worker pool shut down');
  }

  // ... rest of shutdown ...
}

process.on('SIGTERM', shutdownCortex);
process.on('SIGINT', shutdownCortex);
```

### Step 6: Add Event Listeners (Optional)

Monitor pool events for debugging and alerting:

```javascript
// Add event listeners for important events
global.cortexWorkerPool.on('zombie-detected', ({ workerId }) => {
  console.warn(`[WorkerPool] Zombie worker detected: ${workerId}`);
  // Send alert to monitoring system
});

global.cortexWorkerPool.on('worker-error', ({ workerId, error }) => {
  console.error(`[WorkerPool] Worker error in ${workerId}:`, error);
  // Log to error tracking system
});

global.cortexWorkerPool.on('task-failed', ({ taskId, error, retried }) => {
  console.error(`[WorkerPool] Task ${taskId} failed:`, error);
  if (!retried) {
    // Task moved to DLQ, notify user
  }
});

global.cortexWorkerPool.on('pool-scaled-up', ({ count, newSize }) => {
  console.log(`[WorkerPool] Scaled up by ${count} workers to ${newSize}`);
});
```

## Example: Complete Integration

Here's a complete example showing before and after:

### Before (task-executor.js)
```javascript
// Old task executor spawning processes
const { spawn } = require('child_process');

async function executeTask(taskType, taskData) {
  return new Promise((resolve, reject) => {
    const worker = spawn('node', ['./workers/task-worker.js'], {
      env: {
        TASK_TYPE: taskType,
        TASK_DATA: JSON.stringify(taskData)
      }
    });

    let output = '';

    worker.stdout.on('data', (data) => {
      output += data.toString();
    });

    worker.on('close', (code) => {
      if (code === 0) {
        try {
          resolve(JSON.parse(output));
        } catch (error) {
          reject(error);
        }
      } else {
        reject(new Error(`Worker exited with code ${code}`));
      }
    });

    worker.on('error', reject);
  });
}

module.exports = { executeTask };
```

### After (task-executor.js)
```javascript
// New task executor using worker pool
const { createWorkerPool } = require('./lib/worker-pool');

let pool;

async function initializePool() {
  if (!pool) {
    pool = await createWorkerPool({
      poolSize: 20,
      taskTimeout: 300000,
      autoRestart: true
    });
  }
  return pool;
}

async function executeTask(taskType, taskData) {
  const pool = await initializePool();

  return await pool.submitTask({
    type: taskType,
    payload: taskData,
    priority: 10
  });
}

async function shutdown() {
  if (pool) {
    await pool.shutdown(true);
  }
}

module.exports = { executeTask, shutdown, initializePool };
```

## Dynamic Pool Scaling

You can dynamically scale the pool based on workload:

```javascript
// Monitor queue depth and scale accordingly
setInterval(() => {
  const metrics = global.cortexWorkerPool.getPoolMetrics();

  // Scale up if queue is backing up
  if (metrics.tasks.queued > 50 && metrics.workers.total < 50) {
    console.log('Queue backing up, scaling up pool...');
    global.cortexWorkerPool.scaleUp(10);
  }

  // Scale down if mostly idle
  if (metrics.tasks.queued === 0 &&
      metrics.workers.busy < 5 &&
      metrics.workers.total > 10) {
    console.log('Pool mostly idle, scaling down...');
    global.cortexWorkerPool.scaleDown(5);
  }
}, 30000); // Check every 30 seconds
```

## Testing the Integration

1. **Test basic functionality:**
```bash
node lib/worker-pool/test-pool.js
```

2. **Test with real tasks:**
```javascript
// Create a test task
const result = await global.cortexWorkerPool.submitTask({
  type: 'implementation',
  payload: {
    feature: 'test-feature',
    requirements: ['test-req']
  }
});
console.log('Test result:', result);
```

3. **Monitor worker reuse:**
```javascript
// Submit 100 tasks and check reuse rate
for (let i = 0; i < 100; i++) {
  await global.cortexWorkerPool.submitTask({
    type: 'test',
    payload: { taskId: i }
  });
}

const metrics = global.cortexWorkerPool.getPoolMetrics();
console.log('Worker reuse rate:', metrics.performance.workerReuseRate);
// Should show 95%+ reuse rate
```

## Migration Checklist

- [ ] Initialize worker pool during Cortex startup
- [ ] Register task handlers in worker-process.js
- [ ] Replace spawn() calls with pool.submitTask()
- [ ] Add pool metrics to monitoring
- [ ] Implement graceful shutdown
- [ ] Add event listeners for critical events
- [ ] Test with small pool size first (5 workers)
- [ ] Monitor worker reuse rate (should be >95%)
- [ ] Check for zombie workers (should auto-restart)
- [ ] Verify memory usage is stable
- [ ] Scale up to production pool size (20+ workers)
- [ ] Load test with concurrent tasks
- [ ] Update documentation

## Performance Expectations

After integration, you should see:

| Metric | Expected Result |
|--------|----------------|
| Worker Reuse Rate | 95%+ |
| Task Startup Time | <10ms (vs ~500ms before) |
| Zombie Workers | 0 (auto-detected and restarted) |
| Memory Usage | Stable (no process spawn overhead) |
| Max Concurrent Tasks | 20+ (limited by pool size) |

## Troubleshooting

### Workers not reusing
- Check that workers are returning to 'ready' state after tasks
- Verify workers aren't crashing (check logs)
- Ensure task handlers call cleanup properly

### High memory usage
- Lower `workerMemoryLimitMB` config
- Enable auto-restart for memory leaks
- Check for memory leaks in task handlers

### Tasks timing out
- Increase `taskTimeout` config
- Check worker heartbeats are being received
- Verify workers aren't stuck in zombie state

## Support

For issues or questions:
1. Check logs in `logs/worker-pool.log`
2. Get pool metrics: `pool.getPoolMetrics()`
3. Check worker health: `pool.getAllWorkersStatus()`
4. Review the README.md for detailed API docs
