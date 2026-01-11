# Worker Pool Architecture

Visual guide to the Worker Pool Manager architecture and data flow.

## System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Cortex Application                             │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                    Worker Pool Manager                           │ │
│  │                                                                  │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │ │
│  │  │ Task Queue │  │   Health   │  │   Load     │  │ Metrics  │  │ │
│  │  │ (Priority) │  │  Monitor   │  │ Balancer   │  │Collector │  │ │
│  │  │            │  │            │  │            │  │          │  │ │
│  │  │ Min-Heap   │  │ Heartbeat  │  │Round-Robin │  │ Stats    │  │ │
│  │  │ DLQ        │  │ Zombie Det │  │Least-Load  │  │ Alerts   │  │ │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │ │
│  │         │               │               │              │         │ │
│  └─────────┼───────────────┼───────────────┼──────────────┼─────────┘ │
│            │               │               │              │           │
│            ▼               ▼               ▼              ▼           │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     Worker Processes (IPC)                      │  │
│  │                                                                 │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       ┌──────────┐  │  │
│  │  │ Worker 0 │  │ Worker 1 │  │ Worker 2 │  ...  │ Worker N │  │  │
│  │  │          │  │          │  │          │       │          │  │  │
│  │  │  Ready   │  │   Busy   │  │  Ready   │       │  Ready   │  │  │
│  │  │  PID:101 │  │  PID:102 │  │  PID:103 │       │  PID:12N │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘       └──────────┘  │  │
│  │       │             │             │                    │        │  │
│  │       ▼             ▼             ▼                    ▼        │  │
│  │  Heartbeat     Execute Task   Heartbeat           Heartbeat    │  │
│  │   (5s)         Return Result   (5s)                (5s)        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Pool Manager (pool-manager.js)
```
┌─────────────────────────────────────────┐
│         Pool Manager                    │
├─────────────────────────────────────────┤
│ Responsibilities:                       │
│ • Spawn & manage worker processes       │
│ • Assign tasks to available workers     │
│ • Monitor worker health                 │
│ • Handle worker crashes/restarts        │
│ • Collect & expose metrics              │
│ • Coordinate graceful shutdown          │
├─────────────────────────────────────────┤
│ Key Methods:                            │
│ • initialize(poolSize)                  │
│ • submitTask(task) → Promise<result>    │
│ • getWorkerStatus(workerId)             │
│ • getPoolMetrics()                      │
│ • scaleUp(count) / scaleDown(count)     │
│ • shutdown(graceful)                    │
└─────────────────────────────────────────┘
```

### Worker Process (worker-process.js)
```
┌─────────────────────────────────────────┐
│         Worker Process                  │
├─────────────────────────────────────────┤
│ Lifecycle:                              │
│ 1. Initialize → Ready state             │
│ 2. Receive task → Busy state            │
│ 3. Execute task                         │
│ 4. Return result                        │
│ 5. Cleanup memory                       │
│ 6. Ready state (REUSE)                  │
│ 7. Wait for next task                   │
├─────────────────────────────────────────┤
│ Responsibilities:                       │
│ • Execute assigned tasks                │
│ • Emit heartbeats (5s interval)         │
│ • Monitor self (memory, CPU)            │
│ • Cleanup between tasks                 │
│ • Handle shutdown signals               │
└─────────────────────────────────────────┘
```

### Task Queue (task-queue.js)
```
┌─────────────────────────────────────────┐
│         Priority Task Queue             │
├─────────────────────────────────────────┤
│ Structure: Min-Heap                     │
│                                         │
│        Priority 0 (highest)             │
│              /    \                     │
│       Priority 5  Priority 10           │
│         /    \       /    \             │
│      P:8   P:15   P:12  P:20            │
│                                         │
├─────────────────────────────────────────┤
│ Features:                               │
│ • O(log n) enqueue/dequeue              │
│ • FIFO within same priority             │
│ • Automatic retry (3 attempts)          │
│ • Exponential backoff                   │
│ • Dead Letter Queue (DLQ)               │
│ • Task timeout tracking                 │
└─────────────────────────────────────────┘
```

### Health Monitor (health-monitor.js)
```
┌─────────────────────────────────────────┐
│         Health Monitor                  │
├─────────────────────────────────────────┤
│ Monitoring:                             │
│                                         │
│ Worker → Heartbeat (5s)                 │
│    ↓                                    │
│ Monitor: Last heartbeat < 15s? ✓        │
│    ↓                                    │
│ 15s-30s: Warning (Missed heartbeat)     │
│    ↓                                    │
│ >30s: Critical (Zombie detected)        │
│    ↓                                    │
│ Auto-restart worker                     │
│                                         │
├─────────────────────────────────────────┤
│ Tracks:                                 │
│ • Heartbeat timestamps                  │
│ • Memory usage                          │
│ • CPU usage                             │
│ • Task execution counts                 │
│ • Restart attempts                      │
│ • Historical metrics                    │
└─────────────────────────────────────────┘
```

## Data Flow Diagrams

### Task Submission Flow

```
Client
  │
  │ submitTask({ type, payload, priority })
  │
  ▼
Pool Manager
  │
  │ 1. Validate task
  │
  ▼
Task Queue
  │
  │ 2. Enqueue with priority
  │
  ▼
Pool Manager
  │
  │ 3. Get available workers
  │ 4. Select worker (load balancing)
  │
  ▼
Worker Process
  │
  │ 5. Send task via IPC
  │ 6. Execute task
  │ 7. Return result via IPC
  │
  ▼
Pool Manager
  │
  │ 8. Resolve Promise
  │
  ▼
Client
  │
  │ result
  ▼
```

### Worker Lifecycle Flow

```
Pool Manager
  │
  │ fork(worker-process.js)
  │
  ▼
Worker Process
  │
  │ Initialize
  │ Send 'worker-ready'
  │
  ▼
Ready State ◄─────────────┐
  │                       │
  │ Receive 'execute-task'│
  │                       │
  ▼                       │
Busy State                │
  │                       │
  │ Execute task          │
  │ Send result           │
  │                       │
  ▼                       │
Cleanup                   │
  │                       │
  │ Clear cache           │
  │ Garbage collect       │
  │ Check memory          │
  │                       │
  └───────────────────────┘
   (95% WORKER REUSE)

On Error/Shutdown:
  │
  ▼
Exit → Pool Manager → Restart (if auto-restart enabled)
```

### Heartbeat Monitoring Flow

```
Worker Process                Pool Manager              Health Monitor
     │                             │                          │
     │ Start heartbeat timer       │                          │
     │ (every 5 seconds)            │                          │
     │                             │                          │
     ├─ Heartbeat ────────────────►│                          │
     │  {workerId, state,           │                          │
     │   memory, cpu, tasks}        │                          │
     │                             │                          │
     │                             ├─ Record heartbeat ──────►│
     │                             │                          │
     │                             │                ┌─────────┴─────────┐
     │                             │                │ Check timestamp   │
     │                             │                │ < 15s? ✓ Healthy  │
     │                             │                │ 15-30s? ⚠ Warning │
     │                             │                │ >30s? ✗ Zombie    │
     │                             │                └─────────┬─────────┘
     │                             │                          │
     │                             │◄─ Alert/Restart ─────────┤
     │                             │   (if zombie)            │
     │                             │                          │
```

### Load Balancing Flow

```
Task Queue (has tasks)
     │
     │ pool._assignTasks()
     │
     ▼
┌────────────────────────┐
│ Get available workers  │
│ (state === 'ready')    │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│ Load Balancing Strategy│
└────────┬───────────────┘
         │
         ├─── Round-Robin ────► Select next worker (rotating index)
         │
         ├─── Least-Loaded ──► Select worker with fewest tasks
         │
         └─── Capability ────► Select worker by capabilities (future)
         │
         ▼
┌────────────────────────┐
│ Assign task to worker  │
│ • Mark worker as busy  │
│ • Send task via IPC    │
└────────────────────────┘
```

### Error Handling & Retry Flow

```
Task Execution
     │
     ▼
┌─────────┐
│ Success?│
└────┬────┘
     │
     ├─── Yes ────────────► Complete task
     │                     Resolve Promise
     │                     Return to client
     │
     └─── No ─────────────► Task failed
                             │
                             ▼
                      ┌──────────────┐
                      │ Retries < 3? │
                      └──────┬───────┘
                             │
                             ├─── Yes ───► Retry with backoff
                             │             • 1s, 2s, 4s, 8s...
                             │             • Re-enqueue task
                             │             • Try again
                             │
                             └─── No ────► Dead Letter Queue
                                           Reject Promise
                                           Return error to client
```

### Scaling Flow

```
Pool Manager
     │
     │ Monitor queue depth
     │
     ▼
┌────────────────────────┐
│ Queue depth > 50 AND   │
│ Workers < maxWorkers?  │
└────────┬───────────────┘
         │
         ├─── Yes ────► scaleUp(10)
         │               │
         │               ├─ Spawn 10 new workers
         │               ├─ Register with health monitor
         │               └─ Add to worker pool
         │
         └─── No ─────► Check scale down
                         │
                         ▼
                ┌────────────────────────┐
                │ Queue depth === 0 AND  │
                │ Busy workers < 5 AND   │
                │ Total workers > min?   │
                └────────┬───────────────┘
                         │
                         ├─── Yes ────► scaleDown(5)
                         │               │
                         │               ├─ Select idle workers
                         │               ├─ Send shutdown signal
                         │               └─ Remove from pool
                         │
                         └─── No ─────► No scaling needed
```

## State Transitions

### Worker States

```
Initializing
     │
     │ worker-ready message
     │
     ▼
   Ready ◄──────────────────────┐
     │                          │
     │ execute-task message     │
     │                          │
     ▼                          │
   Busy                         │
     │                          │
     │ task-complete message    │
     │ task-failed message      │
     │                          │
     └──────────────────────────┘

Error paths:
  Ready/Busy → Error → Restart (if auto-restart)
  Ready/Busy → Shutting Down → Exited
```

### Task States

```
Created
  │
  │ enqueue()
  │
  ▼
Queued
  │
  │ dequeue()
  │
  ▼
Dequeued (assigned to worker)
  │
  ├─── Success ───────► Completed
  │
  ├─── Failure ───────┐
  │                   │
  │                   ▼
  │              ┌─────────┐
  │              │Retries? │
  │              └────┬────┘
  │                   │
  │                   ├─── Yes ──► Retry-Pending
  │                   │             │
  │                   │             └─► Queued (again)
  │                   │
  │                   └─── No ───► Failed (DLQ)
  │
  └─── Timeout ───────────────────► Failed (DLQ)
```

### Pool States

```
Uninitialized
     │
     │ initialize()
     │
     ▼
Initializing
     │
     │ all workers ready
     │
     ▼
   Ready ◄──────┐
     │          │
     │          │ normal operation
     │          │
     │          └──────────┘
     │
     │ shutdown(graceful=true)
     │
     ▼
Shutting Down (waiting for tasks)
     │
     │ all tasks complete
     │
     ▼
Shut Down
```

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Task Enqueue | O(log n) | Min-heap insertion |
| Task Dequeue | O(log n) | Min-heap extraction |
| Worker Selection | O(w) | w = number of workers |
| Health Check | O(w) | Check all workers |
| Get Metrics | O(1) | Cached statistics |
| Scale Up | O(n) | n = workers to spawn |
| Scale Down | O(n) | n = workers to remove |

### Space Complexity

| Component | Space | Notes |
|-----------|-------|-------|
| Task Queue | O(t) | t = queued tasks |
| Worker Pool | O(w) | w = number of workers |
| Health Data | O(w × h) | h = history depth (100) |
| Metrics | O(1) | Aggregated stats |

### Expected Performance

| Metric | Value | Condition |
|--------|-------|-----------|
| Task Startup | 5ms | Worker already spawned |
| Worker Spawn | 100-500ms | Cold start only |
| Heartbeat Overhead | <1ms | Per worker per 5s |
| Queue Operation | <1ms | Per enqueue/dequeue |
| Health Check | <5ms | All workers per 5s |
| Graceful Shutdown | 5-30s | Depends on in-flight tasks |

## Memory Layout

```
Process Memory
│
├─ Pool Manager (~50MB)
│  ├─ Task Queue (~1MB per 1000 tasks)
│  ├─ Health Monitor (~5MB for 100 workers)
│  ├─ Worker Metadata (~100KB per worker)
│  └─ Event Emitters (~1MB)
│
└─ Worker Processes (~512MB each × N workers)
   ├─ Node.js Runtime (~50MB)
   ├─ Task Execution Context (~200MB)
   ├─ Module Cache (~100MB)
   └─ Heap (~162MB available for tasks)

Total Pool: 50MB + (512MB × N workers)
Example: 20 workers = 50MB + 10GB = ~10GB total
```

## Failure Scenarios

### Worker Crash
```
Worker crashes during task
  ↓
Pool Manager detects exit event
  ↓
Current task marked as failed
  ↓
Task moved to retry queue
  ↓
New worker spawned (if auto-restart)
  ↓
Task retried on new worker
```

### Zombie Worker
```
Worker stops sending heartbeats
  ↓
Health Monitor detects (>30s no heartbeat)
  ↓
Alert: Zombie detected
  ↓
Pool Manager initiates restart
  ↓
SIGTERM sent to zombie
  ↓
Wait 5s for graceful shutdown
  ↓
SIGKILL if still alive
  ↓
New worker spawned
  ↓
Pool capacity restored
```

### Pool Overload
```
Tasks arriving faster than processing
  ↓
Queue depth increases
  ↓
Threshold exceeded (e.g., >50 tasks)
  ↓
Auto-scale triggered (if enabled)
  ↓
New workers spawned
  ↓
Tasks distributed across larger pool
  ↓
Queue drains faster
```

## Summary

The Worker Pool architecture provides:

1. **Persistent Workers**: Long-running processes (95%+ reuse)
2. **Efficient Queuing**: O(log n) priority queue
3. **Health Monitoring**: Automatic zombie detection
4. **Load Balancing**: Multiple strategies
5. **Dynamic Scaling**: Auto-scale based on load
6. **Error Recovery**: Automatic retry and restart
7. **Comprehensive Metrics**: Real-time monitoring
8. **Graceful Shutdown**: Clean task completion

This architecture eliminates per-task spawning overhead while maintaining system health and reliability.
