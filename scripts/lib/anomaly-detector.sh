#!/usr/bin/env bash
# Anomaly Detector
# Phase 4: Advanced Intelligence
# AI-driven anomaly detection for worker behavior and system performance

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Anomaly logs
ANOMALY_LOG="$CORTEX_HOME/coordination/anomalies.jsonl"
WORKER_HEALTH_METRICS="$CORTEX_HOME/coordination/worker-health-metrics.jsonl"
LLM_METRICS="$CORTEX_HOME/coordination/metrics/llm-operations.jsonl"

mkdir -p "$(dirname "$ANOMALY_LOG")"
touch "$ANOMALY_LOG"

##############################################################################
# detect_anomalies: Detect anomalies across all system dimensions
# Args:
#   $1: detection_scope (worker|performance|cost|quality|all)
#   $2: lookback_minutes (default: 60)
# Returns: Anomaly detection results
##############################################################################
detect_anomalies() {
    local scope="${1:-all}"
    local lookback_minutes="${2:-60}"
    local timestamp=$(date -Iseconds)

    local anomalies=()
    local anomaly_count=0

    case "$scope" in
        worker|all)
            detect_worker_anomalies "$lookback_minutes" anomalies
            ;;
    esac

    case "$scope" in
        performance|all)
            detect_performance_anomalies "$lookback_minutes" anomalies
            ;;
    esac

    case "$scope" in
        cost|all)
            detect_cost_anomalies "$lookback_minutes" anomalies
            ;;
    esac

    case "$scope" in
        quality|all)
            detect_quality_anomalies "$lookback_minutes" anomalies
            ;;
    esac

    # Build results
    anomaly_count=${#anomalies[@]}
    local anomalies_json="[]"
    if [ "$anomaly_count" -gt 0 ]; then
        anomalies_json=$(printf '%s\n' "${anomalies[@]}" | jq -s '.')
    fi

    local severity="normal"
    if [ "$anomaly_count" -ge 10 ]; then
        severity="critical"
    elif [ "$anomaly_count" -ge 5 ]; then
        severity="high"
    elif [ "$anomaly_count" -ge 2 ]; then
        severity="medium"
    elif [ "$anomaly_count" -ge 1 ]; then
        severity="low"
    fi

    jq -n \
        --arg timestamp "$timestamp" \
        --arg scope "$scope" \
        --argjson anomaly_count "$anomaly_count" \
        --argjson anomalies "$anomalies_json" \
        --arg severity "$severity" \
        '{
            timestamp: $timestamp,
            detection_scope: $scope,
            anomaly_count: $anomaly_count,
            anomalies: $anomalies,
            severity: $severity,
            status: (if $anomaly_count == 0 then "healthy" else "anomalies_detected" end)
        }'
}

##############################################################################
# detect_worker_anomalies: Detect worker behavior anomalies
# Args:
#   $1: lookback_minutes
#   $2: anomalies_array_name (pass by reference)
##############################################################################
detect_worker_anomalies() {
    local lookback_minutes="$1"
    local -n anomalies_ref=$2

    if [ ! -f "$WORKER_HEALTH_METRICS" ]; then
        return 0
    fi

    local cutoff_time=$(date -v-${lookback_minutes}M -Iseconds 2>/dev/null || date -d "$lookback_minutes minutes ago" -Iseconds)

    # 1. Detect workers with excessive failures
    local failed_workers=$(cat "$WORKER_HEALTH_METRICS" | \
        jq -r "select(.timestamp >= \"$cutoff_time\" and .status == \"failed\") | .worker_id" | \
        sort | uniq -c | sort -rn | head -5)

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        local count=$(echo "$line" | awk '{print $1}')
        local worker_id=$(echo "$line" | awk '{print $2}')

        if [ "$count" -ge 3 ]; then
            local anomaly=$(jq -n \
                --arg type "excessive_worker_failures" \
                --arg worker_id "$worker_id" \
                --argjson count "$count" \
                --arg severity "high" \
                '{
                    type: $type,
                    worker_id: $worker_id,
                    description: "Worker failed \($count) times in \('"$lookback_minutes"') minutes",
                    failure_count: $count,
                    severity: $severity,
                    recommendation: "Investigate worker logs and consider restarting or reconfiguring"
                }')
            anomalies_ref+=("$anomaly")
        fi
    done <<< "$failed_workers"

    # 2. Detect workers with abnormal CPU usage
    local avg_cpu=$(cat "$WORKER_HEALTH_METRICS" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\" and .cpu_usage > 0)) |
              if length > 0 then (map(.cpu_usage) | add / length) else 0 end")

    if [ "$(echo "$avg_cpu > 0" | bc -l)" -eq 1 ]; then
        local high_cpu_workers=$(cat "$WORKER_HEALTH_METRICS" | \
            jq -r "select(.timestamp >= \"$cutoff_time\" and .cpu_usage > ($avg_cpu * 2)) |
                   .worker_id" | sort | uniq)

        for worker_id in $high_cpu_workers; do
            [ -z "$worker_id" ] && continue
            local worker_cpu=$(cat "$WORKER_HEALTH_METRICS" | \
                jq -s "map(select(.worker_id == \"$worker_id\" and .timestamp >= \"$cutoff_time\")) |
                      map(.cpu_usage) | add / length")

            local anomaly=$(jq -n \
                --arg type "abnormal_cpu_usage" \
                --arg worker_id "$worker_id" \
                --arg cpu "$worker_cpu" \
                --arg avg_cpu "$avg_cpu" \
                --arg severity "medium" \
                '{
                    type: $type,
                    worker_id: $worker_id,
                    description: "Worker CPU usage (\($cpu)%) is 2x above average (\($avg_cpu)%)",
                    cpu_usage: ($cpu | tonumber),
                    avg_cpu: ($avg_cpu | tonumber),
                    severity: $severity,
                    recommendation: "Monitor worker for resource leaks or inefficient operations"
                }')
            anomalies_ref+=("$anomaly")
        done
    fi

    # 3. Detect workers stuck in busy state
    local stuck_workers=$(cat "$WORKER_HEALTH_METRICS" | \
        jq -r "select(.timestamp >= \"$cutoff_time\" and .status == \"busy\") | .worker_id" | \
        sort | uniq -c | awk '$1 >= 10 {print $2}')

    for worker_id in $stuck_workers; do
        [ -z "$worker_id" ] && continue
        local anomaly=$(jq -n \
            --arg type "worker_stuck_busy" \
            --arg worker_id "$worker_id" \
            --arg severity "high" \
            '{
                type: $type,
                worker_id: $worker_id,
                description: "Worker appears stuck in busy state",
                severity: $severity,
                recommendation: "Check worker logs for deadlock or infinite loop; consider restart"
            }')
        anomalies_ref+=("$anomaly")
    done
}

##############################################################################
# detect_performance_anomalies: Detect performance anomalies
# Args:
#   $1: lookback_minutes
#   $2: anomalies_array_name (pass by reference)
##############################################################################
detect_performance_anomalies() {
    local lookback_minutes="$1"
    local -n anomalies_ref=$2

    if [ ! -f "$LLM_METRICS" ]; then
        return 0
    fi

    local cutoff_time=$(date -v-${lookback_minutes}M -Iseconds 2>/dev/null || date -d "$lookback_minutes minutes ago" -Iseconds)

    # 1. Detect abnormally high latency
    local avg_latency=$(cat "$LLM_METRICS" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\")) |
              if length > 0 then (map(.performance.latency_ms) | add / length) else 0 end")

    local std_dev=$(cat "$LLM_METRICS" | \
        jq -s --argjson avg "$avg_latency" \
        'map(select(.timestamp >= "'"$cutoff_time"'")) |
         if length > 0 then
           (map(pow(.performance.latency_ms - $avg; 2)) | add / length | sqrt)
         else 0 end')

    local high_latency_threshold=$(echo "$avg_latency + (2 * $std_dev)" | bc -l)

    if [ "$(echo "$high_latency_threshold > 0" | bc -l)" -eq 1 ]; then
        local high_latency_count=$(cat "$LLM_METRICS" | \
            jq -s "map(select(.timestamp >= \"$cutoff_time\" and
                              .performance.latency_ms > $high_latency_threshold)) | length")

        if [ "$high_latency_count" -ge 5 ]; then
            local anomaly=$(jq -n \
                --arg type "high_latency_spike" \
                --arg avg "$avg_latency" \
                --arg threshold "$high_latency_threshold" \
                --argjson count "$high_latency_count" \
                --arg severity "medium" \
                '{
                    type: $type,
                    description: "\($count) operations exceeded latency threshold",
                    avg_latency_ms: ($avg | tonumber),
                    threshold_ms: ($threshold | tonumber),
                    occurrences: $count,
                    severity: $severity,
                    recommendation: "Check API provider status and network connectivity"
                }')
            anomalies_ref+=("$anomaly")
        fi
    fi

    # 2. Detect token usage spikes
    local avg_tokens=$(cat "$LLM_METRICS" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\")) |
              if length > 0 then (map(.tokens.total) | add / length) else 0 end")

    local token_threshold=$(echo "$avg_tokens * 3" | bc -l)

    if [ "$(echo "$token_threshold > 0" | bc -l)" -eq 1 ]; then
        local high_token_ops=$(cat "$LLM_METRICS" | \
            jq -s "map(select(.timestamp >= \"$cutoff_time\" and
                              .tokens.total > $token_threshold)) | length")

        if [ "$high_token_ops" -ge 3 ]; then
            local anomaly=$(jq -n \
                --arg type "token_usage_spike" \
                --arg avg "$avg_tokens" \
                --arg threshold "$token_threshold" \
                --argjson count "$high_token_ops" \
                --arg severity "medium" \
                '{
                    type: $type,
                    description: "\($count) operations used 3x average tokens",
                    avg_tokens: ($avg | tonumber),
                    threshold: ($threshold | tonumber),
                    occurrences: $count,
                    severity: $severity,
                    recommendation: "Review prompts for excessive verbosity or context"
                }')
            anomalies_ref+=("$anomaly")
        fi
    fi
}

##############################################################################
# detect_cost_anomalies: Detect cost-related anomalies
# Args:
#   $1: lookback_minutes
#   $2: anomalies_array_name (pass by reference)
##############################################################################
detect_cost_anomalies() {
    local lookback_minutes="$1"
    local -n anomalies_ref=$2

    if [ ! -f "$LLM_METRICS" ]; then
        return 0
    fi

    local cutoff_time=$(date -v-${lookback_minutes}M -Iseconds 2>/dev/null || date -d "$lookback_minutes minutes ago" -Iseconds)

    # Calculate cost rate (USD per minute)
    local total_cost=$(cat "$LLM_METRICS" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\")) |
              map(.cost.usd | tonumber) | add // 0")

    local cost_per_minute=$(echo "scale=4; $total_cost / $lookback_minutes" | bc -l)

    # Alert if burning > $1/hour
    local hourly_rate=$(echo "scale=2; $cost_per_minute * 60" | bc -l)

    if [ "$(echo "$hourly_rate > 1.0" | bc -l)" -eq 1 ]; then
        local anomaly=$(jq -n \
            --arg type "high_cost_burn_rate" \
            --arg hourly_rate "$hourly_rate" \
            --arg severity "high" \
            '{
                type: $type,
                description: "Cost burn rate exceeds $\($hourly_rate)/hour",
                hourly_rate_usd: ($hourly_rate | tonumber),
                severity: $severity,
                recommendation: "Review token optimizer recommendations and consider model downgrade"
            }')
        anomalies_ref+=("$anomaly")
    fi

    # Detect expensive operation patterns
    local expensive_ops=$(cat "$LLM_METRICS" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\" and
                         (.cost.usd | tonumber) > 0.10)) | length")

    if [ "$expensive_ops" -ge 5 ]; then
        local anomaly=$(jq -n \
            --arg type "frequent_expensive_operations" \
            --argjson count "$expensive_ops" \
            --arg severity "medium" \
            '{
                type: $type,
                description: "\($count) operations cost >$0.10 each",
                occurrences: $count,
                severity: $severity,
                recommendation: "Review expensive operations for optimization opportunities"
            }')
        anomalies_ref+=("$anomaly")
    fi
}

##############################################################################
# detect_quality_anomalies: Detect quality degradation
# Args:
#   $1: lookback_minutes
#   $2: anomalies_array_name (pass by reference)
##############################################################################
detect_quality_anomalies() {
    local lookback_minutes="$1"
    local -n anomalies_ref=$2

    local quality_file="$CORTEX_HOME/coordination/quality-scores.jsonl"

    if [ ! -f "$quality_file" ]; then
        return 0
    fi

    local cutoff_time=$(date -v-${lookback_minutes}M -Iseconds 2>/dev/null || date -d "$lookback_minutes minutes ago" -Iseconds)

    # 1. Detect quality score drop
    local avg_quality=$(cat "$quality_file" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\")) |
              if length > 0 then (map(.composite_score) | add / length) else 0 end")

    local low_quality_count=$(cat "$quality_file" | \
        jq -s "map(select(.timestamp >= \"$cutoff_time\" and .composite_score < 0.7)) | length")

    if [ "$low_quality_count" -ge 5 ]; then
        local anomaly=$(jq -n \
            --arg type "quality_degradation" \
            --argjson count "$low_quality_count" \
            --arg avg "$avg_quality" \
            --arg severity "high" \
            '{
                type: $type,
                description: "\($count) outputs scored below acceptable quality (0.7)",
                low_quality_count: $count,
                avg_quality_score: ($avg | tonumber),
                severity: $severity,
                recommendation: "Review prompt quality and worker configuration"
            }')
        anomalies_ref+=("$anomaly")
    fi

    # 2. Detect workers with consistently poor quality
    local poor_quality_workers=$(cat "$quality_file" | \
        jq -r "select(.timestamp >= \"$cutoff_time\" and .composite_score < 0.7) | .worker_id" | \
        sort | uniq -c | awk '$1 >= 3 {print $2}')

    for worker_id in $poor_quality_workers; do
        [ -z "$worker_id" ] && continue
        local worker_avg=$(cat "$quality_file" | \
            jq -s "map(select(.worker_id == \"$worker_id\" and .timestamp >= \"$cutoff_time\")) |
                  map(.composite_score) | add / length")

        local anomaly=$(jq -n \
            --arg type "worker_quality_issues" \
            --arg worker_id "$worker_id" \
            --arg avg "$worker_avg" \
            --arg severity "medium" \
            '{
                type: $type,
                worker_id: $worker_id,
                description: "Worker producing consistently low quality (avg: \($avg))",
                avg_quality: ($avg | tonumber),
                severity: $severity,
                recommendation: "Review worker prompt engineering and task assignment"
            }')
        anomalies_ref+=("$anomaly")
    done
}

##############################################################################
# get_anomaly_report: Generate human-readable anomaly report
# Args:
#   $1: hours_lookback (default: 24)
##############################################################################
get_anomaly_report() {
    local hours="${1:-24}"
    local minutes=$((hours * 60))

    echo "=== Anomaly Detection Report (Last $hours hours) ==="
    echo ""

    local results=$(detect_anomalies "all" "$minutes")

    local anomaly_count=$(echo "$results" | jq -r '.anomaly_count')
    local severity=$(echo "$results" | jq -r '.severity')
    local status=$(echo "$results" | jq -r '.status')

    echo "Status: $status"
    echo "Severity: $severity"
    echo "Anomalies Detected: $anomaly_count"
    echo ""

    if [ "$anomaly_count" -eq 0 ]; then
        echo "✅ No anomalies detected - system operating normally"
        return 0
    fi

    echo "$results" | jq -r '.anomalies[] |
        "[\(.severity | ascii_upcase)] \(.type)\n  \(.description)\n  → \(.recommendation)\n"'
}

##############################################################################
# log_anomaly: Log detected anomaly
# Args:
#   $1: anomaly_json
##############################################################################
log_anomaly() {
    local anomaly="$1"
    echo "$anomaly" >> "$ANOMALY_LOG"
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        detect)
            shift
            detect_anomalies "${1:-all}" "${2:-60}" | jq '.'
            ;;
        report)
            get_anomaly_report "${2:-24}"
            ;;
        monitor)
            # Continuous monitoring mode
            interval="${2:-300}"  # 5 minutes default
            echo "Starting anomaly monitor (checking every ${interval}s)..."
            while true; do
                results=$(detect_anomalies "all" "60")
                anomaly_count=$(echo "$results" | jq -r '.anomaly_count')

                if [ "$anomaly_count" -gt 0 ]; then
                    echo "[$(date -Iseconds)] 🚨 $anomaly_count anomalies detected!"
                    echo "$results" | jq -r '.anomalies[] | "  - \(.type): \(.description)"'
                    log_anomaly "$results"
                else
                    echo "[$(date -Iseconds)] ✅ System healthy"
                fi

                sleep "$interval"
            done
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  detect [scope] [lookback_minutes]
    Detect anomalies across system (scope: worker|performance|cost|quality|all)

  report [hours]
    Generate human-readable anomaly report (default: 24 hours)

  monitor [interval_seconds]
    Continuous monitoring mode (default: 300s)

Anomaly Types:
  Worker Anomalies:
    - excessive_worker_failures: Worker failing repeatedly
    - abnormal_cpu_usage: CPU usage 2x above average
    - worker_stuck_busy: Worker stuck in busy state

  Performance Anomalies:
    - high_latency_spike: Latency exceeds 2 standard deviations
    - token_usage_spike: Token usage 3x above average

  Cost Anomalies:
    - high_cost_burn_rate: Cost exceeds \$1/hour
    - frequent_expensive_operations: Multiple ops >$0.10

  Quality Anomalies:
    - quality_degradation: Multiple low-quality outputs
    - worker_quality_issues: Worker consistently producing poor quality

Examples:
  # Detect all anomalies in last hour
  $0 detect all 60

  # Generate 24-hour report
  $0 report 24

  # Start continuous monitoring (5 min intervals)
  $0 monitor 300

Anomalies logged to: $ANOMALY_LOG
EOF
            ;;
    esac
fi
