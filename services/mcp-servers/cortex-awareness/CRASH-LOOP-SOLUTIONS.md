# How Self-Awareness Solves the Crash Loop Patterns

This document maps the crash loop patterns you identified to specific awareness features that detect and prevent them.

---

## Pattern 1: Image Pull / Entrypoint Failures

### The Problem
- Missing dependencies in base image
- requirements.txt packages fail at runtime
- Entrypoint script fails before app starts

### Awareness Solution

#### Detection
```python
# diagnostics.py
async def detect_image_pull_failures():
    events = await get_recent_events(minutes=15)
    image_pull_errors = [
        e for e in events 
        if e["reason"] in ["Failed", "BackOff", "ErrImagePull"]
    ]
    
    if len(image_pull_errors) > 3:
        return {
            "severity": "error",
            "pattern": "repeated_image_pull_failure",
            "message": f"{len(image_pull_errors)} image pull failures detected",
            "recommendation": [
                "Check if image exists in registry",
                "Verify image tag is correct",
                "Check for registry authentication issues",
            ],
            "affected_pods": [e["involved_object"] for e in image_pull_errors],
        }
```

#### Prevention
```python
# Pre-deployment validation via MCP tool
async def validate_image_availability(image_name: str, tag: str):
    """Check if image exists before deploying."""
    # Query registry or check recent pull success
    registry_check = await check_registry(f"{image_name}:{tag}")
    
    if not registry_check["exists"]:
        return {
            "proceed": False,
            "reason": f"Image {image_name}:{tag} not found in registry",
            "action": "Build and push image first, or correct tag",
        }
    
    return {"proceed": True}
```

#### Real-World Example from Your Fixes
```python
# What happened with repo-context
state = await awareness.diagnose_issues()
# Would have detected:
# - Pod referencing :numpy-fixed tag
# - Image doesn't exist in registry
# - Recommendation: "Build image first or rollback to :latest"

# Prevention in future deployments
recommendation = await awareness.validate_image_availability(
    "10.43.170.72:5000/repo-context", 
    "numpy-fixed"
)
if not recommendation["proceed"]:
    print(f"Blocking deployment: {recommendation['reason']}")
```

---

## Pattern 2: Resource Starvation

### The Problem
- 7-node cluster tight on resources during dev
- Pods scheduled to nodes without capacity
- OOMKilled or CPU throttling

### Awareness Solution

#### Detection
```python
# diagnostics.py - Resource starvation detector
async def detect_resource_starvation():
    capacity = await get_cluster_capacity()
    
    issues = []
    for node, resources in capacity["nodes"].items():
        if resources["allocatable_cpu_percent"] < 10:
            issues.append({
                "severity": "warning",
                "node": node,
                "message": f"Node {node} has <10% CPU headroom",
                "current_usage": resources["used_cpu_millicores"],
                "limit": resources["allocatable_cpu_millicores"],
            })
        
        if resources["allocatable_memory_percent"] < 15:
            issues.append({
                "severity": "error",
                "node": node,
                "message": f"Node {node} at memory limit",
                "action": "Evict non-essential pods or scale cluster",
            })
    
    return issues
```

#### Prevention - Pre-Deployment Capacity Check
```python
# Before deploying 50 agents
async def check_capacity_before_spawn(agent_count: int, cpu_per_agent: int = 100):
    capacity = await awareness.get_cluster_capacity()
    required_cpu = agent_count * cpu_per_agent  # millicores
    
    available_cpu = capacity["total_allocatable_cpu_millicores"]
    
    if required_cpu > available_cpu * 0.8:  # Leave 20% headroom
        return {
            "proceed": False,
            "reason": f"Insufficient capacity for {agent_count} agents",
            "required": required_cpu,
            "available": available_cpu,
            "recommendation": "Queue agents or request cluster scale-up",
        }
    
    return {"proceed": True}
```

#### Real-World Example
```bash
# Your cluster during fixes
kubectl describe nodes | grep -A5 "Allocated resources"
# Would show: 75-85% CPU allocated across nodes

# Awareness would detect this:
{
    "cluster_cpu_pressure": true,
    "nodes_near_capacity": ["k3s-worker01", "k3s-worker03"],
    "recommendation": "Avoid spawning heavy workloads until capacity increases"
}
```

---

## Pattern 3: The Init Container Trap

### The Problem
- Job builds image but timing races with deployment
- Job hasn't completed → image doesn't exist → pod pulls old/broken image
- DaemonSet tries to pull before build completes

### Awareness Solution

#### Detection
```python
# Detect the race condition
async def detect_build_race_condition():
    # Check for jobs that are building images
    build_jobs = await get_jobs_by_label("job-type=image-build")
    
    # Check for pods trying to use those images
    events = await get_recent_events(minutes=5)
    image_pull_errors = [
        e for e in events 
        if e["reason"] == "ErrImagePull"
    ]
    
    races = []
    for job in build_jobs:
        if job["status"] != "Complete":
            # Find pods trying to use this image
            target_image = job["metadata"]["annotations"]["target-image"]
            for event in image_pull_errors:
                if target_image in event["message"]:
                    races.append({
                        "job": job["name"],
                        "status": job["status"],
                        "affected_pod": event["involved_object"],
                        "issue": "Pod trying to pull image before build complete",
                    })
    
    return races
```

#### Prevention - Build Orchestration
```python
# Proper build + deploy flow
async def orchestrate_image_build_and_deploy(build_spec, deployment_spec):
    """Ensure build completes before deployment updates."""
    
    # Start build job
    build_job = await create_k8s_job(build_spec)
    
    # Wait for completion with timeout
    await wait_for_job_completion(
        build_job["metadata"]["name"],
        timeout_minutes=10
    )
    
    # Verify image exists
    image_name = build_spec["metadata"]["annotations"]["target-image"]
    validation = await validate_image_availability(image_name, "latest")
    
    if not validation["proceed"]:
        raise RuntimeError(f"Build succeeded but image not available: {image_name}")
    
    # Now safe to update deployment
    await update_deployment(deployment_spec)
    
    return {
        "build_duration": build_job["status"]["duration"],
        "deployment_updated": True,
        "image": image_name,
    }
```

#### Real-World Example from Your Fixes
```python
# What happened with repo-context build attempts:
# Job 21: fix-repo-context-final-approach.yaml
# - Started docker build
# - Deployment already updated to use :numpy-fixed
# - Race: Deployment pulled before build finished
# - Result: ImagePullBackOff

# With awareness:
orchestration = await orchestrate_image_build_and_deploy(
    build_spec=build_job_spec,
    deployment_spec=repo_context_deployment
)
# Would have blocked deployment until build confirmed complete
```

---

## Pattern 4: DaemonSet-Specific Pain

### The Problem
- DaemonSets try to run on every node immediately
- 7 simultaneous crashes if init logic isn't baked in
- Can't debug because all instances fail at once

### Awareness Solution

#### Detection - Cluster-Wide Failure Pattern
```python
# Detect synchronized failures across nodes
async def detect_daemonset_cluster_failure():
    daemonsets = await get_daemonsets()
    
    for ds in daemonsets:
        desired = ds["status"]["desired_number_scheduled"]
        ready = ds["status"]["number_ready"]
        
        if desired > 3 and ready == 0:
            # All pods failing simultaneously
            pods = await get_pods_by_label(ds["spec"]["selector"]["matchLabels"])
            
            # Get common failure reason
            failure_reasons = [p["status"]["reason"] for p in pods if p["status"]["phase"] != "Running"]
            most_common = max(set(failure_reasons), key=failure_reasons.count)
            
            return {
                "severity": "critical",
                "daemonset": ds["metadata"]["name"],
                "pattern": "synchronized_daemonset_failure",
                "nodes_affected": desired,
                "common_failure": most_common,
                "recommendation": [
                    "This is a systemic issue, not node-specific",
                    "Fix source (image, config) not individual pods",
                    "Use kubectl rollout undo to revert",
                ],
            }
```

#### Prevention - Canary Rollout for DaemonSets
```python
# Gradual DaemonSet rollout
async def canary_daemonset_update(daemonset_name, new_spec):
    """Update DaemonSet gradually to detect issues early."""
    
    # Get current state
    ds = await get_daemonset(daemonset_name)
    nodes = await get_nodes()
    
    # Pick 1-2 canary nodes (workers, not masters)
    canary_nodes = [n["metadata"]["name"] for n in nodes if "worker" in n["metadata"]["name"]][:2]
    
    # Update with node selector for canary first
    canary_spec = new_spec.copy()
    canary_spec["spec"]["template"]["spec"]["nodeSelector"] = {
        "kubernetes.io/hostname": {"$in": canary_nodes}
    }
    
    await update_daemonset(daemonset_name, canary_spec)
    
    # Wait 60 seconds and check health
    await asyncio.sleep(60)
    
    health = await check_daemonset_pods_healthy(daemonset_name)
    
    if not health["all_healthy"]:
        # Rollback canary
        await rollback_daemonset(daemonset_name)
        return {
            "rollout": "aborted",
            "reason": f"Canary failed: {health['failure_reason']}",
            "action": "Fix issue before cluster-wide rollout",
        }
    
    # Canary successful, remove node selector for full rollout
    full_spec = new_spec.copy()
    await update_daemonset(daemonset_name, full_spec)
    
    return {"rollout": "complete", "canary_validated": True}
```

#### Real-World Example from Your Fixes
```python
# What happened with Falco:
# - Updated ConfigMap with new rules
# - kubectl rollout restart daemonset falco
# - All 7 pods crashed simultaneously with rule syntax error
# - Couldn't debug because logs disappeared

# With awareness + canary:
result = await canary_daemonset_update(
    "falco",
    new_falco_rules_configmap
)
# Would have:
# 1. Updated only 2 worker nodes first
# 2. Detected syntax error on canary pods
# 3. Rolled back before affecting all 7 nodes
# 4. Given clear error from canary logs
```

---

## The "Ghost Pod" Quick Debug

### The Problem
Pods crash so fast they disappear before inspection

### Awareness Solution - Persistent Event Capture
```python
# Event buffer with crash log extraction
class CrashLogCapture:
    def __init__(self):
        self.crash_buffer = deque(maxlen=100)  # Last 100 crashes
    
    async def watch_for_crashes(self):
        """Background watcher that captures crash logs immediately."""
        async for event in watch_events():
            if event["reason"] == "BackOff" or "Crash" in event["message"]:
                pod_name = event["involved_object"]["name"]
                
                # Immediately grab logs (including --previous)
                logs = await get_pod_logs(pod_name, previous=True, tail=100)
                
                self.crash_buffer.append({
                    "timestamp": event["last_timestamp"],
                    "pod": pod_name,
                    "reason": event["reason"],
                    "message": event["message"],
                    "logs": logs,
                })
    
    async def get_crash_history(self, pod_pattern: str):
        """Retrieve crash logs even after pod is gone."""
        matches = [
            c for c in self.crash_buffer 
            if pod_pattern in c["pod"]
        ]
        return matches
```

#### Usage
```python
# Pod crashed 30 seconds ago and is already gone
crash_history = await awareness.get_crash_history("repo-context")
# Returns:
[{
    "timestamp": "2026-01-10T18:30:00Z",
    "pod": "repo-context-65dc44845-znrfx",
    "reason": "CrashLoopBackOff",
    "logs": [
        "File \"/app/src/main.py\", line 43...",
        "ValueError: ChromaDB deprecated API...",
    ]
}]
```

---

## Summary: Awareness as Crash Prevention System

| Pattern | Detection Tool | Prevention Tool | Auto-Fix Potential |
|---------|---------------|-----------------|-------------------|
| Image Pull Failures | `diagnose_issues()` | `validate_image_availability()` | Medium - can rollback |
| Resource Starvation | `get_cluster_capacity()` | `check_capacity_before_spawn()` | High - queue workloads |
| Init Container Race | `detect_build_race_condition()` | `orchestrate_image_build_and_deploy()` | High - synchronize properly |
| DaemonSet Failures | `detect_daemonset_cluster_failure()` | `canary_daemonset_update()` | High - canary + auto-rollback |
| Ghost Pods | `CrashLogCapture` | N/A (reactive) | Low - provides diagnostics |

### Integration with Your Current Stack

```python
# In commit-relay MoE router
async def spawn_agent(agent_type: str):
    # Pre-flight checks via awareness
    capacity = await awareness_mcp.call_tool("check_capacity_before_spawn", {
        "agent_count": 1,
        "cpu_per_agent": 200,
    })
    
    if not capacity["proceed"]:
        # Queue instead of crashing
        await agent_queue.enqueue(agent_type)
        return {"status": "queued", "reason": capacity["reason"]}
    
    # Get optimal placement
    node = await awareness_mcp.call_tool("recommend_agent_placement", {
        "agent_type": agent_type
    })
    
    # Spawn with node affinity
    pod_spec["spec"]["affinity"] = {
        "nodeAffinity": {
            "requiredDuringSchedulingIgnoredDuringExecution": {
                "nodeSelectorTerms": [{
                    "matchExpressions": [{
                        "key": "kubernetes.io/hostname",
                        "operator": "In",
                        "values": [node],
                    }]
                }]
            }
        }
    }
    
    return await create_pod(pod_spec)
```

---

**Next Step**: Implement Phase 1 (Core Infrastructure) to get detection working, then gradually add prevention mechanisms.

