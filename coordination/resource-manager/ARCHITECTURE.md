# Worker Pool Management Architecture

**System Architecture and Data Flows**

---

## System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         CORTEX ECOSYSTEM                                  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Resource Manager Master                        │    │
│  │  - Pool orchestration and scaling decisions                     │    │
│  │  - Health monitoring and auto-repair                            │    │
│  │  - TTL enforcement and cleanup                                  │    │
│  │  - Cost tracking and optimization                               │    │
│  └───────────┬────────────────────────────────────┬─────────────────┘    │
│              │                                    │                       │
│              │                                    │                       │
│  ┌───────────▼──────────┐           ┌────────────▼──────────┐           │
│  │   Proxmox MCP        │           │   Talos MCP           │           │
│  │   - VM provisioning  │           │   - Cluster join      │           │
│  │   - Template cloning │           │   - Config management │           │
│  │   - Lifecycle mgmt   │           │   - Node operations   │           │
│  │   - Resource monitor │           │   - Health checks     │           │
│  └───────────┬──────────┘           └────────────┬──────────┘           │
│              │                                    │                       │
└──────────────┼────────────────────────────────────┼───────────────────────┘
               │                                    │
               │                                    │
┌──────────────▼────────────────────────────────────▼───────────────────────┐
│                     INFRASTRUCTURE LAYER                                  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                  Proxmox Virtualization                          │    │
│  │                                                                  │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │  │ Template │  │ Template │  │ Template │  │ Template │       │    │
│  │  │  Small   │  │  Medium  │  │  Large   │  │   GPU    │       │    │
│  │  │  (9001)  │  │  (9002)  │  │  (9003)  │  │  (9004)  │       │    │
│  │  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘       │    │
│  │        │             │             │             │              │    │
│  │        └─────────────┴─────────────┴─────────────┘              │    │
│  │                          │                                       │    │
│  │                    Clone & Boot                                 │    │
│  │                          │                                       │    │
│  │  ┌───────────────────────▼──────────────────────────────────┐  │    │
│  │  │              Provisioned Worker VMs                       │  │    │
│  │  │  VM-200  VM-201  VM-202  VM-203  VM-204  ...            │  │    │
│  │  └──────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                Kubernetes Cluster (Talos)                        │    │
│  │                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────┐  │    │
│  │  │               Control Plane (HA)                         │  │    │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │    │
│  │  │  │     CP-1   │  │     CP-2   │  │     CP-3   │         │  │    │
│  │  │  │  etcd      │  │  etcd      │  │  etcd      │         │  │    │
│  │  │  │  API       │  │  API       │  │  API       │         │  │    │
│  │  │  └────────────┘  └────────────┘  └────────────┘         │  │    │
│  │  └──────────────────────────────────────────────────────────┘  │    │
│  │                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────┐  │    │
│  │  │               Worker Nodes (Dynamic Pools)               │  │    │
│  │  │                                                           │  │    │
│  │  │  ┌─────────────────────────────────────────────────┐    │  │    │
│  │  │  │  Permanent Pool (Min: 3, Max: 10)               │    │  │    │
│  │  │  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐│    │  │    │
│  │  │  │  │Worker-1│  │Worker-2│  │Worker-3│  │Worker-N││    │  │    │
│  │  │  │  │ Ready  │  │ Ready  │  │ Ready  │  │ Ready  ││    │  │    │
│  │  │  │  └────────┘  └────────┘  └────────┘  └────────┘│    │  │    │
│  │  │  │  [No TTL] [Auto-Scale Enabled]                  │    │  │    │
│  │  │  └─────────────────────────────────────────────────┘    │  │    │
│  │  │                                                           │  │    │
│  │  │  ┌─────────────────────────────────────────────────┐    │  │    │
│  │  │  │  Burst Pool (Min: 0, Max: 20)                   │    │  │    │
│  │  │  │  ┌────────┐  ┌────────┐  ┌────────┐            │    │  │    │
│  │  │  │  │Worker-B1│ │Worker-B2│ │Worker-B3│           │    │  │    │
│  │  │  │  │ Ready  │  │ Ready  │  │ Ready  │            │    │  │    │
│  │  │  │  │TTL: 4h │  │TTL: 4h │  │TTL: 4h │            │    │  │    │
│  │  │  │  └────────┘  └────────┘  └────────┘            │    │  │    │
│  │  │  │  [Taint: burst] [Auto-Terminate]                │    │  │    │
│  │  │  └─────────────────────────────────────────────────┘    │  │    │
│  │  │                                                           │  │    │
│  │  │  ┌─────────────────────────────────────────────────┐    │  │    │
│  │  │  │  Spot Pool (Min: 0, Max: 15)                    │    │  │    │
│  │  │  │  ┌────────┐  ┌────────┐                         │    │  │    │
│  │  │  │  │Worker-S1│ │Worker-S2│                        │    │  │    │
│  │  │  │  │ Ready  │  │ Ready  │                         │    │  │    │
│  │  │  │  │Preempt │  │Preempt │                         │    │  │    │
│  │  │  │  └────────┘  └────────┘                         │    │  │    │
│  │  │  │  [Taint: spot] [70% Cost Savings]                │    │  │    │
│  │  │  └─────────────────────────────────────────────────┘    │  │    │
│  │  │                                                           │  │    │
│  │  │  ┌─────────────────────────────────────────────────┐    │  │    │
│  │  │  │  GPU Pool (Min: 0, Max: 5)                      │    │  │    │
│  │  │  │  ┌────────┐                                      │    │  │    │
│  │  │  │  │Worker-G1│                                     │    │  │    │
│  │  │  │  │ Ready  │                                      │    │  │    │
│  │  │  │  │GPU: T4 │                                      │    │  │    │
│  │  │  │  └────────┘                                      │    │  │    │
│  │  │  │  [Taint: gpu] [PCIe Passthrough]                 │    │  │    │
│  │  │  └─────────────────────────────────────────────────┘    │  │    │
│  │  └──────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Worker Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     WORKER LIFECYCLE STATES                             │
└─────────────────────────────────────────────────────────────────────────┘

    Scaling Trigger
    (Pending Pods / CPU Pressure / Manual)
              │
              ▼
    ┌──────────────────┐
    │   REQUESTED      │ ─── Resource Manager receives scaling request
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  PROVISIONING    │ ─┬─ Clone VM from template (Proxmox)
    │                  │  ├─ Configure CPU/RAM/Disk
    │  (60-90s)        │  ├─ Attach to network (VLAN)
    │                  │  └─ Start VM
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │   JOINING        │ ─┬─ Generate Talos worker config
    │                  │  ├─ Apply config to node
    │  (90-120s)       │  ├─ Node joins cluster
    │                  │  └─ Wait for kubelet Ready
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │     READY        │ ─┬─ Node condition: Ready=True
    │                  │  ├─ Accepting pod scheduling
    │  (Active)        │  ├─ Health monitoring active
    │                  │  └─ Workloads running
    └────────┬─────────┘
             │
             │ (TTL Expiry / Manual Removal / Preemption)
             │
             ▼
    ┌──────────────────┐
    │   DRAINING       │ ─┬─ Cordon node (no new pods)
    │                  │  ├─ Evict existing pods
    │  (300s grace)    │  ├─ Respect PodDisruptionBudgets
    │                  │  └─ Wait for pod evacuation
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  TERMINATING     │ ─┬─ Delete node from Kubernetes
    │                  │  ├─ Shutdown Talos node
    │  (60-120s)       │  ├─ Delete VM from Proxmox
    │                  │  └─ Remove from inventory
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │   TERMINATED     │ ─── Worker fully removed
    └──────────────────┘
```

---

## Provisioning Workflow (Burst Worker)

```
┌─────────────────────────────────────────────────────────────────────────┐
│               BURST WORKER PROVISIONING SEQUENCE                        │
└─────────────────────────────────────────────────────────────────────────┘

Resource Manager                Proxmox MCP              Talos MCP
      │                              │                       │
      │                              │                       │
      │  1. Trigger: Pending Pods    │                       │
      │     (5+ pods, 120s)          │                       │
      │──────────────────────────────│                       │
      │                              │                       │
      │  2. clone_vm(template=9002)  │                       │
      │──────────────────────────────>                       │
      │                              │                       │
      │                              │  Clone VM (30-60s)    │
      │                              │  ┌─────────────┐      │
      │                              │  │ Cloning...  │      │
      │                              │  └─────────────┘      │
      │                              │                       │
      │  3. VM Cloned (VM-200)       │                       │
      │<──────────────────────────────│                       │
      │                              │                       │
      │  4. start_vm(vmid=200)       │                       │
      │──────────────────────────────>                       │
      │                              │                       │
      │                              │  Boot VM (30-60s)     │
      │                              │  ┌─────────────┐      │
      │                              │  │ Booting...  │      │
      │                              │  └─────────────┘      │
      │                              │                       │
      │  5. VM Running (IP: x.x.x.x) │                       │
      │<──────────────────────────────│                       │
      │                              │                       │
      │  6. generate_worker_config   │                       │
      │  (hostname, labels, taints)  │                       │
      │──────────────────────────────────────────────────────>
      │                              │                       │
      │                              │   Generate Config     │
      │                              │   ┌──────────────┐    │
      │                              │   │ worker.yaml  │    │
      │                              │   └──────────────┘    │
      │                              │                       │
      │  7. Worker Config Generated  │                       │
      │<──────────────────────────────────────────────────────│
      │                              │                       │
      │  8. apply_config(nodes=x.x.x.x)                      │
      │──────────────────────────────────────────────────────>
      │                              │                       │
      │                              │   Apply + Join (90s)  │
      │                              │   ┌──────────────┐    │
      │                              │   │ Joining...   │    │
      │                              │   └──────────────┘    │
      │                              │                       │
      │  9. Node Joined Cluster      │                       │
      │<──────────────────────────────────────────────────────│
      │                              │                       │
      │  10. kubectl label node      │                       │
      │  (node-pool=burst, ttl=...)  │                       │
      │                              │                       │
      │  11. Worker READY            │                       │
      │  ✓ Scheduling enabled        │                       │
      │  ✓ Health monitoring active  │                       │
      │  ✓ TTL cleanup scheduled     │                       │
      │                              │                       │
```

---

## TTL Cleanup Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TTL CLEANUP DAEMON WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

    Every 5 minutes:
    ┌──────────────────────────────┐
    │ Get all nodes with TTL label │
    └──────────┬───────────────────┘
               │
               ▼
    ┌──────────────────────────────┐
    │ For each worker:             │
    │  current_time > ttl?         │
    └──────────┬───────────────────┘
               │
         ┌─────┴─────┐
         │           │
        No          Yes
         │           │
         ▼           ▼
    ┌────────┐  ┌──────────────────────────┐
    │ Skip   │  │ Check if idle:           │
    │        │  │  - Pod count = 0?        │
    └────────┘  │  - CPU < 5%?             │
                └──────────┬───────────────┘
                           │
                     ┌─────┴─────┐
                     │           │
                    No          Yes
                     │           │
                     ▼           ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ Drain worker     │  │ Immediate removal│
         │ (300s grace)     │  │ (skip drain)     │
         └────────┬─────────┘  └────────┬─────────┘
                  │                     │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │ Cordon node        │
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ Drain pods         │
                  │ (if not idle)      │
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ Delete from K8s    │
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ Shutdown Talos     │
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ Delete VM (Proxmox)│
                  └────────┬───────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ Remove from        │
                  │ inventory          │
                  └────────────────────┘
```

---

## Auto-Repair Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AUTO-REPAIR DECISION FLOW                            │
└─────────────────────────────────────────────────────────────────────────┘

    Health Check (every 30s)
            │
            ▼
    ┌──────────────────┐
    │ Node condition?  │
    └────────┬─────────┘
             │
       ┌─────┴─────┬──────────┬──────────┬───────────┐
       │           │          │          │           │
       ▼           ▼          ▼          ▼           ▼
    Ready?    MemPress?  DiskPress? PIDPress? KubeletUp?
       │           │          │          │           │
      Yes          │          │          │          Yes
       │           │          │          │           │
       ▼           │          │          │           ▼
    ┌─────┐        │          │          │        ┌─────┐
    │ OK  │        │          │          │        │ OK  │
    └─────┘        │          │          │        └─────┘
                   │          │          │
                  Yes        Yes        Yes
                   │          │          │
                   ▼          ▼          ▼
              ┌─────────────────────────────┐
              │  Unhealthy Detected         │
              └─────────┬───────────────────┘
                        │
                        ▼
              ┌─────────────────────────────┐
              │  Duration > Threshold?      │
              └─────────┬───────────────────┘
                        │
                  ┌─────┴─────┐
                  │           │
                 No          Yes
                  │           │
                  ▼           ▼
              ┌─────┐   ┌──────────────────┐
              │Wait │   │ Select Repair    │
              └─────┘   │ Strategy         │
                        └────────┬─────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
          ┌──────────────┐ ┌──────────┐ ┌──────────────┐
          │ Level 1:     │ │ Level 2: │ │ Level 3:     │
          │ Restart      │ │ Reboot   │ │ Replace      │
          │ Service      │ │ Node     │ │ Node         │
          └──────┬───────┘ └────┬─────┘ └──────┬───────┘
                 │              │              │
                 │              │              │
                 └──────────────┼──────────────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │ Execute Repair    │
                      └─────────┬─────────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │ Wait for Recovery │
                      │ (60-300s)         │
                      └─────────┬─────────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │ Recheck Health    │
                      └─────────┬─────────┘
                                │
                          ┌─────┴─────┐
                          │           │
                      Healthy     Still Bad
                          │           │
                          ▼           ▼
                      ┌─────┐   ┌──────────┐
                      │ OK  │   │ Escalate │
                      └─────┘   │ to L2/L3 │
                                └──────────┘
```

---

## Scaling Trigger Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AUTO-SCALING TRIGGER LOGIC                          │
└─────────────────────────────────────────────────────────────────────────┘

    Monitor Metrics (every 30s)
            │
            ▼
    ┌──────────────────────────────────────┐
    │ Check Scaling Triggers:              │
    │  1. Pending pods count               │
    │  2. CPU utilization                  │
    │  3. Memory utilization               │
    │  4. Custom metrics                   │
    └──────────────┬───────────────────────┘
                   │
         ┌─────────┼─────────┬──────────────┐
         │         │         │              │
         ▼         ▼         ▼              ▼
    ┌─────────┐ ┌──────┐ ┌───────┐  ┌──────────┐
    │Pending  │ │CPU   │ │Memory │  │Custom    │
    │Pods ≥ 5?│ │≥ 80%?│ │≥ 85%? │  │Trigger?  │
    └────┬────┘ └──┬───┘ └───┬───┘  └─────┬────┘
         │         │         │            │
      ┌──┴─┐    ┌──┴─┐    ┌──┴─┐       ┌──┴─┐
      │Yes │    │Yes │    │Yes │       │Yes │
      └──┬─┘    └──┬─┘    └──┬─┘       └──┬─┘
         │         │         │            │
         └─────────┴─────────┴────────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │ Duration > Threshold?│
         │ (120s for pods)      │
         │ (300s for metrics)   │
         └──────────┬───────────┘
                    │
              ┌─────┴─────┐
              │           │
             No          Yes
              │           │
              ▼           ▼
          ┌─────┐   ┌──────────────────┐
          │Wait │   │ Calculate        │
          └─────┘   │ Workers Needed   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Pool Limit OK?   │
                    │ (current < max)  │
                    └────────┬─────────┘
                             │
                       ┌─────┴─────┐
                       │           │
                      No          Yes
                       │           │
                       ▼           ▼
                  ┌────────┐  ┌──────────────┐
                  │ Alert: │  │ Provision    │
                  │ At Max │  │ Workers      │
                  │ Capacity│  └──────┬───────┘
                  └────────┘         │
                                     ▼
                            ┌──────────────────┐
                            │ Select Template  │
                            │ (small/med/large)│
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ Start Provisioning│
                            │ Workflow         │
                            └──────────────────┘
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW OVERVIEW                               │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ Kubernetes   │
│ Metrics      │────┐
└──────────────┘    │
                    │
┌──────────────┐    │     ┌─────────────────────────────────┐
│ Prometheus   │    │     │   Resource Manager              │
│ Monitoring   │────┼────>│   - Scaling decisions           │
└──────────────┘    │     │   - Pool orchestration          │
                    │     │   - Health monitoring           │
┌──────────────┐    │     │   - Cost tracking               │
│ Pending Pods │────┘     └────────┬─────────────┬──────────┘
│ Count        │                   │             │
└──────────────┘                   │             │
                                   │             │
                        ┌──────────▼──────┐ ┌────▼────────────┐
                        │ Proxmox MCP     │ │ Talos MCP       │
                        │ - clone_vm      │ │ - apply_config  │
                        │ - start_vm      │ │ - health        │
                        │ - delete_vm     │ │ - upgrade       │
                        └────────┬────────┘ └────┬────────────┘
                                 │               │
                        ┌────────▼───────────────▼────────┐
                        │  Kubernetes Cluster             │
                        │  - Worker nodes join/leave      │
                        │  - Pods scheduled               │
                        │  - Workloads run                │
                        └────────┬────────────────────────┘
                                 │
                        ┌────────▼────────────────────────┐
                        │  Metrics & Events Flow Back     │
                        │  - Node status                  │
                        │  - Resource utilization         │
                        │  - Pod events                   │
                        └─────────────────────────────────┘
```

---

## Component Interaction Matrix

| Component | Proxmox MCP | Talos MCP | Kubernetes | Resource Mgr |
|-----------|-------------|-----------|------------|--------------|
| **Proxmox MCP** | - | Config exchange | - | VM status |
| **Talos MCP** | VM IP | - | Join/Leave | Health data |
| **Kubernetes** | - | Node ops | - | Metrics |
| **Resource Mgr** | Provision | Config apply | Monitor | - |

---

## State Transitions

```
Worker Pool States:
  IDLE (0 workers) → PROVISIONING → ACTIVE → SCALING_UP → ACTIVE
                                    ↕
                                SCALING_DOWN
                                    ↓
                                  IDLE

Worker States:
  REQUESTED → PROVISIONING → JOINING → READY → DRAINING → TERMINATED
                ↓              ↓         ↓
              FAILED       FAILED    UNHEALTHY
                                        ↓
                                    REPAIRING
```

---

**Maintained By**: Resource Manager
**Last Updated**: 2025-12-09
