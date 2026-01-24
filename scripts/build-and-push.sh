#!/bin/bash
# Build and push Docker images to k3s registry
# Usage: ./scripts/build-and-push.sh <service-name> [image-name]
#
# Examples:
#   ./scripts/build-and-push.sh health-monitor cortex-health-monitor
#   ./scripts/build-and-push.sh youtube-ingestion
#   ./scripts/build-and-push.sh implementation-worker cortex-implementation-worker

set -e

# Local port for port-forward to registry
LOCAL_PORT=5000
# The registry as seen inside the cluster (this is what pod manifests use)
CLUSTER_REGISTRY="10.43.170.72:5000"
# Where we push to via port-forward
PUSH_REGISTRY="localhost:$LOCAL_PORT"
SERVICES_DIR="/Users/ryandahlberg/Projects/cortex-platform/services"

# Service name is required
SERVICE_NAME="${1}"
IMAGE_NAME="${2:-$SERVICE_NAME}"

if [ -z "$SERVICE_NAME" ]; then
    echo "Usage: $0 <service-name> [image-name]"
    echo ""
    echo "Available services:"
    ls -1 "$SERVICES_DIR" | grep -v README | grep -v ".sh"
    exit 1
fi

SERVICE_PATH="$SERVICES_DIR/$SERVICE_NAME"

if [ ! -d "$SERVICE_PATH" ]; then
    echo "Error: Service directory not found: $SERVICE_PATH"
    exit 1
fi

if [ ! -f "$SERVICE_PATH/Dockerfile" ]; then
    echo "Error: Dockerfile not found in $SERVICE_PATH"
    exit 1
fi

echo "=============================================="
echo "Building: $SERVICE_NAME"
echo "Image:    $IMAGE_NAME:latest"
echo "Path:     $SERVICE_PATH"
echo "=============================================="

# Build the image with the cluster registry tag (for correct manifest matching)
cd "$SERVICE_PATH"
docker build -t "$CLUSTER_REGISTRY/$IMAGE_NAME:latest" -t "$PUSH_REGISTRY/$IMAGE_NAME:latest" .

echo ""
echo "Build complete."
echo ""

# Check if port-forward is already running
if ! nc -z localhost $LOCAL_PORT 2>/dev/null; then
    echo "Starting port-forward to registry..."
    kubectl port-forward svc/docker-registry -n cortex-chat $LOCAL_PORT:5000 &
    PF_PID=$!
    sleep 3

    # Verify port-forward is working
    if ! nc -z localhost $LOCAL_PORT 2>/dev/null; then
        echo "Error: Port-forward failed to start"
        kill $PF_PID 2>/dev/null
        exit 1
    fi
    STARTED_PF=true
else
    echo "Port-forward already running on port $LOCAL_PORT"
    STARTED_PF=false
fi

echo "Pushing to registry..."
docker push "$PUSH_REGISTRY/$IMAGE_NAME:latest"

# Clean up port-forward if we started it
if [ "$STARTED_PF" = true ]; then
    echo "Stopping port-forward..."
    kill $PF_PID 2>/dev/null
fi

echo ""
echo "=============================================="
echo "✅ Successfully built and pushed:"
echo "   $CLUSTER_REGISTRY/$IMAGE_NAME:latest"
echo ""
echo "To deploy, restart the deployment:"
echo "   kubectl rollout restart deployment/<deployment-name> -n <namespace>"
echo "=============================================="
