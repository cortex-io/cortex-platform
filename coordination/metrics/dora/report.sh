#!/usr/bin/env bash
# DORA Metrics Report Generator
# Creates human-readable reports from DORA metrics

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/aggregator.sh"

# ==============================================================================
# TERMINAL COLORS
# ==============================================================================

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
MAGENTA="\033[0;35m"
CYAN="\033[0;36m"
BOLD="\033[1m"
NC="\033[0m"  # No Color

# ==============================================================================
# PERFORMANCE LEVEL COLORS
# ==============================================================================

get_level_color() {
    local level="$1"

    case "$level" in
        elite) echo "$GREEN" ;;
        high) echo "$CYAN" ;;
        medium) echo "$YELLOW" ;;
        low) echo "$RED" ;;
        *) echo "$NC" ;;
    esac
}

# ==============================================================================
# FORMATTED REPORT
# ==============================================================================

generate_report() {
    local lookback_days="${1:-30}"
    local master_filter="${2:-all}"

    local metrics=$(aggregate_all_metrics "$lookback_days" "$master_filter")

    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}         DORA METRICS REPORT${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BOLD}Period:${NC} Last $lookback_days days"
    echo -e "${BOLD}Master:${NC} $master_filter"
    echo -e "${BOLD}Generated:${NC} $(date)"
    echo ""

    # Deployment Frequency
    echo -e "${BOLD}${BLUE}1. DEPLOYMENT FREQUENCY${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local deploy_per_day=$(echo "$metrics" | jq -r '.metrics.deployment_frequency.deployments_per_day')
    local deploy_total=$(echo "$metrics" | jq -r '.metrics.deployment_frequency.total_deployments')
    local deploy_level=$(echo "$metrics" | jq -r '.metrics.deployment_frequency.performance_level')
    local deploy_color=$(get_level_color "$deploy_level")

    echo -e "${BOLD}Total Deployments:${NC} $deploy_total"
    echo -e "${BOLD}Per Day:${NC} $deploy_per_day"
    echo -e "${BOLD}Performance Level:${NC} ${deploy_color}${BOLD}${deploy_level^^}${NC}"
    echo ""

    # Lead Time
    echo -e "${BOLD}${BLUE}2. LEAD TIME FOR CHANGES${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local lead_mean=$(echo "$metrics" | jq -r '.metrics.lead_time.mean_minutes // 0')
    local lead_median=$(echo "$metrics" | jq -r '.metrics.lead_time.median_minutes // 0')
    local lead_p95=$(echo "$metrics" | jq -r '.metrics.lead_time.p95_minutes // 0')
    local lead_level=$(echo "$metrics" | jq -r '.metrics.lead_time.performance_level // "unknown"')
    local lead_color=$(get_level_color "$lead_level")

    if [[ "$lead_mean" != "0" ]]; then
        echo -e "${BOLD}Mean:${NC} $lead_mean minutes ($(echo "scale=1; $lead_mean / 60" | bc) hours)"
        echo -e "${BOLD}Median:${NC} $lead_median minutes"
        echo -e "${BOLD}95th Percentile:${NC} $lead_p95 minutes"
        echo -e "${BOLD}Performance Level:${NC} ${lead_color}${BOLD}${lead_level^^}${NC}"
    else
        echo -e "${YELLOW}No data available${NC}"
    fi
    echo ""

    # MTTR
    echo -e "${BOLD}${BLUE}3. MEAN TIME TO RECOVER (MTTR)${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local mttr_mean=$(echo "$metrics" | jq -r '.metrics.mttr.mean_minutes // 0')
    local mttr_failures=$(echo "$metrics" | jq -r '.metrics.mttr.failure_count // 0')
    local mttr_level=$(echo "$metrics" | jq -r '.metrics.mttr.performance_level // "unknown"')
    local mttr_color=$(get_level_color "$mttr_level")

    if [[ "$mttr_failures" != "0" ]]; then
        echo -e "${BOLD}Failures Recovered:${NC} $mttr_failures"
        echo -e "${BOLD}Mean Recovery Time:${NC} $mttr_mean minutes ($(echo "scale=1; $mttr_mean / 60" | bc) hours)"
        echo -e "${BOLD}Performance Level:${NC} ${mttr_color}${BOLD}${mttr_level^^}${NC}"
    else
        echo -e "${GREEN}No failures in period${NC}"
    fi
    echo ""

    # Change Failure Rate
    echo -e "${BOLD}${BLUE}4. CHANGE FAILURE RATE${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local cfr_rate=$(echo "$metrics" | jq -r '.metrics.change_failure_rate.failure_rate_percent')
    local cfr_total=$(echo "$metrics" | jq -r '.metrics.change_failure_rate.total_changes // 0')
    local cfr_failed=$(echo "$metrics" | jq -r '.metrics.change_failure_rate.failed_changes // 0')
    local cfr_level=$(echo "$metrics" | jq -r '.metrics.change_failure_rate.performance_level')
    local cfr_color=$(get_level_color "$cfr_level")

    if [[ "$cfr_total" != "0" ]]; then
        echo -e "${BOLD}Total Changes:${NC} $cfr_total"
        echo -e "${BOLD}Failed Changes:${NC} $cfr_failed"
        echo -e "${BOLD}Failure Rate:${NC} ${cfr_rate}%"
        echo -e "${BOLD}Performance Level:${NC} ${cfr_color}${BOLD}${cfr_level^^}${NC}"
    else
        echo -e "${YELLOW}No data available${NC}"
    fi
    echo ""

    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ==============================================================================
# MASTER COMPARISON REPORT
# ==============================================================================

generate_comparison_report() {
    local lookback_days="${1:-30}"

    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}       MASTER PERFORMANCE COMPARISON${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local comparison=$(compare_masters "$lookback_days")
    local masters=$(echo "$comparison" | jq -r '.masters')

    # Print header
    printf "%-20s %-15s %-15s %-15s %-15s\n" "Master" "Deploy/Day" "Lead Time (min)" "MTTR (min)" "Failure %"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Print each master
    local masters_array=$(echo "$masters" | jq -c '.[]')
    echo "$masters_array" | while IFS= read -r master_metrics; do
        local master=$(echo "$master_metrics" | jq -r '.master_filter')
        local deploy=$(echo "$master_metrics" | jq -r '.metrics.deployment_frequency.deployments_per_day // "0"')
        local lead=$(echo "$master_metrics" | jq -r '.metrics.lead_time.mean_minutes // "0"')
        local mttr=$(echo "$master_metrics" | jq -r '.metrics.mttr.mean_minutes // "0"')
        local failure=$(echo "$master_metrics" | jq -r '.metrics.change_failure_rate.failure_rate_percent // "0"')

        printf "%-20s %-15s %-15s %-15s %-15s\n" "$master" "$deploy" "$lead" "$mttr" "$failure%"
    done

    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ==============================================================================
# JSON REPORT
# ==============================================================================

generate_json_report() {
    local lookback_days="${1:-30}"
    local master_filter="${2:-all}"

    aggregate_all_metrics "$lookback_days" "$master_filter"
}

# ==============================================================================
# MAIN
# ==============================================================================

main() {
    local command="${1:-formatted}"

    case "$command" in
        formatted)
            generate_report "${2:-30}" "${3:-all}"
            ;;
        comparison)
            generate_comparison_report "${2:-30}"
            ;;
        json)
            generate_json_report "${2:-30}" "${3:-all}"
            ;;
        *)
            echo "Usage: $0 {formatted|comparison|json} [lookback_days] [master]"
            echo ""
            echo "Commands:"
            echo "  formatted   - Human-readable report (default)"
            echo "  comparison  - Compare all masters side-by-side"
            echo "  json        - JSON output for programmatic use"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

export -f generate_report
export -f generate_comparison_report
export -f generate_json_report
