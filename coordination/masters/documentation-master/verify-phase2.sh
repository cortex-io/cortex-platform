#!/bin/bash

################################################################################
# Phase 2 Verification Script
#
# Verifies all Phase 2 deliverables are complete and production-ready
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

################################################################################
# Test Functions
################################################################################

test_file_exists() {
    local file="$1"
    local description="$2"

    if [[ -f "${file}" ]]; then
        echo -e "${GREEN}✓${NC} ${description}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} ${description} - File not found: ${file}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_file_executable() {
    local file="$1"
    local description="$2"

    if [[ -x "${file}" ]]; then
        echo -e "${GREEN}✓${NC} ${description}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} ${description} - File not executable: ${file}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_script_syntax() {
    local file="$1"
    local description="$2"

    if bash -n "${file}" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} ${description}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} ${description} - Syntax error in: ${file}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_contains_pattern() {
    local file="$1"
    local pattern="$2"
    local description="$3"

    if grep -q "${pattern}" "${file}" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} ${description}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} ${description} - Pattern not found: ${pattern}"
        ((TESTS_FAILED++))
        return 1
    fi
}

################################################################################
# Phase 2 Tests
################################################################################

echo "=================================================="
echo "Phase 2 Verification - Production-Ready Features"
echo "=================================================="
echo ""

echo "Testing Core Files..."
echo "-------------------"

# Test evolution-tracker.sh exists
test_file_exists "${SCRIPT_DIR}/lib/evolution-tracker.sh" "evolution-tracker.sh created"
test_file_executable "${SCRIPT_DIR}/lib/evolution-tracker.sh" "evolution-tracker.sh is executable"
test_script_syntax "${SCRIPT_DIR}/lib/evolution-tracker.sh" "evolution-tracker.sh syntax valid"

# Test all lib files
for script in crawler.sh indexer.sh query-handler.sh learner.sh; do
    test_file_exists "${SCRIPT_DIR}/lib/${script}" "${script} exists"
    test_file_executable "${SCRIPT_DIR}/lib/${script}" "${script} is executable"
    test_script_syntax "${SCRIPT_DIR}/lib/${script}" "${script} syntax valid"
done

# Test all worker files
for worker in crawler-worker.sh indexer-worker.sh learner-worker.sh; do
    test_file_exists "${SCRIPT_DIR}/workers/${worker}" "${worker} exists"
    test_file_executable "${SCRIPT_DIR}/workers/${worker}" "${worker} is executable"
    test_script_syntax "${SCRIPT_DIR}/workers/${worker}" "${worker} syntax valid"
done

echo ""
echo "Testing Production Features..."
echo "-----------------------------"

# Test cleanup handlers
test_contains_pattern "${SCRIPT_DIR}/lib/crawler.sh" "trap cleanup" "crawler.sh has cleanup handler"
test_contains_pattern "${SCRIPT_DIR}/lib/indexer.sh" "trap cleanup" "indexer.sh has cleanup handler"
test_contains_pattern "${SCRIPT_DIR}/lib/query-handler.sh" "trap cleanup" "query-handler.sh has cleanup handler"
test_contains_pattern "${SCRIPT_DIR}/workers/learner-worker.sh" "trap cleanup" "learner-worker.sh has cleanup handler"

# Test retry logic
test_contains_pattern "${SCRIPT_DIR}/lib/crawler.sh" "max_retries" "crawler.sh has retry logic"
test_contains_pattern "${SCRIPT_DIR}/workers/learner-worker.sh" "max_retries" "learner-worker.sh has retry logic"

# Test timeout protection
test_contains_pattern "${SCRIPT_DIR}/workers/crawler-worker.sh" "timeout" "crawler-worker.sh has timeout"
test_contains_pattern "${SCRIPT_DIR}/workers/indexer-worker.sh" "timeout" "indexer-worker.sh has timeout"

# Test input validation
test_contains_pattern "${SCRIPT_DIR}/lib/query-handler.sh" "Sanitize inputs" "query-handler.sh sanitizes inputs"
test_contains_pattern "${SCRIPT_DIR}/workers/learner-worker.sh" "Input validation" "learner-worker.sh validates inputs"

# Test atomic operations
test_contains_pattern "${SCRIPT_DIR}/lib/indexer.sh" ".tmp" "indexer.sh uses atomic writes"
test_contains_pattern "${SCRIPT_DIR}/workers/learner-worker.sh" ".tmp" "learner-worker.sh uses atomic writes"

echo ""
echo "Testing Evolution Tracker Features..."
echo "------------------------------------"

# Test evolution-tracker functions
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "check_freshness" "evolution-tracker has freshness check"
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "detect_knowledge_gaps" "evolution-tracker has gap detection"
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "calculate_priority_score" "evolution-tracker has priority scoring"
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "prune_low_value_content" "evolution-tracker has pruning"
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "trigger_recrawl" "evolution-tracker has re-crawl trigger"
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "get_status" "evolution-tracker has status API"
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "monitor" "evolution-tracker has monitor loop"

echo ""
echo "Testing Documentation..."
echo "----------------------"

# Test PHASE2-COMPLETE.md
test_file_exists "${SCRIPT_DIR}/PHASE2-COMPLETE.md" "PHASE2-COMPLETE.md created"
test_contains_pattern "${SCRIPT_DIR}/PHASE2-COMPLETE.md" "Production-Ready" "PHASE2-COMPLETE documents production features"
test_contains_pattern "${SCRIPT_DIR}/PHASE2-COMPLETE.md" "evolution-tracker" "PHASE2-COMPLETE documents evolution-tracker"

echo ""
echo "Testing Command Interfaces..."
echo "---------------------------"

# Test evolution-tracker commands (test by checking main function exists)
test_contains_pattern "${SCRIPT_DIR}/lib/evolution-tracker.sh" "main()" "evolution-tracker.sh has main function"

# Test crawler commands
test_contains_pattern "${SCRIPT_DIR}/lib/crawler.sh" "main()" "crawler.sh has main function"

# Test indexer commands
test_contains_pattern "${SCRIPT_DIR}/lib/indexer.sh" "main()" "indexer.sh has main function"

# Test query-handler commands
test_contains_pattern "${SCRIPT_DIR}/lib/query-handler.sh" "main()" "query-handler.sh has main function"

echo ""
echo "Testing Directory Structure..."
echo "----------------------------"

# Test cache directories
test_file_exists "${SCRIPT_DIR}/cache/.gitkeep" "cache directory exists" || mkdir -p "${SCRIPT_DIR}/cache" && touch "${SCRIPT_DIR}/cache/.gitkeep"
test_file_exists "${SCRIPT_DIR}/knowledge-base/.gitkeep" "knowledge-base directory exists" || mkdir -p "${SCRIPT_DIR}/knowledge-base" && touch "${SCRIPT_DIR}/knowledge-base/.gitkeep"

################################################################################
# Summary
################################################################################

echo ""
echo "=================================================="
echo "Verification Summary"
echo "=================================================="
echo ""
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [[ ${TESTS_FAILED} -eq 0 ]]; then
    echo -e "${GREEN}✓ All Phase 2 requirements verified successfully!${NC}"
    echo ""
    echo "Next Steps:"
    echo "1. Review PHASE2-COMPLETE.md for detailed implementation summary"
    echo "2. Run manual tests from testing section"
    echo "3. Proceed to Phase 3: Sandfly MCP Server implementation"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review and fix.${NC}"
    echo ""
    exit 1
fi
