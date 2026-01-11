#!/usr/bin/env bash
#
# Example: Deploy all Cortex services
#
# This script demonstrates how to deploy multiple services using cortex-k8s
#

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-cortex}"
SERVICES=(
    "cortex-api"
    "cortex-chat"
    "cortex-coordinator"
    "cortex-mcp-server"
    "cortex-worker"
    "cortex-dashboard"
)

echo "Deploying all Cortex services to namespace: ${NAMESPACE}"
echo ""

# Deploy each service
for service in "${SERVICES[@]}"; do
    echo "========================================"
    echo "Deploying: ${service}"
    echo "========================================"

    if cortex-k8s deploy "${service}" --namespace="${NAMESPACE}"; then
        echo "✓ ${service} deployed successfully"
    else
        echo "✗ ${service} deployment failed"
        exit 1
    fi

    echo ""
done

echo "========================================"
echo "All services deployed!"
echo "========================================"
echo ""

# Show final status
echo "Checking status..."
cortex-k8s status --namespace="${NAMESPACE}"

echo ""
echo "Done! Services are deployed to namespace: ${NAMESPACE}"
