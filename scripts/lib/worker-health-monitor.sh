#!/usr/bin/env bash
# Worker Health Monitor
# Phase 1: Foundation & Observability
# Monitors and tracks health metrics for all active workers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Health metrics storage
HEALTH_METRICS_FILE="$CORTEX_HOME/coordination/worker-health-metrics.jsonl"
WORKER_POOL_FILE="$CORTEX_HOME/coordination/worker-pool.json"

# Ensure files exist
mkdir -p "$(dirname "$HEALTH_METRICS_FILE")"
touch "$HEALTH_METRICS_FILE"

##############################################################################
# collect_worker_health: Collect health metrics for a worker
# Args:
#   $1: worker_id
#   $2: status (active|idle|busy|failed|completed)
#   $3: cpu_usage (0-100, optional)
#   $4: memory_mb (optional)
#   $5: task_id (optional)
##############################################################################
collect_worker_health() {
    local worker_id="$1"
    local status="$2"
    local cpu_usage="${3:-0}"
    local memory_mb="${4:-0}"
    local task_id="${5:-none}"

    local timestamp=$(date -Iseconds)
    local uptime_seconds=0

    # Calculate uptime if worker exists in pool
    if [ -f "$WORKER_POOL_FILE" ]; then
        local created_at=$(jq -r ".workers[] | select(.worker_id == \"$worker_id\") | .created_at // \"\"" "$WORKER_POOL_FILE" 2>/dev/null || echo "")
        if [ -n "$created_at" ] && [ "$created_at" != "null" ]; then
            local created_timestamp=$(date -d "$created_at" +%s 2>/dev/null || echo "0")
            local current_timestamp=$(date +%s)
            uptime_seconds=$((current_timestamp - created_timestamp))
        fi
    fi

    # Get worker type and master
    local worker_type=$(jq -r ".workers[] | select(.worker_id == \"$worker_id\") | .worker_type // \"unknown\"" "$WORKER_POOL_FILE" 2>/dev/null || echo "unknown")
    local master=$(jq -r ".workers[] | select(.worker_id == \"$worker_id\") | .master // \"unknown\"" "$WORKER_POOL_FILE" 2>/dev/null || echo "unknown")

    # Determine health status
    local health_status="healthy"
    if [ "$status" = "failed" ]; then
        health_status="unhealthy"
    elif [ "$status" = "busy" ] && [ "$uptime_seconds" -gt 3600 ]; then
        health_status="degraded"  # Worker busy for over 1 hour
    elif [ "$cpu_usage" -gt 90 ]; then
        health_status="degraded"
    fi

    # Create health metric entry
    local health_entry=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg worker_id "$worker_id" \
        --arg worker_type "$worker_type" \
        --arg master "$master" \
        --arg status "$status" \
        --arg health_status "$health_status" \
        --arg task_id "$task_id" \
        --argjson cpu_usage "$cpu_usage" \
        --argjson memory_mb "$memory_mb" \
        --argjson uptime_seconds "$uptime_seconds" \
        '{
            timestamp: $timestamp,
            worker_id: $worker_id,
            worker_type: $worker_type,
            assigned_master: $master,
            status: $status,
            health: {
                status: $health_status,
                uptime_seconds: $uptime_seconds,
                uptime_human: (
                    if $uptime_seconds < 60 then "\($uptime_seconds)s"
                    elif $uptime_seconds < 3600 then "\($uptime_seconds / 60 | floor)m"
                    else "\($uptime_seconds / 3600 | floor)h \(($uptime_seconds % 3600) / 60 | floor)m"
                    end
                )
            },
            resources: {
                cpu_usage_percent: $cpu_usage,
                memory_mb: $memory_mb
            },
            current_task: $task_id
        }')

    # Append to health metrics
    echo "$health_entry" >> "$HEALTH_METRICS_FILE"

    echo "$health_entry"
}

##############################################################################
# monitor_all_workers: Monitor health of all active workers
##############################################################################
monitor_all_workers() {
    if [ ! -f "$WORKER_POOL_FILE" ]; then
        echo "Worker pool file not found: $WORKER_POOL_FILE"
        return 1
    fi

    local worker_count=$(jq '.workers | length' "$WORKER_POOL_FILE" 2>/dev/null || echo "0")

    if [ "$worker_count" -eq 0 ]; then
        echo "No active workers to monitor"
        return 0
    fi

    echo "=== Monitoring $worker_count workers ==="
    echo ""

    # Monitor each worker
    jq -r '.workers[] | "\(.worker_id)|\(.status // "unknown")|\(.task_id // "none")"' "$WORKER_POOL_FILE" 2>/dev/null | while IFS='|' read -r worker_id status task_id; do
        if [ -n "$worker_id" ]; then
            collect_worker_health "$worker_id" "$status" 0 0 "$task_id" | jq -c '.'
        fi
    done
}

##############################################################################
# get_worker_health_summary: Get health summary for all workers
##############################################################################
get_worker_health_summary() {
    if [ ! -f "$HEALTH_METRICS_FILE" ]; then
        echo "No health metrics collected yet"
        return 1
    fi

    echo "=== Worker Health Summary ==="
    echo ""

    # Get recent health data (last entry per worker)
    local recent_health=$(cat "$HEALTH_METRICS_FILE" | jq -s 'group_by(.worker_id) | map(max_by(.timestamp))')

    echo "$recent_health" | jq '
        {
            total_workers: length,
            by_status: group_by(.status) | map({status: .[0].status, count: length}),
            by_health: group_by(.health.status) | map({health: .[0].health.status, count: length}),
            by_master: group_by(.assigned_master) | map({master: .[0].assigned_master, count: length}),
            longest_running: max_by(.health.uptime_seconds) | {
                worker_id,
                uptime: .health.uptime_human,
                status,
                task: .current_task
            }
        }
    '
}

##############################################################################
# check_unhealthy_workers: Identify workers needing attention
##############################################################################
check_unhealthy_workers() {
    if [ ! -f "$HEALTH_METRICS_FILE" ]; then
        return 0
    fi

    # Get recent health data
    local unhealthy=$(cat "$HEALTH_METRICS_FILE" | \
        jq -s 'group_by(.worker_id) | map(max_by(.timestamp)) | map(select(.health.status != "healthy"))')

    local count=$(echo "$unhealthy" | jq 'length')

    if [ "$count" -eq 0 ]; then
        echo "✅ All workers are healthy"
        return 0
    fi

    echo "⚠️  Found $count unhealthy workers:"
    echo ""

    echo "$unhealthy" | jq -r '.[] | "  - \(.worker_id): \(.health.status) (\(.status)) - Uptime: \(.health.uptime_human)"'
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-monitor}" in
        monitor)
            monitor_all_workers
            ;;
        summary)
            get_worker_health_summary
            ;;
        check)
            check_unhealthy_workers
            ;;
        worker)
            shift
            collect_worker_health "$@"
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  monitor
    Monitor health of all active workers

  summary
    Display health summary of all workers

  check
    Check for unhealthy workers

  worker <worker_id> <status> [cpu_usage] [memory_mb] [task_id]
    Collect health metrics for specific worker

Examples:
  # Monitor all workers
  $0 monitor

  # Get health summary
  $0 summary

  # Check for issues
  $0 check

  # Record worker health
  $0 worker worker-001 active 45 512 task-123

Health metrics stored in: $HEALTH_METRICS_FILE
EOF
            ;;
    esac
fi
