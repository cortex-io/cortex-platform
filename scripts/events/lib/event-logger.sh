#!/usr/bin/env bash
# Event logger - writes events to JSONL files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source validator first (it sets its own EVENTS_DIR)
source "$SCRIPT_DIR/event-validator.sh"

# Override with correct paths after sourcing
EVENTS_DIR="$PROJECT_ROOT/coordination/events"
QUEUE_DIR="$EVENTS_DIR/queue"

# Log event to appropriate JSONL file
log_event() {
    local event_json="$1"

    # Validate event first
    if ! validate_event "$event_json"; then
        echo "ERROR: Event validation failed" >&2
        return 1
    fi

    # Extract event type to determine target file
    local event_type
    event_type=$(echo "$event_json" | jq -r '.event_type')

    # Determine target log file based on event type
    local log_file
    case "$event_type" in
        worker.*)
            log_file="$EVENTS_DIR/worker-events.jsonl"
            ;;
        task.*)
            log_file="$EVENTS_DIR/task-events.jsonl"
            ;;
        security.*)
            log_file="$EVENTS_DIR/security-events.jsonl"
            ;;
        routing.*)
            log_file="$EVENTS_DIR/routing-events.jsonl"
            ;;
        learning.*)
            log_file="$EVENTS_DIR/learning-events.jsonl"
            ;;
        system.*)
            log_file="$EVENTS_DIR/system-events.jsonl"
            ;;
        daemon.*)
            log_file="$EVENTS_DIR/daemon-events.jsonl"
            ;;
        *)
            log_file="$EVENTS_DIR/unknown-events.jsonl"
            ;;
    esac

    # Ensure directory exists
    mkdir -p "$EVENTS_DIR"

    # Append event to log file (compact JSON, one line)
    echo "$event_json" | jq -c '.' >> "$log_file"

    # Also write to queue for processing
    local event_id
    event_id=$(echo "$event_json" | jq -r '.event_id')
    local queue_file="$QUEUE_DIR/${event_id}.json"

    mkdir -p "$QUEUE_DIR"
    echo "$event_json" | jq '.' > "$queue_file"

    echo "Event logged: $event_id -> $log_file"
    return 0
}

# Create event helper
create_event() {
    local event_type="$1"
    local source="$2"
    local payload="$3"
    local correlation_id="${4:-}"
    local priority="${5:-medium}"

    local event_id
    event_id=$(generate_event_id)

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S%z")

    local event_json
    if [[ -n "$correlation_id" ]]; then
        event_json=$(jq -n \
            --arg id "$event_id" \
            --arg type "$event_type" \
            --arg ts "$timestamp" \
            --arg src "$source" \
            --arg corr "$correlation_id" \
            --arg prio "$priority" \
            --argjson payload "$payload" \
            '{
                event_id: $id,
                event_type: $type,
                timestamp: $ts,
                source: $src,
                correlation_id: $corr,
                metadata: {
                    priority: $prio
                },
                payload: $payload
            }')
    else
        event_json=$(jq -n \
            --arg id "$event_id" \
            --arg type "$event_type" \
            --arg ts "$timestamp" \
            --arg src "$source" \
            --arg prio "$priority" \
            --argjson payload "$payload" \
            '{
                event_id: $id,
                event_type: $type,
                timestamp: $ts,
                source: $src,
                metadata: {
                    priority: $prio
                },
                payload: $payload
            }')
    fi

    echo "$event_json"
}

# Main execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -ge 1 && "${1:-}" == "--create" ]]; then
        shift
        create_event "$@"
    elif [[ $# -ge 1 ]]; then
        log_event "$1"
    elif [[ ! -t 0 ]]; then
        # Read from stdin if piped
        event_json=$(cat)
        if [[ -n "$event_json" ]]; then
            log_event "$event_json"
        else
            echo "ERROR: Empty input from stdin" >&2
            exit 1
        fi
    else
        echo "Usage: $0 <event_json>" >&2
        echo "   or: $0 --create <event_type> <source> <payload_json> [correlation_id] [priority]" >&2
        echo "   or: echo '<event_json>' | $0" >&2
        exit 1
    fi
fi
