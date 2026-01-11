# Cortex Stack Pre-Flight Playbook

## Overview
This playbook ensures the entire Cortex stack is healthy and properly configured. Run this after:
- Cluster restarts/reboots
- Major deployments
- Troubleshooting connectivity issues
- Before critical demos/presentations

## Stack Dependencies
```
k3s Cluster (CPU/Memory/Network)
    ↓
Traefik Ingress Controller
    ↓
MetalLB Load Balancer
    ↓
MCP Servers (UniFi, Sandfly, Proxmox, Cloudflare)
    ↓
Cortex Orchestrator
    ↓
Cortex Chat App
```

## Pre-Flight Checklist

### 1. K3s Cluster Health ✅

**Check node status:**
```bash
kubectl get nodes -o wide
```
**Expected:** All nodes `Ready`, 6 CPUs per node

**Check node resources:**
```bash
kubectl top nodes
```
**Expected:** CPU < 80%, Memory < 80% on all nodes

**Check for resource pressure:**
```bash
kubectl describe nodes | grep -A 5 "Conditions:"
```
**Expected:** No `MemoryPressure`, `DiskPressure`, or `PIDPressure`

**Fix if failing:**
```bash
# Restart unhealthy nodes via Proxmox
# See: docs/node-restart-procedure.md
```

---

### 2. MetalLB Load Balancer ✅

**Check MetalLB pods:**
```bash
kubectl get pods -n metallb-system
```
**Expected:** All pods `Running`

**Check IP pool:**
```bash
kubectl get ipaddresspool -n metallb-system
```
**Expected:** Pool configured with 10.88.145.200-10.88.145.220

**Test IP allocation:**
```bash
kubectl get svc -A | grep LoadBalancer
```
**Expected:** All LoadBalancer services have EXTERNAL-IP assigned

**Fix if failing:**
```bash
kubectl rollout restart deployment -n metallb-system
```

---

### 3. Traefik Ingress Controller ✅

**Check Traefik pods:**
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
```
**Expected:** All pods `Running`

**Check Traefik service:**
```bash
kubectl get svc -n kube-system traefik
```
**Expected:** LoadBalancer with EXTERNAL-IP 10.88.145.200

**Test Traefik dashboard (optional):**
```bash
kubectl port-forward -n kube-system $(kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik -o name | head -1) 9000:9000
# Visit http://localhost:9000/dashboard/
```

**Check ingress routes:**
```bash
kubectl get ingressroute -A
```
**Expected:** Routes for chat, cortex-api, and all MCP servers

**Fix if failing:**
```bash
kubectl rollout restart deployment -n kube-system traefik
```

---

### 4. MCP Servers ✅

**Check all MCP pods:**
```bash
kubectl get pods -n cortex-system | grep mcp
```
**Expected:** All MCP pods `Running` (1/1 READY)

```
unifi-mcp-server-*     1/1  Running
sandfly-mcp-server-*     1/1  Running
proxmox-mcp-server-*   1/1  Running
cloudflare-mcp-server-* 1/1 Running
```

**Check MCP services:**
```bash
kubectl get svc -n cortex-system | grep mcp
```
**Expected:**
```
unifi-mcp-server      ClusterIP  *  3000/TCP
sandfly-mcp-server      ClusterIP  *  8080/TCP
proxmox-mcp-server    ClusterIP  *  3000/TCP
cloudflare-mcp-server ClusterIP  *  3000/TCP

# Alias services for backward compatibility
unifi-mcp             ClusterIP  *  3000/TCP
sandfly-mcp             ClusterIP  *  3000/TCP (→8080)
proxmox-mcp           ClusterIP  *  3000/TCP
```

**Test MCP health endpoints (internal):**
```bash
kubectl run test-mcp --rm -i --restart=Never --image=curlimages/curl -- sh -c "
echo 'UniFi:' && curl -s http://unifi-mcp-server.cortex-system.svc.cluster.local:3000/health
echo 'Sandfly:' && curl -s http://sandfly-mcp-server.cortex-system.svc.cluster.local:8080/health
echo 'Proxmox:' && curl -s http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000/health
"
```
**Expected:** All return `{"status": "healthy"}`

**Test MCP external access (Traefik):**
```bash
curl -k --resolve unifi-mcp.ry-ops.dev:443:10.88.145.200 https://unifi-mcp.ry-ops.dev/health
curl -k --resolve sandfly-mcp.ry-ops.dev:443:10.88.145.200 https://sandfly-mcp.ry-ops.dev/health
curl -k --resolve proxmox-mcp.ry-ops.dev:443:10.88.145.200 https://proxmox-mcp.ry-ops.dev/health
```
**Expected:** All return `{"status": "healthy"}`

**Fix if failing:**
```bash
# Check logs for specific MCP server
kubectl logs -n cortex-system deployment/unifi-mcp-server --tail=50
kubectl logs -n cortex-system deployment/sandfly-mcp-server --tail=50
kubectl logs -n cortex-system deployment/proxmox-mcp-server --tail=50

# Restart MCP servers
kubectl rollout restart deployment -n cortex-system unifi-mcp-server
kubectl rollout restart deployment -n cortex-system sandfly-mcp-server
kubectl rollout restart deployment -n cortex-system proxmox-mcp-server

# If pods stuck in Pending (CPU issues), check node resources
kubectl describe pod -n cortex-system <pod-name>
```

---

### 5. Cortex Orchestrator ✅

**Check Cortex orchestrator pod:**
```bash
kubectl get pods -n cortex -l app=cortex-orchestrator
```
**Expected:** Pod `Running` (1/1 READY)

**Check Cortex service:**
```bash
kubectl get svc -n cortex cortex-orchestrator
```
**Expected:** ClusterIP service on port 8000

**Verify MCP environment variables:**
```bash
kubectl get deployment cortex-orchestrator -n cortex -o jsonpath='{.spec.template.spec.containers[0].env}' | jq '.[] | select(.name | contains("MCP"))'
```
**Expected:**
```json
{
  "name": "UNIFI_MCP_URL",
  "value": "http://unifi-mcp-server.cortex-system.svc.cluster.local:3000"
}
{
  "name": "SANDFLY_MCP_URL",
  "value": "http://sandfly-mcp-server.cortex-system.svc.cluster.local:8080"
}
{
  "name": "PROXMOX_MCP_URL",
  "value": "http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000"
}
```

**Test Cortex API:**
```bash
kubectl run test-cortex --rm -i --restart=Never --image=curlimages/curl -- \
  curl -s http://cortex-orchestrator.cortex.svc.cluster.local:8000/health
```
**Expected:** Healthy response

**Check Cortex logs:**
```bash
kubectl logs -n cortex deployment/cortex-orchestrator --tail=50
```
**Expected:** No errors, "Intelligence: ENABLED ✓"

**Fix if failing:**
```bash
# Check if docker registry is running (needed for image pulls)
kubectl get pods -n cortex-chat | grep docker-registry

# If registry down, restart it
kubectl delete pod -n cortex-chat -l app=docker-registry

# Restart Cortex
kubectl rollout restart deployment -n cortex cortex-orchestrator

# If ImagePullBackOff, check registry logs
kubectl logs -n cortex-chat deployment/docker-registry
```

---

### 6. Cortex Chat App ✅

**Check chat pods:**
```bash
kubectl get pods -n cortex-chat
```
**Expected:**
```
cortex-chat-*         3/3  Running
cortex-chat-proxy-*   1/1  Running
redis-*               1/1  Running
```

**Check chat services:**
```bash
kubectl get svc -n cortex-chat
```
**Expected:**
```
cortex-chat            ClusterIP      *  80/TCP, 8080/TCP
cortex-chat-frontend   LoadBalancer   *  80/TCP (EXTERNAL-IP assigned)
cortex-chat-proxy      ClusterIP      *  8080/TCP
redis                  ClusterIP      *  6379/TCP
```

**Check chat ingress:**
```bash
kubectl get ingress -n cortex-chat cortex-chat
```
**Expected:** Host `chat.ry-ops.dev`, ADDRESS `10.88.145.200`

**Test chat app (external):**
```bash
curl -k --resolve chat.ry-ops.dev:443:10.88.145.200 https://chat.ry-ops.dev | head -20
```
**Expected:** HTML response with "Cortex Chat - v2.0"

**Test chat proxy:**
```bash
kubectl run test-chat-proxy --rm -i --restart=Never --image=curlimages/curl -- \
  curl -s http://cortex-chat-proxy.cortex-chat.svc.cluster.local:8080/health
```
**Expected:** `{"status": "healthy", "mode": "proxy"}`

**Check nginx routing:**
```bash
kubectl get configmap -n cortex-chat cortex-chat-nginx -o jsonpath='{.data.nginx\.conf}' | grep "upstream backend"
```
**Expected:** Points to `cortex-chat-proxy.cortex-chat.svc.cluster.local:8080`

**Fix if failing:**
```bash
# Check chat logs
kubectl logs -n cortex-chat deployment/cortex-chat --tail=50

# Check proxy logs
kubectl logs -n cortex-chat deployment/cortex-chat-proxy --tail=50

# Restart chat components
kubectl rollout restart deployment -n cortex-chat cortex-chat
kubectl rollout restart deployment -n cortex-chat cortex-chat-proxy

# If redis failing, restart it
kubectl delete pod -n cortex-chat -l app=redis
```

---

## Full Health Check Script

Run this automated script to check everything:

```bash
#!/bin/bash
# scripts/preflight-check.sh

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
NODES=$(kubectl get nodes --no-headers | wc -l)
READY_NODES=$(kubectl get nodes --no-headers | grep " Ready" | wc -l)
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
METALLB_PODS=$(kubectl get pods -n metallb-system --no-headers 2>/dev/null | wc -l)
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
for MCP in unifi-mcp-server sandfly-mcp-server proxmox-mcp-server; do
    POD_STATUS=$(kubectl get pod -n cortex-system -l app=$MCP -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
    if [ "$POD_STATUS" == "Running" ]; then
        check_pass "$MCP is Running"
    else
        check_fail "$MCP status: $POD_STATUS"
    fi
done

echo ""
echo "5. Checking MCP Health Endpoints..."
for MCP_URL in "unifi-mcp-server.cortex-system.svc.cluster.local:3000" \
               "sandfly-mcp-server.cortex-system.svc.cluster.local:8080" \
               "proxmox-mcp-server.cortex-system.svc.cluster.local:3000"; do
    HEALTH=$(kubectl run test-mcp-health-$RANDOM --rm -i --restart=Never --image=curlimages/curl -- \
        curl -s -m 5 http://$MCP_URL/health 2>/dev/null | grep -o '"status":"healthy"' || echo "")

    if [ -n "$HEALTH" ]; then
        check_pass "$MCP_URL/health is healthy"
    else
        check_fail "$MCP_URL/health failed"
    fi
done

echo ""
echo "6. Checking Cortex Orchestrator..."
CORTEX_POD=$(kubectl get pod -n cortex -l app=cortex-orchestrator -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$CORTEX_POD" == "Running" ]; then
    check_pass "Cortex orchestrator is Running"
else
    check_fail "Cortex orchestrator status: $CORTEX_POD"
fi

echo ""
echo "7. Checking Cortex Chat..."
CHAT_POD=$(kubectl get pod -n cortex-chat -l app=cortex-chat -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
if [ "$CHAT_POD" == "Running" ]; then
    check_pass "Cortex chat is Running"
else
    check_fail "Cortex chat status: $CHAT_POD"
fi

CHAT_IP=$(kubectl get svc -n cortex-chat cortex-chat-frontend -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
if [ -n "$CHAT_IP" ]; then
    check_pass "Chat LoadBalancer IP: $CHAT_IP"
else
    check_fail "Chat LoadBalancer has no IP"
fi

echo ""
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    echo "Cortex stack is healthy ✓"
    exit 0
else
    echo -e "${RED}Some checks failed!${NC}"
    echo "Review errors above and run fixes"
    exit 1
fi
```

---

## Common Issues & Fixes

### Issue: MCP pods stuck in Pending
**Cause:** Insufficient CPU after node restart
**Fix:**
```bash
# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# If CPU at 100%, may need to:
# 1. Scale down non-critical workloads
# 2. Increase node CPU cores via Proxmox
```

### Issue: Cortex can't reach MCP servers
**Cause:** Service name mismatch or port mismatch
**Fix:**
```bash
# Ensure alias services exist
kubectl get svc -n cortex-system | grep -E "unifi-mcp|sandfly-mcp|proxmox-mcp"

# If missing, create them:
kubectl apply -f /Users/ryandahlberg/Projects/cortex/k8s/mcp-service-aliases.yaml
```

### Issue: Chat app returns 502/504
**Cause:** Chat proxy can't reach Cortex orchestrator
**Fix:**
```bash
# Check proxy logs
kubectl logs -n cortex-chat deployment/cortex-chat-proxy --tail=50

# Verify proxy config
kubectl get configmap -n cortex-chat cortex-chat-nginx -o yaml | grep cortex-orchestrator

# Should point to: cortex-orchestrator.cortex.svc.cluster.local:8000
```

### Issue: Docker registry unavailable after node restart
**Cause:** PVC stuck on old node
**Fix:**
```bash
# Find stuck volume attachment
kubectl get volumeattachment | grep registry

# Delete it
kubectl delete volumeattachment <name>

# Delete pod to recreate
kubectl delete pod -n cortex-chat -l app=docker-registry
```

### Issue: Traefik ingress not routing
**Cause:** Traefik pods restarted, routes not synced
**Fix:**
```bash
# Restart Traefik
kubectl rollout restart deployment -n kube-system traefik

# Verify routes
kubectl get ingressroute -A
```

---

## Post-Node-Restart Procedure

After restarting k3s nodes (for CPU upgrades, etc.), follow this exact sequence:

1. **Wait for all nodes to be Ready** (5-10 minutes)
   ```bash
   kubectl get nodes -w
   ```

2. **Check for stuck pods**
   ```bash
   kubectl get pods -A | grep -E "Unknown|Pending|CrashLoop"
   ```

3. **Fix volume attachments** (if any pods stuck)
   ```bash
   kubectl get volumeattachment
   # Delete any stuck attachments
   ```

4. **Verify MCP servers**
   ```bash
   kubectl get pods -n cortex-system | grep mcp
   # All should be Running
   ```

5. **Verify Cortex orchestrator**
   ```bash
   kubectl get pods -n cortex | grep orchestrator
   ```

6. **Run full pre-flight check**
   ```bash
   ./scripts/preflight-check.sh
   ```

7. **Test chat app end-to-end**
   ```bash
   curl -k https://chat.ry-ops.dev | grep "Cortex Chat"
   ```

---

## Quick Reference

**Check everything:**
```bash
./scripts/preflight-check.sh
```

**Restart everything (nuclear option):**
```bash
kubectl rollout restart deployment -n cortex-system --all
kubectl rollout restart deployment -n cortex cortex-orchestrator
kubectl rollout restart deployment -n cortex-chat cortex-chat cortex-chat-proxy
```

**Watch pod status:**
```bash
watch -n 2 "kubectl get pods -n cortex-system && echo && kubectl get pods -n cortex && echo && kubectl get pods -n cortex-chat"
```

**Tail all logs:**
```bash
stern -n cortex-system mcp
stern -n cortex orchestrator
stern -n cortex-chat chat
```

---

## Monitoring & Alerts (Future)

TODO: Set up automated monitoring with alerts for:
- [ ] Node CPU/Memory > 80%
- [ ] MCP server health checks failing
- [ ] Cortex orchestrator errors
- [ ] Chat app 5xx errors
- [ ] Traefik ingress failures

Recommended tools:
- Prometheus + Grafana
- Alertmanager → Slack/Email
- Uptime monitoring (UptimeRobot, Better Uptime)
