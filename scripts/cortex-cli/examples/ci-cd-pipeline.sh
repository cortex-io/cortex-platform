#!/usr/bin/env bash
#
# Example: CI/CD Pipeline Integration
#
# This script demonstrates how to integrate cortex-k8s into a CI/CD pipeline
# Suitable for Jenkins, GitLab CI, GitHub Actions, etc.
#

set -euo pipefail

# Configuration from environment or defaults
SERVICE="${SERVICE:-cortex-api}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
IMAGE_TAG="${CI_COMMIT_SHA:-$(git rev-parse --short HEAD)}"
REGISTRY="${REGISTRY:-cortex}"
NAMESPACE="${NAMESPACE:-${ENVIRONMENT}}"

echo "=============================================="
echo "CI/CD Pipeline: ${SERVICE}"
echo "=============================================="
echo "Environment: ${ENVIRONMENT}"
echo "Image Tag: ${IMAGE_TAG}"
echo "Namespace: ${NAMESPACE}"
echo "=============================================="
echo ""

# Function to handle errors
handle_error() {
    echo "✗ Pipeline failed at: $1"
    exit 1
}

# Step 1: Verify prerequisites
echo "[1/7] Verifying prerequisites..."
if ! command -v cortex-k8s &> /dev/null; then
    echo "✗ cortex-k8s not found"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "✗ kubectl not found"
    exit 1
fi

echo "✓ Prerequisites verified"
echo ""

# Step 2: Run tests
echo "[2/7] Running tests..."
if [[ -f "package.json" ]] && grep -q '"test"' package.json; then
    npm test || handle_error "Tests"
elif [[ -f "test.sh" ]]; then
    ./test.sh || handle_error "Tests"
else
    echo "⚠ No tests found, skipping..."
fi

echo "✓ Tests passed"
echo ""

# Step 3: Build Docker image
echo "[3/7] Building Docker image..."
if cortex-k8s build "${SERVICE}" "${IMAGE_TAG}"; then
    echo "✓ Build successful"
else
    handle_error "Build"
fi
echo ""

# Step 4: Push to registry
echo "[4/7] Pushing to registry..."
if cortex-k8s build "${SERVICE}" "${IMAGE_TAG}" --push; then
    echo "✓ Push successful"
else
    handle_error "Push"
fi
echo ""

# Step 5: Deploy to environment
echo "[5/7] Deploying to ${ENVIRONMENT}..."
if cortex-k8s deploy "${SERVICE}" --namespace="${NAMESPACE}"; then
    echo "✓ Deployment successful"
else
    handle_error "Deployment"
fi
echo ""

# Step 6: Health check
echo "[6/7] Running health check..."
sleep 10  # Wait for pods to start

MAX_RETRIES=30
RETRY_COUNT=0

while [[ ${RETRY_COUNT} -lt ${MAX_RETRIES} ]]; do
    if cortex-k8s test "${SERVICE}" --namespace="${NAMESPACE}" 2>/dev/null; then
        echo "✓ Health check passed"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [[ ${RETRY_COUNT} -eq ${MAX_RETRIES} ]]; then
        echo "✗ Health check failed after ${MAX_RETRIES} attempts"

        echo ""
        echo "Recent logs:"
        cortex-k8s logs "${SERVICE}" --namespace="${NAMESPACE}" --tail=50

        handle_error "Health check"
    fi

    echo "⏳ Waiting for service to be ready (${RETRY_COUNT}/${MAX_RETRIES})..."
    sleep 10
done
echo ""

# Step 7: Verify deployment
echo "[7/7] Verifying deployment..."
cortex-k8s status "${SERVICE}" --namespace="${NAMESPACE}"
echo ""

# Success
echo "=============================================="
echo "✓ Pipeline completed successfully!"
echo "=============================================="
echo ""
echo "Service: ${SERVICE}"
echo "Version: ${IMAGE_TAG}"
echo "Environment: ${ENVIRONMENT}"
echo "Namespace: ${NAMESPACE}"
echo ""
echo "View logs: cortex-k8s logs ${SERVICE} --namespace=${NAMESPACE} -f"
echo "Check status: cortex-k8s status ${SERVICE} --namespace=${NAMESPACE}"
echo ""

# Optional: Send notification
if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
    curl -X POST "${SLACK_WEBHOOK_URL}" \
        -H 'Content-Type: application/json' \
        -d "{\"text\": \"✓ ${SERVICE} ${IMAGE_TAG} deployed to ${ENVIRONMENT}\"}" \
        2>/dev/null || true
fi
