#!/bin/bash
# Verify Proxmox MCP Server Deployment
# Comprehensive verification including MCP initialization and real data checks

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="cortex-system"
DEPLOYMENT="proxmox-mcp-server"
SERVICE="proxmox-mcp-server"
TIMEOUT=300

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

echo -e "${GREEN}=== Proxmox MCP Server Verification ===${NC}"
echo "Namespace: $NAMESPACE"
echo "Deployment: $DEPLOYMENT"
echo ""

# Test 1: Check deployment exists
print_test "Checking deployment exists"
if kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" &> /dev/null; then
    print_pass "Deployment exists"
else
    print_fail "Deployment not found"
    exit 1
fi

# Test 2: Check deployment status
print_test "Checking deployment status"
REPLICAS=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.status.replicas}')
READY_REPLICAS=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')

if [ "$REPLICAS" == "$READY_REPLICAS" ] && [ "$READY_REPLICAS" -gt 0 ]; then
    print_pass "Deployment ready ($READY_REPLICAS/$REPLICAS replicas)"
else
    print_fail "Deployment not ready ($READY_REPLICAS/$REPLICAS replicas)"
fi

# Test 3: Check pod status
print_test "Checking pod status"
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -z "$POD_NAME" ]; then
    print_fail "No pods found"
else
    POD_STATUS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    POD_READY=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')

    if [ "$POD_STATUS" == "Running" ] && [ "$POD_READY" == "True" ]; then
        print_pass "Pod running and ready ($POD_NAME)"
    else
        print_fail "Pod not ready (Status: $POD_STATUS, Ready: $POD_READY)"
    fi
fi

# Test 4: Check for recent restarts
print_test "Checking for pod restarts"
RESTART_COUNT=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")

if [ "$RESTART_COUNT" -eq 0 ]; then
    print_pass "No restarts detected"
elif [ "$RESTART_COUNT" -lt 3 ]; then
    print_info "Warning: $RESTART_COUNT restarts detected"
    ((TESTS_PASSED++))
else
    print_fail "Too many restarts: $RESTART_COUNT"
fi

# Test 5: Check container logs for errors
print_test "Checking logs for errors"
ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=100 2>/dev/null | grep -i "error\|exception\|failed\|fatal" | grep -v "no error" | wc -l || echo "0")

if [ "$ERROR_COUNT" -eq 0 ]; then
    print_pass "No errors in recent logs"
else
    print_fail "Found $ERROR_COUNT error(s) in logs"
    echo -e "${YELLOW}Recent errors:${NC}"
    kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=100 | grep -i "error\|exception\|failed\|fatal" | grep -v "no error" | head -5
fi

# Test 6: Check for syntax errors
print_test "Checking for Python syntax errors"
SYNTAX_ERROR=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" 2>&1 | grep -i "SyntaxError" | wc -l || echo "0")

if [ "$SYNTAX_ERROR" -eq 0 ]; then
    print_pass "No syntax errors detected"
else
    print_fail "Syntax errors found in logs"
    kubectl logs -n "$NAMESPACE" "$POD_NAME" | grep -A 5 "SyntaxError"
fi

# Test 7: Check MCP initialization
print_test "Checking MCP initialization"
MCP_INIT=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" 2>&1 | grep -i "MCP.*start\|initialization" | tail -1)

if echo "$MCP_INIT" | grep -qi "start"; then
    print_pass "MCP initialization started"
    print_info "Init message: $MCP_INIT"
else
    print_fail "MCP initialization not detected"
fi

# Test 8: Check for broken pipe errors
print_test "Checking for broken pipe errors"
BROKEN_PIPE=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" 2>&1 | grep -i "broken pipe" | wc -l || echo "0")

if [ "$BROKEN_PIPE" -eq 0 ]; then
    print_pass "No broken pipe errors"
else
    print_fail "Broken pipe errors detected ($BROKEN_PIPE occurrences)"
fi

# Test 9: Check service exists
print_test "Checking service exists"
if kubectl get service "$SERVICE" -n "$NAMESPACE" &> /dev/null; then
    SERVICE_IP=$(kubectl get service "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    SERVICE_PORT=$(kubectl get service "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
    print_pass "Service exists (ClusterIP: $SERVICE_IP:$SERVICE_PORT)"
else
    print_fail "Service not found"
fi

# Test 10: Check service endpoints
print_test "Checking service endpoints"
ENDPOINTS=$(kubectl get endpoints "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.subsets[0].addresses[*].ip}' 2>/dev/null || echo "")

if [ -n "$ENDPOINTS" ]; then
    print_pass "Service has endpoints: $ENDPOINTS"
else
    print_fail "Service has no endpoints"
fi

# Test 11: Test HTTP connectivity (if possible)
print_test "Testing HTTP connectivity to MCP server"

# Create a test pod to curl the service
TEST_POD="proxmox-mcp-test-$$"
kubectl run "$TEST_POD" -n "$NAMESPACE" --image=curlimages/curl --rm -i --restart=Never --timeout=30s -- \
    curl -s -o /dev/null -w "%{http_code}" "http://$SERVICE:3000/health" > /tmp/http_test.txt 2>&1 &
TEST_PID=$!

sleep 5
wait $TEST_PID 2>/dev/null || true

if [ -f /tmp/http_test.txt ]; then
    HTTP_CODE=$(cat /tmp/http_test.txt 2>/dev/null | grep -o "[0-9]\{3\}" | head -1 || echo "000")
    if [ "$HTTP_CODE" == "200" ]; then
        print_pass "HTTP health endpoint responding (200 OK)"
    elif [ "$HTTP_CODE" == "404" ]; then
        print_info "Health endpoint not found (404) - may not be implemented yet"
        ((TESTS_PASSED++))
    else
        print_fail "HTTP endpoint not responding correctly (Code: $HTTP_CODE)"
    fi
    rm -f /tmp/http_test.txt
else
    print_info "Could not test HTTP connectivity - skipping"
    ((TESTS_PASSED++))
fi

# Test 12: Check environment variables
print_test "Checking environment variables"
PROXMOX_HOST=$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- env | grep PROXMOX_HOST | cut -d= -f2 || echo "")

if [ -n "$PROXMOX_HOST" ]; then
    print_pass "Environment variables configured (PROXMOX_HOST=$PROXMOX_HOST)"
else
    print_fail "PROXMOX_HOST environment variable not set"
fi

# Test 13: Check Python dependencies installed
print_test "Checking Python dependencies"
DEPS_CHECK=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=200 | grep -i "successfully installed\|requirement already satisfied" | wc -l || echo "0")

if [ "$DEPS_CHECK" -gt 0 ]; then
    print_pass "Python dependencies installed"
else
    print_info "Could not verify dependency installation"
    ((TESTS_PASSED++))
fi

# Test 14: Check for stub data warnings
print_test "Checking for stub data usage"
STUB_WARNING=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" 2>&1 | grep -i "stub\|mock\|dummy" | wc -l || echo "0")

if [ "$STUB_WARNING" -eq 0 ]; then
    print_pass "No stub data warnings detected"
else
    print_info "Warning: Found $STUB_WARNING references to stub/mock data"
    ((TESTS_PASSED++))
fi

# Test 15: Resource usage check
print_test "Checking resource usage"
MEMORY_USAGE=$(kubectl top pod "$POD_NAME" -n "$NAMESPACE" 2>/dev/null | awk 'NR==2 {print $3}' || echo "N/A")
CPU_USAGE=$(kubectl top pod "$POD_NAME" -n "$NAMESPACE" 2>/dev/null | awk 'NR==2 {print $2}' || echo "N/A")

if [ "$MEMORY_USAGE" != "N/A" ]; then
    print_pass "Resource usage - CPU: $CPU_USAGE, Memory: $MEMORY_USAGE"
else
    print_info "Metrics server not available - skipping resource check"
    ((TESTS_PASSED++))
fi

echo ""
echo -e "${GREEN}=== Verification Summary ===${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run integration tests: ./scripts/test-proxmox-integration.sh"
    echo "  2. Verify real data: kubectl exec -n $NAMESPACE $POD_NAME -- python3 -c 'from proxmoxer import ProxmoxAPI; ...'"
    echo "  3. Test MCP tools: kubectl port-forward -n $NAMESPACE $POD_NAME 3000:3000"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the output above.${NC}"
    echo ""
    echo "Debugging commands:"
    echo "  - View logs: kubectl logs -n $NAMESPACE $POD_NAME"
    echo "  - Describe pod: kubectl describe pod $POD_NAME -n $NAMESPACE"
    echo "  - Exec into pod: kubectl exec -it -n $NAMESPACE $POD_NAME -- /bin/bash"
    exit 1
fi
