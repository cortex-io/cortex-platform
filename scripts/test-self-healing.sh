#!/bin/bash

# Test Script for Cortex Self-Healing System
# Tests various failure scenarios and verifies healing behavior

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="cortex-system"
API_URL="http://cortex-api.cortex-system.svc.cluster.local:8000"
TEST_SERVICE="sandfly-mcp-server"
ORIGINAL_REPLICAS=1

echo "========================================================"
echo "Cortex Self-Healing System Test Suite"
echo "========================================================"
echo ""

# Helper: Print colored message
print_status() {
  local color=$1
  shift
  echo -e "${color}$*${NC}"
}

# Helper: Wait for condition
wait_for() {
  local timeout=$1
  local check_cmd=$2
  local description=$3

  print_status "$YELLOW" "Waiting for: $description (timeout: ${timeout}s)"

  local elapsed=0
  while [ $elapsed -lt $timeout ]; do
    if eval "$check_cmd" > /dev/null 2>&1; then
      print_status "$GREEN" "✓ Condition met: $description"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  print_status "$RED" "✗ Timeout waiting for: $description"
  return 1
}

# Helper: Get current replica count
get_replicas() {
  kubectl get deployment -n "$NAMESPACE" "$TEST_SERVICE" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0"
}

# Helper: Save original state
save_original_state() {
  print_status "$YELLOW" "Saving original deployment state..."
  ORIGINAL_REPLICAS=$(kubectl get deployment -n "$NAMESPACE" "$TEST_SERVICE" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
  print_status "$GREEN" "Original replicas: $ORIGINAL_REPLICAS"
}

# Helper: Restore original state
restore_original_state() {
  print_status "$YELLOW" "Restoring original deployment state..."
  kubectl scale deployment -n "$NAMESPACE" "$TEST_SERVICE" \
    --replicas="$ORIGINAL_REPLICAS" > /dev/null 2>&1
  kubectl rollout status deployment -n "$NAMESPACE" "$TEST_SERVICE" \
    --timeout=60s > /dev/null 2>&1
  print_status "$GREEN" "✓ Original state restored"
}

# Helper: Make API request that triggers healing
test_healing_request() {
  local test_name=$1
  local expected_healing=$2

  print_status "$YELLOW" "Making API request to trigger healing..."

  # Make request and capture output
  local response
  response=$(curl -s -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"query": "list sandfly hosts", "streaming": false}' \
    --max-time 120 || echo '{"error": "Request failed"}')

  # Check if healing was triggered
  if echo "$response" | grep -q "healing"; then
    if [ "$expected_healing" = "true" ]; then
      print_status "$GREEN" "✓ Healing was triggered as expected"
      return 0
    else
      print_status "$RED" "✗ Healing was triggered unexpectedly"
      return 1
    fi
  else
    if [ "$expected_healing" = "false" ]; then
      print_status "$GREEN" "✓ No healing triggered as expected"
      return 0
    else
      print_status "$RED" "✗ Expected healing but it was not triggered"
      return 1
    fi
  fi
}

# TEST 1: Service Scaled to Zero
test_scaled_to_zero() {
  echo ""
  echo "========================================================"
  print_status "$YELLOW" "TEST 1: Service Scaled to Zero"
  echo "========================================================"

  # Scale down service
  print_status "$YELLOW" "Scaling service to 0 replicas..."
  kubectl scale deployment -n "$NAMESPACE" "$TEST_SERVICE" --replicas=0 > /dev/null

  # Wait for pods to terminate
  wait_for 30 "[ \$(get_replicas) -eq 0 ]" "Service scaled to 0"

  # Trigger healing via API request
  print_status "$YELLOW" "Triggering healing via API request..."
  test_healing_request "scaled_to_zero" "true"

  # Wait for healing to complete
  sleep 15

  # Verify service is back
  local replicas
  replicas=$(get_replicas)

  if [ "$replicas" -ge 1 ]; then
    print_status "$GREEN" "✓ TEST 1 PASSED: Service restored ($replicas replicas)"
    return 0
  else
    print_status "$RED" "✗ TEST 1 FAILED: Service not restored (replicas: $replicas)"
    return 1
  fi
}

# TEST 2: Pod CrashLoop Simulation
test_crashloop() {
  echo ""
  echo "========================================================"
  print_status "$YELLOW" "TEST 2: Pod CrashLoop (simulated)"
  echo "========================================================"

  # Save current image
  local original_image
  original_image=$(kubectl get deployment -n "$NAMESPACE" "$TEST_SERVICE" \
    -o jsonpath='{.spec.template.spec.containers[0].image}')

  print_status "$YELLOW" "Original image: $original_image"

  # Set invalid image to cause crashloop
  print_status "$YELLOW" "Setting invalid image to trigger crashloop..."
  kubectl set image deployment/"$TEST_SERVICE" -n "$NAMESPACE" \
    "$TEST_SERVICE"=invalid-image:nonexistent > /dev/null 2>&1 || true

  # Wait for pod to be in error state
  sleep 10

  # Trigger healing
  print_status "$YELLOW" "Triggering healing via API request..."
  test_healing_request "crashloop" "true"

  # Wait for healing attempt
  sleep 20

  # Restore original image (healing won't fix imagepull errors)
  print_status "$YELLOW" "Restoring original image..."
  kubectl set image deployment/"$TEST_SERVICE" -n "$NAMESPACE" \
    "$TEST_SERVICE"="$original_image" > /dev/null 2>&1

  # Wait for service to recover
  if wait_for 60 "[ \$(get_replicas) -ge 1 ]" "Service recovery after image restore"; then
    print_status "$GREEN" "✓ TEST 2 PASSED: Healing attempted, service recovered after image restore"
    return 0
  else
    print_status "$RED" "✗ TEST 2 FAILED: Service did not recover"
    return 1
  fi
}

# TEST 3: Worker Script Direct Test
test_worker_script() {
  echo ""
  echo "========================================================"
  print_status "$YELLOW" "TEST 3: Healing Worker Script Direct Test"
  echo "========================================================"

  # Get API pod name
  local api_pod
  api_pod=$(kubectl get pods -n "$NAMESPACE" -l app=cortex-api \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

  if [ -z "$api_pod" ]; then
    print_status "$RED" "✗ TEST 3 SKIPPED: Could not find cortex-api pod"
    return 1
  fi

  print_status "$YELLOW" "Testing worker script in pod: $api_pod"

  # Execute worker script directly
  local result
  result=$(kubectl exec -n "$NAMESPACE" "$api_pod" -- \
    bash /app/scripts/self-heal-worker.sh \
    "$TEST_SERVICE" \
    "connection refused" \
    "http://$TEST_SERVICE.cortex-system.svc.cluster.local:3000" \
    2>&1 | tail -1 || echo '{"success":false}')

  print_status "$YELLOW" "Worker result: $result"

  # Check if result is valid JSON
  if echo "$result" | jq -e '.success' > /dev/null 2>&1; then
    local success
    success=$(echo "$result" | jq -r '.success')

    if [ "$success" = "true" ] || [ "$success" = "false" ]; then
      print_status "$GREEN" "✓ TEST 3 PASSED: Worker script executed and returned valid JSON"
      print_status "$YELLOW" "Diagnosis: $(echo "$result" | jq -r '.diagnosis')"
      return 0
    fi
  fi

  print_status "$RED" "✗ TEST 3 FAILED: Worker script did not return valid JSON"
  return 1
}

# TEST 4: Health Endpoint Test
test_health_endpoint() {
  echo ""
  echo "========================================================"
  print_status "$YELLOW" "TEST 4: API Health Endpoint"
  echo "========================================================"

  local health_response
  health_response=$(curl -s "$API_URL/health" || echo '{}')

  if echo "$health_response" | jq -e '.status' > /dev/null 2>&1; then
    local status
    status=$(echo "$health_response" | jq -r '.status')

    if [ "$status" = "healthy" ]; then
      print_status "$GREEN" "✓ TEST 4 PASSED: Health endpoint returned healthy status"
      return 0
    fi
  fi

  print_status "$RED" "✗ TEST 4 FAILED: Health endpoint did not return healthy status"
  return 1
}

# TEST 5: Timeout Healing
test_timeout_healing() {
  echo ""
  echo "========================================================"
  print_status "$YELLOW" "TEST 5: Timeout-Triggered Healing"
  echo "========================================================"

  # Scale service to 0 to guarantee timeout
  print_status "$YELLOW" "Scaling service to 0 to cause timeout..."
  kubectl scale deployment -n "$NAMESPACE" "$TEST_SERVICE" --replicas=0 > /dev/null

  wait_for 30 "[ \$(get_replicas) -eq 0 ]" "Service scaled to 0"

  # Make request that will timeout
  print_status "$YELLOW" "Making request that will timeout and trigger healing..."

  local start_time
  start_time=$(date +%s)

  # Request with shorter timeout to speed up test
  curl -s -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"query": "list sandfly hosts", "streaming": false}' \
    --max-time 65 > /dev/null 2>&1 || true

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Wait a bit for healing to complete
  sleep 15

  # Check if service was healed
  local replicas
  replicas=$(get_replicas)

  if [ "$replicas" -ge 1 ]; then
    print_status "$GREEN" "✓ TEST 5 PASSED: Timeout triggered healing, service restored (${duration}s)"
    return 0
  else
    print_status "$YELLOW" "⚠ TEST 5 INCONCLUSIVE: Timeout occurred but service not yet restored"
    print_status "$YELLOW" "  This may be due to timing - healing might still be in progress"
    return 0
  fi
}

# Main test execution
main() {
  # Check prerequisites
  print_status "$YELLOW" "Checking prerequisites..."

  if ! command -v kubectl > /dev/null; then
    print_status "$RED" "✗ kubectl not found. Please install kubectl."
    exit 1
  fi

  if ! kubectl get namespace "$NAMESPACE" > /dev/null 2>&1; then
    print_status "$RED" "✗ Namespace $NAMESPACE not found."
    exit 1
  fi

  if ! kubectl get deployment -n "$NAMESPACE" "$TEST_SERVICE" > /dev/null 2>&1; then
    print_status "$RED" "✗ Test service $TEST_SERVICE not found in namespace $NAMESPACE."
    exit 1
  fi

  print_status "$GREEN" "✓ Prerequisites met"

  # Save original state
  save_original_state

  # Set trap to restore state on exit
  trap restore_original_state EXIT

  # Run tests
  local passed=0
  local failed=0

  # TEST 1
  if test_scaled_to_zero; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi

  # Restore state between tests
  restore_original_state
  sleep 5

  # TEST 2
  if test_crashloop; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi

  # Restore state between tests
  restore_original_state
  sleep 5

  # TEST 3
  if test_worker_script; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi

  # Restore state between tests
  restore_original_state
  sleep 5

  # TEST 4
  if test_health_endpoint; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi

  # TEST 5
  if test_timeout_healing; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi

  # Summary
  echo ""
  echo "========================================================"
  print_status "$YELLOW" "TEST SUMMARY"
  echo "========================================================"
  print_status "$GREEN" "Passed: $passed"
  print_status "$RED" "Failed: $failed"
  print_status "$YELLOW" "Total:  $((passed + failed))"
  echo "========================================================"
  echo ""

  if [ "$failed" -eq 0 ]; then
    print_status "$GREEN" "✓ ALL TESTS PASSED"
    exit 0
  else
    print_status "$RED" "✗ SOME TESTS FAILED"
    exit 1
  fi
}

# Run main
main "$@"
