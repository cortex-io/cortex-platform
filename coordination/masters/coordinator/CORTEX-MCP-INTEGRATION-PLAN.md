# Cortex MCP Server Integration Plan
## Coordinator: Larry

**Session ID**: cortex-mcp-integration-2025-12-24
**Status**: In Progress
**Start Time**: 2025-12-24T16:30:00Z

---

## Executive Summary

Building a complete Cortex MCP (Model Context Protocol) Server that exposes the entire Cortex construction company as a unified MCP interface. This will enable AI agents to:
- Query infrastructure (UniFi, Proxmox, Wazuh, k8s) - Tier 1
- Manage infrastructure (VMs, containers, pods) - Tier 2
- Spawn worker swarms (1-10,000 workers) - Tier 3
- Coordinate master agents - Tier 4
- Execute full project builds - Tier 5
- Monitor and control operations - Tier 6

---

## Current State Assessment

### Existing Assets
1. **MCP Server Foundation** (/Users/ryandahlberg/Projects/cortex/mcp-server/)
   - `index.js`: Basic MCP protocol server (JSON-RPC 2.0 over stdio)
   - `tools/index.js`: 8 tools implemented (route_task, spawn_worker, get_system_health, etc.)
   - `resources/index.js`: 13 resources defined (worker pool, task queue, manifests, etc.)
   - `manifests/`: Master agent capability manifests (coordinator, security, dev, inventory, cicd)

2. **MoE Router** (/tmp/cortex-moe-router.js)
   - Keyword-based routing for UniFi, Proxmox, Wazuh, k8s
   - Confidence scoring (0-1.0)
   - Priority-based expert selection

3. **Worker Infrastructure**
   - Scripts: /Users/ryandahlberg/Projects/cortex/scripts/
   - Worker pool daemon: worker-pool-daemon.sh
   - Worker specs: /Users/ryandahlberg/Projects/cortex/coordination/worker-specs/
   - Worker pool state: /Users/ryandahlberg/Projects/cortex/coordination/worker-pool.json

4. **Master Agents**
   - Coordinator: /Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/
   - Development: /Users/ryandahlberg/Projects/cortex/coordination/masters/development/
   - Security: /Users/ryandahlberg/Projects/cortex/coordination/masters/security/
   - Inventory: /Users/ryandahlberg/Projects/cortex/coordination/masters/inventory/
   - CI/CD: /Users/ryandahlberg/Projects/cortex/coordination/masters/cicd/

5. **Helm Chart** (/Users/ryandahlberg/Projects/cortex/deploy/helm/mcp-server/)
   - Deployment, Service, ConfigMap, Secret
   - HPA, PDB, ScaledObject for autoscaling
   - ServiceAccount and RBAC

### Gaps to Fill
1. **Missing MCP clients** for existing MCP servers:
   - UniFi MCP server: http://unifi-mcp-server.cortex-system.svc.cluster.local:3000
   - Wazuh MCP server: http://wazuh-mcp-server.cortex-system.svc.cluster.local:8080
   - Proxmox MCP server: http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000

2. **Worker pool management layer**:
   - Worker spawning orchestration (1-10,000 workers)
   - Worker health monitoring
   - Worker coordination and task distribution

3. **Master coordination interface**:
   - Master agent registry
   - Master handoff management
   - Master capability discovery

4. **Enhanced MCP tools** for Tier 2-6:
   - cortex_manage_infrastructure (VMs, containers, pods)
   - cortex_spawn_workers (swarm management)
   - cortex_coordinate_masters (master orchestration)
   - cortex_build_project (full project execution)
   - cortex_control (pause/resume/cancel operations)
   - cortex_get_status (comprehensive status)

5. **Integration layer**:
   - MoE router integration with MCP server
   - kubectl client for k8s operations
   - Package.json with all dependencies
   - Dockerfile for containerization

---

## Daryl Work Allocation

### Daryl-1: MCP Foundation & Infrastructure Clients
**Responsibility**: Build the core MCP protocol enhancements and infrastructure clients

**Deliverables**:
1. `src/clients/unifi.js` - UniFi MCP client (calls http://unifi-mcp-server...)
2. `src/clients/proxmox.js` - Proxmox MCP client
3. `src/clients/wazuh.js` - Wazuh MCP client
4. `src/clients/k8s.js` - kubectl wrapper client
5. `src/moe-router.js` - Enhanced MoE router (integrate /tmp/cortex-moe-router.js)
6. `src/tools/query.js` - cortex_query tool (Tier 1) - routes to infrastructure clients
7. Enhanced `src/index.js` - Integrate MoE router into MCP server

**Integration Points**:
- Clients use HTTP/JSON-RPC to call existing MCP servers
- MoE router pre-routes queries to correct client
- cortex_query tool orchestrates client calls

**Status**: Pending

---

### Daryl-2: Worker Pool & Master Coordination
**Responsibility**: Build worker swarm management and master coordination layer

**Deliverables**:
1. `src/worker-pool/spawner.js` - Worker spawning (1-10,000 workers)
2. `src/worker-pool/coordinator.js` - Worker task distribution
3. `src/worker-pool/monitor.js` - Worker health monitoring
4. `src/masters/interface.js` - Master agent interface
5. `src/masters/registry.js` - Master capability registry
6. `src/tools/workers.js` - cortex_spawn_workers tool (Tier 3)
7. `src/tools/masters.js` - cortex_coordinate_masters tool (Tier 4)
8. `src/tools/build.js` - cortex_build_project tool (Tier 5)
9. `src/tools/infrastructure.js` - cortex_manage_infrastructure tool (Tier 2)

**Integration Points**:
- Spawner calls existing /Users/ryandahlberg/Projects/cortex/scripts/spawn-worker.sh
- Monitor reads /Users/ryandahlberg/Projects/cortex/coordination/worker-pool.json
- Masters interface reads manifests from /Users/ryandahlberg/Projects/cortex/mcp-server/manifests/
- Registry discovers master capabilities dynamically

**Status**: Pending

---

### Daryl-3: Deployment & Testing
**Responsibility**: Build k8s deployment infrastructure and testing harness

**Deliverables**:
1. `Dockerfile` - Container image for cortex-mcp-server
2. `k8s/cortex-mcp-server.yaml` - Kubernetes deployment manifest
3. `src/tools/control.js` - cortex_control tool (pause/resume/cancel)
4. `src/tools/status.js` - cortex_get_status tool (comprehensive status)
5. `tests/integration/` - Integration test suite
6. `tests/tier-validation.js` - Validate all 6 tiers
7. `README.md` - Comprehensive documentation with examples
8. `docker-compose.yaml` - Local testing environment

**Integration Points**:
- Dockerfile builds from src/ directory
- k8s manifest deploys to cortex-system namespace
- Control/Status tools integrate with worker pool and masters
- Tests validate all tiers end-to-end

**Status**: Pending

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cortex MCP Server                        │
│                    (Port 3000: MCP)                         │
│                    (Port 8080: Status)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
        ┌───────▼────────┐     ┌───────▼────────┐
        │  MoE Router    │     │  MCP Protocol  │
        │  (Pre-route)   │     │  (JSON-RPC)    │
        └───────┬────────┘     └───────┬────────┘
                │                      │
    ┌───────────┴──────────────────────┴────────────┐
    │              Tool Dispatcher                   │
    └───────┬──────────────────┬────────────────────┘
            │                  │
    ┌───────▼────────┐  ┌──────▼─────────────────┐
    │  Infrastructure│  │  Worker/Master Layer   │
    │  Clients       │  │                        │
    │  (Tier 1-2)    │  │  (Tier 3-6)            │
    └───────┬────────┘  └──────┬─────────────────┘
            │                  │
┌───────────┴────────┐    ┌────┴──────────────────┐
│ UniFi MCP Client   │    │  Worker Pool Manager  │
│ Proxmox MCP Client │    │  - Spawner            │
│ Wazuh MCP Client   │    │  - Coordinator        │
│ kubectl Client     │    │  - Monitor            │
└────────────────────┘    └───────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │  Master Coordinator │
                         │  - Registry         │
                         │  - Interface        │
                         │  - Handoffs         │
                         └─────────────────────┘
```

### Data Flow

1. **Query Flow (Tier 1)**:
   ```
   AI Agent → MCP Server → MoE Router → Infrastructure Client → External MCP Server
   ```

2. **Worker Spawn Flow (Tier 3)**:
   ```
   AI Agent → MCP Server → cortex_spawn_workers → Worker Pool Spawner → spawn-worker.sh
   ```

3. **Project Build Flow (Tier 5)**:
   ```
   AI Agent → MCP Server → cortex_build_project → Master Coordinator →
   Task Decomposition → Worker Spawning (N workers) → Aggregation → Result
   ```

---

## File Structure (Final Target)

```
cortex-mcp-server/
├── package.json                 # Larry integrates
├── package-lock.json            # Auto-generated
├── Dockerfile                   # Daryl-3
├── docker-compose.yaml          # Daryl-3
├── README.md                    # Daryl-3
├── k8s/
│   └── cortex-mcp-server.yaml   # Daryl-3
├── src/
│   ├── index.js                 # Enhanced by Daryl-1
│   ├── moe-router.js            # Daryl-1
│   ├── clients/                 # Daryl-1
│   │   ├── unifi.js
│   │   ├── proxmox.js
│   │   ├── wazuh.js
│   │   └── k8s.js
│   ├── tools/                   # Daryl-1, Daryl-2, Daryl-3
│   │   ├── query.js             # Tier 1 (Daryl-1)
│   │   ├── infrastructure.js    # Tier 2 (Daryl-2)
│   │   ├── workers.js           # Tier 3 (Daryl-2)
│   │   ├── masters.js           # Tier 4 (Daryl-2)
│   │   ├── build.js             # Tier 5 (Daryl-2)
│   │   ├── control.js           # Tier 6 (Daryl-3)
│   │   └── status.js            # Tier 6 (Daryl-3)
│   ├── worker-pool/             # Daryl-2
│   │   ├── spawner.js
│   │   ├── coordinator.js
│   │   └── monitor.js
│   ├── masters/                 # Daryl-2
│   │   ├── interface.js
│   │   └── registry.js
│   └── resources/               # Existing + enhancements
│       └── index.js
└── tests/                       # Daryl-3
    ├── integration/
    └── tier-validation.js
```

---

## Conflict Resolution Strategy

### Potential Conflicts
1. **MoE Router Integration**: How to integrate with MCP server?
   - **Decision**: MoE router runs as pre-processor, suggests tool before MCP dispatch
   - **Rationale**: Maintains MCP protocol purity, adds intelligence layer

2. **Worker Spawning**: Direct shell execution vs. API?
   - **Decision**: Use existing spawn-worker.sh via child_process.spawn()
   - **Rationale**: Leverage proven infrastructure, maintain compatibility

3. **Master Coordination**: Direct handoffs vs. MCP tools?
   - **Decision**: MCP tools orchestrate, use existing handoff JSON files
   - **Rationale**: MCP is interface, handoffs are internal protocol

4. **k8s Client**: kubectl exec vs. k8s API?
   - **Decision**: kubectl exec for simplicity, k8s API for future
   - **Rationale**: Faster development, proven reliability

### Code Style Standards
- **Language**: JavaScript (Node.js 18+)
- **Style**: ES6+ with async/await
- **Error Handling**: Try-catch with descriptive errors
- **Logging**: Console with [Component] prefix
- **Comments**: JSDoc for functions, inline for complex logic

---

## Dependencies (package.json)

```json
{
  "name": "@cortex/mcp-server",
  "version": "1.0.0",
  "description": "Cortex MCP Server - Unified interface to Cortex construction company",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "test": "jest",
    "lint": "eslint src/",
    "docker:build": "docker build -t cortex-mcp-server:latest .",
    "k8s:deploy": "kubectl apply -f k8s/cortex-mcp-server.yaml"
  },
  "dependencies": {
    "axios": "^1.6.0",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "eslint": "^8.50.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

---

## Success Criteria

### Tier 1: Simple Queries
- [ ] cortex_query can query UniFi (devices, networks, clients)
- [ ] cortex_query can query Proxmox (VMs, nodes, storage)
- [ ] cortex_query can query Wazuh (alerts, agents, vulnerabilities)
- [ ] cortex_query can query k8s (pods, deployments, services)
- [ ] MoE router correctly routes queries with >90% confidence

### Tier 2: Infrastructure Management
- [ ] cortex_manage_infrastructure can create/delete VMs
- [ ] cortex_manage_infrastructure can manage containers
- [ ] cortex_manage_infrastructure can manage k8s pods

### Tier 3: Worker Swarms
- [ ] cortex_spawn_workers can spawn 1 worker
- [ ] cortex_spawn_workers can spawn 10 workers
- [ ] cortex_spawn_workers can spawn 100 workers
- [ ] cortex_spawn_workers can spawn 1,000 workers
- [ ] Worker health monitoring shows real-time status

### Tier 4: Master Coordination
- [ ] cortex_coordinate_masters can discover all masters
- [ ] cortex_coordinate_masters can route tasks to masters
- [ ] cortex_coordinate_masters can retrieve master status
- [ ] Master handoffs work end-to-end

### Tier 5: Full Project Builds
- [ ] cortex_build_project can decompose project into tasks
- [ ] cortex_build_project can spawn workers for all tasks
- [ ] cortex_build_project can aggregate results
- [ ] Example: "Build 50 microservices in 4 hours" works

### Tier 6: Monitoring & Control
- [ ] cortex_get_status shows system-wide status
- [ ] cortex_control can pause operations
- [ ] cortex_control can resume operations
- [ ] cortex_control can cancel operations

### Deployment
- [ ] Docker image builds successfully
- [ ] k8s deployment succeeds in cortex-system namespace
- [ ] Service is accessible on port 3000 (MCP)
- [ ] Status endpoint is accessible on port 8080
- [ ] Integration tests pass
- [ ] README has complete usage examples

---

## Timeline

### Phase 1: Foundation (Daryl-1)
**Duration**: 2-3 hours
**Deliverables**: MCP foundation, infrastructure clients, query tools

### Phase 2: Worker/Master Layer (Daryl-2)
**Duration**: 3-4 hours
**Deliverables**: Worker pool management, master coordination, build tools

### Phase 3: Deployment (Daryl-3)
**Duration**: 1-2 hours
**Deliverables**: Dockerfile, k8s manifests, tests, documentation

### Phase 4: Integration (Larry)
**Duration**: 1-2 hours
**Deliverables**: Combined system, package.json, final verification

**Total**: 7-11 hours (estimated)

---

## Next Steps

1. **Initialize Daryl work directories**:
   ```bash
   mkdir -p /Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/daryl-{1,2,3}
   ```

2. **Create Daryl handoff files**:
   - daryl-1-handoff.json (MCP foundation)
   - daryl-2-handoff.json (Worker/Master layer)
   - daryl-3-handoff.json (Deployment)

3. **Monitor Daryl progress**:
   - Check handoff status every 30 minutes
   - Resolve conflicts as they arise
   - Update integration plan based on discoveries

4. **Final integration**:
   - Combine all Daryl outputs
   - Create package.json
   - Build and test complete system
   - Deploy to cortex-system

---

## Notes

- All file paths are absolute: /Users/ryandahlberg/Projects/cortex/
- Existing MCP server code is at: /Users/ryandahlberg/Projects/cortex/mcp-server/
- MoE router reference is at: /tmp/cortex-moe-router.js
- Worker spawning script: /Users/ryandahlberg/Projects/cortex/scripts/spawn-worker.sh
- Coordination files: /Users/ryandahlberg/Projects/cortex/coordination/

---

## Status Log

**2025-12-24T16:30:00Z**: Coordination plan created
**2025-12-24T16:30:00Z**: Environment verified, existing assets cataloged
**2025-12-24T16:30:00Z**: Daryl work allocation defined
**2025-12-24T16:30:00Z**: Integration architecture designed

**Status**: Ready to spawn Daryls
