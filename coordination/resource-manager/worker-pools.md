# Worker Pool Management

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Owner**: Resource Manager
**Integration**: Proxmox MCP, Talos MCP

---

## Overview

The Worker Pool Management system provides dynamic, elastic worker node provisioning for Kubernetes clusters using Proxmox virtualization and Talos Linux. This system enables burst capacity, auto-scaling, and lifecycle management of temporary and permanent worker nodes.

### Key Capabilities

- **Burst Provisioning**: Rapid worker deployment via Proxmox API for traffic spikes
- **Auto-Join/Leave**: Automatic Talos cluster membership management
- **TTL-Based Cleanup**: Time-to-live enforcement for temporary workers
- **Multi-Tier Sizing**: Predefined templates (small, medium, large, GPU)
- **Intelligent Scheduling**: Node labels, taints, affinity/anti-affinity
- **Spot Workers**: Preemptible workers for cost-optimized batch workloads
- **Health Monitoring**: Continuous health checks with auto-repair
- **Graceful Operations**: Drain and cordon procedures for zero-downtime maintenance

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Resource Manager Master                      │
│  - Worker pool orchestration                                    │
│  - Scaling decisions                                            │
│  - Health monitoring                                            │
└────────────┬───────────────────────────────────┬────────────────┘
             │                                   │
   ┌─────────▼─────────┐             ┌──────────▼──────────┐
   │  Proxmox MCP      │             │  Talos MCP          │
   │  - VM provisioning│             │  - Cluster join     │
   │  - Template clone │             │  - Config apply     │
   │  - Resource mgmt  │             │  - Node drain       │
   └─────────┬─────────┘             └──────────┬──────────┘
             │                                   │
   ┌─────────▼──────────────────────────────────▼──────────┐
   │           Kubernetes Cluster (Talos)                   │
   │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
   │  │ Worker-1 │  │ Worker-2 │  │ Worker-N │ ...        │
   │  │ [Perm]   │  │ [Burst]  │  │ [Spot]   │            │
   │  └──────────┘  └──────────┘  └──────────┘            │
   └────────────────────────────────────────────────────────┘
```

### Worker Lifecycle States

1. **Requested** → Resource manager receives scaling request
2. **Provisioning** → Proxmox creates VM from template
3. **Joining** → Talos applies config and joins cluster
4. **Ready** → Node Ready, accepting workloads
5. **Draining** → Evicting pods for graceful shutdown
6. **Terminating** → VM deletion in progress
7. **Terminated** → Worker removed from cluster and Proxmox

---

## Worker Pool Types

### 1. Permanent Worker Pool

**Purpose**: Baseline capacity for production workloads

**Characteristics**:
- No TTL (lives until manually removed)
- Survives cluster scaling events
- Preferred for stateful workloads
- Reserved resource allocation

**Configuration**:
```yaml
pool_type: permanent
min_size: 3
max_size: 10
auto_scaling: true
scaling_policy:
  metric: cpu_utilization
  target: 70%
  scale_up_threshold: 80%
  scale_down_threshold: 50%
```

**Use Cases**:
- Production databases
- Long-running services
- Stateful applications
- Core platform services

---

### 2. Burst Worker Pool

**Purpose**: Temporary capacity for traffic spikes and batch jobs

**Characteristics**:
- TTL-based lifecycle (default: 4 hours)
- Rapid provisioning (2-3 minutes)
- Auto-termination when idle
- Cost-optimized sizing

**Configuration**:
```yaml
pool_type: burst
ttl_hours: 4
idle_timeout_minutes: 30
provision_trigger:
  pending_pods_count: 5
  pending_duration_seconds: 120
auto_scale_down: true
```

**Use Cases**:
- Traffic spikes (Black Friday, product launches)
- Batch processing jobs
- CI/CD pipeline runners
- Temporary workload scaling

**Provisioning Workflow**:
1. Detect pending pods > threshold
2. Clone VM from burst template (Proxmox)
3. Apply Talos worker config with TTL label
4. Join cluster (2-3 min from request)
5. Schedule pending pods
6. Monitor for idle timeout
7. Drain and terminate on TTL expiry

---

### 3. Spot Worker Pool

**Purpose**: Cost-optimized workers for interruptible workloads

**Characteristics**:
- Lowest priority scheduling
- Can be preempted for permanent workers
- 60-80% cost reduction vs permanent
- Best-effort availability

**Configuration**:
```yaml
pool_type: spot
preemption_policy: terminate_after_grace_period
grace_period_seconds: 300
priority_class: spot-workload
taints:
  - key: workload-type
    value: spot
    effect: NoSchedule
```

**Use Cases**:
- Machine learning training jobs
- Data analytics batch processing
- Video/image rendering
- Log processing and analysis

**Preemption Behavior**:
```
Permanent worker needed:
1. Select spot worker for termination
2. Drain pods with grace period (5 min)
3. Terminate spot worker
4. Provision permanent worker
5. Reschedule evicted pods (if still needed)
```

---

### 4. GPU Worker Pool

**Purpose**: Workers with GPU passthrough for ML/AI workloads

**Characteristics**:
- PCIe GPU passthrough
- NVIDIA/AMD GPU support
- CUDA/ROCm drivers pre-installed
- Higher resource costs

**Configuration**:
```yaml
pool_type: gpu
gpu_type: nvidia-tesla-t4
gpu_count: 1
driver_version: "535.129.03"
cuda_version: "12.2"
node_labels:
  gpu.nvidia.com/class: tesla-t4
  gpu.nvidia.com/count: "1"
```

**Use Cases**:
- ML model training
- Inference serving
- Video encoding/transcoding
- Scientific computing

---

## Worker Templates

### Template Structure (Proxmox)

```
templates/
├── talos-worker-small-v1.8.0
├── talos-worker-medium-v1.8.0
├── talos-worker-large-v1.8.0
├── talos-worker-gpu-nvidia-v1.8.0
└── talos-worker-gpu-amd-v1.8.0
```

### Small Worker Template

**Specs**:
- CPU: 4 vCPU
- RAM: 8 GB
- Disk: 100 GB SSD
- Network: 1 Gbps

**Pod Capacity**: ~100 pods

**Resource Allocation**:
```yaml
allocatable:
  cpu: 3800m      # 200m reserved for system
  memory: 7.5Gi   # 512Mi reserved for system
  ephemeral-storage: 95Gi
```

**Use Cases**:
- Microservices (low resource)
- Sidecars and proxies
- Development workloads
- Testing environments

**Proxmox Clone Command**:
```bash
# Via Proxmox MCP
proxmox_clone_vm \
  --vmid 200 \
  --name "worker-small-burst-001" \
  --target-node "pve-01" \
  --full-clone true \
  --description "Burst worker - TTL 4h"
```

---

### Medium Worker Template

**Specs**:
- CPU: 8 vCPU
- RAM: 16 GB
- Disk: 200 GB SSD
- Network: 1 Gbps

**Pod Capacity**: ~100 pods (higher resource density)

**Resource Allocation**:
```yaml
allocatable:
  cpu: 7800m
  memory: 15Gi
  ephemeral-storage: 190Gi
```

**Use Cases**:
- General purpose applications
- Web servers (moderate traffic)
- API services
- Databases (small to medium)

**Cost vs Performance**: Best balance for production workloads

---

### Large Worker Template

**Specs**:
- CPU: 16 vCPU
- RAM: 32 GB
- Disk: 500 GB SSD
- Network: 10 Gbps

**Pod Capacity**: ~110 pods (resource-intensive workloads)

**Resource Allocation**:
```yaml
allocatable:
  cpu: 15800m
  memory: 30Gi
  ephemeral-storage: 480Gi
```

**Use Cases**:
- Large databases (PostgreSQL, MongoDB)
- Data processing pipelines
- ML inference serving
- High-traffic applications

**Node Taints** (optional):
```yaml
taints:
  - key: workload-size
    value: large
    effect: NoSchedule
```

---

### GPU Worker Template (NVIDIA)

**Specs**:
- CPU: 8 vCPU
- RAM: 32 GB
- Disk: 500 GB SSD
- GPU: NVIDIA Tesla T4 (16GB VRAM)
- PCIe Passthrough: Enabled

**Pre-installed Software**:
- NVIDIA Driver: 535.129.03
- CUDA Toolkit: 12.2
- nvidia-container-toolkit
- NVIDIA Device Plugin (DaemonSet)

**Resource Allocation**:
```yaml
allocatable:
  cpu: 7800m
  memory: 30Gi
  nvidia.com/gpu: 1
```

**Node Labels**:
```yaml
labels:
  gpu.nvidia.com/class: tesla-t4
  gpu.nvidia.com/count: "1"
  gpu.nvidia.com/memory: "16384"  # MB
  gpu.nvidia.com/cuda: "12.2"
```

**Use Cases**:
- ML training (PyTorch, TensorFlow)
- Inference serving
- Video encoding
- Ray/Dask GPU workloads

**Proxmox GPU Configuration**:
```bash
# PCIe passthrough for GPU
qm set <vmid> -hostpci0 01:00.0,pcie=1,x-vga=1
```

---

## Burst Worker Provisioning

### Trigger Conditions

**Automatic Triggers**:
1. **Pending Pods**: ≥5 pods pending for >2 minutes
2. **CPU Pressure**: Cluster CPU utilization >80% for >5 minutes
3. **Memory Pressure**: Cluster memory utilization >85% for >5 minutes
4. **Custom Metrics**: Application-specific autoscaling rules

**Manual Triggers**:
1. API request from resource manager
2. Scheduled scaling (e.g., pre-scaling for known events)
3. Emergency scaling (incident response)

### Provisioning Workflow

**Step 1: Calculate Required Capacity**
```python
# Pseudocode
pending_pods = get_pending_pods()
required_resources = sum(pod.resources for pod in pending_pods)

# Select template that fits
if required_resources.cpu > 8 or required_resources.memory > 16Gi:
    template = "large"
elif required_resources.cpu > 4 or required_resources.memory > 8Gi:
    template = "medium"
else:
    template = "small"

# Calculate worker count
workers_needed = ceil(required_resources / template_capacity)
```

**Step 2: Provision VMs (Proxmox MCP)**
```bash
# For each worker needed
for i in 1..workers_needed:
    # Clone from template
    vmid = get_next_vmid()
    vm_name = "worker-burst-${timestamp}-${i}"

    proxmox_clone_vm \
      --vmid $vmid \
      --name $vm_name \
      --source-template "talos-worker-${template}-v1.8.0" \
      --target-node "pve-01" \
      --full-clone true \
      --start true

    # Tag as burst worker
    proxmox_set_vm_tags --vmid $vmid --tags "burst,ttl-4h"

    # Wait for VM ready
    wait_for_vm_boot --vmid $vmid --timeout 120s
```

**Step 3: Cluster Join (Talos MCP)**
```bash
# Get VM IP
vm_ip=$(proxmox_get_vm_network --vmid $vmid | jq -r '.ip')

# Generate worker config with TTL metadata
talos_generate_worker_config \
  --cluster "prod-k8s" \
  --hostname $vm_name \
  --labels "node-pool=burst,ttl=$(date -u -d '+4 hours' +%s)" \
  --taints "workload-type=burst:NoSchedule" \
  > /tmp/worker-config-${vmid}.yaml

# Apply config to worker
talos_apply_config \
  --nodes $vm_ip \
  --file /tmp/worker-config-${vmid}.yaml \
  --insecure  # First boot

# Wait for node to join
kubectl wait --for=condition=Ready node/$vm_name --timeout=300s

# Label node in Kubernetes
kubectl label node $vm_name \
  node-pool=burst \
  worker-type=temporary \
  ttl=$(date -u -d '+4 hours' +%s) \
  provisioned-at=$(date -u +%s)
```

**Step 4: Monitor and Schedule**
```bash
# Verify scheduling
kubectl get pods --field-selector=status.phase=Pending

# Force schedule pending pods to new workers (if needed)
for pod in $(get_pending_pods); do
    kubectl patch pod $pod -p '{"spec":{"tolerations":[{"key":"workload-type","value":"burst","effect":"NoSchedule"}]}}'
done
```

**Timeline**:
- VM Clone: 30-60 seconds
- VM Boot: 30-60 seconds
- Talos Join: 60-90 seconds
- Node Ready: 120-180 seconds (2-3 minutes total)

---

## Automatic Cluster Join/Leave

### Join Procedure (Talos)

**Prerequisites**:
1. VM provisioned and booted
2. Network connectivity to cluster
3. Talos machine config available

**Join Steps**:
```bash
#!/bin/bash
# join-worker.sh - Automated worker join script

CLUSTER_NAME="prod-k8s"
WORKER_IP="$1"
WORKER_NAME="$2"
WORKER_TYPE="${3:-permanent}"  # permanent, burst, spot

# 1. Generate worker configuration
echo "Generating worker config for $WORKER_NAME..."
talos_generate_worker_config \
  --cluster $CLUSTER_NAME \
  --hostname $WORKER_NAME \
  --output /tmp/worker-${WORKER_NAME}.yaml

# 2. Apply labels based on worker type
if [ "$WORKER_TYPE" = "burst" ]; then
    TTL=$(date -u -d '+4 hours' +%s)
    cat >> /tmp/worker-${WORKER_NAME}.yaml <<EOF
machine:
  kubelet:
    nodeLabels:
      node-pool: burst
      worker-type: temporary
      ttl: "$TTL"
    registerWithTaints:
      - key: workload-type
        value: burst
        effect: NoSchedule
EOF
elif [ "$WORKER_TYPE" = "spot" ]; then
    cat >> /tmp/worker-${WORKER_NAME}.yaml <<EOF
machine:
  kubelet:
    nodeLabels:
      node-pool: spot
      worker-type: preemptible
    registerWithTaints:
      - key: workload-type
        value: spot
        effect: NoSchedule
EOF
fi

# 3. Apply config to worker
echo "Applying config to $WORKER_IP..."
talos_apply_config \
  --nodes $WORKER_IP \
  --file /tmp/worker-${WORKER_NAME}.yaml \
  --insecure

# 4. Wait for node to appear in cluster
echo "Waiting for node to join..."
timeout 300 kubectl wait --for=condition=Ready node/$WORKER_NAME

# 5. Verify join success
if kubectl get node $WORKER_NAME &>/dev/null; then
    echo "SUCCESS: Worker $WORKER_NAME joined cluster"

    # Record join event
    cat > /tmp/join-event-${WORKER_NAME}.json <<EOF
{
  "event_type": "worker_joined",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "worker_name": "$WORKER_NAME",
  "worker_ip": "$WORKER_IP",
  "worker_type": "$WORKER_TYPE",
  "cluster": "$CLUSTER_NAME"
}
EOF
else
    echo "ERROR: Worker $WORKER_NAME failed to join"
    exit 1
fi
```

### Leave Procedure (Graceful)

**Drain Before Termination**:
```bash
#!/bin/bash
# leave-worker.sh - Graceful worker removal

WORKER_NAME="$1"
GRACE_PERIOD="${2:-300}"  # 5 minutes default

echo "Initiating graceful leave for $WORKER_NAME..."

# 1. Cordon node (prevent new pods)
kubectl cordon $WORKER_NAME

# 2. Drain node (evict existing pods)
kubectl drain $WORKER_NAME \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=$GRACE_PERIOD \
  --timeout=600s

# 3. Wait for all pods to evacuate
while [ $(kubectl get pods --all-namespaces --field-selector spec.nodeName=$WORKER_NAME --no-headers | wc -l) -gt 0 ]; do
    echo "Waiting for pods to evacuate..."
    sleep 10
done

# 4. Remove node from Kubernetes
kubectl delete node $WORKER_NAME

# 5. Shutdown Talos node
WORKER_IP=$(talos_get_node_ip $WORKER_NAME)
talos_shutdown --nodes $WORKER_IP --graceful

# 6. Delete VM from Proxmox
VMID=$(proxmox_get_vmid_by_name $WORKER_NAME)
proxmox_delete_vm --vmid $VMID

echo "Worker $WORKER_NAME successfully removed"
```

**Zero-Downtime Leave**:
- Pods rescheduled before node termination
- StatefulSets maintain quorum
- LoadBalancer updates endpoints
- PersistentVolumes detached gracefully

---

## TTL-Based Cleanup

### TTL Enforcement

**TTL Label**:
```yaml
metadata:
  labels:
    ttl: "1733760000"  # Unix timestamp
    provisioned-at: "1733745600"
    ttl-hours: "4"
```

**Cleanup Daemon** (runs every 5 minutes):
```python
#!/usr/bin/env python3
# ttl-cleanup-daemon.py

import time
import subprocess
import json
from datetime import datetime

def get_workers_with_ttl():
    """Get all workers with TTL labels"""
    result = subprocess.run(
        ["kubectl", "get", "nodes", "-l", "ttl", "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)['items']

def cleanup_expired_workers():
    """Remove workers past their TTL"""
    workers = get_workers_with_ttl()
    current_time = int(time.time())

    for worker in workers:
        worker_name = worker['metadata']['name']
        ttl = int(worker['metadata']['labels'].get('ttl', 0))

        if current_time > ttl:
            print(f"Worker {worker_name} expired (TTL: {ttl}, Now: {current_time})")

            # Check if worker is idle
            pod_count = get_pod_count(worker_name)

            if pod_count == 0:
                print(f"Worker {worker_name} is idle, removing immediately")
                remove_worker(worker_name)
            else:
                print(f"Worker {worker_name} has {pod_count} pods, draining...")
                drain_and_remove_worker(worker_name)

def get_pod_count(node_name):
    """Get number of non-daemonset pods on node"""
    result = subprocess.run(
        ["kubectl", "get", "pods", "--all-namespaces",
         "--field-selector", f"spec.nodeName={node_name}",
         "-o", "json"],
        capture_output=True, text=True
    )
    pods = json.loads(result.stdout)['items']

    # Filter out daemonset pods
    non_daemonset_pods = [
        p for p in pods
        if 'ownerReferences' in p['metadata']
        and not any(ref['kind'] == 'DaemonSet'
                   for ref in p['metadata']['ownerReferences'])
    ]

    return len(non_daemonset_pods)

def remove_worker(worker_name):
    """Remove worker (already idle)"""
    subprocess.run(["./leave-worker.sh", worker_name])

def drain_and_remove_worker(worker_name):
    """Drain then remove worker"""
    subprocess.run(["./leave-worker.sh", worker_name, "300"])

if __name__ == "__main__":
    while True:
        try:
            cleanup_expired_workers()
        except Exception as e:
            print(f"Error in cleanup: {e}")

        # Run every 5 minutes
        time.sleep(300)
```

### TTL Extension

**Extend TTL if worker is still needed**:
```bash
# Extend TTL by 2 hours
WORKER_NAME="worker-burst-001"
CURRENT_TTL=$(kubectl get node $WORKER_NAME -o jsonpath='{.metadata.labels.ttl}')
NEW_TTL=$((CURRENT_TTL + 7200))  # +2 hours

kubectl label node $WORKER_NAME ttl=$NEW_TTL --overwrite

echo "Extended TTL for $WORKER_NAME to $(date -d @$NEW_TTL)"
```

---

## Node Labels and Taints Strategy

### Standard Labels

**System Labels** (automatic):
```yaml
kubernetes.io/arch: amd64
kubernetes.io/os: linux
kubernetes.io/hostname: worker-01
node.kubernetes.io/instance-type: medium-worker
topology.kubernetes.io/zone: dc1-rack-a
```

**Custom Labels** (applied at join):
```yaml
# Worker pool membership
node-pool: burst | permanent | spot | gpu

# Worker lifecycle
worker-type: permanent | temporary | preemptible
provisioned-at: "1733745600"
ttl: "1733760000"  # For burst/spot workers

# Resource capabilities
workload-size: small | medium | large
storage-tier: ssd | nvme
network-speed: 1g | 10g

# GPU workers
gpu.nvidia.com/class: tesla-t4 | a100
gpu.nvidia.com/count: "1"
gpu.nvidia.com/memory: "16384"
```

### Taints Strategy

**Purpose**: Control pod scheduling via tolerations

**Burst Workers**:
```yaml
taints:
  - key: workload-type
    value: burst
    effect: NoSchedule
```

**Spot Workers**:
```yaml
taints:
  - key: workload-type
    value: spot
    effect: NoSchedule
  - key: preemptible
    value: "true"
    effect: PreferNoSchedule
```

**GPU Workers**:
```yaml
taints:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule
```

**Large Workers** (optional):
```yaml
taints:
  - key: workload-size
    value: large
    effect: NoSchedule
```

### Pod Tolerations

**Schedule on Burst Workers**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: batch-job
spec:
  tolerations:
    - key: workload-type
      operator: Equal
      value: burst
      effect: NoSchedule
  nodeSelector:
    node-pool: burst
```

**Schedule on Spot Workers**:
```yaml
tolerations:
  - key: workload-type
    operator: Equal
    value: spot
    effect: NoSchedule
  - key: preemptible
    operator: Equal
    value: "true"
    effect: PreferNoSchedule
nodeSelector:
  node-pool: spot
```

**Schedule on GPU Workers**:
```yaml
tolerations:
  - key: nvidia.com/gpu
    operator: Equal
    value: "true"
    effect: NoSchedule
resources:
  limits:
    nvidia.com/gpu: 1
nodeSelector:
  gpu.nvidia.com/class: tesla-t4
```

---

## Affinity and Anti-Affinity Rules

### Pod Affinity

**Co-locate Related Services**:
```yaml
# Place cache pods near application pods
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
            - key: app
              operator: In
              values:
                - web-server
        topologyKey: kubernetes.io/hostname
```

### Pod Anti-Affinity

**Spread Replicas Across Nodes**:
```yaml
# Ensure high availability - spread replicas
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app
                operator: In
                values:
                  - database
          topologyKey: kubernetes.io/hostname
```

**Spread Across Zones**:
```yaml
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: critical-service
        topologyKey: topology.kubernetes.io/zone
```

### Node Affinity

**Prefer Permanent Workers**:
```yaml
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
            - key: worker-type
              operator: In
              values:
                - permanent
```

**Require SSD Storage**:
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: storage-tier
              operator: In
              values:
                - ssd
                - nvme
```

---

## Worker Health Monitoring

### Health Checks

**Node Conditions** (monitored every 10s):
```yaml
conditions:
  - type: Ready
    status: "True"
  - type: MemoryPressure
    status: "False"
  - type: DiskPressure
    status: "False"
  - type: PIDPressure
    status: "False"
  - type: NetworkUnavailable
    status: "False"
```

**Talos Health Check**:
```bash
# Via Talos MCP
talos_health --nodes <worker-ip>

# Output
{
  "node": "worker-01",
  "status": "healthy",
  "services": {
    "kubelet": "running",
    "containerd": "running",
    "etcd": "not applicable"
  }
}
```

### Health Monitoring Daemon

```python
#!/usr/bin/env python3
# health-monitor.py

import subprocess
import json
import time
from datetime import datetime

def get_all_workers():
    """Get all worker nodes"""
    result = subprocess.run(
        ["kubectl", "get", "nodes", "-l", "!node-role.kubernetes.io/control-plane",
         "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)['items']

def check_node_health(node):
    """Check if node is healthy"""
    node_name = node['metadata']['name']

    # Check conditions
    conditions = node['status']['conditions']
    ready_condition = next((c for c in conditions if c['type'] == 'Ready'), None)

    if not ready_condition or ready_condition['status'] != 'True':
        return {
            'healthy': False,
            'reason': 'NotReady',
            'message': ready_condition.get('message', 'Unknown')
        }

    # Check for pressure conditions
    pressure_conditions = ['MemoryPressure', 'DiskPressure', 'PIDPressure']
    for pressure in pressure_conditions:
        condition = next((c for c in conditions if c['type'] == pressure), None)
        if condition and condition['status'] == 'True':
            return {
                'healthy': False,
                'reason': pressure,
                'message': condition.get('message', 'Unknown')
            }

    return {'healthy': True}

def auto_repair_node(node_name, issue):
    """Attempt automatic repair"""
    print(f"Auto-repair triggered for {node_name}: {issue['reason']}")

    if issue['reason'] == 'NotReady':
        # Restart kubelet
        print(f"Restarting kubelet on {node_name}...")
        worker_ip = get_node_ip(node_name)
        subprocess.run([
            "talos", "service", "kubelet", "restart",
            "--nodes", worker_ip
        ])

        # Wait and recheck
        time.sleep(60)
        return check_node_status(node_name)

    elif issue['reason'] == 'DiskPressure':
        # Clean up disk space
        print(f"Cleaning disk on {node_name}...")
        worker_ip = get_node_ip(node_name)
        subprocess.run([
            "kubectl", "exec", "-it",
            f"node-cleanup-{node_name}",
            "--", "sh", "-c",
            "crictl rmi --prune && docker system prune -af"
        ])
        return True

    return False

def monitor_workers():
    """Main monitoring loop"""
    while True:
        try:
            workers = get_all_workers()

            for worker in workers:
                worker_name = worker['metadata']['name']
                health = check_node_health(worker)

                if not health['healthy']:
                    print(f"UNHEALTHY: {worker_name} - {health['reason']}")

                    # Attempt auto-repair
                    if auto_repair_node(worker_name, health):
                        print(f"Auto-repair successful for {worker_name}")
                    else:
                        print(f"Auto-repair failed for {worker_name}, escalating...")
                        escalate_to_resource_manager(worker_name, health)

        except Exception as e:
            print(f"Monitoring error: {e}")

        # Check every 30 seconds
        time.sleep(30)

if __name__ == "__main__":
    monitor_workers()
```

---

## Graceful Drain and Cordon

### Cordon Node

**Prevent new pod scheduling**:
```bash
kubectl cordon worker-burst-001

# Node marked as unschedulable
node/worker-burst-001 cordoned
```

**Use Cases**:
- Before maintenance
- Before node upgrade
- Before termination

### Drain Node

**Evict all pods gracefully**:
```bash
kubectl drain worker-burst-001 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=300 \
  --timeout=600s \
  --force=false

# Output
node/worker-burst-001 cordoned
evicting pod default/nginx-5d4c8f7f-abc12
evicting pod default/redis-6b9f4c8d-def34
pod/nginx-5d4c8f7f-abc12 evicted
pod/redis-6b9f4c8d-def34 evicted
node/worker-burst-001 drained
```

**Drain Options**:
- `--ignore-daemonsets`: Don't evict DaemonSet pods (they'll be recreated)
- `--delete-emptydir-data`: Allow deleting pods with emptyDir volumes
- `--grace-period=300`: Give pods 5 minutes to terminate gracefully
- `--timeout=600s`: Fail if drain doesn't complete in 10 minutes
- `--force`: Force delete pods if needed (use with caution)

### Drain with PodDisruptionBudget

**Respect application availability requirements**:

```yaml
# PodDisruptionBudget example
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: web-app
```

**Drain behavior**:
- Waits for PDB to allow eviction
- Ensures `minAvailable` replicas stay running
- Blocks drain if eviction violates PDB

### Uncordon Node

**Re-enable scheduling after maintenance**:
```bash
kubectl uncordon worker-burst-001

# Node marked as schedulable
node/worker-burst-001 uncordoned
```

---

## Auto-Repair Mechanisms

### Auto-Repair Triggers

1. **Node NotReady** (>5 minutes)
2. **Kubelet Crash Loop**
3. **Disk Pressure**
4. **Memory Pressure**
5. **Network Unavailable**
6. **Container Runtime Failures**

### Repair Actions

**Level 1: Service Restart**
```bash
# Restart kubelet
talos service kubelet restart --nodes <worker-ip>

# Restart containerd
talos service containerd restart --nodes <worker-ip>
```

**Level 2: Cleanup**
```bash
# Clean up disk space
talos --nodes <worker-ip> cleanup

# Prune unused images
crictl rmi --prune
```

**Level 3: Node Reboot**
```bash
# Graceful reboot
talos reboot --nodes <worker-ip> --graceful
```

**Level 4: Node Replacement**
```bash
# Drain and replace
kubectl drain <worker-name>
kubectl delete node <worker-name>
proxmox_delete_vm --vmid <vmid>

# Provision replacement
./provision-burst-worker.sh --template medium --count 1
```

### Repair Decision Matrix

| Issue | Duration | Action | Auto-Repair |
|-------|----------|--------|-------------|
| NotReady | <5 min | Monitor | No |
| NotReady | 5-10 min | Restart kubelet | Yes |
| NotReady | >10 min | Reboot node | Yes |
| NotReady | >20 min | Replace node | No (escalate) |
| DiskPressure | Any | Cleanup + Prune | Yes |
| MemoryPressure | <10 min | Monitor | No |
| MemoryPressure | >10 min | Drain + Reboot | Yes |
| Kubelet crash | 3 restarts | Reboot node | Yes |
| Containerd crash | 3 restarts | Replace node | No (escalate) |

---

## Integration with Proxmox MCP

### VM Provisioning

**Create Worker from Template**:
```bash
# Via Proxmox MCP
proxmox_clone_vm \
  --source-vmid 9000 \
  --vmid 200 \
  --name "worker-burst-001" \
  --target-node "pve-01" \
  --full-clone true \
  --description "Burst worker - TTL 4h" \
  --start true

# Response
{
  "vmid": 200,
  "name": "worker-burst-001",
  "status": "running",
  "upid": "UPID:pve-01:00012345:001A2B3C:clone:200:root@pam:"
}
```

**Configure VM Resources**:
```bash
# Set CPU and memory
proxmox_configure_vm \
  --vmid 200 \
  --cores 8 \
  --memory 16384 \
  --balloon 8192

# Set network
proxmox_set_vm_network \
  --vmid 200 \
  --bridge "vmbr1" \
  --vlan-tag 20

# Add tags
proxmox_set_vm_tags \
  --vmid 200 \
  --tags "k8s-worker,burst,medium"
```

### VM Lifecycle Management

**Start/Stop/Restart**:
```bash
# Start worker
proxmox_start_vm --vmid 200

# Stop worker (graceful)
proxmox_stop_vm --vmid 200 --timeout 300

# Force stop
proxmox_stop_vm --vmid 200 --force true

# Restart
proxmox_restart_vm --vmid 200
```

**Delete Worker**:
```bash
# Delete VM (after drain)
proxmox_delete_vm --vmid 200 --purge true

# Purge removes all disks and configs
```

### Monitoring via Proxmox

**Get VM Status**:
```bash
proxmox_get_vm_status --vmid 200

# Response
{
  "vmid": 200,
  "status": "running",
  "uptime": 3600,
  "cpu": 0.35,
  "mem": 8589934592,
  "maxmem": 17179869184,
  "disk": 0,
  "maxdisk": 214748364800,
  "netin": 1024000,
  "netout": 2048000
}
```

---

## Integration with Talos MCP

### Worker Configuration

**Generate Worker Config**:
```bash
talos_generate_worker_config \
  --cluster "prod-k8s" \
  --hostname "worker-burst-001" \
  --labels "node-pool=burst" \
  --output worker-config.yaml
```

**Apply Configuration**:
```bash
talos_apply_config \
  --nodes "192.168.1.50" \
  --file worker-config.yaml \
  --insecure  # First boot only
```

### Cluster Operations

**Join Cluster**:
```bash
# Config auto-joins when applied
# Verify join
talos_health --nodes "192.168.1.50"

# Check cluster membership
kubectl get nodes
```

**Leave Cluster**:
```bash
# Reset node (removes from cluster)
talos_reset --nodes "192.168.1.50" --graceful

# Or just shutdown
talos_shutdown --nodes "192.168.1.50"
```

### Maintenance Operations

**Upgrade Worker**:
```bash
talos_upgrade \
  --nodes "192.168.1.50" \
  --image "ghcr.io/siderolabs/installer:v1.8.0"
```

**Reboot Worker**:
```bash
talos_reboot --nodes "192.168.1.50" --graceful
```

---

## Production Best Practices

### 1. Pre-Scaling for Known Events

**Schedule burst workers before traffic spike**:
```bash
# 30 minutes before Black Friday
cron: 0 23 * 11 4  # Nov 24, 11:00 PM
./provision-burst-workers.sh --template large --count 10
```

### 2. Gradual Scale-Down

**Don't terminate all burst workers at once**:
```python
# Scale down 20% every 30 minutes
burst_workers = get_burst_workers()
workers_to_remove = int(len(burst_workers) * 0.2)

for i in range(5):  # 5 batches
    remove_workers(burst_workers[i*workers_to_remove:(i+1)*workers_to_remove])
    time.sleep(1800)  # Wait 30 minutes
```

### 3. Resource Reservation

**Reserve capacity for permanent workloads**:
```yaml
# Priority class for permanent workloads
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: permanent-workload
value: 1000
globalDefault: false
description: "Priority for permanent workload pods"
```

### 4. Cost Optimization

**Spot workers for batch jobs**:
```bash
# Run ML training on spot workers
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ml-training
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
        - name: trainer
          image: ml-training:latest
          resources:
            requests:
              cpu: 4
              memory: 8Gi
EOF
```

### 5. Monitoring and Alerting

**Alert on worker pool issues**:
```yaml
# Prometheus alert
- alert: BurstWorkerStuckProvisioning
  expr: |
    (time() - worker_provision_start_time{pool="burst"}) > 600
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Burst worker stuck provisioning for >10 minutes"
```

---

## Troubleshooting

### Worker Won't Join Cluster

**Symptoms**: VM boots but node doesn't appear in `kubectl get nodes`

**Diagnosis**:
```bash
# Check Talos status
talos_health --nodes <worker-ip>

# Check kubelet logs
talos_logs --nodes <worker-ip> --service kubelet --tail 100

# Check network
talos_get_addresses --nodes <worker-ip>
```

**Common Causes**:
- Network misconfiguration
- Firewall blocking port 6443
- Wrong cluster endpoint
- Certificate issues

**Resolution**:
```bash
# Regenerate config and reapply
talos_generate_worker_config --cluster prod-k8s --output new-config.yaml
talos_apply_config --nodes <worker-ip> --file new-config.yaml
```

---

### Burst Worker Not Terminating

**Symptoms**: Worker past TTL but still running

**Diagnosis**:
```bash
# Check TTL cleanup daemon
kubectl logs -n kube-system ttl-cleanup-daemon

# Check if worker has pods
kubectl get pods --all-namespaces --field-selector spec.nodeName=<worker-name>
```

**Resolution**:
```bash
# Manual drain and delete
./leave-worker.sh <worker-name>
```

---

## References

- **Proxmox API**: https://pve.proxmox.com/pve-docs/api-viewer/
- **Talos Linux**: https://www.talos.dev/
- **Kubernetes Node Management**: https://kubernetes.io/docs/concepts/architecture/nodes/
- **Pod Disruption Budgets**: https://kubernetes.io/docs/concepts/workloads/pods/disruptions/
- **Node Affinity**: https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/

---

**Maintained by**: Resource Manager
**Last Review**: 2025-12-09
**Next Review**: 2025-03-09
