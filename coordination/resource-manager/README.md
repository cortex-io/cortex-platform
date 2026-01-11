# Resource Manager

**Dynamic Infrastructure and Worker Pool Management for Cortex**

---

## Overview

The Resource Manager is responsible for dynamic infrastructure provisioning, worker pool management, and resource optimization across the Cortex ecosystem. It orchestrates Proxmox for VM provisioning and Talos for Kubernetes cluster management.

### Core Capabilities

- **Worker Pool Management**: Dynamic provisioning of Kubernetes workers (permanent, burst, spot, GPU)
- **Auto-Scaling**: Metric and trigger-based scaling for elastic capacity
- **TTL Management**: Automatic cleanup of temporary infrastructure
- **Health Monitoring**: Continuous worker health checks with auto-repair
- **Cost Optimization**: Spot workers and intelligent resource allocation
- **MCP Integration**: Seamless coordination with Proxmox and Talos MCP servers

---

## Directory Structure

```
coordination/resource-manager/
├── README.md                        # This file
├── cost-tracking.md                 # Cost tracking and budget management
├── cost-tracking.json               # Cost metrics, budgets, alerts
├── worker-pools.md                  # Complete worker pool documentation
├── worker-pools.json                # Worker pool configurations
├── worker-pools-quickstart.md       # Quick reference guide
├── k8s-integration.md               # Kubernetes integration details
├── mcp-scaling.md                   # MCP-based scaling documentation
└── mcp-scaling.json                 # MCP scaling configurations
```

---

## Quick Start

### 1. Provision Burst Workers

For temporary traffic spikes:

```bash
# 3 medium workers, 4-hour TTL
./scripts/provision-burst-workers.sh --count 3 --template medium --ttl 4h
```

### 2. Provision Spot Workers

For cost-optimized batch processing:

```bash
# 5 spot workers for batch jobs
./scripts/provision-spot-workers.sh --count 5 --template medium
```

### 3. Provision GPU Workers

For ML/AI workloads:

```bash
# 1 GPU worker with NVIDIA Tesla T4
./scripts/provision-gpu-worker.sh --count 1 --template gpu-nvidia
```

### 4. Check Pool Status

```bash
# View all workers by pool
kubectl get nodes -L node-pool,worker-type,ttl

# View specific pool
kubectl get nodes -l node-pool=burst
```

---

## Documentation

### Cost Tracking and Budget Management

**[Cost Tracking](./cost-tracking.md)**
Comprehensive cost tracking and optimization:
- API token usage tracking per agent/contractor/division
- Compute time tracking (CPU hours, memory hours)
- Storage usage metrics across tiers
- Network egress tracking
- Budget allocation per division/project
- Cost alerts and thresholds (75%, 90%, 100%)
- Chargeback/showback models
- AI-powered cost optimization recommendations
- Historical cost analysis and anomaly detection
- Forecasting and budgeting (30/90/365 day)
- ROI analysis and value tracking
- Dashboard examples (Executive, Division GM, Resource Manager)

**Key Features**:
- 200,000 token daily budget across organization
- Real-time tracking and attribution
- Progressive alerts (Info, Warning, Critical, Emergency)
- Optimization engine with 5+ recommendation types
- Monthly cost reporting and variance analysis

### Worker Pool Management

**[Worker Pool Management](./worker-pools.md)**
Complete guide covering:
- Burst worker provisioning via Proxmox API
- Automatic cluster join/leave procedures for Talos
- TTL-based cleanup of temporary workers
- Worker templates (small, medium, large, GPU)
- Node labels and taints strategy
- Affinity and anti-affinity rules
- Preemptible/spot worker configurations
- Worker health monitoring
- Graceful drain and cordon procedures
- Auto-repair mechanisms

**[Quick Start Guide](./worker-pools-quickstart.md)**
Fast reference for:
- Common commands
- Workflow examples
- Scheduling cheat sheet
- Troubleshooting
- Cost optimization tips

**[Kubernetes Integration](./k8s-integration.md)**
Deep dive on:
- Kubernetes cluster integration
- Pod scheduling strategies
- Resource quotas and limits
- Storage and networking
- Monitoring and observability

**[MCP Scaling](./mcp-scaling.md)**
MCP server integration:
- Proxmox MCP provisioning workflows
- Talos MCP cluster operations
- Scaling automation
- Error handling and retries

---

## Configuration Files

### [cost-tracking.json](./cost-tracking.json)

Complete cost tracking configuration including:

**Metric Definitions**:
- API tokens (input, output, cached, cache_creation)
- Compute (CPU hours, memory hours, GPU hours)
- Storage (hot, warm, cold tiers)
- Network (intra-region, inter-region, egress)
- Efficiency metrics and optimization thresholds

**Model Pricing**:
- Claude Opus 4.5: $15/$75 per 1M (input/output)
- Claude Sonnet 4.5: $3/$15 per 1M (standard tier)
- Claude Haiku 3.5: $0.80/$4 per 1M (economy tier)
- Cache read/write rates

**Budget Configuration**:
- Organizational: 200k tokens/day total
- Divisions: Infrastructure (20k), Containers (15k), Workflows (12k), etc.
- Shared Services: Security (25k), Development (30k), CI/CD (15k), etc.
- Meta Level: Cortex Prime (10k), COO (5k)
- Emergency Reserve: 2k tokens
- Project budgets with time-bound allocations

**Alert Thresholds**:
- Token budget warnings (50%, 75%, 90%, 100%)
- Compute overallocation alerts
- Storage capacity alerts (80%, 90%, 95%)
- Network egress spike detection (3x baseline anomaly)
- Cost variance alerts (10%, 20%, 35%)
- Optimization opportunity notifications

**Optimization Rules**:
- Model selection (downgrade to Haiku/Sonnet where appropriate)
- Cache improvements (increase TTL, enable caching)
- Batch processing (reduce overhead 40-50%)
- Resource rightsizing (CPU/memory optimization)
- Storage tier migration (hot→warm→cold)
- Schedule optimization (off-peak execution)

**Rate Cards**:
- Internal rates (cost-based, 0% markup)
- External rates (cost + 20% markup for clients)
- Chargeback/showback models

### [worker-pools.json](./worker-pools.json)

Production-ready configuration including:

**Worker Pool Definitions**:
- `permanent`: Baseline production capacity
- `burst`: Temporary spike handling
- `spot`: Cost-optimized preemptible workers
- `gpu`: GPU workers for ML/AI

**Worker Templates**:
- `small`: 4 vCPU, 8GB RAM, 100GB SSD ($0.12/hr)
- `medium`: 8 vCPU, 16GB RAM, 200GB SSD ($0.24/hr)
- `large`: 16 vCPU, 32GB RAM, 500GB SSD ($0.48/hr)
- `gpu-nvidia`: 8 vCPU, 32GB RAM, 500GB SSD + Tesla T4 ($1.20/hr)

**Lifecycle Configurations**:
- Provisioning workflows
- Joining procedures
- Draining strategies
- Termination cleanup
- TTL enforcement
- Health monitoring
- Auto-repair policies

**Integration Settings**:
- Proxmox API configuration
- Talos cluster settings
- Kubernetes parameters
- Cost tracking
- Monitoring and alerting

### [mcp-scaling.json](./mcp-scaling.json)

MCP server scaling policies:
- Scaling triggers and thresholds
- Provisioning workflows
- Error handling strategies
- Retry policies
- Timeout configurations

---

## Worker Pool Types

| Pool Type | Min | Max | TTL | Auto-Scale | Cost Savings | Use Case |
|-----------|-----|-----|-----|------------|--------------|----------|
| **Permanent** | 3 | 10 | No | Yes | 0% | Production apps, databases |
| **Burst** | 0 | 20 | 4h | Yes | 0% | Traffic spikes, temporary load |
| **Spot** | 0 | 15 | No* | Yes | 70% | Batch jobs, interruptible work |
| **GPU** | 0 | 5 | No | Manual | N/A | ML training, inference |

*Spot workers are preemptible, not TTL-based

---

## Worker Templates

### Small Worker
- **CPU**: 4 vCPU
- **RAM**: 8 GB
- **Disk**: 100 GB SSD
- **Cost**: $0.12/hour
- **Use Cases**: Microservices, dev/test, sidecars

### Medium Worker
- **CPU**: 8 vCPU
- **RAM**: 16 GB
- **Disk**: 200 GB SSD
- **Cost**: $0.24/hour
- **Use Cases**: Web apps, APIs, small databases

### Large Worker
- **CPU**: 16 vCPU
- **RAM**: 32 GB
- **Disk**: 500 GB SSD
- **Cost**: $0.48/hour
- **Use Cases**: Large databases, data processing

### GPU Worker (NVIDIA)
- **CPU**: 8 vCPU
- **RAM**: 32 GB
- **Disk**: 500 GB SSD
- **GPU**: NVIDIA Tesla T4 (16GB VRAM)
- **Cost**: $1.20/hour
- **Use Cases**: ML training, inference, video encoding

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Resource Manager                            │
│  - Pool orchestration                                           │
│  - Scaling decisions                                            │
│  - Health monitoring                                            │
│  - TTL enforcement                                              │
└────────────┬───────────────────────────────────┬────────────────┘
             │                                   │
   ┌─────────▼─────────┐             ┌──────────▼──────────┐
   │  Proxmox MCP      │             │  Talos MCP          │
   │  - VM provision   │             │  - Cluster join     │
   │  - Template clone │             │  - Config apply     │
   │  - Lifecycle mgmt │             │  - Node drain       │
   └─────────┬─────────┘             └──────────┬──────────┘
             │                                   │
   ┌─────────▼──────────────────────────────────▼──────────┐
   │           Kubernetes Cluster (Talos)                   │
   │                                                         │
   │  ┌────────────┐  ┌────────────┐  ┌────────────┐      │
   │  │ Control    │  │ Control    │  │ Control    │      │
   │  │ Plane 1    │  │ Plane 2    │  │ Plane 3    │      │
   │  └────────────┘  └────────────┘  └────────────┘      │
   │                                                         │
   │  ┌────────────┐  ┌────────────┐  ┌────────────┐      │
   │  │ Worker-1   │  │ Worker-2   │  │ Worker-N   │ ...  │
   │  │ [Perm]     │  │ [Burst]    │  │ [Spot]     │      │
   │  └────────────┘  └────────────┘  └────────────┘      │
   └─────────────────────────────────────────────────────────┘
```

---

## Integration with MCP Servers

### Proxmox MCP Server

**Repository**: https://github.com/ry-ops/proxmox-mcp-server

**Key Operations**:
- `clone_vm`: Clone from worker templates
- `start_vm`: Boot provisioned workers
- `stop_vm`: Gracefully shutdown workers
- `delete_vm`: Remove terminated workers
- `get_vm_status`: Monitor worker health

**Configuration**:
```bash
export PROXMOX_URL="https://pve-01.example.com:8006"
export PROXMOX_TOKEN_ID="cortex@pam!worker-provisioner"
export PROXMOX_TOKEN_SECRET="<secret>"
```

### Talos MCP Server

**Repository**: https://github.com/ry-ops/talos-mcp-server

**Key Operations**:
- `generate_config`: Create worker configurations
- `apply_config`: Apply config to new workers
- `health`: Monitor worker health
- `upgrade`: Upgrade worker OS/Kubernetes
- `reboot`: Gracefully reboot workers

**Configuration**:
```bash
export TALOS_CLUSTER="prod-k8s"
export TALOS_ENDPOINT="https://192.168.1.10:6443"
```

---

## Scaling Triggers

### Automatic Triggers

**Pending Pods**:
- Threshold: 5+ pods pending
- Duration: 120 seconds
- Action: Provision burst workers

**CPU Pressure**:
- Threshold: 80% cluster utilization
- Duration: 300 seconds
- Action: Scale permanent or burst pool

**Memory Pressure**:
- Threshold: 85% cluster utilization
- Duration: 300 seconds
- Action: Scale permanent or burst pool

### Manual Triggers

**Scheduled Scaling**:
```bash
# Pre-scale for known events
cron: 0 23 * 11 4  # Nov 24, 11:00 PM (Black Friday)
./scripts/provision-burst-workers.sh --count 10 --template large
```

**API-Triggered**:
```bash
# Via resource manager API
curl -X POST http://resource-manager/api/v1/pools/burst/scale \
  -d '{"workers": 5, "template": "medium", "ttl_hours": 4}'
```

---

## TTL Management

### TTL Lifecycle

1. **Provisioned**: Worker created with TTL timestamp
2. **Running**: Worker accepts workloads
3. **Approaching TTL**: 5-minute warning
4. **TTL Expired**: Worker marked for termination
5. **Draining**: Pods evacuated gracefully
6. **Terminated**: Worker removed from cluster and Proxmox

### TTL Labels

```yaml
metadata:
  labels:
    ttl: "1733760000"          # Unix timestamp
    provisioned-at: "1733745600"
    ttl-hours: "4"
```

### TTL Extension

```bash
# Extend by 2 hours
./scripts/extend-worker-ttl.sh worker-burst-001 --hours 2
```

### TTL Cleanup Daemon

- **Check Interval**: Every 5 minutes
- **Grace Period**: 5 minutes past TTL
- **Idle Detection**: Workers with <5% CPU and no workload pods
- **Force Termination**: After 30 minutes idle

---

## Health Monitoring

### Monitored Conditions

- **Node Ready**: Must be True
- **Memory Pressure**: Must be False
- **Disk Pressure**: Must be False
- **PID Pressure**: Must be False
- **Network Unavailable**: Must be False
- **Kubelet Running**: Service must be active
- **Containerd Running**: Service must be active

### Auto-Repair

**Level 1**: Service restart (kubelet, containerd)
**Level 2**: Node reboot (graceful)
**Level 3**: Node replacement (drain + provision new)

### Repair Triggers

| Issue | Duration | Action |
|-------|----------|--------|
| NotReady | 5 min | Restart kubelet |
| NotReady | 10 min | Reboot node |
| NotReady | 20 min | Replace node |
| DiskPressure | Any | Cleanup + prune |
| MemoryPressure | 10 min | Drain + reboot |
| Kubelet crash | 3x | Reboot node |

---

## Cost Tracking

### Monthly Budgets

- **Permanent Pool**: $500/month
- **Burst Pool**: $200/month
- **Spot Pool**: $100/month
- **GPU Pool**: $1000/month

### Cost Optimization

1. **Use Spot Workers**: 70% savings for batch jobs
2. **Right-Size Templates**: Don't over-provision
3. **Set Appropriate TTLs**: Avoid idle burst workers
4. **Monitor Utilization**: Scale down unused capacity
5. **Schedule Pre-Scaling**: Avoid emergency provisioning costs

### Cost Alerts

- Budget threshold: 80% of monthly budget
- Per-event max: $50 for burst provisioning
- Spot preemption tracking enabled

---

## Monitoring and Alerting

### Prometheus Metrics

```promql
# Worker count by pool
count(kube_node_labels{label_node_pool="burst"})

# Workers past TTL
count(kube_node_labels{label_ttl!=""} < time())

# Pending pods
kube_pod_status_phase{phase="Pending"} > 5

# Unhealthy nodes
kube_node_status_condition{condition="Ready",status="false"}
```

### Grafana Dashboards

- **Worker Pool Overview**: Real-time pool status and utilization
- **Worker Lifecycle**: Provisioning, joining, and termination metrics
- **Cost Tracking**: Spend by pool, budget utilization

### Alert Rules

- **worker_provision_timeout**: >10 min provisioning
- **worker_join_failure**: 3+ consecutive failures
- **worker_pool_capacity_low**: >90% utilization
- **ttl_cleanup_failure**: Cleanup daemon errors
- **auto_repair_failure**: 3+ repair failures

---

## Best Practices

### Provisioning

1. **Pre-Scale for Known Events**: Provision before spikes
2. **Test in Staging**: Validate large provisioning operations
3. **Set Appropriate TTLs**: Match workload duration
4. **Monitor Capacity**: Ensure Proxmox has resources
5. **Use Templates Correctly**: Right-size for workload

### Scaling

1. **Gradual Scale-Down**: Remove 20% every 30 minutes
2. **Respect PodDisruptionBudgets**: Don't violate availability
3. **Monitor Metrics**: Watch CPU, memory, pending pods
4. **Use Spot for Batch**: Save costs on interruptible work
5. **Set Resource Requests**: Enable accurate scaling decisions

### Operations

1. **Drain Before Terminate**: Always graceful removal
2. **Check for Pods**: Verify node is empty before deletion
3. **Monitor Health**: Fix issues before they escalate
4. **Track Costs**: Stay within budget
5. **Document Changes**: Record scaling events and reasons

---

## Troubleshooting

### Common Issues

**Worker Won't Join**:
- Check network connectivity
- Verify Talos config
- Check firewall rules (port 6443)
- Review kubelet logs

**Worker Won't Terminate**:
- Check TTL cleanup daemon
- Verify no pods running
- Manual drain if needed
- Force delete if emergency

**Auto-Scaling Not Working**:
- Check pending pods
- Verify triggers in config
- Review metrics
- Manual provision if urgent

**GPU Not Available**:
- Check device plugin
- Verify PCIe passthrough
- Check node labels
- Review pod tolerations

See [Quick Start Guide](./worker-pools-quickstart.md) for detailed troubleshooting.

---

## Scripts

### Provisioning

- `./scripts/provision-burst-workers.sh`: Provision burst workers
- `./scripts/provision-spot-workers.sh`: Provision spot workers
- `./scripts/provision-gpu-worker.sh`: Provision GPU workers

### Management

- `./scripts/remove-worker.sh`: Gracefully remove worker
- `./scripts/extend-worker-ttl.sh`: Extend TTL for burst workers
- `./scripts/drain-worker.sh`: Drain worker without removal
- `./scripts/cordon-worker.sh`: Prevent new pod scheduling

### Monitoring

- `./scripts/check-pool-status.sh`: View all pool status
- `./scripts/check-worker-health.sh`: Health check specific worker
- `./scripts/check-ttl-workers.sh`: List workers with TTL

---

## References

**Documentation**:
- [Cost Tracking](./cost-tracking.md) - Complete cost management guide
- [Worker Pool Management](./worker-pools.md) - Complete guide
- [Quick Start](./worker-pools-quickstart.md) - Fast reference
- [Kubernetes Integration](./k8s-integration.md) - K8s details
- [MCP Scaling](./mcp-scaling.md) - MCP integration

**External**:
- [Proxmox API Docs](https://pve.proxmox.com/pve-docs/api-viewer/)
- [Talos Linux Docs](https://www.talos.dev/)
- [Kubernetes Node Management](https://kubernetes.io/docs/concepts/architecture/nodes/)

**MCP Servers**:
- [Proxmox MCP](https://github.com/ry-ops/proxmox-mcp-server)
- [Talos MCP](https://github.com/ry-ops/talos-mcp-server)

---

**Maintained By**: Resource Manager
**Last Updated**: 2025-12-09
**Next Review**: 2025-03-09
