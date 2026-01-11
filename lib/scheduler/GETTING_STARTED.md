# Getting Started with Intelligent Scheduler

## Quick Start (5 minutes)

### 1. Basic Usage

```javascript
const { createIntelligentScheduler } = require('./lib/scheduler');

// Create scheduler with defaults
const scheduler = createIntelligentScheduler();

// Define a task
const task = {
  id: 'task-001',
  type: 'implementation',
  description: 'Implement user authentication',
  priority: 'P1'
};

// Check if we can accept it
const check = scheduler.canAcceptTask(task);
console.log('Can accept:', check.feasible);
console.log('Estimated memory:', check.estimatedResources.memoryMB, 'MB');

// Schedule it
if (check.feasible) {
  scheduler.scheduleTask(task);
}
```

### 2. Complete Workflow

```javascript
const { createIntelligentScheduler } = require('./lib/scheduler');

const scheduler = createIntelligentScheduler({
  maxMemoryMB: 12288,       // 12GB for tasks
  maxConcurrentTasks: 20,   // Max 20 parallel tasks
  tokenBudgetPerHour: 1000000
});

// 1. Check admission
const task = {
  id: 'impl-123',
  type: 'implementation',
  description: 'Add OAuth integration with Google',
  priority: 'P1',
  createdAt: new Date().toISOString()
};

const admission = scheduler.canAcceptTask(task);

if (!admission.feasible) {
  console.log(`Cannot accept: ${admission.reason}`);
  console.log(`Wait time: ${admission.estimatedWaitTimeMs}ms`);
  return;
}

// 2. Schedule the task
const decision = scheduler.scheduleTask(task);
console.log(`Scheduled at position ${decision.queuePosition + 1}`);
console.log(`Priority score: ${decision.priority}`);

// 3. Get next task to execute
const next = scheduler.getNextTask();
if (next && next.task.id === task.id) {
  // 4. Mark as started
  scheduler.startTask(task.id);

  // 5. Execute task (your code here)
  const startTime = Date.now();
  try {
    await executeYourTask(task);

    // 6. Report success
    scheduler.reportOutcome(task.id, {
      memoryMB: 650,
      cpuSeconds: 145,
      tokens: 38000,
      durationMs: Date.now() - startTime
    });
  } catch (error) {
    // Still report outcome even on failure
    scheduler.reportOutcome(task.id, {
      memoryMB: 0,
      cpuSeconds: 0,
      tokens: 0,
      durationMs: Date.now() - startTime
    });
  }
}
```

## Configuration

### Minimal Configuration

```javascript
const scheduler = createIntelligentScheduler();
// Uses all defaults - good for getting started
```

### Recommended Production Configuration

```javascript
const scheduler = createIntelligentScheduler({
  // Resource Limits
  maxMemoryMB: 12288,             // 12GB (leave 4GB for OS on 16GB system)
  maxConcurrentTasks: 20,         // Adjust based on CPU cores
  tokenBudgetPerHour: 1000000,    // 1M tokens/hour
  tokenBudgetPerDay: 10000000,    // 10M tokens/day

  // SLA Settings
  defaultDeadlineMinutes: 60,     // Default 1 hour deadline
  priorityWeights: {
    security: 1.5,                // Higher priority for security
    implementation: 1.0,
    documentation: 0.8            // Lower priority for docs
  },

  // ML Settings
  minSamplesForML: 50,            // Use ML after 50 samples
  fallbackToHeuristics: true,     // Graceful degradation
  modelUpdateInterval: 100,       // Save models every 100 updates
  conservativeMultiplier: 1.2,    // 20% safety margin

  // Admission Control
  enableBackpressure: true,       // Reject when overloaded
  maxQueueDepth: 100,             // Max 100 queued tasks
  rejectOnOverload: true          // Don't queue if system unhealthy
});
```

### Environment-Specific Configurations

#### Development (Laptop)
```javascript
const scheduler = createIntelligentScheduler({
  maxMemoryMB: 4096,        // 4GB
  maxConcurrentTasks: 5,    // Fewer tasks
  tokenBudgetPerHour: 100000
});
```

#### Production (Server)
```javascript
const scheduler = createIntelligentScheduler({
  maxMemoryMB: 12288,       // 12GB
  maxConcurrentTasks: 20,   // More tasks
  tokenBudgetPerHour: 1000000
});
```

#### High-Scale (100+ agents)
```javascript
const scheduler = createIntelligentScheduler({
  maxMemoryMB: 51200,       // 50GB
  maxConcurrentTasks: 100,  // 100 concurrent
  tokenBudgetPerHour: 5000000
});
```

## Task Types

The scheduler recognizes these task types (case-insensitive):

- `implementation` - Feature implementation (high resource usage)
- `security` - Security audits and scans (high priority)
- `documentation` - Documentation tasks (low resource usage)
- `review` - Code reviews
- `test` - Test execution
- `fix` - Bug fixes
- `scan` - Code scanning
- `pr-creation` - Pull request creation
- `unknown` - Default fallback

## Priority Levels

- `P0` or `critical` - Highest priority (3.0x multiplier)
- `P1` or `high` - High priority (2.0x multiplier)
- `P2` or `medium` - Normal priority (1.0x multiplier)
- `P3` or `low` - Low priority (0.5x multiplier)

## Monitoring

### Get System Status

```javascript
// Check current capacity
const capacity = scheduler.getSystemCapacity();
console.log('Available memory:', capacity.resources.memory.availableMB, 'MB');
console.log('Available workers:', capacity.resources.workers.available);
console.log('System healthy:', capacity.health.healthy);
```

### Get Statistics

```javascript
const stats = scheduler.getStats();

// Scheduler stats
console.log('Acceptance rate:',
  (stats.scheduler.acceptedTasks / stats.scheduler.totalRequests * 100).toFixed(1) + '%');

// Predictor stats
console.log('Training samples:', stats.predictor.training.totalRecords);
console.log('ML predictions:', stats.predictor.predictions.mlPredictions);

// Queue stats
console.log('Queue depth:', stats.priority.queueDepth);
```

### Get Prediction Accuracy

```javascript
const accuracy = scheduler.getAccuracyMetrics();

if (accuracy) {
  console.log('Memory prediction error:', accuracy.memoryMB.mape.toFixed(2) + '%');
  console.log('Token prediction error:', accuracy.tokens.mape.toFixed(2) + '%');
}
```

### Listen to Events

```javascript
scheduler.on('task-scheduled', (decision) => {
  console.log('Task scheduled:', decision.taskId);
  console.log('Priority:', decision.priority.toFixed(2));
});

scheduler.on('task-completed', ({ taskId, accuracy }) => {
  console.log('Task completed:', taskId);
  if (accuracy) {
    console.log('Prediction error:', accuracy.memoryErrorPercent.toFixed(1) + '%');
  }
});

scheduler.on('health-check', ({ capacity, queueDepth }) => {
  if (!capacity.health.healthy) {
    console.warn('System unhealthy!');
  }
});
```

## Common Patterns

### Pattern 1: Simple Task Execution

```javascript
function executeTask(task) {
  const check = scheduler.canAcceptTask(task);

  if (!check.feasible) {
    throw new Error(`Task rejected: ${check.reason}`);
  }

  scheduler.scheduleTask(task);
  scheduler.startTask(task.id);

  // Do work...

  scheduler.reportOutcome(task.id, actualResources);
}
```

### Pattern 2: Retry on Rejection

```javascript
async function scheduleWithRetry(task, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    const check = scheduler.canAcceptTask(task);

    if (check.feasible) {
      return scheduler.scheduleTask(task);
    }

    // Wait before retry
    if (check.estimatedWaitTimeMs) {
      await sleep(check.estimatedWaitTimeMs);
    } else {
      await sleep(60000); // Default 1 minute
    }
  }

  throw new Error('Failed to schedule task after retries');
}
```

### Pattern 3: Batch Scheduling

```javascript
function scheduleBatch(tasks) {
  const accepted = [];
  const rejected = [];

  for (const task of tasks) {
    const check = scheduler.canAcceptTask(task);

    if (check.feasible) {
      scheduler.scheduleTask(task);
      accepted.push(task);
    } else {
      rejected.push({ task, reason: check.reason });
    }
  }

  return { accepted, rejected };
}
```

### Pattern 4: Worker Pool Integration

```javascript
class WorkerPool {
  constructor() {
    this.scheduler = createIntelligentScheduler();
    this.workers = new Map();
  }

  async submitTask(task) {
    // Check admission
    const check = this.scheduler.canAcceptTask(task);
    if (!check.feasible) {
      return { accepted: false, reason: check.reason };
    }

    // Schedule
    const decision = this.scheduler.scheduleTask(task);

    // Wait for worker slot
    const worker = await this.getNextAvailableWorker();

    // Execute
    this.scheduler.startTask(task.id);
    const startTime = Date.now();

    try {
      const result = await worker.execute(task);

      // Report success
      this.scheduler.reportOutcome(task.id, {
        memoryMB: result.memoryUsed,
        cpuSeconds: result.cpuTime,
        tokens: result.tokensUsed,
        durationMs: Date.now() - startTime
      });

      return { success: true, result };
    } catch (error) {
      // Report failure
      this.scheduler.reportOutcome(task.id, {
        memoryMB: 0,
        cpuSeconds: 0,
        tokens: 0,
        durationMs: Date.now() - startTime
      });

      throw error;
    }
  }
}
```

## Troubleshooting

### Problem: All tasks are rejected

**Symptoms**: `canAcceptTask()` always returns `feasible: false`

**Solutions**:
1. Check rejection reason:
   ```javascript
   const check = scheduler.canAcceptTask(task);
   console.log('Reason:', check.reason);
   ```

2. Common reasons and fixes:
   - `system-unhealthy`: System CPU/memory too high
     - Solution: Reduce concurrent tasks or increase system resources
   - `insufficient-memory`: Not enough memory for predicted usage
     - Solution: Increase `maxMemoryMB` or wait for tasks to complete
   - `no-worker-slots`: All worker slots occupied
     - Solution: Increase `maxConcurrentTasks`
   - `token-budget-exceeded`: Hourly/daily token limit reached
     - Solution: Increase token budget or wait for next hour
   - `queue-full`: Queue at maximum depth
     - Solution: Increase `maxQueueDepth` or process queue faster

### Problem: Predictions are inaccurate

**Symptoms**: Large error percentages in prediction accuracy

**Solutions**:
1. Check if ML is being used:
   ```javascript
   const stats = scheduler.getStats();
   console.log('ML predictions:', stats.predictor.predictions.mlPredictions);
   ```

2. Ensure outcomes are being reported:
   ```javascript
   // ALWAYS call this after task completion!
   scheduler.reportOutcome(taskId, actualResources);
   ```

3. Retrain models:
   ```javascript
   const result = scheduler.retrainModels(20); // 20 epochs
   console.log('Training result:', result);
   ```

4. Check data quality:
   ```javascript
   const summary = scheduler.getStats().predictor.training;
   console.log('Training samples:', summary.totalRecords);
   console.log('Task types:', summary.taskTypes);
   ```

### Problem: Queue is not processing

**Symptoms**: Tasks stay in queue but never execute

**Solution**: You need to manually dequeue and execute:
```javascript
// Continuously process queue
setInterval(() => {
  const next = scheduler.getNextTask();
  if (next) {
    executeTask(next.task);
  }
}, 1000);
```

## Examples

Run the included examples:

```bash
# Basic examples (7 scenarios)
node lib/scheduler/examples.js

# Quick demo
node lib/scheduler/quick-demo.js

# Full test suite
node lib/scheduler/test-scheduler.js
```

## Next Steps

1. **Integrate with your worker pool**: Connect the scheduler to your task execution system
2. **Configure for your environment**: Adjust resource limits based on your hardware
3. **Monitor accuracy**: Watch prediction errors and retrain as needed
4. **Tune priorities**: Adjust task type weights for your workflow
5. **Set up alerts**: Monitor rejection rates and system health

## Support

For detailed API documentation, see:
- `lib/scheduler/README.md` - Complete API reference
- `lib/scheduler/IMPLEMENTATION_SUMMARY.md` - Implementation details
- `lib/scheduler/examples.js` - 7 comprehensive examples
- `coordination/config/scheduler-config.json` - Configuration reference
