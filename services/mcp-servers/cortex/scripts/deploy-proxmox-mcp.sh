#!/bin/bash
# Deploy Proxmox MCP Server to Kubernetes
# Updates deployment with new image and monitors rollout

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
REGISTRY="docker-registry.cortex-system.svc.cluster.local:5000"
IMAGE_NAME="cortex-mcp-server"
IMAGE_TAG="${1:-latest}"  # Allow override via argument
TIMEOUT=300

echo -e "${GREEN}=== Proxmox MCP Server Deployment ===${NC}"
echo "Namespace: $NAMESPACE"
echo "Deployment: $DEPLOYMENT"
echo "Image: $REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo -e "${RED}Error: Namespace $NAMESPACE not found${NC}"
    exit 1
fi

if ! kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" &> /dev/null; then
    echo -e "${RED}Error: Deployment $DEPLOYMENT not found${NC}"
    echo "Please create deployment first or check deployment name"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# Backup current deployment
echo -e "${YELLOW}Backing up current deployment...${NC}"
BACKUP_FILE="/tmp/${DEPLOYMENT}-backup-$(date +%Y%m%d-%H%M%S).yaml"
kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o yaml > "$BACKUP_FILE"
echo -e "${GREEN}Backup saved to: $BACKUP_FILE${NC}"
echo ""

# Get current revision for potential rollback
CURRENT_REVISION=$(kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE" | tail -1 | awk '{print $1}')
echo -e "${YELLOW}Current revision: $CURRENT_REVISION${NC}"
echo ""

# Update deployment image
echo -e "${YELLOW}Updating deployment image...${NC}"

kubectl set image deployment/"$DEPLOYMENT" \
    app="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG" \
    -n "$NAMESPACE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Image updated successfully${NC}"
else
    echo -e "${RED}Failed to update image${NC}"
    exit 1
fi

# Optionally update image pull policy
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" -p \
    '{"spec":{"template":{"spec":{"containers":[{"name":"app","imagePullPolicy":"Always"}]}}}}'

echo ""

# Monitor rollout
echo -e "${YELLOW}Monitoring rollout...${NC}"
echo "This may take a few minutes..."
echo ""

if kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
    echo ""
    echo -e "${GREEN}Deployment successful!${NC}"
else
    echo ""
    echo -e "${RED}Deployment failed or timed out${NC}"
    echo ""
    echo "Rolling back to revision $CURRENT_REVISION..."
    kubectl rollout undo deployment/"$DEPLOYMENT" -n "$NAMESPACE"
    kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=120s
    echo ""
    echo -e "${RED}Rolled back to previous version${NC}"
    exit 1
fi

# Get new pod info
echo ""
echo -e "${YELLOW}Getting pod information...${NC}"

POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" -o jsonpath='{.items[0].metadata.name}')
POD_STATUS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
POD_IMAGE=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].image}')

echo "Pod Name: $POD_NAME"
echo "Pod Status: $POD_STATUS"
echo "Pod Image: $POD_IMAGE"
echo ""

# Quick health check
echo -e "${YELLOW}Running quick health check...${NC}"

sleep 5  # Give pod time to fully start

# Check for errors in logs
ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=50 2>&1 | grep -i "error\|exception\|failed" | grep -v "no error" | wc -l || echo "0")

if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}No errors detected in logs${NC}"
else
    echo -e "${YELLOW}Warning: Found $ERROR_COUNT error(s) in recent logs${NC}"
    kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=20
    echo ""
fi

# Check for syntax errors
SYNTAX_ERROR=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" 2>&1 | grep -i "SyntaxError" | wc -l || echo "0")

if [ "$SYNTAX_ERROR" -eq 0 ]; then
    echo -e "${GREEN}No syntax errors detected${NC}"
else
    echo -e "${RED}CRITICAL: Syntax errors detected!${NC}"
    kubectl logs -n "$NAMESPACE" "$POD_NAME" | grep -A 5 "SyntaxError"
    echo ""
    echo "Rolling back..."
    kubectl rollout undo deployment/"$DEPLOYMENT" -n "$NAMESPACE"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Deployment Summary:"
echo "  - Image: $REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
echo "  - Replicas: $(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.status.replicas}')"
echo "  - Ready Replicas: $(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')"
echo "  - New Revision: $(kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE" | tail -1 | awk '{print $1}')"
echo ""
echo "Next steps:"
echo "  1. Run verification: ./scripts/verify-proxmox-mcp.sh"
echo "  2. Run integration tests: ./scripts/test-proxmox-integration.sh"
echo "  3. Monitor logs: kubectl logs -n $NAMESPACE $POD_NAME -f"
echo ""
echo "If issues occur, rollback with:"
echo "  ./scripts/rollback-proxmox-mcp.sh"
echo ""
