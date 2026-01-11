# Cortex Intelligent Orchestrator - MCP Server

**Purpose**: Advanced pod lifecycle management with adaptive throttling, self-healing, and dynamic capacity planning for Cortex's 100+ agent workloads.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cortex Agent Request                         │
│                  "Spawn 50 security-master agents"              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              MCP Cortex Orchestrator Server                     │
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                │
│  │  Dynamic Limiter   │  │  Spawn Modulator   │                │
│  │  "Do we have       │  │  "How fast can     │                │
│  │   room?"           │  │   we spawn?"       │                │
│  └─────────┬──────────┘  └──────────┬─────────┘                │
│            │                        │                            │
│            └────────────┬───────────┘                            │
│                         │                                        │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │    Spawn Queue       │                           │
│              │  (Priority-based)    │                           │
│              └──────────┬───────────┘                           │
│                         │                                        │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │   Pod Lifecycle      │                           │
│              │   Manager            │                           │
│              └──────────┬───────────┘                           │
│                         │                                        │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │  Stuck Pod Detector  │ ◄──┐                      │
│              │  (Continuous Watch)  │    │                      │
│              └──────────┬───────────┘    │                      │
│                         │                │                      │
│                  STUCK? │                │                      │
│                    ┌────┴────┐           │                      │
│                   YES        NO           │                      │
│                    │         │            │                      │
│                    ▼         └────────────┘                      │
│              ┌──────────────────────┐                           │
│              │   Pod Swapper        │                           │
│              │   (Self-Healing)     │                           │
│              └──────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    ┌───────────────┐         ┌─────────────────┐
    │ k3s Cluster   │         │ cortex-awareness│
    │ - Pod API     │         │ - Capacity      │
    │ - Events      │         │ - Metrics       │
    └───────────────┘         └─────────────────┘
```

## Core Components

### 1. Dynamic Pod Limiter
**File**: `server/dynamic_limiter.py`

Calculates pod limits based on **actual cluster capacity**, not arbitrary caps.

**Key Features**:
- Calculates limits per resource (CPU, memory)
- Reserves 30% headroom for system + burst
- Adjusts for stability (reduces limit during instability)
- Per-agent-type resource profiling

**MCP Tools**:
- `calculate_current_limit()` - Get dynamic pod limit
- `should_allow_spawn(agent_type)` - Check if spawn is allowed
- `get_resource_profiles()` - Return agent resource requirements

**Example**:
```python
limit = await orchestrator.calculate_current_limit()
# {
#   "current_count": 87,
#   "calculated_limit": 142,
#   "limiting_resource": "memory",
#   "headroom": 55,
#   "can_scale_up": true,
#   "recommendation": "Healthy utilization. Monitor for growth."
# }
```

### 2. Spawn Modulator (Adaptive Throttling)
**File**: `server/spawn_modulator.py`

Prevents "thundering herd" by dynamically adjusting spawn rate based on cluster health.

**Backpressure Signals**:
- CPU headroom (scales with available CPU %)
- Pending pod pressure (slows if >50 pending)
- Recent spawn failure rate
- API server latency (throttles if slow)

**MCP Tools**:
- `calculate_spawn_rate()` - Current pods/second rate
- `request_spawn(agent_spec)` - Gate spawn through modulator
- `get_backpressure_status()` - Show active backpressure signals
- `get_queue_depth()` - Pending spawn requests

**Example**:
```python
decision = await orchestrator.request_spawn({
    "type": "security-master",
    "task_id": "audit-123",
    "priority": "high"
})
# {
#   "approved": true,
#   "estimated_spawn_time": 3.2,  # seconds
#   "current_rate": 8.4,           # pods/sec
#   "queue_position": 12
# }
```

**Adaptive Behavior**:
| Condition | Base Rate (10/s) → Modulated Rate |
|-----------|-----------------------------------|
| CPU 50%, no pending, no failures | 10.0 pods/s (100%) |
| CPU 20%, 30 pending, 2 failures | 10 × 0.67 × 0.4 × 0.7 = 1.9 pods/s |
| CPU 80%, 0 pending, 0 failures | 10 × 1.0 × 1.0 × 1.0 = 10.0 pods/s |
| API latency >500ms | ×0.5 (halved) |

### 3. Stuck Pod Detector + Swapper
**File**: `server/stuck_detector.py`, `server/pod_swapper.py`

Detects pods that are not crashing but also not making progress (zombie pods).

**Detection Signals** (weighted scoring):
- k8s Ready probe (20%)
- Recent log output (20%)
- CPU activity >1m (15%)
- Network activity (15%)
- **Task progress** (30%) - most important for agents

**Stuck Threshold**: Score < 0.4

**MCP Tools**:
- `check_pod_liveness(pod_name)` - Get liveness score
- `evaluate_and_swap(pod_name)` - Swap if stuck
- `get_stuck_pods()` - List all stuck pods
- `get_swap_history()` - Recent swap events

**Self-Healing Flow**:
1. Detect stuck pod (score < 0.4 for >5 minutes)
2. Check swap history (prevent swap loops)
3. Capture agent state (checkpoint if possible)
4. Request replacement spawn (through modulator)
5. Delete stuck pod (grace period: 10s)
6. New pod inherits state

**Example**:
```python
liveness = await orchestrator.check_pod_liveness("agent-code-xyz")
# {
#   "pod_name": "agent-code-xyz",
#   "score": 0.35,
#   "stuck": true,
#   "stuck_duration": 320,  # seconds
#   "signals": {
#     "k8s_ready": true,
#     "recent_logs": false,     # <-- red flag
#     "cpu_activity": false,     # <-- red flag
#     "network_activity": false,
#     "task_progress": false     # <-- red flag (no progress)
#   }
# }

result = await orchestrator.evaluate_and_swap("agent-code-xyz")
# {
#   "swapped": true,
#   "original_pod": "agent-code-xyz",
#   "stuck_duration": 320,
#   "state_preserved": true,
#   "replacement_pod": "agent-code-abc"
# }
```

---

## MCP Tools Exposed

### Orchestration Control
1. `spawn_agent(agent_spec)` - Spawn with intelligent throttling
2. `get_orchestration_status()` - Overall system health
3. `pause_spawning(reason)` - Emergency brake
4. `resume_spawning()` - Resume after pause

### Capacity Management
5. `calculate_current_limit()` - Dynamic pod limit
6. `should_allow_spawn(agent_type)` - Pre-flight check
7. `get_resource_profiles()` - Agent resource requirements
8. `set_resource_profile(agent_type, cpu, memory)` - Update profiles

### Spawn Modulation
9. `calculate_spawn_rate()` - Current throttle rate
10. `request_spawn(agent_spec)` - Queue spawn request
11. `get_backpressure_status()` - Active throttle signals
12. `get_queue_depth()` - Pending requests

### Self-Healing
13. `check_pod_liveness(pod_name)` - Multi-signal liveness
14. `evaluate_and_swap(pod_name)` - Swap stuck pod
15. `get_stuck_pods()` - List zombies
16. `get_swap_history(minutes)` - Recent swaps
17. `force_swap(pod_name, reason)` - Manual intervention

### Monitoring
18. `get_agent_distribution()` - Agents per node
19. `get_spawn_statistics(hours)` - Spawn success rate
20. `get_stability_metrics()` - System stability score

---

## Integration with cortex-awareness

The orchestrator **depends on** cortex-awareness for cluster state:

```python
# server/orchestrator.py
class CortexOrchestrator:
    def __init__(self, awareness_client: AwarenessClient):
        self.awareness = awareness_client

        self.limiter = DynamicPodLimiter(awareness_client)
        self.modulator = SpawnModulator(awareness_client)
        self.detector = StuckPodDetector(awareness_client)
        self.swapper = PodSwapper(self.detector, self.modulator)
```

**Data Flow**:
1. Orchestrator asks awareness: "What's cluster capacity?"
2. Awareness queries k8s metrics, returns CPU/memory state
3. Orchestrator calculates: "Can spawn 55 more agents"
4. commit-relay MoE asks: "Should I spawn security-master?"
5. Orchestrator checks limit → modulator → returns decision

---

## Integration with commit-relay

### Before (Naive Spawning)
```python
# Old approach - no intelligence
for task in tasks:
    agent_type = select_agent(task)
    pod = create_pod(agent_type, task)  # Hope it works!
```

### After (Intelligent Orchestration)
```python
# New approach - orchestrator-aware
async def spawn_agent_for_task(task: Task) -> AgentHandle:
    agent_type = moe_router.select_agent_type(task)

    # Check with orchestrator
    decision = await orchestrator_mcp.call_tool("spawn_agent", {
        "agent_type": agent_type,
        "task_id": task.id,
        "priority": task.priority,
        "estimated_duration": task.estimated_duration,
    })

    if decision["status"] == "queued":
        # Orchestrator says "not yet"
        logger.info(f"Task {task.id} queued: {decision['reason']}")
        return await wait_for_spawn(decision["queue_position"])

    if decision["status"] == "throttled":
        # Spawn rate limited
        await asyncio.sleep(decision["retry_after"])
        return await spawn_agent_for_task(task)  # Retry

    # Spawn approved
    agent = await create_agent_pod(
        agent_type=agent_type,
        task=task,
        node_affinity=decision.get("recommended_node")
    )

    return agent
```

### Continuous Monitoring
```python
# Background task in commit-relay
async def monitor_agents():
    while True:
        await asyncio.sleep(60)

        # Get stuck pods from orchestrator
        stuck = await orchestrator_mcp.call_tool("get_stuck_pods")

        for pod in stuck:
            logger.warning(f"Agent {pod['name']} stuck: {pod['signals']}")

            # Orchestrator auto-swaps if >5min stuck
            # We just log for observability
```

---

## Deployment

### Prerequisites
- cortex-awareness MCP server running
- Prometheus/metrics-server for resource metrics
- k8s 1.24+ with metrics API

### RBAC Requirements
```yaml
rules:
  # Read cluster capacity
  - apiGroups: [""]
    resources: ["nodes", "pods"]
    verbs: ["get", "list", "watch"]

  # Pod lifecycle management
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["create", "delete"]

  # Read metrics
  - apiGroups: ["metrics.k8s.io"]
    resources: ["nodes", "pods"]
    verbs: ["get", "list"]

  # Agent state (commit-relay)
  - apiGroups: ["cortex.ai"]
    resources: ["agents"]
    verbs: ["get", "list", "update"]
```

### Resource Requirements
- CPU: 200m request, 1000m limit (needs headroom for spawn bursts)
- Memory: 256Mi request, 1Gi limit (maintains queue + history)
- Storage: None (stateless)

### Configuration
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cortex-orchestrator-config
  namespace: cortex
data:
  config.yaml: |
    # Spawn Modulation
    base_spawn_rate: 10  # pods/second
    max_pending_queue: 100

    # Dynamic Limits
    cpu_headroom_percent: 30
    memory_headroom_percent: 30
    absolute_max_pods: 500

    # Stuck Detection
    liveness_check_interval: 60  # seconds
    stuck_threshold: 0.4         # score
    stuck_timeout: 300           # 5 minutes
    max_swap_retries: 2

    # Resource Profiles
    agent_profiles:
      code_agent:
        cpu: 250    # millicores
        memory: 512 # Mi
      review_agent:
        cpu: 100
        memory: 256
      test_agent:
        cpu: 500
        memory: 1024
      security_master:
        cpu: 200
        memory: 384
      coordinator_master:
        cpu: 100
        memory: 128
```

---

## Observability

### Metrics (Prometheus)
```python
# Exposed at /metrics
cortex_orchestrator_active_agents{type="code_agent"} 42
cortex_orchestrator_spawn_rate_current 8.4
cortex_orchestrator_spawn_queue_depth 12
cortex_orchestrator_stuck_pods 2
cortex_orchestrator_swaps_total{outcome="success"} 127
cortex_orchestrator_spawn_rejections_total{reason="at_limit"} 3
cortex_orchestrator_backpressure_factor{signal="cpu_headroom"} 0.67
```

### Logs (Structured JSON)
```json
{
  "level": "info",
  "timestamp": "2026-01-10T19:00:00Z",
  "component": "spawn_modulator",
  "event": "rate_adjusted",
  "old_rate": 10.0,
  "new_rate": 8.4,
  "factors": {
    "cpu_headroom": 0.67,
    "pending_pressure": 0.75,
    "failure_rate": 1.0,
    "api_latency": 1.0
  }
}
```

### Elastic Integration
```python
# Ship orchestration events to Elastic
await elastic.index(
    index="cortex-orchestration",
    document={
        "timestamp": datetime.utcnow(),
        "event_type": "spawn_throttled",
        "agent_type": "code_agent",
        "task_id": "task-123",
        "reason": "pending_pressure",
        "backpressure_factors": {...},
        "queue_depth": 42,
    }
)
```

---

## Real-World Scenarios

### Scenario 1: Burst Workload (50 agents needed immediately)
```
1. commit-relay: "Spawn 50 code_agent for PR review"
2. Orchestrator checks limit: 142 total allowed, 87 current = 55 headroom ✅
3. Modulator calculates rate: 8.4 pods/sec
4. Orchestrator: "Spawning at 8.4/s, will take ~6 seconds"
5. Spawn queue processes 50 requests smoothly
6. All 50 agents spawn within 7 seconds
7. Cluster now at 137/142 (96% utilization)
```

### Scenario 2: Cluster Under Pressure
```
1. Cluster CPU: 15% available (low headroom)
2. Limiter calculates new limit: 95 pods (down from 142)
3. Current agents: 137 (OVER limit!)
4. Orchestrator: Reject new spawns with "at_dynamic_limit"
5. Detector finds 8 stuck pods
6. Swapper recycles stuck pods → frees capacity
7. New spawns can proceed as stuck pods clear
```

### Scenario 3: Stuck Agent Detection
```
1. Agent "code-xyz" running for 15 minutes
2. Task should complete in 5 minutes
3. Detector checks every 60s:
   - k8s Ready: ✅ true (0.2 points)
   - Recent logs: ❌ false (0 points - last log 8min ago)
   - CPU activity: ❌ false (0 points - <1m CPU)
   - Network: ❌ false (0 points)
   - Task progress: ❌ false (0 points - no commits)
   - Score: 0.2 (STUCK!)
4. Stuck for 8 minutes (>5min threshold)
5. Swapper captures state (if possible)
6. Swapper deletes stuck pod
7. Modulator spawns replacement with inherited state
8. New agent completes task successfully
```

---

## Testing Strategy

### Unit Tests
- `tests/test_dynamic_limiter.py` - Limit calculations
- `tests/test_spawn_modulator.py` - Backpressure factors
- `tests/test_stuck_detector.py` - Liveness scoring
- `tests/test_pod_swapper.py` - Swap logic

### Integration Tests
- Simulate 100 concurrent spawn requests
- Test stuck pod detection with sleeping containers
- Verify swap preserves agent state
- Test backpressure under synthetic load

### Load Tests
- Spawn 200 agents at max rate
- Verify no cascading failures
- Check API server latency impact
- Measure memory footprint during peak

---

## Files Structure

```
mcp-servers/cortex-orchestrator/
├── README.md                    # This file
├── server/
│   ├── __init__.py
│   ├── orchestrator.py          # Main MCP server
│   ├── dynamic_limiter.py       # Capacity-based limits
│   ├── spawn_modulator.py       # Adaptive throttling
│   ├── stuck_detector.py        # Multi-signal liveness
│   ├── pod_swapper.py           # Self-healing swaps
│   ├── spawn_queue.py           # Priority queue
│   └── models.py                # Data models
├── k8s/
│   ├── deployment.yaml          # Orchestrator deployment
│   ├── rbac.yaml                # ServiceAccount + RBAC
│   ├── configmap.yaml           # Configuration
│   └── service.yaml             # MCP service
├── tests/
│   ├── test_orchestrator.py
│   ├── test_dynamic_limiter.py
│   ├── test_spawn_modulator.py
│   ├── test_stuck_detector.py
│   └── test_integration.py
├── Dockerfile
├── pyproject.toml
└── docker-compose.yml           # Local dev
```

---

## Success Metrics

### Performance
- **Spawn latency p95**: < 2 seconds (gate decision)
- **Swap detection latency**: < 90 seconds (from stuck to swapped)
- **Memory footprint**: < 512MB with 200 agents tracked

### Reliability
- **Spawn success rate**: > 98%
- **False positive swaps**: < 2% (swapping healthy pods)
- **Queue starvation**: 0 (all requests eventually processed)

### Efficiency
- **Cluster utilization**: 80-90% (no wasted capacity)
- **Agent task completion rate**: > 95%
- **Swap frequency**: < 1 per 100 agent-hours (low churn)

---

## Status

**Current**: Design complete, ready for implementation
**Dependencies**: cortex-awareness MCP server
**Target Integration**: commit-relay MoE router, cortex-chat orchestration queries

**Next**: Implement Phase 1 (Dynamic Limiter + Spawn Modulator)
