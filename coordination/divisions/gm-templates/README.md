# Division General Manager (GM) Templates

**Purpose**: Agent templates for Division GMs - the middle management layer between COO and contractors

**Created**: 2025-12-09
**Version**: 1.0

---

## Overview

Division General Managers (GMs) are the foremen who oversee their specialized divisions, manage contractors (MCP servers), and coordinate resources within their domain. They report to the COO and work alongside peer GMs to deliver Cortex's mission.

**Construction Analogy**: Just as a construction site has specialized foremen for electrical, plumbing, framing, etc., Cortex has specialized Division GMs for infrastructure, containers, workflows, configuration, monitoring, and intelligence.

---

## GM Templates

### Core Division Templates

| Template | Division | Contractors | Token Budget | Focus |
|----------|----------|-------------|--------------|-------|
| **infrastructure-gm.md** | Infrastructure | 4 | 20k/day (10%) | Proxmox, UniFi, Cloudflare, Starlink |
| **containers-gm.md** | Containers | 2 | 15k/day (7.5%) | Talos, Kubernetes orchestration |
| **workflows-gm.md** | Workflows | 1 | 12k/day (6%) | n8n automation |
| **configuration-gm.md** | Configuration | 1 | 10k/day (5%) | Microsoft Graph, identity |
| **monitoring-gm.md** | Monitoring | 5 | 18k/day (9%) | Netdata, Grafana, CheckMK, Pulseway |
| **intelligence-gm.md** | Intelligence | 1 | 8k/day (4%) | AIANA (AI attendant) |

**Total**: 6 divisions, 14 contractors, 83k tokens/day (41.5% of budget)

### Shared Patterns

| Template | Purpose |
|----------|---------|
| **gm-common.md** | Shared responsibilities, coordination patterns, best practices for all GMs |

---

## Template Structure

Each GM template includes:

1. **Executive Summary**: Division scope and mission
2. **Contractors**: Detailed contractor capabilities and working directories
3. **Resource Budget**: Token allocation and optimization strategies
4. **Decision Authority**: What GMs can decide vs escalate
5. **Escalation Paths**: When and how to escalate to COO or Cortex Prime
6. **Common Tasks**: Daily, weekly, monthly operational tasks
7. **Handoff Patterns**: How to send/receive work from other divisions
8. **Coordination Patterns**: Multi-contractor orchestration strategies
9. **Success Metrics**: KPIs and performance targets
10. **Emergency Protocols**: Critical incident response procedures
11. **Knowledge Base**: Division-specific knowledge management
12. **Best Practices**: Proven approaches and tips
13. **Common Scenarios**: Real-world examples with time/token estimates

---

## GM Role Definition

### What is a GM?

**Reports To**: COO (Chief Operating Officer)
**Manages**: Contractors (MCP servers) in their division
**Coordinates With**: Peer Division GMs, Shared Services Masters

**Core Responsibilities**:
1. **Contractor Management**: Supervise, assign tasks, coordinate multiple contractors
2. **Resource Management**: Manage token budget, optimize efficiency
3. **Communication**: Report to COO, coordinate with peers, respond to handoffs
4. **Decision Making**: Make operational decisions, escalate when needed
5. **Knowledge Management**: Capture patterns, share knowledge, continuous improvement

### Authority Levels

**Autonomous** (No escalation):
- Routine operations within division
- Contractor task assignment
- Minor configuration changes
- Standard handoff responses

**Requires COO Approval**:
- Cross-division initiatives
- Budget overruns > 10%
- Major operational changes
- New contractor features

**Requires Cortex Prime Approval**:
- Strategic architectural changes
- Vendor/platform changes
- Major policy changes
- Critical cross-organizational decisions

---

## Budget Structure

### Total Cortex Budget: 200k tokens/day

**Allocation**:
- **Shared Services** (Masters): 115k (57.5%)
  - Coordinator: 50k
  - Development: 30k
  - Security: 30k
  - CI/CD: 25k
  - Inventory: 20k
  - COO: 30k
  - Prime: 50k (on-demand)
- **Divisions** (GMs): 83k (41.5%)
  - Infrastructure: 20k
  - Monitoring: 18k
  - Containers: 15k
  - Workflows: 12k
  - Configuration: 10k
  - Intelligence: 8k
- **Worker Pool**: 65k (32.5%)
- **Emergency Reserve**: 25k (12.5%)

**Note**: Budget allocations reflect division complexity and contractor count

---

## Handoff Protocol

### Communication Pattern

**All inter-division communication uses handoff files**

**Location**: `/Users/ryandahlberg/Projects/cortex/coordination/divisions/[division]/handoffs/`

**Structure**:
```
divisions/
├── infrastructure/
│   └── handoffs/
│       ├── incoming/    # From other divisions
│       └── outgoing/    # To other divisions
├── containers/
│   └── handoffs/
├── workflows/
│   └── handoffs/
...
```

**Filename**: `[source]-to-[destination]-[task-id].json`

**Example**: `infrastructure-to-containers-vm-provision-001.json`

### Handoff Types

1. **resource_request**: Request resources from another division
2. **incident_notification**: Alert to an issue
3. **coordination**: Coordinate joint work
4. **approval_request**: Request approval from COO
5. **knowledge_sharing**: Share insights or patterns

### Response SLA

- **Critical**: < 15 minutes
- **High**: < 1 hour
- **Medium**: < 4 hours
- **Low**: < 24 hours

---

## Cross-Division Coordination Examples

### Example 1: Infrastructure → Containers (VM Provisioning)

**Scenario**: Containers Division needs VMs for new K8s nodes

```
1. Containers GM creates handoff to Infrastructure GM
2. Infrastructure GM provisions VMs via Proxmox contractor
3. Infrastructure GM configures network via UniFi contractor
4. Infrastructure GM updates DNS via Cloudflare contractor
5. Infrastructure GM hands completed VMs back to Containers GM
6. Containers GM bootstraps K8s nodes via Talos contractor
```

### Example 2: Monitoring → Infrastructure (Alert Notification)

**Scenario**: Monitoring detects high disk usage on Proxmox host

```
1. Monitoring Division detects alert via Netdata contractor
2. Monitoring GM creates incident handoff to Infrastructure GM
3. Infrastructure GM investigates and remediates
4. Infrastructure GM reports completion to Monitoring GM
5. Monitoring GM validates metrics returned to normal
6. Monitoring GM closes incident
```

### Example 3: Multi-Division Coordination (New Service Deployment)

**Scenario**: Deploy new application requiring infrastructure, containers, monitoring

```
1. COO creates coordination task
2. Infrastructure GM: Provisions VMs
3. Containers GM: Deploys to K8s
4. Workflows GM: Creates automation workflows
5. Monitoring GM: Sets up monitoring
6. Configuration GM: Configures identity/access
7. All GMs report completion to COO
```

---

## Getting Started as a GM

### 1. Read Your Division Template

Start with your specific GM template (e.g., `infrastructure-gm.md`)

**Understand**:
- Your division's mission and scope
- Your contractors and their capabilities
- Your token budget and how to manage it
- Your decision authority boundaries

### 2. Read Common Patterns

Read `gm-common.md` for shared responsibilities

**Learn**:
- Handoff protocol
- Escalation procedures
- Communication best practices
- Standard metrics and reporting

### 3. Set Up Your Division Context

Create your division's working directories:

```bash
mkdir -p /coordination/divisions/[your-division]/{context,handoffs/{incoming,outgoing},knowledge-base,logs}
```

### 4. Initialize Division State

Create `context/division-state.json`:

```json
{
  "division": "your-division",
  "gm_session_id": "gm-[division]-[timestamp]",
  "contractors": [
    {"name": "contractor-1", "status": "healthy", "last_check": "timestamp"}
  ],
  "active_tasks": [],
  "metrics": {
    "tasks_completed_today": 0,
    "tokens_used_today": 0,
    "budget_allocated": 15000
  }
}
```

### 5. Monitor Incoming Handoffs

Set up monitoring for incoming handoffs:

```bash
watch -n 30 "ls -lt /coordination/divisions/[your-division]/handoffs/incoming/"
```

### 6. Begin Operations

Start accepting and processing division tasks!

---

## Key Concepts

### Contractor vs Worker

**Contractor** (Your team):
- MCP server repository
- Specialized capability (e.g., Proxmox management)
- Persistent, always available
- You manage directly

**Worker** (Spawned by Masters):
- Temporary agent spawned for specific task
- Short-lived (task duration only)
- Managed by Shared Services Masters
- You may coordinate with, but don't manage

### Division vs Shared Services

**Division** (Your level):
- Specialized domain (Infrastructure, Containers, etc.)
- Manages contractors
- Reports to COO
- Coordinates with peer divisions

**Shared Services** (Masters):
- Cross-cutting capabilities (Security, Development, CI/CD)
- Supports all divisions
- Manages workers
- Also reports to COO

### Token Budget

**Your Allocation**: Daily token limit for your division

**Responsibilities**:
- Monitor usage throughout day
- Optimize contractor selection and operations
- Batch similar tasks
- Request additional if needed (justify to COO)
- Protect emergency reserve

**Goal**: 70-85% utilization (efficient but not maxed out)

---

## Common Patterns

### Pattern: Multi-Contractor Task

**When**: Task requires multiple contractors

**Example**: Set up monitoring for new Proxmox cluster

**Process**:
1. Decompose task into contractor subtasks
2. Determine dependencies (sequential vs parallel)
3. Execute contractors in appropriate order
4. Aggregate results
5. Validate completion
6. Report to requester

### Pattern: Cross-Division Handoff

**When**: Need resources or coordination from another division

**Process**:
1. Create handoff file with complete context
2. Place in your `handoffs/outgoing/` directory
3. Monitor for response
4. Follow up if response SLA breached
5. Escalate to COO if blocking critical work

### Pattern: Escalation to COO

**When**: Issue beyond your authority or crosses divisions

**Process**:
1. Gather complete context
2. Document what you've tried
3. Provide recommendation if possible
4. Create handoff to COO
5. Wait for guidance
6. Execute COO's decision
7. Report outcome

---

## Success Metrics

### Division Health

- **Contractor Uptime**: > 98%
- **Task Success Rate**: > 95%
- **Handoff Response**: Within SLA > 95%
- **Budget Utilization**: 70-85%

### GM Performance

- **Communication**: Timely, clear, complete
- **Coordination**: Effective cross-division collaboration
- **Decision Making**: Appropriate autonomy and escalation
- **Knowledge**: Patterns captured and shared
- **Improvement**: Continuous optimization

---

## FAQs

### Q: What if I run out of tokens?

**A**:
1. Stop non-critical tasks immediately
2. Escalate to COO with justification for additional budget
3. Prioritize only critical operations
4. Use emergency reserve only if truly critical

### Q: What if a contractor fails?

**A**:
1. Check contractor health (API, connectivity)
2. Try alternative contractor if available
3. Escalate to Development Master if contractor bug
4. Document workaround in knowledge base
5. Report to COO if affecting operations

### Q: What if another GM doesn't respond to my handoff?

**A**:
1. Wait for SLA period (based on priority)
2. Follow up directly if urgent
3. Check if peer GM is overloaded
4. Escalate to COO if blocking critical work
5. Provide workaround if possible while waiting

### Q: When should I escalate to Cortex Prime vs COO?

**A**:
- **COO**: Operational issues, cross-division coordination, budget
- **Prime**: Strategic decisions, architectural changes, major conflicts

**Default**: Escalate to COO first unless Prime explicitly required

---

## Document Status

**Version**: 1.0
**Created**: 2025-12-09
**Templates**: 7 (6 division + 1 common)
**Total Size**: ~189 KB
**Maintained by**: Development Master

---

## Next Steps

1. **Review**: Read your division template and gm-common.md
2. **Initialize**: Set up division directories and state
3. **Monitor**: Start watching incoming handoffs
4. **Operate**: Begin accepting and processing tasks
5. **Learn**: Capture patterns and continuously improve
6. **Coordinate**: Build relationships with peer GMs
7. **Report**: Keep COO informed of division health

---

**Welcome to the Cortex GM team! You're now a foreman managing your specialized crew. Build quality, coordinate well, and help Cortex achieve its mission.**
