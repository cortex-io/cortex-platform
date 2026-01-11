#!/usr/bin/env bash

###############################################################################
# Worker Heartbeat Library
#
# Purpose: Provides heartbeat functionality for workers to prove they're alive
# Usage: Source this file in worker scripts and call start_heartbeat
###############################################################################

# Configuration
HEARTBEAT_INTERVAL=120  # 2 minutes in seconds
HEARTBEAT_PID_FILE=""
WORKER_SPEC_FILE=""

# Get script directory for event logger
HEARTBEAT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME_HB="${CORTEX_HOME:-$(cd "$HEARTBEAT_SCRIPT_DIR/../.." && pwd)}"

# Load event logger if available
EVENT_LOGGER_HB="$HEARTBEAT_SCRIPT_DIR/../events/lib/event-logger.sh"
if [ -f "$EVENT_LOGGER_HB" ]; then
    source "$EVENT_LOGGER_HB"
    EVENTS_ENABLED_HB=true
else
    EVENTS_ENABLED_HB=false
fi

###############################################################################
# Start heartbeat background process
###############################################################################

start_heartbeat() {
    local worker_id="$1"
    local spec_file="$2"

    if [ -z "$worker_id" ] || [ -z "$spec_file" ]; then
        echo "[HEARTBEAT] Error: worker_id and spec_file required"
        return 1
    fi

    WORKER_SPEC_FILE="$spec_file"
    HEARTBEAT_PID_FILE="/tmp/heartbeat-${worker_id}.pid"

    echo "[HEARTBEAT] Starting heartbeat for $worker_id (every ${HEARTBEAT_INTERVAL}s)"

    # Launch background heartbeat process
    (
        while true; do
            # Update heartbeat timestamp in worker spec
            if [ -f "$WORKER_SPEC_FILE" ]; then
                local current_time=$(date +%Y-%m-%dT%H:%M:%S%z)

                # Update last_heartbeat field
                jq --arg time "$current_time" \
                   '.execution.last_heartbeat = $time' \
                   "$WORKER_SPEC_FILE" > "${WORKER_SPEC_FILE}.tmp" 2>/dev/null

                if [ -f "${WORKER_SPEC_FILE}.tmp" ]; then
                    mv "${WORKER_SPEC_FILE}.tmp" "$WORKER_SPEC_FILE"
                fi

                # Emit worker.heartbeat event (non-blocking)
                if [ "$EVENTS_ENABLED_HB" = true ]; then
                    (
                        local worker_type=$(jq -r '.worker_type' "$WORKER_SPEC_FILE" 2>/dev/null || echo "unknown")
                        local task_id=$(jq -r '.task_id' "$WORKER_SPEC_FILE" 2>/dev/null || echo "unknown")
                        local status=$(jq -r '.status' "$WORKER_SPEC_FILE" 2>/dev/null || echo "running")

                        EVENT_PAYLOAD=$(jq -n \
                            --arg worker_id "$worker_id" \
                            --arg worker_type "$worker_type" \
                            --arg task_id "$task_id" \
                            --arg status "$status" \
                            --arg timestamp "$current_time" \
                            '{
                                worker_id: $worker_id,
                                worker_type: $worker_type,
                                task_id: $task_id,
                                status: $status,
                                heartbeat_time: $timestamp
                            }')

                        EVENT_JSON=$("$EVENT_LOGGER_HB" --create "worker.heartbeat" "worker-heartbeat" "$EVENT_PAYLOAD" "$task_id" "low" 2>/dev/null)
                        if [ -n "$EVENT_JSON" ]; then
                            "$EVENT_LOGGER_HB" "$EVENT_JSON" 2>/dev/null || true
                        fi
                    ) &
                fi
            fi

            sleep $HEARTBEAT_INTERVAL
        done
    ) &

    # Save background process PID
    local heartbeat_pid=$!
    echo $heartbeat_pid > "$HEARTBEAT_PID_FILE"

    echo "[HEARTBEAT] Heartbeat process started (PID: $heartbeat_pid)"
}

###############################################################################
# Stop heartbeat (call on worker exit)
###############################################################################

stop_heartbeat() {
    if [ -f "$HEARTBEAT_PID_FILE" ]; then
        local heartbeat_pid=$(cat "$HEARTBEAT_PID_FILE")

        if ps -p "$heartbeat_pid" > /dev/null 2>&1; then
            kill "$heartbeat_pid" 2>/dev/null || true
            echo "[HEARTBEAT] Stopped heartbeat process"
        fi

        rm -f "$HEARTBEAT_PID_FILE"
    fi
}

###############################################################################
# Update progress message (optional - for detailed progress tracking)
###############################################################################

update_progress() {
    local progress_message="$1"

    if [ -f "$WORKER_SPEC_FILE" ]; then
        local current_time=$(date +%Y-%m-%dT%H:%M:%S%z)

        jq --arg time "$current_time" \
           --arg msg "$progress_message" \
           '.execution.last_heartbeat = $time | .execution.progress_message = $msg' \
           "$WORKER_SPEC_FILE" > "${WORKER_SPEC_FILE}.tmp" 2>/dev/null

        if [ -f "${WORKER_SPEC_FILE}.tmp" ]; then
            mv "${WORKER_SPEC_FILE}.tmp" "$WORKER_SPEC_FILE"
        fi
    fi
}

###############################################################################
# Ensure heartbeat is stopped on script exit
###############################################################################

trap stop_heartbeat EXIT SIGINT SIGTERM
