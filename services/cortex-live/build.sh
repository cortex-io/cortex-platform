#!/bin/bash
# Build script for cortex-live Docker image
# Run this on a system with Docker installed

set -e

VERSION="v2.0.0"
REGISTRY="10.43.170.72:5000"
IMAGE_NAME="cortex-live"

echo "Building cortex-live ${VERSION}..."

# Build image
docker build -t ${IMAGE_NAME}:${VERSION} .

# Tag for local registry
docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${IMAGE_NAME}:${VERSION}
docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${IMAGE_NAME}:latest

echo "✓ Built ${IMAGE_NAME}:${VERSION}"
echo ""
echo "To push to cluster registry:"
echo "  docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo "  docker push ${REGISTRY}/${IMAGE_NAME}:latest"
echo ""
echo "Or run: ./push.sh"
