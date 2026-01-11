# Event Replay Quick Reference

## Basic Usage

```bash
# Replay single event
./scripts/events/event-replay.sh --event-id evt_20251201_123456_abc123

# Replay date
./scripts/events/event-replay.sh --date 2025-12-01

# Dry run first
./scripts/events/event-replay.sh --date 2025-12-01 --dry-run

# Verbose output
./scripts/events/event-replay.sh --date 2025-12-01 --verbose
```

## Filters

```bash
# By type (regex)
--type "worker.*"           # All worker events
--type "security.*"         # All security events
--type "worker.failed"      # Specific type

# By source (regex)
--source "security-scanner"
--source "worker-.*-042"

# By priority
--priority critical
--priority high
--priority medium
--priority low

# By correlation ID
--correlation task-123
--correlation deploy-scan-001
```

## Common Commands

```bash
# Debug failed event
./scripts/events/event-replay.sh --event-id <id> --verbose

# Test handler changes
./scripts/events/event-replay.sh --type "worker.*" --date 2025-12-01 --dry-run

# Replay failed events
./scripts/events/event-replay.sh --date 2025-12-01 --queue

# Audit security events
./scripts/events/event-replay.sh --type "security.*" --date 2025-12-01 --verbose

# High priority events only
./scripts/events/event-replay.sh --priority high --date 2025-12-01

# Events for specific task
./scripts/events/event-replay.sh --correlation task-123 --date 2025-12-01
```

## Modes

```bash
# Direct invocation (default) - runs handlers immediately
./scripts/events/event-replay.sh --date 2025-12-01

# Re-queue - adds back to queue for dispatcher
./scripts/events/event-replay.sh --date 2025-12-01 --queue
```

## Combine Filters

```bash
# High priority worker failures
./scripts/events/event-replay.sh \
    --type "worker.failed" \
    --priority high \
    --date 2025-12-01

# Security events from specific scanner
./scripts/events/event-replay.sh \
    --type "security.*" \
    --source "security-scanner" \
    --date 2025-12-01
```

## Troubleshooting

```bash
# Event not found?
find coordination/events/archive -name "evt_*.json"

# Check available dates
ls -la coordination/events/archive/

# Validate event
./scripts/events/lib/event-validator.sh "$(cat event.json)"

# Test handler directly
./scripts/events/handlers/on-worker-complete.sh event.json
```

## Exit Codes

- `0` = Success
- `1` = Failure (check summary for details)

## Output

Look for the summary:
```
Total processed:  15
Successful:       13
Failed:           2
Skipped:          0
```
