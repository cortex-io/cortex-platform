#!/usr/bin/env bash
# Event validator - validates events against schema

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVENTS_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA_FILE="$EVENTS_DIR/event-schema.json"

# Validate event structure
validate_event() {
    local event_json="$1"

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        echo "ERROR: jq is required for event validation" >&2
        return 1
    fi

    # Parse event
    if ! echo "$event_json" | jq empty 2>/dev/null; then
        echo "ERROR: Invalid JSON" >&2
        return 1
    fi

    # Check required fields
    local required_fields=("event_id" "event_type" "timestamp" "source")
    for field in "${required_fields[@]}"; do
        if ! echo "$event_json" | jq -e ".$field" > /dev/null 2>&1; then
            echo "ERROR: Missing required field: $field" >&2
            return 1
        fi
    done

    # Validate event_id format (evt_YYYYMMDD_HHMMSS_random)
    local event_id
    event_id=$(echo "$event_json" | jq -r '.event_id')
    if ! [[ "$event_id" =~ ^evt_[0-9]{8}_[0-9]{6}_[a-z0-9]+$ ]]; then
        echo "ERROR: Invalid event_id format: $event_id" >&2
        return 1
    fi

    # Validate timestamp is ISO 8601
    local timestamp
    timestamp=$(echo "$event_json" | jq -r '.timestamp')
    if ! date -jf "%Y-%m-%dT%H:%M:%S%z" "$timestamp" &>/dev/null 2>&1 && \
       ! date -d "$timestamp" &>/dev/null 2>&1; then
        echo "ERROR: Invalid timestamp format: $timestamp" >&2
        return 1
    fi

    # Validate event_type is recognized
    local event_type
    event_type=$(echo "$event_json" | jq -r '.event_type')
    local valid_types=(
        "worker.started" "worker.completed" "worker.failed" "worker.heartbeat"
        "task.created" "task.assigned" "task.completed" "task.failed"
        "security.scan_completed" "security.vulnerability_found"
        "routing.decision_made" "learning.pattern_detected" "learning.model_updated"
        "system.cleanup_needed" "system.health_alert"
        "daemon.started" "daemon.stopped"
    )

    local valid=false
    for type in "${valid_types[@]}"; do
        if [[ "$event_type" == "$type" ]]; then
            valid=true
            break
        fi
    done

    if [[ "$valid" != "true" ]]; then
        echo "ERROR: Invalid event_type: $event_type" >&2
        return 1
    fi

    echo "Event validation passed"
    return 0
}

# Generate event ID
generate_event_id() {
    local date_part
    local time_part
    local random_part

    date_part=$(date +%Y%m%d)
    time_part=$(date +%H%M%S)
    random_part=$(openssl rand -hex 6 2>/dev/null || cat /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | head -c 12)

    echo "evt_${date_part}_${time_part}_${random_part}"
}

# Main execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -eq 0 ]]; then
        echo "Usage: $0 <event_json>" >&2
        echo "   or: $0 --generate-id" >&2
        exit 1
    fi

    if [[ "$1" == "--generate-id" ]]; then
        generate_event_id
    else
        validate_event "$1"
    fi
fi
