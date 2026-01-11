#!/usr/bin/env bash
# scripts/lib/traced-logging.sh
# Logging with distributed tracing correlation context

# Prevent re-sourcing
if [ -n "${TRACED_LOGGING_LIB_LOADED:-}" ]; then
    return 0
fi
TRACED_LOGGING_LIB_LOADED=1

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/correlation.sh"

# Log directory
TRACED_LOG_DIR="${CORTEX_HOME:-$(pwd)}/coordination/logs/traced"
mkdir -p "$TRACED_LOG_DIR"

# Log levels
declare -r TLOG_LEVEL_DEBUG=0
declare -r TLOG_LEVEL_INFO=1
declare -r TLOG_LEVEL_WARN=2
declare -r TLOG_LEVEL_ERROR=3
declare -r TLOG_LEVEL_CRITICAL=4

# Current log level (default: INFO)
CORTEX_TRACED_LOG_LEVEL="${CORTEX_TRACED_LOG_LEVEL:-$TLOG_LEVEL_INFO}"

# Get log level number from string
get_traced_log_level_number() {
    local level=$(echo "$1" | tr '[:lower:]' '[:upper:]')
    case "$level" in
        DEBUG) echo $TLOG_LEVEL_DEBUG ;;
        INFO) echo $TLOG_LEVEL_INFO ;;
        WARN|WARNING) echo $TLOG_LEVEL_WARN ;;
        ERROR) echo $TLOG_LEVEL_ERROR ;;
        CRITICAL) echo $TLOG_LEVEL_CRITICAL ;;
        *) echo $TLOG_LEVEL_INFO ;;
    esac
}

# Main traced logging function
# Usage: traced_log <level> <message> [additional_context_json]
traced_log() {
    local level="$1"
    local message="$2"
    local additional_context="${3:-{}}"

    # Check if should log based on level
    local level_num=$(get_traced_log_level_number "$level")
    if [ "$level_num" -lt "$CORTEX_TRACED_LOG_LEVEL" ]; then
        return 0
    fi

    local timestamp=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")
    local pid=$$
    local level_upper=$(echo "$level" | tr '[:lower:]' '[:upper:]')

    # Get trace context
    local correlation_id="${CORRELATION_ID:-unknown}"
    local span_id="${SPAN_ID:-unknown}"
    local parent_span_id="${PARENT_SPAN_ID:-}"

    # Console output with colors and trace context
    local color=""
    case "$level_upper" in
        DEBUG) color="\033[0;36m" ;;    # Cyan
        INFO) color="\033[0;32m" ;;     # Green
        WARN) color="\033[0;33m" ;;     # Yellow
        ERROR) color="\033[0;31m" ;;    # Red
        CRITICAL) color="\033[1;31m" ;; # Bold Red
    esac
    local reset="\033[0m"
    local gray="\033[0;90m"

    # Format trace info for console
    local trace_info=""
    if [ "$correlation_id" != "unknown" ]; then
        local short_corr=$(echo "$correlation_id" | cut -d'-' -f2-3)
        trace_info=" ${gray}[trace:${short_corr}]${reset}"
    fi

    echo -e "${color}[$timestamp] $level_upper:${reset} $message${trace_info}" >&2

    # Structured JSONL log with full trace correlation
    local log_file="$TRACED_LOG_DIR/$(date +%Y-%m-%d).jsonl"

    # Build comprehensive JSON log entry
    local json_log=$(jq -nc \
        --arg ts "$timestamp" \
        --arg lvl "$level_upper" \
        --arg msg "$message" \
        --arg cid "$correlation_id" \
        --arg sid "$span_id" \
        --arg psid "$parent_span_id" \
        --arg pid "$pid" \
        --arg hostname "$(hostname)" \
        --argjson ctx "$additional_context" \
        '{
            timestamp: $ts,
            level: $lvl,
            message: $msg,
            trace_context: {
                correlation_id: $cid,
                span_id: $sid,
                parent_span_id: (if $psid != "" then $psid else null end)
            },
            process_id: $pid,
            hostname: $hostname,
            additional_context: $ctx
        }')

    echo "$json_log" >> "$log_file"

    # Emit trace event for significant logs
    if [ "$level_num" -ge "$TLOG_LEVEL_WARN" ] && [ "$correlation_id" != "unknown" ]; then
        local event_data=$(jq -nc \
            --arg lvl "$level_upper" \
            --arg msg "$message" \
            --argjson ctx "$additional_context" \
            '{
                log_level: $lvl,
                log_message: $msg,
                context: $ctx,
                action: "log_entry"
            }')

        emit_trace_event "log" "$event_data"
    fi

    # Send to dashboard if critical
    if [ "$level_num" -ge "$TLOG_LEVEL_ERROR" ]; then
        broadcast_traced_dashboard_event "system_$level_upper" "$message" "$correlation_id"
    fi
}

# Convenience logging functions with trace context
traced_log_debug() {
    traced_log "DEBUG" "$1" "${2:-{}}"
}

traced_log_info() {
    traced_log "INFO" "$1" "${2:-{}}"
}

traced_log_success() {
    traced_log "INFO" "✓ $1" "${2:-{}}"
}

traced_log_warn() {
    traced_log "WARN" "$1" "${2:-{}}"
}

traced_log_error() {
    traced_log "ERROR" "$1" "${2:-{}}"
}

traced_log_critical() {
    traced_log "CRITICAL" "$1" "${2:-{}}"
}

# Broadcast event to dashboard with trace context
broadcast_traced_dashboard_event() {
    local event_type="$1"
    local event_data="$2"
    local correlation_id="${3:-${CORRELATION_ID:-unknown}}"

    local event_file="${CORTEX_HOME:-$(pwd)}/coordination/dashboard-events.jsonl"

    if [ ! -w "$event_file" ]; then
        return 0
    fi

    local event_id="evt-$(date +%s)-$$"
    local timestamp=$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")

    local event=$(jq -nc \
        --arg id "$event_id" \
        --arg ts "$timestamp" \
        --arg type "$event_type" \
        --arg data "$event_data" \
        --arg cid "$correlation_id" \
        '{
            id: $id,
            timestamp: $ts,
            type: $type,
            data: $data,
            correlation_id: $cid,
            source: "traced_automation"
        }')

    echo "$event" >> "$event_file"
}

# Log section headers with trace context
traced_log_section() {
    local title="$1"
    local correlation_id="${CORRELATION_ID:-unknown}"

    traced_log_info ""
    traced_log_info "=========================================="
    traced_log_info "$title"
    if [ "$correlation_id" != "unknown" ]; then
        traced_log_info "Trace: $correlation_id"
    fi
    traced_log_info "=========================================="
}

# Log task lifecycle events
traced_log_task_event() {
    local task_id="$1"
    local event_type="$2"
    local event_details="${3:-{}}"

    local context=$(jq -nc \
        --arg tid "$task_id" \
        --arg evt "$event_type" \
        --argjson details "$event_details" \
        '{
            task_id: $tid,
            event_type: $evt,
            details: $details
        }')

    traced_log_info "Task $event_type: $task_id" "$context"

    # Also emit as trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "task_event" "$context"
    fi
}

# Log worker lifecycle events
traced_log_worker_event() {
    local worker_id="$1"
    local event_type="$2"
    local event_details="${3:-{}}"

    local context=$(jq -nc \
        --arg wid "$worker_id" \
        --arg evt "$event_type" \
        --argjson details "$event_details" \
        '{
            worker_id: $wid,
            event_type: $evt,
            details: $details
        }')

    traced_log_info "Worker $event_type: $worker_id" "$context"

    # Also emit as trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "worker_event" "$context"
    fi
}

# Log handoff events
traced_log_handoff_event() {
    local from_master="$1"
    local to_master="$2"
    local task_id="$3"
    local event_type="${4:-created}"

    local context=$(jq -nc \
        --arg from "$from_master" \
        --arg to "$to_master" \
        --arg tid "$task_id" \
        --arg evt "$event_type" \
        '{
            from_master: $from,
            to_master: $to,
            task_id: $tid,
            event_type: $evt
        }')

    traced_log_info "Handoff $event_type: $from_master -> $to_master (task: $task_id)" "$context"

    # Also emit as trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "handoff_event" "$context"
    fi
}

# Log performance metrics with trace context
traced_log_metric() {
    local metric_name="$1"
    local metric_value="$2"
    local metric_unit="${3:-}"

    local context=$(jq -nc \
        --arg name "$metric_name" \
        --arg value "$metric_value" \
        --arg unit "$metric_unit" \
        '{
            metric_name: $name,
            metric_value: $value,
            metric_unit: (if $unit != "" then $unit else null end)
        }')

    traced_log_debug "Metric: $metric_name = $metric_value $metric_unit" "$context"

    # Emit as trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "metric" "$context"
    fi
}

# Log duration of an operation
# Usage: traced_log_duration <operation_name> <start_timestamp> [end_timestamp]
traced_log_duration() {
    local operation="$1"
    local start_ts="$2"
    local end_ts="${3:-$(date +%s)}"

    local duration=$((end_ts - start_ts))

    local context=$(jq -nc \
        --arg op "$operation" \
        --arg dur "$duration" \
        --arg start "$start_ts" \
        --arg end "$end_ts" \
        '{
            operation: $op,
            duration_seconds: ($dur | tonumber),
            start_timestamp: ($start | tonumber),
            end_timestamp: ($end | tonumber)
        }')

    traced_log_info "Operation '$operation' took ${duration}s" "$context"

    # Emit as trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "duration" "$context"
    fi
}

# Create a traced operation scope
# Usage:
#   start_traced_operation <operation_name>
#   ... do work ...
#   end_traced_operation <operation_name> <status>

# Use temporary files instead of associative arrays for compatibility
TRACED_OPERATION_DIR="/tmp/cortex-traced-ops-$$"
mkdir -p "$TRACED_OPERATION_DIR"

start_traced_operation() {
    local operation="$1"
    local timestamp=$(date +%s)

    # Store start time in file
    echo "$timestamp" > "$TRACED_OPERATION_DIR/${operation}.start"

    local context=$(jq -nc \
        --arg op "$operation" \
        '{
            operation: $op,
            action: "started"
        }')

    traced_log_info "Starting operation: $operation" "$context"

    # Emit trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "operation_start" "$context"
    fi
}

end_traced_operation() {
    local operation="$1"
    local status="${2:-success}"
    local end_ts=$(date +%s)

    # Read start time from file
    local start_ts=$end_ts
    if [ -f "$TRACED_OPERATION_DIR/${operation}.start" ]; then
        start_ts=$(cat "$TRACED_OPERATION_DIR/${operation}.start")
        rm -f "$TRACED_OPERATION_DIR/${operation}.start"
    fi

    local duration=$((end_ts - start_ts))

    local context=$(jq -nc \
        --arg op "$operation" \
        --arg stat "$status" \
        --arg dur "$duration" \
        '{
            operation: $op,
            status: $stat,
            duration_seconds: ($dur | tonumber),
            action: "completed"
        }')

    traced_log_info "Completed operation: $operation (status: $status, duration: ${duration}s)" "$context"

    # Emit trace event
    if [ "${CORRELATION_ID:-unknown}" != "unknown" ]; then
        emit_trace_event "operation_end" "$context"
    fi
}

# Query logs by correlation ID
# Usage: query_logs_by_correlation <correlation_id> [log_level]
query_logs_by_correlation() {
    local correlation_id="$1"
    local log_level="${2:-}"

    local filter=".trace_context.correlation_id == \"$correlation_id\""
    if [ -n "$log_level" ]; then
        local level_upper=$(echo "$log_level" | tr '[:lower:]' '[:upper:]')
        filter="$filter and .level == \"$level_upper\""
    fi

    # Search all traced log files
    find "$TRACED_LOG_DIR" -name "*.jsonl" -type f | \
        xargs cat | \
        jq -s "map(select($filter)) | sort_by(.timestamp)"
}

# Get log summary for a correlation ID
# Usage: get_correlation_log_summary <correlation_id>
get_correlation_log_summary() {
    local correlation_id="$1"

    local logs=$(query_logs_by_correlation "$correlation_id")

    echo "$logs" | jq '{
        correlation_id: "'"$correlation_id"'",
        total_logs: length,
        by_level: (group_by(.level) | map({level: .[0].level, count: length})),
        first_log: (.[0] // null),
        last_log: (.[-1] // null),
        time_span: (
            if length > 0 then
                ((.[-1].timestamp | fromdateiso8601) - (.[0].timestamp | fromdateiso8601))
            else
                0
            end
        )
    }'
}
