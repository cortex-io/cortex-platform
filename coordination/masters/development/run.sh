#!/usr/bin/env bash
# Development Master - Main Entry Point
#
# Usage:
#   ./run.sh                    # Run full development scan
#   ./run.sh --lint-only        # Run linting checks only
#   ./run.sh --complexity-only  # Run complexity analysis only
#   ./run.sh --quick            # Quick scan (skip heavy analysis)
#   ./run.sh --report           # Generate report from latest scan
#   ./run.sh --help             # Show this help

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load lib scripts (create if needed)
LIB_DIR="$SCRIPT_DIR/lib"
mkdir -p "$LIB_DIR"

# Configuration
SCANS_DIR="$SCRIPT_DIR/scans"

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "   ╔═══════════════════════════════════════════════════════════════╗"
    echo "   ║                  DEVELOPMENT MASTER                            ║"
    echo "   ║      Code Quality • Linting • Complexity • Best Practices      ║"
    echo "   ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    print_banner
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --lint-only         Run linting checks only"
    echo "  --complexity-only   Run complexity analysis only"
    echo "  --quick             Quick scan (skip heavy analysis)"
    echo "  --report            Generate human-readable report"
    echo "  --latest            Use latest scan instead of running new one"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Full development scan"
    echo "  $0 --lint-only              # Run linting checks only"
    echo "  $0 --quick                  # Quick scan"
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
# LINTING PATTERNS
# ==============================================================================

check_bash_patterns() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/bash-lint.json}"

    echo "Checking bash script patterns..." >&2

    local issues=()

    # Pattern 1: Missing set -euo pipefail
    while IFS= read -r file; do
        if ! head -20 "$file" | grep -q "set -euo pipefail"; then
            local relative_path="${file#$PROJECT_ROOT/}"
            issues+=("{\"file\": \"$relative_path\", \"issue\": \"missing_strict_mode\", \"line\": 1, \"severity\": \"warning\", \"message\": \"Script missing 'set -euo pipefail'\"}")
        fi
    done < <(find "$scan_dir" -type f -name "*.sh" 2>/dev/null | grep -v node_modules)

    # Pattern 2: Unquoted variables
    while IFS=: read -r file line_num line_content; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"
        local issue_detail=$(echo "$line_content" | grep -oE '\$[a-zA-Z_][a-zA-Z0-9_]*' | head -1)
        issues+=("{\"file\": \"$relative_path\", \"issue\": \"unquoted_variable\", \"line\": $line_num, \"severity\": \"info\", \"message\": \"Consider quoting variable: $issue_detail\"}")
    done < <(grep -rn '\$[a-zA-Z_][a-zA-Z0-9_]*[^{]' "$scan_dir" --include="*.sh" 2>/dev/null | grep -v '"\$' | head -20 || true)

    # Pattern 3: Missing function documentation
    while IFS= read -r file; do
        local func_count=$(grep -c "^[[:space:]]*\(function[[:space:]]\+\)\?[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*()[[:space:]]*{" "$file" 2>/dev/null || echo "0")
        func_count=$(echo "$func_count" | tr -d '\n' | xargs)
        local doc_count=$(grep -c "^#.*Args:\|^#.*Returns:" "$file" 2>/dev/null || echo "0")
        doc_count=$(echo "$doc_count" | tr -d '\n' | xargs)

        if [[ $func_count -gt 3 && $doc_count -eq 0 ]]; then
            local relative_path="${file#$PROJECT_ROOT/}"
            issues+=("{\"file\": \"$relative_path\", \"issue\": \"missing_documentation\", \"severity\": \"info\", \"message\": \"File has $func_count functions but no documentation\"}")
        fi
    done < <(find "$scan_dir" -type f -name "*.sh" 2>/dev/null | grep -v node_modules)

    echo "  Found ${#issues[@]} bash pattern issues" >&2

    # Generate JSON output
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${issues[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "bash_patterns",
                timestamp: $timestamp,
                count: (. | length),
                issues: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "bash_patterns",
                timestamp: $timestamp,
                count: 0,
                issues: []
            }' > "$results_file"
    fi

    echo "${#issues[@]}"
}

check_python_patterns() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/python-lint.json}"

    echo "Checking Python code patterns..." >&2

    local issues=()

    # Pattern 1: Missing docstrings
    while IFS= read -r file; do
        local func_count=$(grep -c "^def " "$file" 2>/dev/null || echo "0")
        func_count=$(echo "$func_count" | tr -d '\n' | xargs)
        local doc_count=$(grep -c "\"\"\"" "$file" 2>/dev/null || echo "0")
        doc_count=$(echo "$doc_count" | tr -d '\n' | xargs)

        if [[ $func_count -gt 2 && $doc_count -eq 0 ]]; then
            local relative_path="${file#$PROJECT_ROOT/}"
            issues+=("{\"file\": \"$relative_path\", \"issue\": \"missing_docstrings\", \"severity\": \"warning\", \"message\": \"File has $func_count functions but no docstrings\"}")
        fi
    done < <(find "$scan_dir" -type f -name "*.py" 2>/dev/null | grep -v -E '(node_modules|\.venv|__pycache__|site-packages)')

    # Pattern 2: Bare except clauses
    while IFS=: read -r file line_num line_content; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"
        issues+=("{\"file\": \"$relative_path\", \"issue\": \"bare_except\", \"line\": $line_num, \"severity\": \"warning\", \"message\": \"Bare except clause - specify exception type\"}")
    done < <(grep -rn "except:" "$scan_dir" --include="*.py" 2>/dev/null | grep -v "#" | head -20 || true)

    # Pattern 3: Print statements (should use logging)
    while IFS=: read -r file line_num line_content; do
        [[ -z "$file" ]] && continue
        # Skip if file is clearly a script or has __main__
        if grep -q "if __name__ == '__main__'" "$file" 2>/dev/null; then
            continue
        fi
        local relative_path="${file#$PROJECT_ROOT/}"
        issues+=("{\"file\": \"$relative_path\", \"issue\": \"print_statement\", \"line\": $line_num, \"severity\": \"info\", \"message\": \"Consider using logging instead of print\"}")
    done < <(grep -rn "print(" "$scan_dir" --include="*.py" 2>/dev/null | grep -v -E '(test_|__pycache__|\.venv)' | head -15 || true)

    echo "  Found ${#issues[@]} Python pattern issues" >&2

    # Generate JSON output
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${issues[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "python_patterns",
                timestamp: $timestamp,
                count: (. | length),
                issues: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "python_patterns",
                timestamp: $timestamp,
                count: 0,
                issues: []
            }' > "$results_file"
    fi

    echo "${#issues[@]}"
}

check_json_validity() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/json-validity.json}"

    echo "Checking JSON file validity..." >&2

    local issues=()

    while IFS= read -r file; do
        if ! jq empty "$file" 2>/dev/null; then
            local relative_path="${file#$PROJECT_ROOT/}"
            local error_msg=$(jq empty "$file" 2>&1 | head -1)
            issues+=("{\"file\": \"$relative_path\", \"issue\": \"invalid_json\", \"severity\": \"error\", \"message\": \"Invalid JSON: $error_msg\"}")
        fi
    done < <(find "$scan_dir" -type f -name "*.json" 2>/dev/null | grep -v -E '(node_modules|\.git|package-lock\.json)')

    echo "  Found ${#issues[@]} JSON validity issues" >&2

    # Generate JSON output
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${issues[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "json_validity",
                timestamp: $timestamp,
                count: (. | length),
                issues: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "json_validity",
                timestamp: $timestamp,
                count: 0,
                issues: []
            }' > "$results_file"
    fi

    echo "${#issues[@]}"
}

# ==============================================================================
# COMPLEXITY ANALYSIS
# ==============================================================================

analyze_script_complexity() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/complexity.json}"

    echo "Analyzing script complexity..." >&2

    local complex_files=()

    while IFS= read -r file; do
        local relative_path="${file#$PROJECT_ROOT/}"

        # Calculate metrics
        local lines=$(wc -l < "$file" | tr -d ' ')
        local functions=$(grep -c "^[[:space:]]*\(function[[:space:]]\+\)\?[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*()[[:space:]]*{" "$file" 2>/dev/null || echo "0")
        functions=$(echo "$functions" | tr -d '\n' | xargs)
        local conditionals=$(grep -c -E "if |while |for |case " "$file" 2>/dev/null || echo "0")
        conditionals=$(echo "$conditionals" | tr -d '\n' | xargs)
        local pipes=$(grep -c "|" "$file" 2>/dev/null || echo "0")
        pipes=$(echo "$pipes" | tr -d '\n' | xargs)

        # Calculate complexity score
        local score=0
        if [[ $lines -gt 500 ]]; then
            score=$((score + 3))
        elif [[ $lines -gt 200 ]]; then
            score=$((score + 2))
        elif [[ $lines -gt 100 ]]; then
            score=$((score + 1))
        fi

        if [[ $functions -gt 20 ]]; then
            score=$((score + 2))
        elif [[ $functions -gt 10 ]]; then
            score=$((score + 1))
        fi

        if [[ $conditionals -gt 30 ]]; then
            score=$((score + 2))
        elif [[ $conditionals -gt 15 ]]; then
            score=$((score + 1))
        fi

        # Only report files with complexity > 3
        if [[ $score -gt 3 ]]; then
            local level="moderate"
            if [[ $score -gt 5 ]]; then
                level="high"
            fi
            if [[ $score -gt 7 ]]; then
                level="very-high"
            fi

            complex_files+=("{\"file\": \"$relative_path\", \"lines\": $lines, \"functions\": $functions, \"conditionals\": $conditionals, \"complexity_score\": $score, \"complexity_level\": \"$level\"}")
        fi
    done < <(find "$scan_dir" -type f -name "*.sh" 2>/dev/null | grep -v node_modules)

    echo "  Found ${#complex_files[@]} complex files" >&2

    # Generate JSON output
    if [[ ${#complex_files[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${complex_files[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "complexity_analysis",
                timestamp: $timestamp,
                count: (. | length),
                files: . | sort_by(-.complexity_score)
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "complexity_analysis",
                timestamp: $timestamp,
                count: 0,
                files: []
            }' > "$results_file"
    fi

    echo "${#complex_files[@]}"
}

analyze_function_length() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/function-length.json}"

    echo "Analyzing function length..." >&2

    local long_functions=()

    while IFS= read -r file; do
        local relative_path="${file#$PROJECT_ROOT/}"

        # Extract functions and count their lines
        local in_function=0
        local func_name=""
        local func_start=0
        local func_lines=0

        while IFS= read -r line_num line_content; do
            # Detect function start
            if echo "$line_content" | grep -q "^[[:space:]]*\(function[[:space:]]\+\)\?[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*()[[:space:]]*{"; then
                func_name=$(echo "$line_content" | sed -E 's/.*function\s+([a-zA-Z_][a-zA-Z0-9_]*).*/\1/' | sed -E 's/.*([a-zA-Z_][a-zA-Z0-9_]*)\(\).*/\1/')
                func_start=$line_num
                func_lines=1
                in_function=1
            elif [[ $in_function -eq 1 ]]; then
                func_lines=$((func_lines + 1))

                # Detect function end (closing brace at start of line)
                if echo "$line_content" | grep -q "^}"; then
                    in_function=0

                    # Report if function is too long
                    if [[ $func_lines -gt 50 ]]; then
                        local severity="warning"
                        if [[ $func_lines -gt 100 ]]; then
                            severity="error"
                        fi
                        long_functions+=("{\"file\": \"$relative_path\", \"function\": \"$func_name\", \"start_line\": $func_start, \"length\": $func_lines, \"severity\": \"$severity\"}")
                    fi
                fi
            fi
        done < <(cat -n "$file")

    done < <(find "$scan_dir" -type f -name "*.sh" 2>/dev/null | grep -v node_modules | head -20)

    echo "  Found ${#long_functions[@]} long functions" >&2

    # Generate JSON output
    if [[ ${#long_functions[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${long_functions[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "function_length",
                timestamp: $timestamp,
                count: (. | length),
                functions: . | sort_by(-.length)
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "function_length",
                timestamp: $timestamp,
                count: 0,
                functions: []
            }' > "$results_file"
    fi

    echo "${#long_functions[@]}"
}

# ==============================================================================
# COMMON DEVELOPMENT ISSUES
# ==============================================================================

check_common_issues() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/common-issues.json}"

    echo "Checking for common development issues..." >&2

    local issues=()

    # Issue 1: TODO/FIXME comments
    while IFS=: read -r file line_num line_content; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"
        local marker=$(echo "$line_content" | grep -oE 'TODO|FIXME|XXX|HACK' | head -1)
        local comment=$(echo "$line_content" | sed 's/.*#//' | xargs)
        issues+=("{\"file\": \"$relative_path\", \"issue\": \"todo_comment\", \"line\": $line_num, \"marker\": \"$marker\", \"severity\": \"info\", \"message\": \"$comment\"}")
    done < <(grep -rn -E "TODO|FIXME|XXX|HACK" "$scan_dir" --include="*.sh" --include="*.py" --include="*.js" 2>/dev/null | head -30 || true)

    # Issue 2: Hardcoded credentials patterns
    while IFS=: read -r file line_num line_content; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"
        issues+=("{\"file\": \"$relative_path\", \"issue\": \"potential_credential\", \"line\": $line_num, \"severity\": \"warning\", \"message\": \"Potential hardcoded credential detected\"}")
    done < <(grep -rn -E "password[[:space:]]*=[[:space:]]*[\"']|api_key[[:space:]]*=[[:space:]]*[\"']|secret[[:space:]]*=[[:space:]]*[\"']" "$scan_dir" --include="*.sh" --include="*.py" --include="*.js" 2>/dev/null | grep -v -E '(test_|example|\.env\.example)' | head -10 || true)

    # Issue 3: Debugging statements left in code
    while IFS=: read -r file line_num line_content; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"
        issues+=("{\"file\": \"$relative_path\", \"issue\": \"debug_statement\", \"line\": $line_num, \"severity\": \"info\", \"message\": \"Debug statement found in code\"}")
    done < <(grep -rn -E "console\.log|debugger|import pdb|set -x" "$scan_dir" --include="*.sh" --include="*.py" --include="*.js" 2>/dev/null | head -15 || true)

    echo "  Found ${#issues[@]} common issues" >&2

    # Generate JSON output
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${issues[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "common_issues",
                timestamp: $timestamp,
                count: (. | length),
                issues: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "common_issues",
                timestamp: $timestamp,
                count: 0,
                issues: []
            }' > "$results_file"
    fi

    echo "${#issues[@]}"
}

# ==============================================================================
# MAIN SCAN
# ==============================================================================

run_full_scan() {
    local output_dir="${1:-$SCANS_DIR}"
    local quick_mode="${2:-false}"

    mkdir -p "$output_dir"

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local scan_id="scan-$timestamp"
    local scan_dir="$output_dir/$scan_id"

    mkdir -p "$scan_dir"

    echo "=== Development Master - Full Scan ===" >&2
    echo "Scan ID: $scan_id" >&2
    echo "" >&2

    # Run all scans
    local bash_issues=$(check_bash_patterns "$PROJECT_ROOT" "$scan_dir/bash-patterns.json")
    local python_issues=$(check_python_patterns "$PROJECT_ROOT" "$scan_dir/python-patterns.json")
    local json_issues=$(check_json_validity "$PROJECT_ROOT" "$scan_dir/json-validity.json")
    local complexity=$(analyze_script_complexity "$PROJECT_ROOT" "$scan_dir/complexity-analysis.json")

    local function_length=0
    if [[ "$quick_mode" != "true" ]]; then
        function_length=$(analyze_function_length "$PROJECT_ROOT" "$scan_dir/function-length.json")
    fi

    local common_issues=$(check_common_issues "$PROJECT_ROOT" "$scan_dir/common-issues.json")

    # Calculate totals
    local total_issues=$((bash_issues + python_issues + json_issues + common_issues))
    local total_complexity=$((complexity + function_length))

    # Generate summary
    jq -n \
        --arg scan_id "$scan_id" \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --argjson bash_issues "$bash_issues" \
        --argjson python_issues "$python_issues" \
        --argjson json_issues "$json_issues" \
        --argjson complexity "$complexity" \
        --argjson function_length "$function_length" \
        --argjson common_issues "$common_issues" \
        --argjson total_issues "$total_issues" \
        --argjson total_complexity "$total_complexity" \
        --argjson quick_mode "$([[ "$quick_mode" == "true" ]] && echo "true" || echo "false")" \
        '{
            scan_id: $scan_id,
            timestamp: $timestamp,
            quick_mode: $quick_mode,
            summary: {
                bash_pattern_issues: $bash_issues,
                python_pattern_issues: $python_issues,
                json_validity_issues: $json_issues,
                common_issues: $common_issues,
                total_code_issues: $total_issues,
                complex_files: $complexity,
                long_functions: $function_length,
                total_complexity_warnings: $total_complexity
            },
            findings: {
                errors: $json_issues,
                warnings: ($bash_issues + $python_issues),
                info: $common_issues
            },
            scan_directory: "'"$scan_dir"'"
        }' > "$scan_dir/summary.json"

    echo "" >&2
    echo "=== Scan Complete ===" >&2
    echo "Results: $scan_dir" >&2
    cat "$scan_dir/summary.json" | jq '.summary' >&2

    echo "$scan_dir"
}

# ==============================================================================
# MAIN WORKFLOW
# ==============================================================================

run_development_master() {
    local do_lint=true
    local do_complexity=true
    local do_issues=true
    local do_report=false
    local use_latest=false
    local quick_mode=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --lint-only)
                do_complexity=false
                do_issues=false
                shift
                ;;
            --complexity-only)
                do_lint=false
                do_issues=false
                shift
                ;;
            --quick)
                quick_mode=true
                shift
                ;;
            --report)
                do_report=true
                do_lint=false
                do_complexity=false
                do_issues=false
                shift
                ;;
            --latest)
                use_latest=true
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
    if [[ "$use_latest" == "true" ]]; then
        scan_dir=$(get_latest_scan)
        if [[ -z "$scan_dir" ]]; then
            echo -e "${RED}No existing scan found. Run without --latest first.${NC}"
            exit 1
        fi
        echo -e "${YELLOW}Using existing scan: $(basename "$scan_dir")${NC}"
        echo ""
    else
        echo -e "${BLUE}${BOLD}Running Development Quality Scan${NC}"
        echo ""
        scan_dir=$(run_full_scan "$SCANS_DIR" "$quick_mode")
        echo ""
    fi

    # Generate report if requested
    if [[ "$do_report" == "true" ]]; then
        if [[ -z "$scan_dir" ]]; then
            scan_dir=$(get_latest_scan)
        fi

        if [[ -z "$scan_dir" || ! -d "$scan_dir" ]]; then
            echo -e "${RED}No scan found. Run a scan first.${NC}"
            exit 1
        fi

        echo -e "${MAGENTA}${BOLD}=== Development Quality Report ===${NC}"
        echo ""

        if [[ -f "$scan_dir/summary.json" ]]; then
            echo -e "${BOLD}Summary:${NC}"
            jq -r '.summary | to_entries | .[] | "  \(.key): \(.value)"' "$scan_dir/summary.json"
            echo ""

            echo -e "${BOLD}Findings Breakdown:${NC}"
            jq -r '.findings | to_entries | .[] | "  \(.key): \(.value)"' "$scan_dir/summary.json"
            echo ""
        fi

        # Show top issues
        if [[ -f "$scan_dir/bash-patterns.json" ]]; then
            local bash_count=$(jq '.count' "$scan_dir/bash-patterns.json")
            if [[ $bash_count -gt 0 ]]; then
                echo -e "${YELLOW}Top Bash Issues:${NC}"
                jq -r '.issues[0:5] | .[] | "  \(.file):\(.line // "N/A") - \(.message)"' "$scan_dir/bash-patterns.json" || true
                echo ""
            fi
        fi

        if [[ -f "$scan_dir/complexity-analysis.json" ]]; then
            local complexity_count=$(jq '.count' "$scan_dir/complexity-analysis.json")
            if [[ $complexity_count -gt 0 ]]; then
                echo -e "${YELLOW}Most Complex Files:${NC}"
                jq -r '.files[0:5] | .[] | "  \(.file) - \(.lines) lines, \(.functions) functions, complexity: \(.complexity_level)"' "$scan_dir/complexity-analysis.json" || true
                echo ""
            fi
        fi
    fi

    # Print final summary
    echo ""
    echo -e "${GREEN}${BOLD}=== Development Master Complete ===${NC}"
    echo ""
    echo -e "  Scan results: ${CYAN}$scan_dir${NC}"
    echo ""

    if [[ -f "$scan_dir/summary.json" ]]; then
        local total_issues=$(jq -r '.summary.total_code_issues' "$scan_dir/summary.json")
        local total_complexity=$(jq -r '.summary.total_complexity_warnings' "$scan_dir/summary.json")

        echo -e "  ${BOLD}Quality Metrics:${NC}"
        echo "    Code Issues: $total_issues"
        echo "    Complexity Warnings: $total_complexity"
        echo ""
    fi

    echo -e "  ${BOLD}Next steps:${NC}"
    echo "    - Review scan results in $scan_dir/"
    echo "    - Run '$0 --report' for detailed report"
    echo "    - Address high-severity issues first"
    echo ""
}

# ==============================================================================
# ENTRY POINT
# ==============================================================================

run_development_master "$@"
