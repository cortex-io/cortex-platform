# Event Replay Guide

**Status**: ✅ Implemented
**Date**: 2025-12-01
**Script**: `/Users/ryandahlberg/Projects/cortex/scripts/events/event-replay.sh`

---

## Overview

The Event Replay tool allows you to replay archived events for debugging, testing, and incident investigation. This is essential for:

- Debugging failed event handlers
- Testing event processing logic
- Reproducing production issues
- Auditing event handling behavior
- Recovery from system failures

---

## Features

### 1. Single Event Replay
Replay a specific event by its ID:

```bash
./scripts/events/event-replay.sh --event-id evt_20251201_123456_abc123
```

### 2. Date-Based Replay
Replay all events from a specific date:

```bash
./scripts/events/event-replay.sh --date 2025-12-01
```

### 3. Filtered Replay

#### By Event Type
Replay only specific types of events using regex patterns:

```bash
# Replay all worker events
./scripts/events/event-replay.sh --type "worker.*" --date 2025-12-01

# Replay all security events
./scripts/events/event-replay.sh --type "security.*" --date 2025-12-01

# Replay specific event type
./scripts/events/event-replay.sh --type "worker.completed" --date 2025-12-01
```

#### By Source
Filter events by source component:

```bash
# Replay events from security scanner
./scripts/events/event-replay.sh --source "security-scanner" --date 2025-12-01

# Replay events from specific worker
./scripts/events/event-replay.sh --source "worker-.*-042" --date 2025-12-01
```

#### By Priority
Replay only events with specific priority:

```bash
# Replay critical events
./scripts/events/event-replay.sh --priority critical --date 2025-12-01

# Replay high priority events
./scripts/events/event-replay.sh --priority high --date 2025-12-01
```

#### By Correlation ID
Replay all events related to a specific task or operation:

```bash
# Replay all events for a task
./scripts/events/event-replay.sh --correlation task-123 --date 2025-12-01
```

### 4. Dry-Run Mode
Preview what would be replayed without executing:

```bash
./scripts/events/event-replay.sh --date 2025-12-01 --dry-run
```

### 5. Verbose Mode
Get detailed output for debugging:

```bash
./scripts/events/event-replay.sh --date 2025-12-01 --verbose
```

### 6. Replay Modes

#### Direct Invocation (Default)
Handlers are invoked immediately for instant execution:

```bash
./scripts/events/event-replay.sh --date 2025-12-01
```

#### Re-Queue Mode
Events are placed back in the queue for dispatcher processing:

```bash
./scripts/events/event-replay.sh --date 2025-12-01 --queue
```

---

## Usage Examples

### Example 1: Debug Failed Event

```bash
# Find the failed event ID from logs
cat coordination/events/worker-events.jsonl | jq 'select(.payload.status == "failed")'

# Replay with verbose output
./scripts/events/event-replay.sh \
    --event-id evt_20251201_093827_85c15a3d1640 \
    --verbose
```

### Example 2: Test Event Handler Changes

```bash
# After modifying on-worker-complete.sh, test with old events
./scripts/events/event-replay.sh \
    --type "worker.completed" \
    --date 2025-12-01 \
    --dry-run  # First verify what will be replayed

# Then run for real
./scripts/events/event-replay.sh \
    --type "worker.completed" \
    --date 2025-12-01 \
    --verbose
```

### Example 3: Reproduce Production Issue

```bash
# Replay all events from the incident timeframe
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --priority high \
    --verbose
```

### Example 4: Recover from Handler Failure

```bash
# Re-queue failed events for reprocessing
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --queue
```

### Example 5: Audit Security Events

```bash
# Replay all security events to verify handling
./scripts/events/event-replay.sh \
    --type "security.*" \
    --date 2025-12-01 \
    --dry-run \
    --verbose
```

### Example 6: Test Complete Task Flow

```bash
# Replay all events for a specific task
./scripts/events/event-replay.sh \
    --correlation task-security-scan-001 \
    --date 2025-12-01 \
    --verbose
```

### Example 7: Combine Multiple Filters

```bash
# Replay high-priority worker failures
./scripts/events/event-replay.sh \
    --type "worker.failed" \
    --priority high \
    --date 2025-12-01 \
    --verbose
```

---

## Command Reference

### Options

| Option | Argument | Description |
|--------|----------|-------------|
| `--event-id` | `<event_id>` | Replay specific event by ID |
| `--date` | `<YYYY-MM-DD>` | Replay all events from date |
| `--type` | `<regex>` | Filter by event type (e.g., "worker.*") |
| `--source` | `<regex>` | Filter by event source |
| `--priority` | `<level>` | Filter by priority (critical\|high\|medium\|low) |
| `--correlation` | `<id>` | Filter by correlation ID |
| `--dry-run` | - | Show what would be replayed without executing |
| `--verbose` | - | Enable verbose output |
| `--queue` | - | Re-queue instead of direct invocation |
| `--help` | - | Show help message |

### Required Arguments

- **Either** `--event-id` **or** `--date` must be specified
- All other options are optional

---

## Output Format

### Standard Output

```
[2025-12-01T15:00:00Z] [INFO] Event Replay Tool Starting...
[2025-12-01T15:00:01Z] [INFO] Replaying events from date: 2025-12-01
[2025-12-01T15:00:01Z] [INFO] Found 15 event(s) to process
[2025-12-01T15:00:02Z] [INFO] Replaying event: evt_20251201_093827_85c15a3d1640
[2025-12-01T15:00:02Z] [INFO]   Handler executed successfully
[2025-12-01T15:00:03Z] [INFO] Replaying event: evt_20251201_093829_6ea2dfaac986
[2025-12-01T15:00:03Z] [INFO]   Handler executed successfully

[2025-12-01T15:00:10Z] [INFO] =========================================
[2025-12-01T15:00:10Z] [INFO] Event Replay Summary
[2025-12-01T15:00:10Z] [INFO] =========================================
[2025-12-01T15:00:10Z] [INFO] Total processed:  15
[2025-12-01T15:00:10Z] [INFO] Successful:       13
[2025-12-01T15:00:10Z] [INFO] Failed:           2
[2025-12-01T15:00:10Z] [INFO] Skipped:          0
[2025-12-01T15:00:10Z] [INFO] =========================================
[2025-12-01T15:00:10Z] [INFO] Mode: DIRECT INVOCATION
```

### Verbose Output

```
[2025-12-01T15:00:00Z] [INFO] Event Replay Tool Starting...
[2025-12-01T15:00:00Z] [INFO] VERBOSE MODE: Enabled
[2025-12-01T15:00:01Z] [INFO] Replaying events from date: 2025-12-01
[2025-12-01T15:00:01Z] [VERBOSE] Searching for events in: coordination/events/archive/2025-12-01
[2025-12-01T15:00:01Z] [INFO] Found 15 event(s) to process
[2025-12-01T15:00:02Z] [INFO] Replaying event: evt_20251201_093827_85c15a3d1640
[2025-12-01T15:00:02Z] [VERBOSE]   Type: worker.completed
[2025-12-01T15:00:02Z] [VERBOSE]   Source: worker-implementation-042
[2025-12-01T15:00:02Z] [VERBOSE]   Priority: high
[2025-12-01T15:00:02Z] [VERBOSE]   Invoking handler: scripts/events/handlers/on-worker-complete.sh
[2025-12-01T15:00:03Z] [INFO]   Handler executed successfully
```

### Dry-Run Output

```
[2025-12-01T15:00:00Z] [INFO] Event Replay Tool Starting...
[2025-12-01T15:00:00Z] [INFO] DRY-RUN MODE: No events will be replayed
[2025-12-01T15:00:01Z] [INFO] Replaying events from date: 2025-12-01
[2025-12-01T15:00:01Z] [INFO] Found 15 event(s) to process
[2025-12-01T15:00:02Z] [INFO] Replaying event: evt_20251201_093827_85c15a3d1640
[2025-12-01T15:00:02Z] [INFO]   [DRY-RUN] Would replay this event

[2025-12-01T15:00:10Z] [INFO] =========================================
[2025-12-01T15:00:10Z] [INFO] Event Replay Summary
[2025-12-01T15:00:10Z] [INFO] =========================================
[2025-12-01T15:00:10Z] [INFO] Total processed:  15
[2025-12-01T15:00:10Z] [INFO] Successful:       15
[2025-12-01T15:00:10Z] [INFO] Failed:           0
[2025-12-01T15:00:10Z] [INFO] Skipped:          0
[2025-12-01T15:00:10Z] [INFO] =========================================
[2025-12-01T15:00:10Z] [INFO] Mode: DRY RUN (no events were actually replayed)
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - All events replayed successfully |
| 1 | Failure - One or more events failed to replay |

---

## Architecture

### Event Discovery

The replay tool searches for events in the archive directory:

```
coordination/events/archive/
├── 2025-12-01/
│   ├── evt_20251201_093827_*.json
│   └── evt_20251201_093829_*.json
├── failed/
│   └── evt_20251201_103000_*.json
└── invalid/
    └── evt_20251201_110000_*.json
```

### Replay Modes

#### 1. Direct Invocation (Default)

```
Event File → Validate → Check Filters → Invoke Handler → Report Result
```

Advantages:
- Immediate execution
- Real-time feedback
- No dispatcher needed
- Perfect for debugging

#### 2. Re-Queue Mode

```
Event File → Validate → Check Filters → Copy to Queue → Wait for Dispatcher
```

Advantages:
- Preserves normal processing flow
- Respects priority ordering
- Good for bulk recovery

### Handler Mapping

The replay tool uses the same handler mapping as the dispatcher:

| Event Type | Handler |
|------------|---------|
| `worker.completed` | `on-worker-complete.sh` |
| `worker.failed` | `on-worker-failed.sh` |
| `worker.heartbeat` | `on-worker-heartbeat.sh` |
| `task.completed` | `on-task-complete.sh` |
| `task.failed` | `on-task-failure.sh` |
| `security.*` | `on-security-alert.sh` |
| `routing.decision_made` | `on-routing-decision.sh` |
| `learning.pattern_detected` | `on-learning-pattern.sh` |
| `system.cleanup_needed` | `on-cleanup-needed.sh` |
| `system.health_alert` | `on-health-alert.sh` |

---

## Best Practices

### 1. Always Dry-Run First

Before replaying events, especially in production:

```bash
./scripts/events/event-replay.sh --date 2025-12-01 --dry-run
```

### 2. Use Verbose Mode for Debugging

When investigating issues:

```bash
./scripts/events/event-replay.sh \
    --event-id evt_20251201_093827_85c15a3d1640 \
    --verbose
```

### 3. Filter Aggressively

Replay only what you need:

```bash
# Bad: Replays everything
./scripts/events/event-replay.sh --date 2025-12-01

# Good: Replays only relevant events
./scripts/events/event-replay.sh \
    --type "worker.failed" \
    --priority high \
    --date 2025-12-01
```

### 4. Test Handler Changes

Before deploying handler changes:

```bash
# Replay a few test events
./scripts/events/event-replay.sh \
    --type "worker.completed" \
    --date 2025-12-01 \
    --dry-run

# Then test for real
./scripts/events/event-replay.sh \
    --type "worker.completed" \
    --date 2025-12-01 \
    --verbose
```

### 5. Document Replay Sessions

Keep a log of what you replay and why:

```bash
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --verbose \
    2>&1 | tee replay-session-$(date +%Y%m%d-%H%M%S).log
```

### 6. Use Correlation IDs

When debugging task flows:

```bash
# Find correlation ID from task
TASK_ID="task-security-scan-001"

# Replay all related events
./scripts/events/event-replay.sh \
    --correlation "$TASK_ID" \
    --date 2025-12-01 \
    --verbose
```

---

## Troubleshooting

### Problem: Event Not Found

```
[ERROR] Event not found: evt_20251201_123456_abc123
```

**Solution**: Check if the event exists in archive:

```bash
find coordination/events/archive -name "evt_20251201_123456_abc123.json"
```

### Problem: No Events for Date

```
[ERROR] No archived events found for date: 2025-12-01
```

**Solution**: Check available dates:

```bash
ls -la coordination/events/archive/
```

### Problem: Handler Not Executable

```
[ERROR] Handler not executable: scripts/events/handlers/on-worker-complete.sh
```

**Solution**: Make handler executable:

```bash
chmod +x scripts/events/handlers/on-worker-complete.sh
```

### Problem: Handler Fails During Replay

```
[ERROR] Handler failed
```

**Solution**: Run handler directly with verbose output:

```bash
# Extract event file
EVENT_FILE="coordination/events/archive/2025-12-01/evt_20251201_093827_*.json"

# Run handler directly
./scripts/events/handlers/on-worker-complete.sh "$EVENT_FILE"
```

### Problem: Invalid Event

```
[ERROR] Invalid event in file: evt_20251201_123456_abc123.json
```

**Solution**: Validate event structure:

```bash
./scripts/events/lib/event-validator.sh "$(cat $EVENT_FILE)"
```

---

## Common Workflows

### Workflow 1: Debug Handler Failure

1. Find failed event in logs
2. Replay with verbose output
3. Fix handler
4. Replay again to verify
5. Re-queue failed events

```bash
# Step 1: Find failed event
grep "Handler failed" /var/log/cortex-events.log

# Step 2: Replay with verbose
./scripts/events/event-replay.sh \
    --event-id evt_20251201_093827_85c15a3d1640 \
    --verbose

# Step 3: Fix handler
vim scripts/events/handlers/on-worker-complete.sh

# Step 4: Replay again
./scripts/events/event-replay.sh \
    --event-id evt_20251201_093827_85c15a3d1640 \
    --verbose

# Step 5: Re-queue all failed events
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --queue
```

### Workflow 2: Test Event Processing Changes

1. Dry-run to see what will be replayed
2. Replay with verbose output
3. Verify results
4. Deploy to production

```bash
# Step 1: Dry-run
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --dry-run

# Step 2: Replay
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --verbose

# Step 3: Verify
cat coordination/events/worker-events.jsonl | tail -20 | jq '.'

# Step 4: Deploy
git commit -am "feat: Improved event handler"
git push
```

### Workflow 3: Investigate Production Issue

1. Identify timeframe
2. Replay high priority events
3. Analyze logs
4. Replay specific event types
5. Document findings

```bash
# Step 1-2: Replay high priority events
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --priority high \
    --verbose \
    2>&1 | tee incident-replay.log

# Step 3: Analyze
grep ERROR incident-replay.log

# Step 4: Focus on specific type
./scripts/events/event-replay.sh \
    --type "security.*" \
    --date 2025-12-01 \
    --verbose

# Step 5: Document
echo "Incident Analysis: ..." >> incident-report.md
```

---

## Integration with Other Tools

### With Event Dispatcher

Replay events to queue, then process:

```bash
# Re-queue events
./scripts/events/event-replay.sh --date 2025-12-01 --queue

# Process queue
./scripts/events/event-dispatcher.sh
```

### With Event Logger

Create test events, then replay:

```bash
# Create test event
./scripts/events/lib/event-logger.sh --create \
    "worker.completed" \
    "test-worker" \
    '{"test": true}' \
    "test-task" \
    "low"

# Replay it
./scripts/events/event-replay.sh \
    --source "test-worker" \
    --date $(date +%Y-%m-%d) \
    --verbose
```

### With Monitoring

Track replay metrics:

```bash
# Replay with metrics
./scripts/events/event-replay.sh \
    --date 2025-12-01 \
    --verbose \
    2>&1 | tee /tmp/replay.log

# Extract metrics
grep "Total processed" /tmp/replay.log
grep "Successful" /tmp/replay.log
grep "Failed" /tmp/replay.log
```

---

## Advanced Usage

### Batch Replay Multiple Dates

```bash
#!/bin/bash
for date in 2025-11-28 2025-11-29 2025-11-30 2025-12-01; do
    echo "Replaying events from: $date"
    ./scripts/events/event-replay.sh \
        --date "$date" \
        --type "worker.failed" \
        --queue
done
```

### Conditional Replay

```bash
#!/bin/bash
# Replay only if failed events exist
if ls coordination/events/archive/failed/*.json 1> /dev/null 2>&1; then
    echo "Found failed events, replaying..."
    ./scripts/events/event-replay.sh \
        --date 2025-12-01 \
        --verbose
fi
```

### Custom Filter Script

```bash
#!/bin/bash
# Replay events with custom logic
for event in coordination/events/archive/2025-12-01/*.json; do
    # Custom filtering logic
    tokens=$(jq -r '.payload.tokens_used // 0' "$event")
    if [[ $tokens -gt 10000 ]]; then
        event_id=$(jq -r '.event_id' "$event")
        ./scripts/events/event-replay.sh --event-id "$event_id"
    fi
done
```

---

## Security Considerations

1. **Replay Side Effects**: Be aware that replaying events may trigger side effects (notifications, API calls, etc.)

2. **Data Sensitivity**: Archived events may contain sensitive data. Handle with care.

3. **Handler Permissions**: Ensure handlers have appropriate permissions for replay operations.

4. **Rate Limiting**: When replaying many events, consider rate limiting to avoid overwhelming external services.

---

## Performance

### Benchmarks

- **Single event replay**: ~100ms
- **Batch replay (100 events)**: ~10-15 seconds
- **Dry-run (1000 events)**: ~2-3 seconds

### Optimization Tips

1. Use filters to reduce events processed
2. Use `--dry-run` for validation without execution
3. Use `--queue` mode for bulk processing
4. Batch related events together

---

## Future Enhancements

- [ ] Event transformation during replay
- [ ] Replay to different environment
- [ ] Event mutation for testing
- [ ] Parallel replay for performance
- [ ] Replay session management
- [ ] Integration with CI/CD testing

---

## Support

For issues or questions:
- Run with `--verbose` for detailed output
- Check handler logs for errors
- Validate events with event-validator.sh
- Review event schema in event-schema.json

---

**Last Updated**: 2025-12-01
**Maintained By**: Cortex Team
**Script Location**: `/Users/ryandahlberg/Projects/cortex/scripts/events/event-replay.sh`
