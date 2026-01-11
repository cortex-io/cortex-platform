# Coordination Daemon Quick Start

Get started with the Coordination Daemon in 5 minutes.

## Installation

1. Install the WebSocket dependency:

```bash
npm install ws
```

## Start the Daemon

### Option 1: Using the CLI

```bash
# Default configuration
node scripts/coordination-daemon.js

# Production mode with persistence
node scripts/coordination-daemon.js --preset production

# Custom ports
node scripts/coordination-daemon.js --port 8080 --ws-port 8081
```

### Option 2: Programmatically

```javascript
const { createCoordinationDaemon } = require('./lib/coordination');

const daemon = createCoordinationDaemon({
  port: 9500,
  wsPort: 9501,
  persistence: 'periodic-snapshot'
});

await daemon.start();
```

## Create a Worker

```javascript
const { CoordinationClient } = require('./lib/coordination/client');

const client = new CoordinationClient({
  workerId: 'my-worker-001',
  capabilities: ['development', 'testing'],
  wsUrl: 'ws://localhost:9501'
});

// Handle task assignments
client.on('task_assigned', async (task) => {
  console.log('Got task:', task.id);

  // Do work...
  await doWork(task);

  // Report completion
  client.completeTask(task.id, { status: 'success' });
});

await client.connect();
```

## Assign Tasks

### Via HTTP API

```bash
curl -X POST http://localhost:9500/api/tasks/assign \
  -H "Content-Type: application/json" \
  -d '{
    "taskId": "task-123",
    "taskData": {
      "title": "My task",
      "type": "development"
    }
  }'
```

### Programmatically

```javascript
const result = await daemon.assignTask('task-123', null, {
  title: 'My task',
  type: 'development',
  capabilities: ['development']
});

console.log('Assigned to:', result.workerId);
```

## Monitor Performance

```bash
# Get metrics
curl http://localhost:9500/api/metrics

# Get state
curl http://localhost:9500/api/state

# Health check
curl http://localhost:9500/health
```

## Run Examples

### Basic Daemon
```bash
node lib/coordination/examples/basic-daemon.js
```

### Basic Worker
```bash
# Terminal 1: Start daemon
node lib/coordination/examples/basic-daemon.js

# Terminal 2: Start worker
node lib/coordination/examples/basic-worker.js worker-001 development
```

### Task Orchestrator
```bash
# Terminal 1: Start orchestrator (auto-creates tasks)
node lib/coordination/examples/task-orchestrator.js

# Terminal 2: Start workers
node lib/coordination/examples/basic-worker.js worker-001 development &
node lib/coordination/examples/basic-worker.js worker-002 security &
node lib/coordination/examples/basic-worker.js worker-003 testing &
```

### Performance Test
```bash
node lib/coordination/examples/performance-test.js
```

This will:
- Start a daemon
- Create 10 workers
- Assign 1,000 tasks
- Measure throughput and latency
- Validate 1,000+ ops/sec target

## Common Operations

### Register a Worker
```javascript
await client.connect();
```

### Complete a Task
```javascript
client.completeTask(taskId, {
  status: 'success',
  result: { /* your data */ }
});
```

### Fail a Task
```javascript
client.failTask(taskId, {
  message: 'Task failed',
  error: error.stack
});
```

### Update Progress
```javascript
client.updateProgress(taskId, 50); // 50% complete
```

### Subscribe to State Changes
```javascript
client.subscribe(['tasks:*', 'workers:*']);

client.on('state_change', (change) => {
  console.log('State changed:', change);
});
```

## Environment Variables

```bash
# HTTP port
export COORDINATION_PORT=9500

# WebSocket port
export COORDINATION_WS_PORT=9501

# Persistence mode
export COORDINATION_PERSISTENCE=periodic-snapshot

# Snapshot path
export COORDINATION_SNAPSHOT_PATH=./coordination/state-snapshot.json
```

## Integration with Existing Cortex Workers

Replace file-based coordination:

### Before
```javascript
// Poll task-queue.json
const tasks = JSON.parse(fs.readFileSync('coordination/task-queue.json'));
```

### After
```javascript
const { CoordinationClient } = require('./lib/coordination/client');

const client = new CoordinationClient({
  workerId: process.env.WORKER_ID,
  capabilities: ['your-capabilities']
});

client.on('task_assigned', handleTask);
await client.connect();
```

## Next Steps

- Read the [full README](./README.md) for detailed documentation
- Explore [examples](./examples/) for more use cases
- Check [API reference](./README.md#api-reference) for all endpoints
- Review [performance tuning](./README.md#performance-tuning) for optimization

## Troubleshooting

### Workers not receiving tasks?
- Verify WebSocket connection: `client.connected` should be `true`
- Check capabilities match task requirements
- Monitor heartbeat: listen for `heartbeat_ack` events

### High latency?
- Check `metrics.daemon.averageLatency`
- Use `memory-only` persistence for development
- Reduce snapshot frequency in production

### Connection issues?
- Verify daemon is running: `curl http://localhost:9500/health`
- Check firewall settings for ports 9500 and 9501
- Review daemon logs for errors

## Support

For issues or questions:
1. Check the [README](./README.md)
2. Review [examples](./examples/)
3. Check daemon logs for errors
4. Verify network connectivity and ports
