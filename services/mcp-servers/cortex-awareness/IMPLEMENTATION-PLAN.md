# Cortex Self-Awareness - Implementation Plan

## Phase 1: Core Infrastructure (Week 1)

### 1.1 MCP Server Foundation
**Files**: `server/awareness_server.py`, `server/k8s_client.py`

**Tasks**:
- [x] Design complete
- [ ] Implement basic MCP server with health endpoint
- [ ] K8s API client wrapper (in-cluster + local kubeconfig)
- [ ] Basic tools: `get_self_state()`, `get_sibling_pods()`

**Success Criteria**:
- MCP server runs in k3s pod
- Can query own pod state
- Returns pod list for namespace

**Estimated Time**: 2-3 days

### 1.2 State Model & Metrics
**Files**: `server/state_model.py`

**Tasks**:
- [ ] Implement `MetricWindow` with rolling window
- [ ] Trend detection (increasing/decreasing/stable)
- [ ] Volatility calculation
- [ ] Basic `CortexStateModel` with CPU/memory tracking

**Success Criteria**:
- 60-minute rolling windows maintained
- Correct trend detection on test data
- Volatility < 0.3 for stable metrics

**Estimated Time**: 2 days

### 1.3 Kubernetes Deployment
**Files**: `k8s/deployment.yaml`, `k8s/rbac.yaml`

**Tasks**:
- [ ] Create ServiceAccount with minimal RBAC
- [ ] Deployment manifest with env vars (POD_NAMESPACE, HOSTNAME)
- [ ] Resource limits (100m CPU, 128Mi memory)
- [ ] Health/readiness probes

**Success Criteria**:
- Pod starts successfully
- RBAC allows reading pods/nodes
- Can call MCP tools from outside pod

**Estimated Time**: 1 day

**Deliverable**: Working MCP server in k3s answering basic queries

---

## Phase 2: Diagnostics & Intelligence (Week 2)

### 2.1 Self-Diagnostics
**Files**: `server/diagnostics.py`

**Tasks**:
- [ ] Implement `diagnose_issues()` logic
- [ ] Health thresholds (restart count, memory usage)
- [ ] Issue severity levels (info, warning, error)
- [ ] Recommendation engine

**Success Criteria**:
- Detects high restart count (>3)
- Warns on elevated memory (>80% limit)
- Provides actionable recommendations

**Estimated Time**: 2 days

### 2.2 Cluster Capacity Analysis
**Files**: `server/k8s_client.py` (extend)

**Tasks**:
- [ ] Node-level resource query (allocatable vs used)
- [ ] Calculate cluster-wide capacity percentages
- [ ] Identify nodes with headroom for scheduling
- [ ] Implement `get_cluster_capacity()` tool

**Success Criteria**:
- Returns per-node CPU/memory availability
- Cluster-wide capacity percentage accurate
- Identifies schedulable nodes

**Estimated Time**: 2 days

### 2.3 Event Stream Integration
**Files**: `server/awareness_server.py` (extend)

**Tasks**:
- [ ] Kubernetes event watcher
- [ ] Filter events by namespace/pod
- [ ] Time-based event retrieval (last N minutes)
- [ ] Implement `get_recent_events()` tool

**Success Criteria**:
- Returns events from last 30 minutes
- Filters by severity (Warning, Error)
- Performance: <100ms for event query

**Estimated Time**: 1-2 days

**Deliverable**: Full diagnostic capabilities with event correlation

---

## Phase 3: Agent Orchestration Awareness (Week 3)

### 3.1 Agent Tracker
**Files**: `server/agent_tracker.py`

**Tasks**:
- [ ] Agent registry (in-memory state)
- [ ] Track agent lifecycle (spawn, running, complete, failed)
- [ ] Agent spawn rate tracking with `MetricWindow`
- [ ] Implement `track_agent_spawn()` tool

**Success Criteria**:
- Maintains registry of 100+ active agents
- Spawn rate trend detection works
- Memory footprint < 50MB for 200 agents

**Estimated Time**: 2 days

### 3.2 Agent Placement Recommender
**Files**: `server/agent_tracker.py` (extend)

**Tasks**:
- [ ] Query current agent distribution across nodes
- [ ] Score nodes by: available CPU, existing agent count, network locality
- [ ] Implement `recommend_agent_placement()` tool
- [ ] Handle capacity exhaustion (return None)

**Success Criteria**:
- Recommends least-loaded node with capacity
- Balances agent distribution across cluster
- Returns None when no capacity available

**Estimated Time**: 2 days

### 3.3 commit-relay Integration
**Files**: Integration hooks in cortex repo

**Tasks**:
- [ ] Hook MoE router to call `track_agent_spawn()` on launch
- [ ] Pre-spawn capacity check via `recommend_scaling()`
- [ ] Use `recommend_agent_placement()` for node affinity
- [ ] Backpressure mechanism when capacity low

**Success Criteria**:
- Agents spawn with node affinity recommendations
- Backpressure activates at <20% capacity
- Agent distribution visible in awareness dashboard

**Estimated Time**: 2-3 days

**Deliverable**: Agent-aware scaling and placement

---

## Phase 4: Observability Integration (Week 4)

### 4.1 Prometheus Metrics Export
**Files**: `server/metrics_exporter.py`

**Tasks**:
- [ ] Prometheus exporter endpoint (`/metrics`)
- [ ] Export gauges: active_agents, cpu_percent, memory_mb
- [ ] Export counters: agent_spawns_total, diagnostics_run_total
- [ ] Histogram: capacity_check_duration

**Success Criteria**:
- Prometheus scrapes metrics successfully
- Grafana dashboard shows trends
- Metrics cardinality < 100 (avoid explosion)

**Estimated Time**: 1-2 days

### 4.2 Elastic Cloud Integration
**Files**: `server/elastic_shipper.py`

**Tasks**:
- [ ] Elasticsearch client setup
- [ ] Ship awareness state every 60s to `cortex-awareness` index
- [ ] Include: pod_state, diagnostics, agent_stats, cluster_capacity
- [ ] Query historical data for trend analysis

**Success Criteria**:
- Metrics visible in Kibana within 2 minutes
- Index template optimized for time-series
- 7-day retention policy configured

**Estimated Time**: 2 days

### 4.3 relay-dash Real-Time Updates
**Files**: New WebSocket endpoint in relay-dash

**Tasks**:
- [ ] Add `/awareness/stream` WebSocket endpoint
- [ ] Stream awareness state every 5 seconds
- [ ] Dashboard UI component for live pod/agent view
- [ ] Alert banners for diagnostics issues

**Success Criteria**:
- Dashboard shows live pod count, CPU, memory
- Agent distribution map updates in real-time
- Red alert when diagnostics detect issues

**Estimated Time**: 2-3 days

**Deliverable**: Full observability stack integration

---

## Phase 5: Natural Language Interface (Week 5)

### 5.1 Query Handler
**Files**: `server/nl_interface.py`

**Tasks**:
- [ ] Parse natural language queries: "How am I doing?", "Should I scale?"
- [ ] Route to appropriate MCP tools
- [ ] Generate human-readable responses
- [ ] Context awareness (remember previous queries in session)

**Success Criteria**:
- Correctly routes 10 common query patterns
- Responses are < 3 sentences, actionable
- Contextual follow-ups work ("What about the last hour?")

**Estimated Time**: 3 days

### 5.2 cortex-chat Integration
**Files**: Modify cortex-chat backend to route self-awareness queries

**Tasks**:
- [ ] Detect self-awareness queries in chat
- [ ] Route to cortex-awareness MCP server
- [ ] Display formatted responses in chat UI
- [ ] Add `/status` slash command for quick check

**Success Criteria**:
- User asks "Cortex, how are you doing?" → gets pod state
- `/status` shows diagnostics summary
- Responses formatted with Markdown

**Estimated Time**: 2 days

**Deliverable**: Conversational self-awareness

---

## Phase 6: Advanced Features (Week 6+)

### 6.1 Predictive Scaling
**Tasks**:
- [ ] Time-series forecasting (ARIMA or simple linear regression)
- [ ] Predict capacity needs 1-4 hours ahead
- [ ] Proactive scale-up recommendations

**Estimated Time**: 3-4 days

### 6.2 Cost Awareness
**Tasks**:
- [ ] Track resource cost per node type
- [ ] Calculate agent cost (CPU-hours × cost)
- [ ] Recommend cost-optimized placement

**Estimated Time**: 2-3 days

### 6.3 Pattern Learning
**Tasks**:
- [ ] Detect recurring failure patterns
- [ ] Link events to past resolutions
- [ ] Auto-suggest fixes based on history

**Estimated Time**: 4-5 days

**Deliverable**: AI-enhanced self-management

---

## Testing Strategy

### Unit Tests
- `tests/test_state_model.py` - MetricWindow, trend detection
- `tests/test_diagnostics.py` - Issue detection logic
- `tests/test_k8s_client.py` - Mocked k8s API responses

### Integration Tests
- `tests/test_integration.py` - Full MCP server in test cluster
- Test with real k3s (kind or minikube)
- Simulate agent spawns, pod failures

### Load Tests
- 200 concurrent agents
- 10 queries/sec to MCP server
- Validate memory footprint < 256MB

---

## Deployment Checklist

- [ ] RBAC created with minimal permissions
- [ ] Deployment manifest with resource limits
- [ ] Health probes configured
- [ ] Prometheus scraping enabled
- [ ] Elastic index template created
- [ ] relay-dash WebSocket endpoint deployed
- [ ] cortex-chat integration merged
- [ ] Documentation updated
- [ ] Runbook for incident response

---

## Success Metrics

### Performance
- **MCP query latency**: < 50ms p95
- **Memory usage**: < 256MB with 200 agents
- **CPU usage**: < 200m average

### Reliability
- **Uptime**: > 99.5%
- **Crash rate**: < 1 restart per 7 days
- **Error rate**: < 0.1% of queries

### Functionality
- **Diagnostic accuracy**: > 95% true positive rate
- **Placement recommendations**: Improve distribution stdev by 30%
- **Capacity predictions**: ±10% accuracy at 1-hour horizon

---

## Next Steps

**Start with Phase 1** - Core infrastructure is blocking everything else.

**Quick Win**: Get `get_self_state()` working in 2 days and demo to stakeholders.

**Milestone 1** (End of Week 2): Full diagnostics with event correlation  
**Milestone 2** (End of Week 3): Agent orchestration awareness integrated  
**Milestone 3** (End of Week 4): Observability stack complete  
**Milestone 4** (End of Week 5): Natural language interface live  

**Go/No-Go Decision Point**: After Phase 2, evaluate if ROI justifies advanced features (Phase 6).

