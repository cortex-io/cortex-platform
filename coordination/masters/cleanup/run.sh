#!/usr/bin/env bash
# Cleanup Master - Main Entry Point
#
# Usage:
#   ./run.sh                    # Run full orchestration (inventory + cleanup)
#   ./run.sh --auto-fix         # Orchestrated scan + auto-fix (dry run)
#   ./run.sh --auto-fix --live  # Orchestrated scan + auto-fix (apply changes)
#   ./run.sh --cleanup-only     # Run cleanup without inventory (legacy mode)
#   ./run.sh --report           # Generate report from latest scan
#   ./run.sh --help             # Show this help

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ==============================================================================
# ORCHESTRATION DELEGATION
# ==============================================================================
# If not already in orchestration mode, delegate to the orchestrator
# This ensures inventory runs first for protected files list

ORCHESTRATOR="$SCRIPT_DIR/../orchestrator.sh"

if [[ -z "${ORCHESTRATION_MODE:-}" && -x "$ORCHESTRATOR" ]]; then
    # Check if --cleanup-only flag was passed (skip orchestration)
    CLEANUP_ONLY=false
    for arg in "$@"; do
        if [[ "$arg" == "--cleanup-only" ]]; then
            CLEANUP_ONLY=true
            break
        fi
    done

    if [[ "$CLEANUP_ONLY" == "false" ]]; then
        # Build orchestrator args from our args
        ORCH_ARGS=""
        for arg in "$@"; do
            case "$arg" in
                --auto-fix) ORCH_ARGS="$ORCH_ARGS --auto-fix" ;;
                --live)     ORCH_ARGS="$ORCH_ARGS --live" ;;
                --quick)    ORCH_ARGS="$ORCH_ARGS --quick" ;;
                --parallel) ORCH_ARGS="$ORCH_ARGS --parallel" ;;
            esac
        done

        echo "Delegating to Master Orchestrator (inventory + cleanup)..."
        echo "Use --cleanup-only to skip inventory phase"
        echo ""
        exec "$ORCHESTRATOR" $ORCH_ARGS
    fi
fi

# Mark that we're in orchestration mode (prevent recursion)
export ORCHESTRATION_MODE=1

# Load lib scripts
source "$SCRIPT_DIR/lib/scanner.sh"
source "$SCRIPT_DIR/lib/analyzer.sh"
source "$SCRIPT_DIR/lib/auto-fix.sh"

# Configuration
SCANS_DIR="$SCRIPT_DIR/scans"
CONFIG_FILE="$SCRIPT_DIR/config/cleanup-rules.json"

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
    echo "   ║                    CLEANUP MASTER                              ║"
    echo "   ║        Dead Code Detection • Pattern Analysis • Auto-Fix       ║"
    echo "   ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    print_banner
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --scan-only       Run scan without analysis (faster)"
    echo "  --analyze-only    Run analysis on latest scan"
    echo "  --auto-fix        Run auto-fix after scan and analysis"
    echo "  --live            Apply changes (without this, runs in dry-run mode)"
    echo "  --report          Generate human-readable report"
    echo "  --latest          Use latest scan instead of running new one"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Full scan + analysis (dry run)"
    echo "  $0 --auto-fix               # Full scan + analysis + auto-fix preview"
    echo "  $0 --auto-fix --live        # Full scan + analysis + apply fixes"
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
# MAIN WORKFLOW
# ==============================================================================

run_cleanup_master() {
    local do_scan=true
    local do_analyze=true
    local do_autofix=false
    local do_report=false
    local live_mode=false
    local use_latest=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --scan-only)
                do_analyze=false
                do_autofix=false
                shift
                ;;
            --analyze-only)
                do_scan=false
                use_latest=true
                shift
                ;;
            --auto-fix)
                do_autofix=true
                shift
                ;;
            --live)
                live_mode=true
                shift
                ;;
            --report)
                do_report=true
                do_scan=false
                do_analyze=false
                do_autofix=false
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
            --cleanup-only)
                # Already in orchestration mode, just continue
                shift
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

    # Step 1: Run scan (or get latest)
    if [[ "$do_scan" == "true" ]]; then
        echo -e "${BLUE}${BOLD}Step 1/3: Running Full Scan${NC}"
        echo ""
        scan_dir=$(run_full_scan "$SCANS_DIR")
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

    # Step 2: Run analysis
    if [[ "$do_analyze" == "true" ]]; then
        echo -e "${BLUE}${BOLD}Step 2/3: Running Pattern Analysis${NC}"
        echo ""
        run_full_analysis "$SCANS_DIR"
        echo ""
    fi

    # Step 3: Run auto-fix
    if [[ "$do_autofix" == "true" ]]; then
        echo -e "${BLUE}${BOLD}Step 3/3: Running Auto-Fix${NC}"

        if [[ "$live_mode" == "true" ]]; then
            echo -e "${RED}${BOLD}WARNING: LIVE MODE - Changes will be applied!${NC}"
            echo ""
            read -p "Are you sure you want to continue? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted."
                exit 0
            fi
            run_auto_fix "$scan_dir" "false"
        else
            echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}"
            echo ""
            run_auto_fix "$scan_dir" "true"
        fi
        echo ""
    fi

    # Step 4: Generate report
    if [[ "$do_report" == "true" ]]; then
        if [[ -z "$scan_dir" ]]; then
            scan_dir=$(get_latest_scan)
        fi

        if [[ -z "$scan_dir" || ! -d "$scan_dir" ]]; then
            echo -e "${RED}No scan found. Run a scan first.${NC}"
            exit 1
        fi

        "$SCRIPT_DIR/report.sh" "$scan_dir"
    fi

    # Print final summary
    echo ""
    echo -e "${GREEN}${BOLD}=== Cleanup Master Complete ===${NC}"
    echo ""
    echo -e "  Scan results: ${CYAN}$scan_dir${NC}"
    echo ""

    if [[ -f "$scan_dir/summary.json" ]]; then
        echo -e "  ${BOLD}Summary:${NC}"
        jq -r '.summary | to_entries | .[] | "    \(.key): \(.value)"' "$scan_dir/summary.json" 2>/dev/null || true
        echo ""
    fi

    echo -e "  ${BOLD}Next steps:${NC}"
    echo "    - Review scan results in $scan_dir/"
    echo "    - Run '$0 --report' for detailed report"
    if [[ "$do_autofix" == "false" ]]; then
        echo "    - Run '$0 --auto-fix' to preview fixes"
        echo "    - Run '$0 --auto-fix --live' to apply fixes"
    fi
    echo ""
}

# ==============================================================================
# ENTRY POINT
# ==============================================================================

run_cleanup_master "$@"
