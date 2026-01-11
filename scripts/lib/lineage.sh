#!/usr/bin/env bash
# scripts/lib/lineage.sh
# Task Lineage Tracking Library
# Provides complete observability of task lifecycle from creation to completion
#
# Usage:
#   source "$(dirname "$0")/lib/lineage.sh"
#   log_task_created "task-001" "user-ryan" '{"priority": "high"}'
#   log_task_assigned "task-001" "coordinator-master" "security-master"
#   log_worker_spawned "task-001" "security-master" "worker-scan-001" "scan-worker"
#   log_task_completed "task-001" "security-master" "success" '{"deliverables": ["report.json"]}'

set -euo pipefail

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Source environment library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/environment.sh" ]; then
    source "$SCRIPT_DIR/environment.sh"
fi

# Lineage storage directory (environment-aware)
if type get_lineage_dir &>/dev/null; then
    LINEAGE_DIR=$(get_lineage_dir)
else
    # Fallback for backwards compatibility
    LINEAGE_DIR="${CORTEX_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/coordination/lineage"
fi

# Schema is shared across environments
if [ -z "${CORTEX_HOME:-}" ]; then
    CORTEX_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
LINEAGE_SCHEMA="$CORTEX_HOME/coordination/schemas/task-lineage.schema.json"

# Version
LINEAGE_SCHEMA_VERSION="1.0.0"

# Ensure lineage directory exists
mkdir -p "$LINEAGE_DIR"

# ==============================================================================
# INTERNAL UTILITIES
# ==============================================================================

# Generate unique lineage ID based on timestamp
_generate_lineage_id() {
    local timestamp_s
    timestamp_s=$(date +%s)
    # Use seconds plus nanoseconds for uniqueness on macOS
    local nanos=$((RANDOM % 1000))
    echo "lineage-${timestamp_s}${nanos}"
}

# Get current ISO-8601 timestamp
_get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Write lineage event to JSONL file
# Args: $1=lineage_event_json
_write_lineage_event() {
    local event_json="$1"
    local lineage_file="$LINEAGE_DIR/task-lineage.jsonl"

    # Append to JSONL file (one JSON object per line)
    echo "$event_json" >> "$lineage_file"

    # Also write to dated file for archival
    local date_file="$LINEAGE_DIR/lineage-$(date +%Y-%m-%d).jsonl"
    echo "$event_json" >> "$date_file"
}

# Create base lineage event structure
# Args: $1=task_id, $2=event_type, $3=actor_type, $4=actor_id, $5=event_data_json, $6=parent_lineage_id(optional)
_create_lineage_event() {
    local task_id="$1"
    local event_type="$2"
    local actor_type="$3"
    local actor_id="$4"
    local event_data_json="${5-}"
    local parent_lineage_id="${6:-null}"

    # Handle empty or missing event_data
    if [ -z "$event_data_json" ]; then
        event_data_json="{}"
    fi

    local lineage_id
    lineage_id=$(_generate_lineage_id)

    local timestamp
    timestamp=$(_get_timestamp)

    # Get session context if available
    local session_id="${CORTEX_SESSION_ID:-}"
    local trace_id="${CORTEX_TRACE_ID:-}"
    local principal="${CORTEX_PRINCIPAL:-system}"

    # Build context object (compact JSON, no newlines)
    local context_json="{}"
    if [ -n "$session_id" ]; then
        context_json=$(echo "$context_json" | jq -c --arg sid "$session_id" '. + {session_id: $sid}')
    fi
    if [ -n "$trace_id" ]; then
        context_json=$(echo "$context_json" | jq -c --arg tid "$trace_id" '. + {trace_id: $tid}')
    fi

    # Build parent reference - handle as string arg, conditionally set as string or null
    local has_parent="false"
    if [ -n "$parent_lineage_id" ] && [ "$parent_lineage_id" != "null" ]; then
        has_parent="true"
    fi

    # Create the lineage event
    local lineage_event
    if [ "$has_parent" = "true" ]; then
        lineage_event=$(jq -n \
            --arg lid "$lineage_id" \
            --arg tid "$task_id" \
            --arg etype "$event_type" \
            --arg ts "$timestamp" \
            --arg atype "$actor_type" \
            --arg aid "$actor_id" \
            --arg principal "$principal" \
            --argjson edata "$event_data_json" \
            --argjson context "$context_json" \
            --arg parent "$parent_lineage_id" \
            --arg version "$LINEAGE_SCHEMA_VERSION" \
            '{
                lineage_id: $lid,
                task_id: $tid,
                event_type: $etype,
                timestamp: $ts,
                actor: {
                    type: $atype,
                    id: $aid,
                    principal: $principal
                },
                event_data: $edata,
                parent_lineage_id: $parent,
                context: $context,
                version: $version
            }')
    else
        lineage_event=$(jq -n \
            --arg lid "$lineage_id" \
            --arg tid "$task_id" \
            --arg etype "$event_type" \
            --arg ts "$timestamp" \
            --arg atype "$actor_type" \
            --arg aid "$actor_id" \
            --arg principal "$principal" \
            --argjson edata "$event_data_json" \
            --argjson context "$context_json" \
            --arg version "$LINEAGE_SCHEMA_VERSION" \
            '{
                lineage_id: $lid,
                task_id: $tid,
                event_type: $etype,
                timestamp: $ts,
                actor: {
                    type: $atype,
                    id: $aid,
                    principal: $principal
                },
                event_data: $edata,
                parent_lineage_id: null,
                context: $context,
                version: $version
            }')
    fi

    _write_lineage_event "$lineage_event"
    echo "$lineage_id"  # Return lineage_id for potential parent reference
}

# ==============================================================================
# PUBLIC API - TASK LIFECYCLE EVENTS
# ==============================================================================

# Log task creation event
# Args: $1=task_id, $2=creator_id, $3=event_data_json(optional)
# Example: log_task_created "task-001" "user-ryan" '{"priority": "high", "type": "security"}'
log_task_created() {
    local task_id="$1"
    local creator_id="$2"
    local event_data="${3-}"  # Use dash, not colon-dash to avoid double-appending
    if [ -z "$event_data" ]; then event_data="{}"; fi
    if [ -z "$event_data" ]; then
        event_data="{}"
    fi

    # Determine actor type from creator_id
    local actor_type="user"
    if [[ "$creator_id" =~ ^(coordinator|security|development|inventory|cicd)-master$ ]]; then
        actor_type="master"
    elif [[ "$creator_id" =~ daemon$ ]]; then
        actor_type="daemon"
    elif [[ "$creator_id" == "system" ]]; then
        actor_type="system"
    fi

    _create_lineage_event "$task_id" "task_created" "$actor_type" "$creator_id" "$event_data"
}

# Log task assignment to master
# Args: $1=task_id, $2=assigner_id, $3=master_id, $4=priority(optional)
# Example: log_task_assigned "task-001" "coordinator-master" "security-master" "high"
log_task_assigned() {
    local task_id="$1"
    local assigner_id="$2"
    local master_id="$3"
    local priority="${4:-medium}"

    local event_data
    event_data=$(jq -n \
        --arg mid "$master_id" \
        --arg prio "$priority" \
        '{master_id: $mid, priority: $prio}')

    _create_lineage_event "$task_id" "task_assigned" "coordinator" "$assigner_id" "$event_data"
}

# Log task started by master
# Args: $1=task_id, $2=master_id, $3=event_data_json(optional)
# Example: log_task_started "task-001" "security-master" '{}'
log_task_started() {
    local task_id="$1"
    local master_id="$2"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    _create_lineage_event "$task_id" "task_started" "master" "$master_id" "$event_data"
}

# Log worker spawning
# Args: $1=task_id, $2=master_id, $3=worker_id, $4=worker_type, $5=event_data_json(optional)
# Example: log_worker_spawned "task-001" "security-master" "worker-scan-001" "scan-worker" '{}'
log_worker_spawned() {
    local task_id="$1"
    local master_id="$2"
    local worker_id="$3"
    local worker_type="$4"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    # Merge worker info into event_data
    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg wid "$worker_id" \
        --arg wtype "$worker_type" \
        '. + {worker_id: $wid, worker_type: $wtype}')

    _create_lineage_event "$task_id" "worker_spawned" "master" "$master_id" "$merged_data"
}

# Log worker started execution
# Args: $1=task_id, $2=worker_id, $3=worker_type, $4=event_data_json(optional)
# Example: log_worker_started "task-001" "worker-scan-001" "scan-worker" '{}'
log_worker_started() {
    local task_id="$1"
    local worker_id="$2"
    local worker_type="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg wid "$worker_id" \
        --arg wtype "$worker_type" \
        '. + {worker_id: $wid, worker_type: $wtype}')

    _create_lineage_event "$task_id" "worker_started" "worker" "$worker_id" "$merged_data"
}

# Log worker progress update
# Args: $1=task_id, $2=worker_id, $3=progress_percentage, $4=event_data_json(optional)
# Example: log_worker_progress "task-001" "worker-scan-001" 45 '{"current_step": "scanning files"}'
log_worker_progress() {
    local task_id="$1"
    local worker_id="$2"
    local progress_percentage="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg wid "$worker_id" \
        --argjson prog "$progress_percentage" \
        '. + {worker_id: $wid, progress_percentage: $prog}')

    _create_lineage_event "$task_id" "worker_progress" "worker" "$worker_id" "$merged_data"
}

# Log worker completion
# Args: $1=task_id, $2=worker_id, $3=completion_status, $4=event_data_json(optional)
# Example: log_worker_completed "task-001" "worker-scan-001" "success" '{"deliverables": ["scan-report.json"], "token_usage": {"total_tokens": 5000}}'
log_worker_completed() {
    local task_id="$1"
    local worker_id="$2"
    local completion_status="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg wid "$worker_id" \
        --arg status "$completion_status" \
        '. + {worker_id: $wid, completion_status: $status}')

    _create_lineage_event "$task_id" "worker_completed" "worker" "$worker_id" "$merged_data"
}

# Log worker failure
# Args: $1=task_id, $2=worker_id, $3=error_message, $4=event_data_json(optional)
# Example: log_worker_failed "task-001" "worker-scan-001" "Timeout exceeded" '{"error_type": "timeout"}'
log_worker_failed() {
    local task_id="$1"
    local worker_id="$2"
    local error_message="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local error_details
    error_details=$(jq -n \
        --arg msg "$error_message" \
        '{error_type: "worker_failure", error_message: $msg}')

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg wid "$worker_id" \
        --argjson err "$error_details" \
        '. + {worker_id: $wid, error_details: $err}')

    _create_lineage_event "$task_id" "worker_failed" "worker" "$worker_id" "$merged_data"
}

# Log task completion
# Args: $1=task_id, $2=completer_id, $3=completion_status, $4=event_data_json(optional)
# Example: log_task_completed "task-001" "security-master" "success" '{"deliverables": ["report.json", "fixes.json"]}'
log_task_completed() {
    local task_id="$1"
    local completer_id="$2"
    local completion_status="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg status "$completion_status" \
        '. + {completion_status: $status}')

    _create_lineage_event "$task_id" "task_completed" "master" "$completer_id" "$merged_data"
}

# Log task failure
# Args: $1=task_id, $2=actor_id, $3=reason, $4=event_data_json(optional)
# Example: log_task_failed "task-001" "security-master" "All workers failed" '{}'
log_task_failed() {
    local task_id="$1"
    local actor_id="$2"
    local reason="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg reason "$reason" \
        '. + {reason: $reason}')

    _create_lineage_event "$task_id" "task_failed" "master" "$actor_id" "$merged_data"
}

# Log task blocked
# Args: $1=task_id, $2=actor_id, $3=reason, $4=event_data_json(optional)
# Example: log_task_blocked "task-001" "security-master" "Waiting for dependency task-000" '{}'
log_task_blocked() {
    local task_id="$1"
    local actor_id="$2"
    local reason="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg reason "$reason" \
        '. + {reason: $reason}')

    _create_lineage_event "$task_id" "task_blocked" "master" "$actor_id" "$merged_data"
}

# Log task unblocked
# Args: $1=task_id, $2=actor_id, $3=reason, $4=event_data_json(optional)
# Example: log_task_unblocked "task-001" "security-master" "Dependency completed" '{}'
log_task_unblocked() {
    local task_id="$1"
    local actor_id="$2"
    local reason="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg reason "$reason" \
        '. + {reason: $reason}')

    _create_lineage_event "$task_id" "task_unblocked" "master" "$actor_id" "$merged_data"
}

# Log task reassignment
# Args: $1=task_id, $2=from_master, $3=to_master, $4=reason, $5=event_data_json(optional)
# Example: log_task_reassigned "task-001" "security-master" "development-master" "Security scan completed" '{}'
log_task_reassigned() {
    local task_id="$1"
    local from_master="$2"
    local to_master="$3"
    local reason="$4"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg from "$from_master" \
        --arg to "$to_master" \
        --arg reason "$reason" \
        '. + {from_master: $from, to_master: $to, reason: $reason}')

    _create_lineage_event "$task_id" "task_reassigned" "coordinator" "coordinator-master" "$merged_data"
}

# Log task escalation
# Args: $1=task_id, $2=escalator_id, $3=reason, $4=event_data_json(optional)
# Example: log_task_escalated "task-001" "security-master" "Requires manual intervention" '{}'
log_task_escalated() {
    local task_id="$1"
    local escalator_id="$2"
    local reason="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg reason "$reason" \
        '. + {reason: $reason}')

    _create_lineage_event "$task_id" "task_escalated" "master" "$escalator_id" "$merged_data"
}

# Log task cancellation
# Args: $1=task_id, $2=canceller_id, $3=reason, $4=event_data_json(optional)
# Example: log_task_cancelled "task-001" "coordinator-master" "User requested cancellation" '{}'
log_task_cancelled() {
    local task_id="$1"
    local canceller_id="$2"
    local reason="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg reason "$reason" \
        '. + {reason: $reason}')

    _create_lineage_event "$task_id" "task_cancelled" "system" "$canceller_id" "$merged_data"
}

# ==============================================================================
# PUBLIC API - HANDOFF EVENTS
# ==============================================================================

# Log handoff creation
# Args: $1=task_id, $2=handoff_id, $3=from_master, $4=to_master, $5=event_data_json(optional)
# Example: log_handoff_created "task-001" "handoff-001" "security-master" "development-master" '{}'
log_handoff_created() {
    local task_id="$1"
    local handoff_id="$2"
    local from_master="$3"
    local to_master="$4"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg hid "$handoff_id" \
        --arg from "$from_master" \
        --arg to "$to_master" \
        '. + {handoff_id: $hid, from_master: $from, to_master: $to}')

    _create_lineage_event "$task_id" "handoff_created" "master" "$from_master" "$merged_data"
}

# Log handoff acceptance
# Args: $1=task_id, $2=handoff_id, $3=accepting_master, $4=event_data_json(optional)
# Example: log_handoff_accepted "task-001" "handoff-001" "development-master" '{}'
log_handoff_accepted() {
    local task_id="$1"
    local handoff_id="$2"
    local accepting_master="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg hid "$handoff_id" \
        '. + {handoff_id: $hid}')

    _create_lineage_event "$task_id" "handoff_accepted" "master" "$accepting_master" "$merged_data"
}

# Log handoff completion
# Args: $1=task_id, $2=handoff_id, $3=completing_master, $4=event_data_json(optional)
# Example: log_handoff_completed "task-001" "handoff-001" "development-master" '{"deliverables": ["fixes.json"]}'
log_handoff_completed() {
    local task_id="$1"
    local handoff_id="$2"
    local completing_master="$3"
    local event_data="${3-}"
    if [ -z "$event_data" ]; then event_data="{}"; fi

    local merged_data
    merged_data=$(echo "$event_data" | jq \
        --arg hid "$handoff_id" \
        '. + {handoff_id: $hid}')

    _create_lineage_event "$task_id" "handoff_completed" "master" "$completing_master" "$merged_data"
}

# ==============================================================================
# PUBLIC API - QUERY UTILITIES
# ==============================================================================

# Get all lineage events for a specific task
# Args: $1=task_id
# Example: get_task_lineage "task-001"
get_task_lineage() {
    local task_id="$1"
    local lineage_file="$LINEAGE_DIR/task-lineage.jsonl"

    if [ ! -f "$lineage_file" ]; then
        echo "[]"
        return
    fi

    jq -s --arg tid "$task_id" '[.[] | select(.task_id == $tid)]' "$lineage_file"
}

# Get lineage events by type
# Args: $1=event_type
# Example: get_lineage_by_type "worker_spawned"
get_lineage_by_type() {
    local event_type="$1"
    local lineage_file="$LINEAGE_DIR/task-lineage.jsonl"

    if [ ! -f "$lineage_file" ]; then
        echo "[]"
        return
    fi

    jq -s --arg etype "$event_type" '[.[] | select(.event_type == $etype)]' "$lineage_file"
}

# Get lineage events by actor
# Args: $1=actor_id
# Example: get_lineage_by_actor "security-master"
get_lineage_by_actor() {
    local actor_id="$1"
    local lineage_file="$LINEAGE_DIR/task-lineage.jsonl"

    if [ ! -f "$lineage_file" ]; then
        echo "[]"
        return
    fi

    jq -s --arg aid "$actor_id" '[.[] | select(.actor.id == $aid)]' "$lineage_file"
}

# Get lineage statistics
# Example: get_lineage_stats
get_lineage_stats() {
    local lineage_file="$LINEAGE_DIR/task-lineage.jsonl"

    if [ ! -f "$lineage_file" ]; then
        echo '{"total_events": 0, "event_types": {}, "actors": {}}'
        return
    fi

    jq -s '{
        total_events: length,
        event_types: (group_by(.event_type) | map({key: .[0].event_type, value: length}) | from_entries),
        actors: (group_by(.actor.id) | map({key: .[0].actor.id, value: length}) | from_entries),
        tasks_tracked: (map(.task_id) | unique | length)
    }' "$lineage_file"
}

# Export the functions (for bash compatibility)
export -f log_task_created
export -f log_task_assigned
export -f log_task_started
export -f log_worker_spawned
export -f log_worker_started
export -f log_worker_progress
export -f log_worker_completed
export -f log_worker_failed
export -f log_task_completed
export -f log_task_failed
export -f log_task_blocked
export -f log_task_unblocked
export -f log_task_reassigned
export -f log_task_escalated
export -f log_task_cancelled
export -f log_handoff_created
export -f log_handoff_accepted
export -f log_handoff_completed
export -f get_task_lineage
export -f get_lineage_by_type
export -f get_lineage_by_actor
export -f get_lineage_stats
