#!/usr/bin/env bash
# Master Orchestrator - Coordinates all masters in sequence
#
# Usage:
#   ./orchestrator.sh              # Run inventory + cleanup in sequence
#   ./orchestrator.sh --auto-fix   # Run with auto-fix (dry run)
#   ./orchestrator.sh --auto-fix --live  # Run with auto-fix (apply changes)
#   ./orchestrator.sh --parallel   # Run masters in parallel where possible

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
AUTO_FIX=false
LIVE_MODE=false
PARALLEL_MODE=false
QUICK_MODE=false

# Shared data directory for inter-master communication
SHARED_DATA="$SCRIPT_DIR/shared-data"
mkdir -p "$SHARED_DATA"

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

print_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "   ╔═══════════════════════════════════════════════════════════════╗"
    echo "   ║              CORTEX MASTER ORCHESTRATOR                        ║"
    echo "   ║           Inventory → Analysis → Cleanup → Report              ║"
    echo "   ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_phase() {
    local phase="$1"
    local status="$2"
    local color="$BLUE"

    case "$status" in
        "start") color="$CYAN" ;;
        "done")  color="$GREEN" ;;
        "skip")  color="$YELLOW" ;;
        "fail")  color="$RED" ;;
    esac

    echo -e "${color}[ORCHESTRATOR]${NC} $phase"
}

run_master() {
    local name="$1"
    local script="$2"
    shift 2
    local args=()
    if [[ $# -gt 0 ]]; then
        args=("$@")
    fi

    if [[ ! -x "$script" ]]; then
        log_phase "$name" "skip"
        echo "  Script not found or not executable: $script"
        return 0
    fi

    log_phase "$name - Starting" "start"

    # Run the master with prefixed output
    if [[ ${#args[@]} -gt 0 ]]; then
        "$script" "${args[@]}" 2>&1 | sed "s/^/  [$name] /"
    else
        "$script" 2>&1 | sed "s/^/  [$name] /"
    fi

    if [[ $? -eq 0 ]]; then
        log_phase "$name - Complete" "done"
        return 0
    else
        log_phase "$name - Failed" "fail"
        return 1
    fi
}

# ==============================================================================
# PHASE 1: INVENTORY
# ==============================================================================

run_inventory() {
    log_phase "Phase 1: Inventory" "start"

    local inventory_script="$SCRIPT_DIR/inventory/run.sh"

    if [[ -x "$inventory_script" ]]; then
        # Run inventory and capture protected files list
        export INVENTORY_OUTPUT="$SHARED_DATA/inventory-results.json"
        export PROTECTED_FILES="$SHARED_DATA/protected-files.txt"

        if run_master "INVENTORY" "$inventory_script"; then
            # Export protected files for cleanup master
            export CLEANUP_PROTECTED_FILES="$PROTECTED_FILES"
            log_phase "Phase 1: Inventory - Complete" "done"
        else
            log_phase "Phase 1: Inventory - Failed (continuing)" "fail"
        fi
    else
        log_phase "Phase 1: Inventory - Skipped (no script)" "skip"
    fi
}

# ==============================================================================
# PHASE 2: CLEANUP
# ==============================================================================

run_cleanup() {
    log_phase "Phase 2: Cleanup" "start"

    local cleanup_script="$SCRIPT_DIR/cleanup/run.sh"
    local cleanup_args=("--cleanup-only")

    if [[ "$AUTO_FIX" == "true" ]]; then
        cleanup_args+=("--auto-fix")
    fi

    if [[ "$LIVE_MODE" == "true" ]]; then
        cleanup_args+=("--live")
    fi

    # Mark that we're in orchestration mode
    export ORCHESTRATION_MODE=1

    if run_master "CLEANUP" "$cleanup_script" "${cleanup_args[@]}"; then
        log_phase "Phase 2: Cleanup - Complete" "done"
    else
        log_phase "Phase 2: Cleanup - Failed" "fail"
    fi
}

# ==============================================================================
# SUMMARY
# ==============================================================================

print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}=== Orchestration Complete ===${NC}"
    echo ""

    # Inventory summary
    if [[ -f "$SHARED_DATA/inventory-results.json" ]]; then
        echo -e "  ${BOLD}Inventory Results:${NC}"
        jq -r 'to_entries | .[:5] | .[] | "    \(.key): \(.value)"' "$SHARED_DATA/inventory-results.json" 2>/dev/null || true
        echo ""
    fi

    # Cleanup summary
    local latest_scan=$(ls -t "$SCRIPT_DIR/cleanup/scans" 2>/dev/null | grep "^scan-" | head -1)
    if [[ -n "$latest_scan" && -f "$SCRIPT_DIR/cleanup/scans/$latest_scan/auto-fix-summary.json" ]]; then
        echo -e "  ${BOLD}Cleanup Results:${NC}"
        jq -r '.fixes[] | "    \(.type): \(.count)"' "$SCRIPT_DIR/cleanup/scans/$latest_scan/auto-fix-summary.json" 2>/dev/null || true
        echo -e "    ${CYAN}Total fixes: $(jq -r '.total_fixes' "$SCRIPT_DIR/cleanup/scans/$latest_scan/auto-fix-summary.json" 2>/dev/null)${NC}"
        echo ""
    fi

    echo -e "  ${BOLD}Shared Data:${NC} $SHARED_DATA"
    echo ""
}

# ==============================================================================
# MAIN
# ==============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --auto-fix)  AUTO_FIX=true; shift ;;
            --live)      LIVE_MODE=true; shift ;;
            --parallel)  PARALLEL_MODE=true; shift ;;
            --quick)     QUICK_MODE=true; shift ;;
            --help|-h)
                echo "Usage: $0 [--auto-fix] [--live] [--parallel] [--quick]"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    print_banner

    echo -e "  Mode: $([ "$AUTO_FIX" == "true" ] && echo "${YELLOW}Auto-Fix${NC}" || echo "Scan Only")"
    echo -e "  Live: $([ "$LIVE_MODE" == "true" ] && echo "${RED}Yes - Changes will be applied${NC}" || echo "${GREEN}No - Dry run${NC}")"
    echo ""

    # Run phases
    run_inventory
    run_cleanup

    # Print summary
    print_summary
}

main "$@"
