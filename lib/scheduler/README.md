# Intelligent Scheduler

ML-powered task scheduling system for Cortex with resource prediction, SLA-aware prioritization, and admission control.

## Features

- **ML-Based Resource Prediction**: Predicts CPU, memory, tokens, and duration for each task
- **Preemptive Feasibility Checks**: Prevents OOM by checking resources before accepting tasks
- **SLA-Aware Prioritization**: Prioritizes tasks based on deadlines, type, dependencies, and wait time
- **Admission Control**: Rejects tasks when system is overloaded (backpressure signaling)
- **Online Learning**: Improves predictions as tasks complete
- **Zero Heavy Dependencies**: Pure JavaScript ML (no numpy, sklearn, tensorflow)
- **100-Agent Scale**: Designed to run 100+ agents on 16GB RAM

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          Intelligent Scheduler                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │   Resource   │  │ Feasibility  │  │ Priority │ │
│  │  Predictor   │→ │   Checker    │→ │  Engine  │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│         ↓                  ↓                ↓      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │  ML Models   │  │   System     │  │  Queue   │ │
│  │ (Linear Reg) │  │  Resources   │  │ Manager  │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│         ↓                                          │
│  ┌──────────────┐                                 │
│  │  Training    │                                 │
│  │    Data      │                                 │
│  └──────────────┘                                 │
└─────────────────────────────────────────────────────┘
```

## Quick Start

```javascript
const { createIntelligentScheduler } = require('./lib/scheduler');

// Create scheduler
const scheduler = createIntelligentScheduler({
  maxMemoryMB: 12288,        // 12GB for tasks, leave 4GB for OS
  maxConcurrentTasks: 20,    // Max 20 tasks running simultaneously
  tokenBudgetPerHour: 1000000 // 1M tokens per hour
});

// Check if we can accept a task
const task = {
  id: 'task-123',
  type: 'implementation',
  description: 'Implement user authentication feature',
  priority: 'P1',
  deadline: new Date(Date.now() + 3600000) // 1 hour from now
};

const check = await scheduler.canAcceptTask(task);
console.log('Can accept:', check.feasible);
console.log('Estimated resources:', check.estimatedResources);

if (check.feasible) {
  // Schedule the task
  const decision = scheduler.scheduleTask(task);
  console.log('Task scheduled with priority:', decision.priority);
  console.log('Queue position:', decision.queuePosition);

  // When task starts
  scheduler.startTask(task.id);

  // When task completes, report outcome for ML learning
  scheduler.reportOutcome(task.id, {
    memoryMB: 450,
    cpuSeconds: 120,
    tokens: 15000,
    durationMs: 180000
  });
} else {
  console.log('Task rejected:', check.reason);
  console.log('Estimated wait time:', check.estimatedWaitTimeMs, 'ms');
}
```

## API Reference

### `createIntelligentScheduler(options)`

Creates a new intelligent scheduler instance.

**Options:**
- `maxMemoryMB` (number): Maximum memory for all tasks (default: 12288)
- `maxConcurrentTasks` (number): Max concurrent tasks (default: 20)
- `tokenBudgetPerHour` (number): Token budget per hour (default: 1000000)
- `minSamplesForML` (number): Min samples before using ML (default: 50)
- `fallbackToHeuristics` (boolean): Use heuristics when ML unavailable (default: true)

### `scheduler.canAcceptTask(task)`

Check if a task can be accepted.

**Parameters:**
- `task` (object): Task to check
  - `id` (string): Task ID
  - `type` (string): Task type (implementation, security, etc.)
  - `description` (string): Task description
  - `priority` (string): Priority level (P0, P1, P2, P3)
  - `deadline` (Date, optional): Task deadline

**Returns:**
```javascript
{
  feasible: boolean,
  reason: string,              // If not feasible
  estimatedResources: {
    memoryMB: number,
    cpuSeconds: number,
    tokens: number,
    durationMs: number
  },
  predictionMethod: 'ml' | 'heuristic',
  estimatedWaitTimeMs: number  // Time until resources available
}
```

### `scheduler.scheduleTask(task)`

Schedule a task for execution.

**Returns:**
```javascript
{
  scheduled: boolean,
  taskId: string,
  priority: number,            // Priority score
  queuePosition: number,       // Position in queue
  queueSize: number,
  estimatedResources: { ... }
}
```

### `scheduler.reportOutcome(taskId, actualResources)`

Report task completion for ML learning.

**Parameters:**
- `taskId` (string): Task ID
- `actualResources` (object):
  - `memoryMB` (number): Actual memory used
  - `cpuSeconds` (number): Actual CPU time
  - `tokens` (number): Actual tokens used
  - `durationMs` (number): Actual duration

**Returns:**
```javascript
{
  recorded: true,
  accuracy: {
    memoryError: number,
    memoryErrorPercent: number,
    tokenError: number,
    tokenErrorPercent: number
  }
}
```

### `scheduler.getSchedule()`

Get current schedule with queue state.

**Returns:**
```javascript
{
  queue: [...],              // Prioritized task list
  queueDepth: number,
  runningTasks: [...],
  systemCapacity: { ... }
}
```

### `scheduler.getStats()`

Get scheduler statistics.

**Returns:**
```javascript
{
  scheduler: {
    totalRequests: number,
    acceptedTasks: number,
    rejectedTasks: number,
    completedTasks: number,
    rejectionReasons: { ... }
  },
  predictor: { ... },
  priority: { ... },
  capacity: { ... }
}
```

## ML Models

### Linear Regression

Used for resource prediction (memory, CPU, tokens, duration).

**Algorithm**: Stochastic Gradient Descent (SGD) with online learning
- Updates weights incrementally as new samples arrive
- L2 regularization to prevent overfitting
- Feature normalization using z-score

**Features (18 total)**:
1. Task type (one-hot encoded, 9 dimensions)
2. Description length (normalized)
3. Description word count (normalized)
4. Description complexity score
5. File count estimate (normalized)
6. Has deadline (binary)
7. Priority level (normalized)
8. Historical mean for task type
9. Historical std for task type

### Heuristic Fallback

When insufficient training data (&lt;50 samples), uses heuristic estimates based on task type:

| Task Type | Memory | CPU | Tokens | Duration |
|-----------|--------|-----|--------|----------|
| implementation | 800 MB | 180s | 50k | 5 min |
| security | 600 MB | 120s | 25k | 3 min |
| documentation | 400 MB | 60s | 15k | 2 min |
| fix | 700 MB | 150s | 40k | 4 min |

## Priority Scoring

Tasks are prioritized using a weighted scoring system:

```
Priority Score =
  Base Priority × 0.25 +
  SLA Urgency × 0.30 +
  Dependency Score × 0.15 +
  Resource Efficiency × 0.15 +
  Starvation Prevention × 0.15
```

**Base Priority**: Task type weight × priority level multiplier
**SLA Urgency**: Increases exponentially as deadline approaches
**Dependency Score**: Tasks blocking others get priority boost
**Resource Efficiency**: Prefers tasks that fit current capacity
**Starvation Prevention**: Long-waiting tasks get progressive boost

## Feasibility Checks

Before accepting a task, the scheduler checks:

1. **Memory Availability**: Is there enough free memory?
2. **Worker Slots**: Are there available worker slots?
3. **Token Budget**: Is there token budget remaining?
4. **System Health**: Is CPU/memory usage within limits?
5. **Queue Depth**: Is queue below maximum depth?

If any check fails, the task is rejected with a specific reason and estimated wait time.

## Configuration

See `coordination/config/scheduler-config.json` for full configuration options.

Key settings:
- `resourceLimits`: System resource constraints
- `sla.priorityWeights`: Task type priority weights
- `prediction.minSamplesForML`: Samples needed for ML
- `admission.maxQueueDepth`: Max queue size before backpressure

## Data Storage

Training data and models are stored in:
- `coordination/scheduler-data/task-outcomes.jsonl` - Training outcomes
- `coordination/scheduler-data/models/` - Saved ML models
- `coordination/scheduler-data/token-usage.json` - Token tracking

## Events

The scheduler emits events for monitoring:

```javascript
scheduler.on('task-scheduled', (decision) => {
  console.log('Task scheduled:', decision.taskId);
});

scheduler.on('task-started', ({ taskId }) => {
  console.log('Task started:', taskId);
});

scheduler.on('task-completed', ({ taskId, accuracy }) => {
  console.log('Task completed:', taskId);
  console.log('Prediction accuracy:', accuracy);
});

scheduler.on('health-check', ({ capacity, queueDepth }) => {
  console.log('System capacity:', capacity);
  console.log('Queue depth:', queueDepth);
});
```

## Best Practices

1. **Always report outcomes**: Call `reportOutcome()` when tasks complete to improve ML accuracy
2. **Set realistic limits**: Configure `maxMemoryMB` and `maxConcurrentTasks` based on your system
3. **Monitor accuracy**: Use `getAccuracyMetrics()` to track prediction quality
4. **Handle rejections**: Implement retry logic for rejected tasks
5. **Use priorities**: Set appropriate task priorities and deadlines
6. **Retrain periodically**: Call `retrainModels()` after significant data accumulation

## Performance

Designed for:
- **Scale**: 100+ agents on 16GB RAM
- **Throughput**: 20 concurrent tasks
- **Token Budget**: 1M tokens/hour
- **Latency**: &lt;10ms for scheduling decisions
- **Accuracy**: &gt;80% prediction accuracy after 500+ samples

## Examples

### Example 1: Basic Usage

```javascript
const scheduler = createIntelligentScheduler();

const task = {
  id: 'impl-001',
  type: 'implementation',
  description: 'Add user authentication',
  priority: 'P1'
};

const check = await scheduler.canAcceptTask(task);
if (check.feasible) {
  scheduler.scheduleTask(task);
}
```

### Example 2: Priority Queue Management

```javascript
// Get current schedule
const schedule = scheduler.getSchedule();
console.log('Queue depth:', schedule.queueDepth);
console.log('Running tasks:', schedule.runningTasks.length);

// Get next task to execute
const next = scheduler.getNextTask();
if (next) {
  console.log('Next task:', next.task.id);
  console.log('Priority:', next.priority);
}
```

### Example 3: Monitoring and Metrics

```javascript
// Get overall statistics
const stats = scheduler.getStats();
console.log('Acceptance rate:',
  stats.scheduler.acceptedTasks / stats.scheduler.totalRequests);

// Get prediction accuracy
const accuracy = scheduler.getAccuracyMetrics();
console.log('Memory prediction error:', accuracy.memoryMB.mape, '%');
console.log('Token prediction error:', accuracy.tokens.mape, '%');

// Get system capacity
const capacity = scheduler.getSystemCapacity();
console.log('Available memory:', capacity.resources.memory.availableMB);
console.log('Available workers:', capacity.resources.workers.available);
```

### Example 4: Custom Configuration

```javascript
const scheduler = createIntelligentScheduler({
  maxMemoryMB: 10240,  // 10GB
  maxConcurrentTasks: 15,
  tokenBudgetPerHour: 500000,
  priorityWeights: {
    security: 2.0,      // Higher priority for security tasks
    documentation: 0.5  // Lower priority for docs
  },
  minSamplesForML: 100  // Require more samples before using ML
});
```

### Example 5: Integration with Worker Pool

```javascript
class TaskExecutor {
  constructor() {
    this.scheduler = createIntelligentScheduler();
  }

  async submitTask(task) {
    // Check if we can accept
    const check = await this.scheduler.canAcceptTask(task);

    if (!check.feasible) {
      throw new Error(`Task rejected: ${check.reason}`);
    }

    // Schedule it
    const decision = this.scheduler.scheduleTask(task);

    // Execute
    const startTime = Date.now();
    this.scheduler.startTask(task.id);

    try {
      const result = await this.executeTask(task);

      // Report outcome
      this.scheduler.reportOutcome(task.id, {
        memoryMB: result.memoryUsed,
        cpuSeconds: result.cpuTime,
        tokens: result.tokensUsed,
        durationMs: Date.now() - startTime
      });

      return result;
    } catch (error) {
      // Still report outcome even on failure
      this.scheduler.reportOutcome(task.id, {
        memoryMB: 0,
        cpuSeconds: 0,
        tokens: 0,
        durationMs: Date.now() - startTime
      });
      throw error;
    }
  }

  async executeTask(task) {
    // Execute task logic here
    return { success: true };
  }
}
```

## Troubleshooting

### Tasks are being rejected

Check rejection reasons:
```javascript
const stats = scheduler.getStats();
console.log('Rejection reasons:', stats.scheduler.rejectionReasons);
```

Common reasons:
- `insufficient-memory`: Increase `maxMemoryMB` or reduce concurrent tasks
- `no-worker-slots`: Increase `maxConcurrentTasks`
- `token-budget-exceeded`: Increase `tokenBudgetPerHour`
- `queue-full`: System is overloaded, implement backoff retry

### Predictions are inaccurate

1. Check if ML is being used:
```javascript
const stats = scheduler.getStats();
console.log('ML predictions:', stats.predictor.predictions.mlPredictions);
console.log('Heuristic predictions:', stats.predictor.predictions.heuristicPredictions);
```

2. Ensure you're reporting outcomes:
```javascript
// Always call this after task completion!
scheduler.reportOutcome(taskId, actualResources);
```

3. Retrain models:
```javascript
const result = scheduler.retrainModels(20); // 20 epochs
console.log('Training results:', result);
```

### Memory usage is high

1. Check current capacity:
```javascript
const capacity = scheduler.getSystemCapacity();
console.log('Memory usage:', capacity.health.memoryPercent, '%');
```

2. Reduce limits:
```javascript
scheduler.setResourceLimits({
  maxMemoryMB: 8192,  // Reduce from 12GB to 8GB
  maxConcurrentTasks: 15  // Reduce concurrency
});
```

## License

MIT
