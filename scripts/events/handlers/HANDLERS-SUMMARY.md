# Cortex Event Handlers Summary

This document provides an overview of all event handlers in the Cortex event-driven architecture.

## Overview

Event handlers are bash scripts that process specific event types. They are invoked by the event dispatcher (`event-dispatcher.sh`) when events matching their type are found in the event queue.

## Handler Architecture

All handlers follow this pattern:

1. **Accept event file path** as argument
2. **Parse event JSON** to extract relevant data
3. **Perform handler-specific actions** (logging, metrics, state updates)
4. **Update relevant data stores** (JSONL logs, JSON state files)
5. **Create follow-up events** if needed
6. **Return success (0) or failure (non-zero)**

## Handler Inventory

### Task Lifecycle Handlers

#### 1. on-task-created.sh
**Event Type:** `task.created`

**Purpose:** Triggered when new tasks are created in the system.

**Actions:**
- Records task creation metrics in `coordination/metrics/task-creation-metrics.jsonl`
- Updates task statistics by priority, type, and master
- Adds task to task queue if not present
- Creates high-priority alerts for critical/high priority tasks
- Logs to dashboard events for visibility

**Output Files:**
- `coordination/metrics/task-creation-metrics.jsonl` - Task creation log
- `coordination/metrics/task-stats.json` - Aggregated task statistics
- `coordination/task-queue.json` - Updated task queue
- `coordination/dashboard-events.jsonl` - Dashboard events

**Alert Conditions:**
- Creates `system.health_alert` for tasks with priority "high" or "critical"

---

#### 2. on-task-assigned.sh
**Event Type:** `task.assigned`

**Purpose:** Triggered when tasks are assigned to workers.

**Actions:**
- Records task assignment in tracking file
- Updates task queue status to "assigned"
- Updates worker pool status to "busy"
- Logs routing decision
- Updates assignment statistics (by strategy, worker type, master)
- Creates routing event for learning system
- Logs to dashboard events

**Output Files:**
- `coordination/metrics/task-assignments.jsonl` - Assignment tracking log
- `coordination/task-queue.json` - Updated task queue
- `coordination/worker-pool.json` - Updated worker pool
- `coordination/routing/routing-decisions.jsonl` - Routing decisions
- `coordination/metrics/assignment-stats.json` - Assignment statistics
- `coordination/dashboard-events.jsonl` - Dashboard events

**Follow-up Events:**
- Creates `routing.decision_made` event for learning system

---

### Worker Lifecycle Handlers

#### 3. on-worker-complete.sh
**Event Type:** `worker.completed`

**Purpose:** Triggered when workers complete their tasks successfully.

**Actions:**
- Records worker performance metrics (duration, tokens used)
- Triggers auto-learning for successful completions
- Updates worker pool status to "available"
- Creates learning pattern event

**Output Files:**
- `coordination/metrics/worker-performance.jsonl` - Performance metrics
- `coordination/worker-pool.json` - Updated worker pool

**Follow-up Events:**
- Creates `learning.pattern_detected` event for successful completions

---

#### 4. on-worker-heartbeat.sh
**Event Type:** `worker.heartbeat`

**Purpose:** Tracks worker health and activity.

**Actions:**
- Updates worker health metrics
- Tracks worker activity timestamps
- Detects stale workers (no heartbeat in expected interval)

**Output Files:**
- `coordination/worker-health-metrics.jsonl` - Health tracking log

---

### System Lifecycle Handlers

#### 5. on-system-startup.sh
**Event Type:** `daemon.started`

**Purpose:** Triggered when Cortex system or daemons start.

**Actions:**
- Records startup event with version and mode
- Verifies and creates critical directories if missing
- Performs comprehensive health check:
  - Event dispatcher availability
  - Config file presence
  - Disk space check
- Creates health alerts for detected issues
- Initializes/updates system status
- Cleans up stale PID files on restart
- Updates startup statistics

**Output Files:**
- `coordination/metrics/system-startups.jsonl` - Startup log
- `coordination/system-health.json` - Health check results
- `coordination/status.json` - System status
- `coordination/metrics/startup-stats.json` - Startup statistics
- `coordination/dashboard-events.jsonl` - Dashboard events

**Health Checks:**
- Event dispatcher executable check
- Main config file existence
- Disk space availability (warns if < 1GB free)

**Alert Conditions:**
- Creates `system.health_alert` if health issues detected during startup

---

#### 6. on-system-shutdown.sh
**Event Type:** `daemon.stopped`

**Purpose:** Triggered when Cortex system or daemons shut down.

**Actions:**
- Records shutdown event with reason and graceful flag
- Backs up critical state files to timestamped directory:
  - task-queue.json
  - worker-pool.json
  - status.json
  - system-health.json
  - pm-state.json
- Cleans up temporary files (*.tmp files in queue, temp, /tmp)
- Archives old events (>7 days) to compressed tar.gz on graceful shutdown
- Checks for active workers during shutdown
- Creates alerts if workers still active
- Updates system status to "stopped"
- Generates shutdown report
- Updates shutdown statistics

**Output Files:**
- `coordination/metrics/system-shutdowns.jsonl` - Shutdown log
- `coordination/history/shutdown-YYYYMMDD-HHMMSS/` - State backup directory
- `coordination/history/shutdown-YYYYMMDD-HHMMSS/shutdown-report.json` - Shutdown report
- `coordination/status.json` - Updated system status
- `coordination/metrics/shutdown-stats.json` - Shutdown statistics
- `coordination/dashboard-events.jsonl` - Dashboard events

**Alert Conditions:**
- Creates `system.health_alert` if active workers detected during shutdown

---

### Security Handlers

#### 7. on-security-scan-completed.sh
**Event Type:** `security.scan_completed`

**Purpose:** Triggered when security scans finish.

**Actions:**
- Records scan results with vulnerability counts by severity
- Creates detailed vulnerability report if vulnerabilities found
- Creates alerts for critical/high severity vulnerabilities
- Aggregates scan statistics (by scanner, scan type, severity)
- Calculates and updates security posture score:
  - Score = 100 - (critical×10 + high×5 + medium×2 + low×1)
  - Max deduction: 100 (minimum score: 0)
- Triggers remediation workflow for critical vulnerabilities
- Creates follow-up vulnerability events for critical findings
- Logs to dashboard events

**Output Files:**
- `coordination/security/scan-results.jsonl` - Scan results log
- `coordination/security/reports/scan-{id}-YYYYMMDD-HHMMSS.json` - Detailed vulnerability reports
- `coordination/metrics/security-stats.json` - Aggregated security statistics
- `coordination/security/posture-score.json` - Security posture score
- `coordination/remediation/remediation-{scan_id}.json` - Remediation tasks
- `coordination/dashboard-events.jsonl` - Dashboard events

**Alert Conditions:**
- Creates `system.health_alert` for critical or high severity vulnerabilities
- Priority "critical" if critical vulnerabilities found, otherwise "high"

**Follow-up Events:**
- Creates `security.vulnerability_found` event for critical vulnerabilities

**Remediation Triggers:**
- Automatically creates remediation task for any critical vulnerabilities

---

#### 8. on-security-alert.sh
**Event Type:** `security.vulnerability_found`

**Purpose:** Processes individual security vulnerabilities and scan results.

**Actions:**
- Records security event details
- Updates security dashboard metrics for high/critical alerts
- Maintains rolling window of last 10 critical alerts
- Aggregates security statistics by severity
- Updates security stats counters

**Output Files:**
- `coordination/security/scan-results.jsonl` - Security event log
- `coordination/security/dashboard-metrics.json` - Dashboard metrics
- `coordination/metrics/security-stats.json` - Security statistics

**Alert Conditions:**
- Creates `system.health_alert` for high/critical severity events

---

### Routing & Learning Handlers

#### 9. on-routing-decision.sh
**Event Type:** `routing.decision_made`

**Purpose:** Logs routing decisions for analysis and learning.

**Actions:**
- Records routing decision details
- Tracks routing patterns
- Updates routing statistics

**Output Files:**
- `coordination/routing/routing-decisions.jsonl` - Routing decisions log

---

#### 10. on-learning-pattern.sh
**Event Type:** `learning.pattern_detected`

**Purpose:** Processes detected patterns for ASI learning system.

**Actions:**
- Records learning patterns
- Updates pattern detection statistics
- Triggers knowledge base updates

**Output Files:**
- `coordination/patterns/learning-patterns.jsonl` - Learning patterns log

---

### Maintenance Handlers

#### 11. on-cleanup-needed.sh
**Event Type:** `system.cleanup_needed`

**Purpose:** Triggers system cleanup operations.

**Actions:**
- Archives old logs and events
- Compresses historical data
- Removes temporary files
- Purges expired data

**Output Files:**
- `coordination/metrics/cleanup-operations.jsonl` - Cleanup log

---

#### 12. on-task-failure.sh
**Event Type:** `task.failed`

**Purpose:** Handles task failures and triggers auto-fix if applicable.

**Actions:**
- Records failure pattern in database
- Detects repeated failure patterns (>3 occurrences)
- Creates health alerts for repeated failures
- Triggers auto-fix for known error types (timeout, connection_error, rate_limit)
- Updates task queue status to "failed"

**Output Files:**
- `coordination/patterns/failure-patterns.jsonl` - Failure patterns log
- `coordination/task-queue.json` - Updated task queue

**Alert Conditions:**
- Creates `system.health_alert` if same error type occurs >3 times in recent history

**Auto-fix Triggers:**
- timeout → retry with backoff
- connection_error → retry with backoff
- rate_limit → retry with backoff

---

## Event Dispatcher Routing

The event dispatcher (`event-dispatcher.sh`) routes events to handlers based on `event_type`:

| Event Type | Handler |
|------------|---------|
| `worker.completed` | on-worker-complete.sh |
| `worker.failed` | on-worker-failed.sh (if exists) |
| `worker.heartbeat` | on-worker-heartbeat.sh |
| `task.created` | on-task-created.sh |
| `task.assigned` | on-task-assigned.sh |
| `task.completed` | on-task-complete.sh (if exists) |
| `task.failed` | on-task-failure.sh |
| `security.scan_completed` | on-security-scan-completed.sh |
| `security.vulnerability_found` | on-security-alert.sh |
| `routing.decision_made` | on-routing-decision.sh |
| `learning.pattern_detected` | on-learning-pattern.sh |
| `system.cleanup_needed` | on-cleanup-needed.sh |
| `system.health_alert` | on-health-alert.sh (if exists) |
| `daemon.started` | on-system-startup.sh |
| `daemon.stopped` | on-system-shutdown.sh |

## Handler Best Practices

All handlers implement these best practices:

1. **Idempotency**: Safe to run multiple times with same event
2. **Error Handling**: Use `set -euo pipefail` for robust error handling
3. **Logging**: Consistent timestamped logging format
4. **Atomic Updates**: Use temporary files and `mv` for atomic updates
5. **JSON Validation**: Use `jq` for safe JSON parsing
6. **Directory Creation**: Always create output directories if missing
7. **Default Values**: Provide sensible defaults for missing fields
8. **Follow-up Events**: Create events for cascading actions
9. **Metrics Collection**: Record quantitative data for analysis
10. **Dashboard Integration**: Log significant events to dashboard

## Testing Handlers

To test a handler manually:

```bash
# Create a test event
cat > /tmp/test-event.json <<EOF
{
  "event_id": "evt_20251201_120000_test123",
  "event_type": "task.created",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source": "test-source",
  "correlation_id": "task-test-001",
  "metadata": {
    "priority": "high",
    "master": "development"
  },
  "payload": {
    "task_id": "task-test-001",
    "task_type": "implementation",
    "description": "Test task for handler validation"
  }
}
EOF

# Run the handler
/Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-task-created.sh /tmp/test-event.json

# Check the outputs
tail -5 /Users/ryandahlberg/Projects/cortex/coordination/metrics/task-creation-metrics.jsonl
cat /Users/ryandahlberg/Projects/cortex/coordination/metrics/task-stats.json | jq
```

## Handler Development Checklist

When creating new handlers:

- [ ] Use standard bash error handling (`set -euo pipefail`)
- [ ] Accept event file path as first argument
- [ ] Parse event JSON with `jq`
- [ ] Provide defaults for optional fields
- [ ] Log actions with timestamps
- [ ] Create output directories if missing
- [ ] Use atomic file operations (temp file + mv)
- [ ] Update relevant metrics files
- [ ] Create follow-up events if needed
- [ ] Log to dashboard events
- [ ] Make file executable (`chmod +x`)
- [ ] Add route to event-dispatcher.sh
- [ ] Test with sample event
- [ ] Document in this file

## File Locations

- **Handlers Directory**: `/Users/ryandahlberg/Projects/cortex/scripts/events/handlers/`
- **Event Queue**: `/Users/ryandahlberg/Projects/cortex/coordination/events/queue/`
- **Event Archive**: `/Users/ryandahlberg/Projects/cortex/coordination/events/archive/`
- **Metrics**: `/Users/ryandahlberg/Projects/cortex/coordination/metrics/`
- **Security**: `/Users/ryandahlberg/Projects/cortex/coordination/security/`
- **Dashboard**: `/Users/ryandahlberg/Projects/cortex/coordination/dashboard-events.jsonl`

## Related Documentation

- [Event Schema](../event-schema.json) - JSON schema for all events
- [Event-Driven Architecture](../../../docs/EVENT-DRIVEN-ARCHITECTURE.md) - Architecture overview
- [Quick Start Guide](../../../docs/QUICK-START-EVENT-DRIVEN.md) - Getting started guide

## Maintenance

Last Updated: 2025-12-01
Handlers Count: 12 active handlers
Event Types Covered: 16 event types
