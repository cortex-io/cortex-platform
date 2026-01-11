# Project Management (PM) System

## Overview

The Cortex Project Management system enables ephemeral PM agents to coordinate complex, multi-division projects from initiation through closure. PMs are spawned per-project and exist only for the duration of that specific project.

## Directory Structure

```
coordination/project-management/
├── README.md                       # This file
├── pm-template.md                  # PM agent role and responsibilities
├── project-template.json           # Project state schema and template
├── pm-playbook.md                  # Patterns, strategies, and examples
├── project-examples/               # Example project templates
│   ├── deploy-k8s-cluster.md      # Multi-division infrastructure project
│   ├── setup-monitoring.md        # Single-division project
│   └── infrastructure-migration.md # Complex multi-phase migration
└── projects/                       # Active and archived projects
    └── ${PROJECT_ID}/              # Per-project directory (created at runtime)
        ├── project-state.json      # Current project state
        ├── project-plan.json       # Detailed task breakdown
        ├── risk-register.json      # Risk tracking
        ├── status-updates.jsonl    # Status history
        ├── handoffs/               # Division coordination
        │   ├── to-development/
        │   ├── to-security/
        │   ├── to-infrastructure/
        │   └── from-divisions/
        └── artifacts/
            ├── deliverables/
            └── reports/
```

## When to Spawn a PM

### Criteria for PM Spawning

**Spawn PM When**:
- Project involves 3+ divisions
- Estimated duration >4 hours
- Complex dependencies between tasks
- Multi-phase execution required
- High risk or critical business impact
- Requires coordinated handoffs and tracking

**Don't Spawn PM When**:
- Single division, <3 tasks
- Simple, routine operations
- Estimated duration <2 hours
- No cross-division dependencies

### Spawning Process

The Coordinator Master spawns PMs when it receives complex project requests:

```bash
# Coordinator creates PM spawn request
cat > coordination/masters/coordinator/pm-spawns/pm-spawn-${PROJECT_ID}.json <<EOF
{
  "pm_id": "pm-${PROJECT_ID}",
  "project_id": "${PROJECT_ID}",
  "project_name": "Deploy Production K8s Cluster",
  "spawn_trigger": "multi_division_coordination",
  "spawned_by": "coordinator",
  "spawned_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "project_template": "coordination/project-management/project-template.json",
  "initial_context": {
    "objective": "Deploy production-ready K8s cluster",
    "divisions_involved": ["infrastructure", "security", "monitoring"],
    "estimated_duration": "8 hours",
    "token_budget": 50000,
    "priority": "high"
  }
}
EOF
```

## PM Lifecycle

### 1. Initialization
- PM receives spawn request from coordinator
- Creates project directory from template
- Loads initial context and requirements
- Notifies all involved divisions

### 2. Planning
- Breaks down objectives into tasks
- Maps dependencies
- Allocates resources
- Creates risk register
- Defines success criteria

### 3. Execution
- Issues handoffs to divisions
- Monitors task progress
- Manages dependencies
- Handles blockers
- Provides status updates

### 4. Closure
- Validates success criteria
- Creates completion report
- Documents lessons learned
- Archives artifacts
- Terminates PM instance

## Key Files

### pm-template.md
Complete PM agent specification including:
- Role and responsibilities
- How PMs are spawned
- Project lifecycle phases
- Multi-division coordination
- Status reporting format
- Escalation triggers
- Success criteria tracking

**Use**: Read this to understand PM agent behavior and capabilities.

---

### project-template.json
Structured JSON template for project state including:
- Project metadata
- Phase definitions
- Milestone tracking
- Task breakdown
- Resource allocation
- Risk register
- Dependencies
- Success criteria

**Use**: Copy this template when initializing new projects.

---

### pm-playbook.md
Practical patterns and strategies including:
- Common project patterns (sequential, parallel, wave-based, etc.)
- Multi-division coordination examples
- Timeline management
- Blocker handling procedures
- Handoff best practices
- PM success patterns
- Common pitfalls to avoid

**Use**: Reference this during project execution for proven patterns.

---

### Project Examples

#### deploy-k8s-cluster.md
**Type**: Multi-division infrastructure deployment
**Duration**: 12 hours
**Divisions**: Infrastructure, Security, Monitoring, Documentation
**Complexity**: Medium-High

Complete example showing:
- Multi-phase execution
- Parallel and sequential work
- Security hardening
- Comprehensive testing
- Risk management

**Use**: Template for infrastructure deployment projects.

---

#### setup-monitoring.md
**Type**: Single-division infrastructure project
**Duration**: 4 hours
**Divisions**: Monitoring (primary), Documentation (minimal)
**Complexity**: Medium

Example demonstrating:
- Why single-division projects may still need PM
- Simpler coordination model
- Focus on single division with supporting docs
- Operational readiness validation

**Use**: Template for focused, single-division projects.

---

#### infrastructure-migration.md
**Type**: Complex multi-phase migration
**Duration**: 40 hours (3 PM sessions)
**Divisions**: Infrastructure, Data, Security, Monitoring, Documentation
**Complexity**: Very High

Advanced example showing:
- Multi-session PM approach
- Progressive validation (dev → staging → prod)
- High-risk project management
- Cutover planning and execution
- Zero-downtime strategies
- Comprehensive risk management

**Use**: Template for complex migrations and multi-session projects.

## Usage Patterns

### For Coordinator Master

When receiving project request:

```bash
# 1. Evaluate if PM needed
if [[ $division_count -ge 3 ]] || [[ $estimated_hours -gt 4 ]]; then
  # 2. Create PM spawn request
  # 3. Initialize project from template
  # 4. Hand off to PM
fi
```

### For PM Agent

On initialization:

```bash
# 1. Load pm-template.md for role understanding
# 2. Copy project-template.json to project directory
# 3. Review relevant project examples
# 4. Reference pm-playbook.md during execution
# 5. Follow lifecycle: initiation → planning → execution → closure
```

### For Division Masters

When receiving PM handoff:

```bash
# 1. Acknowledge handoff immediately
# 2. Execute assigned task
# 3. Provide status updates per PM request
# 4. Return completion handoff with deliverables
# 5. Report blockers immediately
```

## Success Metrics

PMs track and report:

**Schedule Performance**:
- Planned vs actual duration
- Milestone achievement rate
- Task completion velocity

**Budget Performance**:
- Token allocation vs usage
- Resource utilization efficiency

**Quality Performance**:
- Success criteria achievement
- Deliverable quality scores
- Rework requirements

**Coordination Performance**:
- Handoff response times
- Blocker resolution times
- Division satisfaction

## Integration Points

### With Coordinator Master
- **Receives**: Project spawn requests
- **Reports**: Status updates, escalations, completion
- **Requests**: Additional resources, architectural decisions

### With Division Masters
- **Sends**: Task assignments via handoffs
- **Receives**: Status updates, completions, blockers
- **Coordinates**: Dependencies, resource allocation

### With Knowledge Base
- **Reads**: Implementation patterns, past projects
- **Writes**: Lessons learned, project outcomes, reusable patterns

### With Dashboard
- **Reports**: Project status, metrics, events
- **Provides**: Real-time visibility into project progress

## Best Practices

### For Successful PM Operation

1. **Plan Thoroughly, Execute Fast**
   - Time-box planning phase
   - Front-load risk identification
   - Move to execution with "good enough" plan

2. **Communicate Proactively**
   - Regular status updates (every 30 minutes)
   - Escalate early, not late
   - Over-communicate rather than under

3. **Manage Dependencies Aggressively**
   - Dependencies are your primary concern
   - Unblock fast
   - Maximize parallelism

4. **Enforce Quality Gates**
   - Don't accept substandard deliverables
   - Validate against acceptance criteria
   - Reject incomplete work

5. **Track Everything**
   - Update project state continuously
   - Document decisions and rationale
   - Capture lessons learned throughout

6. **Know When to Escalate**
   - Blockers >30 minutes
   - Resource exhaustion
   - Division unresponsive >2 hours
   - Timeline at risk

7. **Learn and Share**
   - Document lessons learned
   - Update knowledge base
   - Share patterns with future PMs

### Common Pitfalls

**Avoid**:
- Over-planning (analysis paralysis)
- Under-communicating
- Ignoring early warning signs
- Skipping quality gates
- Resource exhaustion
- Micromanaging divisions

## Example Handoff Flows

### Task Assignment (PM to Division)

```json
{
  "handoff_id": "pm-to-dev-001",
  "from": "pm-proj-001",
  "to": "development",
  "handoff_type": "task_assignment",
  "task_id": "task-dev-001",
  "task_description": "Implement API authentication middleware",
  "dependencies": ["task-sec-001"],
  "priority": "high",
  "resources": {
    "token_allocation": 8000,
    "estimated_time": "2 hours"
  },
  "acceptance_criteria": [
    "JWT validation implemented",
    "Tests passing with >80% coverage",
    "Security review completed"
  ],
  "status_update_frequency": "30 minutes",
  "created_at": "2025-12-09T14:00:00Z"
}
```

### Task Completion (Division to PM)

```json
{
  "handoff_id": "dev-to-pm-001",
  "from": "development",
  "to": "pm-proj-001",
  "handoff_type": "task_completion",
  "task_id": "task-dev-001",
  "status": "completed",
  "deliverables": [
    "src/middleware/auth.js",
    "tests/middleware/auth.test.js"
  ],
  "acceptance_criteria_met": [
    {
      "criterion": "JWT validation implemented",
      "status": "met"
    },
    {
      "criterion": "Tests passing with >80% coverage",
      "status": "met",
      "evidence": "87% coverage"
    },
    {
      "criterion": "Security review completed",
      "status": "met"
    }
  ],
  "metrics": {
    "time_spent": "1.5 hours",
    "tokens_used": 6500
  },
  "completed_at": "2025-12-09T15:30:00Z"
}
```

### Blocker Report (Division to PM)

```json
{
  "handoff_id": "dev-to-pm-002-blocker",
  "from": "development",
  "to": "pm-proj-001",
  "handoff_type": "blocker_report",
  "task_id": "task-dev-002",
  "status": "blocked",
  "blocker": {
    "type": "dependency",
    "description": "Cannot implement payment processing without PCI compliance approval",
    "blocked_on": "task-sec-002",
    "impact": "Cannot proceed with task-dev-002",
    "time_blocked": "45 minutes"
  },
  "requested_action": "Fast-track security PCI compliance review",
  "reported_at": "2025-12-09T16:00:00Z"
}
```

## Status Reporting

PMs provide regular status updates to coordinator:

```json
{
  "project_id": "proj-001",
  "pm_id": "pm-proj-001",
  "timestamp": "2025-12-09T15:00:00Z",
  "phase": "execution",
  "overall_status": "on_track",
  "progress_percentage": 65,
  "milestones": {
    "completed": 2,
    "in_progress": 1,
    "pending": 2
  },
  "tasks": {
    "completed": 8,
    "in_progress": 3,
    "blocked": 1,
    "pending": 4
  },
  "resource_utilization": {
    "tokens_used": 32500,
    "tokens_remaining": 17500
  },
  "risks": [
    {
      "risk_id": "risk-001",
      "severity": "medium",
      "status": "active"
    }
  ]
}
```

## Multi-Session Projects

For projects exceeding single PM session capacity:

**Approach**: Break into multiple PM sessions, each with clear deliverables.

**Example**: Infrastructure Migration
- Session 1: Assessment & Dev Migration (12h)
- Session 2: Staging Migration & Validation (14h)
- Session 3: Production Migration & Cutover (14h)

**Benefits**:
- Manageable token budgets per session
- Natural validation gates between sessions
- Learning from each session informs next
- Reduced risk through progressive approach

**Process**:
1. Session 1 PM completes and documents
2. Coordinator spawns Session 2 PM with Session 1 learnings
3. Continue pattern through all sessions
4. Final session creates comprehensive project report

## Knowledge Base Integration

PMs contribute to organizational learning:

**During Project**:
- Reference past project patterns
- Apply proven strategies
- Document new approaches

**At Closure**:
- Create lessons learned document
- Update implementation patterns
- Share coordination strategies
- Document risk mitigations

**Knowledge Base Updates**:
- `/coordination/knowledge-base/project-patterns.jsonl`
- `/coordination/knowledge-base/pm-strategies.json`
- `/coordination/knowledge-base/risk-mitigations.json`

## Quick Reference

### PM Initialization Checklist
- [ ] Load pm-template.md
- [ ] Create project directory from template
- [ ] Review project objective and constraints
- [ ] Identify all divisions involved
- [ ] Create initial task breakdown
- [ ] Initialize risk register
- [ ] Notify divisions

### During Execution Checklist
- [ ] Issue handoffs with clear acceptance criteria
- [ ] Monitor task progress every 30 minutes
- [ ] Update project state after each event
- [ ] Handle blockers within 30 minutes
- [ ] Provide status updates to coordinator
- [ ] Enforce quality gates
- [ ] Track resource utilization

### Project Closure Checklist
- [ ] Validate all success criteria met
- [ ] All deliverables received and validated
- [ ] Create project completion report
- [ ] Document lessons learned
- [ ] Update knowledge base
- [ ] Archive project artifacts
- [ ] Hand off to coordinator
- [ ] Terminate PM instance

---

## Version

**PM System Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintained By**: Cortex Development Master

## Related Documentation

- `/coordination/masters/coordinator/coordinator-template.md` - Coordinator master (spawns PMs)
- `/coordination/divisions/README.md` - Division structure
- `/coordination/knowledge-base/` - Organizational learning
- `/coordination/templates/handoff-template.json` - Handoff format
