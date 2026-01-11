#!/usr/bin/env bash
# Token Optimizer
# Phase 3: Security & Efficiency
# Optimizes token usage and reduces LLM API costs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Token metrics
LLM_METRICS="$CORTEX_HOME/coordination/metrics/llm-operations.jsonl"
TOKEN_BUDGET="$CORTEX_HOME/coordination/token-budget.json"
OPTIMIZATION_RECOMMENDATIONS="$CORTEX_HOME/coordination/token-optimization-recommendations.jsonl"

mkdir -p "$(dirname "$OPTIMIZATION_RECOMMENDATIONS")"

##############################################################################
# analyze_token_usage: Analyze token usage patterns
# Args:
#   $1: task_type or master_type (optional)
#   $2: lookback_days (default: 7)
##############################################################################
analyze_token_usage() {
    local filter_type="${1:-all}"
    local lookback_days="${2:-7}"

    if [ ! -f "$LLM_METRICS" ]; then
        echo "No LLM metrics available"
        return 1
    fi

    echo "=== Token Usage Analysis (Last $lookback_days days) ==="
    echo ""

    local cutoff_date=$(date -v-${lookback_days}d +%Y-%m-%d 2>/dev/null || date -d "$lookback_days days ago" +%Y-%m-%d)

    local analysis=$(cat "$LLM_METRICS" | jq -s '
        map(select(.timestamp >= "'"$cutoff_date"'")) |
        {
            total_operations: length,
            total_tokens: map(.tokens.total) | add // 0,
            total_cost_usd: map(.cost.usd | tonumber) | add // 0,
            avg_tokens_per_operation: ((map(.tokens.total) | add // 0) / length),
            by_operation_type: group_by(.operation_type) | map({
                type: .[0].operation_type,
                operations: length,
                total_tokens: map(.tokens.total) | add,
                avg_tokens: ((map(.tokens.total) | add) / length),
                cost: (map(.cost.usd | tonumber) | add)
            }),
            by_model: group_by(.model.id) | map({
                model: .[0].model.id,
                operations: length,
                total_tokens: map(.tokens.total) | add,
                cost: (map(.cost.usd | tonumber) | add)
            }),
            efficiency_score: (
                # Lower tokens per operation = higher efficiency
                if ((map(.tokens.total) | add // 0) / length) < 2000 then 0.9
                elif ((map(.tokens.total) | add // 0) / length) < 4000 then 0.7
                elif ((map(.tokens.total) | add // 0) / length) < 6000 then 0.5
                else 0.3
                end
            )
        }
    ')

    echo "$analysis" | jq '.'
}

##############################################################################
# optimize_token_usage: Generate optimization recommendations
# Args:
#   $1: task_type
#   $2: current_avg_tokens
#   $3: current_quality_score (optional)
##############################################################################
optimize_token_usage() {
    local task_type="$1"
    local current_avg_tokens="$2"
    local current_quality_score="${3:-0.8}"

    local recommendations=()
    local potential_savings=0
    local timestamp=$(date -Iseconds)

    # Strategy 1: Model downgrade if quality permits
    if [ "$current_avg_tokens" -lt 2000 ] && (( $(echo "$current_quality_score >= 0.85" | bc -l) )); then
        recommendations+=("Consider using claude-haiku for this task type - quality is high and token usage is low")
        potential_savings=$((potential_savings + 20))
    fi

    # Strategy 2: Context caching
    if [ "$current_avg_tokens" -gt 3000 ]; then
        recommendations+=("Enable prompt caching for repeated context - could save 30-50% on prompt tokens")
        potential_savings=$((potential_savings + 35))
    fi

    # Strategy 3: Trim verbosity
    if [ "$current_avg_tokens" -gt 4000 ]; then
        recommendations+=("Add conciseness constraint to prompts - outputs may be unnecessarily verbose")
        potential_savings=$((potential_savings + 15))
    fi

    # Strategy 4: Few-shot vs zero-shot
    if [ "$current_avg_tokens" -gt 2500 ]; then
        recommendations+=("Evaluate if few-shot examples are necessary - may be able to use zero-shot prompting")
        potential_savings=$((potential_savings + 10))
    fi

    # Strategy 5: Output format optimization
    recommendations+=("Specify output format constraints to reduce token usage in responses")
    potential_savings=$((potential_savings + 10))

    # Build recommendations JSON
    local recs_json=$(printf '%s\n' "${recommendations[@]}" | jq -R . | jq -s .)

    local result=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg task_type "$task_type" \
        --argjson current_tokens "$current_avg_tokens" \
        --arg quality "$current_quality_score" \
        --argjson recommendations "$recs_json" \
        --argjson potential_savings "$potential_savings" \
        '{
            timestamp: $timestamp,
            task_type: $task_type,
            current_metrics: {
                avg_tokens: $current_tokens,
                quality_score: $quality
            },
            recommendations: $recommendations,
            potential_savings_percent: $potential_savings,
            estimated_cost_reduction: (($current_tokens * $potential_savings / 100) | floor)
        }')

    echo "$result" >> "$OPTIMIZATION_RECOMMENDATIONS"
    echo "$result"
}

##############################################################################
# recommend_model: Recommend optimal model based on usage
# Args:
#   $1: task_complexity (1-10)
#   $2: avg_tokens_used
#   $3: quality_threshold (0.0-1.0)
##############################################################################
recommend_model() {
    local complexity="$1"
    local avg_tokens="$2"
    local quality_threshold="$3"

    local recommended_model=""
    local reasoning=""

    # Decision matrix
    if [ "$complexity" -le 3 ] && [ "$avg_tokens" -lt 1500 ]; then
        recommended_model="claude-haiku"
        reasoning="Low complexity, low token usage - Haiku is most cost-effective"
    elif [ "$complexity" -le 6 ] && [ "$avg_tokens" -lt 3000 ]; then
        recommended_model="claude-sonnet-4"
        reasoning="Moderate complexity - Sonnet provides good balance of quality and cost"
    elif [ "$complexity" -ge 7 ] || [ "$avg_tokens" -gt 4000 ]; then
        recommended_model="claude-opus-4"
        reasoning="High complexity or large context - Opus recommended for best quality"
    else
        recommended_model="claude-sonnet-4"
        reasoning="Default recommendation for most tasks"
    fi

    jq -n \
        --arg model "$recommended_model" \
        --arg reasoning "$reasoning" \
        --argjson complexity "$complexity" \
        --argjson avg_tokens "$avg_tokens" \
        --arg quality_threshold "$quality_threshold" \
        '{
            recommended_model: $model,
            reasoning: $reasoning,
            input_factors: {
                complexity: $complexity,
                avg_tokens: $avg_tokens,
                quality_threshold: $quality_threshold
            }
        }'
}

##############################################################################
# calculate_cost_savings: Calculate potential cost savings
# Args:
#   $1: current_model
#   $2: recommended_model
#   $3: monthly_operations
#   $4: avg_tokens_per_operation
##############################################################################
calculate_cost_savings() {
    local current_model="$1"
    local recommended_model="$2"
    local monthly_ops="$3"
    local avg_tokens="$4"

    # Simplified pricing (per 1M tokens)
    local current_cost=0
    local recommended_cost=0

    case "$current_model" in
        *haiku*)
            current_cost=1.00
            ;;
        *sonnet*)
            current_cost=3.00
            ;;
        *opus*)
            current_cost=15.00
            ;;
    esac

    case "$recommended_model" in
        *haiku*)
            recommended_cost=1.00
            ;;
        *sonnet*)
            recommended_cost=3.00
            ;;
        *opus*)
            recommended_cost=15.00
            ;;
    esac

    # Calculate monthly costs
    local current_monthly=$(echo "scale=2; $monthly_ops * $avg_tokens * $current_cost / 1000000" | bc -l)
    local recommended_monthly=$(echo "scale=2; $monthly_ops * $avg_tokens * $recommended_cost / 1000000" | bc -l)
    local savings=$(echo "scale=2; $current_monthly - $recommended_monthly" | bc -l)
    local savings_percent=0

    if (( $(echo "$current_monthly > 0" | bc -l) )); then
        savings_percent=$(echo "scale=0; ($savings / $current_monthly) * 100" | bc -l)
    fi

    jq -n \
        --arg current_model "$current_model" \
        --arg recommended_model "$recommended_model" \
        --arg current_monthly "$current_monthly" \
        --arg recommended_monthly "$recommended_monthly" \
        --arg savings "$savings" \
        --argjson savings_percent "$savings_percent" \
        '{
            current: {
                model: $current_model,
                monthly_cost_usd: $current_monthly
            },
            recommended: {
                model: $recommended_model,
                monthly_cost_usd: $recommended_monthly
            },
            savings: {
                monthly_usd: $savings,
                percent: $savings_percent
            }
        }'
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        analyze)
            analyze_token_usage "${2:-all}" "${3:-7}"
            ;;
        optimize)
            shift
            if [ $# -lt 2 ]; then
                echo "Error: optimize requires <task_type> <current_avg_tokens> [quality_score]"
                exit 1
            fi
            optimize_token_usage "$@" | jq '.'
            ;;
        recommend-model)
            shift
            if [ $# -lt 3 ]; then
                echo "Error: recommend-model requires <complexity> <avg_tokens> <quality_threshold>"
                exit 1
            fi
            recommend_model "$@" | jq '.'
            ;;
        calculate-savings)
            shift
            if [ $# -lt 4 ]; then
                echo "Error: calculate-savings requires <current_model> <recommended_model> <monthly_ops> <avg_tokens>"
                exit 1
            fi
            calculate_cost_savings "$@" | jq '.'
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  analyze [task_type] [lookback_days]
    Analyze token usage patterns (default: all types, 7 days)

  optimize <task_type> <current_avg_tokens> [quality_score]
    Generate optimization recommendations

  recommend-model <complexity> <avg_tokens> <quality_threshold>
    Recommend optimal model for task

  calculate-savings <current_model> <recommended_model> <monthly_ops> <avg_tokens>
    Calculate potential cost savings

Optimization Strategies:
  1. Model Downgrade: Use smaller models when quality permits
  2. Context Caching: Enable caching for repeated context
  3. Trim Verbosity: Add conciseness constraints
  4. Few-shot Optimization: Reduce examples when possible
  5. Format Constraints: Specify output format limits

Examples:
  # Analyze token usage
  $0 analyze development-master 30

  # Get optimization recommendations
  $0 optimize implementation-worker 3500 0.85

  # Recommend model
  $0 recommend-model 5 2500 0.8

  # Calculate savings
  $0 calculate-savings claude-opus-4 claude-sonnet-4 10000 3000

Metrics stored in: $LLM_METRICS
Recommendations stored in: $OPTIMIZATION_RECOMMENDATIONS
EOF
            ;;
    esac
fi
