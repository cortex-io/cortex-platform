#!/bin/bash
# Push script for cortex-live Docker image

set -e

VERSION="v2.0.0"
REGISTRY="10.43.170.72:5000"
IMAGE_NAME="cortex-live"

echo "Pushing cortex-live ${VERSION} to ${REGISTRY}..."

# Push to registry
docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}
docker push ${REGISTRY}/${IMAGE_NAME}:latest

echo "✓ Pushed ${IMAGE_NAME}:${VERSION}"
echo "✓ Pushed ${IMAGE_NAME}:latest"
echo ""
echo "Image available at: ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo ""
echo "To deploy:"
echo "  kubectl apply -f ~/Projects/cortex-gitops/apps/cortex-live/"
echo ""
echo "Or wait for ArgoCD auto-sync (3 minutes)"
