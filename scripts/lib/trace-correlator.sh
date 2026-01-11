#!/usr/bin/env bash
# Trace Correlator
# Phase 1: Foundation & Observability
# Correlates traces across task → master → worker → completion flow

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Trace data sources
TASKS_DIR="$CORTEX_HOME/coordination/tasks"
ROUTING_LOG="$CORTEX_HOME/coordination/masters/coordinator/knowledge-base/routing-decisions.jsonl"
WORKER_POOL="$CORTEX_HOME/coordination/worker-pool.json"
WORKER_SPECS_DIR="$CORTEX_HOME/coordination/worker-specs/active"
LLM_METRICS="$CORTEX_HOME/coordination/metrics/llm-operations.jsonl"

##############################################################################
# correlate_task_trace: Build complete trace for a task
# Args:
#   $1: task_id
# Returns: JSON with complete trace correlation
##############################################################################
correlate_task_trace() {
    local task_id="$1"

    # 1. Get task creation info
    local task_file="$TASKS_DIR/${task_id}.json"
    local task_data="{}"

    if [ -f "$task_file" ]; then
        task_data=$(cat "$task_file" | jq '{
            task_id,
            description,
            phase,
            priority,
            created_at,
            status
        }')
    else
        task_data=$(jq -n --arg task_id "$task_id" '{task_id: $task_id, status: "not_found"}')
    fi

    # 2. Get routing decision
    local routing_data="{}"

    if [ -f "$ROUTING_LOG" ]; then
        routing_data=$(grep "\"task_id\":\"$task_id\"" "$ROUTING_LOG" 2>/dev/null | tail -1 || echo "{}")

        if [ -n "$routing_data" ] && [ "$routing_data" != "{}" ]; then
            routing_data=$(echo "$routing_data" | jq '{
                timestamp,
                routing_method,
                decision: {
                    primary_expert,
                    primary_confidence,
                    strategy,
                    parallel_experts
                }
            }')
        else
            routing_data='{"status": "no_routing_found"}'
        fi
    fi

    # 3. Get worker execution info
    local worker_data="[]"

    # Find workers for this task
    if [ -d "$WORKER_SPECS_DIR" ]; then
        local worker_specs=$(grep -l "\"task_id\":\"$task_id\"" "$WORKER_SPECS_DIR"/*.json 2>/dev/null || echo "")

        if [ -n "$worker_specs" ]; then
            worker_data=$(for spec_file in $worker_specs; do
                cat "$spec_file" | jq '{
                    worker_id,
                    worker_type,
                    created_by,
                    created_at,
                    status,
                    execution: {
                        started_at,
                        completed_at,
                        tokens_used,
                        duration_minutes
                    },
                    results: {
                        status,
                        summary
                    }
                }'
            done | jq -s '.')
        else
            worker_data='[]'
        fi
    fi

    # 4. Get LLM metrics for this task
    local llm_metrics="[]"

    if [ -f "$LLM_METRICS" ]; then
        llm_metrics=$(grep "\"task_id\":\"$task_id\"" "$LLM_METRICS" 2>/dev/null | jq -s '.' || echo "[]")
    fi

    # 5. Calculate trace statistics
    local trace_duration=0
    local total_tokens=0
    local total_cost=0

    if [ "$llm_metrics" != "[]" ]; then
        total_tokens=$(echo "$llm_metrics" | jq '[.[].tokens.total] | add // 0')
        total_cost=$(echo "$llm_metrics" | jq '[.[].cost.usd | tonumber] | add // 0')
    fi

    # Build complete trace correlation
    local trace=$(jq -n \
        --argjson task "$task_data" \
        --argjson routing "$routing_data" \
        --argjson workers "$worker_data" \
        --argjson llm_metrics "$llm_metrics" \
        --argjson total_tokens "$total_tokens" \
        --arg total_cost "$total_cost" \
        '{
            task: $task,
            routing: $routing,
            workers: $workers,
            llm_operations: $llm_metrics,
            trace_summary: {
                worker_count: ($workers | length),
                llm_operations_count: ($llm_metrics | length),
                total_tokens: $total_tokens,
                total_cost_usd: $total_cost
            }
        }')

    echo "$trace"
}

##############################################################################
# validate_trace_completeness: Check if trace has all expected components
# Args:
#   $1: trace JSON
# Returns: validation result
##############################################################################
validate_trace_completeness() {
    local trace="$1"

    local has_task=$(echo "$trace" | jq '.task.task_id != null')
    local has_routing=$(echo "$trace" | jq '.routing.decision != null')
    local has_workers=$(echo "$trace" | jq '.workers | length > 0')
    local has_metrics=$(echo "$trace" | jq '.llm_operations | length > 0')

    local completeness_score=0

    [ "$has_task" = "true" ] && completeness_score=$((completeness_score + 25))
    [ "$has_routing" = "true" ] && completeness_score=$((completeness_score + 25))
    [ "$has_workers" = "true" ] && completeness_score=$((completeness_score + 25))
    [ "$has_metrics" = "true" ] && completeness_score=$((completeness_score + 25))

    local status="incomplete"
    [ "$completeness_score" -eq 100 ] && status="complete"
    [ "$completeness_score" -ge 75 ] && status="partial"

    jq -n \
        --arg status "$status" \
        --argjson score "$completeness_score" \
        --argjson has_task "$has_task" \
        --argjson has_routing "$has_routing" \
        --argjson has_workers "$has_workers" \
        --argjson has_metrics "$has_metrics" \
        '{
            status: $status,
            completeness_score: $score,
            components: {
                task: $has_task,
                routing: $has_routing,
                workers: $has_workers,
                llm_metrics: $has_metrics
            }
        }'
}

##############################################################################
# correlate_all_recent_tasks: Correlate traces for recent tasks
# Args:
#   $1: count (default: 10)
##############################################################################
correlate_all_recent_tasks() {
    local count="${1:-10}"

    echo "=== Correlating traces for $count most recent tasks ==="
    echo ""

    if [ ! -d "$TASKS_DIR" ]; then
        echo "Tasks directory not found: $TASKS_DIR"
        return 1
    fi

    # Get recent task files
    local task_files=$(ls -t "$TASKS_DIR"/task-*.json 2>/dev/null | head -"$count")

    if [ -z "$task_files" ]; then
        echo "No task files found"
        return 1
    fi

    local results=()

    for task_file in $task_files; do
        local task_id=$(basename "$task_file" .json)
        local trace=$(correlate_task_trace "$task_id")
        local validation=$(validate_trace_completeness "$trace")

        local completeness=$(echo "$validation" | jq -r '.completeness_score')
        local status=$(echo "$validation" | jq -r '.status')

        echo "Task: $task_id - Trace: $status ($completeness%)"

        results+=("$completeness")
    done

    # Calculate average completeness
    if [ ${#results[@]} -gt 0 ]; then
        local sum=0
        for score in "${results[@]}"; do
            sum=$((sum + score))
        done
        local avg=$((sum / ${#results[@]}))

        echo ""
        echo "Average trace completeness: $avg%"
    fi
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        correlate)
            if [ -z "${2:-}" ]; then
                echo "Error: task_id required"
                exit 1
            fi
            correlate_task_trace "$2" | jq '.'
            ;;
        validate)
            if [ -z "${2:-}" ]; then
                echo "Error: task_id required"
                exit 1
            fi
            trace=$(correlate_task_trace "$2")
            validate_trace_completeness "$trace" | jq '.'
            ;;
        recent)
            correlate_all_recent_tasks "${2:-10}"
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  correlate <task_id>
    Correlate complete trace for a task

  validate <task_id>
    Validate trace completeness for a task

  recent [count]
    Correlate traces for recent tasks (default: 10)

Examples:
  # Correlate trace for a specific task
  $0 correlate task-metrics-collector

  # Validate trace completeness
  $0 validate task-metrics-collector

  # Correlate recent tasks
  $0 recent 20

Trace components:
  - Task creation data
  - MoE routing decision
  - Worker execution info
  - LLM operation metrics
EOF
            ;;
    esac
fi
