#!/bin/bash
# Run all tests for Cortex

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}==================================="
echo "Cortex Test Suite"
echo -e "===================================${NC}"

# Track test results
UNIT_JS_RESULT=0
UNIT_PY_RESULT=0
INT_JS_RESULT=0
INT_PY_RESULT=0

# Run JavaScript unit tests
echo ""
echo -e "${YELLOW}Running JavaScript Unit Tests...${NC}"
cd "${TESTING_ROOT}/unit/js"
npm test || UNIT_JS_RESULT=$?

# Run Python unit tests
echo ""
echo -e "${YELLOW}Running Python Unit Tests...${NC}"
cd "${TESTING_ROOT}/unit/python"
pytest || UNIT_PY_RESULT=$?

# Run JavaScript integration tests
echo ""
echo -e "${YELLOW}Running JavaScript Integration Tests...${NC}"
cd "${TESTING_ROOT}/integration/js"
npm test || INT_JS_RESULT=$?

# Run Python integration tests
echo ""
echo -e "${YELLOW}Running Python Integration Tests...${NC}"
cd "${TESTING_ROOT}/integration/python"
pytest || INT_PY_RESULT=$?

# Print summary
echo ""
echo -e "${GREEN}==================================="
echo "Test Summary"
echo -e "===================================${NC}"

if [ $UNIT_JS_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} JavaScript Unit Tests: PASSED"
else
    echo -e "${RED}✗${NC} JavaScript Unit Tests: FAILED"
fi

if [ $UNIT_PY_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Python Unit Tests: PASSED"
else
    echo -e "${RED}✗${NC} Python Unit Tests: FAILED"
fi

if [ $INT_JS_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} JavaScript Integration Tests: PASSED"
else
    echo -e "${RED}✗${NC} JavaScript Integration Tests: FAILED"
fi

if [ $INT_PY_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Python Integration Tests: PASSED"
else
    echo -e "${RED}✗${NC} Python Integration Tests: FAILED"
fi

# Exit with failure if any test failed
TOTAL_FAILURES=$((UNIT_JS_RESULT + UNIT_PY_RESULT + INT_JS_RESULT + INT_PY_RESULT))

if [ $TOTAL_FAILURES -eq 0 ]; then
    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}Some tests failed. Please check the output above.${NC}"
    exit 1
fi
