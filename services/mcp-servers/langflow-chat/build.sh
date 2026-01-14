#!/bin/bash
set -e

REGISTRY="10.43.170.72:5000"
IMAGE_NAME="langflow-chat-mcp-server"
TAG="${1:-latest}"

echo "Building ${IMAGE_NAME}:${TAG}..."
docker build -t ${IMAGE_NAME}:${TAG} .

echo "Tagging for registry..."
docker tag ${IMAGE_NAME}:${TAG} ${REGISTRY}/${IMAGE_NAME}:${TAG}

echo "Pushing to registry..."
docker push ${REGISTRY}/${IMAGE_NAME}:${TAG}

echo "Done! Image: ${REGISTRY}/${IMAGE_NAME}:${TAG}"
