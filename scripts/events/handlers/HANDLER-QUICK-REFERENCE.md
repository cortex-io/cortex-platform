# Cortex Event Handlers - Quick Reference

## Overview
15 event handlers covering all event types in the Cortex event schema.

## Handlers by Category

### Task Events (5 handlers)
| Event Type | Handler | Purpose |
|------------|---------|---------|
| `task.created` | on-task-created.sh | Log task creation, update metrics, alert on high-priority |
| `task.assigned` | on-task-assigned.sh | Track assignment, update routing decisions |
| `task.completed` | on-task-complete.sh | Record completion metrics, update task queue |
| `task.failed` | on-task-failure.sh | Log failures, detect patterns, trigger auto-fix |

### Worker Events (3 handlers)
| Event Type | Handler | Purpose |
|------------|---------|---------|
| `worker.completed` | on-worker-complete.sh | Track performance, trigger learning |
| `worker.failed` | on-worker-failed.sh | Record failures, update worker pool |
| `worker.heartbeat` | on-worker-heartbeat.sh | Monitor worker health |

### Security Events (2 handlers)
| Event Type | Handler | Purpose |
|------------|---------|---------|
| `security.scan_completed` | on-security-scan-completed.sh | Aggregate results, create alerts, trigger remediation |
| `security.vulnerability_found` | on-security-alert.sh | Process vulnerabilities, update dashboard |

### System Events (2 handlers)
| Event Type | Handler | Purpose |
|------------|---------|---------|
| `daemon.started` | on-system-startup.sh | Initialize state, health check, verify directories |
| `daemon.stopped` | on-system-shutdown.sh | Backup state, cleanup, archive events |

### Routing & Learning (2 handlers)
| Event Type | Handler | Purpose |
|------------|---------|---------|
| `routing.decision_made` | on-routing-decision.sh | Log routing decisions for analysis |
| `learning.pattern_detected` | on-learning-pattern.sh | Record patterns for ASI learning |

### Maintenance (2 handlers)
| Event Type | Handler | Purpose |
|------------|---------|---------|
| `system.cleanup_needed` | on-cleanup-needed.sh | Archive logs, remove temp files |
| `system.health_alert` | on-health-alert.sh | Process health alerts, track statistics |

## Key Output Locations

### Metrics
- `coordination/metrics/task-creation-metrics.jsonl` - Task creation log
- `coordination/metrics/task-assignments.jsonl` - Assignment tracking
- `coordination/metrics/task-completion-metrics.jsonl` - Completion log
- `coordination/metrics/worker-performance.jsonl` - Worker performance
- `coordination/metrics/worker-failures.jsonl` - Worker failures
- `coordination/metrics/system-startups.jsonl` - Startup events
- `coordination/metrics/system-shutdowns.jsonl` - Shutdown events

### Statistics (aggregated)
- `coordination/metrics/task-stats.json` - Task statistics by priority/type/master
- `coordination/metrics/assignment-stats.json` - Assignment statistics
- `coordination/metrics/security-stats.json` - Security scan statistics
- `coordination/metrics/health-alert-stats.json` - Health alert statistics

### Security
- `coordination/security/scan-results.jsonl` - All scan results
- `coordination/security/reports/scan-*.json` - Detailed vulnerability reports
- `coordination/security/posture-score.json` - Current security posture
- `coordination/remediation/remediation-*.json` - Remediation tasks

### State Files
- `coordination/task-queue.json` - Current task queue
- `coordination/worker-pool.json` - Worker pool state
- `coordination/status.json` - System status
- `coordination/system-health.json` - Health check results
- `coordination/health-alerts.json` - Active health alerts

### Patterns & Learning
- `coordination/patterns/failure-patterns.jsonl` - Failure patterns
- `coordination/patterns/learning-patterns.jsonl` - Learning patterns
- `coordination/routing/routing-decisions.jsonl` - Routing decisions

### Dashboard & Reports
- `coordination/dashboard-events.jsonl` - Dashboard event stream
- `coordination/health-reports.jsonl` - Health report log

## Handler Features

All handlers implement:
- **Idempotent operations** - Safe to run multiple times
- **Error handling** - `set -euo pipefail`
- **Structured logging** - Timestamped with component tag
- **JSON validation** - Safe parsing with jq
- **Atomic updates** - Temp file + mv pattern
- **Metrics collection** - Quantitative tracking
- **Dashboard integration** - Event logging
- **Follow-up events** - Cascading actions

## Testing a Handler

```bash
# Example: Test task creation handler
cat > /tmp/test-task-created.json <<EOF
{
  "event_id": "evt_$(date +%Y%m%d_%H%M%S)_test001",
  "event_type": "task.created",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source": "test-system",
  "correlation_id": "task-test-001",
  "metadata": {
    "priority": "high",
    "master": "development"
  },
  "payload": {
    "task_id": "task-test-001",
    "task_type": "feature",
    "description": "Test feature implementation"
  }
}
EOF

# Run handler
/Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-task-created.sh /tmp/test-task-created.json

# Verify outputs
tail -1 /Users/ryandahlberg/Projects/cortex/coordination/metrics/task-creation-metrics.jsonl | jq
cat /Users/ryandahlberg/Projects/cortex/coordination/metrics/task-stats.json | jq
```

## Event Priority Handling

Events are processed by priority (in dispatcher):
1. **critical** - Immediate processing
2. **high** - High priority processing
3. **medium** - Normal priority (default)
4. **low** - Background processing

## Alert Triggers

Handlers create alerts for:

| Handler | Condition | Priority |
|---------|-----------|----------|
| on-task-created | Priority = high/critical | high/critical |
| on-task-failure | >3 repeated failures | high |
| on-system-startup | Health issues detected | high |
| on-system-shutdown | Active workers during shutdown | high |
| on-security-scan-completed | Critical/high vulnerabilities | critical/high |
| on-security-alert | High/critical severity | critical/high |

## Remediation Workflows

Automatic remediation triggered by:
- **Critical vulnerabilities** (on-security-scan-completed.sh)
- **Known error types** (on-task-failure.sh): timeout, connection_error, rate_limit

## Files Created

**New Handlers** (8):
1. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-task-created.sh
2. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-task-assigned.sh
3. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-system-startup.sh
4. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-system-shutdown.sh
5. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-security-scan-completed.sh
6. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-worker-failed.sh
7. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-task-complete.sh
8. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/on-health-alert.sh

**Updated Files** (1):
1. /Users/ryandahlberg/Projects/cortex/scripts/events/event-dispatcher.sh - Added routing for new handlers

**Documentation** (2):
1. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/HANDLERS-SUMMARY.md - Comprehensive documentation
2. /Users/ryandahlberg/Projects/cortex/scripts/events/handlers/HANDLER-QUICK-REFERENCE.md - Quick reference guide

## Related Files
- **Event Schema**: scripts/events/event-schema.json
- **Event Logger**: scripts/events/lib/event-logger.sh
- **Event Validator**: scripts/events/lib/event-validator.sh
- **Event Dispatcher**: scripts/events/event-dispatcher.sh

## Next Steps

1. **Test handlers** with sample events
2. **Integrate with event emitters** (masters, workers, daemons)
3. **Monitor handler execution** via logs
4. **Review handler outputs** in coordination/ directories
5. **Tune alert thresholds** based on operational data

Last Updated: 2025-12-01
Total Handlers: 15
Event Types Covered: 16
