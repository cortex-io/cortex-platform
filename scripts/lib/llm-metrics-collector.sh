#!/usr/bin/env bash
# LLM Metrics Collector
# Phase 1: Foundation & Observability
# Collects comprehensive metrics for all LLM operations in Cortex

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Metrics storage
METRICS_DIR="$CORTEX_HOME/coordination/metrics"
METRICS_FILE="$METRICS_DIR/llm-operations.jsonl"
SNAPSHOT_FILE="$CORTEX_HOME/coordination/observability/metrics-snapshot.json"

# Ensure directories exist
mkdir -p "$METRICS_DIR"
mkdir -p "$(dirname "$SNAPSHOT_FILE")"

##############################################################################
# collect_llm_metrics: Record LLM operation metrics
# Args:
#   $1: operation_type (routing|worker_execution|learning|analysis)
#   $2: task_id
#   $3: model (claude-sonnet-4-5|claude-haiku|etc)
#   $4: tokens_prompt
#   $5: tokens_completion
#   $6: latency_ms
#   $7: cost_usd (optional)
#   $8: worker_id (optional)
#   $9: master_type (optional)
##############################################################################
collect_llm_metrics() {
    local operation_type="$1"
    local task_id="$2"
    local model="$3"
    local tokens_prompt="$4"
    local tokens_completion="$5"
    local latency_ms="$6"
    local cost_usd="${7:-0}"
    local worker_id="${8:-unknown}"
    local master_type="${9:-unknown}"

    local timestamp=$(date -Iseconds)
    local tokens_total=$((tokens_prompt + tokens_completion))

    # Calculate cost if not provided
    if [ "$cost_usd" = "0" ]; then
        cost_usd=$(calculate_cost "$model" "$tokens_prompt" "$tokens_completion")
    fi

    # Create metrics entry
    local metrics_entry=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg operation_type "$operation_type" \
        --arg task_id "$task_id" \
        --arg model "$model" \
        --arg worker_id "$worker_id" \
        --arg master_type "$master_type" \
        --argjson tokens_prompt "$tokens_prompt" \
        --argjson tokens_completion "$tokens_completion" \
        --argjson tokens_total "$tokens_total" \
        --argjson latency_ms "$latency_ms" \
        --arg cost_usd "$cost_usd" \
        '{
            timestamp: $timestamp,
            operation_type: $operation_type,
            task_id: $task_id,
            worker_id: $worker_id,
            master_type: $master_type,
            model: {
                id: $model,
                provider: "anthropic"
            },
            tokens: {
                prompt: $tokens_prompt,
                completion: $tokens_completion,
                total: $tokens_total
            },
            performance: {
                latency_ms: $latency_ms,
                tokens_per_second: (($tokens_total * 1000) / $latency_ms)
            },
            cost: {
                usd: $cost_usd
            }
        }')

    # Append to JSONL
    echo "$metrics_entry" >> "$METRICS_FILE"

    # Update snapshot for real-time dashboard
    update_metrics_snapshot

    echo "$metrics_entry"
}

##############################################################################
# calculate_cost: Calculate LLM API cost
# Args:
#   $1: model
#   $2: tokens_prompt
#   $3: tokens_completion
# Returns: cost in USD
##############################################################################
calculate_cost() {
    local model="$1"
    local tokens_prompt="$2"
    local tokens_completion="$3"

    # Pricing per 1M tokens (as of 2025)
    local prompt_price=0
    local completion_price=0

    case "$model" in
        claude-sonnet-4*|claude-sonnet-4-5*)
            prompt_price=3.00
            completion_price=15.00
            ;;
        claude-opus-4*)
            prompt_price=15.00
            completion_price=75.00
            ;;
        claude-haiku*|claude-3-5-haiku*)
            prompt_price=0.80
            completion_price=4.00
            ;;
        *)
            # Default to Sonnet pricing
            prompt_price=3.00
            completion_price=15.00
            ;;
    esac

    # Calculate cost
    local prompt_cost=$(echo "scale=6; $tokens_prompt * $prompt_price / 1000000" | bc -l)
    local completion_cost=$(echo "scale=6; $tokens_completion * $completion_price / 1000000" | bc -l)
    local total_cost=$(echo "scale=6; $prompt_cost + $completion_cost" | bc -l)

    printf "%.6f" "$total_cost"
}

##############################################################################
# update_metrics_snapshot: Update real-time metrics snapshot for dashboard
##############################################################################
update_metrics_snapshot() {
    if [ ! -f "$METRICS_FILE" ]; then
        return 0
    fi

    # Calculate aggregate metrics from last 100 operations
    local recent_metrics=$(tail -100 "$METRICS_FILE" 2>/dev/null || echo "")

    if [ -z "$recent_metrics" ]; then
        return 0
    fi

    # Aggregate statistics
    local total_operations=$(echo "$recent_metrics" | wc -l | tr -d ' ')
    local total_tokens=$(echo "$recent_metrics" | jq -s 'map(.tokens.total) | add // 0')
    local total_cost=$(echo "$recent_metrics" | jq -s 'map(.cost.usd | tonumber) | add // 0')
    local avg_latency=$(echo "$recent_metrics" | jq -s 'map(.performance.latency_ms) | add / length // 0')
    local avg_tokens_per_sec=$(echo "$recent_metrics" | jq -s 'map(.performance.tokens_per_second) | add / length // 0')

    # Operations by type
    local routing_ops=$(echo "$recent_metrics" | jq -s 'map(select(.operation_type == "routing")) | length')
    local worker_ops=$(echo "$recent_metrics" | jq -s 'map(select(.operation_type == "worker_execution")) | length')
    local learning_ops=$(echo "$recent_metrics" | jq -s 'map(select(.operation_type == "learning")) | length')

    # Create snapshot
    local snapshot=$(jq -n \
        --arg timestamp "$(date -Iseconds)" \
        --argjson total_operations "$total_operations" \
        --argjson total_tokens "$total_tokens" \
        --arg total_cost "$total_cost" \
        --argjson avg_latency "$avg_latency" \
        --argjson avg_tokens_per_sec "$avg_tokens_per_sec" \
        --argjson routing_ops "$routing_ops" \
        --argjson worker_ops "$worker_ops" \
        --argjson learning_ops "$learning_ops" \
        '{
            snapshot_time: $timestamp,
            window: "last_100_operations",
            aggregate_metrics: {
                total_operations: $total_operations,
                total_tokens: $total_tokens,
                total_cost_usd: $total_cost,
                avg_latency_ms: $avg_latency,
                avg_tokens_per_second: $avg_tokens_per_sec
            },
            operations_by_type: {
                routing: $routing_ops,
                worker_execution: $worker_ops,
                learning: $learning_ops
            }
        }')

    echo "$snapshot" > "$SNAPSHOT_FILE"
}

##############################################################################
# get_metrics_summary: Get summary of recent metrics
# Args:
#   $1: count (default: 100)
##############################################################################
get_metrics_summary() {
    local count="${1:-100}"

    if [ ! -f "$METRICS_FILE" ]; then
        echo "No metrics collected yet"
        return 1
    fi

    echo "=== LLM Metrics Summary (Last $count operations) ==="
    echo ""

    tail -"$count" "$METRICS_FILE" | jq -s '
        {
            total_operations: length,
            total_tokens: map(.tokens.total) | add,
            total_cost_usd: map(.cost.usd | tonumber) | add,
            avg_latency_ms: (map(.performance.latency_ms) | add / length),
            operations_by_type: group_by(.operation_type) | map({
                type: .[0].operation_type,
                count: length
            }),
            operations_by_master: group_by(.master_type) | map({
                master: .[0].master_type,
                count: length
            }),
            models_used: group_by(.model.id) | map({
                model: .[0].model.id,
                count: length,
                total_tokens: map(.tokens.total) | add
            })
        }
    '
}

##############################################################################
# Main execution (if run directly)
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-summary}" in
        collect)
            shift
            collect_llm_metrics "$@"
            ;;
        summary)
            get_metrics_summary "${2:-100}"
            ;;
        snapshot)
            update_metrics_snapshot
            cat "$SNAPSHOT_FILE" | jq '.'
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  collect <operation_type> <task_id> <model> <tokens_prompt> <tokens_completion> <latency_ms> [cost_usd] [worker_id] [master_type]
    Collect LLM operation metrics

  summary [count]
    Display summary of recent metrics (default: last 100)

  snapshot
    Update and display current metrics snapshot

Examples:
  # Collect metrics for a worker execution
  $0 collect worker_execution task-123 claude-sonnet-4-5 1500 800 3200 0.023 worker-001 development-master

  # Get summary
  $0 summary

  # Update snapshot for dashboard
  $0 snapshot

Metrics are stored in:
  JSONL: $METRICS_FILE
  Snapshot: $SNAPSHOT_FILE
EOF
            ;;
    esac
fi
