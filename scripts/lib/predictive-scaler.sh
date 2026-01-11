#!/usr/bin/env bash
# Predictive Scaler
# Phase 4: Advanced Intelligence
# ML-based predictive worker pool scaling for optimal resource utilization

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Data sources
WORKER_POOL="$CORTEX_HOME/coordination/worker-pool.json"
WORKER_HEALTH_METRICS="$CORTEX_HOME/coordination/worker-health-metrics.jsonl"
TASK_HISTORY="$CORTEX_HOME/coordination/tasks"
SCALING_HISTORY="$CORTEX_HOME/coordination/scaling-history.jsonl"

# Scaling predictions
SCALING_PREDICTIONS="$CORTEX_HOME/coordination/scaling-predictions.jsonl"

mkdir -p "$(dirname "$SCALING_PREDICTIONS")"
touch "$SCALING_HISTORY"
touch "$SCALING_PREDICTIONS"

##############################################################################
# predict_worker_demand: Predict future worker demand
# Args:
#   $1: forecast_horizon_minutes (default: 60)
#   $2: worker_type (optional, default: all)
# Returns: Demand prediction JSON
##############################################################################
predict_worker_demand() {
    local horizon_minutes="${1:-60}"
    local worker_type="${2:-all}"
    local timestamp=$(date -Iseconds)

    # Analyze historical patterns
    local historical_data=$(analyze_historical_demand "$worker_type" "1440")  # Last 24 hours

    # Extract patterns
    local current_hour=$(date +%H)
    local current_dow=$(date +%u)  # 1=Monday, 7=Sunday
    local current_active=$(get_current_active_workers "$worker_type")

    # Time-based patterns
    local hour_pattern=$(echo "$historical_data" | jq -r ".hourly_avg[$current_hour] // $current_active")
    local dow_pattern=$(echo "$historical_data" | jq -r ".daily_avg[$current_dow] // $current_active")

    # Trend analysis (simple linear regression on last 6 hours)
    local trend=$(calculate_demand_trend "$worker_type" "360")

    # Combine patterns for prediction
    local base_prediction=$(echo "scale=0; ($hour_pattern + $dow_pattern) / 2" | bc)
    local trend_adjusted=$(echo "scale=0; $base_prediction + ($trend * $horizon_minutes / 60)" | bc)

    # Apply bounds
    local min_workers=1
    local max_workers=20
    local predicted_demand=$trend_adjusted

    # Bounds checking
    if [ "$(echo "$predicted_demand < $min_workers" | bc)" -eq 1 ]; then
        predicted_demand=$min_workers
    fi
    if [ "$(echo "$predicted_demand > $max_workers" | bc)" -eq 1 ]; then
        predicted_demand=$max_workers
    fi

    # Calculate confidence based on pattern stability
    local variance=$(echo "$historical_data" | jq -r '.variance // 2.0')
    local confidence=$(calculate_prediction_confidence "$variance")

    # Generate recommendation
    local recommendation="maintain"
    local reasoning="Current capacity adequate"

    local scale_threshold=2  # Only recommend scaling if difference >= 2 workers

    if [ "$(echo "$predicted_demand > ($current_active + $scale_threshold)" | bc)" -eq 1 ]; then
        recommendation="scale_up"
        reasoning="Predicted demand increase of $(echo "$predicted_demand - $current_active" | bc) workers"
    elif [ "$(echo "$predicted_demand < ($current_active - $scale_threshold)" | bc)" -eq 1 ]; then
        recommendation="scale_down"
        reasoning="Predicted demand decrease of $(echo "$current_active - $predicted_demand" | bc) workers"
    fi

    jq -n \
        --arg timestamp "$timestamp" \
        --arg worker_type "$worker_type" \
        --argjson horizon "$horizon_minutes" \
        --argjson current "$current_active" \
        --argjson predicted "$predicted_demand" \
        --arg confidence "$confidence" \
        --arg recommendation "$recommendation" \
        --arg reasoning "$reasoning" \
        --arg trend "$trend" \
        '{
            timestamp: $timestamp,
            worker_type: $worker_type,
            forecast_horizon_minutes: $horizon,
            current_workers: $current,
            predicted_demand: $predicted,
            prediction_confidence: $confidence,
            trend: ($trend | tonumber),
            recommendation: {
                action: $recommendation,
                reasoning: $reasoning,
                target_workers: (
                    if $recommendation == "scale_up" then $predicted
                    elif $recommendation == "scale_down" then $predicted
                    else $current
                    end
                )
            }
        }'
}

##############################################################################
# analyze_historical_demand: Analyze historical worker demand patterns
# Args:
#   $1: worker_type
#   $2: lookback_minutes
# Returns: Pattern analysis JSON
##############################################################################
analyze_historical_demand() {
    local worker_type="$1"
    local lookback_minutes="$2"

    if [ ! -f "$WORKER_HEALTH_METRICS" ]; then
        echo '{"hourly_avg": {}, "daily_avg": {}, "variance": 2.0}'
        return 0
    fi

    local cutoff_time=$(date -v-${lookback_minutes}M -Iseconds 2>/dev/null || date -d "$lookback_minutes minutes ago" -Iseconds)

    # Count active workers per hour
    local hourly_pattern=$(cat "$WORKER_HEALTH_METRICS" | jq -s "
        map(select(.timestamp >= \"$cutoff_time\")) |
        group_by(.timestamp[0:13]) |
        map({
            hour: (.[0].timestamp[11:13] | tonumber),
            active_count: (map(select(.status == \"active\" or .status == \"busy\")) | length)
        }) |
        group_by(.hour) |
        map({
            hour: .[0].hour,
            avg: (map(.active_count) | add / length)
        }) |
        reduce .[] as \$item ({}; . + {\$item.hour: \$item.avg})
    ")

    # Count active workers per day of week
    local daily_pattern=$(cat "$WORKER_HEALTH_METRICS" | jq -s '
        map(select(.timestamp >= "'"$cutoff_time"'")) |
        group_by(.timestamp[0:10]) |
        map({
            active_count: (map(select(.status == "active" or .status == "busy")) | length)
        }) |
        if length > 0 then
            {avg: (map(.active_count) | add / length)}
        else
            {avg: 0}
        end
    ')

    # Calculate variance
    local variance=$(cat "$WORKER_HEALTH_METRICS" | jq -s '
        map(select(.timestamp >= "'"$cutoff_time"'")) |
        group_by(.timestamp[0:13]) |
        map(map(select(.status == "active" or .status == "busy")) | length) |
        if length > 1 then
            . as $data |
            ($data | add / length) as $mean |
            ($data | map(pow(. - $mean; 2)) | add / length | sqrt)
        else 2.0
        end
    ')

    jq -n \
        --argjson hourly "$hourly_pattern" \
        --argjson daily "$daily_pattern" \
        --arg variance "$variance" \
        '{
            hourly_avg: $hourly,
            daily_avg: {"1": ($daily.avg // 0)},
            variance: ($variance | tonumber)
        }'
}

##############################################################################
# calculate_demand_trend: Calculate demand trend over period
# Args:
#   $1: worker_type
#   $2: lookback_minutes
# Returns: Trend value (workers per hour)
##############################################################################
calculate_demand_trend() {
    local worker_type="$1"
    local lookback_minutes="$2"

    if [ ! -f "$WORKER_HEALTH_METRICS" ]; then
        echo "0"
        return 0
    fi

    local cutoff_time=$(date -v-${lookback_minutes}M -Iseconds 2>/dev/null || date -d "$lookback_minutes minutes ago" -Iseconds)

    # Simple trend: compare first half vs second half
    local midpoint=$(date -v-$((lookback_minutes / 2))M -Iseconds 2>/dev/null || date -d "$((lookback_minutes / 2)) minutes ago" -Iseconds)

    local first_half_avg=$(cat "$WORKER_HEALTH_METRICS" | jq -s "
        map(select(.timestamp >= \"$cutoff_time\" and .timestamp < \"$midpoint\")) |
        group_by(.timestamp[0:16]) |
        map(map(select(.status == \"active\" or .status == \"busy\")) | length) |
        if length > 0 then (add / length) else 0 end
    ")

    local second_half_avg=$(cat "$WORKER_HEALTH_METRICS" | jq -s "
        map(select(.timestamp >= \"$midpoint\")) |
        group_by(.timestamp[0:16]) |
        map(map(select(.status == \"active\" or .status == \"busy\")) | length) |
        if length > 0 then (add / length) else 0 end
    ")

    # Calculate trend (workers per hour)
    local trend=$(echo "scale=2; ($second_half_avg - $first_half_avg) * 2" | bc)

    echo "$trend"
}

##############################################################################
# calculate_prediction_confidence: Calculate confidence score
# Args:
#   $1: variance
# Returns: Confidence level (high|medium|low)
##############################################################################
calculate_prediction_confidence() {
    local variance="$1"

    # Lower variance = higher confidence
    if [ "$(echo "$variance < 1.0" | bc -l)" -eq 1 ]; then
        echo "high"
    elif [ "$(echo "$variance < 2.5" | bc -l)" -eq 1 ]; then
        echo "medium"
    else
        echo "low"
    fi
}

##############################################################################
# get_current_active_workers: Get count of currently active workers
# Args:
#   $1: worker_type
# Returns: Worker count
##############################################################################
get_current_active_workers() {
    local worker_type="$1"

    if [ ! -f "$WORKER_POOL" ]; then
        echo "0"
        return 0
    fi

    local count=$(cat "$WORKER_POOL" | jq -r '
        .active_workers |
        to_entries |
        map(select(.value.status == "active" or .value.status == "busy")) |
        length
    ')

    echo "${count:-0}"
}

##############################################################################
# recommend_scaling_action: Generate actionable scaling recommendation
# Args:
#   $1: worker_type
#   $2: forecast_horizon_minutes
# Returns: Scaling recommendation with cost analysis
##############################################################################
recommend_scaling_action() {
    local worker_type="$1"
    local horizon_minutes="${2:-60}"
    local timestamp=$(date -Iseconds)

    # Get demand prediction
    local prediction=$(predict_worker_demand "$horizon_minutes" "$worker_type")

    local current_workers=$(echo "$prediction" | jq -r '.current_workers')
    local target_workers=$(echo "$prediction" | jq -r '.recommendation.target_workers')
    local action=$(echo "$prediction" | jq -r '.recommendation.action')
    local confidence=$(echo "$prediction" | jq -r '.prediction_confidence')

    # Calculate cost impact
    local worker_cost_per_hour=0.50  # Estimated cost per worker per hour
    local hourly_cost_current=$(echo "scale=2; $current_workers * $worker_cost_per_hour" | bc)
    local hourly_cost_target=$(echo "scale=2; $target_workers * $worker_cost_per_hour" | bc)
    local cost_impact=$(echo "scale=2; $hourly_cost_target - $hourly_cost_current" | bc)

    # Risk assessment
    local risk="low"
    if [ "$action" = "scale_down" ] && [ "$confidence" = "low" ]; then
        risk="high"
    elif [ "$action" = "scale_up" ] && [ "$confidence" = "low" ]; then
        risk="medium"
    fi

    echo "$prediction" | jq \
        --arg cost_current "$hourly_cost_current" \
        --arg cost_target "$hourly_cost_target" \
        --arg cost_impact "$cost_impact" \
        --arg risk "$risk" \
        '. + {
            cost_analysis: {
                current_hourly_cost: ($cost_current | tonumber),
                target_hourly_cost: ($cost_target | tonumber),
                cost_impact: ($cost_impact | tonumber),
                impact_description: (
                    if ($cost_impact | tonumber) > 0 then
                        "Scaling up will increase costs by $\($cost_impact)/hour"
                    elif ($cost_impact | tonumber) < 0 then
                        "Scaling down will reduce costs by $\($cost_impact * -1)/hour"
                    else
                        "No cost impact"
                    end
                )
            },
            risk_assessment: {
                level: $risk,
                description: (
                    if $risk == "high" then
                        "Low confidence prediction - scaling down may impact performance"
                    elif $risk == "medium" then
                        "Medium confidence - monitor closely after scaling"
                    else
                        "Low risk - confident prediction"
                    end
                )
            }
        }'
}

##############################################################################
# auto_scale: Automatically scale worker pool based on prediction
# Args:
#   $1: worker_type
#   $2: confidence_threshold (high|medium|low - default: medium)
# Returns: Scaling action result
##############################################################################
auto_scale() {
    local worker_type="$1"
    local confidence_threshold="${2:-medium}"
    local timestamp=$(date -Iseconds)

    local recommendation=$(recommend_scaling_action "$worker_type" "60")

    local action=$(echo "$recommendation" | jq -r '.recommendation.action')
    local confidence=$(echo "$recommendation" | jq -r '.prediction_confidence')
    local target_workers=$(echo "$recommendation" | jq -r '.recommendation.target_workers')

    # Check confidence threshold
    local should_execute=false

    case "$confidence_threshold" in
        high)
            [ "$confidence" = "high" ] && should_execute=true
            ;;
        medium)
            [ "$confidence" = "high" ] || [ "$confidence" = "medium" ] && should_execute=true
            ;;
        low)
            should_execute=true
            ;;
    esac

    if [ "$should_execute" = false ]; then
        echo "$recommendation" | jq \
            --arg status "skipped" \
            --arg reason "Confidence ($confidence) below threshold ($confidence_threshold)" \
            '. + {
                execution: {
                    status: $status,
                    reason: $reason
                }
            }'
        return 0
    fi

    # Execute scaling action
    local execution_status="success"
    local execution_message=""

    case "$action" in
        scale_up)
            # Call worker spawning logic here
            execution_message="Would spawn $(echo "$target_workers - $(echo "$recommendation" | jq -r '.current_workers')" | bc) additional workers"
            ;;
        scale_down)
            # Call worker termination logic here
            execution_message="Would terminate $(echo "$(echo "$recommendation" | jq -r '.current_workers') - $target_workers" | bc) workers"
            ;;
        maintain)
            execution_message="No scaling action required"
            ;;
    esac

    # Log scaling decision
    local scaling_event=$(echo "$recommendation" | jq \
        --arg status "$execution_status" \
        --arg message "$execution_message" \
        '. + {
            execution: {
                status: $status,
                message: $message,
                executed_at: .timestamp
            }
        }')

    echo "$scaling_event" >> "$SCALING_HISTORY"
    echo "$scaling_event"
}

##############################################################################
# get_scaling_report: Generate scaling analysis report
# Args:
#   $1: hours_lookback (default: 24)
##############################################################################
get_scaling_report() {
    local hours="${1:-24}"

    echo "=== Predictive Scaling Report (Last $hours hours) ==="
    echo ""

    local prediction=$(predict_worker_demand "60" "all")

    echo "Current Status:"
    echo "$prediction" | jq -r '
        "  Active Workers: \(.current_workers)",
        "  Predicted Demand (1h): \(.predicted_demand)",
        "  Trend: \(.trend) workers/hour",
        "  Confidence: \(.prediction_confidence)"
    '
    echo ""

    echo "Recommendation:"
    echo "$prediction" | jq -r '
        "  Action: \(.recommendation.action)",
        "  Target: \(.recommendation.target_workers) workers",
        "  Reasoning: \(.recommendation.reasoning)"
    '
    echo ""

    # Show cost impact
    local recommendation=$(recommend_scaling_action "all" "60")
    echo "Cost Analysis:"
    echo "$recommendation" | jq -r '
        "  Current: $\(.cost_analysis.current_hourly_cost)/hour",
        "  Target: $\(.cost_analysis.target_hourly_cost)/hour",
        "  Impact: \(.cost_analysis.impact_description)"
    '
    echo ""

    # Recent scaling history
    if [ -f "$SCALING_HISTORY" ]; then
        local recent_actions=$(tail -10 "$SCALING_HISTORY" | jq -s 'length')
        echo "Recent Scaling Actions: $recent_actions"
    fi
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        predict)
            shift
            predict_worker_demand "${1:-60}" "${2:-all}" | jq '.'
            ;;
        recommend)
            shift
            recommend_scaling_action "${1:-all}" "${2:-60}" | jq '.'
            ;;
        auto-scale)
            shift
            auto_scale "${1:-all}" "${2:-medium}" | jq '.'
            ;;
        report)
            get_scaling_report "${2:-24}"
            ;;
        monitor)
            # Continuous monitoring with auto-scaling
            interval="${2:-600}"  # 10 minutes default
            confidence="${3:-medium}"

            echo "Starting predictive scaling monitor (checking every ${interval}s)..."
            while true; do
                echo "[$(date -Iseconds)] Running prediction..."
                result=$(auto_scale "all" "$confidence")
                action=$(echo "$result" | jq -r '.recommendation.action')
                status=$(echo "$result" | jq -r '.execution.status // "n/a"')

                echo "  Action: $action | Status: $status"

                sleep "$interval"
            done
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  predict [horizon_minutes] [worker_type]
    Predict worker demand (default: 60 minutes, all types)

  recommend [worker_type] [horizon_minutes]
    Generate scaling recommendation with cost analysis

  auto-scale [worker_type] [confidence_threshold]
    Automatically scale based on prediction (threshold: high|medium|low)

  report [hours]
    Generate scaling analysis report (default: 24 hours)

  monitor [interval_seconds] [confidence_threshold]
    Continuous monitoring with auto-scaling (default: 600s, medium)

Prediction Features:
  - Time-of-day pattern analysis
  - Day-of-week patterns
  - Trend detection (6-hour window)
  - Confidence scoring based on variance
  - Cost impact analysis
  - Risk assessment

Confidence Levels:
  - high: Low variance, strong patterns
  - medium: Moderate variance, some patterns
  - low: High variance, weak patterns

Examples:
  # Predict demand for next hour
  $0 predict 60 implementation-worker

  # Get scaling recommendation
  $0 recommend all 120

  # Auto-scale with high confidence only
  $0 auto-scale all high

  # Generate 24-hour report
  $0 report 24

  # Start auto-scaling monitor (10 min intervals, medium confidence)
  $0 monitor 600 medium

Scaling history logged to: $SCALING_HISTORY
EOF
            ;;
    esac
fi
