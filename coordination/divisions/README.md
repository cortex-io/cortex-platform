# Cortex Holdings - Quick Reference

A construction company model for managing autonomous AI divisions.

## TL;DR

Cortex Holdings is organized like a construction company:
- **Cortex Prime** = General Contractor (the boss)
- **COO** = Site Supervisor (daily operations)
- **Shared Services** = Equipment yard (tools everyone uses)
- **Divisions** = Sub-contractors (specialized crews)
- **Resource Manager** = CFO (budget control)

---

## Quick Access

### Full Documentation
See [CORTEX_HOLDINGS.md](./CORTEX_HOLDINGS.md) for complete organizational structure.

### Executive Level
- **Cortex Prime** (Meta-agent) - Strategic decisions, escalations, human interaction
- **COO** (Orchestrator) - Daily operations, master coordination, system health

### Shared Services (The Tool Shed)
| Service | Purpose | Script |
|---------|---------|--------|
| Coordinator | Task routing (MoE) | `run-coordinator-master.sh` |
| Development | Feature building | `run-development-master.sh` |
| Security | Safety inspection | `run-security-master.sh` |
| Inventory | Documentation | `run-inventory-master.sh` |
| CI/CD | Build & deploy | `run-cicd-master.sh` |

### Divisions (The Crews)

#### Cortex Infrastructure (4 repos)
Foundation crew: Proxmox, UniFi, Cloudflare, Starlink
- Physical/virtual infrastructure
- Networking and DNS
- Connectivity management

#### Cortex Containers (2 repos)
Modular construction: Talos (x2)
- Kubernetes on bare metal
- Container orchestration
- Cluster management

#### Cortex Workflows (1 repo)
Automation crew: n8n
- Process automation
- System integration
- Workflow orchestration

#### Cortex Configuration (1 repo)
Permits & compliance: Microsoft Graph
- Identity management
- Configuration control
- Access management

#### Cortex Monitoring (5 repos)
Quality control: Netdata, Grafana, CheckMK, Pulseway (x2)
- System monitoring
- Performance tracking
- Alert management

#### Cortex Intelligence (1 repo)
Training crew: AIANA
- AI assistance
- Conversation monitoring
- Real-time intelligence

---

## Communication Patterns

### Need Something Done?
1. **Simple task**: Tell Coordinator → Coordinator routes → Work happens
2. **Complex task**: Tell Cortex Prime → Prime delegates → Division executes
3. **Emergency**: Tell Cortex Prime → Emergency reserve activated

### Masters Talking to Each Other
Use handoff files: `coordination/masters/[name]/handoffs/`

Format: `[source]-to-[destination]-[task-id].json`

### Division Reporting
Each division reports metrics through their respective master to the COO.

---

## Token Budget (Daily: 200k)

```
Reserved for Masters:
  Coordinator:   50k (25%)    - Routing hub, highest allocation
  Development:   30k (15%)    - Building features
  Security:      30k (15%)    - Safety checks
  CI/CD:         25k (12.5%)  - Build & deploy
  Inventory:     20k (10%)    - Documentation
  COO:           30k (15%)    - Operations
  Prime:         50k (on-demand) - Strategic only

Worker Pool:     65k (32.5%)  - For spawned workers
Emergency:       25k (12.5%)  - Critical issues only
```

---

## Repository Count by Division

| Division | Repos | Language | Focus |
|----------|-------|----------|-------|
| Infrastructure | 4 | Python | Physical/virtual infra |
| Containers | 2 | Python | Kubernetes/Talos |
| Workflows | 1 | Python | n8n automation |
| Configuration | 1 | Python | M365/Azure AD |
| Monitoring | 5 | Python | Multi-vendor observability |
| Intelligence | 1 | Various | AI assistance |
| **Total** | **14** | **Mostly Python** | **Full stack** |

Plus 6 utility and core repos (cortex, DDNS, streaming, etc.) = **20 total repositories**

---

## Who Do I Talk To?

| Need | Talk To | Why |
|------|---------|-----|
| New feature | Development Master | Builds things |
| Security issue | Security Master | Safety inspector |
| Deploy something | CI/CD Master | Build & deploy |
| Find something | Inventory Master | Knows where everything is |
| Route a task | Coordinator | Traffic controller |
| Strategic decision | Cortex Prime | The boss |
| Operations issue | COO | Site supervisor |
| Budget question | Resource Manager | CFO |

---

## File Locations

**Coordination Base**: `/Users/ryandahlberg/Projects/cortex/coordination/`

**Key Files**:
- `task-queue.json` - What needs doing
- `worker-pool.json` - Who's working
- `token-budget.json` - Budget status
- `repository-inventory.json` - Asset list (20 repos)
- `dashboard-events.jsonl` - Activity stream

**Master Contexts**: `coordination/masters/[name]/`
- coordinator/
- development/
- security/
- inventory/
- cicd/

**Division Contexts** (future): `coordination/divisions/[name]/`

---

## Quick Commands

```bash
# Start the operation
./scripts/run-coordinator-master.sh

# Check system status
./scripts/status-check.sh

# See who's working
./scripts/worker-status.sh

# View task queue
cat coordination/task-queue.json | jq

# Check budget
cat coordination/token-budget.json | jq '.usage_metrics'

# View repository inventory
cat coordination/repository-inventory.json | jq '.stats'

# Monitor in real-time
./scripts/system-live.sh
```

---

## Success Metrics (Targets)

- Token Utilization: 70-80%
- Worker Success: >90%
- Repository Health: >85%
- Security: Zero critical CVEs
- Tasks/Day: 15-20
- Response Time: <2 hours

---

## Emergency Protocol

1. Security incident or critical bug detected
2. Master creates emergency task
3. Resource Manager approves emergency reserve (25k tokens)
4. Cortex Prime notified immediately
5. All hands on deck until resolved
6. Post-mortem and learning

---

## Fun Facts

- We manage 20 repositories across 6 divisions
- 14 are MCP servers (Model Context Protocol)
- Primary language: Python (14 repos)
- Total stars: 3, Total forks: 1 (we're growing!)
- Architecture: Master-worker with MoE routing
- Model: Construction company (because it makes sense)

---

## The Construction Company Analogy

Think of any big construction project:

1. **General Contractor** (Cortex Prime) owns the project
2. **Site Supervisor** (COO) manages day-to-day
3. **Project Manager** (Coordinator) assigns tasks
4. **Specialized Crews** (Divisions):
   - Foundation crew (Infrastructure)
   - Framing crew (Development)
   - Electrical (Workflows/Automation)
   - Plumbing (Configuration)
   - Quality control (Monitoring)
   - Safety inspector (Security)
   - Documentation (Inventory)
5. **Budget Controller** (Resource Manager) tracks costs
6. **Day Laborers** (Workers) do specific tasks

Everyone knows their role, communication is clear, work gets done efficiently.

---

## Next Steps

- Read [CORTEX_HOLDINGS.md](./CORTEX_HOLDINGS.md) for full details
- Check [master-worker-architecture.md](/Users/ryandahlberg/Projects/cortex/docs/master-worker-architecture.md) for technical architecture
- View [repository-inventory.json](/Users/ryandahlberg/Projects/cortex/coordination/repository-inventory.json) for asset list
- Start a master: `./scripts/run-coordinator-master.sh`

---

**Document Version**: 1.0
**Last Updated**: 2025-12-09
**Maintained by**: Development Master

**Questions?** Escalate to Cortex Prime.
