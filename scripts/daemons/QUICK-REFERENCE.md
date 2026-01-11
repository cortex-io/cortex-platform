# Deprecated Daemons - Quick Reference

All daemons deprecated 2025-12-01. Use event-driven architecture instead.

## Quick Migration Map

| Old Daemon | New Event Handler | Event Type |
|------------|-------------------|------------|
| heartbeat-monitor-daemon.sh | on-worker-heartbeat.sh | worker.heartbeat |
| worker-restart-daemon.sh | on-worker-heartbeat.sh | worker.failed |
| workflow-daemon.sh | on-worker-complete.sh | task.completed |
| failure-pattern-daemon.sh | on-task-failure.sh | task.failed |
| auto-fix-daemon.sh | on-task-failure.sh | task.failed |
| auto-learning-daemon.sh | on-learning-pattern.sh | learning.pattern_detected |
| moe-learning-daemon.sh | on-routing-decision.sh | routing.decision_made |
| anomaly-detector-daemon.sh | on-worker-heartbeat.sh | worker.heartbeat |
| security-scan-daemon.sh | on-security-alert.sh | security.scan_completed |
| threat-intel-daemon.sh | on-security-alert.sh | security.vulnerability_found |
| cleanup-daemon.sh | on-cleanup-needed.sh | system.cleanup_needed |
| backup-daemon.sh | on-backup-scheduled.sh | system.backup_scheduled |
| freshness-daemon.sh | on-cleanup-needed.sh | system.freshness_check |
| metrics-aggregator-daemon.sh | Multiple handlers | All events |
| observability-hub-daemon.sh | Event logs + notebooks | All events |
| ingestion-daemon.sh | event-dispatcher.sh | All events |

## Stop All Daemons

```bash
./scripts/daemons/stop-all-daemons.sh
```

## Start Event System

```bash
# One-time
./scripts/events/event-dispatcher.sh

# Automated (cron)
* * * * * cd /Users/ryandahlberg/Projects/cortex && ./scripts/events/event-dispatcher.sh
```

## Emit Event (Replace Daemon Call)

```bash
source scripts/events/lib/event-logger.sh
create_and_log_event "EVENT_TYPE" "SOURCE" '{"data":"here"}' "CORRELATION_ID" "PRIORITY"
```

## Full Documentation

- DEPRECATED.md - Complete migration guide
- DAEMON-DECOMMISSION-REPORT.md - Detailed report
- docs/EVENT-DRIVEN-ARCHITECTURE.md - Architecture overview
