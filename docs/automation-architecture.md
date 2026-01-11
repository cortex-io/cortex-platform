# Cortex Automation Architecture

**Status**: 🚧 In Progress
**Version**: 1.0
**Last Updated**: 2025-11-02
**Owner**: Development Team

---

## Overview

This document outlines the three-phase approach to building autonomous agent automation for the cortex master-worker system. The goal is to move from manual orchestration (using Task tool directly) to fully autonomous agent coordination.

**Current State**: Manual "role-playing" where we invoke agents via Task tool
**Target State**: Self-coordinating system where agents autonomously process task queues

---

## Design Principles

1. **Incremental Automation**: Build in phases, validate each level before advancing
2. **Fail-Safe Design**: Always maintain manual override capability
3. **Observable Behavior**: All agent actions logged and traceable
4. **Stateless Execution**: Agents read/write coordination files, don't maintain state
5. **Token Efficiency**: Optimize for minimal token usage while maintaining quality

---

## Three-Phase Roadmap

### Phase 1: Script-Triggered Automation (Foundation)
**Timeline**: Current sprint
**Automation Level**: Semi-automatic (manual trigger, autonomous execution)
**Status**: 🟡 In Progress

### Phase 2: Daemon-Based Automation (Continuous Processing)
**Timeline**: Next sprint
**Automation Level**: Fully automatic (autonomous task processing)
**Status**: ⚪ Planned

### Phase 3: Event-Driven Automation (Real-Time Response)
**Timeline**: Future (after Phase 2 stabilizes)
**Automation Level**: Real-time reactive (instant task response)
**Status**: ⚪ Planned

---

## Option A: Script-Triggered Automation

### Description

Shell scripts that orchestrate individual master agents. **You manually invoke** the script when ready, then the agent runs autonomously until completion.

```bash
# User manually triggers when needed
./scripts/run-security-master.sh

# Security Master autonomously:
# 1. Reads task-queue.json for security tasks
# 2. Makes strategic decisions about approach
# 3. Spawns workers as needed via spawn-worker.sh
# 4. Monitors worker progress
# 5. Aggregates results
# 6. Updates coordination files
# 7. Creates handoffs if needed
# 8. Exits when complete
```

### Architecture

```
User
  ↓ (manual trigger)
scripts/run-security-master.sh
  ↓
Security Master Agent (Task tool invocation)
  ↓ (reads)
coordination/task-queue.json
  ↓ (spawns)
scripts/spawn-worker.sh --type scan-worker --task task-010 --repo n8n-mcp-server
  ↓
Worker Agent (Task tool invocation)
  ↓ (writes results)
agents/logs/workers/2025-11-02/worker-scan-101/results.json
  ↓ (aggregates)
Security Master reads results, updates coordination files
  ↓ (updates)
coordination/task-queue.json (status: completed)
coordination/handoffs.json (if needed)
```

### Components to Build

#### 1. Core Scripts

```bash
scripts/
├── spawn-worker.sh              # Spawn individual workers
├── run-coordinator.sh           # Run coordinator master
├── run-security-master.sh       # Run security master
├── run-development-master.sh    # Run development master
├── run-inventory-master.sh      # Run inventory master
└── worker-status.sh             # Check worker progress
```

#### 2. Library Functions

```bash
scripts/lib/
├── coordination.sh              # Read/write coordination files
├── logging.sh                   # Structured logging
├── validation.sh                # Input validation
└── token-tracking.sh            # Token budget management
```

#### 3. Worker Templates

```bash
scripts/worker-templates/
├── scan-worker.md               # Security scanning worker
├── fix-worker.md                # Security fix worker
├── implementation-worker.md     # Feature implementation worker
├── test-worker.md               # Testing worker
└── pr-worker.md                 # Pull request worker
```

#### 4. Master Prompts

```bash
agents/prompts/
├── coordinator-master.md        # ✅ Already exists
├── security-master.md           # ✅ Already exists
├── development-master.md        # ✅ Already exists
└── inventory-master.md          # ✅ Already exists
```

### Script Interfaces

#### spawn-worker.sh

```bash
Usage: spawn-worker.sh [OPTIONS]

Required:
  --type TYPE           Worker type (scan-worker, fix-worker, etc.)
  --task TASK_ID        Task ID from task-queue.json
  --master MASTER_ID    Master agent spawning this worker
  --repo REPO           Repository (e.g., ry-ops/n8n-mcp-server)

Optional:
  --priority PRIORITY   Priority level (critical, high, medium, low)
  --scope JSON          Additional scope/context as JSON
  --timeout MINUTES     Worker timeout (default: from worker type)

Environment:
  COMMIT_RELAY_HOME     Path to cortex repository

Output:
  Worker ID (e.g., worker-scan-101)

Returns:
  0 on success, non-zero on error

Example:
  ./scripts/spawn-worker.sh \
    --type scan-worker \
    --task task-010 \
    --master security-master \
    --repo ry-ops/n8n-mcp-server \
    --priority critical
```

#### run-security-master.sh

```bash
Usage: run-security-master.sh [OPTIONS]

Optional:
  --task TASK_ID        Process specific task (default: auto-detect)
  --dry-run             Show what would be done without executing
  --force               Skip confirmation prompts

Environment:
  COMMIT_RELAY_HOME     Path to cortex repository

Output:
  Logs to agents/logs/security/YYYY-MM-DD.md
  Updates coordination files

Returns:
  0 on success, non-zero on error

Example:
  # Auto-detect and process security tasks
  ./scripts/run-security-master.sh

  # Process specific task
  ./scripts/run-security-master.sh --task task-010

  # Dry run to see what would happen
  ./scripts/run-security-master.sh --dry-run
```

### Execution Flow (Detailed)

**1. User Triggers Master**
```bash
$ cd ~/cortex
$ ./scripts/run-security-master.sh
```

**2. Script Initialization**
```bash
# Load libraries
source scripts/lib/coordination.sh
source scripts/lib/logging.sh

# Validate environment
check_commit_relay_home
check_git_status
acquire_lock "security-master"  # Prevent concurrent runs
```

**3. Master Agent Invocation**
```bash
# Build master prompt from template
PROMPT=$(cat agents/prompts/security-master.md)
PROMPT+=$'\n\n'"## Current Task Queue"
PROMPT+=$'\n'"$(cat coordination/task-queue.json | jq '.tasks[] | select(.type == "security" and .status == "pending")')"

# Invoke master using Task tool
claude-code task run \
  --agent-type general-purpose \
  --model sonnet \
  --prompt "$PROMPT" \
  --output agents/logs/security/$(date +%Y-%m-%d)/session-$SESSION_ID.log
```

**4. Master Spawns Workers**

Security Master decides to spawn 3 workers, calls spawn-worker.sh for each:

```bash
# From within master agent execution
./scripts/spawn-worker.sh \
  --type scan-worker \
  --task task-010 \
  --master security-master \
  --repo ry-ops/n8n-mcp-server
```

**5. Worker Execution**

spawn-worker.sh:
```bash
# Generate worker ID
WORKER_ID="worker-scan-$(date +%s)"

# Create worker workspace
mkdir -p agents/logs/workers/$(date +%Y-%m-%d)/$WORKER_ID

# Build worker prompt from template + task context
WORKER_PROMPT=$(cat scripts/worker-templates/scan-worker.md)
WORKER_PROMPT+=$'\n\n'"## Task Context"
WORKER_PROMPT+=$'\n'"$(get_task_context task-010)"

# Invoke worker
claude-code task run \
  --agent-type general-purpose \
  --model haiku \  # Workers use cheaper model
  --prompt "$WORKER_PROMPT" \
  --output agents/logs/workers/$(date +%Y-%m-%d)/$WORKER_ID/execution.log

# Update worker-pool.json
update_worker_pool "$WORKER_ID" "completed" "scan-worker" "security-master"
```

**6. Master Aggregates Results**

Security Master reads worker results:
```bash
# In master agent execution
for worker_id in $WORKER_IDS; do
  RESULT=$(cat agents/logs/workers/$(date +%Y-%m-%d)/$worker_id/results.json)
  # Aggregate findings
done

# Update task status
update_task_status task-010 "completed"

# Create handoff if needed
create_handoff "security-master" "coordinator-master" "Task completed"
```

**7. Cleanup and Exit**
```bash
# Release lock
release_lock "security-master"

# Final status
echo "✅ Security Master completed: 3 workers spawned, task-010 completed"
exit 0
```

### Advantages

- ✅ **Controlled**: You decide when to run agents
- ✅ **Simple**: Straightforward shell scripts
- ✅ **Debuggable**: Easy to trace execution
- ✅ **Safe**: Manual trigger prevents runaway execution
- ✅ **Quick to Build**: Leverages existing Task tool
- ✅ **Testable**: Can dry-run and verify behavior

### Disadvantages

- ❌ **Manual Trigger Required**: Not fully autonomous
- ❌ **No Background Processing**: Must wait for completion
- ❌ **No Task Queue Monitoring**: Doesn't watch for new tasks
- ❌ **Limited Coordination**: Handoffs require manual follow-up

### Use Cases

- Daily security scans (run on demand)
- Feature development (when ready to start)
- Critical security fixes (immediate response)
- Repository cataloging (scheduled via cron)

### Success Criteria

- [ ] User can trigger `./scripts/run-security-master.sh`
- [ ] Security Master autonomously processes task-010
- [ ] Workers spawn and execute without intervention
- [ ] Results aggregated and coordination files updated
- [ ] All actions logged to activity logs
- [ ] Process completes successfully end-to-end

---

## Option B: Daemon-Based Automation

### Description

Background daemon process that **continuously monitors** the task queue and automatically dispatches work to appropriate master agents. Fully autonomous for queued tasks.

```bash
# Start the daemon once
./scripts/coordinator-daemon.sh start

# Daemon runs continuously in background:
# 1. Polls task-queue.json every 30 seconds
# 2. Detects new tasks or status changes
# 3. Automatically routes tasks to appropriate master
# 4. Masters spawn workers autonomously
# 5. Monitors completion and creates handoffs
# 6. Continues processing until stopped

# Check daemon status
./scripts/coordinator-daemon.sh status

# Stop daemon
./scripts/coordinator-daemon.sh stop
```

### Architecture

```
coordinator-daemon.sh (background process)
  ↓ (polls every 30s)
coordination/task-queue.json
  ↓ (detects new task)
task-011: type=security, status=pending
  ↓ (dispatches)
./scripts/run-security-master.sh --task task-011 &
  ↓ (spawns workers)
Security Master → spawn-worker.sh × 3
  ↓ (workers complete)
Security Master updates task-011: status=completed
  ↓ (daemon detects)
coordinator-daemon.sh sees completion
  ↓ (checks handoffs)
coordination/handoffs.json
  ↓ (processes handoff)
./scripts/run-coordinator.sh --handoff handoff-XYZ &
  ↓ (loop continues)
Wait 30s, poll again...
```

### Components to Build

#### 1. Daemon Scripts

```bash
scripts/
├── coordinator-daemon.sh        # Main daemon process
├── handoff-processor.sh         # Process handoffs automatically
└── health-monitor.sh            # Monitor system health
```

#### 2. Process Management

```bash
scripts/lib/
├── daemon.sh                    # Daemon utilities (start/stop/status)
├── pid-management.sh            # PID file handling
└── signal-handlers.sh           # Graceful shutdown
```

#### 3. Configuration

```bash
config/
├── daemon.conf                  # Daemon configuration
└── priorities.conf              # Task priority rules
```

### Daemon Configuration

**daemon.conf**
```bash
# Polling interval (seconds)
POLL_INTERVAL=30

# Maximum concurrent master agents
MAX_CONCURRENT_MASTERS=2

# Task priority thresholds for auto-dispatch
AUTO_DISPATCH_CRITICAL=true
AUTO_DISPATCH_HIGH=true
AUTO_DISPATCH_MEDIUM=false
AUTO_DISPATCH_LOW=false

# Working hours (empty = 24/7)
WORKING_HOURS_START=""
WORKING_HOURS_END=""

# Token budget safety threshold
TOKEN_BUDGET_EMERGENCY_THRESHOLD=0.9

# Logging
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=30
```

### Execution Flow (Detailed)

**1. Daemon Startup**
```bash
$ ./scripts/coordinator-daemon.sh start

Starting coordinator-daemon...
✅ PID 12345 written to /var/run/cortex-daemon.pid
✅ Logs: agents/logs/daemon/2025-11-02.log
✅ Polling task queue every 30 seconds
✅ Auto-dispatch: critical=yes, high=yes, medium=no, low=no
```

**2. Daemon Main Loop**
```bash
while true; do
  # Check for stop signal
  if [ -f "$STOP_SIGNAL_FILE" ]; then
    graceful_shutdown
    exit 0
  fi

  # Load current state
  TASKS=$(get_pending_tasks)
  HANDOFFS=$(get_pending_handoffs)
  ACTIVE_MASTERS=$(get_active_masters)

  # Process pending tasks
  for task in $TASKS; do
    TASK_ID=$(echo $task | jq -r '.id')
    TASK_TYPE=$(echo $task | jq -r '.type')
    TASK_PRIORITY=$(echo $task | jq -r '.priority')

    # Check if should auto-dispatch
    if should_auto_dispatch "$TASK_PRIORITY"; then
      # Check concurrency limits
      if [ "$ACTIVE_MASTERS" -lt "$MAX_CONCURRENT_MASTERS" ]; then
        dispatch_task "$TASK_ID" "$TASK_TYPE" &
        log "INFO" "Dispatched $TASK_ID to $TASK_TYPE-master"
      else
        log "WARN" "Concurrency limit reached, queuing $TASK_ID"
      fi
    fi
  done

  # Process pending handoffs
  for handoff in $HANDOFFS; do
    process_handoff "$handoff" &
    log "INFO" "Processing handoff $handoff"
  done

  # Update health metrics
  update_health_metrics

  # Sleep until next poll
  sleep $POLL_INTERVAL
done
```

**3. Task Dispatch**
```bash
dispatch_task() {
  local TASK_ID=$1
  local TASK_TYPE=$2

  case $TASK_TYPE in
    security)
      ./scripts/run-security-master.sh --task $TASK_ID
      ;;
    development)
      ./scripts/run-development-master.sh --task $TASK_ID
      ;;
    inventory)
      ./scripts/run-inventory-master.sh --task $TASK_ID
      ;;
    *)
      ./scripts/run-coordinator.sh --task $TASK_ID
      ;;
  esac
}
```

**4. Handoff Processing**
```bash
process_handoff() {
  local HANDOFF_ID=$1

  # Read handoff details
  HANDOFF=$(get_handoff_details $HANDOFF_ID)
  TO_AGENT=$(echo $HANDOFF | jq -r '.to_agent')
  TASK_ID=$(echo $HANDOFF | jq -r '.task_id')

  # Dispatch to target agent
  case $TO_AGENT in
    coordinator-master)
      ./scripts/run-coordinator.sh --handoff $HANDOFF_ID
      ;;
    security-master)
      ./scripts/run-security-master.sh --handoff $HANDOFF_ID
      ;;
    development-master)
      ./scripts/run-development-master.sh --handoff $HANDOFF_ID
      ;;
  esac

  # Mark handoff as processed
  update_handoff_status $HANDOFF_ID "processed"
}
```

**5. Health Monitoring**
```bash
update_health_metrics() {
  # Check token budget
  TOKEN_USAGE=$(get_token_usage_percentage)
  if (( $(echo "$TOKEN_USAGE > $TOKEN_BUDGET_EMERGENCY_THRESHOLD" | bc -l) )); then
    log "WARN" "Token budget at ${TOKEN_USAGE}% - approaching limit"
    send_alert "Token budget critical"
  fi

  # Check stuck workers
  STUCK_WORKERS=$(find_stuck_workers)
  if [ -n "$STUCK_WORKERS" ]; then
    log "ERROR" "Stuck workers detected: $STUCK_WORKERS"
    cleanup_stuck_workers $STUCK_WORKERS
  fi

  # Update status.json
  update_system_status
}
```

**6. Graceful Shutdown**
```bash
graceful_shutdown() {
  log "INFO" "Shutdown signal received, cleaning up..."

  # Wait for active masters to complete (up to 5 minutes)
  TIMEOUT=300
  while [ "$ACTIVE_MASTERS" -gt 0 ] && [ "$TIMEOUT" -gt 0 ]; do
    log "INFO" "Waiting for $ACTIVE_MASTERS active masters to complete..."
    sleep 10
    ACTIVE_MASTERS=$(get_active_masters)
    TIMEOUT=$((TIMEOUT - 10))
  done

  # Force kill if timeout
  if [ "$ACTIVE_MASTERS" -gt 0 ]; then
    log "WARN" "Force killing $ACTIVE_MASTERS active masters"
    kill_active_masters
  fi

  # Clean up PID file
  rm -f "$PID_FILE"

  log "INFO" "Coordinator daemon stopped"
}
```

### Daemon Management

**Start Daemon**
```bash
$ ./scripts/coordinator-daemon.sh start
Starting coordinator-daemon...
✅ Daemon started (PID: 12345)
```

**Check Status**
```bash
$ ./scripts/coordinator-daemon.sh status
✅ Daemon running (PID: 12345)
📊 Status:
  - Uptime: 2h 34m
  - Tasks processed: 5
  - Active masters: 1 (security-master)
  - Token usage: 45% (121,500 / 270,000)
  - Last poll: 5 seconds ago
  - Health: ✅ Healthy
```

**Stop Daemon**
```bash
$ ./scripts/coordinator-daemon.sh stop
Stopping coordinator-daemon...
⏳ Waiting for active masters to complete...
✅ Daemon stopped gracefully
```

**Restart Daemon**
```bash
$ ./scripts/coordinator-daemon.sh restart
Stopping coordinator-daemon...
✅ Daemon stopped
Starting coordinator-daemon...
✅ Daemon started (PID: 12346)
```

### Advantages

- ✅ **Fully Autonomous**: No manual intervention needed
- ✅ **Continuous Processing**: Always monitoring and responding
- ✅ **Automatic Handoffs**: Seamless agent coordination
- ✅ **Scalable**: Can handle multiple tasks concurrently
- ✅ **Resilient**: Health monitoring and auto-recovery
- ✅ **Production-Ready**: Designed for long-running operation

### Disadvantages

- ❌ **More Complex**: Requires process management
- ❌ **Resource Usage**: Daemon runs continuously (low overhead)
- ❌ **Debugging Harder**: Background process, need good logging
- ❌ **Race Conditions**: Need proper locking mechanisms

### Use Cases

- Production deployment (always-on coordination)
- Multi-repository management (continuous monitoring)
- Long-running projects (autonomous task processing)
- Team environments (multiple users adding tasks)

### Success Criteria

- [ ] Daemon starts and runs in background
- [ ] Auto-detects and processes critical/high tasks
- [ ] Multiple masters can run concurrently
- [ ] Handoffs processed automatically
- [ ] Health monitoring prevents issues
- [ ] Graceful shutdown on stop signal
- [ ] Logs provide full audit trail
- [ ] Runs reliably for 24+ hours

---

## Option C: Event-Driven Automation

### Description

Real-time event-driven system using file system watchers (inotify/fswatch). **Instant response** to changes with no polling delay.

```bash
# Start event monitoring
./scripts/event-monitor.sh start

# System immediately responds to events:
# 1. New task added to task-queue.json → Instant dispatch
# 2. Worker completes → Instant aggregation
# 3. Handoff created → Instant processing
# 4. Token budget updated → Instant health check

# Events trigger within milliseconds
# No 30-second polling delay
```

### Architecture

```
event-monitor.sh (background process)
  ↓ (using fswatch/inotify)
Watches: coordination/*.json, agents/logs/workers/**
  ↓ (detects change instantly)
coordination/task-queue.json MODIFIED
  ↓ (triggers)
Task Change Handler
  ↓ (analyzes diff)
New task detected: task-012
  ↓ (dispatches immediately)
./scripts/run-security-master.sh --task task-012 &
  ↓ (0ms delay)
Instant task processing

Parallel event stream:
agents/logs/workers/worker-123/results.json CREATED
  ↓ (triggers)
Worker Completion Handler
  ↓ (processes immediately)
Aggregate results, update task status
  ↓ (0ms delay)
Instant feedback loop
```

### Event Types

**File System Events Monitored:**

1. **Task Queue Changes** (`coordination/task-queue.json`)
   - New task added → Dispatch to master
   - Task status changed → Update monitoring
   - Task completed → Archive and cleanup

2. **Worker Completion** (`agents/logs/workers/**/results.json`)
   - Worker finishes → Aggregate results
   - Worker fails → Retry or escalate
   - Worker timeout → Kill and restart

3. **Handoff Creation** (`coordination/handoffs.json`)
   - New handoff → Route to target agent
   - Handoff accepted → Update status
   - Handoff rejected → Escalate

4. **Token Budget Updates** (`coordination/token-budget.json`)
   - Budget approaching limit → Throttle dispatches
   - Emergency reserve triggered → Alert
   - Daily reset → Resume full operation

5. **Status Changes** (`coordination/status.json`)
   - System health degraded → Reduce load
   - Error threshold exceeded → Auto-pause
   - Recovery detected → Resume operations

### Components to Build

#### 1. Event Monitor

```bash
scripts/
├── event-monitor.sh             # Main event monitoring daemon
├── event-handlers/
│   ├── task-queue-handler.sh   # Handle task queue changes
│   ├── worker-handler.sh        # Handle worker events
│   ├── handoff-handler.sh       # Handle handoff events
│   ├── budget-handler.sh        # Handle budget events
│   └── health-handler.sh        # Handle health events
```

#### 2. Event Processing

```bash
scripts/lib/
├── event-parser.sh              # Parse file system events
├── diff-detector.sh             # Detect what changed
└── event-queue.sh               # Queue events if overwhelmed
```

#### 3. Rate Limiting

```bash
scripts/lib/
├── rate-limiter.sh              # Prevent event storms
└── backpressure.sh              # Handle overload gracefully
```

### Event Monitor Implementation

**Using fswatch (macOS/Linux)**

```bash
#!/bin/bash
# scripts/event-monitor.sh

# Start monitoring all coordination files
fswatch -0 \
  coordination/task-queue.json \
  coordination/handoffs.json \
  coordination/token-budget.json \
  coordination/status.json \
  "agents/logs/workers/**/*.json" | \
while read -d "" event; do
  handle_event "$event"
done
```

**Event Handler Dispatcher**

```bash
handle_event() {
  local FILE_PATH=$1
  local FILE_NAME=$(basename "$FILE_PATH")

  # Rate limiting: Skip if too many events
  if is_event_storm; then
    queue_event "$FILE_PATH"
    return
  fi

  # Route to appropriate handler
  case $FILE_NAME in
    task-queue.json)
      ./scripts/event-handlers/task-queue-handler.sh "$FILE_PATH" &
      ;;
    handoffs.json)
      ./scripts/event-handlers/handoff-handler.sh "$FILE_PATH" &
      ;;
    token-budget.json)
      ./scripts/event-handlers/budget-handler.sh "$FILE_PATH" &
      ;;
    status.json)
      ./scripts/event-handlers/health-handler.sh "$FILE_PATH" &
      ;;
    results.json)
      ./scripts/event-handlers/worker-handler.sh "$FILE_PATH" &
      ;;
  esac
}
```

**Task Queue Event Handler**

```bash
#!/bin/bash
# scripts/event-handlers/task-queue-handler.sh

FILE_PATH=$1

# Get previous state (from cache)
PREV_STATE=$(cat /tmp/task-queue-cache.json 2>/dev/null || echo '{}')

# Get current state
CURR_STATE=$(cat "$FILE_PATH")

# Detect changes using jq
NEW_TASKS=$(jq -n \
  --argjson prev "$PREV_STATE" \
  --argjson curr "$CURR_STATE" \
  '$curr.tasks - $prev.tasks')

# Process new tasks immediately
echo "$NEW_TASKS" | jq -c '.[]' | while read -r task; do
  TASK_ID=$(echo "$task" | jq -r '.id')
  TASK_TYPE=$(echo "$task" | jq -r '.type')
  TASK_PRIORITY=$(echo "$task" | jq -r '.priority')

  log "EVENT" "New task detected: $TASK_ID (type=$TASK_TYPE, priority=$TASK_PRIORITY)"

  # Instant dispatch (no polling delay!)
  dispatch_task_immediate "$TASK_ID" "$TASK_TYPE" "$TASK_PRIORITY"
done

# Cache current state for next comparison
echo "$CURR_STATE" > /tmp/task-queue-cache.json
```

**Worker Completion Handler**

```bash
#!/bin/bash
# scripts/event-handlers/worker-handler.sh

RESULTS_FILE=$1
WORKER_ID=$(basename $(dirname "$RESULTS_FILE"))

log "EVENT" "Worker completed: $WORKER_ID"

# Extract worker details
WORKER_DATA=$(cat "$RESULTS_FILE")
TASK_ID=$(echo "$WORKER_DATA" | jq -r '.task_id')
MASTER_ID=$(echo "$WORKER_DATA" | jq -r '.master_id')
STATUS=$(echo "$WORKER_DATA" | jq -r '.status')

# Notify master agent immediately
notify_master_agent "$MASTER_ID" "worker_completed" "$WORKER_ID" "$TASK_ID"

# Update worker pool
update_worker_pool_immediate "$WORKER_ID" "$STATUS"

# Trigger aggregation if all workers done
if all_workers_completed "$TASK_ID"; then
  trigger_aggregation "$TASK_ID" "$MASTER_ID"
fi
```

### Event Storm Protection

```bash
# Rate limiting: Max 10 events per second per file
is_event_storm() {
  local CURRENT_TIME=$(date +%s)
  local EVENT_COUNT=$(get_event_count_last_second)

  if [ "$EVENT_COUNT" -gt 10 ]; then
    log "WARN" "Event storm detected (${EVENT_COUNT}/s), activating rate limiting"
    return 0  # true
  fi

  return 1  # false
}

# Queue events during storms
queue_event() {
  local FILE_PATH=$1
  echo "$FILE_PATH" >> /tmp/event-queue.txt
  log "INFO" "Event queued: $FILE_PATH"
}

# Process queued events when storm subsides
process_event_queue() {
  if [ ! -f /tmp/event-queue.txt ]; then
    return
  fi

  while read -r event; do
    if ! is_event_storm; then
      handle_event "$event"
    else
      break  # Storm still active, wait
    fi
  done < /tmp/event-queue.txt

  # Clear processed events
  > /tmp/event-queue.txt
}
```

### Advantages

- ✅ **Instant Response**: 0ms polling delay, immediate reaction
- ✅ **Real-Time Coordination**: Tightest possible feedback loops
- ✅ **Resource Efficient**: No continuous polling CPU usage
- ✅ **Highly Responsive**: Best user experience
- ✅ **Event Audit Trail**: Every change captured and logged
- ✅ **Scalable**: Handles high-frequency changes

### Disadvantages

- ❌ **Most Complex**: Requires robust event handling
- ❌ **Event Storms**: Need protection against rapid-fire changes
- ❌ **Platform-Specific**: fswatch/inotify behavior varies
- ❌ **Race Conditions**: Concurrent event processing tricky
- ❌ **Debugging Complexity**: Event chains hard to trace
- ❌ **Overkill**: Might be unnecessary for typical workloads

### Use Cases

- High-frequency task environments (many tasks/minute)
- Multi-user scenarios (simultaneous task additions)
- CI/CD integration (instant response to commits)
- Real-time dashboards (live updates)
- Mission-critical operations (zero-delay response)

### Success Criteria

- [ ] Events detected within <100ms of file change
- [ ] No polling overhead when idle
- [ ] Event storm protection prevents overload
- [ ] Concurrent events handled safely
- [ ] Full event audit trail maintained
- [ ] Graceful degradation under load
- [ ] Works reliably across platforms
- [ ] Event queue processes backlog correctly

---

## Implementation Roadmap

### Phase 1: Script-Triggered Automation (Current Sprint)

**Goal**: Manual trigger, autonomous execution

**Deliverables**:
- ✅ spawn-worker.sh (worker spawning)
- ✅ run-security-master.sh (security automation)
- ✅ run-development-master.sh (development automation)
- ✅ run-inventory-master.sh (inventory automation)
- ✅ Worker prompt templates
- ✅ Library functions (coordination, logging, validation)
- ✅ End-to-end test with real task

**Timeline**: 1-2 days

**Success Metric**: Can run `./scripts/run-security-master.sh` and have it autonomously complete a security task from queue

---

### Phase 2: Daemon-Based Automation (Next Sprint)

**Goal**: Continuous autonomous operation

**Prerequisites**: Phase 1 complete and stable

**Deliverables**:
- ⚪ coordinator-daemon.sh (main daemon)
- ⚪ handoff-processor.sh (automatic handoffs)
- ⚪ health-monitor.sh (system health)
- ⚪ Process management utilities
- ⚪ daemon.conf (configuration)
- ⚪ Graceful shutdown handlers
- ⚪ 24-hour stability test

**Timeline**: 2-3 days

**Success Metric**: Daemon runs for 24+ hours, processing tasks automatically without intervention

---

### Phase 3: Event-Driven Automation (Future)

**Goal**: Real-time instant response

**Prerequisites**: Phase 2 complete, stable, and production-tested

**Deliverables**:
- ⚪ event-monitor.sh (file system watching)
- ⚪ Event handlers (task, worker, handoff, budget, health)
- ⚪ Event parsing and diffing utilities
- ⚪ Rate limiting and backpressure
- ⚪ Event queue management
- ⚪ Cross-platform compatibility
- ⚪ Load testing with high event frequency

**Timeline**: 3-5 days

**Success Metric**: Events processed within <100ms, system handles 100+ events/minute gracefully

---

## Decision Matrix: Which Option When?

| Scenario | Recommended Option | Rationale |
|----------|-------------------|-----------|
| **Getting started** | Option A | Simplest, fastest to build |
| **Daily security scans** | Option A or B | A if manual trigger OK, B for automation |
| **Production deployment** | Option B | Continuous operation needed |
| **High-frequency tasks** | Option C | Real-time response required |
| **Single-user** | Option A | Manual trigger sufficient |
| **Team environment** | Option B | Multiple users need automation |
| **CI/CD integration** | Option C | Instant response to commits |
| **Development/Testing** | Option A | Easy debugging |
| **Mission-critical** | Option C | Zero-delay response |
| **Resource-constrained** | Option A | Lowest overhead |

---

## Technical Considerations

### Concurrency Control

**Problem**: Multiple masters running simultaneously could conflict

**Solution**:
```bash
# scripts/lib/coordination.sh

acquire_lock() {
  local AGENT_ID=$1
  local LOCK_FILE="/tmp/cortex-${AGENT_ID}.lock"

  # Check if another instance running
  if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "ERROR: $AGENT_ID already running (PID: $PID)"
      exit 1
    else
      # Stale lock file, remove it
      rm -f "$LOCK_FILE"
    fi
  fi

  # Create lock
  echo $$ > "$LOCK_FILE"
}

release_lock() {
  local AGENT_ID=$1
  rm -f "/tmp/cortex-${AGENT_ID}.lock"
}
```

### Token Budget Tracking

**Problem**: Need real-time token tracking to prevent overruns

**Solution**:
```bash
# scripts/lib/token-tracking.sh

check_token_budget() {
  local AGENT_ID=$1
  local ESTIMATED_TOKENS=$2

  # Read current budget
  BUDGET=$(jq ".masters.${AGENT_ID}.allocated" coordination/token-budget.json)
  USED=$(jq ".masters.${AGENT_ID}.used" coordination/token-budget.json)
  AVAILABLE=$((BUDGET - USED))

  # Check if enough budget
  if [ "$ESTIMATED_TOKENS" -gt "$AVAILABLE" ]; then
    log "ERROR" "Insufficient token budget: need $ESTIMATED_TOKENS, have $AVAILABLE"
    return 1
  fi

  return 0
}

consume_tokens() {
  local AGENT_ID=$1
  local TOKENS_USED=$2

  # Atomic update using jq
  jq ".masters.${AGENT_ID}.used += $TOKENS_USED" \
    coordination/token-budget.json > /tmp/token-budget.tmp
  mv /tmp/token-budget.tmp coordination/token-budget.json

  log "INFO" "$AGENT_ID consumed $TOKENS_USED tokens"
}
```

### Error Handling

**Problem**: Workers can fail, need robust retry logic

**Solution**:
```bash
# scripts/spawn-worker.sh

spawn_worker_with_retry() {
  local MAX_RETRIES=3
  local RETRY_COUNT=0

  while [ "$RETRY_COUNT" -lt "$MAX_RETRIES" ]; do
    if spawn_worker "$@"; then
      return 0
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    log "WARN" "Worker spawn failed, retry $RETRY_COUNT/$MAX_RETRIES"
    sleep $((RETRY_COUNT * 5))  # Exponential backoff
  done

  log "ERROR" "Worker spawn failed after $MAX_RETRIES retries"
  return 1
}
```

### Logging Strategy

**All Options Use Structured Logging**:

```bash
# scripts/lib/logging.sh

log() {
  local LEVEL=$1
  local MESSAGE=$2
  local TIMESTAMP=$(date -Iseconds)

  # Console output
  echo "[$TIMESTAMP] $LEVEL: $MESSAGE"

  # Structured log file
  echo "{\"timestamp\":\"$TIMESTAMP\",\"level\":\"$LEVEL\",\"message\":\"$MESSAGE\"}" \
    >> agents/logs/system/$(date +%Y-%m-%d).jsonl

  # Send to dashboard events if significant
  if [ "$LEVEL" == "ERROR" ] || [ "$LEVEL" == "CRITICAL" ]; then
    broadcast_dashboard_event "system_error" "$MESSAGE"
  fi
}
```

---

## Migration Path

### Phase 1 → Phase 2

**What Changes**:
- Add coordinator-daemon.sh
- Scripts remain the same (reusable!)
- Add configuration files
- Add process management

**Migration Steps**:
1. Ensure Phase 1 scripts work reliably
2. Build daemon wrapper around existing scripts
3. Test daemon with manual task additions
4. Gradually increase auto-dispatch scope
5. Monitor for 24+ hours before trusting fully

**Rollback Plan**: Stop daemon, return to manual script execution

---

### Phase 2 → Phase 3

**What Changes**:
- Replace polling with event monitoring
- Add event handlers (call same scripts!)
- Add rate limiting
- Add event queue

**Migration Steps**:
1. Run event monitor alongside daemon (parallel)
2. Compare behavior (should be identical)
3. Gradually switch from daemon to event monitor
4. Monitor event storm protection
5. Full cutover when confident

**Rollback Plan**: Stop event monitor, restart daemon

---

## Monitoring & Observability

### Key Metrics

All phases should track:

- **Task Throughput**: Tasks completed per hour
- **Worker Success Rate**: % of workers that complete successfully
- **Token Efficiency**: Actual vs estimated token usage
- **Response Time**: Time from task creation to completion
- **System Health**: Token budget, active workers, error rate
- **Coordination Lag**: Time between agent handoffs

### Dashboards

- **Option A**: Manual status checks via `./scripts/worker-status.sh`
- **Option B**: Dashboard updates from daemon status
- **Option C**: Real-time dashboard via WebSocket events

---

## Security Considerations

### Credential Management

**Never hardcode credentials in scripts**

```bash
# ❌ Bad
API_KEY="sk-1234567890"

# ✅ Good
API_KEY="${N8N_API_KEY:-$(security find-generic-password -a n8n -s cortex -w)}"
```

### Script Permissions

```bash
# All scripts should be executable by owner only
chmod 700 scripts/*.sh
chmod 700 scripts/event-handlers/*.sh

# Coordination files should be writable by daemon
chmod 660 coordination/*.json
```

### Audit Trail

All phases maintain complete audit trail:
- Every agent execution logged
- Every worker spawn recorded
- Every coordination file change timestamped
- Every token usage tracked

---

## Testing Strategy

### Phase 1 Testing

- ✅ Unit test each script independently
- ✅ Integration test worker spawning
- ✅ End-to-end test with real task
- ✅ Dry-run mode validation
- ✅ Error handling verification

### Phase 2 Testing

- ⚪ Daemon start/stop/restart reliability
- ⚪ Concurrent task processing
- ⚪ Graceful shutdown under load
- ⚪ 24-hour stability test
- ⚪ Token budget enforcement
- ⚪ Health monitoring accuracy

### Phase 3 Testing

- ⚪ Event detection latency (<100ms)
- ⚪ Event storm protection (1000+ events/sec)
- ⚪ Race condition handling
- ⚪ Cross-platform compatibility
- ⚪ Event queue backlog processing
- ⚪ Load testing (sustained high frequency)

---

## FAQ

### When should I use which option?

- **Just starting**: Use Option A
- **Ready for automation**: Use Option B
- **Need real-time**: Use Option C

### Can I run multiple options simultaneously?

No, they conflict. Choose one at a time.

### How do I debug issues?

- Check logs: `agents/logs/system/*.jsonl`
- Check coordination files: `coordination/*.json`
- Use dry-run mode: `--dry-run` flag
- Enable verbose logging: `LOG_LEVEL=DEBUG`

### What if token budget runs out?

- System automatically stops dispatching
- Emergency reserve available for critical tasks
- Health monitor alerts immediately
- Graceful degradation prevents failures

### How do I add a new master agent?

1. Add prompt: `agents/prompts/new-master.md`
2. Add script: `scripts/run-new-master.sh`
3. Update registry: `agents/configs/agent-registry.json`
4. Update daemon routing (Phase 2+)
5. Update event handlers (Phase 3)

---

## Appendix A: File Structure

```
cortex/
├── scripts/
│   ├── spawn-worker.sh              # Phase 1
│   ├── run-coordinator.sh           # Phase 1
│   ├── run-security-master.sh       # Phase 1
│   ├── run-development-master.sh    # Phase 1
│   ├── run-inventory-master.sh      # Phase 1
│   ├── worker-status.sh             # Phase 1
│   ├── coordinator-daemon.sh        # Phase 2
│   ├── handoff-processor.sh         # Phase 2
│   ├── health-monitor.sh            # Phase 2
│   ├── event-monitor.sh             # Phase 3
│   ├── lib/
│   │   ├── coordination.sh          # All phases
│   │   ├── logging.sh               # All phases
│   │   ├── validation.sh            # All phases
│   │   ├── token-tracking.sh        # All phases
│   │   ├── daemon.sh                # Phase 2
│   │   ├── pid-management.sh        # Phase 2
│   │   ├── signal-handlers.sh       # Phase 2
│   │   ├── event-parser.sh          # Phase 3
│   │   ├── diff-detector.sh         # Phase 3
│   │   ├── event-queue.sh           # Phase 3
│   │   ├── rate-limiter.sh          # Phase 3
│   │   └── backpressure.sh          # Phase 3
│   ├── worker-templates/
│   │   ├── scan-worker.md
│   │   ├── fix-worker.md
│   │   ├── implementation-worker.md
│   │   ├── test-worker.md
│   │   └── pr-worker.md
│   └── event-handlers/             # Phase 3
│       ├── task-queue-handler.sh
│       ├── worker-handler.sh
│       ├── handoff-handler.sh
│       ├── budget-handler.sh
│       └── health-handler.sh
├── config/
│   ├── daemon.conf                  # Phase 2
│   └── priorities.conf              # Phase 2
└── docs/
    └── automation-architecture.md   # This document
```

---

## Appendix B: Example Session

### Phase 1 Example

```bash
# User manually triggers security master
$ ./scripts/run-security-master.sh

📋 Reading task queue...
✅ Found task-010 (CRITICAL security remediation)

🎯 Security Master Decision:
   Task: task-010 (n8n-mcp-server security regression)
   Strategy: Spawn 3 fix-workers
   Estimated tokens: 18,000

🔄 Spawning workers...
   ✅ worker-validation-001 (6,000 tokens)
   ✅ worker-errors-002 (6,000 tokens)
   ✅ worker-tests-003 (6,000 tokens)

⏳ Monitoring worker progress...
   [▓▓▓▓▓▓▓▓▓▓] worker-validation-001 complete
   [▓▓▓▓▓▓▓▓▓▓] worker-errors-002 complete
   [▓▓▓▓▓▓▓▓▓▓] worker-tests-003 complete

📊 Aggregating results...
   ✅ 3 CRITICAL vulnerabilities fixed
   ✅ 18 security tests added
   ✅ All tests passing (36/36)

💾 Updating coordination files...
   ✅ task-queue.json (task-010: completed)
   ✅ worker-pool.json (3 workers completed)
   ✅ token-budget.json (17,500 tokens used)
   ✅ handoffs.json (handoff to coordinator)

✅ Security Master completed successfully
   Duration: 10 minutes
   Workers: 3/3 successful
   Tokens: 20,000 used (18,000 workers + 2,000 master)
```

### Phase 2 Example

```bash
# Daemon running in background
$ ./scripts/coordinator-daemon.sh status

✅ Daemon running (PID: 12345)
📊 Status:
   Uptime: 3h 45m
   Tasks processed: 12
   Active masters: 2
     - security-master (task-010)
     - development-master (task-008)
   Token usage: 52% (140,400 / 270,000)
   Last poll: 8 seconds ago
   Health: ✅ Healthy

# New task gets added to queue (automatically)
$ echo '{"id":"task-013",...}' >> coordination/task-queue.json

# Daemon detects within 30 seconds (next poll)
# [Daemon Log]
[2025-11-02T14:23:15] INFO: New task detected: task-013
[2025-11-02T14:23:15] INFO: Dispatching to security-master
[2025-11-02T14:23:16] INFO: security-master started (PID: 12456)
[2025-11-02T14:23:45] INFO: security-master completed task-013
[2025-11-02T14:23:45] INFO: Handoff created to coordinator-master
[2025-11-02T14:23:46] INFO: Processing handoff handoff-025
```

### Phase 3 Example

```bash
# Event monitor running
$ ./scripts/event-monitor.sh status

✅ Event monitor running (PID: 12345)
📊 Status:
   Uptime: 6h 12m
   Events processed: 456
   Events/minute: 1.2
   Avg response: 45ms
   Health: ✅ Healthy

# New task added
$ echo '{"id":"task-014",...}' >> coordination/task-queue.json

# Event detected INSTANTLY (< 100ms)
# [Event Monitor Log]
[2025-11-02T14:23:15.123] EVENT: task-queue.json modified
[2025-11-02T14:23:15.156] INFO: New task detected: task-014
[2025-11-02T14:23:15.167] INFO: Dispatching immediately
[2025-11-02T14:23:15.189] INFO: security-master started (PID: 12456)

# Total latency: 66ms from file change to agent start
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-02
**Next Review**: After Phase 1 completion

---

*This is a living document. Update as implementation progresses and new requirements emerge.*
