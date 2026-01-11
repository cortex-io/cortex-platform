#!/bin/bash
# Manual build script for Cortex MCP Server
# Uses kubectl cp to transfer source and build in-cluster

set -e

NAMESPACE="cortex-system"
POD_NAME="cortex-mcp-builder-$(date +%s)"
REGISTRY="docker-registry.cortex-system.svc.cluster.local:5000"
IMAGE="cortex-mcp-server:latest"

echo "[1/6] Creating builder pod..."
kubectl run $POD_NAME \
  --namespace=$NAMESPACE \
  --image=gcr.io/kaniko-project/executor:latest \
  --restart=Never \
  --command -- sleep 3600

echo "[2/6] Waiting for pod to be ready..."
kubectl wait --for=condition=Ready pod/$POD_NAME -n $NAMESPACE --timeout=60s

echo "[3/6] Copying source code to pod..."
cd "$(dirname "$0")/.."
tar czf - --exclude=node_modules --exclude=.git . | \
  kubectl exec -i $POD_NAME -n $NAMESPACE -- tar xzf - -C /workspace

echo "[4/6] Building image with Kaniko..."
kubectl exec $POD_NAME -n $NAMESPACE -- \
  /kaniko/executor \
    --dockerfile=/workspace/Dockerfile \
    --context=/workspace \
    --destination=$REGISTRY/$IMAGE \
    --insecure \
    --skip-tls-verify \
    --cache=true \
    --cache-repo=$REGISTRY/cache

echo "[5/6] Cleaning up builder pod..."
kubectl delete pod $POD_NAME -n $NAMESPACE

echo "[6/6] Restarting Cortex MCP deployment..."
kubectl rollout restart deployment cortex-mcp-server -n $NAMESPACE 2>/dev/null || \
  echo "Note: Cortex MCP deployment will be created on first apply"

echo "✅ Build complete! Image pushed to $REGISTRY/$IMAGE"
