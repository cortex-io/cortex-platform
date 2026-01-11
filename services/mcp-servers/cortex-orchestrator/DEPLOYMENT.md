# Cortex Orchestrator - Deployment Guide

Complete guide for deploying the Cortex Intelligent Orchestrator to your k3s cluster.

## Prerequisites

1. **Running k3s cluster** with:
   - Metrics Server enabled (`kubectl top nodes` works)
   - At least 3 nodes recommended
   - Minimum 8GB RAM, 4 CPU cores per node

2. **cortex-awareness MCP server** deployed and accessible at:
   - `http://cortex-awareness.cortex-system.svc.cluster.local:8080`

3. **commit-relay** (optional but recommended) deployed at:
   - `http://commit-relay.cortex-system.svc.cluster.local:8000`

4. **Container registry access** for pushing orchestrator image

## Step 1: Build Container Image

```bash
# From the cortex-orchestrator directory
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex-orchestrator

# Build the image
docker build -t cortex/orchestrator:latest .

# Tag for your registry
docker tag cortex/orchestrator:latest <your-registry>/cortex/orchestrator:latest

# Push to registry
docker push <your-registry>/cortex/orchestrator:latest
```

## Step 2: Update Image References

Edit `k8s/deployment.yaml` to use your registry:

```yaml
spec:
  template:
    spec:
      containers:
      - name: orchestrator
        image: <your-registry>/cortex/orchestrator:latest
```

## Step 3: Create Namespace

```bash
# Create cortex-system namespace if it doesn't exist
kubectl create namespace cortex-system
```

## Step 4: Review and Customize Configuration

Edit `k8s/configmap.yaml` to match your cluster:

### Key Configuration Values:

**Dynamic Limiter:**
```yaml
limiter:
  cpu_headroom_percent: 30        # Adjust based on cluster size
  memory_headroom_percent: 30
  absolute_min_pods: 5
  absolute_max_pods: 500          # Adjust to cluster capacity
```

**Spawn Modulator:**
```yaml
modulator:
  base_spawn_rate: 10             # pods/second (adjust for cluster)
  max_pending_queue: 100
```

**Stuck Detector:**
```yaml
detector:
  stuck_timeout: 300              # 5 minutes (adjust tolerance)
  stuck_threshold: 0.4            # Liveness score threshold
```

**Agent Resource Profiles:**
Update these to match your actual agent resource usage:

```yaml
limiter:
  agent_profiles:
    coordinator_master:
      cpu_millicores: 500
      memory_mb: 512

    # Add profiles for your agent types
    my_custom_agent:
      cpu_millicores: 800
      memory_mb: 1024
```

## Step 5: Deploy RBAC

```bash
kubectl apply -f k8s/rbac.yaml
```

Verify RBAC creation:
```bash
kubectl get serviceaccount cortex-orchestrator -n cortex-system
kubectl get clusterrole cortex-orchestrator
kubectl get clusterrolebinding cortex-orchestrator
```

## Step 6: Deploy Configuration

```bash
kubectl apply -f k8s/configmap.yaml
```

Verify ConfigMap:
```bash
kubectl get configmap cortex-orchestrator-config -n cortex-system
```

## Step 7: Deploy Orchestrator

```bash
kubectl apply -f k8s/deployment.yaml
```

## Step 8: Verify Deployment

### Check Pod Status:
```bash
kubectl get pods -n cortex-system -l app=cortex-orchestrator
```

Expected output:
```
NAME                                   READY   STATUS    RESTARTS   AGE
cortex-orchestrator-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
```

### Check Logs:
```bash
kubectl logs -n cortex-system -l app=cortex-orchestrator --tail=50
```

Look for:
```json
{"event": "cortex_orchestrator_starting", "level": "info", ...}
{"event": "awareness_client_initialized", "level": "info", ...}
{"event": "k8s_client_initialized", "level": "info", ...}
{"event": "prometheus_metrics_started", "level": "info", "port": 9090}
{"event": "orchestrator_monitoring_started", "level": "info"}
{"event": "mcp_server_started", "level": "info"}
```

### Check Service:
```bash
kubectl get svc cortex-orchestrator -n cortex-system
```

Expected output:
```
NAME                   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
cortex-orchestrator    ClusterIP   10.43.xxx.xxx   <none>        8080/TCP,9090/TCP   1m
```

## Step 9: Test MCP Connectivity

From another pod in the cluster:

```bash
# Test health endpoint
curl http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/health

# Test metrics endpoint
curl http://cortex-orchestrator.cortex-system.svc.cluster.local:9090/metrics
```

## Step 10: Monitor Orchestrator

### View Orchestration Status:
```bash
# Port-forward to access MCP server locally
kubectl port-forward -n cortex-system svc/cortex-orchestrator 8080:8080

# In another terminal, use MCP client to call tools
# (Example using Python MCP client)
python -c "
import asyncio
from mcp import Client

async def main():
    client = Client('http://localhost:8080')
    status = await client.call_tool('get_orchestration_status')
    print(status)

asyncio.run(main())
"
```

### View Prometheus Metrics:
```bash
# Port-forward metrics endpoint
kubectl port-forward -n cortex-system svc/cortex-orchestrator 9090:9090

# Access metrics
curl http://localhost:9090/metrics
```

### Monitor Logs:
```bash
# Follow logs in real-time
kubectl logs -n cortex-system -l app=cortex-orchestrator -f --tail=100
```

## Step 11: Integration with Cortex Agents

### Update Agent Spawning Code:

All Cortex agents that spawn new pods should integrate with the orchestrator:

```python
from mcp import Client

orchestrator = Client('http://cortex-orchestrator.cortex-system.svc.cluster.local:8080')

# Before spawning a pod
decision = await orchestrator.call_tool('spawn_agent', {
    'agent_spec': {
        'agent_type': 'code_agent',
        'task_id': 'task-12345',
        'priority': 7,
        'estimated_duration': 600
    }
})

if decision['approved']:
    print(f"Spawn approved! Rate: {decision['current_rate']} pods/s")
    # Proceed with pod creation
else:
    print(f"Spawn throttled: {decision['reason']}")
    print(f"Retry after {decision['estimated_spawn_time']}s")
    # Queue for later or wait
```

### Agent Coordinator Integration:

Update your coordinator-master or spawning logic to:

1. **Query orchestrator before spawning**
2. **Respect throttling decisions**
3. **Use priority levels** (1-10, higher = more important)
4. **Provide estimated duration** for better scheduling

## Troubleshooting

### Pod Not Starting:

```bash
# Check events
kubectl describe pod -n cortex-system -l app=cortex-orchestrator

# Check RBAC permissions
kubectl auth can-i list pods --as=system:serviceaccount:cortex-system:cortex-orchestrator
kubectl auth can-i delete pods --as=system:serviceaccount:cortex-system:cortex-orchestrator
```

### Awareness Connection Failing:

```bash
# Test awareness connectivity from orchestrator pod
kubectl exec -n cortex-system -it <orchestrator-pod> -- \
  curl http://cortex-awareness.cortex-system.svc.cluster.local:8080/health
```

### High Memory Usage:

```bash
# Check resource usage
kubectl top pod -n cortex-system -l app=cortex-orchestrator

# If memory is high, adjust limits in deployment.yaml:
spec:
  resources:
    limits:
      memory: 1Gi  # Increase if needed
```

### Spawn Queue Saturated:

If you see "spawn_queue_saturated" errors:

1. **Increase max_pending_queue** in ConfigMap:
   ```yaml
   modulator:
     max_pending_queue: 200  # Increase from 100
   ```

2. **Restart orchestrator** to pick up changes:
   ```bash
   kubectl rollout restart deployment cortex-orchestrator -n cortex-system
   ```

### Stuck Pod Detection Not Working:

If pods aren't being detected as stuck:

1. **Verify commit-relay integration** is enabled:
   ```yaml
   integration:
     commit_relay:
       enabled: true
       url: "http://commit-relay.cortex-system.svc.cluster.local:8000"
   ```

2. **Lower stuck_threshold** for more aggressive detection:
   ```yaml
   detector:
     stuck_threshold: 0.3  # Lower from 0.4
     stuck_timeout: 180    # Reduce from 300s
   ```

## Monitoring and Alerts

### Key Metrics to Monitor:

**Prometheus metrics exposed on port 9090:**

- `cortex_orchestrator_spawn_rate` - Current spawn rate (pods/s)
- `cortex_orchestrator_active_agents` - Active pod count
- `cortex_orchestrator_capacity_limit` - Calculated capacity limit
- `cortex_orchestrator_stuck_pods` - Number of stuck pods detected
- `cortex_orchestrator_swap_count` - Successful pod swaps
- `cortex_orchestrator_queue_depth` - Pending spawn requests

### Recommended Alerts:

```yaml
# Prometheus AlertManager rules
groups:
- name: cortex-orchestrator
  rules:
  - alert: OrchestratorDown
    expr: up{job="cortex-orchestrator"} == 0
    for: 5m
    annotations:
      summary: "Orchestrator is down"

  - alert: HighStuckPodCount
    expr: cortex_orchestrator_stuck_pods > 5
    for: 10m
    annotations:
      summary: "More than 5 pods stuck"

  - alert: NearCapacity
    expr: cortex_orchestrator_active_agents / cortex_orchestrator_capacity_limit > 0.9
    for: 15m
    annotations:
      summary: "Cluster near capacity (>90%)"

  - alert: SpawnRateThrottled
    expr: cortex_orchestrator_spawn_rate < 2
    for: 10m
    annotations:
      summary: "Spawn rate heavily throttled (<2 pods/s)"
```

## Updating Configuration

To update configuration without downtime:

```bash
# 1. Edit ConfigMap
kubectl edit configmap cortex-orchestrator-config -n cortex-system

# 2. Restart orchestrator to pick up changes
kubectl rollout restart deployment cortex-orchestrator -n cortex-system

# 3. Verify restart
kubectl rollout status deployment cortex-orchestrator -n cortex-system
```

## Scaling Orchestrator

The orchestrator runs as a **single replica** by design (Recreate strategy).

**Why single replica?**
- Maintains consistent state (spawn queue, swap history)
- Avoids race conditions on pod swaps
- Simplified leader election

**High Availability:**
- Uses Recreate strategy for quick failover
- K8s will restart pod on different node if node fails
- Typically <10s downtime during failover

## Uninstalling

To remove the orchestrator:

```bash
# Delete deployment and service
kubectl delete -f k8s/deployment.yaml

# Delete ConfigMap
kubectl delete -f k8s/configmap.yaml

# Delete RBAC (if no longer needed)
kubectl delete -f k8s/rbac.yaml

# Verify cleanup
kubectl get all -n cortex-system -l app=cortex-orchestrator
```

## Next Steps

1. **Integrate with your agent spawning logic** (see Step 11)
2. **Set up Prometheus scraping** for orchestrator metrics
3. **Configure alerts** for orchestrator health
4. **Tune resource profiles** based on actual agent usage
5. **Monitor and adjust** spawn rates and thresholds

## Support

For issues or questions:
- Check logs: `kubectl logs -n cortex-system -l app=cortex-orchestrator`
- Review events: `kubectl get events -n cortex-system --sort-by='.lastTimestamp'`
- Verify RBAC: `kubectl auth can-i --list --as=system:serviceaccount:cortex-system:cortex-orchestrator`
