# Redis Coordination Protocol for 3-Larry Distributed Orchestration

## Overview

This document defines the Redis-based coordination protocol used by 3 Larry instances to execute distributed AI orchestration without conflicts. The protocol ensures lock-based task assignment, real-time progress tracking, inter-Larry messaging, and clean convergence.

**Redis Deployment:** `redis-cluster.redis-ha.svc.cluster.local:6379`
**Architecture:** Pub/Sub + Distributed Locking + Shared State
**Larrys:** larry-01, larry-02, larry-03

---

## Key Namespaces

### Phase Status Keys

Track the execution state of each Larry's phase:

```redis
# Phase status (enum: pending | in_progress | completed | failed)
SET phase:larry-01:status "in_progress"
SET phase:larry-02:status "in_progress"
SET phase:larry-03:status "in_progress"

# Progress percentage (0-100)
SET phase:larry-01:progress 45
SET phase:larry-02:progress 60
SET phase:larry-03:progress 30

# Timestamps
SET phase:larry-01:started_at "2025-12-22T10:00:00Z"
SET phase:larry-01:completed_at "2025-12-22T10:25:00Z"

# Phase-specific metrics
HSET phase:larry-01:metrics tasks_completed 4 workers_active 0
HSET phase:larry-02:findings critical 3 high 4 medium 5 low 2
HSET phase:larry-03:inventory assets_discovered 150
```

### Task Locking Keys

Prevent duplicate work using distributed locks:

```redis
# Task ownership (TTL: 3600 seconds)
SET task:lock:fix-pgadmin-crashloop "larry-01" NX EX 3600
SET task:lock:security-scan-database "larry-02" NX EX 3600
SET task:lock:catalog-deployments "larry-03" NX EX 3600

# Task status
SET task:status:fix-pgadmin-crashloop "in_progress"
SET task:status:security-scan-database "completed"

# Task results (hash)
HSET task:result:fix-pgadmin-crashloop success true restarts 0 timestamp "2025-12-22T10:15:00Z"
```

### Worker Registration Keys

Track active workers across all Larrys:

```redis
# Worker ownership
SET worker:larry-01-cleanup-worker:master "larry-01"
SET worker:larry-01-cleanup-worker:node "k3s-worker01"
SET worker:larry-01-cleanup-worker:status "busy"

# Worker metrics
HSET worker:larry-01-cleanup-worker:metrics tokens_used 6500 duration_seconds 780
```

### Metrics Keys

System-wide metrics for monitoring:

```redis
# Per-Larry task completion
INCR metrics:larry-01:tasks_completed  # Returns: 4
INCR metrics:larry-02:cves_found       # Returns: 12
INCR metrics:larry-03:assets_cataloged # Returns: 150

# Token usage
INCRBY tokens:larry-01:used 8000
GET tokens:larry-01:limit              # Returns: 111000
```

---

## Pub/Sub Channels

### `larry:coordination` Channel

Main coordination channel for inter-Larry messaging:

```json
// Phase start event
{
  "from": "larry-01",
  "event": "phase_started",
  "timestamp": "2025-12-22T10:00:00Z"
}

// Progress update
{
  "from": "larry-02",
  "event": "progress_update",
  "progress": 50,
  "message": "2/4 security workers completed",
  "timestamp": "2025-12-22T10:15:00Z"
}

// Phase completion
{
  "from": "larry-03",
  "event": "phase_complete",
  "timestamp": "2025-12-22T10:30:00Z",
  "summary": {
    "assets_cataloged": 150,
    "prs_created": 5,
    "coverage_increase": "12%"
  }
}

// Task conflict
{
  "from": "larry-02",
  "event": "task_conflict",
  "task_id": "fix-pgadmin-crashloop",
  "owner": "larry-01",
  "timestamp": "2025-12-22T10:05:00Z"
}
```

### `larry:alerts` Channel

Critical alerts and escalations:

```json
// Critical CVE discovered
{
  "from": "larry-02",
  "event": "critical_cve",
  "severity": "critical",
  "data": {
    "cve_id": "CVE-2025-12345",
    "cvss": 9.8,
    "affected_service": "postgresql",
    "namespace": "database",
    "recommendation": "Immediate patching required"
  },
  "timestamp": "2025-12-22T10:12:00Z"
}

// Worker failure
{
  "from": "larry-03",
  "event": "worker_failure",
  "severity": "high",
  "data": {
    "worker_id": "larry-03-feature-worker",
    "task_id": "implement-priority-feature",
    "error": "Timeout exceeded",
    "retry_count": 2
  },
  "timestamp": "2025-12-22T10:20:00Z"
}

// Rollback initiated
{
  "from": "larry-01",
  "event": "rollback_initiated",
  "severity": "high",
  "reason": "Database consolidation failed validation",
  "timestamp": "2025-12-22T10:18:00Z"
}
```

---

## Core Operations

### 1. Task Lock Acquisition

**Algorithm:** Atomic SET with NX (Not eXists) flag and TTL

```python
import redis
from datetime import datetime

r = redis.Redis(
    host='redis-cluster.redis-ha.svc.cluster.local',
    port=6379,
    decode_responses=True
)

def acquire_task_lock(task_id, larry_id, ttl=3600):
    """
    Atomically acquire task lock using Redis SET NX.

    Returns:
        bool: True if lock acquired, False if already owned by another Larry
    """
    lock_key = f"task:lock:{task_id}"

    # Atomic SET with NX (only set if not exists) and EX (expiry)
    acquired = r.set(lock_key, larry_id, nx=True, ex=ttl)

    if acquired:
        # Successfully acquired lock
        r.set(f"task:status:{task_id}", "in_progress")
        print(f"[{larry_id}] Acquired lock for task: {task_id}")
        return True
    else:
        # Another Larry already owns this task
        owner = r.get(lock_key)
        print(f"[{larry_id}] Task {task_id} already claimed by {owner}")

        # Publish conflict event
        event = {
            "from": larry_id,
            "event": "task_conflict",
            "task_id": task_id,
            "owner": owner,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        r.publish("larry:coordination", json.dumps(event))
        return False

def release_task_lock(task_id, larry_id):
    """
    Release task lock only if we own it (check-and-delete).

    Returns:
        bool: True if lock released, False if not owned
    """
    lock_key = f"task:lock:{task_id}"

    # Verify we own the lock before deleting
    current_owner = r.get(lock_key)
    if current_owner == larry_id:
        r.delete(lock_key)
        r.set(f"task:status:{task_id}", "completed")
        print(f"[{larry_id}] Released lock for task: {task_id}")
        return True
    else:
        print(f"[{larry_id}] Cannot release task {task_id} - owned by {current_owner}")
        return False

# Usage example
if acquire_task_lock("fix-pgadmin-crashloop", "larry-01"):
    # Perform work
    print("Fixing PgAdmin CrashLoopBackOff...")
    time.sleep(10)

    # Release lock
    release_task_lock("fix-pgadmin-crashloop", "larry-01")
```

### 2. Progress Broadcasting

**Pattern:** Periodic SET + PUBLISH for real-time updates

```python
import json
from datetime import datetime

def broadcast_progress(larry_id, progress, message):
    """
    Broadcast progress update to all Larrys via Redis.

    Args:
        larry_id (str): Larry instance ID (larry-01, larry-02, larry-03)
        progress (int): Progress percentage (0-100)
        message (str): Human-readable status message
    """
    # Update progress in Redis
    r.set(f"phase:{larry_id}:progress", progress)

    # Publish event
    event = {
        "from": larry_id,
        "event": "progress_update",
        "progress": progress,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    r.publish("larry:coordination", json.dumps(event))
    print(f"[{larry_id}] Progress: {progress}% - {message}")

# Usage example
broadcast_progress("larry-01", 25, "Database cleanup completed")
broadcast_progress("larry-01", 50, "PostgreSQL consolidation in progress")
broadcast_progress("larry-01", 75, "Performance optimization complete")
broadcast_progress("larry-01", 100, "All infrastructure tasks complete")
```

### 3. Progress Subscription

**Pattern:** SUBSCRIBE to pub/sub channel, react to events

```python
import json

def monitor_all_larrys():
    """
    Subscribe to Larry coordination channel and monitor progress.
    """
    pubsub = r.pubsub()
    pubsub.subscribe("larry:coordination")

    print("Monitoring all Larrys...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                event = json.loads(message['data'])

                if event['event'] == 'progress_update':
                    print(f"[{event['from']}] {event['progress']}% - {event['message']}")

                elif event['event'] == 'phase_complete':
                    print(f"[{event['from']}] COMPLETED at {event['timestamp']}")

                    # Check if all Larrys are done
                    if all_larrys_complete():
                        print("All Larrys completed - initiating convergence phase")
                        initiate_phase_4()
                        break

                elif event['event'] == 'task_conflict':
                    print(f"[WARNING] {event['from']} attempted to claim task owned by {event['owner']}")

            except json.JSONDecodeError:
                print(f"Invalid JSON: {message['data']}")

def all_larrys_complete():
    """
    Check if all 3 Larrys have completed their phases.
    """
    larry_ids = ["larry-01", "larry-02", "larry-03"]
    statuses = {
        larry_id: r.get(f"phase:{larry_id}:status")
        for larry_id in larry_ids
    }

    return all(status == "completed" for status in statuses.values())

# Usage
monitor_all_larrys()
```

### 4. Barrier Synchronization

**Pattern:** Polling + blocking wait for all Larrys to complete

```python
import time

def wait_for_all_larrys(larry_ids, timeout=600):
    """
    Block until all Larrys reach 'completed' status or timeout.

    Args:
        larry_ids (list): List of Larry IDs to wait for
        timeout (int): Max wait time in seconds

    Returns:
        bool: True if all completed, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        statuses = {
            larry_id: r.get(f"phase:{larry_id}:status")
            for larry_id in larry_ids
        }

        # Check if all are completed
        if all(status == "completed" for status in statuses.values()):
            print("Barrier sync complete - all Larrys finished!")
            return True

        # Print current status
        for larry_id, status in statuses.items():
            progress = r.get(f"phase:{larry_id}:progress") or 0
            print(f"  [{larry_id}] {status} ({progress}%)")

        time.sleep(5)  # Poll every 5 seconds

    # Timeout
    print(f"ERROR: Timeout after {timeout}s waiting for Larrys")
    return False

# Usage
larry_ids = ["larry-01", "larry-02", "larry-03"]
if wait_for_all_larrys(larry_ids):
    print("Starting Phase 4: Convergence & Validation")
else:
    print("Aborting - not all Larrys completed in time")
```

### 5. Emergency Alert Broadcasting

**Pattern:** PUBLISH to `larry:alerts` for critical events

```python
def broadcast_critical_alert(larry_id, severity, event_type, data):
    """
    Broadcast critical alert to all Larrys.

    Args:
        larry_id (str): Source Larry
        severity (str): critical | high | medium | low
        event_type (str): critical_cve | worker_failure | rollback_initiated
        data (dict): Event-specific data
    """
    alert = {
        "from": larry_id,
        "event": event_type,
        "severity": severity,
        "data": data,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    r.publish("larry:alerts", json.dumps(alert))
    print(f"[{larry_id}] ALERT: {severity.upper()} - {event_type}")

# Example: Critical CVE discovered
broadcast_critical_alert(
    larry_id="larry-02",
    severity="critical",
    event_type="critical_cve",
    data={
        "cve_id": "CVE-2025-12345",
        "cvss": 9.8,
        "affected_service": "postgresql",
        "namespace": "database",
        "recommendation": "Immediate patching required"
    }
)

# Example: Worker failure
broadcast_critical_alert(
    larry_id="larry-03",
    severity="high",
    event_type="worker_failure",
    data={
        "worker_id": "larry-03-feature-worker",
        "task_id": "implement-priority-feature",
        "error": "Timeout exceeded",
        "retry_count": 2
    }
)
```

---

## Execution Workflow

### Phase 1: Initialization (T+0:00)

```python
def initialize_larry(larry_id, phase):
    """
    Initialize Larry instance in Redis.
    """
    # Set phase status
    r.set(f"phase:{larry_id}:status", "in_progress")
    r.set(f"phase:{larry_id}:progress", 0)
    r.set(f"phase:{larry_id}:started_at", datetime.utcnow().isoformat() + "Z")

    # Initialize metrics
    if larry_id == "larry-01":
        r.hset(f"phase:{larry_id}:metrics", mapping={
            "tasks_completed": 0,
            "workers_active": 4
        })
    elif larry_id == "larry-02":
        r.hset(f"phase:{larry_id}:findings", mapping={
            "critical": 0, "high": 0, "medium": 0, "low": 0
        })
    elif larry_id == "larry-03":
        r.set(f"phase:{larry_id}:inventory:assets_discovered", 0)
        r.set(f"phase:{larry_id}:development:prs_created", 0)
        r.set(f"phase:{larry_id}:testing:coverage_increase", 0)

    # Broadcast start event
    event = {
        "from": larry_id,
        "event": "phase_started",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    r.publish("larry:coordination", json.dumps(event))

# Initialize all 3 Larrys
initialize_larry("larry-01", "infrastructure")
initialize_larry("larry-02", "security")
initialize_larry("larry-03", "development")
```

### Phase 2: Worker Execution (T+0:01 → T+0:30)

```python
def monitor_workers(larry_id, total_workers):
    """
    Monitor worker progress and update Redis.
    """
    while True:
        # Count completed workers (via Kubernetes API)
        completed = get_completed_worker_count(larry_id)
        progress = (completed * 100) // total_workers

        # Update Redis
        r.set(f"phase:{larry_id}:progress", progress)
        broadcast_progress(larry_id, progress, f"{completed}/{total_workers} workers completed")

        # Check if all workers done
        if completed == total_workers:
            print(f"[{larry_id}] All workers completed!")
            break

        time.sleep(10)

# Larry-01: 4 workers
monitor_workers("larry-01", 4)

# Larry-02: 4 workers
monitor_workers("larry-02", 4)

# Larry-03: 8 workers
monitor_workers("larry-03", 8)
```

### Phase 3: Completion (T+0:25 → T+0:30)

```python
def mark_phase_complete(larry_id):
    """
    Mark Larry phase as completed in Redis.
    """
    # Update status
    r.set(f"phase:{larry_id}:status", "completed")
    r.set(f"phase:{larry_id}:completed_at", datetime.utcnow().isoformat() + "Z")

    # Broadcast completion event
    event = {
        "from": larry_id,
        "event": "phase_complete",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    r.publish("larry:coordination", json.dumps(event))

# Each Larry marks completion
mark_phase_complete("larry-01")  # T+0:25
mark_phase_complete("larry-02")  # T+0:30
mark_phase_complete("larry-03")  # T+0:30
```

### Phase 4: Convergence (T+0:30 → T+0:40)

```python
def initiate_phase_4():
    """
    Phase 4: Convergence & Final Reporting.
    All 3 Larrys have completed - aggregate results.
    """
    print("PHASE 4: Convergence & Final Reporting")

    # Load all Larry reports
    reports = {}
    for larry_id in ["larry-01", "larry-02", "larry-03"]:
        report_file = f"/coordination/reports/{larry_id}-final.json"
        with open(report_file, 'r') as f:
            reports[larry_id] = json.load(f)

    # Cross-validate
    validate_infrastructure(reports["larry-01"])
    validate_security(reports["larry-02"])
    validate_development(reports["larry-03"])

    # Aggregate final report
    final_report = aggregate_reports(reports)

    # Save final report
    with open("/coordination/reports/3-LARRY-EXECUTION-SUMMARY.md", 'w') as f:
        f.write(generate_executive_summary(final_report))

    print("3-Larry orchestration complete!")

# Wait for all Larrys, then converge
if wait_for_all_larrys(["larry-01", "larry-02", "larry-03"]):
    initiate_phase_4()
```

---

## Error Handling

### Task Lock Expiry

If a worker crashes, the task lock will expire after TTL (3600s), allowing another worker to claim it:

```python
def retry_failed_tasks(larry_id):
    """
    Check for expired task locks and retry.
    """
    # Scan for tasks in 'in_progress' status
    for key in r.scan_iter("task:status:*"):
        task_id = key.split(":")[-1]

        # Check if lock exists
        lock_key = f"task:lock:{task_id}"
        if not r.exists(lock_key):
            # Lock expired - task failed
            print(f"[{larry_id}] Task {task_id} lock expired - retrying")

            # Attempt to acquire lock
            if acquire_task_lock(task_id, larry_id):
                # Retry task
                retry_task(task_id)
```

### Worker Failure

Kubernetes `restartPolicy: OnFailure` will automatically retry failed workers. If max retries exceeded:

```python
def handle_worker_failure(larry_id, worker_id, task_id, error):
    """
    Handle worker failure by releasing lock and alerting.
    """
    # Release task lock
    release_task_lock(task_id, larry_id)

    # Broadcast alert
    broadcast_critical_alert(
        larry_id=larry_id,
        severity="high",
        event_type="worker_failure",
        data={
            "worker_id": worker_id,
            "task_id": task_id,
            "error": str(error),
            "retry_count": 3
        }
    )
```

### Redis Connection Failure

Fallback to local file-based coordination:

```python
def check_redis_health():
    """
    Health check Redis connection.
    """
    try:
        r.ping()
        return True
    except redis.ConnectionError:
        print("ERROR: Redis connection failed - falling back to local state")
        return False

def get_phase_status(larry_id):
    """
    Get phase status with Redis fallback.
    """
    if check_redis_health():
        # Use Redis
        return r.get(f"phase:{larry_id}:status")
    else:
        # Fallback to local file
        with open(f"/coordination/state/{larry_id}-status.txt", 'r') as f:
            return f.read().strip()
```

---

## Cleanup

After execution, clean up Redis keys:

```bash
#!/bin/bash

# Delete phase keys
redis-cli --scan --pattern "phase:larry-*" | xargs redis-cli del

# Delete task locks
redis-cli --scan --pattern "task:lock:*" | xargs redis-cli del
redis-cli --scan --pattern "task:status:*" | xargs redis-cli del

# Delete worker keys
redis-cli --scan --pattern "worker:*" | xargs redis-cli del

# Delete metrics
redis-cli --scan --pattern "metrics:larry-*" | xargs redis-cli del
redis-cli --scan --pattern "tokens:larry-*" | xargs redis-cli del

echo "Redis cleanup complete"
```

---

## Monitoring Queries

Useful Redis commands for monitoring:

```bash
# Check all Larry statuses
redis-cli MGET phase:larry-01:status phase:larry-02:status phase:larry-03:status

# Get progress
redis-cli MGET phase:larry-01:progress phase:larry-02:progress phase:larry-03:progress

# Count active task locks
redis-cli KEYS "task:lock:*" | wc -l

# Get security findings
redis-cli HGETALL phase:larry-02:findings

# Get inventory metrics
redis-cli GET phase:larry-03:inventory:assets_discovered

# Monitor coordination channel (real-time)
redis-cli SUBSCRIBE larry:coordination

# Monitor alerts channel (real-time)
redis-cli SUBSCRIBE larry:alerts
```

---

## Summary

This Redis coordination protocol enables:

1. **Lock-Based Task Assignment** - Prevents duplicate work via atomic SET NX
2. **Real-Time Progress Tracking** - Pub/Sub for instant updates
3. **Inter-Larry Messaging** - Coordination and conflict resolution
4. **Barrier Synchronization** - Wait for all Larrys to complete
5. **Emergency Alerts** - Critical event broadcasting
6. **Fault Tolerance** - TTL-based lock expiry, Redis health checks
7. **Clean Convergence** - Phase 4 aggregation and validation

**Key Redis Features Used:**
- SET NX (atomic lock acquisition)
- EX (TTL for automatic cleanup)
- PUBLISH/SUBSCRIBE (real-time messaging)
- HSET/HGETALL (structured metrics)
- SCAN (efficient key iteration)

This protocol is the backbone of distributed AI orchestration in the Cortex system.
