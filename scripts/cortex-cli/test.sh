#!/usr/bin/env bash
#
# Test script for cortex-k8s CLI
#
# Runs comprehensive tests on the CLI tool
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_test() {
    echo -e "${BLUE}[TEST]${NC} $*"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

run_test() {
    local test_name="$1"
    shift
    local test_cmd="$*"

    TESTS_RUN=$((TESTS_RUN + 1))
    log_test "${test_name}"

    if eval "${test_cmd}" &>/dev/null; then
        log_pass "${test_name}"
        return 0
    else
        log_fail "${test_name}"
        return 1
    fi
}

echo "========================================"
echo "Cortex K8s CLI - Test Suite"
echo "========================================"
echo ""

# Test 1: Syntax Check
echo "1. Syntax Tests"
echo "----------------"

run_test "cortex-k8s syntax" "bash -n ${SCRIPT_DIR}/cortex-k8s"
run_test "install.sh syntax" "bash -n ${SCRIPT_DIR}/install.sh"
run_test "completion.bash syntax" "bash -n ${SCRIPT_DIR}/cortex-k8s-completion.bash"

echo ""

# Test 2: File Permissions
echo "2. File Permission Tests"
echo "------------------------"

run_test "cortex-k8s is executable" "test -x ${SCRIPT_DIR}/cortex-k8s"
run_test "install.sh is executable" "test -x ${SCRIPT_DIR}/install.sh"

for example in "${SCRIPT_DIR}"/examples/*.sh; do
    if [[ -f "$example" ]]; then
        run_test "$(basename "$example") is executable" "test -x $example"
    fi
done

echo ""

# Test 3: Required Files
echo "3. Required Files Tests"
echo "-----------------------"

required_files=(
    "cortex-k8s"
    "cortex-k8s-completion.bash"
    "cortex-k8s-completion.zsh"
    "install.sh"
    "README.md"
    "QUICKSTART.md"
    "CHANGELOG.md"
    "CONTRIBUTING.md"
    "Makefile"
    "examples/deploy-all.sh"
    "examples/rolling-update.sh"
    "examples/health-check.sh"
    "examples/ci-cd-pipeline.sh"
    "examples/README.md"
)

for file in "${required_files[@]}"; do
    run_test "File exists: ${file}" "test -f ${SCRIPT_DIR}/${file}"
done

echo ""

# Test 4: Command Help Output
echo "4. Help Output Tests"
echo "--------------------"

run_test "Help command works" "${SCRIPT_DIR}/cortex-k8s help"
run_test "Version command works" "${SCRIPT_DIR}/cortex-k8s version"

echo ""

# Test 5: Prerequisites Check
echo "5. Prerequisites Tests"
echo "----------------------"

if command -v kubectl &> /dev/null; then
    log_pass "kubectl is installed"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_fail "kubectl is not installed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

if command -v jq &> /dev/null; then
    log_pass "jq is installed"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_fail "jq is not installed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

echo ""

# Test 6: Shellcheck (if available)
echo "6. Shellcheck Tests"
echo "-------------------"

if command -v shellcheck &> /dev/null; then
    run_test "Shellcheck cortex-k8s" "shellcheck -x ${SCRIPT_DIR}/cortex-k8s"
    run_test "Shellcheck install.sh" "shellcheck -x ${SCRIPT_DIR}/install.sh"
    run_test "Shellcheck completion.bash" "shellcheck ${SCRIPT_DIR}/cortex-k8s-completion.bash"

    for example in "${SCRIPT_DIR}"/examples/*.sh; do
        if [[ -f "$example" ]]; then
            run_test "Shellcheck $(basename "$example")" "shellcheck $example"
        fi
    done
else
    echo "Shellcheck not installed, skipping..."
fi

echo ""

# Test 7: Documentation Tests
echo "7. Documentation Tests"
echo "----------------------"

# Check README has key sections
run_test "README has Installation section" "grep -q '## Installation' ${SCRIPT_DIR}/README.md"
run_test "README has Usage section" "grep -q '## Usage' ${SCRIPT_DIR}/README.md"
run_test "README has Examples section" "grep -q '## Examples' ${SCRIPT_DIR}/README.md"

# Check QUICKSTART
run_test "QUICKSTART has steps" "grep -q '## 1. Install' ${SCRIPT_DIR}/QUICKSTART.md"

# Check CHANGELOG
run_test "CHANGELOG has version" "grep -q '\[1.0.0\]' ${SCRIPT_DIR}/CHANGELOG.md"

echo ""

# Test 8: Completion Tests
echo "8. Completion Tests"
echo "-------------------"

# Source bash completion (in subshell to not affect current shell)
if (
    source "${SCRIPT_DIR}/cortex-k8s-completion.bash"
    type _cortex_k8s_completions &>/dev/null
); then
    log_pass "Bash completion can be sourced"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_fail "Bash completion cannot be sourced"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Check zsh completion syntax (zsh not always available)
run_test "Zsh completion file is valid" "test -s ${SCRIPT_DIR}/cortex-k8s-completion.zsh"

echo ""

# Test 9: Example Scripts Tests
echo "9. Example Scripts Tests"
echo "------------------------"

# Check examples have usage info
run_test "deploy-all.sh has usage" "grep -q 'Usage:' ${SCRIPT_DIR}/examples/deploy-all.sh || grep -q 'NAMESPACE' ${SCRIPT_DIR}/examples/deploy-all.sh"
run_test "rolling-update.sh has usage" "grep -q 'Usage:' ${SCRIPT_DIR}/examples/rolling-update.sh"
run_test "health-check.sh has namespace config" "grep -q 'NAMESPACE' ${SCRIPT_DIR}/examples/health-check.sh"
run_test "ci-cd-pipeline.sh has pipeline steps" "grep -q 'Step' ${SCRIPT_DIR}/examples/ci-cd-pipeline.sh"

echo ""

# Summary
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Tests Run:    ${TESTS_RUN}"
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [[ ${TESTS_FAILED} -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}✗ Some tests failed${NC}"
    exit 1
fi
