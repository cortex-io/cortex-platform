# Talos Contractor Implementation Patterns

Comprehensive knowledge base for Talos Linux Kubernetes cluster management in the Cortex ecosystem.

## Table of Contents

1. [Cluster Architecture Patterns](#cluster-architecture-patterns)
2. [Control Plane Configurations](#control-plane-configurations)
3. [Worker Node Sizing and Scaling](#worker-node-sizing-and-scaling)
4. [Storage Options](#storage-options)
5. [Networking](#networking)
6. [Security Configurations](#security-configurations)
7. [Upgrade Strategies](#upgrade-strategies)
8. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
9. [GitOps Integration](#gitops-integration)
10. [Monitoring Stack Deployment](#monitoring-stack-deployment)
11. [Common Helm Charts](#common-helm-charts)
12. [Troubleshooting Guides](#troubleshooting-guides)

---

## Cluster Architecture Patterns

### Single Node Development Cluster

**Overview**: Minimal cluster for development and testing. Single node runs both control plane and workloads.

**Topology**:
```yaml
cluster_name: dev-cluster
node_count: 1
architecture: x86_64

nodes:
  - hostname: dev-node-01
    role: controlplane
    allow_scheduling: true
    resources:
      cpu_cores: 4
      memory_gb: 8
      storage_gb: 100
```

**Use Cases**:
- Local development environments
- CI/CD ephemeral test clusters
- Learning Kubernetes and Talos
- Feature testing before production
- Cost-effective experimentation

**Configuration Example**:
```bash
# Generate single-node cluster config
talosctl gen config dev-cluster https://192.168.1.10:6443 \
  --output-dir ./cluster-configs \
  --with-docs=false \
  --with-examples=false

# Modify controlplane.yaml to allow workload scheduling
# Remove the taint: node-role.kubernetes.io/control-plane:NoSchedule

# Apply configuration
talosctl apply-config --insecure \
  --nodes 192.168.1.10 \
  --file controlplane.yaml

# Bootstrap the cluster
talosctl bootstrap --nodes 192.168.1.10
```

**Considerations**:
- No high availability - single point of failure
- etcd runs on single node (no quorum)
- Suitable only for non-production workloads
- Fast bootstrap time (2-3 minutes)
- Minimum resource requirements
- Easy to tear down and recreate

**Resource Limits**:
- Max pods: ~110
- Max services: ~100
- Suitable for: 5-10 microservices
- Storage: Local storage only

---

### High Availability Production Cluster

**Overview**: Enterprise-grade cluster with redundant control plane and dedicated worker nodes.

**Topology**:
```yaml
cluster_name: prod-cluster
architecture: x86_64

control_plane:
  count: 3
  resources:
    cpu_cores: 4
    memory_gb: 16
    storage_gb: 200
  nodes:
    - hostname: prod-cp-01
      ip: 192.168.1.10
      zone: zone-a
    - hostname: prod-cp-02
      ip: 192.168.1.11
      zone: zone-b
    - hostname: prod-cp-03
      ip: 192.168.1.12
      zone: zone-c

workers:
  count: 6
  resources:
    cpu_cores: 8
    memory_gb: 32
    storage_gb: 500
  nodes:
    - hostname: prod-worker-01
      ip: 192.168.1.20
      zone: zone-a
    - hostname: prod-worker-02
      ip: 192.168.1.21
      zone: zone-a
    - hostname: prod-worker-03
      ip: 192.168.1.22
      zone: zone-b
    - hostname: prod-worker-04
      ip: 192.168.1.23
      zone: zone-b
    - hostname: prod-worker-05
      ip: 192.168.1.24
      zone: zone-c
    - hostname: prod-worker-06
      ip: 192.168.1.25
      zone: zone-c

load_balancer:
  vip: 192.168.1.100
  backend_nodes:
    - 192.168.1.10:6443
    - 192.168.1.11:6443
    - 192.168.1.12:6443
```

**Use Cases**:
- Production workloads requiring 99.9%+ uptime
- Multi-tenant SaaS platforms
- Business-critical applications
- Compliance-regulated workloads
- 24/7 service availability

**Configuration Steps**:

1. **Generate base configs with VIP**:
```bash
talosctl gen config prod-cluster https://192.168.1.100:6443 \
  --output-dir ./prod-configs \
  --with-secrets secrets.yaml
```

2. **Customize controlplane config**:
```yaml
# controlplane.yaml additions
machine:
  network:
    interfaces:
      - interface: eth0
        dhcp: false
        addresses:
          - 192.168.1.10/24
        routes:
          - network: 0.0.0.0/0
            gateway: 192.168.1.1
        vip:
          ip: 192.168.1.100

cluster:
  etcd:
    extraArgs:
      election-timeout: "5000"
      heartbeat-interval: "500"
      quota-backend-bytes: "8589934592"  # 8GB
```

3. **Apply to control plane nodes**:
```bash
# First control plane (init node)
talosctl apply-config --insecure \
  --nodes 192.168.1.10 \
  --file controlplane-01.yaml

# Wait for node to be configured
sleep 30

# Bootstrap etcd on init node
talosctl bootstrap --nodes 192.168.1.10

# Apply to additional control planes
talosctl apply-config --insecure \
  --nodes 192.168.1.11 \
  --file controlplane-02.yaml

talosctl apply-config --insecure \
  --nodes 192.168.1.12 \
  --file controlplane-03.yaml

# Wait for etcd cluster to form
sleep 60
```

4. **Apply to worker nodes**:
```bash
for ip in 192.168.1.{20..25}; do
  talosctl apply-config --insecure \
    --nodes $ip \
    --file worker.yaml
  sleep 10
done
```

**Considerations**:
- etcd quorum requires odd number of control planes (3, 5, 7)
- Geographic distribution across availability zones
- Load balancer required for API server HA
- Higher resource costs (~18 nodes minimum for full HA)
- Control plane nodes should not run workloads (tainted)
- Minimum 3 workers for pod replica distribution

**Capacity Planning**:
- Max pods: ~660 (110 per worker × 6 workers)
- Max services: ~5000
- Suitable for: 50+ microservices
- Concurrent deployments: 10+
- Database replicas: 3-5

**Network Requirements**:
- Control plane nodes: 2Gbps bandwidth minimum
- Worker nodes: 10Gbps recommended
- Inter-zone latency: <10ms preferred
- Load balancer health checks every 5s

---

### Edge Computing Cluster

**Overview**: Lightweight cluster optimized for edge locations with resource constraints.

**Topology**:
```yaml
cluster_name: edge-cluster
architecture: arm64  # or x86_64

control_plane:
  count: 1  # or 3 for edge HA
  resources:
    cpu_cores: 2
    memory_gb: 4
    storage_gb: 50
  hardware: "Raspberry Pi 4, NVIDIA Jetson, or low-power x86"

workers:
  count: 2
  resources:
    cpu_cores: 2
    memory_gb: 4
    storage_gb: 50

total_cluster_resources:
  cpu_cores: 6
  memory_gb: 12
  storage_gb: 150
```

**Use Cases**:
- IoT edge processing
- Remote site deployments
- Retail point-of-sale systems
- Manufacturing floor edge computing
- Remote monitoring stations
- Network edge caching
- 5G edge applications

**Edge-Optimized Configuration**:
```yaml
# Edge machine config optimizations
machine:
  kubelet:
    extraArgs:
      max-pods: "50"  # Reduced from default 110
      system-reserved: "cpu=100m,memory=256Mi"
      kube-reserved: "cpu=100m,memory=256Mi"
      eviction-hard: "memory.available<100Mi,nodefs.available<5%"
      feature-gates: "LocalStorageCapacityIsolation=true"

  install:
    image: ghcr.io/siderolabs/installer:v1.8.0
    disk: /dev/mmcblk0  # SD card or eMMC

  network:
    hostname: edge-node-01
    interfaces:
      - interface: eth0
        dhcp: true
        mtu: 1500

cluster:
  network:
    cni:
      name: flannel  # Lightweight CNI for edge
    podSubnets:
      - 10.244.0.0/16
    serviceSubnets:
      - 10.96.0.0/16

  controllerManager:
    extraArgs:
      node-monitor-grace-period: "60s"  # Tolerate flaky edge networks
      pod-eviction-timeout: "2m"
```

**Edge Deployment Pattern**:
```bash
# 1. Generate edge config with reduced features
talosctl gen config edge-cluster https://edge-site-01:6443 \
  --kubernetes-version 1.31.0 \
  --output-dir ./edge-configs

# 2. Customize for edge constraints
# Edit config to reduce resource reservations
# Enable edge-optimized features

# 3. Deploy to edge nodes (possibly over slow WAN)
talosctl apply-config --insecure \
  --nodes edge-site-01 \
  --file edge-controlplane.yaml \
  --timeout 10m  # Longer timeout for slow links

# 4. Bootstrap with patience
talosctl bootstrap --nodes edge-site-01

# 5. Install minimal workload set
# - Metrics server (lightweight monitoring)
# - Edge application pods
# - Local caching layer
```

**Edge-Specific Considerations**:
- Intermittent internet connectivity
- Limited bandwidth to central management
- Power consumption constraints
- Fanless/passive cooling requirements
- SD card storage (limited write endurance)
- ARM architecture compatibility
- Automated recovery without site visit
- Local data processing and aggregation
- Sync with central cluster when connected

**Edge Hardware Examples**:
- **Raspberry Pi 4** (8GB): 4-core ARM, $75, 5W power
- **NVIDIA Jetson Nano**: 4-core ARM, GPU, $99, 10W power
- **Intel NUC**: 4-core x86, $300, 15W power
- **ASUS Tinker Board**: 6-core ARM, $125, 10W power

---

### Hybrid Control Plane Cluster

**Overview**: Large-scale cluster with dedicated control plane and scalable worker pools.

**Topology**:
```yaml
cluster_name: hybrid-cluster
architecture: x86_64

control_plane:
  count: 5  # Large cluster needs more etcd capacity
  dedicated: true  # No workload scheduling
  resources:
    cpu_cores: 8
    memory_gb: 32
    storage_gb: 500
    storage_type: nvme  # Fast SSD for etcd

worker_pools:
  general_purpose:
    count: 20
    resources:
      cpu_cores: 16
      memory_gb: 64
      storage_gb: 1000
    labels:
      workload-type: general
      node-pool: general

  high_memory:
    count: 5
    resources:
      cpu_cores: 16
      memory_gb: 128
      storage_gb: 500
    labels:
      workload-type: memory-intensive
      node-pool: high-memory
    taints:
      - key: high-memory
        value: "true"
        effect: NoSchedule

  gpu:
    count: 3
    resources:
      cpu_cores: 32
      memory_gb: 256
      storage_gb: 2000
      gpu: nvidia-a100
    labels:
      workload-type: gpu
      node-pool: gpu
    taints:
      - key: nvidia.com/gpu
        value: "true"
        effect: NoSchedule

total_nodes: 33
total_capacity:
  cpu_cores: 872
  memory_gb: 2048
  storage_gb: 26500
```

**Use Cases**:
- Large enterprises (50+ nodes)
- Multi-tenant SaaS platforms
- ML/AI training clusters
- Big data processing
- High-traffic web applications
- Microservices at scale (100+ services)

**Advanced Configuration**:
```yaml
# Control plane configuration for scale
cluster:
  apiServer:
    extraArgs:
      max-requests-inflight: "800"
      max-mutating-requests-inflight: "400"
      default-watch-cache-size: "1000"
      watch-cache-sizes: "persistentvolumeclaims#1000,persistentvolumes#1000"

  controllerManager:
    extraArgs:
      kube-api-qps: "200"
      kube-api-burst: "400"
      node-monitor-period: "5s"

  etcd:
    advertisedSubnets:
      - 192.168.1.0/24
    extraArgs:
      quota-backend-bytes: "17179869184"  # 16GB
      snapshot-count: "10000"
      auto-compaction-retention: "5m"
      auto-compaction-mode: "periodic"
```

**Worker Pool Management**:
```bash
# Create node pool configs
for pool in general high-memory gpu; do
  cat > worker-${pool}.yaml <<EOF
machine:
  kubelet:
    nodeLabels:
      node-pool: ${pool}
      workload-type: ${pool}
EOF
done

# Apply appropriate config to each pool
talosctl apply-config --nodes 192.168.1.20-39 --file worker-general.yaml
talosctl apply-config --nodes 192.168.1.40-44 --file worker-high-memory.yaml
talosctl apply-config --nodes 192.168.1.45-47 --file worker-gpu.yaml
```

**Scaling Operations**:
```bash
# Add nodes to general purpose pool
# 1. Provision VMs via infrastructure-contractor
# 2. Apply worker config
for ip in 192.168.1.{48..50}; do
  talosctl apply-config --insecure \
    --nodes $ip \
    --file worker-general.yaml
done

# 3. Verify nodes joined
kubectl get nodes --selector='node-pool=general'
```

---

## Control Plane Configurations

### Standard Control Plane Setup

**Configuration Pattern**:
```yaml
machine:
  type: controlplane

  kubelet:
    image: ghcr.io/siderolabs/kubelet:v1.31.0
    extraArgs:
      rotate-server-certificates: "true"
      feature-gates: "RotateKubeletServerCertificate=true"
    nodeLabels:
      node-role.kubernetes.io/control-plane: ""

  network:
    hostname: control-plane-01
    nameservers:
      - 1.1.1.1
      - 8.8.8.8
    interfaces:
      - interface: eth0
        addresses:
          - 192.168.1.10/24
        routes:
          - network: 0.0.0.0/0
            gateway: 192.168.1.1

cluster:
  clusterName: production-cluster

  controlPlane:
    endpoint: https://192.168.1.100:6443

  apiServer:
    image: registry.k8s.io/kube-apiserver:v1.31.0
    certSANs:
      - 192.168.1.100
      - api.example.com
      - production-cluster.local
    extraArgs:
      audit-log-path: /var/log/audit.log
      audit-log-maxage: "30"
      audit-log-maxbackup: "10"
      audit-log-maxsize: "100"
      audit-policy-file: /etc/kubernetes/audit-policy.yaml
      enable-admission-plugins: NodeRestriction,PodSecurityPolicy
      encryption-provider-config: /etc/kubernetes/encryption-config.yaml

  controllerManager:
    image: registry.k8s.io/kube-controller-manager:v1.31.0
    extraArgs:
      bind-address: "0.0.0.0"
      leader-elect: "true"
      node-cidr-mask-size: "24"

  scheduler:
    image: registry.k8s.io/kube-scheduler:v1.31.0
    extraArgs:
      bind-address: "0.0.0.0"
      leader-elect: "true"

  etcd:
    image: gcr.io/etcd-development/etcd:v3.5.15
    advertisedSubnets:
      - 192.168.1.0/24
    extraArgs:
      listen-metrics-urls: "http://0.0.0.0:2381"
      election-timeout: "5000"
      heartbeat-interval: "500"
      quota-backend-bytes: "8589934592"  # 8GB

  network:
    cni:
      name: custom
      urls:
        - https://raw.githubusercontent.com/cilium/cilium/v1.16.0/install/kubernetes/quick-install.yaml
    dnsDomain: cluster.local
    podSubnets:
      - 10.244.0.0/16
    serviceSubnets:
      - 10.96.0.0/12
```

### etcd Configuration Best Practices

**Performance Tuning**:
```yaml
cluster:
  etcd:
    # Database size management
    extraArgs:
      quota-backend-bytes: "8589934592"  # 8GB limit
      auto-compaction-mode: "periodic"
      auto-compaction-retention: "5m"  # Compact every 5 minutes
      snapshot-count: "10000"  # Snapshot after 10k changes

      # Performance tuning
      heartbeat-interval: "500"  # 500ms
      election-timeout: "5000"  # 5000ms

      # Monitoring
      listen-metrics-urls: "http://0.0.0.0:2381"

      # Backup configuration
      enable-v2: "false"  # Disable deprecated v2 API
```

**etcd Maintenance Commands**:
```bash
# Check etcd health
talosctl --nodes 192.168.1.10 service etcd status

# List etcd members
talosctl --nodes 192.168.1.10 etcd members

# Check database size
talosctl --nodes 192.168.1.10 etcd status

# Defragment database (run on each member)
talosctl --nodes 192.168.1.10 etcd defrag

# Compact old revisions
talosctl --nodes 192.168.1.10 etcd alarm disarm
talosctl --nodes 192.168.1.10 etcd compact

# Snapshot for backup
talosctl --nodes 192.168.1.10 etcd snapshot /tmp/etcd-backup.db
```

### API Server Configuration

**High Availability Setup**:
```yaml
cluster:
  apiServer:
    # Certificate SANs for all access methods
    certSANs:
      - 192.168.1.100  # VIP
      - 192.168.1.10   # CP node 1
      - 192.168.1.11   # CP node 2
      - 192.168.1.12   # CP node 3
      - api.production.example.com
      - kubernetes
      - kubernetes.default
      - kubernetes.default.svc
      - kubernetes.default.svc.cluster.local

    # Performance and limits
    extraArgs:
      max-requests-inflight: "400"
      max-mutating-requests-inflight: "200"
      default-watch-cache-size: "100"
      event-ttl: "1h"

      # Security
      anonymous-auth: "false"
      authorization-mode: "Node,RBAC"
      enable-admission-plugins: "NodeRestriction,PodSecurity"

      # Auditing
      audit-log-path: "/var/log/kubernetes/audit.log"
      audit-log-maxage: "30"
      audit-log-maxbackup: "10"
      audit-log-maxsize: "100"
      audit-policy-file: "/etc/kubernetes/audit-policy.yaml"
```

---

## Worker Node Sizing and Scaling

### Node Sizing Guidelines

**Small Worker Node** (Development/Edge):
```yaml
resources:
  cpu_cores: 2-4
  memory_gb: 4-8
  storage_gb: 50-100

workload_capacity:
  max_pods: 50
  typical_services: 5-10
  resource_allocation:
    cpu_allocatable: "1.8 cores"  # After system/kube reserved
    memory_allocatable: "6 GiB"   # After system/kube reserved

cost_profile:
  monthly_cost: $30-60
  use_case: "Dev, testing, edge"
```

**Medium Worker Node** (General Production):
```yaml
resources:
  cpu_cores: 8-16
  memory_gb: 16-32
  storage_gb: 200-500

workload_capacity:
  max_pods: 110
  typical_services: 20-30
  resource_allocation:
    cpu_allocatable: "14 cores"
    memory_allocatable: "28 GiB"

cost_profile:
  monthly_cost: $100-200
  use_case: "General production workloads"
```

**Large Worker Node** (High-Performance):
```yaml
resources:
  cpu_cores: 32-64
  memory_gb: 64-256
  storage_gb: 1000-2000

workload_capacity:
  max_pods: 110  # Still limited by default
  typical_services: 30-50
  resource_allocation:
    cpu_allocatable: "60 cores"
    memory_allocatable: "250 GiB"

cost_profile:
  monthly_cost: $400-1000
  use_case: "ML/AI, databases, high-memory apps"
```

### Resource Reservation Patterns

**Standard Reservation**:
```yaml
machine:
  kubelet:
    extraArgs:
      # System reserved (OS, system daemons)
      system-reserved: "cpu=200m,memory=512Mi,ephemeral-storage=1Gi"

      # Kubernetes reserved (kubelet, kube-proxy, etc)
      kube-reserved: "cpu=200m,memory=512Mi,ephemeral-storage=1Gi"

      # Eviction thresholds
      eviction-hard: "memory.available<500Mi,nodefs.available<10%,imagefs.available<10%"
      eviction-soft: "memory.available<1Gi,nodefs.available<15%"
      eviction-soft-grace-period: "memory.available=2m,nodefs.available=2m"

      # Pod limits
      max-pods: "110"
      pods-per-core: "10"
```

**High-Density Configuration**:
```yaml
machine:
  kubelet:
    extraArgs:
      # Minimal reservations for maximum pod density
      system-reserved: "cpu=100m,memory=256Mi"
      kube-reserved: "cpu=100m,memory=256Mi"
      max-pods: "250"  # Increase from default 110
      pods-per-core: "25"

      # Pod resource limits
      registry-qps: "20"
      registry-burst: "40"
      serialize-image-pulls: "false"  # Parallel image pulls
```

### Horizontal Scaling Patterns

**Manual Scaling Process**:
```bash
# 1. Provision new VMs (via infrastructure-contractor)
# 2. Apply worker configuration
talosctl apply-config --insecure \
  --nodes 192.168.1.50 \
  --file worker.yaml

# 3. Wait for node to join
kubectl wait --for=condition=Ready node/worker-07 --timeout=5m

# 4. Label new node
kubectl label node worker-07 \
  node-pool=general \
  workload-type=general

# 5. Verify node is schedulable
kubectl describe node worker-07 | grep -i taint
```

**Cluster Autoscaler Integration**:
```yaml
# Install cluster autoscaler
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cluster-autoscaler
  template:
    metadata:
      labels:
        app: cluster-autoscaler
    spec:
      serviceAccountName: cluster-autoscaler
      containers:
      - name: cluster-autoscaler
        image: registry.k8s.io/autoscaling/cluster-autoscaler:v1.31.0
        command:
          - ./cluster-autoscaler
          - --cloud-provider=clusterapi  # or your provider
          - --nodes=3:20:worker-pool-general
          - --scale-down-enabled=true
          - --scale-down-delay-after-add=10m
          - --scale-down-unneeded-time=10m
          - --skip-nodes-with-local-storage=false
        resources:
          requests:
            cpu: 100m
            memory: 300Mi
```

### Vertical Scaling (Node Resizing)

**Process**:
```bash
# 1. Cordon node to prevent new pods
kubectl cordon worker-05

# 2. Drain node gracefully
kubectl drain worker-05 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=300

# 3. Power off node
talosctl --nodes 192.168.1.24 shutdown

# 4. Resize VM (via infrastructure-contractor or hypervisor)
# - Increase CPU cores
# - Increase memory
# - Increase storage

# 5. Power on node
# Node will rejoin cluster automatically

# 6. Uncordon node
kubectl uncordon worker-05

# 7. Verify new resources
kubectl describe node worker-05 | grep -A 10 "Capacity"
```

---

## Storage Options

### Longhorn Distributed Storage

**Architecture**:
- Distributed block storage built for Kubernetes
- Replicates data across multiple nodes
- Built-in snapshots and backups
- iSCSI-based volume provisioning

**Installation**:
```bash
# 1. Install Longhorn prerequisites on Talos
# Talos includes open-iscsi by default, no extra configuration needed

# 2. Install Longhorn via Helm
helm repo add longhorn https://charts.longhorn.io
helm repo update

helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --create-namespace \
  --version 1.7.0 \
  --set defaultSettings.defaultReplicaCount=3 \
  --set defaultSettings.defaultDataPath="/var/lib/longhorn" \
  --set persistence.defaultClass=true \
  --set persistence.defaultClassReplicaCount=3

# 3. Wait for deployment
kubectl wait --for=condition=ready pod \
  -n longhorn-system \
  -l app=longhorn-manager \
  --timeout=10m

# 4. Verify storage class
kubectl get storageclass longhorn
```

**Longhorn Configuration**:
```yaml
# StorageClass with custom parameters
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn-fast
provisioner: driver.longhorn.io
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: Immediate
parameters:
  numberOfReplicas: "3"
  staleReplicaTimeout: "2880"  # 48 hours
  fromBackup: ""
  fsType: "ext4"
  dataLocality: "disabled"  # or "best-effort"
  replicaAutoBalance: "disabled"
```

**Longhorn Features**:

1. **Snapshots**:
```bash
# Create snapshot via kubectl
kubectl create -f - <<EOF
apiVersion: longhorn.io/v1beta2
kind: Snapshot
metadata:
  name: pvc-backup-20240101
  namespace: default
spec:
  volume: pvc-abc123
EOF

# Restore from snapshot
kubectl create -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restored-pvc
spec:
  dataSource:
    name: pvc-backup-20240101
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 10Gi
EOF
```

2. **Backups to S3**:
```yaml
# Configure backup target
apiVersion: longhorn.io/v1beta2
kind: Setting
metadata:
  name: backup-target
  namespace: longhorn-system
value: "s3://longhorn-backups@us-east-1/"

---
apiVersion: v1
kind: Secret
metadata:
  name: aws-secret
  namespace: longhorn-system
type: Opaque
data:
  AWS_ACCESS_KEY_ID: <base64-encoded>
  AWS_SECRET_ACCESS_KEY: <base64-encoded>
```

3. **Volume Encryption**:
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn-encrypted
provisioner: driver.longhorn.io
parameters:
  numberOfReplicas: "3"
  encrypted: "true"
  # Requires encrypted CSI driver
```

**Performance Tuning**:
```yaml
# Longhorn settings for performance
apiVersion: longhorn.io/v1beta2
kind: Setting
metadata:
  name: guarantee-engine-manager-cpu
value: "12"  # Percentage of CPU guaranteed

---
apiVersion: longhorn.io/v1beta2
kind: Setting
metadata:
  name: guarantee-replica-manager-cpu
value: "12"
```

**Monitoring**:
```bash
# Access Longhorn UI
kubectl port-forward -n longhorn-system \
  svc/longhorn-frontend 8080:80

# Open http://localhost:8080

# Prometheus metrics endpoint
kubectl get svc -n longhorn-system longhorn-manager
# Scrape metrics from http://<svc-ip>:9500/metrics
```

---

### Local Path Provisioner

**Use Case**: Fast local storage for non-critical or development workloads.

**Installation**:
```bash
# Install local-path-provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.28/deploy/local-path-storage.yaml

# Verify installation
kubectl get storageclass local-path
kubectl get pods -n local-path-storage
```

**Configuration**:
```yaml
# ConfigMap for local-path-provisioner
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-path-config
  namespace: local-path-storage
data:
  config.json: |-
    {
      "nodePathMap":[
        {
          "node":"DEFAULT_PATH_FOR_NON_LISTED_NODES",
          "paths":["/var/lib/local-path-provisioner"]
        },
        {
          "node":"worker-01",
          "paths":["/mnt/ssd/local-path"]
        },
        {
          "node":"worker-02",
          "paths":["/mnt/ssd/local-path"]
        }
      ]
    }
  setup: |-
    #!/bin/sh
    set -eu
    mkdir -m 0777 -p "$VOL_DIR"
  teardown: |-
    #!/bin/sh
    set -eu
    rm -rf "$VOL_DIR"
```

**Usage Example**:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: local-storage-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 10Gi
```

**Limitations**:
- No replication or redundancy
- Data lost if node fails
- Pods pinned to specific nodes
- Not suitable for production databases
- No volume migration between nodes

---

### NFS Storage

**Architecture**: External NFS server provides shared storage.

**NFS Server Setup** (outside Kubernetes):
```bash
# On NFS server (Ubuntu/Debian)
sudo apt install nfs-kernel-server

# Create export directory
sudo mkdir -p /srv/nfs/k8s
sudo chown nobody:nogroup /srv/nfs/k8s

# Configure exports
sudo tee /etc/exports <<EOF
/srv/nfs/k8s 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
EOF

# Apply and start NFS
sudo exportfs -ra
sudo systemctl restart nfs-kernel-server
```

**Client Installation in Cluster**:
```bash
# Install NFS CSI driver
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner

helm install nfs-provisioner \
  nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --namespace kube-system \
  --set nfs.server=192.168.1.5 \
  --set nfs.path=/srv/nfs/k8s \
  --set storageClass.name=nfs-client \
  --set storageClass.defaultClass=false \
  --set storageClass.accessModes=ReadWriteMany
```

**Usage Example** (ReadWriteMany):
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-storage
spec:
  accessModes:
    - ReadWriteMany  # Multiple pods can mount
  storageClassName: nfs-client
  resources:
    requests:
      storage: 50Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 3  # All replicas share the volume
  template:
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        volumeMounts:
        - name: shared-data
          mountPath: /usr/share/nginx/html
      volumes:
      - name: shared-data
        persistentVolumeClaim:
          claimName: shared-storage
```

**Performance Considerations**:
- Network latency adds overhead
- Not suitable for databases (file locking issues)
- Good for: logs, uploads, shared configs
- NFS server becomes bottleneck
- Use 10GbE network for better performance

---

### Ceph RBD (Enterprise)

**Overview**: Enterprise-grade distributed storage with Rook operator.

**Prerequisites**:
```bash
# Each node needs raw block device
# Check available devices
lsblk -f

# Ensure devices are clean (no filesystem or partitions)
sudo wipefs -a /dev/sdb
```

**Rook Operator Installation**:
```bash
# Install Rook operator
helm repo add rook-release https://charts.rook.io/release
helm repo update

helm install rook-ceph rook-release/rook-ceph \
  --namespace rook-ceph \
  --create-namespace \
  --version v1.14.0

# Wait for operator
kubectl wait --for=condition=ready pod \
  -n rook-ceph \
  -l app=rook-ceph-operator \
  --timeout=5m
```

**Ceph Cluster Configuration**:
```yaml
apiVersion: ceph.rook.io/v1
kind: CephCluster
metadata:
  name: rook-ceph
  namespace: rook-ceph
spec:
  cephVersion:
    image: quay.io/ceph/ceph:v18.2.0
  dataDirHostPath: /var/lib/rook
  mon:
    count: 3
    allowMultiplePerNode: false
  mgr:
    count: 2
  dashboard:
    enabled: true
  storage:
    useAllNodes: false
    useAllDevices: false
    nodes:
      - name: "worker-01"
        devices:
          - name: "/dev/sdb"
      - name: "worker-02"
        devices:
          - name: "/dev/sdb"
      - name: "worker-03"
        devices:
          - name: "/dev/sdb"
```

**Storage Class**:
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  clusterID: rook-ceph
  pool: replicapool
  imageFormat: "2"
  imageFeatures: layering
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-rbd-node
  csi.storage.k8s.io/fstype: ext4
reclaimPolicy: Delete
allowVolumeExpansion: true
```

---

## Networking

### CNI Options Comparison

| Feature | Cilium | Flannel | Calico |
|---------|--------|---------|--------|
| Performance | Excellent (eBPF) | Good (VXLAN) | Good-Excellent |
| Network Policy | Yes (eBPF) | No | Yes (iptables/eBPF) |
| Service Mesh | Built-in | No | No |
| Observability | Hubble | Basic | Basic |
| Complexity | Medium | Low | Medium |
| Best For | Production, security | Dev, simple | Security, compliance |

### Cilium CNI Installation

**Installation via Helm**:
```bash
# Add Cilium repo
helm repo add cilium https://helm.cilium.io/
helm repo update

# Install Cilium
helm install cilium cilium/cilium \
  --namespace kube-system \
  --version 1.16.0 \
  --set operator.replicas=2 \
  --set ipam.mode=kubernetes \
  --set tunnel=disabled \  # Native routing
  --set autoDirectNodeRoutes=true \
  --set kubeProxyReplacement=strict \
  --set k8sServiceHost=192.168.1.100 \
  --set k8sServicePort=6443 \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true

# Verify installation
cilium status --wait
```

**Cilium Features Configuration**:

1. **Network Policies**:
```yaml
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: allow-frontend-to-backend
spec:
  endpointSelector:
    matchLabels:
      app: backend
  ingress:
    - fromEndpoints:
        - matchLabels:
            app: frontend
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
```

2. **Service Mesh (without Istio)**:
```bash
# Enable service mesh
helm upgrade cilium cilium/cilium \
  --namespace kube-system \
  --reuse-values \
  --set encryption.enabled=true \
  --set encryption.type=wireguard

# Enable L7 traffic management
kubectl annotate pod my-pod \
  "policy.cilium.io/proxy-visibility=<Ingress/80/TCP/HTTP>"
```

3. **Hubble Observability**:
```bash
# Install Hubble CLI
HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)
curl -L --remote-name-all https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz
tar xzvf hubble-linux-amd64.tar.gz
sudo mv hubble /usr/local/bin

# Access Hubble UI
kubectl port-forward -n kube-system svc/hubble-ui 12000:80

# CLI observability
hubble observe --namespace default
hubble observe --pod frontend-pod --follow
```

**Cilium Performance Tuning**:
```yaml
# High-performance configuration
helm upgrade cilium cilium/cilium \
  --namespace kube-system \
  --reuse-values \
  --set bpf.monitorAggregation=maximum \
  --set bpf.ctTcpMax=524288 \
  --set bpf.ctAnyMax=262144 \
  --set bpf.hostRouting=true \
  --set bandwidthManager.enabled=true
```

---

### Flannel CNI (Simple & Reliable)

**Installation**:
```bash
# Flannel with VXLAN backend
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml

# Verify
kubectl get pods -n kube-flannel
```

**Configuration**:
```yaml
# Edit kube-flannel ConfigMap for custom settings
apiVersion: v1
kind: ConfigMap
metadata:
  name: kube-flannel-cfg
  namespace: kube-flannel
data:
  net-conf.json: |
    {
      "Network": "10.244.0.0/16",
      "Backend": {
        "Type": "vxlan",
        "Port": 8472
      }
    }
```

**Host-GW Backend** (for better performance when nodes are in same L2 network):
```json
{
  "Network": "10.244.0.0/16",
  "Backend": {
    "Type": "host-gw"
  }
}
```

---

### Ingress Controllers

#### NGINX Ingress Controller

**Installation**:
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.service.type=LoadBalancer \
  --set controller.metrics.enabled=true \
  --set controller.podAnnotations."prometheus\.io/scrape"="true" \
  --set controller.podAnnotations."prometheus\.io/port"="10254"
```

**Usage Example**:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - example.com
    secretName: example-tls
  rules:
  - host: example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

#### Traefik Ingress Controller

**Installation**:
```bash
helm repo add traefik https://traefik.github.io/charts
helm repo update

helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace \
  --set ports.web.redirectTo.port=websecure \
  --set ports.websecure.tls.enabled=true \
  --set dashboard.enabled=true \
  --set metrics.prometheus.enabled=true
```

**Middleware Example** (Rate Limiting):
```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: rate-limit
spec:
  rateLimit:
    average: 100
    burst: 50
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: default-rate-limit@kubernetescrd
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
```

---

### Service Mesh Integration

**Linkerd** (Lightweight Service Mesh):
```bash
# Install Linkerd CLI
curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | sh
export PATH=$PATH:$HOME/.linkerd2/bin

# Install Linkerd control plane
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check

# Inject sidecar into deployment
kubectl get deploy -n myapp myapp -o yaml \
  | linkerd inject - \
  | kubectl apply -f -

# Verify mesh
linkerd viz install | kubectl apply -f -
linkerd viz dashboard
```

---

## Security Configurations

### Pod Security Standards

**Namespace Configuration**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Pod Security Levels**:
- **Privileged**: Unrestricted (default)
- **Baseline**: Minimally restrictive
- **Restricted**: Heavily restricted, security best practices

**Restricted Pod Example**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: myapp:1.0
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 200m
        memory: 256Mi
    volumeMounts:
    - name: tmp
      mountPath: /tmp
  volumes:
  - name: tmp
    emptyDir: {}
```

### Network Policies

**Default Deny All**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

**Allow Frontend to Backend**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

**Allow DNS**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    - podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

### RBAC Configuration

**Service Account with Limited Access**:
```yaml
# Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-reader
  namespace: production

---
# Role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: configmap-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "watch"]

---
# RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-reader-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: app-reader
  namespace: production
roleRef:
  kind: Role
  name: configmap-reader
  apiGroup: rbac.authorization.k8s.io
```

**ClusterRole for Monitoring**:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus-scraper
rules:
- apiGroups: [""]
  resources:
  - nodes
  - nodes/proxy
  - services
  - endpoints
  - pods
  verbs: ["get", "list", "watch"]
- apiGroups: ["extensions"]
  resources:
  - ingresses
  verbs: ["get", "list", "watch"]
- nonResourceURLs: ["/metrics"]
  verbs: ["get"]
```

### Secrets Management

**Sealed Secrets** (Encrypted Secrets in Git):
```bash
# Install Sealed Secrets controller
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system

# Install kubeseal CLI
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.26.0/kubeseal-0.26.0-linux-amd64.tar.gz
tar xfz kubeseal-0.26.0-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal

# Create sealed secret
kubectl create secret generic mysecret \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml \
  | kubeseal -o yaml > mysealedsecret.yaml

# Commit to Git
git add mysealedsecret.yaml
git commit -m "Add sealed secret"
```

**External Secrets Operator** (Vault/AWS Secrets Manager):
```bash
# Install ESO
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  --namespace external-secrets-system \
  --create-namespace

# Configure SecretStore
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: production
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "my-app-role"
```

---

## Upgrade Strategies

### Rolling Upgrade

**Best Practice Workflow**:
```bash
#!/bin/bash
# Rolling upgrade script

UPGRADE_VERSION="v1.8.1"
CONTROL_PLANE_IPS=("192.168.1.10" "192.168.1.11" "192.168.1.12")
WORKER_IPS=("192.168.1.20" "192.168.1.21" "192.168.1.22" "192.168.1.23")

# 1. Backup etcd
echo "Backing up etcd..."
talosctl --nodes ${CONTROL_PLANE_IPS[0]} etcd snapshot /tmp/etcd-pre-upgrade.db

# 2. Upgrade control plane nodes one by one
for cp_ip in "${CONTROL_PLANE_IPS[@]}"; do
  echo "Upgrading control plane node $cp_ip..."

  talosctl --nodes $cp_ip upgrade \
    --image ghcr.io/siderolabs/installer:${UPGRADE_VERSION} \
    --preserve

  echo "Waiting for node to be ready..."
  sleep 120

  # Verify node health
  talosctl --nodes $cp_ip health --wait-timeout 5m

  echo "Control plane node $cp_ip upgraded successfully"
  sleep 30
done

# 3. Upgrade worker nodes in batches of 2
batch_size=2
for ((i=0; i<${#WORKER_IPS[@]}; i+=batch_size)); do
  batch=("${WORKER_IPS[@]:i:batch_size}")

  echo "Upgrading worker batch: ${batch[*]}"

  for worker_ip in "${batch[@]}"; do
    kubectl drain $(kubectl get node -o wide | grep $worker_ip | awk '{print $1}') \
      --ignore-daemonsets \
      --delete-emptydir-data \
      --grace-period=300 \
      --timeout=10m &
  done

  wait  # Wait for all drains to complete

  for worker_ip in "${batch[@]}"; do
    talosctl --nodes $worker_ip upgrade \
      --image ghcr.io/siderolabs/installer:${UPGRADE_VERSION} \
      --preserve &
  done

  wait  # Wait for all upgrades to start

  sleep 120

  for worker_ip in "${batch[@]}"; do
    talosctl --nodes $worker_ip health --wait-timeout 5m

    node_name=$(kubectl get node -o wide | grep $worker_ip | awk '{print $1}')
    kubectl uncordon $node_name

    echo "Worker node $worker_ip upgraded successfully"
  done

  sleep 30
done

echo "Cluster upgrade complete!"
kubectl get nodes
```

### Blue-Green Cluster Upgrade

**Workflow**:
```bash
# 1. Provision new "green" cluster with target version
# (via infrastructure-contractor)

# 2. Install same applications on green cluster
# (via GitOps - point ArgoCD to new cluster)

# 3. Replicate data to green cluster
# (database replication, storage sync)

# 4. Test green cluster
# (smoke tests, integration tests)

# 5. Switch DNS/load balancer to green cluster
# (update DNS A records, LB backends)

# 6. Monitor green cluster
# (watch metrics, logs, alerts)

# 7. Decommission blue cluster after validation period
# (delete old cluster after 7-14 days)
```

---

## Backup and Disaster Recovery

### etcd Backup Strategies

**Automated Daily Backups**:
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: etcd-backup
  namespace: kube-system
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: etcd-backup
          containers:
          - name: backup
            image: bitnami/kubectl:latest
            command:
            - /bin/bash
            - -c
            - |
              set -e
              BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
              BACKUP_FILE="/backup/etcd-${BACKUP_DATE}.db"

              # Take snapshot
              talosctl --nodes 192.168.1.10 etcd snapshot $BACKUP_FILE

              # Upload to S3
              aws s3 cp $BACKUP_FILE s3://k8s-backups/etcd/

              # Cleanup old local backups
              find /backup -name "etcd-*.db" -mtime +7 -delete

              echo "Backup completed: $BACKUP_FILE"
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
            env:
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: access_key_id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: secret_access_key
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: etcd-backup-pvc
          restartPolicy: OnFailure
```

### etcd Restore Procedure

```bash
# 1. Stop all control plane nodes except one
talosctl --nodes 192.168.1.11 shutdown
talosctl --nodes 192.168.1.12 shutdown

# 2. Restore from backup on remaining node
talosctl --nodes 192.168.1.10 etcd restore \
  --from /backup/etcd-20240101-020000.db

# 3. Reset other control plane nodes
talosctl --nodes 192.168.1.11 reset --graceful=false --reboot
talosctl --nodes 192.168.1.12 reset --graceful=false --reboot

# 4. Reapply configs to reset nodes
talosctl --nodes 192.168.1.11 apply-config --file controlplane-02.yaml
talosctl --nodes 192.168.1.12 apply-config --file controlplane-03.yaml

# 5. Verify etcd cluster
talosctl --nodes 192.168.1.10 etcd members

# 6. Verify cluster health
kubectl get nodes
kubectl get pods --all-namespaces
```

### Application Data Backup

**Velero** (Cluster Backup & Restore):
```bash
# Install Velero
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.10.0 \
  --bucket k8s-velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config region=us-east-1 \
  --snapshot-location-config region=us-east-1 \
  --use-node-agent

# Create backup schedule
velero schedule create daily-backup \
  --schedule="0 3 * * *" \
  --include-namespaces production,staging \
  --ttl 720h  # 30 days

# Manual backup
velero backup create production-backup \
  --include-namespaces production \
  --include-resources '*' \
  --snapshot-volumes

# Restore
velero restore create --from-backup production-backup-20240101
```

---

## GitOps Integration

### ArgoCD Installation

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Expose UI
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Install ArgoCD CLI
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
```

### Application Manifest

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/k8s-manifests
    targetRevision: main
    path: apps/myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
    - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### Flux Installation

```bash
# Install Flux CLI
curl -s https://fluxcd.io/install.sh | sudo bash

# Bootstrap Flux
flux bootstrap github \
  --owner=myorg \
  --repository=k8s-clusters \
  --branch=main \
  --path=clusters/production \
  --personal

# Create GitRepository
flux create source git myapp \
  --url=https://github.com/myorg/myapp \
  --branch=main \
  --interval=1m

# Create Kustomization
flux create kustomization myapp \
  --source=myapp \
  --path="./deploy" \
  --prune=true \
  --interval=5m
```

---

## Monitoring Stack Deployment

### Prometheus + Grafana (kube-prometheus-stack)

```bash
# Install kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=longhorn \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi \
  --set grafana.adminPassword=admin123 \
  --set grafana.persistence.enabled=true \
  --set grafana.persistence.storageClassName=longhorn \
  --set grafana.persistence.size=10Gi

# Access Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# Login: admin / admin123
```

### Custom ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp-metrics
  namespace: production
spec:
  selector:
    matchLabels:
      app: myapp
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

### Alert Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: myapp-alerts
  namespace: monitoring
spec:
  groups:
  - name: myapp
    interval: 30s
    rules:
    - alert: HighErrorRate
      expr: |
        rate(http_requests_total{job="myapp",status=~"5.."}[5m]) > 0.05
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High error rate detected"
        description: "Error rate is {{ $value }} (threshold: 0.05)"

    - alert: PodCrashLooping
      expr: |
        rate(kube_pod_container_status_restarts_total{namespace="production"}[15m]) > 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Pod {{ $labels.pod }} is crash looping"
```

---

## Common Helm Charts

### cert-manager (TLS Certificates)

```bash
# Install cert-manager
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true

# ClusterIssuer for Let's Encrypt
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### External DNS

```bash
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/

helm install external-dns external-dns/external-dns \
  --namespace kube-system \
  --set provider=cloudflare \
  --set cloudflare.apiToken=<token> \
  --set cloudflare.proxied=false \
  --set domainFilters[0]=example.com
```

### Redis Cluster

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami

helm install redis bitnami/redis \
  --namespace production \
  --set architecture=replication \
  --set auth.password=supersecret \
  --set master.persistence.enabled=true \
  --set master.persistence.storageClass=longhorn \
  --set master.persistence.size=10Gi \
  --set replica.replicaCount=2 \
  --set replica.persistence.enabled=true \
  --set replica.persistence.storageClass=longhorn \
  --set replica.persistence.size=10Gi
```

---

## Troubleshooting Guides

### Node Troubleshooting

**Node Not Ready**:
```bash
# 1. Check node status
kubectl describe node <node-name>

# 2. Check kubelet status
talosctl --nodes <ip> service kubelet status
talosctl --nodes <ip> logs kubelet

# 3. Check containerd
talosctl --nodes <ip> service containerd status

# 4. Check disk space
talosctl --nodes <ip> get disk

# 5. Check network connectivity
talosctl --nodes <ip> get addresses
ping <node-ip>

# 6. Restart services if needed
talosctl --nodes <ip> service kubelet restart
```

**High CPU/Memory**:
```bash
# 1. Check top pods on node
kubectl top pods --all-namespaces --sort-by=cpu | grep <node-name>
kubectl top pods --all-namespaces --sort-by=memory | grep <node-name>

# 2. Describe node for resource allocation
kubectl describe node <node-name> | grep -A 10 "Allocated resources"

# 3. Check for resource limits
kubectl get pods --all-namespaces -o json | \
  jq '.items[] | select(.spec.nodeName=="<node-name>") | {name:.metadata.name, limits:.spec.containers[].resources.limits}'
```

### Pod Troubleshooting

**CrashLoopBackOff**:
```bash
# 1. Check pod logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous

# 2. Describe pod for events
kubectl describe pod <pod-name> -n <namespace>

# 3. Check resource limits
kubectl get pod <pod-name> -n <namespace> -o yaml | grep -A 10 resources

# 4. Exec into pod (if possible)
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# 5. Check liveness/readiness probes
kubectl get pod <pod-name> -n <namespace> -o yaml | grep -A 10 livenessProbe
```

**ImagePullBackOff**:
```bash
# 1. Check image name
kubectl describe pod <pod-name> | grep Image

# 2. Check image pull secrets
kubectl get pod <pod-name> -o yaml | grep imagePullSecrets

# 3. Test image pull manually
docker pull <image-name>

# 4. Check registry credentials
kubectl get secret <secret-name> -o yaml
```

### Network Troubleshooting

**Pod-to-Pod Connectivity**:
```bash
# 1. Deploy test pod
kubectl run test-pod --image=nicolaka/netshoot --rm -it -- /bin/bash

# 2. Inside test pod, check connectivity
ping <target-pod-ip>
curl http://<target-pod-ip>:8080

# 3. Check DNS resolution
nslookup kubernetes.default
nslookup <service-name>.<namespace>.svc.cluster.local

# 4. Check network policies
kubectl get networkpolicies --all-namespaces
kubectl describe networkpolicy <policy-name> -n <namespace>
```

**Service Not Reachable**:
```bash
# 1. Check service endpoints
kubectl get endpoints <service-name> -n <namespace>

# 2. Check service configuration
kubectl describe service <service-name> -n <namespace>

# 3. Check pod labels match service selector
kubectl get pods -n <namespace> --show-labels
kubectl get service <service-name> -n <namespace> -o yaml | grep selector

# 4. Test service from within cluster
kubectl run test-pod --image=curlimages/curl --rm -it -- \
  curl http://<service-name>.<namespace>.svc.cluster.local
```

### Storage Troubleshooting

**PVC Pending**:
```bash
# 1. Describe PVC
kubectl describe pvc <pvc-name> -n <namespace>

# 2. Check storage class
kubectl get storageclass
kubectl describe storageclass <storage-class-name>

# 3. Check provisioner logs
kubectl logs -n kube-system -l app=local-path-provisioner
kubectl logs -n longhorn-system -l app=longhorn-manager

# 4. Check available storage on nodes
kubectl get nodes -o json | \
  jq '.items[] | {name:.metadata.name, allocatable:.status.allocatable}'
```

---

## Performance Optimization Patterns

### Node Optimization

```yaml
machine:
  kubelet:
    extraArgs:
      # Image pull optimization
      serialize-image-pulls: "false"
      max-parallel-image-pulls: "3"

      # Registry optimization
      registry-qps: "20"
      registry-burst: "40"

      # Eviction tuning
      eviction-hard: "memory.available<500Mi,nodefs.available<5%"
      eviction-minimum-reclaim: "memory.available=500Mi,nodefs.available=5%"

      # Pod lifecycle
      pod-max-pids: "4096"
```

### etcd Performance Tuning

```bash
# Monitor etcd performance
talosctl --nodes <cp-ip> etcd status

# Key metrics:
# - DB size (should be < 8GB)
# - Backend commit duration (should be < 25ms p99)
# - Peer round trip time (should be < 50ms)

# If performance is degraded:
# 1. Defragment
talosctl --nodes <cp-ip> etcd defrag

# 2. Compact
talosctl --nodes <cp-ip> etcd alarm disarm

# 3. Check disk I/O
# Ensure etcd is on SSD with > 3000 IOPS
```

---

This comprehensive patterns document provides 500+ lines of deep domain knowledge for the talos-contractor agent in the Cortex ecosystem. It covers all major aspects of Talos Linux and Kubernetes cluster management, including practical examples, troubleshooting guides, and best practices.
