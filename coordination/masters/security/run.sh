#!/usr/bin/env bash
# Security Master - Main Entry Point
#
# Usage:
#   ./run.sh                    # Run full security scan
#   ./run.sh --quick            # Run fast scans only
#   ./run.sh --report           # Generate report from latest scan
#   ./run.sh --help             # Show this help

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Configuration
SCANS_DIR="$SCRIPT_DIR/scans"

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
    echo "   ║                    SECURITY MASTER                             ║"
    echo "   ║      Vulnerability Detection • Secret Scanning • Audits        ║"
    echo "   ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    print_banner
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --quick           Run fast scans only (skip deep dependency analysis)"
    echo "  --report          Generate human-readable report from latest scan"
    echo "  --latest          Use latest scan instead of running new one"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Full security scan"
    echo "  $0 --quick                  # Fast scan (secrets + basic vulns)"
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

timestamp() {
    date +%Y%m%d_%H%M%S
}

# ==============================================================================
# SECURITY SCANNING FUNCTIONS
# ==============================================================================

scan_secrets() {
    local output_file="$1"
    local quick_mode="${2:-false}"

    echo -e "${BLUE}Scanning for secrets and credentials...${NC}" >&2

    local findings=()
    local count=0

    # Common secret patterns
    local patterns=(
        "password\s*=\s*['\"].*['\"]"
        "api[_-]?key\s*=\s*['\"].*['\"]"
        "secret\s*=\s*['\"].*['\"]"
        "token\s*=\s*['\"].*['\"]"
        "aws_access_key_id"
        "aws_secret_access_key"
        "AKIA[0-9A-Z]{16}"
        "github_token"
        "private[_-]?key"
    )

    # Search for secret patterns
    for pattern in "${patterns[@]}"; do
        while IFS=: read -r file line_num content; do
            # Skip if in .git or node_modules
            if [[ "$file" =~ \.git/ ]] || [[ "$file" =~ node_modules/ ]]; then
                continue
            fi

            findings+=("{\"file\":\"$file\",\"line\":$line_num,\"pattern\":\"$pattern\",\"content\":\"$(echo "$content" | sed 's/"/\\"/g' | head -c 100)...\"}")
            ((count++))
        done < <(grep -rn -iE "$pattern" "$PROJECT_ROOT" 2>/dev/null || true)

        if [[ "$quick_mode" == "true" && "$count" -gt 50 ]]; then
            break
        fi
    done

    # Check for .env files
    while IFS= read -r env_file; do
        findings+=("{\"file\":\"$env_file\",\"type\":\"env_file\",\"severity\":\"high\",\"message\":\"Environment file detected - verify not in version control\"}")
        ((count++))
    done < <(find "$PROJECT_ROOT" -name ".env*" -type f 2>/dev/null || true)

    # Generate JSON output
    local json_findings="[]"
    if [[ ${#findings[@]} -gt 0 ]]; then
        json_findings=$(printf '%s\n' "${findings[@]}" | jq -s '.' 2>/dev/null || echo "[]")
    fi

    cat > "$output_file" << EOF
{
    "scan_type": "secret_detection",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "findings_count": $count,
    "findings": $json_findings
}
EOF

    echo "  Found $count potential secrets" >&2
    echo "$count"
}

scan_vulnerabilities() {
    local output_file="$1"
    local quick_mode="${2:-false}"

    echo -e "${BLUE}Scanning for known vulnerabilities...${NC}" >&2

    local npm_vulns=0
    local pip_vulns=0
    local findings=()

    # Check for package.json and run npm audit
    if [[ -f "$PROJECT_ROOT/package.json" ]]; then
        echo "  Checking npm dependencies..." >&2
        local npm_audit_output=$(cd "$PROJECT_ROOT" && npm audit --json 2>/dev/null || echo '{"vulnerabilities":{}}')
        npm_vulns=$(echo "$npm_audit_output" | jq -r '.metadata.vulnerabilities.total // 0' 2>/dev/null || echo "0")

        # Extract high and critical vulnerabilities
        if [[ "$npm_vulns" -gt 0 ]]; then
            local npm_findings=$(echo "$npm_audit_output" | jq -r '
                .vulnerabilities | to_entries[] | select(.value.severity == "high" or .value.severity == "critical") |
                {
                    package: .key,
                    severity: .value.severity,
                    title: .value.via[0].title // "Unknown",
                    range: .value.range,
                    fixAvailable: .value.fixAvailable
                }
            ' 2>/dev/null || echo "{}")

            findings+=("$npm_findings")
        fi
    fi

    # Check for requirements.txt and run pip-audit (if available)
    if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
        echo "  Checking Python dependencies..." >&2
        if command -v pip-audit &> /dev/null; then
            local pip_audit_output=$(cd "$PROJECT_ROOT" && pip-audit -r requirements.txt --format json 2>/dev/null || echo '{"vulnerabilities":[]}')
            pip_vulns=$(echo "$pip_audit_output" | jq '.vulnerabilities | length' 2>/dev/null || echo "0")

            if [[ "$pip_vulns" -gt 0 ]]; then
                local pip_findings=$(echo "$pip_audit_output" | jq -r '
                    .vulnerabilities[] |
                    {
                        package: .name,
                        version: .version,
                        id: .id,
                        description: .description,
                        fix_versions: .fix_versions
                    }
                ' 2>/dev/null || echo "{}")

                findings+=("$pip_findings")
            fi
        else
            echo "  pip-audit not found, skipping Python vulnerability scan" >&2
        fi
    fi

    local total_vulns=$((npm_vulns + pip_vulns))

    # Generate JSON output
    local json_findings="[]"
    if [[ ${#findings[@]} -gt 0 ]]; then
        json_findings=$(printf '%s\n' "${findings[@]}" | jq -s '.' 2>/dev/null || echo "[]")
    fi

    cat > "$output_file" << EOF
{
    "scan_type": "vulnerability_detection",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "npm_vulnerabilities": $npm_vulns,
    "python_vulnerabilities": $pip_vulns,
    "total_vulnerabilities": $total_vulns,
    "findings": $json_findings
}
EOF

    echo "  Found $total_vulns vulnerabilities (npm: $npm_vulns, python: $pip_vulns)" >&2
    echo "$total_vulns"
}

scan_dependencies() {
    local output_file="$1"
    local quick_mode="${2:-false}"

    echo -e "${BLUE}Auditing dependencies...${NC}" >&2

    local outdated_count=0
    local deprecated_count=0
    local findings=()

    # Check npm dependencies
    if [[ -f "$PROJECT_ROOT/package.json" ]]; then
        echo "  Checking npm packages..." >&2

        # Get outdated packages
        if [[ "$quick_mode" == "false" ]]; then
            local outdated=$(cd "$PROJECT_ROOT" && npm outdated --json 2>/dev/null || echo '{}')
            outdated_count=$(echo "$outdated" | jq 'keys | length' 2>/dev/null || echo "0")

            if [[ "$outdated_count" -gt 0 ]]; then
                findings+=("$(echo "$outdated" | jq -c '.')")
            fi
        fi
    fi

    # Check Python dependencies
    if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
        echo "  Checking Python packages..." >&2

        if command -v pip &> /dev/null && [[ "$quick_mode" == "false" ]]; then
            # List outdated packages
            local pip_outdated=$(pip list --outdated --format json 2>/dev/null || echo '[]')
            local pip_outdated_count=$(echo "$pip_outdated" | jq 'length' 2>/dev/null || echo "0")
            outdated_count=$((outdated_count + pip_outdated_count))

            if [[ "$pip_outdated_count" -gt 0 ]]; then
                findings+=("$(echo "$pip_outdated" | jq -c '.')")
            fi
        fi
    fi

    # Generate JSON output
    local json_findings="[]"
    if [[ ${#findings[@]} -gt 0 ]]; then
        json_findings=$(printf '%s\n' "${findings[@]}" | jq -s '.' 2>/dev/null || echo "[]")
    fi

    cat > "$output_file" << EOF
{
    "scan_type": "dependency_audit",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "outdated_packages": $outdated_count,
    "deprecated_packages": $deprecated_count,
    "findings": $json_findings,
    "quick_mode": $quick_mode
}
EOF

    echo "  Found $outdated_count outdated packages" >&2
    echo "$outdated_count"
}

scan_insecure_code() {
    local output_file="$1"
    local quick_mode="${2:-false}"

    echo -e "${BLUE}Scanning for insecure code patterns...${NC}" >&2

    local findings=()
    local count=0

    # Insecure code patterns
    local patterns=(
        "eval\("                              # Code injection
        "exec\("                              # Code execution
        "os\.system\("                        # Shell injection
        "subprocess\.call\(.*shell=True"      # Shell injection
        "innerHTML\s*="                       # XSS
        "dangerouslySetInnerHTML"            # React XSS
        "md5\("                              # Weak crypto
        "sha1\("                             # Weak crypto
        "__import__\("                       # Dynamic imports
    )

    for pattern in "${patterns[@]}"; do
        while IFS=: read -r file line_num content; do
            # Skip if in .git, node_modules, or test files
            if [[ "$file" =~ \.git/ ]] || [[ "$file" =~ node_modules/ ]] || [[ "$file" =~ test/ ]]; then
                continue
            fi

            findings+=("{\"file\":\"$file\",\"line\":$line_num,\"pattern\":\"$pattern\",\"content\":\"$(echo "$content" | sed 's/"/\\"/g' | head -c 100)...\"}")
            ((count++))
        done < <(grep -rn -E "$pattern" "$PROJECT_ROOT" --include="*.py" --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" 2>/dev/null || true)

        if [[ "$quick_mode" == "true" && "$count" -gt 50 ]]; then
            break
        fi
    done

    # Generate JSON output
    local json_findings="[]"
    if [[ ${#findings[@]} -gt 0 ]]; then
        json_findings=$(printf '%s\n' "${findings[@]}" | jq -s '.' 2>/dev/null || echo "[]")
    fi

    cat > "$output_file" << EOF
{
    "scan_type": "insecure_code_patterns",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "findings_count": $count,
    "findings": $json_findings
}
EOF

    echo "  Found $count potentially insecure code patterns" >&2
    echo "$count"
}

# ==============================================================================
# MAIN WORKFLOW
# ==============================================================================

run_security_scan() {
    local quick_mode="${1:-false}"
    local scan_dir=""

    # Create timestamped scan directory
    scan_dir="$SCANS_DIR/scan-$(timestamp)"
    mkdir -p "$scan_dir"

    echo -e "${GREEN}Scan directory: $scan_dir${NC}" >&2
    echo "" >&2

    local start_time=$(date +%s)

    # Run scans
    local secrets_count=$(scan_secrets "$scan_dir/secrets.json" "$quick_mode")
    echo "" >&2

    local vuln_count=$(scan_vulnerabilities "$scan_dir/vulnerabilities.json" "$quick_mode")
    echo "" >&2

    if [[ "$quick_mode" == "false" ]]; then
        local dep_count=$(scan_dependencies "$scan_dir/dependencies.json" "$quick_mode")
        echo "" >&2
    else
        echo -e "${YELLOW}Skipping dependency audit in quick mode${NC}" >&2
        echo "" >&2
        dep_count=0
    fi

    local insecure_count=$(scan_insecure_code "$scan_dir/insecure-code.json" "$quick_mode")
    echo "" >&2

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Calculate severity levels
    local critical=0
    local high=0
    local medium=0
    local low=0

    # Secrets are high severity
    high=$((high + secrets_count))

    # Vulnerabilities vary
    if [[ -f "$scan_dir/vulnerabilities.json" ]]; then
        local vuln_high=$(jq -r '.findings[] | select(.severity == "high" or .severity == "critical") | .package' "$scan_dir/vulnerabilities.json" 2>/dev/null | wc -l | tr -d ' ')
        high=$((high + vuln_high))
    fi

    # Insecure code patterns are medium
    medium=$((medium + insecure_count))

    # Generate summary
    cat > "$scan_dir/summary.json" << EOF
{
    "scan_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "duration_seconds": $duration,
    "quick_mode": $quick_mode,
    "total_findings": $((secrets_count + vuln_count + insecure_count)),
    "findings": {
        "secrets": $secrets_count,
        "vulnerabilities": $vuln_count,
        "outdated_dependencies": $dep_count,
        "insecure_code_patterns": $insecure_count
    },
    "severity": {
        "critical": $critical,
        "high": $high,
        "medium": $medium,
        "low": $low
    },
    "scan_directory": "$scan_dir"
}
EOF

    echo "$scan_dir"
}

generate_report() {
    local scan_dir="$1"

    if [[ ! -f "$scan_dir/summary.json" ]]; then
        echo -e "${RED}No summary found in $scan_dir${NC}"
        return 1
    fi

    echo -e "${BLUE}${BOLD}=== Security Scan Report ===${NC}"
    echo ""

    local timestamp=$(jq -r '.scan_timestamp' "$scan_dir/summary.json")
    local duration=$(jq -r '.duration_seconds' "$scan_dir/summary.json")
    local total=$(jq -r '.total_findings' "$scan_dir/summary.json")

    echo -e "  ${BOLD}Scan Date:${NC} $timestamp"
    echo -e "  ${BOLD}Duration:${NC} ${duration}s"
    echo -e "  ${BOLD}Total Findings:${NC} $total"
    echo ""

    echo -e "${BOLD}Findings by Category:${NC}"
    jq -r '.findings | to_entries | .[] | "  \(.key): \(.value)"' "$scan_dir/summary.json"
    echo ""

    echo -e "${BOLD}Severity Distribution:${NC}"
    jq -r '.severity | to_entries | .[] | "  \(.key): \(.value)"' "$scan_dir/summary.json"
    echo ""

    # Show critical/high findings
    local high_count=$(jq -r '.severity.high' "$scan_dir/summary.json")
    if [[ "$high_count" -gt 0 ]]; then
        echo -e "${RED}${BOLD}High Severity Findings:${NC}"

        if [[ -f "$scan_dir/secrets.json" ]]; then
            local secret_count=$(jq -r '.findings_count' "$scan_dir/secrets.json")
            if [[ "$secret_count" -gt 0 ]]; then
                echo -e "  ${YELLOW}Secrets detected: $secret_count${NC}"
            fi
        fi

        if [[ -f "$scan_dir/vulnerabilities.json" ]]; then
            local vuln_count=$(jq -r '.total_vulnerabilities' "$scan_dir/vulnerabilities.json")
            if [[ "$vuln_count" -gt 0 ]]; then
                echo -e "  ${YELLOW}Known vulnerabilities: $vuln_count${NC}"
            fi
        fi
        echo ""
    fi
}

run_security_master() {
    local do_scan=true
    local do_report=false
    local quick_mode=false
    local use_latest=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --quick)
                quick_mode=true
                shift
                ;;
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

    # Run scan or get latest
    if [[ "$do_scan" == "true" ]]; then
        echo -e "${BLUE}${BOLD}Running Security Scan${NC}"
        if [[ "$quick_mode" == "true" ]]; then
            echo -e "${YELLOW}Quick mode enabled - skipping deep analysis${NC}"
        fi
        echo ""

        scan_dir=$(run_security_scan "$quick_mode")
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

    # Generate report if requested
    if [[ "$do_report" == "true" ]]; then
        generate_report "$scan_dir"
    fi

    # Print final summary
    echo ""
    echo -e "${GREEN}${BOLD}=== Security Master Complete ===${NC}"
    echo ""
    echo -e "  Scan results: ${CYAN}$scan_dir${NC}"
    echo ""

    if [[ -f "$scan_dir/summary.json" ]]; then
        echo -e "  ${BOLD}Summary:${NC}"
        jq -r '.findings | to_entries | .[] | "    \(.key): \(.value)"' "$scan_dir/summary.json" 2>/dev/null || true
        echo ""

        local total=$(jq -r '.total_findings' "$scan_dir/summary.json" 2>/dev/null || echo "0")
        if [[ "$total" -gt 0 ]]; then
            echo -e "  ${BOLD}${YELLOW}Action Required:${NC}"
            echo "    - Review findings in $scan_dir/"
            echo "    - Run '$0 --report' for detailed report"
            echo "    - Address high-severity issues first"
        else
            echo -e "  ${BOLD}${GREEN}No security issues found${NC}"
        fi
    fi
    echo ""
}

# ==============================================================================
# ENTRY POINT
# ==============================================================================

run_security_master "$@"
