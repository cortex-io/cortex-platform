# Cortex MCP Server - Quick Reference

## Deployment Information

**Namespace:** `cortex-system`
**Service Name:** `cortex-mcp-server`
**Cluster IP:** `10.43.41.79`

## Endpoints

```
Health:   http://cortex-mcp-server.cortex-system.svc.cluster.local:8080/health
Metrics:  http://cortex-mcp-server.cortex-system.svc.cluster.local:8080/metrics
MCP:      http://cortex-mcp-server.cortex-system.svc.cluster.local:3000/query
```

## Quick Commands

### View Status
```bash
kubectl get deployment,pod,svc -n cortex-system -l app=cortex-mcp-server
```

### View Logs
```bash
kubectl logs -n cortex-system -l app=cortex-mcp-server --tail=50 -f
```

### Test Health
```bash
kubectl run test --rm -i --restart=Never --image=curlimages/curl -n cortex-system \
  -- curl -s http://cortex-mcp-server:8080/health
```

### Update Source Files
```bash
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex
./scripts/create-complete-configmap.sh
kubectl rollout restart deployment/cortex-mcp-server -n cortex-system
```

### Redeploy
```bash
kubectl apply -f /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/k8s/cortex-mcp-server-simple.yaml
```

## MCP Tools Available

1. **cortex_query** - Query routing to UniFi, Proxmox, Sandfly, K8s
2. **cortex_get_status** - Aggregate status from all subsystems

## Integration URLs

- UniFi: `http://unifi-mcp-server.cortex-system.svc.cluster.local:3000`
- Proxmox: `http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000`
- Sandfly: `http://sandfly-mcp-server.cortex-system.svc.cluster.local:8080`
- Kubernetes: (in-cluster API)

## Files

- **Deployment:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/k8s/cortex-mcp-server-simple.yaml`
- **ConfigMap Script:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/scripts/create-complete-configmap.sh`
- **Documentation:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/DEPLOYMENT_SUCCESS.md`
