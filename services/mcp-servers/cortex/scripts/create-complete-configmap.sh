#!/bin/bash
# Create complete ConfigMap with all Cortex MCP Server source files

set -e

NAMESPACE="cortex-system"
CM_NAME="cortex-mcp-src"
SRC_DIR="/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex"

echo "Creating complete ConfigMap for Cortex MCP Server..."
echo "Source directory: $SRC_DIR"
echo "ConfigMap name: $CM_NAME"
echo "Namespace: $NAMESPACE"

cd "$SRC_DIR"

# Delete existing ConfigMap if it exists
kubectl delete configmap -n "$NAMESPACE" "$CM_NAME" 2>/dev/null || true

# Create ConfigMap from source files
kubectl create configmap "$CM_NAME" -n "$NAMESPACE" \
  --from-file=Dockerfile \
  --from-file=package.json \
  --from-file=src/index.js \
  --from-file=src/moe-router.js \
  --from-file=src/clients/k8s.js \
  --from-file=src/clients/proxmox.js \
  --from-file=src/clients/unifi.js \
  --from-file=src/clients/wazuh.js \
  --from-file=src/tools/query.js \
  --from-file=src/tools/status.js \
  --from-file=src/worker-pool/coordinator.js \
  --from-file=src/worker-pool/monitor.js \
  --from-file=src/worker-pool/spawner.js

echo "ConfigMap created successfully!"
echo ""
echo "Verifying ConfigMap contents:"
kubectl get configmap -n "$NAMESPACE" "$CM_NAME" -o jsonpath='{.data}' | jq 'keys'
echo ""
echo "ConfigMap size:"
kubectl get configmap -n "$NAMESPACE" "$CM_NAME" -o json | jq '.data | to_entries | map({key: .key, size: (.value | length)}) | .[]'
