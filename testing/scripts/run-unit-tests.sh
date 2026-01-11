#!/bin/bash
# Run unit tests only

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Running Unit Tests${NC}"

# JavaScript unit tests
echo ""
echo -e "${YELLOW}JavaScript Unit Tests...${NC}"
cd "${TESTING_ROOT}/unit/js"
npm test -- --coverage

# Python unit tests
echo ""
echo -e "${YELLOW}Python Unit Tests...${NC}"
cd "${TESTING_ROOT}/unit/python"
pytest --cov --cov-report=term-missing

echo ""
echo -e "${GREEN}Unit tests complete!${NC}"
