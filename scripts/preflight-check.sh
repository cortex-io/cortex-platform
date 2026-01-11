#!/bin/bash
# Cortex Stack Pre-Flight Check Script
# Run this after cluster restarts, deployments, or when troubleshooting

set -e

echo "========================================"
echo "  Cortex Stack Pre-Flight Check"
echo "========================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    FAILED=1
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

FAILED=0

echo "1. Checking k3s cluster..."
NODES=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
READY_NODES=$(kubectl get nodes --no-headers | grep " Ready" | wc -l | tr -d ' ')
if [ "$NODES" -eq "$READY_NODES" ]; then
    check_pass "All $NODES nodes are Ready"
else
    check_fail "Only $READY_NODES/$NODES nodes are Ready"
fi

CPU_CORES=$(kubectl get node k3s-master01 -o jsonpath='{.status.capacity.cpu}')
if [ "$CPU_CORES" -eq 6 ]; then
    check_pass "Nodes have 6 CPU cores"
else
    check_fail "Nodes have $CPU_CORES CPU cores (expected 6)"
fi

echo ""
echo "2. Checking MetalLB..."
METALLB_PODS=$(kubectl get pods -n metallb-system --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$METALLB_PODS" -gt 0 ]; then
    check_pass "MetalLB pods running ($METALLB_PODS)"
else
    check_fail "MetalLB pods not found"
fi

echo ""
echo "3. Checking Traefik..."
TRAEFIK_IP=$(kubectl get svc -n kube-system traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
if [ "$TRAEFIK_IP" == "10.88.145.200" ]; then
    check_pass "Traefik LoadBalancer IP: $TRAEFIK_IP"
else
    check_fail "Traefik LoadBalancer IP: $TRAEFIK_IP (expected 10.88.145.200)"
fi

echo ""
echo "4. Checking MCP Servers..."
for MCP in unifi-mcp-server wazuh-mcp-server proxmox-mcp-server; do
    POD_STATUS=$(kubectl get pod -n cortex-system -l app=$MCP -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
    if [ "$POD_STATUS" == "Running" ]; then
        check_pass "$MCP is Running"
    else
        check_fail "$MCP status: $POD_STATUS"
    fi
done

echo ""
echo "5. Checking MCP Service Aliases..."
for SVC in unifi-mcp wazuh-mcp proxmox-mcp; do
    SVC_EXISTS=$(kubectl get svc -n cortex-system $SVC --no-headers 2>/dev/null | wc -l | tr -d ' ')
    if [ "$SVC_EXISTS" -eq 1 ]; then
        check_pass "Service alias $SVC exists"
    else
        check_fail "Service alias $SVC missing - run: kubectl apply -f k8s/mcp-service-aliases.yaml"
    fi
done

echo ""
echo "6. Checking MCP Health Endpoints..."
HEALTH_CHECKS=0
HEALTH_PASS=0

# UniFi
UNIFI_HEALTH=$(kubectl run test-mcp-unifi-$RANDOM --rm -i --restart=Never --image=curlimages/curl --quiet -- \
    curl -s -m 5 http://unifi-mcp-server.cortex-system.svc.cluster.local:3000/health 2>/dev/null | grep -o '"status":"healthy"' || echo "")
HEALTH_CHECKS=$((HEALTH_CHECKS + 1))
if [ -n "$UNIFI_HEALTH" ]; then
    check_pass "UniFi MCP health check passed"
    HEALTH_PASS=$((HEALTH_PASS + 1))
else
    check_fail "UniFi MCP health check failed"
fi

# Wazuh
WAZUH_HEALTH=$(kubectl run test-mcp-wazuh-$RANDOM --rm -i --restart=Never --image=curlimages/curl --quiet -- \
    curl -s -m 5 http://wazuh-mcp-server.cortex-system.svc.cluster.local:8080/health 2>/dev/null | grep -o '"status":"healthy"' || echo "")
HEALTH_CHECKS=$((HEALTH_CHECKS + 1))
if [ -n "$WAZUH_HEALTH" ]; then
    check_pass "Wazuh MCP health check passed"
    HEALTH_PASS=$((HEALTH_PASS + 1))
else
    check_fail "Wazuh MCP health check failed"
fi

# Proxmox
PROXMOX_HEALTH=$(kubectl run test-mcp-proxmox-$RANDOM --rm -i --restart=Never --image=curlimages/curl --quiet -- \
    curl -s -m 5 http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000/health 2>/dev/null | grep -o '"status":"healthy"' || echo "")
HEALTH_CHECKS=$((HEALTH_CHECKS + 1))
if [ -n "$PROXMOX_HEALTH" ]; then
    check_pass "Proxmox MCP health check passed"
    HEALTH_PASS=$((HEALTH_PASS + 1))
else
    check_fail "Proxmox MCP health check failed"
fi

echo "   ($HEALTH_PASS/$HEALTH_CHECKS health checks passed)"

echo ""
echo "7. Checking Cortex Orchestrator..."
CORTEX_POD=$(kubectl get pod -n cortex -l app=cortex-orchestrator -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$CORTEX_POD" == "Running" ]; then
    check_pass "Cortex orchestrator is Running"

    # Check MCP env vars
    UNIFI_ENV=$(kubectl get deployment cortex-orchestrator -n cortex -o jsonpath='{.spec.template.spec.containers[0].env}' | jq -r '.[] | select(.name=="UNIFI_MCP_URL") | .value' 2>/dev/null)
    if [[ "$UNIFI_ENV" == *"unifi-mcp"* ]]; then
        check_pass "Cortex MCP URLs configured"
    else
        check_warn "Cortex MCP URLs may need updating"
    fi
else
    check_fail "Cortex orchestrator status: $CORTEX_POD"
fi

echo ""
echo "8. Checking Cortex Chat..."
CHAT_POD=$(kubectl get pod -n cortex-chat -l app=cortex-chat -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$CHAT_POD" == "Running" ]; then
    check_pass "Cortex chat is Running"
else
    check_fail "Cortex chat status: $CHAT_POD"
fi

CHAT_PROXY_POD=$(kubectl get pod -n cortex-chat -l app=cortex-chat-proxy -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$CHAT_PROXY_POD" == "Running" ]; then
    check_pass "Cortex chat proxy is Running"
else
    check_fail "Cortex chat proxy status: $CHAT_PROXY_POD"
fi

CHAT_IP=$(kubectl get svc -n cortex-chat cortex-chat-frontend -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
if [ -n "$CHAT_IP" ]; then
    check_pass "Chat LoadBalancer IP: $CHAT_IP"
else
    check_fail "Chat LoadBalancer has no IP"
fi

echo ""
echo "9. Checking Traefik Ingress Routes..."
CHAT_INGRESS=$(kubectl get ingress -n cortex-chat cortex-chat --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$CHAT_INGRESS" -eq 1 ]; then
    check_pass "Chat ingress route exists"
else
    check_fail "Chat ingress route missing"
fi

MCP_ROUTES=$(kubectl get ingressroute -n cortex-system --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$MCP_ROUTES" -ge 3 ]; then
    check_pass "MCP ingress routes exist ($MCP_ROUTES)"
else
    check_warn "Only $MCP_ROUTES MCP ingress routes found (expected at least 3)"
fi

echo ""
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    echo "Cortex stack is healthy ✓"
    echo ""
    echo "Access points:"
    echo "  Chat App:  https://chat.ry-ops.dev"
    echo "  Chat IP:   http://$CHAT_IP"
    echo ""
    exit 0
else
    echo -e "${RED}Some checks failed!${NC}"
    echo ""
    echo "Common fixes:"
    echo "  1. Apply MCP service aliases:"
    echo "     kubectl apply -f k8s/mcp-service-aliases.yaml"
    echo ""
    echo "  2. Restart failed components:"
    echo "     kubectl rollout restart deployment -n cortex-system <deployment>"
    echo "     kubectl rollout restart deployment -n cortex cortex-orchestrator"
    echo "     kubectl rollout restart deployment -n cortex-chat cortex-chat"
    echo ""
    echo "  3. Check logs for errors:"
    echo "     kubectl logs -n cortex-system deployment/<mcp-server> --tail=50"
    echo "     kubectl logs -n cortex deployment/cortex-orchestrator --tail=50"
    echo ""
    echo "See docs/PREFLIGHT-PLAYBOOK.md for detailed troubleshooting"
    echo ""
    exit 1
fi

echo ""
echo "10. Checking Automation Daemons..."
ZOMBIE_DAEMON=$(kubectl get pod -n cortex-system -l app=zombie-cleanup-daemon -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$ZOMBIE_DAEMON" == "Running" ]; then
    check_pass "Zombie cleanup daemon is Running"
else
    check_fail "Zombie cleanup daemon status: $ZOMBIE_DAEMON"
fi

AUTOFIX_DAEMON=$(kubectl get pod -n cortex-system -l app=auto-fix-daemon -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$AUTOFIX_DAEMON" == "Running" ]; then
    check_pass "Auto-fix daemon is Running"
else
    check_fail "Auto-fix daemon status: $AUTOFIX_DAEMON"
fi
