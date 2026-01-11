# Cortex Self-Awareness MCP Server

**Purpose**: Give Cortex introspective awareness of its own infrastructure state, resource consumption, and operational health.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Cortex Agent                            │
│  "How am I doing?" → "Should I scale?" → "What happened?"  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP Cortex Awareness Server                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ K8s Watcher │  │ Metrics      │  │ Event Stream │      │
│  │             │  │ Scraper      │  │              │      │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                │                  │               │
│         └────────────────┴──────────────────┘               │
│                          │                                  │
│                   ┌──────▼──────┐                          │
│                   │ State Model │                          │
│                   │  - CPU       │                          │
│                   │  - Memory    │                          │
│                   │  - Agents    │                          │
│                   │  - Trends    │                          │
│                   └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    ┌───────────────┐         ┌─────────────┐
    │ k3s Cluster   │         │ Prometheus  │
    │ - Pods        │         │ Elastic     │
    │ - Nodes       │         │ Netdata     │
    │ - Events      │         └─────────────┘
    └───────────────┘
```

## Key Features

### 1. Self-Discovery
- Cortex knows which pod it's running in
- Understands its resource usage (CPU, memory)
- Tracks restart count and health status

### 2. Sibling Awareness
- Monitors all pods in its namespace
- Understands agent distribution across nodes
- Detects unhealthy siblings

### 3. Cluster Understanding
- Knows available capacity for scaling decisions
- Tracks node-level resources
- Understands scheduling constraints

### 4. Temporal Intelligence
- Maintains rolling windows of metrics
- Detects trends (increasing, decreasing, stable)
- Calculates volatility for predictive scaling

### 5. Agent Orchestration Awareness
- Tracks commit-relay agent spawn rate
- Monitors agent distribution across nodes
- Recommends placement for new agents

### 6. Natural Language Self-Reflection
Cortex can answer questions about itself:
- "How am I doing?"
- "Should I scale up for this task?"
- "What happened to my agents in the last hour?"
- "Which node should host the next security-master agent?"

## MCP Tools Exposed

### Core Tools
1. `get_self_state()` - Current pod state and resources
2. `get_sibling_pods()` - All pods in namespace
3. `get_cluster_capacity()` - Available cluster resources
4. `get_recent_events(minutes)` - Recent k8s events
5. `diagnose_issues()` - Self-diagnostic routine
6. `recommend_scaling(workload_type)` - Scaling recommendations

### Agent Tools (commit-relay integration)
7. `track_agent_spawn(agent_id, type)` - Record agent creation
8. `get_agent_distribution()` - Agent placement across nodes
9. `recommend_agent_placement(type)` - Best node for next agent
10. `get_agent_health()` - Health status of active agents

### Observability Tools
11. `get_resource_trends()` - CPU/memory trends
12. `get_error_patterns()` - Recent error patterns
13. `predict_capacity_need(hours)` - Predictive capacity planning

## Integration Points

### Elastic Cloud
```python
# Ship awareness metrics to Elastic for long-term analysis
await elastic_client.index(
    index="cortex-awareness",
    document={
        "timestamp": datetime.utcnow(),
        "pod_state": self_state,
        "cluster_capacity": capacity,
        "diagnostics": issues,
    }
)
```

### relay-dash
```python
# WebSocket endpoint for real-time updates
@app.websocket("/awareness/stream")
async def awareness_stream(websocket):
    while True:
        state = await awareness.get_self_state()
        await websocket.send_json(state)
        await asyncio.sleep(5)
```

### commit-relay MoE
```python
# Query before spawning agents
capacity = await mcp_client.call_tool("get_cluster_capacity")
if capacity["allocatable_cpu_percent"] < 20:
    # Implement backpressure or queue agents
    return {"action": "queue", "reason": "low_capacity"}

node = await mcp_client.call_tool("recommend_agent_placement", {
    "agent_type": "security-master"
})
# Spawn agent with node affinity
```

## Deployment

### RBAC Requirements
- `get, list, watch` on pods, nodes, events
- `get, list` on metrics.k8s.io (for resource usage)
- Read-only access to deployments, daemonsets, statefulsets

### Resource Requirements
- CPU: 100m request, 500m limit
- Memory: 128Mi request, 512Mi limit
- Storage: None (stateless, metrics in Prometheus/Elastic)

### High Availability
- Single replica (stateless)
- Can be restarted without data loss
- State rebuilt from k8s API on startup

## Usage Examples

### Self-Check
```python
# Cortex checks itself
state = await mcp.call_tool("get_self_state")
if state["restart_count"] > 5:
    print("I'm crashing frequently - investigating...")
    diagnostics = await mcp.call_tool("diagnose_issues")
    # Take corrective action
```

### Pre-Scaling Decision
```python
# Before launching 50 agents
recommendation = await mcp.call_tool("recommend_scaling", {
    "workload_type": "batch_agents"
})

if recommendation["should_scale"]:
    # Proceed with agent spawns
    for agent in agents:
        node = await mcp.call_tool("recommend_agent_placement", {
            "agent_type": agent.type
        })
        spawn_agent(agent, node_affinity=node)
else:
    # Queue for later or request cluster scale-up
    queue_agents(agents)
```

### Post-Incident Analysis
```python
# "What happened during the spike?"
events = await mcp.call_tool("get_recent_events", {"minutes": 60})
trends = await mcp.call_tool("get_resource_trends")

analysis = f"""
During the last hour:
- CPU trend: {trends['cpu']['trend']}
- Memory trend: {trends['memory']['trend']}
- Events: {len(events)} significant events
- Issue: {trends['summary']}
"""
```

## Future Enhancements

1. **Predictive Scaling**
   - Use historical patterns to predict capacity needs
   - Proactive scale-up before constraints hit

2. **Cost Awareness**
   - Track resource cost per agent type
   - Optimize placement for cost efficiency

3. **Multi-Cluster Awareness**
   - Federated view across multiple k3s clusters
   - Cross-cluster agent migration

4. **Learning from Patterns**
   - Detect recurring issues (e.g., "Falco crashes every deployment")
   - Auto-suggest fixes based on past resolutions

## Files Structure

```
mcp-servers/cortex-awareness/
├── README.md                    # This file
├── server/
│   ├── __init__.py
│   ├── awareness_server.py      # Main MCP server
│   ├── state_model.py           # Temporal state tracking
│   ├── k8s_client.py            # Kubernetes API wrapper
│   ├── agent_tracker.py         # commit-relay integration
│   └── diagnostics.py           # Self-diagnostic logic
├── k8s/
│   ├── deployment.yaml          # Kubernetes deployment
│   ├── rbac.yaml                # ServiceAccount + RBAC
│   └── service.yaml             # Service for MCP access
├── tests/
│   ├── test_awareness.py        # Unit tests
│   └── test_integration.py      # Integration tests
├── Dockerfile
├── pyproject.toml
└── docker-compose.yml           # Local dev setup
```

## Status

**Current**: Design complete, ready for implementation
**Next**: Implement core server + k8s client
**Target**: Integrated with cortex-chat backend for self-queries

