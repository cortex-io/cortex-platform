# Cortex Holdings - Organizational Structure

**Status**: Active
**Model**: Construction Company Architecture
**Last Updated**: 2025-12-09

---

## Executive Summary

Cortex Holdings operates as a multi-divisional technology conglomerate using a construction company organizational model. Think of it as a general contractor (Cortex Prime) that coordinates specialized sub-contractors (divisions) to build and maintain digital infrastructure.

Just like a construction company has:
- A general contractor who manages the overall project
- Specialized crews (electrical, plumbing, framing)
- Shared resources (tools, equipment, admin)
- A project manager who coordinates everyone

Cortex Holdings has:
- **Cortex Prime** - The general contractor (meta-agent)
- **Divisions** - Specialized technology crews
- **Shared Services** - Common tools and coordination
- **Resource Manager** - Budget and allocation controller

---

## Organizational Chart

```
                    CORTEX HOLDINGS
                         |
         +---------------+---------------+
         |                               |
    EXECUTIVE                      SHARED SERVICES
    LEVEL                          (Support Functions)
         |                               |
    +----+----+                    +-----+-----+
    |         |                    |     |     |
  Prime     COO              Coordinator |  Development
  (Meta)  (Orchestrator)     (Routing) CI/CD  (Features)
                                   |
                              Inventory
                             (Documentation)

         |
    DIVISIONS
    (Business Units)
         |
    +----+----+----+----+
    |    |    |    |    |
  Infra Cont Work Conf ResMan
  (Ops) (K8s) (Auto)(Cfg)(Budget)
```

---

## Executive Level

### Cortex Prime (General Contractor)
**Role**: Meta-agent, strategic decision-maker, escalation handler
**Analogy**: The general contractor who owns the company

**Responsibilities**:
- Strategic planning and architectural decisions
- Handling escalations from all divisions
- Approving major changes and initiatives
- Inter-division coordination
- Human interaction and communication
- Emergency response and critical issues

**Token Allocation**: 50k (reserved, on-demand)
**Working Directory**: `/Users/ryandahlberg/Projects/cortex/`
**Status**: Active (called by user or on escalation)

**Skills**:
- Cross-domain expertise
- High-level strategic thinking
- Conflict resolution
- Resource allocation oversight

---

### Chief Operating Officer (Orchestrator Master)
**Role**: Day-to-day operations manager
**Analogy**: The site supervisor who makes sure everything runs smoothly

**Responsibilities**:
- Daily operations monitoring
- Master coordination and health checks
- Daemon management (heartbeat, cleanup)
- System-wide performance tracking
- Operational metrics and reporting
- Cross-master handoff facilitation

**Token Allocation**: 30k
**Script**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/orchestrator.sh`
**Working Directory**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/`
**Status**: Active

**Skills**:
- Operations management
- System monitoring
- Performance optimization
- Cross-functional coordination

---

## Shared Services (Support Functions)

These are the "shared equipment yard" of Cortex Holdings - centralized functions that support all divisions.

### Coordinator Master (Project Manager)
**Role**: Task routing and assignment using MoE pattern matching
**Analogy**: The project manager who assigns work to the right crew

**Responsibilities**:
- Task queue monitoring
- Intelligent routing (MoE neural routing)
- Task decomposition
- Worker spawning and lifecycle management
- Token budget enforcement
- Task aggregation and reporting

**Token Allocation**: 50k (largest allocation for routing)
**Script**: `/Users/ryandahlberg/Projects/cortex/scripts/run-coordinator-master.sh`
**Context**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/`
**Status**: Active

**Worker Types Managed**:
- Analysis workers
- Coordinator overflow workers

**Skills**:
- Pattern matching (MoE)
- Task decomposition
- Resource allocation
- Worker orchestration

---

### Inventory Master (Documentation Crew)
**Role**: Repository cataloging and documentation
**Analogy**: The documentation team that keeps track of all assets and blueprints

**Responsibilities**:
- Repository scanning and cataloging
- Health status tracking
- Dependency mapping
- Documentation generation
- Asset inventory maintenance
- Compliance reporting

**Token Allocation**: 20k
**Script**: `/Users/ryandahlberg/Projects/cortex/scripts/run-inventory-master.sh`
**Context**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/inventory/`
**Status**: Active

**Managed Repositories**: 20 repositories (see inventory)

**Skills**:
- Repository scanning
- Documentation generation
- Data cataloging
- Compliance tracking

---

### CI/CD Master (Build & Deploy Crew)
**Role**: Continuous integration and deployment automation
**Analogy**: The crew that builds, tests, and delivers the finished product

**Responsibilities**:
- Build automation
- Test execution
- Deployment orchestration
- Dashboard deployment
- Pipeline management
- Release coordination

**Token Allocation**: 25k
**Script**: `/Users/ryandahlberg/Projects/cortex/scripts/run-cicd-master.sh`
**Context**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/cicd/`
**Status**: Active

**Skills**:
- Build automation
- Test orchestration
- Deployment management
- Pipeline optimization

---

### Development Master (Construction Crew)
**Role**: Feature implementation and code development
**Analogy**: The framing/construction crew that builds new features

**Responsibilities**:
- Feature implementation planning
- Bug fixing coordination
- Code refactoring
- Performance optimization
- Technical debt management
- Code review coordination

**Token Allocation**: 30k
**Script**: `/Users/ryandahlberg/Projects/cortex/scripts/run-development-master.sh`
**Context**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/development/`
**Status**: Active

**Worker Types** (MoE Specialization):
- Feature implementers
- Bug fixers
- Refactorers
- Optimizers

**Skills**:
- Feature development
- Debugging
- Code quality
- Performance tuning

---

### Security Master (Safety Inspector)
**Role**: Security scanning and vulnerability remediation
**Analogy**: The safety inspector who ensures everything is built to code

**Responsibilities**:
- Security scanning strategy
- CVE detection and tracking
- Vulnerability remediation
- Dependency auditing
- Security policy enforcement
- Compliance monitoring

**Token Allocation**: 30k
**Script**: `/Users/ryandahlberg/Projects/cortex/scripts/run-security-master.sh`
**Context**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/security/`
**Status**: Active

**Worker Types**:
- Scan workers
- Audit workers
- Remediation workers

**Skills**:
- Security scanning
- Vulnerability analysis
- Remediation planning
- Compliance enforcement

---

## Divisions (Business Units)

Each division is a specialized business unit focused on specific technology domains. Divisions operate semi-autonomously under Cortex Holdings but coordinate through Shared Services.

---

### Cortex Infrastructure Division
**Focus**: Physical and virtual infrastructure management
**Analogy**: The foundation and structural engineering crew

**Mission**: Manage core infrastructure including hypervisors, networking, and DNS

**Subsidiaries**:

#### 1. Proxmox MCP Server
- **Repository**: `ry-ops/proxmox-mcp-server`
- **Language**: Python
- **Purpose**: Proxmox VE management and orchestration
- **Status**: Active
- **Capabilities**: VM/LXC management, resource monitoring, backup orchestration

#### 2. UniFi MCP Server
- **Repository**: `ry-ops/unifi-mcp-server`
- **Language**: Python
- **Purpose**: UniFi network equipment management
- **Status**: Active
- **Stars**: 1
- **Capabilities**: Network device management, client tracking, wireless optimization

#### 3. Cloudflare MCP Server
- **Repository**: `ry-ops/cloudflare-mcp-server`
- **Language**: Python
- **Purpose**: DNS and CDN management
- **Status**: Active
- **Forks**: 1
- **Capabilities**: DNS management, WAF rules, SSL/TLS configuration

#### 4. Starlink Enterprise MCP Server
- **Repository**: `ry-ops/starlink-enterprise-mcp-server`
- **Language**: Python
- **Purpose**: Starlink terminal management
- **Status**: Active
- **Capabilities**: Terminal monitoring, network statistics, failover management

**Division Metrics**:
- Total Repositories: 4
- Primary Language: Python
- Combined Stars: 1
- Combined Forks: 1

**Coordination**:
- Reports to: Shared Services (Coordinator)
- Collaborates with: Cortex Containers (infrastructure layer)
- Escalates to: Cortex Prime (architectural decisions)

---

### Cortex Containers Division
**Focus**: Container orchestration and Kubernetes management
**Analogy**: The modular construction and prefab crew

**Mission**: Manage containerized workloads and Kubernetes infrastructure

**Subsidiaries**:

#### 1. Talos MCP Server
- **Repository**: `ry-ops/talos-mcp-server`
- **Language**: Python
- **Purpose**: Talos Linux cluster management
- **Status**: Active
- **Capabilities**: Node management, cluster operations, certificate management

#### 2. Talos A2A MCP Server
- **Repository**: `ry-ops/talos-a2a-mcp-server`
- **Language**: Python
- **Purpose**: Agent-to-agent Talos operations
- **Status**: Active
- **Capabilities**: Automated cluster coordination, multi-cluster management

**Division Metrics**:
- Total Repositories: 2
- Primary Language: Python
- Specialization: Kubernetes on bare metal (Talos Linux)

**Coordination**:
- Reports to: Shared Services (Coordinator)
- Collaborates with: Cortex Infrastructure (underlying infrastructure)
- Escalates to: Cortex Prime (cluster architecture)

---

### Cortex Workflows Division
**Focus**: Workflow automation and process orchestration
**Analogy**: The automation and controls crew

**Mission**: Automate business processes and integrate systems

**Subsidiaries**:

#### 1. n8n MCP Server
- **Repository**: `ry-ops/n8n-mcp-server`
- **Language**: Python
- **Purpose**: n8n workflow automation platform management
- **Status**: Active
- **Capabilities**: Workflow management, execution monitoring, credential management
- **Description**: "A Model Context Protocol (MCP) server that provides seamless integration with the n8n API. Manage your n8n workflows, executions, and credentials through natural language using Claude AI."

**Division Metrics**:
- Total Repositories: 1
- Primary Language: Python
- Integration Focus: Workflow automation

**Coordination**:
- Reports to: Shared Services (Coordinator)
- Collaborates with: All divisions (provides automation)
- Escalates to: Cortex Prime (workflow strategy)

---

### Cortex Configuration Division
**Focus**: Configuration management and identity systems
**Analogy**: The permits and compliance crew

**Mission**: Manage system configurations, identity, and access control

**Subsidiaries**:

#### 1. Microsoft Graph MCP Server
- **Repository**: `ry-ops/microsoft-graph-mcp-server`
- **Language**: Python
- **Purpose**: Microsoft 365 and Azure AD management
- **Status**: Active
- **Capabilities**: User management, group management, email operations, calendar management

**Division Metrics**:
- Total Repositories: 1
- Primary Language: Python
- Integration Focus: Microsoft ecosystem

**Coordination**:
- Reports to: Shared Services (Coordinator)
- Collaborates with: Security Master (identity security)
- Escalates to: Cortex Prime (IAM strategy)

---

### Cortex Monitoring Division
**Focus**: Observability and system monitoring
**Analogy**: The quality control and inspection crew

**Mission**: Monitor infrastructure health and performance

**Subsidiaries**:

#### 1. Netdata MCP Server
- **Repository**: `ry-ops/netdata-mcp-server`
- **Language**: Python
- **Purpose**: Real-time system monitoring
- **Status**: Active
- **Capabilities**: Metrics collection, alerting, performance monitoring

#### 2. Grafana A2A MCP Server
- **Repository**: `ry-ops/grafana-a2a-mcp-server`
- **Language**: Python
- **Purpose**: Grafana dashboard and alerting management
- **Status**: Active
- **Capabilities**: Dashboard management, data source configuration, alert rules

#### 3. CheckMK MCP Server
- **Repository**: `ry-ops/checkmk-mcp-server`
- **Language**: Python
- **Purpose**: Infrastructure monitoring and alerting
- **Status**: Active
- **Capabilities**: Host monitoring, service checks, notification management

#### 4. Pulseway MCP Server
- **Repository**: `ry-ops/pulseway-mcp-server`
- **Language**: Python
- **Purpose**: Remote monitoring and management
- **Status**: Active
- **Capabilities**: System monitoring, remote management, alerting

#### 5. Pulseway RMM A2A MCP Server
- **Repository**: `ry-ops/pulseway-rmm-a2a-mcp-server`
- **Language**: Python
- **Purpose**: Agent-to-agent RMM operations
- **Status**: Active
- **Capabilities**: Automated remediation, fleet management

**Division Metrics**:
- Total Repositories: 5
- Primary Language: Python
- Focus: Multi-vendor observability

**Coordination**:
- Reports to: Shared Services (Coordinator)
- Collaborates with: All divisions (monitors everything)
- Escalates to: COO (operational issues)

---

### Cortex Intelligence Division
**Focus**: AI assistance and conversation monitoring
**Analogy**: The quality assurance and training crew

**Mission**: AI-powered assistance and conversation intelligence

**Subsidiaries**:

#### 1. AIANA (AI Attendant)
- **Repository**: `ry-ops/aiana`
- **Language**: (in development)
- **Purpose**: AI conversation attendant for Claude Code
- **Status**: Active
- **Description**: "AI conversation attendant for Claude Code - monitors and records conversations in real-time via Claude Code API"
- **Capabilities**: Conversation monitoring, API interaction, real-time recording

**Division Metrics**:
- Total Repositories: 1
- Primary Focus: AI assistance
- Integration: Claude Code API

**Coordination**:
- Reports to: Shared Services (Coordinator)
- Collaborates with: Development Master (implementation)
- Escalates to: Cortex Prime (AI strategy)

---

## Resource Manager (Finance & Budget Controller)

**Role**: Token budget management and resource allocation
**Analogy**: The CFO and project accountant

**Responsibilities**:
- Daily token budget allocation (200k tokens)
- Master agent token reservations
- Worker pool management (65k tokens)
- Emergency reserve protection (25k tokens)
- Budget alerts and enforcement
- Cost optimization
- Usage metrics and reporting

**Token Budget Breakdown**:
```
Total Daily Budget: 200,000 tokens

Masters (Reserved):
  - Coordinator: 50,000 (25%)
  - Development: 30,000 (15%)
  - Security: 30,000 (15%)
  - CI/CD: 25,000 (12.5%)
  - Inventory: 20,000 (10%)
  - COO: 30,000 (15%)
  - Cortex Prime: 50,000 (on-demand)

Worker Pool: 65,000 (32.5%)
Emergency Reserve: 25,000 (12.5%)
```

**Budget Tracking**:
- File: `/Users/ryandahlberg/Projects/cortex/coordination/token-budget.json`
- Alert Threshold: 75% usage
- Critical Threshold: 90% usage
- Reset: Daily at midnight UTC

**Skills**:
- Budget planning
- Resource allocation
- Cost optimization
- Financial reporting

---

## Communication Protocols

### Handoff Protocol
Masters and divisions communicate through handoff files in their respective contexts:

**Format**: `handoffs/[source]-to-[destination]-[task-id].json`

**Example**:
```json
{
  "handoff_id": "dev-to-security-task-123",
  "from_master": "development",
  "to_master": "security",
  "task_id": "task-123",
  "handoff_type": "security_review",
  "context": {
    "summary": "New authentication feature needs security review",
    "files_changed": ["lib/auth/*.js"],
    "priority": "high"
  },
  "created_at": "2025-12-09T10:00:00Z",
  "status": "pending_pickup"
}
```

### Escalation Protocol
When a division or master needs executive decision-making:

1. Create escalation handoff to Cortex Prime
2. Include full context and attempted solutions
3. Specify decision needed
4. Wait for Prime response
5. Implement decision and report back

**Escalation Triggers**:
- Architectural decisions affecting multiple divisions
- Budget overruns or emergency reserve requests
- Inter-division conflicts
- Security incidents requiring immediate action
- Strategic planning and roadmap decisions

---

## Coordination Files

All inter-division communication uses shared files in `/Users/ryandahlberg/Projects/cortex/coordination/`:

**Core Files**:
- `task-queue.json` - Centralized task assignments
- `worker-pool.json` - Active worker tracking
- `token-budget.json` - Budget allocation and usage
- `repository-inventory.json` - Asset catalog (20 repositories)
- `dashboard-events.jsonl` - Event stream

**Master Contexts**:
- `masters/coordinator/` - Coordinator state and handoffs
- `masters/development/` - Development state and knowledge base
- `masters/security/` - Security state and findings
- `masters/inventory/` - Inventory state and catalogs
- `masters/cicd/` - CI/CD state and pipelines

**Division Contexts** (Future):
- `divisions/infrastructure/` - Infrastructure division state
- `divisions/containers/` - Containers division state
- `divisions/workflows/` - Workflows division state
- `divisions/configuration/` - Configuration division state
- `divisions/monitoring/` - Monitoring division state
- `divisions/intelligence/` - Intelligence division state

---

## Reporting Structure

### Daily Standup (Automated)
Each master reports daily metrics:
- Tasks completed
- Tokens used
- Workers spawned
- Issues encountered
- Handoffs created/received

**Aggregated by**: COO (Orchestrator Master)
**Delivered to**: Dashboard + Cortex Prime (on-demand)

### Weekly Review (On-Demand)
Division performance metrics:
- Repository health scores
- Security posture
- Development velocity
- Infrastructure stability
- Budget efficiency

**Generated by**: Inventory Master
**Reviewed by**: Cortex Prime

### Emergency Reports (Immediate)
Critical issues requiring immediate attention:
- Security vulnerabilities (CVSS >= 9.0)
- System outages
- Budget exhaustion
- Worker failures (>3 consecutive)

**Routed to**: Cortex Prime immediately

---

## Success Metrics

### Organizational KPIs

**Efficiency**:
- Token utilization rate: Target 70-80%
- Worker success rate: Target >90%
- Task completion time: Decreasing trend
- Parallel execution ratio: Target >50%

**Quality**:
- Repository health score: Target >85%
- Security posture: Zero critical CVEs
- Code coverage: Target >80%
- Documentation completeness: Target >90%

**Velocity**:
- Tasks per day: Target 15-20
- Mean time to resolution: Target <4 hours
- Master response time: Target <2 hours
- Worker spawn time: Target <5 minutes

**Cost**:
- Tokens per task: Decreasing trend
- Emergency reserve usage: Target <5%
- Worker efficiency: Target 85%+
- Budget variance: Target <10%

---

## Future Roadmap

### Q1 2026: Division Autonomy
- Division-specific knowledge bases
- Semi-autonomous decision making
- Inter-division collaboration protocols
- Division performance dashboards

### Q2 2026: Advanced Orchestration
- Predictive task routing
- Adaptive worker spawning
- ML-based budget optimization
- Cross-repository pattern learning

### Q3 2026: Scale & Expansion
- New divisions (Storage, Networking, Database)
- Multi-region support
- 24/7 autonomous operations
- Advanced analytics and reporting

### Q4 2026: AI Excellence
- ASI learning loops operational
- Self-optimizing architecture
- Proactive issue resolution
- Full autonomous capability

---

## Appendices

### Appendix A: Repository Inventory by Division

**Cortex Infrastructure** (4 repos):
- proxmox-mcp-server
- unifi-mcp-server
- cloudflare-mcp-server
- starlink-enterprise-mcp-server

**Cortex Containers** (2 repos):
- talos-mcp-server
- talos-a2a-mcp-server

**Cortex Workflows** (1 repo):
- n8n-mcp-server

**Cortex Configuration** (1 repo):
- microsoft-graph-mcp-server

**Cortex Monitoring** (5 repos):
- netdata-mcp-server
- grafana-a2a-mcp-server
- checkmk-mcp-server
- pulseway-mcp-server
- pulseway-rmm-a2a-mcp-server

**Cortex Intelligence** (1 repo):
- aiana

**Cortex Core** (1 repo):
- cortex

**Utilities** (3 repos):
- unifi-cloudflare-ddns
- unifi-grafana-streamer
- cara

**Other** (2 repos):
- minimal
- ry-ops (profile)

**Total**: 20 repositories

---

### Appendix B: Construction Company Analogy Guide

| Cortex Role | Construction Equivalent | Key Responsibility |
|-------------|------------------------|-------------------|
| Cortex Prime | General Contractor | Overall project leadership |
| COO | Site Supervisor | Daily operations |
| Coordinator | Project Manager | Work assignment |
| Development Master | Construction Crew | Building features |
| Security Master | Safety Inspector | Code compliance |
| Inventory Master | Documentation Team | Asset tracking |
| CI/CD Master | Build & Delivery | Testing and deployment |
| Resource Manager | CFO/Accountant | Budget control |
| Workers | Day Laborers | Specific tasks |
| Divisions | Sub-contractors | Specialized work |

---

### Appendix C: File Paths Reference

**Master Scripts**:
```
/Users/ryandahlberg/Projects/cortex/scripts/run-coordinator-master.sh
/Users/ryandahlberg/Projects/cortex/scripts/run-development-master.sh
/Users/ryandahlberg/Projects/cortex/scripts/run-security-master.sh
/Users/ryandahlberg/Projects/cortex/scripts/run-inventory-master.sh
/Users/ryandahlberg/Projects/cortex/scripts/run-cicd-master.sh
/Users/ryandahlberg/Projects/cortex/coordination/masters/orchestrator.sh
```

**Coordination Files**:
```
/Users/ryandahlberg/Projects/cortex/coordination/task-queue.json
/Users/ryandahlberg/Projects/cortex/coordination/worker-pool.json
/Users/ryandahlberg/Projects/cortex/coordination/token-budget.json
/Users/ryandahlberg/Projects/cortex/coordination/repository-inventory.json
/Users/ryandahlberg/Projects/cortex/coordination/dashboard-events.jsonl
```

**Master Contexts**:
```
/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/
/Users/ryandahlberg/Projects/cortex/coordination/masters/development/
/Users/ryandahlberg/Projects/cortex/coordination/masters/security/
/Users/ryandahlberg/Projects/cortex/coordination/masters/inventory/
/Users/ryandahlberg/Projects/cortex/coordination/masters/cicd/
```

---

## Document Status

**Version**: 1.0
**Status**: Active
**Last Updated**: 2025-12-09
**Next Review**: 2026-01-09

**Maintained by**: Cortex Prime (Development Master)
**Approved by**: Cortex Holdings Executive Team

---

**Welcome to Cortex Holdings - Building the Future, Autonomously.**
