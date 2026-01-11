# Cortex Event System Scripts

This directory contains the event-driven architecture scripts for Cortex.

## Core Scripts

### Event Dispatcher
**File**: `event-dispatcher.sh`

Routes events from the queue to appropriate handlers. Runs once and exits.

```bash
./scripts/events/event-dispatcher.sh
```

**Features**:
- Processes events by priority (critical → high → medium → low)
- Routes to type-specific handlers
- Archives processed events by date
- Validates events before processing

### Event Replay
**File**: `event-replay.sh`

Replay archived events for debugging and testing.

```bash
# Replay single event
./scripts/events/event-replay.sh --event-id evt_20251201_123456_abc123

# Replay all events from a date
./scripts/events/event-replay.sh --date 2025-12-01

# Replay with filters
./scripts/events/event-replay.sh --type "worker.*" --date 2025-12-01 --verbose

# Dry run
./scripts/events/event-replay.sh --date 2025-12-01 --dry-run
```

**Features**:
- Replay by event ID or date
- Filter by type, source, priority, correlation ID
- Dry-run mode for preview
- Verbose debugging output
- Direct invocation or re-queue modes

See: `EVENT-REPLAY-QUICK-REF.md` and `/Users/ryandahlberg/Projects/cortex/docs/EVENT-REPLAY-GUIDE.md`

## Library Scripts

### Event Logger
**File**: `lib/event-logger.sh`

Creates and logs events to JSONL files and queue.

```bash
# Create and log event
./scripts/events/lib/event-logger.sh --create \
    "worker.completed" \
    "worker-001" \
    '{"status": "completed"}' \
    "task-123" \
    "medium"

# Or use programmatically
source scripts/events/lib/event-logger.sh
event=$(create_event "task.failed" "processor" '{"error": "timeout"}')
log_event "$event"
```

### Event Validator
**File**: `lib/event-validator.sh`

Validates event structure against schema.

```bash
./scripts/events/lib/event-validator.sh "$(cat event.json)"
```

## Event Handlers

Located in `handlers/`, these scripts process specific event types:

| Handler | Event Type | Purpose |
|---------|------------|---------|
| `on-worker-complete.sh` | `worker.completed` | Process completed worker |
| `on-worker-failed.sh` | `worker.failed` | Handle worker failures |
| `on-worker-heartbeat.sh` | `worker.heartbeat` | Monitor worker health |
| `on-task-complete.sh` | `task.completed` | Process completed task |
| `on-task-failure.sh` | `task.failed` | Handle task failures |
| `on-security-alert.sh` | `security.*` | Process security events |
| `on-routing-decision.sh` | `routing.decision_made` | Log routing decisions |
| `on-learning-pattern.sh` | `learning.pattern_detected` | Update learning models |
| `on-cleanup-needed.sh` | `system.cleanup_needed` | Trigger cleanup |
| `on-health-alert.sh` | `system.health_alert` | Handle health alerts |

## Configuration

### Event Schema
**File**: `event-schema.json`

Defines the structure of valid events.

Required fields:
- `event_id`: Unique identifier
- `event_type`: Event type (e.g., "worker.completed")
- `timestamp`: ISO 8601 timestamp
- `source`: Component that emitted the event

Optional fields:
- `correlation_id`: ID to correlate related events
- `metadata`: Additional context (priority, tags)
- `payload`: Event-specific data

## Testing

### Test Event Flow
**File**: `test-event-flow.sh`

End-to-end test of event system.

```bash
./scripts/events/test-event-flow.sh
```

### Test Event Replay
**File**: `test-event-replay.sh`

Comprehensive test suite for event replay.

```bash
./scripts/events/test-event-replay.sh
```

## Directory Structure

```
scripts/events/
├── event-dispatcher.sh           # Main event router
├── event-replay.sh               # Event replay tool (NEW)
├── event-schema.json             # Event structure definition
├── lib/
│   ├── event-logger.sh           # Event logging utilities
│   └── event-validator.sh        # Event validation
├── handlers/
│   ├── on-worker-complete.sh     # Worker completion handler
│   ├── on-worker-failed.sh       # Worker failure handler
│   ├── on-worker-heartbeat.sh    # Worker heartbeat handler
│   ├── on-task-complete.sh       # Task completion handler
│   ├── on-task-failure.sh        # Task failure handler
│   ├── on-security-alert.sh      # Security event handler
│   ├── on-routing-decision.sh    # Routing decision handler
│   ├── on-learning-pattern.sh    # Learning pattern handler
│   ├── on-cleanup-needed.sh      # Cleanup trigger handler
│   └── on-health-alert.sh        # Health alert handler
├── test-event-flow.sh            # End-to-end tests
├── test-event-replay.sh          # Event replay tests (NEW)
├── README.md                     # This file
└── EVENT-REPLAY-QUICK-REF.md     # Quick reference (NEW)
```

## Event Flow

```
Event Source → event-logger.sh → Queue & JSONL logs
                                      ↓
                             event-dispatcher.sh
                                      ↓
                            Event Handler (handlers/*.sh)
                                      ↓
                                   Archive
                                      ↓
                          (Optional) event-replay.sh
```

## Quick Start

### 1. Create an Event

```bash
./scripts/events/lib/event-logger.sh --create \
    "worker.completed" \
    "my-worker" \
    '{"result": "success"}' \
    "my-task" \
    "medium"
```

### 2. Process Events

```bash
./scripts/events/event-dispatcher.sh
```

### 3. Replay Events (Debugging)

```bash
# Preview what happened
./scripts/events/event-replay.sh --date 2025-12-01 --dry-run --verbose

# Replay specific events
./scripts/events/event-replay.sh --type "worker.*" --date 2025-12-01
```

## Common Tasks

### Debug a Failed Event

```bash
# Find the event
cat coordination/events/worker-events.jsonl | jq 'select(.payload.status == "failed")'

# Replay it with verbose output
./scripts/events/event-replay.sh --event-id <event_id> --verbose
```

### Test Handler Changes

```bash
# Modify handler
vim scripts/events/handlers/on-worker-complete.sh

# Test with old events
./scripts/events/event-replay.sh --type "worker.completed" --date 2025-12-01 --dry-run
./scripts/events/event-replay.sh --type "worker.completed" --date 2025-12-01 --verbose
```

### Investigate Production Issue

```bash
# Replay events from incident timeframe
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --priority high \
    --verbose \
    2>&1 | tee incident-replay.log

# Analyze specific event type
./scripts/events/event-replay.sh \
    --type "security.*" \
    --date 2025-12-01 \
    --verbose
```

### Monitor Event Processing

```bash
# Watch live events
tail -f coordination/events/worker-events.jsonl | jq '.'

# Check queue depth
ls coordination/events/queue/*.json 2>/dev/null | wc -l

# View recent events
jq '.' coordination/events/worker-events.jsonl | tail -20
```

## Best Practices

1. **Always validate events** before logging
2. **Use correlation IDs** to trace related events
3. **Set appropriate priorities** (critical sparingly, high for important, medium default, low for info)
4. **Test with dry-run** before replaying events
5. **Use verbose mode** for debugging
6. **Archive old events** regularly to manage disk space
7. **Monitor queue depth** to detect processing issues

## Troubleshooting

### Events Not Processing

```bash
# Check queue
ls -la coordination/events/queue/

# Run dispatcher manually
./scripts/events/event-dispatcher.sh

# Check for errors
./scripts/events/event-dispatcher.sh 2>&1 | grep ERROR
```

### Invalid Events

```bash
# Validate event
./scripts/events/lib/event-validator.sh "$(cat event.json)"

# Check schema
cat scripts/events/event-schema.json
```

### Handler Failures

```bash
# Test handler directly
./scripts/events/handlers/on-worker-complete.sh event.json

# Check permissions
ls -l scripts/events/handlers/

# Replay with verbose
./scripts/events/event-replay.sh --event-id <id> --verbose
```

## Documentation

- **Architecture**: `/Users/ryandahlberg/Projects/cortex/docs/EVENT-DRIVEN-ARCHITECTURE.md`
- **Event Replay Guide**: `/Users/ryandahlberg/Projects/cortex/docs/EVENT-REPLAY-GUIDE.md`
- **Quick Start**: `/Users/ryandahlberg/Projects/cortex/docs/QUICK-START-EVENT-DRIVEN.md`
- **Quick Reference**: `EVENT-REPLAY-QUICK-REF.md`

## Support

For issues or questions:
- Run tests: `./test-event-flow.sh` or `./test-event-replay.sh`
- Check logs: `tail -f coordination/events/*.jsonl`
- Validate events: `./lib/event-validator.sh`
- Review documentation above

---

**Last Updated**: 2025-12-01
**Version**: 1.1.0 (Added event replay capability)
