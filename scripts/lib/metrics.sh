#!/usr/bin/env bash
#
# Production Metrics Library - Enhanced Observability
# Builds upon existing metrics-collector.sh with production-specific features
#
# Usage:
#   source scripts/lib/metrics.sh
#   emit_master_metric "development-master" "task_processed" 1500 '{"task_type":"feature"}'
#   emit_task_processing_time "task-123" 2500
#   emit_token_usage "worker-456" 5000
#   emit_worker_spawn_result "worker-789" "success" '{"worker_type":"scan"}'
#

set -euo pipefail

# Avoid redefining readonly variables if already sourced
if [[ -z "${METRICS_LIB_LOADED:-}" ]]; then
    readonly METRICS_LIB_LOADED=true
    readonly METRICS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Source existing metrics collector
    if [[ -f "$METRICS_SCRIPT_DIR/observability/metrics-collector.sh" ]]; then
        source "$METRICS_SCRIPT_DIR/observability/metrics-collector.sh"
    else
        echo "Warning: metrics-collector.sh not found, using fallback mode" >&2
        ENABLE_METRICS=false
    fi
fi

# Source environment library for environment-aware paths
if [ -f "$METRICS_SCRIPT_DIR/environment.sh" ]; then
    source "$METRICS_SCRIPT_DIR/environment.sh"
fi

# Production metrics configuration (environment-aware)
if type get_metrics_dir &>/dev/null; then
    METRICS_BASE_DIR=$(get_metrics_dir)
    readonly METRICS_PRODUCTION_DIR="${METRICS_PRODUCTION_DIR:-${METRICS_BASE_DIR}/production}"
    readonly METRICS_ALERTS_DIR="${METRICS_ALERTS_DIR:-${METRICS_BASE_DIR}/alerts}"
    readonly METRICS_AGGREGATES_DIR="${METRICS_AGGREGATES_DIR:-${METRICS_BASE_DIR}/aggregates}"
    readonly METRICS_MASTER_DIR="${METRICS_MASTER_DIR:-${METRICS_BASE_DIR}/masters}"
else
    # Fallback for backwards compatibility
    readonly METRICS_PRODUCTION_DIR="${METRICS_PRODUCTION_DIR:-coordination/metrics/production}"
    readonly METRICS_ALERTS_DIR="${METRICS_ALERTS_DIR:-coordination/metrics/alerts}"
    readonly METRICS_AGGREGATES_DIR="${METRICS_AGGREGATES_DIR:-coordination/metrics/aggregates}"
    readonly METRICS_MASTER_DIR="${METRICS_MASTER_DIR:-coordination/metrics/masters}"
fi

# Initialize directories
mkdir -p "$METRICS_PRODUCTION_DIR" "$METRICS_ALERTS_DIR" "$METRICS_AGGREGATES_DIR" "$METRICS_MASTER_DIR"

#
# Emit a generic master metric
# Usage: emit_master_metric <master_id> <metric_name> <value> [dimensions_json] [unit]
#
emit_master_metric() {
    local master_id="$1"
    local metric_name="$2"
    local value="$3"
    local dimensions="${4:-{}}"
    local unit="${5:-count}"

    # Add master_id to dimensions
    local enhanced_dims=$(echo "$dimensions" | jq --arg mid "$master_id" '. + {master_id: $mid}' 2>/dev/null || echo '{"master_id":"'"$master_id"'"}')

    # Record using base metrics collector
    record_histogram "master_${metric_name}" "$value" "$enhanced_dims" "$unit"

    # Also write to master-specific file for easy querying
    local master_metrics_file="$METRICS_MASTER_DIR/${master_id}-$(date +%Y-%m-%d).jsonl"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    echo "{\"timestamp\":\"$timestamp\",\"master_id\":\"$master_id\",\"metric\":\"$metric_name\",\"value\":$value,\"unit\":\"$unit\",\"dimensions\":$enhanced_dims}" >> "$master_metrics_file"
}

#
# Emit task processing time metric
# Usage: emit_task_processing_time <task_id> <duration_ms> [task_type] [master_id]
#
emit_task_processing_time() {
    local task_id="$1"
    local duration_ms="$2"
    local task_type="${3:-unknown}"
    local master_id="${4:-unknown}"

    local dimensions=$(jq -n \
        --arg tid "$task_id" \
        --arg type "$task_type" \
        --arg mid "$master_id" \
        '{task_id: $tid, task_type: $type, master_id: $mid}')

    # Record histogram for percentile tracking
    record_histogram "task_processing_time_ms" "$duration_ms" "$dimensions" "milliseconds"

    # Record counter for total tasks processed
    record_counter "tasks_processed_total" 1 "$dimensions"

    # Emit master metric if master_id provided
    if [[ "$master_id" != "unknown" ]]; then
        emit_master_metric "$master_id" "task_processing_time_ms" "$duration_ms" "{\"task_type\":\"$task_type\"}" "milliseconds"
    fi

    # Check SLA threshold (5 minutes = 300000ms)
    if [[ $duration_ms -gt 300000 ]]; then
        emit_alert "task_processing_sla_breach" "high" "Task $task_id exceeded 5min SLA: ${duration_ms}ms" "$dimensions"
    fi
}

#
# Emit token usage metric
# Usage: emit_token_usage <entity_id> <tokens_used> <entity_type> [operation]
#
emit_token_usage() {
    local entity_id="$1"
    local tokens_used="$2"
    local entity_type="${3:-worker}"  # worker, master, orchestrator
    local operation="${4:-unknown}"

    local dimensions=$(jq -n \
        --arg eid "$entity_id" \
        --arg type "$entity_type" \
        --arg op "$operation" \
        '{entity_id: $eid, entity_type: $type, operation: $op}')

    # Record gauge for current usage
    record_gauge "token_usage" "$tokens_used" "$dimensions" "tokens"

    # Record counter for cumulative usage
    record_counter "tokens_consumed_total" "$tokens_used" "$dimensions"

    # Check high token usage threshold (>50k)
    if [[ $tokens_used -gt 50000 ]]; then
        emit_alert "high_token_usage" "medium" "Entity $entity_id consumed ${tokens_used} tokens" "$dimensions"
    fi
}

#
# Emit worker spawn result metric
# Usage: emit_worker_spawn_result <worker_id> <result> [dimensions_json]
# result: success, failed, timeout
#
emit_worker_spawn_result() {
    local worker_id="$1"
    local result="$2"
    local dimensions="${3:-{}}"

    # Add worker_id and result to dimensions
    local enhanced_dims=$(echo "$dimensions" | jq \
        --arg wid "$worker_id" \
        --arg res "$result" \
        '. + {worker_id: $wid, result: $res}')

    # Record counter for spawn attempts
    record_counter "worker_spawns_total" 1 "$enhanced_dims"

    # Record success/failure specifically
    if [[ "$result" == "success" ]]; then
        record_counter "worker_spawns_successful" 1 "$enhanced_dims"
    else
        record_counter "worker_spawns_failed" 1 "$enhanced_dims"
        emit_alert "worker_spawn_failure" "medium" "Worker $worker_id spawn failed: $result" "$enhanced_dims"
    fi
}

#
# Emit worker completion metric
# Usage: emit_worker_completion <worker_id> <duration_ms> <status> [tokens_used]
#
emit_worker_completion() {
    local worker_id="$1"
    local duration_ms="$2"
    local status="$3"
    local tokens_used="${4:-0}"

    local dimensions=$(jq -n \
        --arg wid "$worker_id" \
        --arg status "$status" \
        --arg tokens "$tokens_used" \
        '{worker_id: $wid, status: $status, tokens_used: $tokens}')

    # Record completion time
    record_histogram "worker_duration_ms" "$duration_ms" "$dimensions" "milliseconds"

    # Record completion counter
    record_counter "workers_completed_total" 1 "$dimensions"

    # Record success/failure
    if [[ "$status" == "completed" ]]; then
        record_counter "workers_successful" 1 "$dimensions"
    else
        record_counter "workers_failed" 1 "$dimensions"
    fi

    # Record token usage if provided
    if [[ $tokens_used -gt 0 ]]; then
        emit_token_usage "$worker_id" "$tokens_used" "worker" "completion"
    fi
}

#
# Emit master handoff metric
# Usage: emit_master_handoff <from_master> <to_master> <task_id> <success>
#
emit_master_handoff() {
    local from_master="$1"
    local to_master="$2"
    local task_id="$3"
    local success="${4:-true}"

    local dimensions=$(jq -n \
        --arg from "$from_master" \
        --arg to "$to_master" \
        --arg tid "$task_id" \
        --arg success "$success" \
        '{from_master: $from, to_master: $to, task_id: $tid, success: $success}')

    record_counter "master_handoffs_total" 1 "$dimensions"

    if [[ "$success" == "true" ]]; then
        record_counter "master_handoffs_successful" 1 "$dimensions"
    else
        record_counter "master_handoffs_failed" 1 "$dimensions"
        emit_alert "master_handoff_failure" "high" "Handoff failed: $from_master -> $to_master for $task_id" "$dimensions"
    fi
}

#
# Emit routing decision metric
# Usage: emit_routing_decision <task_id> <selected_master> <confidence> <method>
#
emit_routing_decision() {
    local task_id="$1"
    local selected_master="$2"
    local confidence="$3"
    local method="${4:-hybrid}"

    local dimensions=$(jq -n \
        --arg tid "$task_id" \
        --arg master "$selected_master" \
        --arg method "$method" \
        '{task_id: $tid, selected_master: $master, routing_method: $method}')

    record_histogram "routing_confidence" "$confidence" "$dimensions" "ratio"
    record_counter "routing_decisions_total" 1 "$dimensions"

    # Alert on low confidence routing
    if (( $(echo "$confidence < 0.5" | bc -l) )); then
        emit_alert "low_routing_confidence" "medium" "Routing confidence ${confidence} for $task_id to $selected_master" "$dimensions"
    fi
}

#
# Emit system health metric
# Usage: emit_system_health <component> <health_score> [details_json]
#
emit_system_health() {
    local component="$1"
    local health_score="$2"
    local details="${3:-{}}"

    local dimensions=$(echo "$details" | jq --arg comp "$component" '. + {component: $comp}')

    record_gauge "system_health_score" "$health_score" "$dimensions" "percentage"

    # Alert on degraded health
    if (( $(echo "$health_score < 70" | bc -l) )); then
        local severity="high"
        [[ $(echo "$health_score < 50" | bc -l) -eq 1 ]] && severity="critical"
        emit_alert "system_health_degraded" "$severity" "Component $component health: ${health_score}%" "$dimensions"
    fi
}

#
# Emit RAG retrieval metric
# Usage: emit_rag_retrieval <retrieval_time_ms> <num_results> <query_type>
#
emit_rag_retrieval() {
    local retrieval_time_ms="$1"
    local num_results="$2"
    local query_type="${3:-semantic}"

    local dimensions=$(jq -n \
        --arg type "$query_type" \
        --arg count "$num_results" \
        '{query_type: $type, result_count: $count}')

    record_histogram "rag_retrieval_time_ms" "$retrieval_time_ms" "$dimensions" "milliseconds"
    record_gauge "rag_results_returned" "$num_results" "$dimensions" "count"

    # Alert on slow retrievals
    if [[ $retrieval_time_ms -gt 5000 ]]; then
        emit_alert "slow_rag_retrieval" "low" "RAG retrieval took ${retrieval_time_ms}ms" "$dimensions"
    fi
}

#
# Emit alert
# Usage: emit_alert <alert_type> <severity> <message> [dimensions_json]
# severity: low, medium, high, critical
#
emit_alert() {
    local alert_type="$1"
    local severity="$2"
    local message="$3"
    local dimensions="${4:-{}}"

    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local alert_id="alert-$(date +%s%N | cut -b1-13)-$(openssl rand -hex 3)"

    local alert_json=$(jq -n \
        --arg aid "$alert_id" \
        --arg ts "$timestamp" \
        --arg type "$alert_type" \
        --arg sev "$severity" \
        --arg msg "$message" \
        --argjson dims "$dimensions" \
        '{
            alert_id: $aid,
            timestamp: $ts,
            alert_type: $type,
            severity: $sev,
            message: $msg,
            dimensions: $dims,
            status: "active"
        }')

    # Write to alerts file
    local alerts_file="$METRICS_ALERTS_DIR/alerts-$(date +%Y-%m-%d).jsonl"
    echo "$alert_json" >> "$alerts_file"

    # Also update active alerts
    local active_alerts="$METRICS_ALERTS_DIR/active-alerts.json"
    if [[ -f "$active_alerts" ]]; then
        jq --argjson alert "$alert_json" '.alerts += [$alert]' "$active_alerts" > "$active_alerts.tmp" && mv "$active_alerts.tmp" "$active_alerts"
    else
        echo "{\"alerts\":[$alert_json]}" > "$active_alerts"
    fi

    # Record alert metric
    record_counter "alerts_triggered_total" 1 "{\"alert_type\":\"$alert_type\",\"severity\":\"$severity\"}"
}

#
# Get master performance summary
# Usage: get_master_performance <master_id> [hours_back]
#
get_master_performance() {
    local master_id="$1"
    local hours_back="${2:-24}"

    local master_metrics_file="$METRICS_MASTER_DIR/${master_id}-$(date +%Y-%m-%d).jsonl"

    if [[ ! -f "$master_metrics_file" ]]; then
        echo '{"error":"no_data"}'
        return
    fi

    local since_ts=$(date -u -v-${hours_back}H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "${hours_back} hours ago" +%Y-%m-%dT%H:%M:%SZ)

    cat "$master_metrics_file" | jq -s --arg since "$since_ts" '
        map(select(.timestamp >= $since)) |
        {
            master_id: .[0].master_id // "unknown",
            period: "'"${hours_back}h"'",
            total_metrics: length,
            metrics_by_type: (group_by(.metric) | map({key: .[0].metric, value: length}) | from_entries),
            avg_task_time: (map(select(.metric == "task_processing_time_ms")) | map(.value) | if length > 0 then add / length else 0 end),
            total_tasks: (map(select(.metric == "task_processing_time_ms")) | length),
            token_usage: (map(select(.metric == "token_usage")) | map(.value) | add // 0)
        }
    '
}

#
# Get system-wide metrics summary
# Usage: get_system_summary [hours_back]
#
get_system_summary() {
    local hours_back="${1:-24}"

    local metrics_file="$METRICS_RAW_DIR/metrics-$(date +%Y-%m-%d).jsonl"

    if [[ ! -f "$metrics_file" ]]; then
        echo '{"error":"no_data"}'
        return
    fi

    local since_ms=$(( ($(date +%s) - (hours_back * 3600)) * 1000 ))

    cat "$metrics_file" | jq -s --arg since "$since_ms" '
        map(select(.timestamp >= ($since | tonumber))) |
        {
            period: "'"${hours_back}h"'",
            total_metrics: length,
            metrics_by_type: (group_by(.metric_type) | map({key: .[0].metric_type, value: length}) | from_entries),
            top_metrics: (group_by(.metric_name) | sort_by(length) | reverse | .[0:10] | map({metric: .[0].metric_name, count: length})),
            alert_count: (map(select(.metric_name | contains("alert"))) | length),
            worker_spawns: (map(select(.metric_name == "worker_spawns_total")) | map(.value) | add // 0),
            tasks_completed: (map(select(.metric_name == "tasks_processed_total")) | map(.value) | add // 0),
            total_tokens: (map(select(.metric_name == "tokens_consumed_total")) | map(.value) | add // 0)
        }
    '
}

#
# Create performance snapshot for archival
# Usage: create_performance_snapshot
#
create_performance_snapshot() {
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local snapshot_file="$METRICS_AGGREGATES_DIR/snapshot-$(date +%Y-%m-%d-%H%M).json"

    local snapshot=$(jq -n \
        --arg ts "$timestamp" \
        --argjson system "$(get_system_summary 1)" \
        --argjson dev "$(get_master_performance development-master 1)" \
        --argjson sec "$(get_master_performance security-master 1)" \
        --argjson inv "$(get_master_performance inventory-master 1)" \
        --argjson cicd "$(get_master_performance cicd-master 1)" \
        --argjson coord "$(get_master_performance coordinator-master 1)" \
        '{
            snapshot_timestamp: $ts,
            system_summary: $system,
            masters: {
                development: $dev,
                security: $sec,
                inventory: $inv,
                cicd: $cicd,
                coordinator: $coord
            }
        }')

    echo "$snapshot" > "$snapshot_file"
    echo "$snapshot_file"
}

#
# Calculate success rate for entity
# Usage: calculate_success_rate <entity_type> <entity_id> [hours_back]
#
calculate_success_rate() {
    local entity_type="$1"
    local entity_id="$2"
    local hours_back="${3:-24}"

    local metrics_file="$METRICS_RAW_DIR/metrics-$(date +%Y-%m-%d).jsonl"

    if [[ ! -f "$metrics_file" ]]; then
        echo "0"
        return
    fi

    local since_ms=$(( ($(date +%s) - (hours_back * 3600)) * 1000 ))

    cat "$metrics_file" | jq -r --arg type "$entity_type" --arg id "$entity_id" --arg since "$since_ms" '
        map(select(.timestamp >= ($since | tonumber) and .dimensions.'$entity_type' == $id)) |
        if length == 0 then 0 else
            (map(select(.dimensions.status == "completed" or .dimensions.result == "success")) | length) / length
        end
    '
}

# Export all functions
export -f emit_master_metric
export -f emit_task_processing_time
export -f emit_token_usage
export -f emit_worker_spawn_result
export -f emit_worker_completion
export -f emit_master_handoff
export -f emit_routing_decision
export -f emit_system_health
export -f emit_rag_retrieval
export -f emit_alert
export -f get_master_performance
export -f get_system_summary
export -f create_performance_snapshot
export -f calculate_success_rate
