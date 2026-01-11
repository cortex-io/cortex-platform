# Trace Query Examples

This document provides example queries for analyzing distributed traces.

## Basic Queries

### List All Traces

```bash
./scripts/show-trace.sh --list

# Limit results
./scripts/show-trace.sh --list --limit 50

# JSON output
./scripts/show-trace.sh --list --json | jq '.'
```

### View Specific Trace

```bash
# Summary
./scripts/show-trace.sh --summary corr-1764281775-433e01-coordinator

# Full details
./scripts/show-trace.sh corr-1764281775-433e01-coordinator

# Verbose (includes logs and related traces)
./scripts/show-trace.sh --verbose corr-1764281775-433e01-coordinator

# JSON output
./scripts/show-trace.sh --json corr-1764281775-433e01-coordinator
```

## Advanced Queries

### Find Traces by Component

```bash
# Find all coordinator traces
grep -l "coordinator" coordination/traces/corr-*.jsonl | \
    xargs -n1 basename | sed 's/.jsonl//'

# Find all worker traces
grep -l "worker" coordination/traces/corr-*.jsonl | \
    xargs -n1 basename | sed 's/.jsonl//'

# Find specific worker type
grep -l "worker-scan" coordination/traces/corr-*.jsonl | \
    xargs -n1 basename | sed 's/.jsonl//'
```

### Find Traces by Event Type

```bash
# Find traces with handoffs
grep -l '"event_type":"handoff"' coordination/traces/corr-*.jsonl | \
    xargs -n1 basename | sed 's/.jsonl//'

# Find traces with failures
grep -l '"status":"failed"' coordination/traces/corr-*.jsonl | \
    xargs -n1 basename | sed 's/.jsonl//'

# Find traces with errors
grep -l '"event_type":"log"' coordination/traces/corr-*.jsonl | \
    grep -l '"log_level":"ERROR"' | \
    xargs -n1 basename | sed 's/.jsonl//'
```

### Find Traces by Time Range

```bash
# Traces from today
find coordination/traces -name "corr-*.jsonl" -mtime 0

# Traces from last hour
find coordination/traces -name "corr-*.jsonl" -mmin -60

# Traces from specific date
cat coordination/traces/daily/2025-11-27.jsonl | \
    jq -s 'group_by(.correlation_id) | map(.[0].correlation_id) | unique'
```

### Find Long-Running Traces

```bash
# Calculate duration for each trace
for trace in coordination/traces/corr-*.jsonl; do
    duration=$(jq -s '
        (.[0].timestamp | fromdateiso8601) as $start |
        (.[-1].timestamp | fromdateiso8601) as $end |
        $end - $start
    ' "$trace" 2>/dev/null || echo "0")

    if [ "$duration" != "null" ] && [ "$duration" -gt 60 ]; then
        echo "$(basename "$trace" .jsonl): ${duration}s"
    fi
done | sort -t: -k2 -rn
```

### Find Traces with High Event Count

```bash
# Count events per trace
for trace in coordination/traces/corr-*.jsonl; do
    count=$(wc -l < "$trace" | tr -d ' ')
    if [ "$count" -gt 10 ]; then
        echo "$(basename "$trace" .jsonl): $count events"
    fi
done | sort -t: -k2 -rn
```

## Programmatic Queries (Using Libraries)

### Query from Bash Script

```bash
#!/bin/bash
source scripts/lib/correlation.sh
source scripts/lib/traced-logging.sh

# Get trace summary
summary=$(get_trace_summary "corr-1764281775-433e01-coordinator")
echo "$summary" | jq '.event_count'

# List recent traces
traces=$(list_traces 10)
echo "$traces" | jq -r '.correlation_id'

# Query logs by correlation
logs=$(query_logs_by_correlation "corr-1764281775-433e01-coordinator")
echo "$logs" | jq 'length'
```

## Analysis Queries

### Average Trace Duration

```bash
# Calculate average duration across all traces
durations=()
for trace in coordination/traces/corr-*.jsonl; do
    duration=$(jq -s '
        (.[0].timestamp | fromdateiso8601) as $start |
        (.[-1].timestamp | fromdateiso8601) as $end |
        $end - $start
    ' "$trace" 2>/dev/null || echo "0")

    if [ "$duration" != "null" ] && [ "$duration" -gt 0 ]; then
        durations+=("$duration")
    fi
done

# Calculate average
if [ ${#durations[@]} -gt 0 ]; then
    avg=$(printf '%s\n' "${durations[@]}" | jq -s 'add / length')
    echo "Average trace duration: ${avg}s"
fi
```

### Event Type Distribution

```bash
# Count events by type across all traces
cat coordination/traces/corr-*.jsonl | \
    jq -r '.event_type' | \
    sort | uniq -c | sort -rn
```

### Most Active Components

```bash
# Count traces by component
for trace in coordination/traces/corr-*.jsonl; do
    basename "$trace" .jsonl | awk -F'-' '{print $NF}'
done | sort | uniq -c | sort -rn
```

### Success Rate by Component

```bash
# Calculate success rate for each component
for component in coordinator security development inventory cicd; do
    total=$(grep -l "$component" coordination/traces/corr-*.jsonl | wc -l | tr -d ' ')

    if [ "$total" -gt 0 ]; then
        success=$(grep -l "$component" coordination/traces/corr-*.jsonl | \
            xargs grep -l '"status":"success"' 2>/dev/null | wc -l | tr -d ' ')

        rate=$(echo "scale=2; $success * 100 / $total" | bc)
        echo "$component: ${rate}% success ($success/$total)"
    fi
done
```

### Trace Relationship Analysis

```bash
# Find parent-child relationships
correlation_id="corr-1764281775-433e01-coordinator"

# Find all child traces
grep -l "parent_correlation_id.*$correlation_id" coordination/traces/corr-*.jsonl | \
    xargs -n1 basename | sed 's/.jsonl//'

# Find parent trace
parent=$(cat "coordination/traces/${correlation_id}.jsonl" | \
    jq -r 'select(.event_data.parent_correlation_id) | .event_data.parent_correlation_id' | \
    head -1)

if [ -n "$parent" ]; then
    echo "Parent trace: $parent"
fi
```

## Performance Metrics Queries

### Extract All Metrics

```bash
# Get all metrics from a trace
cat "coordination/traces/corr-1764281775-433e01-coordinator.jsonl" | \
    jq 'select(.event_type == "metric") | {
        metric_name: .event_data.metric_name,
        metric_value: .event_data.metric_value,
        metric_unit: .event_data.metric_unit,
        timestamp: .timestamp
    }'
```

### Average Metric Value

```bash
# Calculate average for a specific metric
metric_name="scan_duration"

cat coordination/traces/corr-*.jsonl | \
    jq -s "
        map(select(.event_type == \"metric\" and .event_data.metric_name == \"$metric_name\")) |
        map(.event_data.metric_value | tonumber) |
        if length > 0 then add / length else 0 end
    "
```

### Operation Duration Summary

```bash
# Get duration of all operations
cat coordination/traces/corr-*.jsonl | \
    jq -s '
        map(select(.event_type == "operation_end")) |
        group_by(.event_data.operation) |
        map({
            operation: .[0].event_data.operation,
            avg_duration: (map(.event_data.duration_seconds | tonumber) | add / length),
            count: length
        })
    '
```

## Debugging Queries

### Find Failed Operations

```bash
# Find all failed operations
cat coordination/traces/corr-*.jsonl | \
    jq 'select(.event_type == "operation_end" and .event_data.status == "failed") | {
        correlation_id,
        operation: .event_data.operation,
        timestamp
    }'
```

### Find Error Logs

```bash
# Extract all error logs
cat coordination/logs/traced/*.jsonl | \
    jq 'select(.level == "ERROR" or .level == "CRITICAL") | {
        correlation_id: .trace_context.correlation_id,
        message,
        timestamp,
        additional_context
    }'
```

### Trace Error Propagation

```bash
# Find errors and their child traces
correlation_id="corr-with-error-123"

# Get error
cat "coordination/traces/${correlation_id}.jsonl" | \
    jq 'select(.event_type == "log" and .event_data.log_level == "ERROR")'

# Find child traces that might be affected
grep -l "parent_correlation_id.*$correlation_id" coordination/traces/corr-*.jsonl
```

## Daily Reports

### Daily Trace Summary

```bash
# Summary for today
today=$(date +%Y-%m-%d)

if [ -f "coordination/traces/daily/${today}.jsonl" ]; then
    cat "coordination/traces/daily/${today}.jsonl" | jq -s '
        group_by(.correlation_id) as $traces |
        {
            date: "'"$today"'",
            total_traces: ($traces | length),
            total_events: length,
            event_types: (group_by(.event_type) | map({type: .[0].event_type, count: length})),
            components: (group_by(.correlation_id | split("-") | last) | map({component: .[0].correlation_id | split("-") | last, count: length}))
        }
    '
fi
```

### Top 10 Longest Traces Today

```bash
today=$(date +%Y-%m-%d)

cat "coordination/traces/daily/${today}.jsonl" | \
    jq -s '
        group_by(.correlation_id) |
        map({
            correlation_id: .[0].correlation_id,
            duration: (((.[-1].timestamp | fromdateiso8601) - (.[0].timestamp | fromdateiso8601))),
            event_count: length
        }) |
        sort_by(.duration) |
        reverse |
        .[0:10]
    '
```

## Export and Reporting

### Export Trace to JSON

```bash
# Export full trace with metadata
correlation_id="corr-1764281775-433e01-coordinator"

jq -s '{
    correlation_id: "'"$correlation_id"'",
    exported_at: (now | todate),
    summary: {
        event_count: length,
        start_time: .[0].timestamp,
        end_time: .[-1].timestamp,
        duration: (((.[-1].timestamp | fromdateiso8601) - (.[0].timestamp | fromdateiso8601)))
    },
    events: .
}' "coordination/traces/${correlation_id}.jsonl" > "trace-export-${correlation_id}.json"
```

### Generate CSV Report

```bash
# Export trace events to CSV
echo "timestamp,event_type,span_id,action" > trace-report.csv

cat coordination/traces/corr-*.jsonl | \
    jq -r '[.timestamp, .event_type, .span_id, (.event_data.action // "N/A")] | @csv' \
    >> trace-report.csv
```

## Cleanup Queries

### Find Old Traces (>7 days)

```bash
# List traces older than 7 days
find coordination/traces -name "corr-*.jsonl" -mtime +7
```

### Archive Old Traces

```bash
# Archive traces older than 7 days
mkdir -p coordination/traces/archive
find coordination/traces -maxdepth 1 -name "corr-*.jsonl" -mtime +7 \
    -exec mv {} coordination/traces/archive/ \;
```

### Clean Up Daily Logs (>30 days)

```bash
# Remove daily logs older than 30 days
find coordination/traces/daily -name "*.jsonl" -mtime +30 -delete
```
