#!/usr/bin/env bash
#
# Example: Comprehensive health check
#
# Checks the health of all Cortex services
#

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-cortex}"

echo "Cortex Health Check - Namespace: ${NAMESPACE}"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get all deployments
deployments=$(kubectl get deployments -n "${NAMESPACE}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

if [[ -z "${deployments}" ]]; then
    echo -e "${RED}✗ No deployments found in namespace: ${NAMESPACE}${NC}"
    exit 1
fi

# Check each deployment
all_healthy=true

for deployment in ${deployments}; do
    echo "Checking: ${deployment}"

    # Get desired and ready replicas
    desired=$(kubectl get deployment "${deployment}" -n "${NAMESPACE}" \
        -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    ready=$(kubectl get deployment "${deployment}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")

    # Check if healthy
    if [[ "${ready}" == "${desired}" ]] && [[ "${desired}" != "0" ]]; then
        echo -e "  ${GREEN}✓${NC} ${ready}/${desired} replicas ready"
    else
        echo -e "  ${RED}✗${NC} ${ready}/${desired} replicas ready"
        all_healthy=false

        # Show pod status
        echo "  Pod status:"
        kubectl get pods -n "${NAMESPACE}" -l "app=${deployment}" \
            -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,READY:.status.conditions[?\(@.type==\"Ready\"\)].status \
            --no-headers | sed 's/^/    /'

        # Show recent events
        echo "  Recent events:"
        kubectl get events -n "${NAMESPACE}" \
            --field-selector involvedObject.name="${deployment}" \
            --sort-by='.lastTimestamp' \
            -o custom-columns=TIME:.lastTimestamp,MESSAGE:.message \
            --no-headers | tail -3 | sed 's/^/    /'
    fi

    echo ""
done

echo "=============================================="

if [[ "${all_healthy}" == "true" ]]; then
    echo -e "${GREEN}✓ All services are healthy!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some services are unhealthy${NC}"
    echo ""
    echo "Troubleshooting tips:"
    echo "  - Check logs: cortex-k8s logs <service>"
    echo "  - View details: cortex-k8s status <service>"
    echo "  - Restart service: cortex-k8s restart <service>"
    exit 1
fi
