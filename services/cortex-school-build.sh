#!/bin/bash
# Build script for Cortex Online School services
# Builds and pushes all 5 service images to local registry

set -e

REGISTRY="10.43.170.72:5000"
SERVICES=("coordinator" "moe-router" "rag-validator" "implementation-worker" "health-monitor")

echo "Building Cortex Online School services..."

for service in "${SERVICES[@]}"; do
    echo ""
    echo "========================================"
    echo "Building cortex-$service"
    echo "========================================"

    cd "$service"

    # Build image
    docker build -t "cortex-$service:latest" .

    # Tag for registry
    docker tag "cortex-$service:latest" "$REGISTRY/cortex-$service:latest"

    # Push to registry
    docker push "$REGISTRY/cortex-$service:latest"

    echo "✓ Successfully built and pushed cortex-$service"

    cd ..
done

echo ""
echo "========================================"
echo "All services built and pushed successfully!"
echo "========================================"
echo ""
echo "Services deployed:"
for service in "${SERVICES[@]}"; do
    echo "  - $REGISTRY/cortex-$service:latest"
done
echo ""
echo "Next: Restart pods in cortex-school namespace"
echo "  kubectl delete pods -n cortex-school --all"
