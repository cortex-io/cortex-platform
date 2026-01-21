#!/bin/bash
# =============================================================================
# Cortex Container Image Build and Push Script
# =============================================================================
#
# This script builds and pushes Cortex container images to the registry.
#
# Usage:
#   ./build-and-push.sh [image-name] [tag]
#
# Examples:
#   ./build-and-push.sh cortex-python-base 3.11
#   ./build-and-push.sh layer-activator latest
#   ./build-and-push.sh memory-service v1.0.0
#
# =============================================================================

set -e

# Configuration
REGISTRY="${REGISTRY:-registry-mirror.registry.svc.cluster.local:5000}"
REGISTRY_EXTERNAL="${REGISTRY_EXTERNAL:-10.43.90.31:5000}"
BUILD_DIR="$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check arguments
IMAGE_NAME="${1:-cortex-python-base}"
TAG="${2:-latest}"

log_info "Building image: ${IMAGE_NAME}:${TAG}"

# Find Dockerfile
DOCKERFILE="${BUILD_DIR}/Dockerfile.${IMAGE_NAME}"
if [[ ! -f "$DOCKERFILE" ]]; then
    # Check in services directory
    DOCKERFILE="${BUILD_DIR}/../services/${IMAGE_NAME}/Dockerfile"
fi

if [[ ! -f "$DOCKERFILE" ]]; then
    log_error "Dockerfile not found for ${IMAGE_NAME}"
    log_info "Searched:"
    log_info "  - ${BUILD_DIR}/Dockerfile.${IMAGE_NAME}"
    log_info "  - ${BUILD_DIR}/../services/${IMAGE_NAME}/Dockerfile"
    exit 1
fi

log_info "Using Dockerfile: ${DOCKERFILE}"

# Build image
log_info "Building..."
docker build -f "$DOCKERFILE" -t "${IMAGE_NAME}:${TAG}" "${BUILD_DIR}/.."

# Tag for registry
FULL_TAG="${REGISTRY}/${IMAGE_NAME}:${TAG}"
docker tag "${IMAGE_NAME}:${TAG}" "${FULL_TAG}"

log_info "Tagged as: ${FULL_TAG}"

# Push to registry
log_info "Pushing to registry..."
if docker push "${FULL_TAG}" 2>/dev/null; then
    log_info "Successfully pushed ${FULL_TAG}"
else
    log_warn "Failed to push to ${REGISTRY}, trying external address..."
    FULL_TAG="${REGISTRY_EXTERNAL}/${IMAGE_NAME}:${TAG}"
    docker tag "${IMAGE_NAME}:${TAG}" "${FULL_TAG}"
    if docker push "${FULL_TAG}" 2>/dev/null; then
        log_info "Successfully pushed ${FULL_TAG}"
    else
        log_error "Failed to push image"
        log_info "Is the registry running? Check with:"
        log_info "  kubectl get pods -n registry"
        exit 1
    fi
fi

log_info ""
log_info "=== Build Complete ==="
log_info "Image: ${IMAGE_NAME}:${TAG}"
log_info "Registry: ${FULL_TAG}"
log_info ""
log_info "To use in deployment:"
log_info "  image: ${FULL_TAG}"
