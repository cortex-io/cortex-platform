# Cortex Orchestrator - Quick Start

Get the orchestrator running in 5 minutes.

## Prerequisites

- k3s cluster with metrics-server
- cortex-awareness MCP server running
- Docker or Podman

## Fast Deploy

```bash
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex-orchestrator

# 1. Build image
docker build -t cortex/orchestrator:latest .

# 2. Tag for your registry (if using one)
docker tag cortex/orchestrator:latest localhost:5000/cortex/orchestrator:latest
docker push localhost:5000/cortex/orchestrator:latest

# 3. Update image in deployment (if using registry)
sed -i 's|cortex/orchestrator:latest|localhost:5000/cortex/orchestrator:latest|' k8s/deployment.yaml

# 4. Deploy everything
kubectl create namespace cortex-system 2>/dev/null || true
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml

# 5. Wait for ready
kubectl wait --for=condition=ready pod -l app=cortex-orchestrator -n cortex-system --timeout=60s

# 6. Check status
kubectl logs -n cortex-system -l app=cortex-orchestrator --tail=20
```

## Verify

```bash
# Check pod is running
kubectl get pods -n cortex-system -l app=cortex-orchestrator

# Check logs show successful startup
kubectl logs -n cortex-system -l app=cortex-orchestrator | grep "mcp_server_started"

# Test health endpoint
kubectl port-forward -n cortex-system svc/cortex-orchestrator 8080:8080 &
curl http://localhost:8080/health
```

Expected output:
```json
{"status": "healthy", "components": {"awareness": "ok", "k8s": "ok"}}
```

## Use It

Call the MCP tools from your agents:

```python
from mcp import Client

orchestrator = Client('http://cortex-orchestrator.cortex-system.svc.cluster.local:8080')

# Check orchestrator status
status = await orchestrator.call_tool('get_orchestration_status')
print(f"Active: {status['active_agents']}/{status['capacity_limit']}")
print(f"Spawn rate: {status['current_spawn_rate']} pods/s")

# Request spawn
decision = await orchestrator.call_tool('spawn_agent', {
    'agent_spec': {
        'agent_type': 'code_agent',
        'task_id': 'task-123',
        'priority': 7
    }
})

if decision['approved']:
    print(f"✅ Spawn approved! Queue position: {decision['queue_position']}")
else:
    print(f"❌ Throttled: {decision['reason']}")
```

## Monitor

```bash
# Follow logs
kubectl logs -n cortex-system -l app=cortex-orchestrator -f

# Watch metrics
kubectl port-forward -n cortex-system svc/cortex-orchestrator 9090:9090 &
curl http://localhost:9090/metrics | grep cortex_orchestrator
```

## Tune

Edit configuration:
```bash
kubectl edit configmap cortex-orchestrator-config -n cortex-system
kubectl rollout restart deployment cortex-orchestrator -n cortex-system
```

Common tuning:
- **Increase spawn rate**: `base_spawn_rate: 20` (from 10)
- **Increase max pods**: `absolute_max_pods: 1000` (from 500)
- **Faster stuck detection**: `stuck_timeout: 180` (from 300)
- **More aggressive swaps**: `stuck_threshold: 0.3` (from 0.4)

## Troubleshoot

```bash
# Pod not starting?
kubectl describe pod -n cortex-system -l app=cortex-orchestrator

# RBAC issues?
kubectl auth can-i list pods --as=system:serviceaccount:cortex-system:cortex-orchestrator

# Awareness connection failing?
kubectl exec -n cortex-system -it $(kubectl get pod -n cortex-system -l app=cortex-orchestrator -o name) -- \
  curl http://cortex-awareness.cortex-system.svc.cluster.local:8080/health
```

## Uninstall

```bash
kubectl delete -f k8s/deployment.yaml
kubectl delete -f k8s/configmap.yaml
kubectl delete -f k8s/rbac.yaml
```

## Full Documentation

- **Architecture**: README.md
- **Deployment Guide**: DEPLOYMENT.md
- **Implementation Details**: IMPLEMENTATION-COMPLETE.md
