#!/bin/bash
# Sandfly API Explorer - Daryl-1

set -e

SANDFLY_HOST="10.88.140.176"
USERNAME="admin"
PASSWORD="emphasize-art-nibble-arguable-paradox-flick-unpack"
BASE_URL="https://${SANDFLY_HOST}/v4"

echo "========================================================================"
echo "SANDFLY API EXPLORATION - DARYL-1"
echo "========================================================================"
echo ""

# Authenticate and get token
echo "Step 1: Authenticating..."
AUTH_RESPONSE=$(curl -k -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}")

TOKEN=$(echo "$AUTH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to authenticate"
  exit 1
fi

echo "✓ Authentication successful"
echo ""

# Function to test an endpoint
test_endpoint() {
  local METHOD=$1
  local ENDPOINT=$2
  local PAYLOAD=$3

  echo "========================================================================"
  echo "$METHOD $ENDPOINT"
  echo "========================================================================"

  if [ "$METHOD" = "GET" ]; then
    RESPONSE=$(curl -k -s -w "\nHTTP_CODE:%{http_code}" -X GET "${BASE_URL}${ENDPOINT}" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json")
  else
    RESPONSE=$(curl -k -s -w "\nHTTP_CODE:%{http_code}" -X POST "${BASE_URL}${ENDPOINT}" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD")
  fi

  HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
  BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

  echo "Status: $HTTP_CODE"

  if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ SUCCESS"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  else
    echo "✗ FAILED"
    echo "$BODY"
  fi

  echo ""
}

# System/Info endpoints
test_endpoint "GET" "/version"
test_endpoint "GET" "/health"
test_endpoint "GET" "/status"
test_endpoint "GET" "/stats"
test_endpoint "GET" "/system"

# Host endpoints
test_endpoint "GET" "/hosts?page=1&size=5"
test_endpoint "POST" "/hosts" '{"filter":{},"page":1,"size":5}'
test_endpoint "GET" "/hosts/summary"
test_endpoint "GET" "/hosts/stats"

# Results/Scans endpoints
test_endpoint "POST" "/results" '{"filter":{},"page":1,"size":5,"summary":false}'
test_endpoint "GET" "/results?page=1&size=5"
test_endpoint "GET" "/results/summary"
test_endpoint "GET" "/results/stats"

# Alerts endpoints
test_endpoint "GET" "/alerts?page=1&size=5"
test_endpoint "POST" "/alerts" '{"filter":{},"page":1,"size":5}'
test_endpoint "GET" "/alerts/summary"
test_endpoint "GET" "/alerts/active"

# Sandboxes
test_endpoint "GET" "/sandboxes"
test_endpoint "POST" "/sandboxes" '{"filter":{},"page":1,"size":10}'

# Policies
test_endpoint "GET" "/policies"
test_endpoint "GET" "/policies/summary"

# Schedules
test_endpoint "GET" "/schedules"
test_endpoint "POST" "/schedules" '{"filter":{},"page":1,"size":10}'

# Users
test_endpoint "GET" "/users"
test_endpoint "GET" "/users/me"

# Activity/Audit
test_endpoint "GET" "/activity?page=1&size=5"
test_endpoint "GET" "/audit?page=1&size=5"

# Categories/Tags
test_endpoint "GET" "/categories"
test_endpoint "GET" "/tags"

# Metrics (might be internal)
test_endpoint "GET" "/metrics"

echo "========================================================================"
echo "API EXPLORATION COMPLETE"
echo "========================================================================"
