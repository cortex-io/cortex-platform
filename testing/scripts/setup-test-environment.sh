#!/bin/bash
# Setup test environment for Cortex

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Setting up Cortex Test Environment${NC}"
echo "====================================="

# Check prerequisites
echo ""
echo "Checking prerequisites..."

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js: ${NODE_VERSION}"
else
    echo -e "${YELLOW}⚠${NC} Node.js not found. Please install Node.js 20+"
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Python: ${PYTHON_VERSION}"
else
    echo -e "${YELLOW}⚠${NC} Python not found. Please install Python 3.11+"
    exit 1
fi

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}✓${NC} Docker: ${DOCKER_VERSION}"
else
    echo -e "${YELLOW}⚠${NC} Docker not found. Integration tests will not work."
fi

# Check kubectl
if command -v kubectl &> /dev/null; then
    KUBECTL_VERSION=$(kubectl version --client --short 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓${NC} kubectl: ${KUBECTL_VERSION}"
else
    echo -e "${YELLOW}⚠${NC} kubectl not found. E2E tests will not work."
fi

# Install JavaScript dependencies
echo ""
echo "Installing JavaScript dependencies..."

echo "  - Unit tests..."
cd "${TESTING_ROOT}/unit/js" && npm install --silent

echo "  - Integration tests..."
cd "${TESTING_ROOT}/integration/js" && npm install --silent

echo "  - E2E tests..."
cd "${TESTING_ROOT}/e2e/js" && npm install --silent

echo -e "${GREEN}✓${NC} JavaScript dependencies installed"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."

echo "  - Unit tests..."
cd "${TESTING_ROOT}/unit/python" && pip install -q -r requirements.txt

echo "  - Integration tests..."
cd "${TESTING_ROOT}/integration/python" && pip install -q -r requirements.txt

echo "  - E2E tests..."
cd "${TESTING_ROOT}/e2e/python" && pip install -q -r requirements.txt

echo -e "${GREEN}✓${NC} Python dependencies installed"

# Create coverage directories
echo ""
echo "Creating coverage directories..."
mkdir -p "${TESTING_ROOT}/coverage/unit/js"
mkdir -p "${TESTING_ROOT}/coverage/unit/python"
mkdir -p "${TESTING_ROOT}/coverage/integration/js"
mkdir -p "${TESTING_ROOT}/coverage/integration/python"
mkdir -p "${TESTING_ROOT}/coverage/reports"
echo -e "${GREEN}✓${NC} Coverage directories created"

# Setup K8s test namespace (if kubectl available)
if command -v kubectl &> /dev/null; then
    echo ""
    echo "Setting up Kubernetes test namespace..."
    if kubectl get namespace cortex-test &> /dev/null; then
        echo -e "${GREEN}✓${NC} Test namespace already exists"
    else
        kubectl create namespace cortex-test
        echo -e "${GREEN}✓${NC} Test namespace created"
    fi

    echo "Applying test resources..."
    kubectl apply -f "${TESTING_ROOT}/k8s/test-resources/" &> /dev/null || true
    echo -e "${GREEN}✓${NC} Test resources applied"
fi

echo ""
echo -e "${GREEN}==================================="
echo "Setup Complete!"
echo -e "===================================${NC}"
echo ""
echo "You can now run tests:"
echo "  ${TESTING_ROOT}/scripts/run-all-tests.sh"
echo ""
echo "Or run specific test suites:"
echo "  ${TESTING_ROOT}/scripts/run-unit-tests.sh"
echo "  ${TESTING_ROOT}/scripts/run-integration-tests.sh"
echo "  ${TESTING_ROOT}/scripts/run-e2e-tests.sh"
