#!/usr/bin/env bash
# CI/CD Master - Main Entry Point
#
# Usage:
#   ./run.sh                    # Run full CI/CD pipeline validation
#   ./run.sh --report           # Generate report from latest scan
#   ./run.sh --help             # Show this help

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Configuration
SCANS_DIR="$SCRIPT_DIR/scans"
WORKFLOWS_DIR="$PROJECT_ROOT/.github/workflows"

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "   ╔═══════════════════════════════════════════════════════════════╗"
    echo "   ║                    CI/CD MASTER                                ║"
    echo "   ║      Pipeline Validation • Configuration Analysis • Quality    ║"
    echo "   ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    print_banner
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --report          Generate human-readable report from latest scan"
    echo "  --latest          Use latest scan instead of running new one"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Full CI/CD pipeline scan"
    echo "  $0 --report                 # Generate report from latest scan"
    echo ""
}

get_latest_scan() {
    local latest=$(ls -t "$SCANS_DIR" 2>/dev/null | grep "^scan-" | head -1)
    if [[ -n "$latest" ]]; then
        echo "$SCANS_DIR/$latest"
    else
        echo ""
    fi
}

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

validate_workflow_syntax() {
    local workflow_file="$1"
    local issues=""

    # Check for required fields
    if ! grep -q "^name:" "$workflow_file"; then
        issues="${issues}Missing_'name'_field "
    fi

    if ! grep -q "^on:" "$workflow_file"; then
        issues="${issues}Missing_'on'_field_(trigger) "
    fi

    if ! grep -q "^jobs:" "$workflow_file"; then
        issues="${issues}Missing_'jobs'_field "
    fi

    # Check for permissions definition (security best practice)
    if ! grep -q "^permissions:" "$workflow_file"; then
        issues="${issues}Missing_'permissions'_field_(security_risk) "
    fi

    # Check for hardcoded secrets
    if grep -qE "(password|token|api[_-]?key|secret).*[:=].*['\"]" "$workflow_file"; then
        issues="${issues}Potential_hardcoded_secret_detected "
    fi

    # Check for deprecated actions versions
    if grep -qE "actions/checkout@v[12]" "$workflow_file"; then
        issues="${issues}Using_deprecated_checkout_action_(v1_or_v2) "
    fi

    if grep -qE "actions/setup-node@v[12]" "$workflow_file"; then
        issues="${issues}Using_deprecated_setup-node_action_(v1_or_v2) "
    fi

    if grep -qE "actions/setup-python@v[1-3]" "$workflow_file"; then
        issues="${issues}Using_deprecated_setup-python_action_(v1-v3) "
    fi

    echo "$issues"
}

check_pipeline_efficiency() {
    local workflow_file="$1"
    local recommendations=""

    # Check for caching
    if grep -q "setup-node" "$workflow_file" && ! grep -q "cache:" "$workflow_file"; then
        recommendations="${recommendations}Consider_enabling_npm/yarn_cache_in_setup-node "
    fi

    # Check for timeout settings
    if grep -q "^jobs:" "$workflow_file" && ! grep -q "timeout-minutes:" "$workflow_file"; then
        recommendations="${recommendations}No_timeout_specified_-_jobs_could_run_indefinitely "
    fi

    # Check for continue-on-error usage
    if grep -q "continue-on-error: true" "$workflow_file"; then
        recommendations="${recommendations}Using_continue-on-error_may_hide_failures "
    fi

    # Check for artifact retention
    if grep -q "upload-artifact" "$workflow_file" && ! grep -q "retention-days:" "$workflow_file"; then
        recommendations="${recommendations}Artifact_retention_not_specified_(defaults_to_90_days) "
    fi

    echo "$recommendations"
}

check_security_issues() {
    local workflow_file="$1"
    local security_issues=""

    # Check for pull_request_target (dangerous)
    if grep -q "pull_request_target:" "$workflow_file"; then
        security_issues="${security_issues}CRITICAL:_pull_request_target_can_expose_secrets_to_untrusted_code "
    fi

    # Check for unrestricted permissions
    if grep -q "permissions:.*write-all" "$workflow_file"; then
        security_issues="${security_issues}HIGH:_write-all_permission_is_overly_permissive "
    fi

    # Check for script injection vulnerabilities
    if grep -qE '\$\{\{.*github\.(event\.issue\.title|event\.pull_request\.title|event\.comment\.body)' "$workflow_file"; then
        security_issues="${security_issues}HIGH:_Potential_script_injection_from_user-controlled_input "
    fi

    # Check for checkout of untrusted code
    if grep -q "pull_request:" "$workflow_file" && grep -q "ref:.*head" "$workflow_file"; then
        security_issues="${security_issues}MEDIUM:_Checking_out_PR_code_could_be_risky "
    fi

    echo "$security_issues"
}

# ==============================================================================
# MAIN WORKFLOW
# ==============================================================================

run_cicd_scan() {
    local scan_timestamp=$(date +%Y%m%d_%H%M%S)
    local scan_dir="$SCANS_DIR/scan-$scan_timestamp"

    echo -e "${BLUE}${BOLD}Creating scan directory: $scan_dir${NC}"
    mkdir -p "$scan_dir"

    echo ""
    echo -e "${BLUE}${BOLD}Step 1/4: Discovering CI/CD Configuration Files${NC}"
    echo ""

    if [[ ! -d "$WORKFLOWS_DIR" ]]; then
        echo -e "${RED}ERROR: Workflows directory not found: $WORKFLOWS_DIR${NC}"
        exit 1
    fi

    local workflow_files=$(find "$WORKFLOWS_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) 2>/dev/null)
    local workflow_count=$(echo "$workflow_files" | grep -v '^$' | wc -l | tr -d ' ')

    echo "  Found $workflow_count workflow files"

    # Save workflow inventory
    echo "$workflow_files" | grep -v '^$' > "$scan_dir/workflows-inventory.txt"

    echo ""
    echo -e "${BLUE}${BOLD}Step 2/4: Validating Workflow Syntax${NC}"
    echo ""

    local total_issues=0
    local syntax_data_file="$scan_dir/.syntax-data.tmp"
    > "$syntax_data_file"

    while IFS= read -r workflow; do
        [[ -z "$workflow" ]] && continue

        local workflow_name=$(basename "$workflow")
        echo "  Checking $workflow_name..."

        local issues=$(validate_workflow_syntax "$workflow")
        if [[ -n "$issues" ]]; then
            echo "$workflow_name|$issues" >> "$syntax_data_file"
            total_issues=$((total_issues + 1))
        fi
    done <<< "$workflow_files"

    # Write syntax issues to JSON
    {
        echo "{"
        echo "  \"total_workflows\": $workflow_count,"
        echo "  \"workflows_with_issues\": $total_issues,"
        echo "  \"issues\": {"

        local first=true
        while IFS='|' read -r wf_name wf_issues; do
            [[ "$first" == "false" ]] && echo ","
            first=false
            # Trim trailing space and convert underscores back to spaces
            wf_issues=$(echo "$wf_issues" | sed 's/ $//' | sed 's/_/ /g')
            echo -n "    \"$wf_name\": [\"$(echo "$wf_issues" | sed 's/  */", "/g' | sed 's/", "$//g')\"]"
        done < "$syntax_data_file"

        echo ""
        echo "  }"
        echo "}"
    } > "$scan_dir/syntax-issues.json"

    echo ""
    echo -e "${BLUE}${BOLD}Step 3/4: Checking Pipeline Efficiency${NC}"
    echo ""

    local total_recommendations=0
    local efficiency_data_file="$scan_dir/.efficiency-data.tmp"
    > "$efficiency_data_file"

    while IFS= read -r workflow; do
        [[ -z "$workflow" ]] && continue

        local workflow_name=$(basename "$workflow")
        echo "  Analyzing $workflow_name..."

        local recommendations=$(check_pipeline_efficiency "$workflow")
        if [[ -n "$recommendations" ]]; then
            echo "$workflow_name|$recommendations" >> "$efficiency_data_file"
            total_recommendations=$((total_recommendations + 1))
        fi
    done <<< "$workflow_files"

    # Write efficiency recommendations to JSON
    {
        echo "{"
        echo "  \"total_workflows\": $workflow_count,"
        echo "  \"workflows_with_recommendations\": $total_recommendations,"
        echo "  \"recommendations\": {"

        first=true
        while IFS='|' read -r wf_name wf_recs; do
            [[ "$first" == "false" ]] && echo ","
            first=false
            # Trim trailing space and convert underscores back to spaces
            wf_recs=$(echo "$wf_recs" | sed 's/ $//' | sed 's/_/ /g')
            echo -n "    \"$wf_name\": [\"$(echo "$wf_recs" | sed 's/  */", "/g' | sed 's/", "$//g')\"]"
        done < "$efficiency_data_file"

        echo ""
        echo "  }"
        echo "}"
    } > "$scan_dir/efficiency-recommendations.json"

    echo ""
    echo -e "${BLUE}${BOLD}Step 4/4: Security Analysis${NC}"
    echo ""

    local total_security_issues=0
    local critical_issues=0
    local high_issues=0
    local medium_issues=0
    local security_data_file="$scan_dir/.security-data.tmp"
    > "$security_data_file"

    while IFS= read -r workflow; do
        [[ -z "$workflow" ]] && continue

        local workflow_name=$(basename "$workflow")
        echo "  Scanning $workflow_name..."

        local sec_issues=$(check_security_issues "$workflow")
        if [[ -n "$sec_issues" ]]; then
            echo "$workflow_name|$sec_issues" >> "$security_data_file"
            total_security_issues=$((total_security_issues + 1))

            # Count severity
            if [[ "$sec_issues" == *"CRITICAL"* ]]; then
                critical_issues=$((critical_issues + 1))
            fi
            if [[ "$sec_issues" == *"HIGH"* ]]; then
                high_issues=$((high_issues + 1))
            fi
            if [[ "$sec_issues" == *"MEDIUM"* ]]; then
                medium_issues=$((medium_issues + 1))
            fi
        fi
    done <<< "$workflow_files"

    # Write security issues to JSON
    {
        echo "{"
        echo "  \"total_workflows\": $workflow_count,"
        echo "  \"workflows_with_security_issues\": $total_security_issues,"
        echo "  \"severity_breakdown\": {"
        echo "    \"critical\": $critical_issues,"
        echo "    \"high\": $high_issues,"
        echo "    \"medium\": $medium_issues"
        echo "  },"
        echo "  \"issues\": {"

        first=true
        while IFS='|' read -r wf_name wf_sec; do
            [[ "$first" == "false" ]] && echo ","
            first=false
            # Trim trailing space and convert underscores back to spaces
            wf_sec=$(echo "$wf_sec" | sed 's/ $//' | sed 's/_/ /g')
            echo -n "    \"$wf_name\": [\"$(echo "$wf_sec" | sed 's/  */", "/g' | sed 's/", "$//g')\"]"
        done < "$security_data_file"

        echo ""
        echo "  }"
        echo "}"
    } > "$scan_dir/security-issues.json"

    # Cleanup temp files
    rm -f "$syntax_data_file" "$efficiency_data_file" "$security_data_file"

    # Generate summary.json
    {
        echo "{"
        echo "  \"scan_timestamp\": \"$scan_timestamp\","
        echo "  \"scan_date\": \"$(date -u +"%Y-%m-%d %H:%M:%S UTC")\","
        echo "  \"project_root\": \"$PROJECT_ROOT\","
        echo "  \"workflows_directory\": \"$WORKFLOWS_DIR\","
        echo "  \"summary\": {"
        echo "    \"total_workflows\": $workflow_count,"
        echo "    \"workflows_with_syntax_issues\": $total_issues,"
        echo "    \"workflows_with_efficiency_recommendations\": $total_recommendations,"
        echo "    \"workflows_with_security_issues\": $total_security_issues,"
        echo "    \"critical_security_issues\": $critical_issues,"
        echo "    \"high_security_issues\": $high_issues,"
        echo "    \"medium_security_issues\": $medium_issues"
        echo "  },"
        echo "  \"scan_artifacts\": ["
        echo "    \"workflows-inventory.txt\","
        echo "    \"syntax-issues.json\","
        echo "    \"efficiency-recommendations.json\","
        echo "    \"security-issues.json\""
        echo "  ]"
        echo "}"
    } > "$scan_dir/summary.json"

    echo "$scan_dir"
}

run_cicd_master() {
    local do_scan=true
    local do_report=false
    local use_latest=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --report)
                do_report=true
                do_scan=false
                shift
                ;;
            --latest)
                use_latest=true
                do_scan=false
                shift
                ;;
            --help|-h)
                print_help
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                print_help
                exit 1
                ;;
        esac
    done

    print_banner

    # Ensure scans directory exists
    mkdir -p "$SCANS_DIR"

    local scan_dir=""

    # Run scan (or get latest)
    if [[ "$do_scan" == "true" ]]; then
        scan_dir=$(run_cicd_scan)
        echo ""
    else
        scan_dir=$(get_latest_scan)
        if [[ -z "$scan_dir" ]]; then
            echo -e "${RED}No existing scan found. Run without --latest first.${NC}"
            exit 1
        fi
        echo -e "${YELLOW}Using existing scan: $(basename "$scan_dir")${NC}"
        echo ""
    fi

    # Generate report
    if [[ "$do_report" == "true" ]]; then
        if [[ -z "$scan_dir" ]]; then
            scan_dir=$(get_latest_scan)
        fi

        if [[ -z "$scan_dir" || ! -d "$scan_dir" ]]; then
            echo -e "${RED}No scan found. Run a scan first.${NC}"
            exit 1
        fi

        echo -e "${BLUE}${BOLD}Generating CI/CD Pipeline Report${NC}"
        echo ""

        if command -v jq &>/dev/null && [[ -f "$scan_dir/summary.json" ]]; then
            echo -e "${BOLD}Summary:${NC}"
            jq -r '.summary | to_entries | .[] | "  \(.key): \(.value)"' "$scan_dir/summary.json"
            echo ""
        fi
    fi

    # Print final summary
    echo ""
    echo -e "${GREEN}${BOLD}=== CI/CD Master Complete ===${NC}"
    echo ""
    echo -e "  Scan results: ${CYAN}$scan_dir${NC}"
    echo ""

    if [[ -f "$scan_dir/summary.json" ]]; then
        echo -e "  ${BOLD}Summary:${NC}"
        if command -v jq &>/dev/null; then
            jq -r '.summary | to_entries | .[] | "    \(.key): \(.value)"' "$scan_dir/summary.json" 2>/dev/null || cat "$scan_dir/summary.json"
        else
            cat "$scan_dir/summary.json"
        fi
        echo ""
    fi

    echo -e "  ${BOLD}Next steps:${NC}"
    echo "    - Review scan results in $scan_dir/"
    echo "    - Run '$0 --report' for detailed report"
    echo "    - Check security-issues.json for critical findings"
    echo ""

    # Exit with error code if critical security issues found
    if [[ -f "$scan_dir/summary.json" ]] && command -v jq &>/dev/null; then
        local critical=$(jq -r '.summary.critical_security_issues' "$scan_dir/summary.json" 2>/dev/null || echo "0")
        if [[ "$critical" -gt 0 ]]; then
            echo -e "${RED}${BOLD}WARNING: $critical critical security issue(s) found!${NC}"
            echo ""
            exit 1
        fi
    fi
}

# ==============================================================================
# ENTRY POINT
# ==============================================================================

run_cicd_master "$@"
