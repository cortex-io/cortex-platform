#!/bin/bash
set -e

# Configuration
REGISTRY="10.43.170.72:5000"
IMAGE="youtube-school-bridge"
TAG="latest"
FULL_IMAGE="${REGISTRY}/${IMAGE}:${TAG}"

echo "Building ${FULL_IMAGE}..."

# Build the image
docker build -t "${FULL_IMAGE}" .

echo "Pushing to registry..."

# Push to internal registry
docker push "${FULL_IMAGE}"

echo "Build and push complete: ${FULL_IMAGE}"
