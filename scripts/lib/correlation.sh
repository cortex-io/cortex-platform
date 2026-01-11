#!/usr/bin/env bash
# scripts/lib/correlation.sh
# Correlation ID generation and propagation for distributed tracing

# Prevent re-sourcing
if [ -n "${CORRELATION_LIB_LOADED:-}" ]; then
    return 0
fi
CORRELATION_LIB_LOADED=1

# Correlation ID format: corr-{timestamp}-{random}-{component}
# Example: corr-1732741200-a3f4b2-coordinator
# - timestamp: Unix timestamp for temporal ordering
# - random: 6-char hex for uniqueness
# - component: agent/master/worker identifier

# Generate a new correlation ID
# Usage: generate_correlation_id <component_name>
# Returns: correlation ID string
generate_correlation_id() {
    local component="${1:-unknown}"
    local timestamp=$(date +%s)
    local random=$(openssl rand -hex 3 2>/dev/null || echo "$(printf '%06x' $RANDOM)")

    echo "corr-${timestamp}-${random}-${component}"
}

# Generate a span ID for a specific operation within a trace
# Usage: generate_span_id <operation_name>
# Returns: span ID string
generate_span_id() {
    local operation="${1:-op}"
    # Use seconds + nanoseconds for better precision on macOS
    local timestamp=$(date +%s)
    local nanos=$(echo $((RANDOM % 1000)) | awk '{printf "%03d", $1}')
    local random=$(openssl rand -hex 2 2>/dev/null || echo "$(printf '%04x' $RANDOM)")

    echo "span-${timestamp}${nanos}-${random}-${operation}"
}

# Extract component name from correlation ID
# Usage: get_correlation_component <correlation_id>
extract_correlation_component() {
    local corr_id="$1"
    echo "$corr_id" | awk -F'-' '{print $NF}'
}

# Extract timestamp from correlation ID
# Usage: get_correlation_timestamp <correlation_id>
extract_correlation_timestamp() {
    local corr_id="$1"
    echo "$corr_id" | awk -F'-' '{print $2}'
}

# Set trace context environment variables
# Usage: set_trace_context <correlation_id> [parent_span_id]
set_trace_context() {
    local correlation_id="$1"
    local parent_span_id="${2:-}"

    export CORRELATION_ID="$correlation_id"
    export TRACE_ID="$correlation_id"  # Alias for compatibility
    export PARENT_SPAN_ID="$parent_span_id"

    # Generate span ID for current operation
    local component=$(extract_correlation_component "$correlation_id")
    export SPAN_ID=$(generate_span_id "$component")
}

# Clear trace context
# Usage: clear_trace_context
clear_trace_context() {
    unset CORRELATION_ID
    unset TRACE_ID
    unset SPAN_ID
    unset PARENT_SPAN_ID
}

# Get current trace context as JSON
# Usage: get_trace_context_json
get_trace_context_json() {
    jq -n \
        --arg cid "${CORRELATION_ID:-}" \
        --arg sid "${SPAN_ID:-}" \
        --arg psid "${PARENT_SPAN_ID:-}" \
        '{
            correlation_id: (if $cid != "" then $cid else null end),
            span_id: (if $sid != "" then $sid else null end),
            parent_span_id: (if $psid != "" then $psid else null end)
        }'
}

# Propagate correlation ID to a coordination file
# Usage: propagate_to_file <file_path> <correlation_id> [span_id] [parent_span_id]
propagate_to_file() {
    local file_path="$1"
    local correlation_id="$2"
    local span_id="${3:-}"
    local parent_span_id="${4:-}"

    if [ ! -f "$file_path" ]; then
        return 1
    fi

    local temp_file=$(mktemp)

    # Add trace context to JSON file
    jq \
        --arg cid "$correlation_id" \
        --arg sid "$span_id" \
        --arg psid "$parent_span_id" \
        '. + {
            trace_context: {
                correlation_id: $cid,
                span_id: (if $sid != "" then $sid else null end),
                parent_span_id: (if $psid != "" then $psid else null end),
                propagated_at: (now | todate)
            }
        }' \
        "$file_path" > "$temp_file"

    if [ $? -eq 0 ]; then
        mv "$temp_file" "$file_path"
        return 0
    else
        rm -f "$temp_file"
        return 1
    fi
}

# Extract correlation ID from a coordination file
# Usage: extract_from_file <file_path>
extract_from_file() {
    local file_path="$1"

    if [ ! -f "$file_path" ]; then
        return 1
    fi

    jq -r '.trace_context.correlation_id // .correlation_id // empty' "$file_path"
}

# Create a trace event and log it
# Usage: emit_trace_event <event_type> <event_data_json>
emit_trace_event() {
    local event_type="$1"
    local event_data="${2:-{}}"

    local correlation_id="${CORRELATION_ID:-unknown}"
    local span_id="${SPAN_ID:-unknown}"
    local parent_span_id="${PARENT_SPAN_ID:-}"
    local timestamp=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

    # Create trace directory if it doesn't exist
    local trace_dir="${CORTEX_HOME:-$(pwd)}/coordination/traces"
    mkdir -p "$trace_dir"

    # Store trace events by correlation ID
    local trace_file="$trace_dir/${correlation_id}.jsonl"

    # Create trace event
    local trace_event=$(jq -nc \
        --arg cid "$correlation_id" \
        --arg sid "$span_id" \
        --arg psid "$parent_span_id" \
        --arg ts "$timestamp" \
        --arg type "$event_type" \
        --argjson data "$event_data" \
        --arg pid "$$" \
        --arg hostname "$(hostname)" \
        '{
            correlation_id: $cid,
            span_id: $sid,
            parent_span_id: (if $psid != "" then $psid else null end),
            timestamp: $ts,
            event_type: $type,
            event_data: $data,
            process_id: $pid,
            hostname: $hostname
        }')

    echo "$trace_event" >> "$trace_file"

    # Also write to daily trace log for aggregation
    local daily_trace_file="$trace_dir/daily/$(date +%Y-%m-%d).jsonl"
    mkdir -p "$trace_dir/daily"
    echo "$trace_event" >> "$daily_trace_file"
}

# Initialize trace for a new task
# Usage: init_task_trace <task_id> <component> [parent_correlation_id]
init_task_trace() {
    local task_id="$1"
    local component="$2"
    local parent_correlation_id="${3:-}"

    # Generate new correlation ID
    local correlation_id=$(generate_correlation_id "$component")

    # Set trace context
    if [ -n "$parent_correlation_id" ]; then
        # Extract parent span for continuation
        set_trace_context "$correlation_id" "$parent_correlation_id"
    else
        set_trace_context "$correlation_id"
    fi

    # Emit task initialization event
    local event_data=$(jq -nc \
        --arg tid "$task_id" \
        --arg comp "$component" \
        --arg parent "$parent_correlation_id" \
        '{
            task_id: $tid,
            component: $comp,
            parent_correlation_id: (if $parent != "" then $parent else null end),
            action: "task_started"
        }')

    emit_trace_event "task_lifecycle" "$event_data"

    echo "$correlation_id"
}

# Initialize trace for a worker spawn
# Usage: init_worker_trace <worker_id> <parent_correlation_id>
init_worker_trace() {
    local worker_id="$1"
    local parent_correlation_id="$2"

    # Generate correlation ID for worker
    local correlation_id=$(generate_correlation_id "worker-${worker_id}")

    # Set trace context with parent
    set_trace_context "$correlation_id" "$parent_correlation_id"

    # Emit worker spawn event
    local event_data=$(jq -nc \
        --arg wid "$worker_id" \
        --arg parent "$parent_correlation_id" \
        '{
            worker_id: $wid,
            parent_correlation_id: $parent,
            action: "worker_spawned"
        }')

    emit_trace_event "worker_lifecycle" "$event_data"

    echo "$correlation_id"
}

# Initialize trace for a handoff
# Usage: init_handoff_trace <from_master> <to_master> <parent_correlation_id>
init_handoff_trace() {
    local from_master="$1"
    local to_master="$2"
    local parent_correlation_id="$3"

    # Continue with parent correlation ID
    set_trace_context "$parent_correlation_id"

    # Emit handoff event
    local event_data=$(jq -nc \
        --arg from "$from_master" \
        --arg to "$to_master" \
        '{
            from_master: $from,
            to_master: $to,
            action: "handoff_created"
        }')

    emit_trace_event "handoff" "$event_data"
}

# Complete a trace span
# Usage: complete_trace_span <outcome> <result_data_json>
complete_trace_span() {
    local outcome="$1"
    local result_data="${2:-{}}"

    local event_data=$(jq -nc \
        --arg outcome "$outcome" \
        --argjson data "$result_data" \
        '{
            outcome: $outcome,
            result: $data,
            action: "span_completed"
        }')

    emit_trace_event "span_completion" "$event_data"
}

# Get trace summary for a correlation ID
# Usage: get_trace_summary <correlation_id>
get_trace_summary() {
    local correlation_id="$1"
    local trace_dir="${CORTEX_HOME:-$(pwd)}/coordination/traces"
    local trace_file="$trace_dir/${correlation_id}.jsonl"

    if [ ! -f "$trace_file" ]; then
        echo "{\"error\": \"Trace not found for correlation_id: $correlation_id\"}"
        return 1
    fi

    # Aggregate trace events
    jq -s '{
        correlation_id: .[0].correlation_id,
        start_time: .[0].timestamp,
        end_time: .[-1].timestamp,
        event_count: length,
        events: .
    }' "$trace_file"
}

# List all traces
# Usage: list_traces [limit]
list_traces() {
    local limit="${1:-20}"
    local trace_dir="${CORTEX_HOME:-$(pwd)}/coordination/traces"

    find "$trace_dir" -maxdepth 1 -name "corr-*.jsonl" -type f | \
        while read -r trace_file; do
            local correlation_id=$(basename "$trace_file" .jsonl)
            local event_count=$(wc -l < "$trace_file" | tr -d ' ')
            local first_event=$(head -n1 "$trace_file")
            local last_event=$(tail -n1 "$trace_file")

            local start_time=$(echo "$first_event" | jq -r '.timestamp')
            local end_time=$(echo "$last_event" | jq -r '.timestamp')

            jq -nc \
                --arg cid "$correlation_id" \
                --arg start "$start_time" \
                --arg end "$end_time" \
                --arg count "$event_count" \
                '{
                    correlation_id: $cid,
                    start_time: $start,
                    end_time: $end,
                    event_count: ($count | tonumber)
                }'
        done | jq -s "sort_by(.start_time) | reverse | limit($limit; .[])"
}
