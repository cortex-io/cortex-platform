#!/usr/bin/env bash
# Cleanup Master - Report Generator
#
# Generates human-readable reports from scan results
#
# Usage:
#   ./report.sh                    # Report from latest scan
#   ./report.sh <scan-dir>         # Report from specific scan
#   ./report.sh --json             # Output as JSON
#   ./report.sh --markdown         # Output as Markdown

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Configuration
SCANS_DIR="$SCRIPT_DIR/scans"
CONFIG_FILE="$SCRIPT_DIR/config/cleanup-rules.json"
MAX_ITEMS=50

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'
DIM='\033[2m'

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

get_latest_scan() {
    local latest=$(ls -t "$SCANS_DIR" 2>/dev/null | grep "^scan-" | head -1)
    if [[ -n "$latest" ]]; then
        echo "$SCANS_DIR/$latest"
    else
        echo ""
    fi
}

print_header() {
    local title="$1"
    local count="${2:-}"

    echo ""
    echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [[ -n "$count" ]]; then
        echo -e "${BLUE}${BOLD}  $title ${DIM}($count items)${NC}"
    else
        echo -e "${BLUE}${BOLD}  $title${NC}"
    fi
    echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_subheader() {
    local title="$1"
    echo ""
    echo -e "  ${CYAN}${BOLD}$title${NC}"
    echo -e "  ${DIM}────────────────────────────────────────────${NC}"
}

print_item() {
    local icon="$1"
    local text="$2"
    echo -e "    $icon $text"
}

severity_icon() {
    local severity="$1"
    case "$severity" in
        critical|high)   echo -e "${RED}●${NC}" ;;
        medium)          echo -e "${YELLOW}●${NC}" ;;
        low)             echo -e "${GREEN}●${NC}" ;;
        *)               echo -e "${DIM}○${NC}" ;;
    esac
}

# ==============================================================================
# REPORT SECTIONS
# ==============================================================================

report_summary() {
    local scan_dir="$1"

    if [[ ! -f "$scan_dir/summary.json" ]]; then
        echo -e "${RED}No summary found${NC}"
        return
    fi

    print_header "SCAN SUMMARY"

    local scan_id=$(jq -r '.scan_id' "$scan_dir/summary.json")
    local timestamp=$(jq -r '.timestamp' "$scan_dir/summary.json")
    local total=$(jq -r '.summary.total_issues // 0' "$scan_dir/summary.json")

    echo ""
    echo -e "  ${BOLD}Scan ID:${NC}     $scan_id"
    echo -e "  ${BOLD}Timestamp:${NC}   $timestamp"
    echo -e "  ${BOLD}Total Issues:${NC} $total"
    echo ""

    # Issue breakdown
    echo -e "  ${BOLD}Issue Breakdown:${NC}"
    echo ""

    local categories=(
        "unreferenced_files:Unreferenced Files"
        "dead_functions:Dead Functions"
        "empty_directories:Empty Directories"
        "permission_issues:Permission Issues"
        "duplicate_files:Duplicate Files"
        "broken_references:Broken References"
        "legacy_api_calls:Legacy API Calls"
        "legacy_patterns:Legacy Patterns"
        "gitignore_issues:Gitignore Issues"
    )

    for cat in "${categories[@]}"; do
        local key=$(echo "$cat" | cut -d: -f1)
        local label=$(echo "$cat" | cut -d: -f2)
        local count=$(jq -r ".summary.$key // 0" "$scan_dir/summary.json")

        local icon
        if [[ $count -eq 0 ]]; then
            icon="${GREEN}✓${NC}"
        elif [[ $count -lt 5 ]]; then
            icon="${YELLOW}!${NC}"
        else
            icon="${RED}✗${NC}"
        fi

        printf "    $icon %-25s %s\n" "$label:" "$count"
    done
}

report_unreferenced_files() {
    local scan_dir="$1"
    local file="$scan_dir/unreferenced-files.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "UNREFERENCED FILES" "$count"

    print_subheader "Files not referenced anywhere in the codebase"

    jq -r ".files[:$MAX_ITEMS][]" "$file" 2>/dev/null | while read -r f; do
        print_item "$(severity_icon low)" "${DIM}$f${NC}"
    done

    if [[ $count -gt $MAX_ITEMS ]]; then
        echo ""
        echo -e "    ${DIM}... and $((count - MAX_ITEMS)) more${NC}"
    fi
}

report_dead_functions() {
    local scan_dir="$1"
    local file="$scan_dir/dead-functions.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "DEAD FUNCTIONS" "$count"

    print_subheader "Functions defined but never called"

    jq -r ".functions[:$MAX_ITEMS][] | \"\\(.file):\\(.function)\"" "$file" 2>/dev/null | while read -r line; do
        local f=$(echo "$line" | cut -d: -f1)
        local func=$(echo "$line" | cut -d: -f2)
        print_item "$(severity_icon low)" "${DIM}$f${NC}: ${YELLOW}$func()${NC}"
    done
}

report_permission_issues() {
    local scan_dir="$1"
    local file="$scan_dir/permission-issues.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "PERMISSION ISSUES" "$count"

    print_subheader "Scripts not executable"
    jq -r ".issues[:$MAX_ITEMS][] | select(.issue == \"not_executable\") | .file" "$file" 2>/dev/null | while read -r f; do
        print_item "$(severity_icon medium)" "$f ${RED}(needs +x)${NC}"
    done

    print_subheader "Files that should not be executable"
    jq -r ".issues[:$MAX_ITEMS][] | select(.issue == \"should_not_be_executable\") | .file" "$file" 2>/dev/null | while read -r f; do
        print_item "$(severity_icon low)" "$f ${YELLOW}(remove +x)${NC}"
    done
}

report_duplicate_files() {
    local scan_dir="$1"
    local file="$scan_dir/duplicate-files.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "DUPLICATE FILES" "$count"

    print_subheader "Files with identical content"

    jq -r ".duplicates[:$MAX_ITEMS][] | \"\\(.original) == \\(.duplicate)\"" "$file" 2>/dev/null | while read -r line; do
        local orig=$(echo "$line" | cut -d= -f1 | tr -d ' ')
        local dup=$(echo "$line" | cut -d= -f2 | tr -d ' ')
        print_item "$(severity_icon medium)" "${DIM}$orig${NC}"
        echo -e "        ${DIM}duplicate:${NC} ${YELLOW}$dup${NC}"
    done
}

report_broken_references() {
    local scan_dir="$1"
    local file="$scan_dir/broken-references.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "BROKEN REFERENCES" "$count"

    print_subheader "Files referencing non-existent resources"

    jq -r ".references[:$MAX_ITEMS][] | \"\\(.file)|\\(.missing_reference)|\\(.type)\"" "$file" 2>/dev/null | while IFS='|' read -r f ref type; do
        print_item "$(severity_icon high)" "$f"
        echo -e "        ${RED}missing:${NC} $ref ${DIM}($type)${NC}"
    done
}

report_legacy_patterns() {
    local scan_dir="$1"
    local file="$scan_dir/legacy-patterns.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "LEGACY PATTERNS" "$count"

    print_subheader "Deprecated code patterns found"

    jq -r ".findings[:$MAX_ITEMS][] | \"\\(.file):\\(.line)|\\(.pattern)|\\(.description)\"" "$file" 2>/dev/null | while IFS='|' read -r loc pattern desc; do
        print_item "$(severity_icon medium)" "${DIM}$loc${NC}"
        echo -e "        ${YELLOW}$pattern${NC}: $desc"
    done
}

report_legacy_api_calls() {
    local scan_dir="$1"
    local file="$scan_dir/legacy-api-calls.json"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local count=$(jq -r '.count // 0' "$file")
    [[ $count -eq 0 ]] && return

    print_header "LEGACY API CALLS" "$count"

    print_subheader "References to deprecated API endpoints"

    jq -r ".findings[:$MAX_ITEMS][] | \"\\(.file):\\(.line)|\\(.pattern)\"" "$file" 2>/dev/null | while IFS='|' read -r loc pattern; do
        print_item "$(severity_icon medium)" "${DIM}$loc${NC}: ${YELLOW}$pattern${NC}"
    done
}

report_recommendations() {
    local scan_dir="$1"

    print_header "RECOMMENDATIONS"

    echo ""
    echo -e "  ${BOLD}Immediate Actions (High Priority):${NC}"

    # Check for high-priority issues
    local broken=$(jq -r '.summary.broken_references // 0' "$scan_dir/summary.json" 2>/dev/null)
    local perms=$(jq -r '.summary.permission_issues // 0' "$scan_dir/summary.json" 2>/dev/null)

    if [[ $broken -gt 0 ]]; then
        echo -e "    ${RED}1.${NC} Fix $broken broken references - these may cause runtime errors"
    fi

    if [[ $perms -gt 0 ]]; then
        echo -e "    ${YELLOW}2.${NC} Fix $perms permission issues - run: ./run.sh --auto-fix --live"
    fi

    echo ""
    echo -e "  ${BOLD}Cleanup Actions (Medium Priority):${NC}"

    local dups=$(jq -r '.summary.duplicate_files // 0' "$scan_dir/summary.json" 2>/dev/null)
    local empty=$(jq -r '.summary.empty_directories // 0' "$scan_dir/summary.json" 2>/dev/null)
    local legacy=$(jq -r '.summary.legacy_patterns // 0' "$scan_dir/summary.json" 2>/dev/null)

    if [[ $dups -gt 0 ]]; then
        echo -e "    ${YELLOW}3.${NC} Remove $dups duplicate files to reduce confusion"
    fi

    if [[ $empty -gt 0 ]]; then
        echo -e "    ${DIM}4.${NC} Remove $empty empty directories"
    fi

    if [[ $legacy -gt 0 ]]; then
        echo -e "    ${YELLOW}5.${NC} Update $legacy legacy patterns to current standards"
    fi

    echo ""
    echo -e "  ${BOLD}Maintenance Actions (Low Priority):${NC}"

    local unref=$(jq -r '.summary.unreferenced_files // 0' "$scan_dir/summary.json" 2>/dev/null)
    local dead=$(jq -r '.summary.dead_functions // 0' "$scan_dir/summary.json" 2>/dev/null)

    if [[ $unref -gt 0 ]]; then
        echo -e "    ${DIM}6.${NC} Review $unref unreferenced files - may be safe to remove"
    fi

    if [[ $dead -gt 0 ]]; then
        echo -e "    ${DIM}7.${NC} Consider removing $dead dead functions"
    fi

    echo ""
    echo -e "  ${BOLD}Quick Fix Command:${NC}"
    echo -e "    ${CYAN}./run.sh --auto-fix --live${NC}"
    echo ""
}

# ==============================================================================
# OUTPUT FORMATS
# ==============================================================================

output_json() {
    local scan_dir="$1"

    if [[ -f "$scan_dir/summary.json" ]]; then
        cat "$scan_dir/summary.json"
    else
        echo "{\"error\": \"No scan summary found\"}"
    fi
}

output_markdown() {
    local scan_dir="$1"

    echo "# Cleanup Master Report"
    echo ""
    echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo ""

    if [[ -f "$scan_dir/summary.json" ]]; then
        echo "## Summary"
        echo ""
        echo "| Category | Count |"
        echo "|----------|-------|"

        jq -r '.summary | to_entries[] | "| \(.key) | \(.value) |"' "$scan_dir/summary.json"
        echo ""
    fi

    # Add sections for each issue type
    local files=(
        "unreferenced-files.json:Unreferenced Files"
        "dead-functions.json:Dead Functions"
        "permission-issues.json:Permission Issues"
        "broken-references.json:Broken References"
    )

    for item in "${files[@]}"; do
        local file=$(echo "$item" | cut -d: -f1)
        local title=$(echo "$item" | cut -d: -f2)

        if [[ -f "$scan_dir/$file" ]]; then
            local count=$(jq -r '.count // 0' "$scan_dir/$file")
            if [[ $count -gt 0 ]]; then
                echo "## $title ($count)"
                echo ""
                echo '```'
                jq -r '.files // .issues // .functions // .references | .[:20][]' "$scan_dir/$file" 2>/dev/null || true
                echo '```'
                echo ""
            fi
        fi
    done
}

output_terminal() {
    local scan_dir="$1"

    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "   ╔═══════════════════════════════════════════════════════════════╗"
    echo "   ║                CLEANUP MASTER - SCAN REPORT                    ║"
    echo "   ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    report_summary "$scan_dir"
    report_broken_references "$scan_dir"
    report_permission_issues "$scan_dir"
    report_duplicate_files "$scan_dir"
    report_legacy_patterns "$scan_dir"
    report_legacy_api_calls "$scan_dir"
    report_unreferenced_files "$scan_dir"
    report_dead_functions "$scan_dir"
    report_recommendations "$scan_dir"

    echo ""
    echo -e "${DIM}Report generated from: $scan_dir${NC}"
    echo ""
}

# ==============================================================================
# MAIN
# ==============================================================================

main() {
    local scan_dir=""
    local output_format="terminal"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_format="json"
                shift
                ;;
            --markdown|--md)
                output_format="markdown"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [scan-dir] [--json|--markdown]"
                echo ""
                echo "Options:"
                echo "  --json       Output as JSON"
                echo "  --markdown   Output as Markdown"
                echo "  --help       Show this help"
                exit 0
                ;;
            *)
                if [[ -d "$1" ]]; then
                    scan_dir="$1"
                else
                    echo "Error: Invalid scan directory: $1"
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Get scan directory
    if [[ -z "$scan_dir" ]]; then
        scan_dir=$(get_latest_scan)
    fi

    if [[ -z "$scan_dir" || ! -d "$scan_dir" ]]; then
        echo -e "${RED}No scan found. Run './run.sh' first.${NC}"
        exit 1
    fi

    # Generate report in requested format
    case "$output_format" in
        json)
            output_json "$scan_dir"
            ;;
        markdown)
            output_markdown "$scan_dir"
            ;;
        *)
            output_terminal "$scan_dir"
            ;;
    esac
}

main "$@"
