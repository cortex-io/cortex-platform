# Async Coordination Daemon

High-performance coordination daemon for the Cortex project, designed to replace JSON file read/write polling with in-memory state management and real-time communication.

## Performance Targets

- **Throughput**: 1,000+ operations/second
- **Latency**: <100ms coordination latency
- **Persistence**: Configurable strategies (memory-only, periodic snapshots, WAL)
- **Communication**: WebSocket for real-time updates, HTTP REST for admin operations

## Architecture

### Components

1. **Coordination Daemon** (`daemon.js`)
   - Main coordination server
   - EventEmitter-based pub/sub
   - HTTP REST API for management
   - WebSocket server for real-time worker communication
   - Automatic worker heartbeat monitoring
   - Task assignment and lifecycle management

2. **State Store** (`state-store.js`)
   - High-performance in-memory state management
   - Map-based data structures for O(1) operations
   - Transactional updates with rollback support
   - Multiple persistence strategies:
     - `memory-only`: No persistence (fastest)
     - `periodic-snapshot`: Periodic state snapshots to disk
     - `write-ahead-log`: WAL for durability

3. **Message Bus** (`message-bus.js`)
   - Inter-process communication
   - Priority-based message queue
   - Delivery guarantees (at-most-once, at-least-once, exactly-once)
   - Broadcast and point-to-point messaging

4. **Client Library** (`client.js`)
   - Worker-side client for daemon communication
   - WebSocket-based real-time connection
   - Automatic reconnection
   - Heartbeat management
   - HTTP fallback for operations

## Installation

The daemon requires the following dependencies (add to package.json if not present):

```json
{
  "dependencies": {
    "express": "^5.2.1",
    "ws": "^8.0.0"
  }
}
```

Install dependencies:

```bash
npm install ws
```

## Quick Start

### Starting the Daemon

#### Using the CLI

```bash
# Start with default configuration
node scripts/coordination-daemon.js

# Start with production preset
node scripts/coordination-daemon.js --preset production

# Start with custom configuration
node scripts/coordination-daemon.js \
  --port 9500 \
  --ws-port 9501 \
  --persistence periodic-snapshot \
  --snapshot-interval 30000
```

#### Programmatically

```javascript
const { createCoordinationDaemon } = require('./lib/coordination');

const daemon = createCoordinationDaemon({
  port: 9500,
  wsPort: 9501,
  persistence: 'periodic-snapshot',
  snapshotInterval: 30000,
  snapshotPath: './coordination/state-snapshot.json'
});

await daemon.start();
```

### Connecting Workers

```javascript
const { CoordinationClient } = require('./lib/coordination/client');

const client = new CoordinationClient({
  workerId: 'worker-001',
  capabilities: ['development', 'security'],
  wsUrl: 'ws://localhost:9501',
  httpUrl: 'http://localhost:9500'
});

// Listen for task assignments
client.on('task_assigned', async (task) => {
  console.log('Received task:', task);

  try {
    // Do work...
    const result = await performTask(task);

    // Report completion
    client.completeTask(task.id, result);
  } catch (error) {
    // Report failure
    client.failTask(task.id, { message: error.message });
  }
});

// Connect to daemon
await client.connect();
```

## Configuration

### Configuration Presets

Four presets are available via `getConfigPreset()`:

#### Development
```javascript
{
  port: 9500,
  wsPort: 9501,
  persistence: 'memory-only',
  heartbeatInterval: 5000,
  heartbeatTimeout: 15000
}
```

#### Production
```javascript
{
  port: 9500,
  wsPort: 9501,
  persistence: 'periodic-snapshot',
  snapshotInterval: 30000,
  snapshotPath: './coordination/state-snapshot.json',
  heartbeatInterval: 5000,
  heartbeatTimeout: 15000,
  maxTasksPerWorker: 10
}
```

#### High Availability
```javascript
{
  port: 9500,
  wsPort: 9501,
  persistence: 'write-ahead-log',
  walPath: './coordination/wal.log',
  walSyncInterval: 1000,
  snapshotInterval: 60000,
  heartbeatInterval: 3000,
  heartbeatTimeout: 10000,
  maxTasksPerWorker: 5
}
```

#### Testing
```javascript
{
  port: 9500,
  wsPort: 9501,
  persistence: 'memory-only',
  heartbeatInterval: 1000,
  heartbeatTimeout: 3000,
  maxTasksPerWorker: 5
}
```

### Environment Variables

```bash
COORDINATION_PORT=9500                # HTTP API port
COORDINATION_WS_PORT=9501             # WebSocket port
COORDINATION_PERSISTENCE=periodic-snapshot
COORDINATION_SNAPSHOT_PATH=./coordination/state-snapshot.json
COORDINATION_WAL_PATH=./coordination/wal.log
```

## API Reference

### HTTP REST API

#### Health Check
```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "uptime": 123456,
  "version": "1.0.0"
}
```

#### Get State
```
GET /api/state
```

Response:
```json
{
  "workers": [...],
  "tasks": [...],
  "assignments": [...],
  "metadata": {
    "totalWorkers": 5,
    "totalTasks": 10,
    "activeAssignments": 3
  }
}
```

#### Get Metrics
```
GET /api/metrics
```

Response:
```json
{
  "daemon": {
    "operations": 1234,
    "operationsPerSecond": 145,
    "averageLatency": 23.5,
    "activeWorkers": 5,
    "activeTasks": 3,
    "uptime": 123456
  },
  "stateStore": {...},
  "messageBus": {...}
}
```

#### Register Worker
```
POST /api/workers/register
Content-Type: application/json

{
  "workerId": "worker-001",
  "capabilities": ["development", "security"],
  "metadata": {}
}
```

#### Unregister Worker
```
POST /api/workers/unregister
Content-Type: application/json

{
  "workerId": "worker-001"
}
```

#### Assign Task
```
POST /api/tasks/assign
Content-Type: application/json

{
  "taskId": "task-123",
  "workerId": "worker-001",  // Optional - daemon will auto-assign if omitted
  "taskData": {
    "title": "Example task",
    "capabilities": ["development"]
  }
}
```

#### Complete Task
```
POST /api/tasks/complete
Content-Type: application/json

{
  "taskId": "task-123",
  "result": {
    "status": "success",
    "output": "Task completed successfully"
  }
}
```

#### Fail Task
```
POST /api/tasks/fail
Content-Type: application/json

{
  "taskId": "task-123",
  "error": {
    "message": "Task failed",
    "code": "EXECUTION_ERROR"
  }
}
```

### WebSocket Protocol

#### Register Worker
```json
{
  "type": "register",
  "workerId": "worker-001",
  "capabilities": ["development"],
  "metadata": {}
}
```

Response:
```json
{
  "type": "registered",
  "workerId": "worker-001",
  "timestamp": 1638360000000
}
```

#### Heartbeat
```json
{
  "type": "heartbeat",
  "workerId": "worker-001"
}
```

Response:
```json
{
  "type": "heartbeat_ack",
  "timestamp": 1638360000000
}
```

#### Task Assignment (from daemon)
```json
{
  "type": "task_assigned",
  "task": {
    "id": "task-123",
    "title": "Example task",
    "status": "assigned",
    "assignedTo": "worker-001"
  },
  "timestamp": 1638360000000
}
```

#### Task Update (from worker)
```json
{
  "type": "task_update",
  "taskId": "task-123",
  "status": "in_progress",
  "progress": 50
}
```

#### Subscribe to State Changes
```json
{
  "type": "subscribe",
  "topics": ["tasks:set", "workers:update", "*"]
}
```

#### State Change Notification (from daemon)
```json
{
  "type": "state_change",
  "change": {
    "collection": "tasks",
    "key": "task-123",
    "operation": "set"
  },
  "timestamp": 1638360000000
}
```

## Client Library

### CoordinationClient API

#### Constructor
```javascript
new CoordinationClient({
  workerId: 'worker-001',
  capabilities: ['development'],
  wsUrl: 'ws://localhost:9501',
  httpUrl: 'http://localhost:9500',
  reconnect: true,
  reconnectInterval: 5000,
  heartbeatInterval: 5000,
  metadata: {}
})
```

#### Methods

- `connect()` - Connect to daemon via WebSocket
- `disconnect()` - Disconnect from daemon
- `updateTask(taskId, status, data)` - Update task status
- `completeTask(taskId, result)` - Mark task as completed
- `failTask(taskId, error)` - Mark task as failed
- `updateProgress(taskId, progress)` - Update task progress
- `subscribe(topics)` - Subscribe to state changes
- `getMetrics()` - Get client metrics

HTTP methods:
- `registerHttp()` - Register via HTTP
- `unregisterHttp()` - Unregister via HTTP
- `completeTaskHttp(taskId, result)` - Complete task via HTTP
- `failTaskHttp(taskId, error)` - Fail task via HTTP
- `getState()` - Get daemon state
- `getDaemonMetrics()` - Get daemon metrics

#### Events

- `connected` - Connected to daemon
- `disconnected` - Disconnected from daemon
- `reconnecting` - Attempting to reconnect
- `reconnected` - Reconnected successfully
- `registered` - Registered with daemon
- `task_assigned` - Task assigned to worker
- `state_change` - State change notification
- `heartbeat_ack` - Heartbeat acknowledged
- `error` - Error occurred

## Examples

### Example 1: Basic Worker

```javascript
const { CoordinationClient } = require('./lib/coordination/client');

async function startWorker() {
  const client = new CoordinationClient({
    workerId: 'worker-development-001',
    capabilities: ['development', 'testing'],
    wsUrl: 'ws://localhost:9501',
    httpUrl: 'http://localhost:9500'
  });

  client.on('task_assigned', async (task) => {
    console.log('Received task:', task.id);

    // Simulate work
    for (let i = 0; i <= 100; i += 10) {
      await sleep(1000);
      client.updateProgress(task.id, i);
      console.log(`Progress: ${i}%`);
    }

    client.completeTask(task.id, {
      status: 'success',
      message: 'Task completed'
    });
  });

  await client.connect();
  console.log('Worker started');
}

startWorker();
```

### Example 2: Task Orchestrator

```javascript
const { createCoordinationDaemon } = require('./lib/coordination');

async function startOrchestrator() {
  const daemon = createCoordinationDaemon({
    port: 9500,
    wsPort: 9501,
    persistence: 'periodic-snapshot',
    snapshotInterval: 30000
  });

  daemon.on('worker-registered', (data) => {
    console.log('Worker registered:', data.workerId);
  });

  daemon.on('task-completed', (data) => {
    console.log('Task completed:', data.taskId);
  });

  await daemon.start();

  // Assign tasks programmatically
  setInterval(async () => {
    const taskId = `task-${Date.now()}`;
    const result = await daemon.assignTask(taskId, null, {
      title: 'Automated task',
      type: 'development',
      capabilities: ['development']
    });

    if (result.success) {
      console.log(`Assigned ${taskId} to ${result.workerId}`);
    }
  }, 10000); // Every 10 seconds
}

startOrchestrator();
```

### Example 3: Monitoring Dashboard

```javascript
const fetch = require('node-fetch');

async function monitorDaemon() {
  const baseUrl = 'http://localhost:9500';

  setInterval(async () => {
    const metrics = await fetch(`${baseUrl}/api/metrics`).then(r => r.json());
    const state = await fetch(`${baseUrl}/api/state`).then(r => r.json());

    console.clear();
    console.log('=== Coordination Daemon Status ===\n');
    console.log(`Operations/sec: ${metrics.daemon.operationsPerSecond}`);
    console.log(`Average latency: ${metrics.daemon.averageLatency.toFixed(2)}ms`);
    console.log(`Active workers: ${state.metadata.totalWorkers}`);
    console.log(`Active tasks: ${metrics.daemon.activeTasks}`);
    console.log(`Queue depth: ${metrics.messageBus.queueDepth}`);
    console.log(`Uptime: ${Math.round(metrics.daemon.uptime / 1000)}s`);
  }, 2000);
}

monitorDaemon();
```

## Integration with Cortex

### Replacing File-Based Coordination

The daemon replaces the existing JSON file polling pattern:

**Before:**
```javascript
// Read task-queue.json
const tasks = JSON.parse(fs.readFileSync('coordination/task-queue.json'));
// Poll for changes...
```

**After:**
```javascript
const client = new CoordinationClient({
  workerId: 'worker-001',
  capabilities: ['development']
});

client.on('task_assigned', async (task) => {
  // Task received in real-time
  await processTask(task);
  client.completeTask(task.id, result);
});

await client.connect();
```

### Worker Pool Migration

Update existing workers to use the coordination client:

```javascript
// In worker initialization
const { CoordinationClient } = require('./lib/coordination/client');

class Worker {
  constructor(workerId, capabilities) {
    this.client = new CoordinationClient({
      workerId,
      capabilities,
      wsUrl: process.env.COORDINATION_WS_URL || 'ws://localhost:9501',
      httpUrl: process.env.COORDINATION_HTTP_URL || 'http://localhost:9500'
    });

    this.client.on('task_assigned', (task) => this.handleTask(task));
  }

  async start() {
    await this.client.connect();
  }

  async handleTask(task) {
    // Process task...
  }
}
```

## Performance Tuning

### Optimizing for High Throughput

1. **Disable Persistence** (development/testing):
```javascript
const daemon = createCoordinationDaemon({
  persistence: 'memory-only'
});
```

2. **Tune Snapshot Interval** (production):
```javascript
const daemon = createCoordinationDaemon({
  persistence: 'periodic-snapshot',
  snapshotInterval: 60000  // 1 minute
});
```

3. **Adjust Message Processing**:
```javascript
const messageBus = new MessageBus({
  processingInterval: 5,  // Process every 5ms for higher throughput
  maxQueueSize: 200000
});
```

4. **Worker Capacity**:
```javascript
const daemon = createCoordinationDaemon({
  maxTasksPerWorker: 20  // Allow more concurrent tasks
});
```

### Optimizing for Low Latency

1. **Disable WebSocket Compression**:
Already configured in daemon (perMessageDeflate: false)

2. **Reduce Heartbeat Interval**:
```javascript
const daemon = createCoordinationDaemon({
  heartbeatInterval: 3000,
  heartbeatTimeout: 10000
});
```

3. **Use WAL for Durability**:
```javascript
const daemon = createCoordinationDaemon({
  persistence: 'write-ahead-log',
  walSyncInterval: 500  // Sync every 500ms
});
```

## Troubleshooting

### High Latency

- Check `metrics.daemon.averageLatency`
- Verify network connectivity
- Reduce snapshot frequency
- Increase `processingInterval` for message bus

### Workers Not Receiving Tasks

- Verify WebSocket connection: check `client.connected`
- Check worker capabilities match task requirements
- Verify heartbeat is working: monitor `heartbeat_ack` events
- Check daemon logs for assignment errors

### State Not Persisting

- Verify snapshot path is writable
- Check disk space
- Review daemon logs for snapshot errors
- Ensure graceful shutdown for final snapshot

### Memory Usage

- Monitor `stateStore` metrics
- Reduce snapshot interval if using periodic strategy
- Clear completed tasks periodically
- Consider WAL strategy for large state

## License

MIT
