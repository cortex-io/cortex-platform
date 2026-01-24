# Layer Activator Guide

The Layer Activator is a serverless MCP stack orchestration system that manages on-demand activation and deactivation of specialized AI processing stacks to optimize cluster resource usage.

## Overview

The Layer Activator solves the problem of resource constraints by:
- Scaling idle stacks to 0 replicas
- Automatically scaling up when traffic arrives
- Preserving learned vector embeddings via PVCs
- Reducing idle memory from ~20GB to ~512MB

## Architecture

```
                    ┌─────────────────────┐
                    │   Layer Activator   │
                    │   (Always Running)  │
                    └─────────┬───────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │ Stack 1 │         │ Stack 2 │         │ Stack N │
    │ (0→1)   │         │ (0→1)   │         │ (0→1)   │
    └─────────┘         └─────────┘         └─────────┘
```

## Configured Stacks

| Stack ID | Name | Namespace | Min Replicas | Cooldown |
|----------|------|-----------|--------------|----------|
| security-stack | Security Operations | cortex-security | 0 | 300s |
| infra-stack | Infrastructure Operations | cortex-system | 0 | 300s |
| knowledge-stack | Knowledge Operations | cortex-knowledge | 0 | 600s |
| school-stack | Cortex Online School | cortex-school | 1 | 0 |
| github-stack | GitHub Operations | cortex-system | 0 | 300s |
| dev-stack | Development Operations | cortex-dev | 0 | 300s |
| n8n-stack | N8N Workflows | cortex-system | 0 | 300s |

## API Endpoints

The Layer Activator exposes the following endpoints:

### Health Check
```bash
curl http://layer-activator.cortex-system.svc.cluster.local:8080/health
# {"status":"healthy"}
```

### List Stacks
```bash
curl http://layer-activator.cortex-system.svc.cluster.local:8080/stacks
# {"stacks":[{"id":"security-stack","status":"active","replicas":2},...]}
```

### Get Stack Details
```bash
curl http://layer-activator.cortex-system.svc.cluster.local:8080/stacks/{stack_id}
```

### Activate Stack
```bash
curl -X POST http://layer-activator.cortex-system.svc.cluster.local:8080/activate \
  -H "Content-Type: application/json" \
  -d '{"stack_id":"security-stack"}'
```

### Scale Down Stack
```bash
curl -X POST http://layer-activator.cortex-system.svc.cluster.local:8080/scale-down/{stack_id}
# {"stack_id":"dev-stack","status":"scaled_down"}
```

### Route Request (Auto-Activate)
```bash
curl -X POST http://layer-activator.cortex-system.svc.cluster.local:8080/route \
  -H "Content-Type: application/json" \
  -d '{"task_type":"security_scan","payload":{}}'
```

### Metrics
```bash
curl http://layer-activator.cortex-system.svc.cluster.local:8080/metrics
# {"total_stacks":7,"active_stacks":4,"scaled_down_stacks":3}
```

## Manual Operations

### Scale Down Idle Stacks to Free Memory

When cluster memory is constrained:

```bash
# Using kubectl run with curl
kubectl run -it --rm curl-cmd --image=curlimages/curl --restart=Never -- \
  curl -s -X POST http://layer-activator.cortex-system.svc.cluster.local:8080/scale-down/dev-stack

kubectl run -it --rm curl-cmd2 --image=curlimages/curl --restart=Never -- \
  curl -s -X POST http://layer-activator.cortex-system.svc.cluster.local:8080/scale-down/github-stack
```

### Check Current Stack Status

```bash
kubectl run -it --rm curl-status --image=curlimages/curl --restart=Never -- \
  curl -s http://layer-activator.cortex-system.svc.cluster.local:8080/stacks
```

## Configuration

The Layer Activator configuration is stored in a ConfigMap:

```bash
kubectl get configmap -n cortex-system layer-activator-config -o yaml
```

### Stack Configuration Format

```yaml
stacks:
  - id: security-stack
    name: Security Operations
    namespace: cortex-security
    min_replicas: 0
    max_replicas: 5
    cooldown: 300
    service_port: 3000
    components:
      - deployment: sandfly-mcp-server
        namespace: cortex-system
    routes:
      - pattern: "security.*"
      - pattern: "scan_.*"
```

## Auto Scale-Down Behavior

The Layer Activator runs a background loop that:
1. Checks each stack every 60 seconds
2. If a stack has been inactive longer than its cooldown period
3. And the stack has `min_replicas: 0`
4. Then scales down all components to 0

## Integration with KEDA

The Layer Activator works alongside KEDA for HTTP-triggered scaling:

```bash
# Check KEDA HTTPScaledObjects
kubectl get httpscaledobjects -A

# Check KEDA ScaledObjects
kubectl get scaledobjects -A
```

## Troubleshooting

### Stack Won't Scale Down

1. Check if `min_replicas > 0` in config
2. Verify cooldown period hasn't elapsed
3. Check Layer Activator logs:
   ```bash
   kubectl logs -n cortex-system deploy/layer-activator
   ```

### Stack Won't Scale Up

1. Check cluster memory availability:
   ```bash
   kubectl top nodes
   kubectl describe nodes | grep -A5 "Allocated resources:"
   ```
2. Scale down other stacks to free memory
3. Check deployment events:
   ```bash
   kubectl describe deploy -n <namespace> <deployment>
   ```

### Layer Activator Not Responding

```bash
# Check pod status
kubectl get pods -n cortex-system -l app=layer-activator

# Check logs
kubectl logs -n cortex-system deploy/layer-activator

# Check Redis connectivity
kubectl exec -n cortex-system deploy/layer-activator -- \
  python -c "import redis; r=redis.from_url('redis://redis.cortex-system.svc.cluster.local:6379'); print(r.ping())"
```

## Related Documentation

- [K3s Cluster Configuration](./k3s-cluster-configuration.md)
- [Tailscale DNS Configuration](./tailscale-dns-configuration.md)
- [Monitoring Exporters](./monitoring-exporters.md)
