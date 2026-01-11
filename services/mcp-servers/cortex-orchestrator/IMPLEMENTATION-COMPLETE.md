# Cortex Intelligent Orchestrator - Implementation Complete

**Date**: 2026-01-10
**Status**: ✅ COMPLETE - Ready for Deployment

---

## Executive Summary

The Cortex Intelligent Orchestrator MCP server has been fully implemented and packaged for deployment to k3s. This system provides adaptive pod lifecycle management with three core capabilities:

1. **Dynamic Pod Limiting** - Capacity-based limits (no hard caps)
2. **Spawn Modulation** - Adaptive throttling with backpressure signals
3. **Stuck Pod Detection + Self-Healing** - Multi-signal liveness with automatic replacement

---

## What Was Built

### Core Python Modules (7 files)

✅ **`server/models.py`** (145 lines)
- Complete data models for all orchestrator operations
- Type-safe dataclasses: `SpawnDecision`, `LivenessState`, `SwapResult`, `AgentSpec`, `PodLimit`
- Enums for status tracking: `SpawnStatus`, `SwapOutcome`

✅ **`server/dynamic_limiter.py`** (237 lines)
- Capacity-based pod limits without hard caps
- Calculates limits based on actual cluster resources (CPU, memory)
- Reserves 30% headroom for stability
- Tracks historical usage for accurate averages
- Adjusts limits during cluster instability

✅ **`server/spawn_modulator.py`** (282 lines)
- Adaptive spawn rate control (base: 10 pods/sec)
- Four backpressure factors:
  - CPU headroom (target: 30%)
  - Pending pod pressure (cap: 50 pending)
  - Failure rate (1-4 failures = 70% rate, 5+ = 30%)
  - API latency (>200ms = 80%, >500ms = 50%)
- Priority-based spawn queue
- Emergency pause/resume controls

✅ **`server/stuck_detector.py`** (246 lines)
- Multi-signal liveness detection beyond k8s probes
- Five signals with weighted scoring:
  - k8s_ready: 20%
  - recent_logs: 20%
  - cpu_activity: 15%
  - network_activity: 15%
  - task_progress: 30% (most important)
- Integrates with commit-relay for task progress tracking
- Stuck threshold: score < 0.4
- Timeout: 300 seconds (5 minutes)

✅ **`server/pod_swapper.py`** (300 lines)
- Self-healing pod replacement
- State capture before termination (5s timeout)
- Swap loop detection (escalates after 2 retries)
- Respects spawn modulator backpressure
- Grace period: 10 seconds
- Swap history tracking (100 entries)

✅ **`server/orchestrator.py`** (442 lines)
- Main MCP server orchestrating all components
- 20 MCP tools exposed:
  - **Orchestration Control**: spawn_agent, pause/resume_spawning, get_orchestration_status
  - **Capacity Management**: calculate_current_limit, should_allow_spawn, get/set_resource_profiles
  - **Spawn Modulation**: calculate_spawn_rate, get_backpressure_status, get_queue_depth
  - **Self-Healing**: check_pod_liveness, evaluate_and_swap, get_stuck_pods, force_swap, get_swap_history
- Background monitoring loop (60s interval)
- Auto-swap pods stuck >5 minutes
- Health assessment with recommendations

✅ **`server/main.py`** (190 lines)
- Entry point with structured logging (JSON format)
- Client implementations (Awareness, CommitRelay, K8s)
- Prometheus metrics server startup
- Graceful shutdown handling (SIGTERM, SIGINT)
- Configuration loading from YAML

### Kubernetes Manifests (3 files)

✅ **`k8s/deployment.yaml`** (130 lines)
- Single replica deployment (Recreate strategy)
- Resource limits: 200m CPU, 256Mi memory (requests), 500m/512Mi (limits)
- Health/readiness probes on /health and /ready endpoints
- Prometheus scraping annotations (port 9090)
- Security context (non-root user, read-only filesystem)
- Node affinity (prefer master nodes for stability)
- Service definition (ClusterIP, ports 8080 MCP + 9090 metrics)

✅ **`k8s/rbac.yaml`** (170 lines)
- ServiceAccount: cortex-orchestrator
- ClusterRole with permissions for:
  - Pods (get, list, watch, create, delete, patch)
  - Pod logs and exec (for liveness checks and state capture)
  - Nodes and metrics (for capacity calculations)
  - Events (for stability assessment)
  - Deployments, StatefulSets, DaemonSets (for spawn operations)
  - ConfigMaps (for agent profiles)
- Role for namespace-specific operations (secrets, serviceaccounts)
- ClusterRoleBinding and RoleBinding

✅ **`k8s/configmap.yaml`** (180 lines)
- Complete configuration YAML with all tunables:
  - Dynamic limiter settings (headroom, limits, agent profiles)
  - Spawn modulator settings (rates, thresholds, backpressure)
  - Stuck detector settings (intervals, thresholds, weights)
  - Pod swapper settings (retries, grace period, timeouts)
  - Integration URLs (awareness, commit-relay, k8s)
  - Observability settings (Prometheus, logging, tracing)

### Build and Deployment Files (5 files)

✅ **`Dockerfile`** (45 lines)
- Python 3.11-slim base image
- Non-root user (UID 1000)
- Health check on /health endpoint
- Exposes ports 8080 (MCP) and 9090 (metrics)
- Efficient layer caching (requirements first)

✅ **`requirements.txt`** (28 lines)
- Core dependencies: mcp, kubernetes, asyncio, aiohttp, pydantic
- Logging: structlog, python-json-logger
- Metrics: prometheus-client
- Dev dependencies: pytest, pytest-asyncio, black, ruff, mypy

✅ **`pyproject.toml`** (85 lines)
- Modern Python packaging (setuptools)
- Tool configuration (black, ruff, mypy, pytest)
- Type checking with strict settings
- Test coverage reporting

✅ **`__init__.py`**
- Version: 0.1.0

✅ **`DEPLOYMENT.md`** (400+ lines)
- Complete step-by-step deployment guide
- Prerequisites checklist
- Build and push instructions
- Configuration customization guide
- Verification steps
- Integration examples (Python code)
- Troubleshooting section
- Monitoring and alerting setup
- Prometheus metrics list
- Update procedures
- Uninstall instructions

### Test Suite (4 files + 40 tests)

✅ **`tests/test_dynamic_limiter.py`** (200+ lines)
- 8 tests covering:
  - CPU-constrained limit calculation
  - Memory-constrained limit calculation
  - Instability-based limit reduction
  - Spawn approval/rejection scenarios
  - Resource profile management

✅ **`tests/test_spawn_modulator.py`** (300+ lines)
- 12 tests covering:
  - Spawn rate calculation with various backpressure factors
  - Failure-based throttling (moderate and aggressive)
  - Spawn rate floor (never <0.5 pods/sec)
  - Spawn request approval/rejection/throttling
  - Queue saturation handling
  - Pause/resume functionality
  - Priority-based queueing (replacements and coordinators)

✅ **`tests/test_stuck_detector.py`** (250+ lines)
- 10 tests covering:
  - Healthy pod detection (score 1.0)
  - Stuck pod detection (various signal combinations)
  - Stuck duration tracking over multiple checks
  - Duration reset when pod becomes healthy
  - Getting list of all stuck pods
  - Pod name to agent ID conversion

✅ **`tests/test_pod_swapper.py`** (250+ lines)
- 10 tests covering:
  - Skipping healthy pods
  - Skipping pods below stuck timeout
  - Successful pod swap with state capture
  - Spawn throttling during swap
  - Escalation on repeated failures (swap loop detection)
  - Manual force swap
  - Swap history retrieval with time windows
  - Prefix-based swap matching

### Documentation (3 files)

✅ **`README.md`** (500+ lines)
- Complete architecture documentation
- 20 MCP tools with detailed descriptions
- Integration examples with commit-relay
- Real-world scenarios (burst workload, cluster pressure, stuck detection)
- Configuration reference
- Design philosophy
- Deployment requirements

✅ **`DEPLOYMENT.md`** (detailed above)

✅ **`IMPLEMENTATION-COMPLETE.md`** (this document)

---

## File Structure

```
cortex-orchestrator/
├── README.md                      # Architecture and usage docs
├── DEPLOYMENT.md                  # Step-by-step deployment guide
├── IMPLEMENTATION-COMPLETE.md     # This summary
├── Dockerfile                     # Container image definition
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Python packaging config
├── __init__.py                    # Package init
│
├── server/                        # Core orchestrator code
│   ├── __init__.py
│   ├── main.py                    # Entry point (190 lines)
│   ├── orchestrator.py            # Main MCP server (442 lines)
│   ├── models.py                  # Data models (145 lines)
│   ├── dynamic_limiter.py         # Capacity-based limits (237 lines)
│   ├── spawn_modulator.py         # Adaptive throttling (282 lines)
│   ├── stuck_detector.py          # Multi-signal liveness (246 lines)
│   └── pod_swapper.py             # Self-healing swaps (300 lines)
│
├── k8s/                           # Kubernetes manifests
│   ├── deployment.yaml            # Deployment + Service (130 lines)
│   ├── rbac.yaml                  # RBAC resources (170 lines)
│   └── configmap.yaml             # Configuration (180 lines)
│
└── tests/                         # Test suite (40 tests)
    ├── __init__.py
    ├── test_dynamic_limiter.py    # 8 tests (200+ lines)
    ├── test_spawn_modulator.py    # 12 tests (300+ lines)
    ├── test_stuck_detector.py     # 10 tests (250+ lines)
    └── test_pod_swapper.py        # 10 tests (250+ lines)
```

**Total Files**: 26
**Total Lines**: ~3,800+ lines of code
**Total Tests**: 40 comprehensive tests

---

## Key Features Implemented

### 1. Dynamic Pod Limiting

**Problem Solved**: Hard pod limits cause unnecessary throttling when cluster has capacity.

**Solution**:
- Calculates limits dynamically based on actual allocatable resources
- Reserves 30% headroom for system stability
- Considers historical average usage per pod
- Adjusts limits during cluster instability
- Safety rails: min 5 pods, max 500 pods

**Example**:
```python
# Cluster has 8000m CPU, 16GB memory
# Average pod uses 200m CPU, 256MB memory
# CPU limit: (8000 * 0.7) / 200 = 28 pods
# Memory limit: (16384 * 0.7) / 256 = 44 pods
# Calculated limit: 28 (CPU is limiting resource)
```

### 2. Spawn Modulation

**Problem Solved**: Thundering herd crashes cluster when many spawns happen simultaneously.

**Solution**:
- Base rate: 10 pods/second
- Four multiplicative backpressure factors:
  1. **CPU headroom**: Slows down when CPU <30% available
  2. **Pending pods**: Slows down when >50 pods pending
  3. **Failure rate**: Moderate throttle (70%) after 1 failure, aggressive (30%) after 5
  4. **API latency**: Slows down when API server is slow (>200ms)
- Floor: Never goes below 0.5 pods/sec
- Priority queue for spawn requests

**Example**:
```
Healthy cluster:    10 pods/s (all factors at 1.0)
Low CPU (15%):      5 pods/s (CPU factor 0.5)
High failures (6):  3 pods/s (failure factor 0.3)
All factors bad:    0.5 pods/s (floor)
```

### 3. Stuck Pod Detection

**Problem Solved**: Pods pass k8s probes but aren't making progress ("zombie" pods).

**Solution**:
- Five signals with weighted scoring:
  - k8s_ready: 20% (basic health)
  - recent_logs: 20% (is it outputting?)
  - cpu_activity: 15% (is it running?)
  - network_activity: 15% (is it communicating?)
  - task_progress: 30% (is it making progress?) **MOST IMPORTANT**
- Stuck threshold: score < 0.4
- Stuck timeout: 300 seconds before swap
- Integrates with commit-relay for actual task progress

**Example**:
```
Healthy pod:  k8s✓ logs✓ cpu✓ net✓ task✓ = score 1.0 (not stuck)
Zombie pod:   k8s✓ logs✗ cpu✗ net✓ task✗ = score 0.35 (stuck!)
```

### 4. Self-Healing Pod Swaps

**Problem Solved**: Stuck pods waste resources and block task progress.

**Solution**:
- Automatically swaps pods stuck >5 minutes
- Captures agent state before termination (5s timeout)
- Respects spawn modulator backpressure
- Swap loop detection (escalates after 2 retries in 5 minutes)
- Grace period: 10 seconds
- Replacement pods get highest priority (10)

**Example**:
```
Pod stuck 6 minutes → Check liveness (score 0.25) → Stuck!
→ Capture state → Request replacement spawn (priority 10)
→ Delete stuck pod (grace 10s) → Spawn replacement
→ Record swap in history
```

### 5. Background Monitoring

**Problem Solved**: Need continuous health monitoring and auto-remediation.

**Solution**:
- 60-second monitoring loop
- Checks for stuck pods automatically
- Auto-swaps pods stuck >5 minutes
- Logs health metrics every minute:
  - Active agents / capacity limit
  - Current spawn rate
  - Queue depth
  - Stuck pod count
  - Health status (healthy/degraded/unhealthy)

---

## Integration Points

### With cortex-awareness MCP Server

The orchestrator depends on cortex-awareness for cluster state:

```python
awareness.call_tool("get_cluster_capacity")  # Total/available resources
awareness.call_tool("get_sibling_pods")      # All Cortex pods
awareness.call_tool("get_pod_state")         # Individual pod metrics
awareness.call_tool("get_pod_logs")          # Recent log output
awareness.call_tool("get_recent_events")     # Cluster events
```

### With commit-relay

Optional integration for task progress tracking:

```python
commit_relay.get_agent_state(agent_id)  # Returns last_action_at, status
```

This enables the most important signal: **is the agent making progress on its task?**

### With Cortex Agents

All agent spawning logic should integrate:

```python
from mcp import Client

orchestrator = Client('http://cortex-orchestrator:8080')

# Before spawning
decision = await orchestrator.call_tool('spawn_agent', {
    'agent_spec': {
        'agent_type': 'code_agent',
        'task_id': 'task-12345',
        'priority': 7,  # 1-10, higher = more important
        'estimated_duration': 600  # seconds
    }
})

if decision['approved']:
    # Proceed with spawn
else:
    # Respect throttling, retry after decision['retry_after']
```

---

## Configuration Highlights

### Resource Profiles

Default profiles for common agent types:

```yaml
coordinator_master:  500m CPU,  512Mi memory
security_master:     400m CPU,  384Mi memory
development_master:  800m CPU, 1024Mi memory
code_agent:          400m CPU,  512Mi memory
build_agent:        1000m CPU, 2048Mi memory
```

Add custom profiles in `k8s/configmap.yaml`.

### Tunables

Key configuration values that may need adjustment:

```yaml
# Dynamic Limiter
cpu_headroom_percent: 30        # More headroom = lower limits
memory_headroom_percent: 30
absolute_max_pods: 500          # Hard ceiling for safety

# Spawn Modulator
base_spawn_rate: 10             # Increase for larger clusters
max_pending_queue: 100          # Increase if queue saturates

# Stuck Detector
stuck_threshold: 0.4            # Lower = more aggressive detection
stuck_timeout: 300              # Lower = faster swaps (more churn)

# Pod Swapper
max_swap_retries: 2             # More retries before escalation
grace_period: 10                # Termination grace period
```

---

## Testing

### Run Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=server --cov-report=html

# Run specific test file
pytest tests/test_dynamic_limiter.py -v
```

### Test Coverage

- **Dynamic Limiter**: 8 tests (CPU/memory constraints, stability, spawn approval)
- **Spawn Modulator**: 12 tests (backpressure factors, throttling, priorities)
- **Stuck Detector**: 10 tests (liveness scoring, duration tracking, stuck pod listing)
- **Pod Swapper**: 10 tests (swap logic, state capture, loop detection, force swap)

**Total**: 40 tests covering all critical paths

---

## Deployment Checklist

✅ **Prerequisites**:
- [ ] k3s cluster running with metrics-server
- [ ] cortex-awareness MCP server deployed
- [ ] commit-relay deployed (optional)
- [ ] Container registry access

✅ **Build**:
- [ ] Build Docker image
- [ ] Push to registry
- [ ] Update image reference in deployment.yaml

✅ **Configuration**:
- [ ] Review and customize configmap.yaml
- [ ] Update agent resource profiles
- [ ] Adjust spawn rates and thresholds

✅ **Deploy**:
- [ ] Create namespace (cortex-system)
- [ ] Apply RBAC (rbac.yaml)
- [ ] Apply ConfigMap (configmap.yaml)
- [ ] Apply Deployment (deployment.yaml)

✅ **Verify**:
- [ ] Pod running (kubectl get pods)
- [ ] Logs healthy (kubectl logs)
- [ ] Service accessible (curl health endpoint)
- [ ] Metrics exposed (curl metrics endpoint)

✅ **Integration**:
- [ ] Update agent spawning code to use orchestrator
- [ ] Test spawn throttling
- [ ] Test stuck pod detection
- [ ] Monitor logs for auto-swaps

✅ **Observability**:
- [ ] Configure Prometheus scraping
- [ ] Set up alerts (high stuck pods, near capacity, spawn rate)
- [ ] Add dashboard (Grafana)

---

## Metrics Exposed

Prometheus metrics on port 9090:

- `cortex_orchestrator_spawn_rate` - Current spawn rate (pods/s)
- `cortex_orchestrator_active_agents` - Active pod count
- `cortex_orchestrator_capacity_limit` - Calculated capacity limit
- `cortex_orchestrator_headroom` - Available capacity
- `cortex_orchestrator_stuck_pods` - Number of stuck pods detected
- `cortex_orchestrator_swap_count` - Total successful swaps
- `cortex_orchestrator_swap_escalations` - Swaps escalated (loop detected)
- `cortex_orchestrator_queue_depth` - Pending spawn requests
- `cortex_orchestrator_backpressure_cpu` - CPU backpressure factor
- `cortex_orchestrator_backpressure_pending` - Pending pod pressure factor
- `cortex_orchestrator_backpressure_failures` - Failure rate factor
- `cortex_orchestrator_backpressure_api_latency` - API latency factor

---

## Next Steps

1. **Deploy to k3s cluster** following DEPLOYMENT.md
2. **Integrate with agent spawning** (coordinator-master, development-master, etc.)
3. **Set up monitoring** (Prometheus, Grafana, AlertManager)
4. **Tune configuration** based on actual cluster behavior
5. **Monitor and iterate** on spawn rates, thresholds, and profiles

---

## Success Criteria

The orchestrator is considered successful when:

✅ **Dynamic Limits Work**:
- Pod count stays within calculated capacity
- No unnecessary throttling when cluster has capacity
- Adjusts limits during instability

✅ **Spawn Modulation Works**:
- No thundering herd during burst workloads
- Respects backpressure signals
- Priority pods (replacements, coordinators) get spawned first

✅ **Stuck Detection Works**:
- Zombie pods detected within 5 minutes
- No false positives (healthy pods marked stuck)
- Task progress signal is accurate

✅ **Self-Healing Works**:
- Stuck pods automatically swapped
- Agent state preserved when possible
- Swap loops detected and escalated

✅ **Observability Works**:
- Logs are actionable
- Metrics are accurate
- Alerts fire appropriately

---

## Design Philosophy

The orchestrator embodies three key principles:

1. **Adaptive, Not Rigid**
   - Dynamic limits instead of hard caps
   - Backpressure-based throttling instead of fixed rates
   - Multi-signal liveness instead of just k8s probes

2. **Self-Healing, Not Brittle**
   - Automatic pod replacement for stuck pods
   - State preservation when possible
   - Escalation when loops detected

3. **Observable, Not Opaque**
   - Structured JSON logging
   - Prometheus metrics for all operations
   - Clear recommendations in status outputs

---

## Acknowledgments

This implementation builds on lessons learned from:
- **8-hour service fixing session** (10/10 services fixed)
- **Crash loop pattern analysis** (DaemonSet pain, init container traps, image pull races)
- **cortex-awareness MCP server** design (self-discovery, diagnostics, scaling)
- **Real-world k3s operations** (PVC corruption, NumPy incompatibilities, Falco rules)

The orchestrator is designed to prevent the crash loops and stuck pods encountered during that session.

---

## Status

**IMPLEMENTATION**: ✅ COMPLETE
**TESTING**: ✅ 40 tests passing
**DOCUMENTATION**: ✅ Complete (README, DEPLOYMENT, this summary)
**DEPLOYMENT**: ⏳ Ready for deployment to k3s

**All files created. Ready to deploy.**

---

*Implementation completed: 2026-01-10*
*Total development time: ~3 hours*
*Lines of code: ~3,800+*
*Test coverage: 40 tests across 4 modules*
