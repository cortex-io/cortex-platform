# Worker Pool Management - Quick Start Guide

**Quick Reference for Cortex Worker Pool Operations**

---

## 1-Minute Overview

The Worker Pool Management system provides dynamic Kubernetes worker provisioning using:
- **Proxmox MCP**: VM provisioning and lifecycle
- **Talos MCP**: Kubernetes cluster join/leave
- **4 Pool Types**: Permanent, Burst, Spot, GPU
- **Auto-Scaling**: Trigger-based and metric-based
- **TTL Cleanup**: Automatic termination of temporary workers
- **Auto-Repair**: Self-healing worker infrastructure

---

## Quick Commands

### Provision Burst Workers

```bash
# Provision 3 medium burst workers (4h TTL)
./scripts/provision-burst-workers.sh --count 3 --template medium --ttl 4h

# Provision 5 large burst workers (immediate spike)
./scripts/provision-burst-workers.sh --count 5 --template large --ttl 2h
```

### Provision Spot Workers

```bash
# Provision 2 spot workers for batch jobs
./scripts/provision-spot-workers.sh --count 2 --template medium

# Check spot worker status
kubectl get nodes -l node-pool=spot
```

### Provision GPU Workers

```bash
# Provision 1 GPU worker for ML training
./scripts/provision-gpu-worker.sh --template gpu-nvidia --count 1

# Verify GPU available
kubectl get nodes -l gpu.nvidia.com/class=tesla-t4
```

### Manual Worker Removal

```bash
# Gracefully remove worker (drain + terminate)
./scripts/remove-worker.sh worker-burst-001

# Force remove (emergency only)
./scripts/remove-worker.sh worker-burst-001 --force
```

### Check Worker Pool Status

```bash
# View all worker pools
kubectl get nodes -L node-pool,worker-type,ttl

# Check permanent pool
kubectl get nodes -l node-pool=permanent

# Check burst pool
kubectl get nodes -l node-pool=burst

# Check workers with TTL
kubectl get nodes -l ttl --sort-by=.metadata.labels.ttl
```

---

## Common Workflows

### Scenario 1: Traffic Spike (Black Friday)

**Pre-Scale (30 min before)**:
```bash
# Add 10 large workers for expected spike
./scripts/provision-burst-workers.sh --count 10 --template large --ttl 8h
```

**During Spike**:
```bash
# Monitor pending pods
kubectl get pods --field-selector=status.phase=Pending

# If more capacity needed
./scripts/provision-burst-workers.sh --count 5 --template large --ttl 4h
```

**Post-Spike**:
```bash
# Extend TTL if still needed
./scripts/extend-worker-ttl.sh worker-burst-001 --hours 2

# Or let TTL cleanup handle automatic removal
```

---

### Scenario 2: Batch Job Processing

**Provision Spot Workers**:
```bash
# 5 spot workers for cost-optimized batch processing
./scripts/provision-spot-workers.sh --count 5 --template medium
```

**Submit Job**:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-processing
spec:
  template:
    spec:
      priorityClassName: spot-workload
      tolerations:
        - key: workload-type
          value: spot
          effect: NoSchedule
      nodeSelector:
        node-pool: spot
      containers:
        - name: processor
          image: data-processor:latest
```

**Cleanup**:
```bash
# Spot workers auto-terminate when idle (30min default)
# Or manually remove
./scripts/remove-worker.sh worker-spot-001
```

---

### Scenario 3: ML Training Job

**Provision GPU Worker**:
```bash
# 1 GPU worker with NVIDIA Tesla T4
./scripts/provision-gpu-worker.sh --count 1 --template gpu-nvidia
```

**Submit Training Job**:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: ml-training
spec:
  template:
    spec:
      tolerations:
        - key: nvidia.com/gpu
          value: "true"
          effect: NoSchedule
      nodeSelector:
        gpu.nvidia.com/class: tesla-t4
      containers:
        - name: trainer
          image: pytorch-training:latest
          resources:
            limits:
              nvidia.com/gpu: 1
```

**Verify GPU Usage**:
```bash
# Check GPU worker
kubectl describe node <gpu-worker-name> | grep nvidia.com/gpu

# Check training pod logs
kubectl logs -f <training-pod-name>
```

---

## Worker Templates

| Template | CPU | RAM | Disk | Cost/Hour | Use Case |
|----------|-----|-----|------|-----------|----------|
| **small** | 4 | 8GB | 100GB | $0.12 | Microservices, dev/test |
| **medium** | 8 | 16GB | 200GB | $0.24 | General apps, APIs |
| **large** | 16 | 32GB | 500GB | $0.48 | Databases, data processing |
| **gpu-nvidia** | 8 | 32GB | 500GB + T4 | $1.20 | ML training, inference |

---

## Pool Types

### Permanent Pool
- **Min Size**: 3 workers
- **Max Size**: 10 workers
- **Auto-Scaling**: Yes (CPU/memory-based)
- **TTL**: No (permanent)
- **Use For**: Production apps, databases, core services

### Burst Pool
- **Min Size**: 0 workers
- **Max Size**: 20 workers
- **Auto-Scaling**: Yes (trigger-based)
- **TTL**: 4 hours (default)
- **Use For**: Traffic spikes, temporary workloads

### Spot Pool
- **Min Size**: 0 workers
- **Max Size**: 15 workers
- **Auto-Scaling**: Yes (cost-optimized)
- **TTL**: No (but preemptible)
- **Use For**: Batch jobs, ML training, interruptible work

### GPU Pool
- **Min Size**: 0 workers
- **Max Size**: 5 workers
- **Auto-Scaling**: Manual
- **TTL**: No
- **Use For**: ML/AI workloads, video encoding

---

## Scheduling Cheat Sheet

### Schedule on Permanent Workers (Default)
```yaml
# No special configuration needed
# Will schedule on permanent workers automatically
```

### Schedule on Burst Workers
```yaml
tolerations:
  - key: workload-type
    value: burst
    effect: NoSchedule
nodeSelector:
  node-pool: burst
```

### Schedule on Spot Workers
```yaml
tolerations:
  - key: workload-type
    value: spot
    effect: NoSchedule
  - key: preemptible
    value: "true"
    effect: PreferNoSchedule
nodeSelector:
  node-pool: spot
priorityClassName: spot-workload
```

### Schedule on GPU Workers
```yaml
tolerations:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule
nodeSelector:
  gpu.nvidia.com/class: tesla-t4
resources:
  limits:
    nvidia.com/gpu: 1
```

---

## Troubleshooting

### Worker Not Joining Cluster

```bash
# Check Talos status
talos health --nodes <worker-ip>

# Check kubelet logs
talos logs --nodes <worker-ip> --service kubelet --tail 100

# Verify network
talos get addresses --nodes <worker-ip>

# Regenerate and reapply config
talos generate config prod-k8s https://192.168.1.10:6443
talos apply-config --nodes <worker-ip> --file worker.yaml
```

### Worker Not Terminating (Past TTL)

```bash
# Check TTL cleanup daemon
kubectl logs -n kube-system ttl-cleanup-daemon

# Check if worker has pods
kubectl get pods --all-namespaces --field-selector spec.nodeName=<worker-name>

# Manual drain and delete
kubectl drain <worker-name> --ignore-daemonsets --delete-emptydir-data
kubectl delete node <worker-name>
```

### Auto-Scaling Not Triggering

```bash
# Check pending pods
kubectl get pods --field-selector=status.phase=Pending

# Check cluster metrics
kubectl top nodes

# Check scaling triggers in config
cat /Users/ryandahlberg/Projects/cortex/coordination/resource-manager/worker-pools.json | jq '.worker_pool_definitions.burst.provisioning_triggers'

# Manually trigger provisioning
./scripts/provision-burst-workers.sh --count 2 --template medium
```

### GPU Not Detected

```bash
# Check GPU node labels
kubectl get nodes -l gpu.nvidia.com/class -L gpu.nvidia.com/count

# Check NVIDIA device plugin
kubectl get pods -n kube-system | grep nvidia-device-plugin

# Check GPU availability on node
kubectl describe node <gpu-worker-name> | grep nvidia.com/gpu

# SSH to node (emergency only via Talos)
talos dashboard --nodes <gpu-worker-ip>
```

---

## Monitoring

### Prometheus Metrics

```promql
# Worker count by pool
count(kube_node_labels{label_node_pool="burst"})

# Workers past TTL
count(kube_node_labels{label_ttl!=""} < time())

# Pending pods (trigger for burst provisioning)
kube_pod_status_phase{phase="Pending"} > 5

# Node conditions (health monitoring)
kube_node_status_condition{condition="Ready",status="false"}
```

### Grafana Dashboards

- **Worker Pool Overview**: `/dashboards/worker-pools-overview`
- **Worker Lifecycle**: `/dashboards/worker-lifecycle`
- **Cost Tracking**: `/dashboards/worker-cost-tracking`

---

## Cost Optimization Tips

1. **Use Spot Workers for Batch Jobs**: Save 60-80% vs permanent workers
2. **Set Appropriate TTLs**: Avoid paying for idle burst workers
3. **Right-Size Templates**: Don't over-provision (use small/medium for most workloads)
4. **Schedule Burst Pre-Scaling**: Provision before spike to avoid emergency scaling
5. **Monitor Idle Workers**: Check for workers with low utilization
6. **Use Auto-Scaling**: Let system scale down when not needed

---

## Safety Checklist

Before provisioning workers:
- [ ] Verify Proxmox has capacity (CPU, RAM, storage)
- [ ] Check network capacity and VLANs
- [ ] Confirm budget for additional workers
- [ ] Test provisioning in staging first (for large deployments)
- [ ] Set appropriate TTLs for burst workers
- [ ] Configure monitoring and alerting

Before removing workers:
- [ ] Check for running pods on worker
- [ ] Verify PodDisruptionBudgets are satisfied
- [ ] Drain gracefully (don't force unless emergency)
- [ ] Wait for all pods to evacuate
- [ ] Confirm worker removed from cluster before VM deletion

---

## File Locations

- **Documentation**: `/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/worker-pools.md`
- **Configuration**: `/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/worker-pools.json`
- **Scripts**: `/Users/ryandahlberg/Projects/cortex/scripts/worker-pools/`
- **Provisioning Scripts**: `./scripts/provision-{burst|spot|gpu}-workers.sh`
- **Removal Script**: `./scripts/remove-worker.sh`
- **TTL Extension**: `./scripts/extend-worker-ttl.sh`

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review full documentation: `worker-pools.md`
3. Check Proxmox/Talos MCP logs
4. Escalate to resource-manager master

---

**Last Updated**: 2025-12-09
**Maintained By**: Resource Manager
