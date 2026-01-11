#!/bin/bash

# Get token
AUTH_RESP=$(curl -k -s -X POST https://10.88.140.176/v4/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"emphasize-art-nibble-arguable-paradox-flick-unpack"}')

TOKEN=$(echo "$AUTH_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "=== STATUS endpoint (summary data) ==="
curl -k -s -X GET "https://10.88.140.176/v4/status" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== USERS endpoint ==="
curl -k -s -X GET "https://10.88.140.176/v4/users" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== AUDIT endpoint (first 2 items) ==="
curl -k -s -X GET "https://10.88.140.176/v4/audit?page=1&size=2" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
