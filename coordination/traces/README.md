# Distributed Tracing

This directory contains distributed tracing data for cortex multi-agent workflows.

## Directory Structure

```
traces/
├── daily/                          # Daily aggregated trace logs
│   └── YYYY-MM-DD.jsonl           # All traces for a given day
├── corr-*.jsonl                   # Individual trace files by correlation ID
└── README.md
```

## File Formats

### Individual Trace Files (corr-*.jsonl)

Each correlation ID gets its own file containing all trace events:

```json
{
  "correlation_id": "corr-1732741200-a3f4b2-coordinator",
  "span_id": "span-1732741201000-f4a3-task_started",
  "parent_span_id": null,
  "timestamp": "2025-11-27T12:00:01-06:00",
  "event_type": "task_lifecycle",
  "event_data": {
    "task_id": "task-123",
    "component": "coordinator",
    "action": "task_started"
  },
  "process_id": "12345",
  "hostname": "cortex-server"
}
```

### Daily Aggregated Files (daily/*.jsonl)

Same format, but all traces aggregated by date for easier querying.

## Correlation ID Format

`corr-{timestamp}-{random}-{component}`

- **timestamp**: Unix timestamp (10 digits) for temporal ordering
- **random**: 6-character hex for uniqueness
- **component**: Agent/master/worker identifier

Example: `corr-1732741200-a3f4b2-coordinator`

## Span ID Format

`span-{timestamp}-{random}-{operation}`

- **timestamp**: Unix timestamp with milliseconds (13 digits)
- **random**: 4-character hex for uniqueness
- **operation**: Operation name

Example: `span-1732741201000-f4a3-task_started`

## Event Types

- **task_lifecycle**: Task creation, assignment, completion
- **worker_lifecycle**: Worker spawning, execution, completion
- **handoff**: Cross-master handoffs
- **operation_start/operation_end**: Timed operations
- **span_completion**: Span finalization with outcome
- **log**: Significant log entries (WARN+)
- **metric**: Performance metrics
- **duration**: Operation timing

## Usage

### Bash Scripts

```bash
#!/bin/bash
source scripts/lib/correlation.sh
source scripts/lib/traced-logging.sh

# Initialize trace for a task
correlation_id=$(init_task_trace "task-123" "coordinator")

# Set trace context (automatically sets CORRELATION_ID, SPAN_ID, etc.)
set_trace_context "$correlation_id"

# Log with trace context
traced_log_info "Processing task" '{"task_id": "task-123"}'

# Emit custom trace event
emit_trace_event "custom_event" '{"key": "value"}'

# Complete the span
complete_trace_span "success" '{"result": "completed"}'
```

### For Worker Spawning

```bash
# Worker inherits parent's correlation ID
worker_correlation_id=$(init_worker_trace "worker-456" "$CORRELATION_ID")
set_trace_context "$worker_correlation_id" "$CORRELATION_ID"
```

### For Handoffs

```bash
# Handoff continues parent trace
init_handoff_trace "coordinator" "development" "$CORRELATION_ID"
propagate_to_file "$handoff_file" "$CORRELATION_ID" "$SPAN_ID"
```

## Viewing Traces

### List Recent Traces

```bash
./scripts/show-trace.sh --list
./scripts/show-trace.sh --list --limit 50
```

### Show Specific Trace

```bash
# Summary
./scripts/show-trace.sh --summary corr-1732741200-a3f4b2-coordinator

# Full details
./scripts/show-trace.sh corr-1732741200-a3f4b2-coordinator

# With logs and related traces
./scripts/show-trace.sh --verbose corr-1732741200-a3f4b2-coordinator

# JSON output
./scripts/show-trace.sh --json corr-1732741200-a3f4b2-coordinator
```

### Visualize Traces

```bash
# Timeline visualization
./scripts/visualize-trace.sh corr-1732741200-a3f4b2-coordinator

# Gantt chart
./scripts/visualize-trace.sh --gantt corr-1732741200-a3f4b2-coordinator

# Hierarchical tree
./scripts/visualize-trace.sh --tree corr-1732741200-a3f4b2-coordinator

# Sequence diagram
./scripts/visualize-trace.sh --sequence corr-1732741200-a3f4b2-coordinator

# Save to file
./scripts/visualize-trace.sh --gantt -o trace.txt corr-1732741200-a3f4b2-coordinator
```

## Query Examples

### Find all traces for a component

```bash
grep -l "coordinator" coordination/traces/corr-*.jsonl
```

### Get traces from today

```bash
cat coordination/traces/daily/$(date +%Y-%m-%d).jsonl | jq -s 'group_by(.correlation_id) | length'
```

### Find failed operations

```bash
cat coordination/traces/daily/*.jsonl | jq 'select(.event_data.status == "failed")'
```

### Average trace duration

```bash
for trace in coordination/traces/corr-*.jsonl; do
    jq -s '(.[0].timestamp | fromdateiso8601) as $start | (.[-1].timestamp | fromdateiso8601) as $end | $end - $start' "$trace"
done | jq -s 'add / length'
```

## Retention Policy

- Individual trace files: Keep for 7 days
- Daily aggregated files: Keep for 30 days
- Archive old traces to coordination/traces/archive/ before deletion

## Integration

See `INTEGRATION-POINTS.md` for where to add correlation IDs in existing code.
