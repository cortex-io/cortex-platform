# GM Decision Engine

**Document Type**: Division General Manager Decision Support System
**Version**: 1.0.0
**Created**: 2025-12-09
**Maintained By**: Cortex Development Master

---

## Purpose

The GM Decision Engine provides Division General Managers with algorithms, matrices, and decision trees to route tasks to contractors efficiently, estimate resource needs, manage priorities, and coordinate cross-division work effectively.

**Construction Analogy**: Like a foreman's experience-based judgment combined with project management tools - systematically deciding which specialized crew handles each task, how long it will take, and what resources are needed.

---

## Table of Contents

1. [Task Complexity Scoring Algorithm](#task-complexity-scoring-algorithm)
2. [Contractor Selection Matrix](#contractor-selection-matrix)
3. [Resource Estimation Formulas](#resource-estimation-formulas)
4. [Priority Queue Management](#priority-queue-management)
5. [Load Balancing Across Contractors](#load-balancing-across-contractors)
6. [Escalation Criteria](#escalation-criteria)
7. [Decision Trees for Common Scenarios](#decision-trees-for-common-scenarios)
8. [Cross-Division Coordination Rules](#cross-division-coordination-rules)
9. [Budget Allocation Logic](#budget-allocation-logic)
10. [SLA Definitions Per Task Type](#sla-definitions-per-task-type)

---

## Task Complexity Scoring Algorithm

### Complexity Score: 1-10 Scale

**Purpose**: Objectively assess task complexity to inform contractor selection, resource allocation, and timeline estimation.

### Scoring Dimensions (Weighted)

Each dimension scored 1-10, then weighted:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| **Technical Complexity** | 30% | How difficult is the technical work? |
| **Integration Points** | 20% | How many systems must interact? |
| **Unknowns/Ambiguity** | 20% | How well-defined is the task? |
| **Risk Level** | 15% | What's the impact of failure? |
| **Dependencies** | 15% | How many external dependencies? |

### Technical Complexity (30% weight)

**Score 1-3: Low Complexity**
- Well-understood problem
- Standard patterns apply
- Previous examples exist
- Minimal edge cases
- Single technology

**Examples**:
- Create DNS A record
- Start/stop VM
- Read configuration file
- Simple CRUD operation

**Score 4-6: Medium Complexity**
- Some unknowns present
- Multiple components involved
- Moderate edge cases
- 2-3 technologies
- Some custom logic needed

**Examples**:
- Configure VLAN with firewall rules
- Deploy application with dependencies
- Multi-step workflow with validation
- Database migration with rollback

**Score 7-10: High Complexity**
- Novel problem or approach
- Complex algorithms required
- Many edge cases
- 4+ technologies integrated
- Significant custom development

**Examples**:
- Design distributed system architecture
- Implement custom authentication system
- Multi-region active-active setup
- Complex data transformation pipeline

### Integration Points (20% weight)

**Score = Number of Integration Points**

| Systems | Score | Examples |
|---------|-------|----------|
| 1 system | 1-2 | Single MCP operation (create VM) |
| 2 systems | 3-4 | VM + Network configuration |
| 3 systems | 5-6 | VM + Network + DNS |
| 4 systems | 7-8 | Full stack: VM + Network + DNS + Storage |
| 5+ systems | 9-10 | Complex orchestration across many systems |

### Unknowns/Ambiguity (20% weight)

**Score 1-3: Well-Defined**
- Clear requirements
- Explicit acceptance criteria
- Known approach
- Documented patterns
- Previous similar work

**Score 4-6: Moderate Ambiguity**
- General requirements clear
- Some acceptance criteria missing
- Approach generally known
- Some patterns available
- Research needed

**Score 7-10: High Ambiguity**
- Vague requirements
- Unclear acceptance criteria
- Approach unknown
- No existing patterns
- Significant research/experimentation

### Risk Level (15% weight)

**Score 1-3: Low Risk**
- Development/test environment
- No production impact
- Easy rollback
- Non-critical system
- Minimal user impact

**Score 4-6: Medium Risk**
- Staging environment
- Limited production impact
- Moderate rollback complexity
- Important but not critical
- Some user impact possible

**Score 7-10: High Risk**
- Production environment
- Critical system
- Difficult/impossible rollback
- Business-critical function
- High user impact

### Dependencies (15% weight)

**Score = Number of External Dependencies**

| Dependencies | Score | Examples |
|--------------|-------|----------|
| 0 dependencies | 1 | Self-contained task |
| 1-2 dependencies | 2-4 | Depends on 1-2 other tasks/systems |
| 3-4 dependencies | 5-7 | Multiple dependencies, some blocking |
| 5+ dependencies | 8-10 | Complex dependency chain |

### Calculating Final Complexity Score

**Formula**:
```
Complexity Score = (Technical * 0.30) +
                   (Integration * 0.20) +
                   (Unknowns * 0.20) +
                   (Risk * 0.15) +
                   (Dependencies * 0.15)
```

**Result**: 1.0 - 10.0 (round to 1 decimal place)

### Complexity Score Interpretation

| Score Range | Classification | Characteristics |
|-------------|----------------|-----------------|
| 1.0 - 3.0 | **Simple** | Single contractor, < 1 hour, < 3k tokens |
| 3.1 - 5.0 | **Moderate** | Single contractor, 1-2 hours, 3-6k tokens |
| 5.1 - 7.0 | **Complex** | 1-2 contractors, 2-4 hours, 6-12k tokens |
| 7.1 - 8.5 | **Very Complex** | Multiple contractors, 4-8 hours, 12-20k tokens |
| 8.6 - 10.0 | **Extremely Complex** | Multi-contractor coordination, 8+ hours, 20k+ tokens |

### Examples with Scoring

**Example 1: Create DNS Record**
- Technical: 2 (simple API call)
- Integration: 2 (single system - Cloudflare)
- Unknowns: 1 (well-defined)
- Risk: 3 (dev environment)
- Dependencies: 1 (none)

**Calculation**: (2×0.30) + (2×0.20) + (1×0.20) + (3×0.15) + (1×0.15) = 1.8
**Classification**: Simple
**Estimated**: 30 minutes, 2k tokens, infrastructure-contractor

---

**Example 2: Deploy Full Application Stack**
- Technical: 6 (multi-component deployment)
- Integration: 7 (VM + Network + DNS + Storage + K8s)
- Unknowns: 5 (some configuration discovery needed)
- Risk: 7 (production deployment)
- Dependencies: 6 (must sequence properly)

**Calculation**: (6×0.30) + (7×0.20) + (5×0.20) + (7×0.15) + (6×0.15) = 6.2
**Classification**: Complex
**Estimated**: 3-4 hours, 10-12k tokens, infrastructure + talos contractors

---

**Example 3: Design New Authentication System**
- Technical: 9 (novel design, security critical)
- Integration: 8 (API + Database + Auth + Frontend + Backend)
- Unknowns: 8 (many design decisions)
- Risk: 10 (production auth system)
- Dependencies: 7 (multiple team inputs)

**Calculation**: (9×0.30) + (8×0.20) + (8×0.20) + (10×0.15) + (7×0.15) = 8.5
**Classification**: Very Complex
**Estimated**: 6-8 hours, 18-22k tokens, multiple contractors + escalation to COO

---

## Contractor Selection Matrix

### Selection Criteria

**Primary Criteria**: Technology domain match
**Secondary Criteria**: Current load, success rate, cost efficiency

### Domain-to-Contractor Mapping

| Task Domain | Primary Contractor | Backup Contractor | Escalation |
|-------------|-------------------|-------------------|------------|
| **VM Provisioning** | infrastructure-contractor | - | COO (capacity) |
| **Network Configuration** | infrastructure-contractor | - | COO (design) |
| **DNS Management** | infrastructure-contractor | - | COO (architecture) |
| **Kubernetes Cluster** | talos-contractor | infrastructure-contractor | COO (architecture) |
| **K8s Workloads** | talos-contractor | - | COO (design) |
| **Workflow Automation** | n8n-contractor | - | COO (architecture) |
| **Integration Design** | n8n-contractor | - | COO (architecture) |
| **Multi-System Orchestration** | infrastructure-contractor | - | COO (coordination) |

### Selection Decision Tree

```
START: New Task Received
│
├─> Task requires VM/Network/DNS?
│   ├─> YES → infrastructure-contractor
│   │   └─> Check contractor availability
│   │       ├─> Available → Assign
│   │       └─> Overloaded → Queue or escalate to COO
│   │
│   └─> NO → Continue
│
├─> Task requires Kubernetes operations?
│   ├─> YES → talos-contractor
│   │   └─> Check contractor availability
│   │       ├─> Available → Assign
│   │       └─> Overloaded → Queue or escalate to COO
│   │
│   └─> NO → Continue
│
├─> Task requires workflow automation?
│   ├─> YES → n8n-contractor
│   │   └─> Check contractor availability
│   │       ├─> Available → Assign
│   │       └─> Overloaded → Queue or escalate to COO
│   │
│   └─> NO → Continue
│
└─> No matching contractor
    └─> Escalate to COO for contractor assignment or creation
```

### Multi-Contractor Tasks

**When to use multiple contractors**:
- Complexity score > 7.0
- Requires 3+ technology domains
- Estimated time > 4 hours
- Clear separation of concerns possible

**Coordination patterns**:

**Sequential** (dependencies exist):
```
infrastructure-contractor: Provision VMs
    ↓ (VMs ready)
talos-contractor: Bootstrap K8s cluster
    ↓ (Cluster ready)
n8n-contractor: Deploy workflow automation
```

**Parallel** (no dependencies):
```
infrastructure-contractor: Configure networking
║
n8n-contractor: Design workflows
║
talos-contractor: Prepare K8s configs
```

### Contractor Health Check

Before assignment, verify contractor status:

```json
{
  "contractor_id": "infrastructure-contractor",
  "health": "healthy",
  "current_load": {
    "active_tasks": 2,
    "capacity": 5,
    "utilization": 0.40
  },
  "performance_metrics": {
    "avg_response_time": "45 minutes",
    "success_rate": 0.96,
    "sla_compliance": 0.98
  },
  "availability": "available"
}
```

**Assignment Rules**:
- Utilization < 80%: Assign immediately
- Utilization 80-90%: Queue (low priority tasks) or assign (high priority)
- Utilization > 90%: Queue all tasks, escalate if high priority

---

## Resource Estimation Formulas

### Token Estimation

**Base Formula**:
```
Estimated Tokens = Base_Tokens + (Complexity_Multiplier × Integration_Factor) + Contingency
```

**Base Tokens by Task Type**:

| Task Type | Base Tokens | Description |
|-----------|-------------|-------------|
| Simple API call | 500-1000 | Single operation |
| Configuration task | 1500-3000 | Read config, apply changes |
| Single VM/resource | 2000-4000 | Provision and configure |
| Multi-step workflow | 3000-6000 | Multiple sequential operations |
| Complex orchestration | 8000-15000 | Multi-system coordination |
| Architecture/design | 5000-10000 | Design and planning |

**Complexity Multiplier**:
- Simple (1.0-3.0): 1.0x
- Moderate (3.1-5.0): 1.3x
- Complex (5.1-7.0): 1.6x
- Very Complex (7.1-8.5): 2.0x
- Extremely Complex (8.6-10.0): 2.5x

**Integration Factor**:
- 1 system: +0%
- 2 systems: +25%
- 3 systems: +50%
- 4 systems: +75%
- 5+ systems: +100%

**Contingency Buffer**:
- Well-defined task: +15%
- Moderate unknowns: +30%
- High unknowns: +50%

### Example Token Calculation

**Task**: Deploy VM with networking and DNS
- Base: 3000 tokens (multi-step workflow)
- Complexity: 5.2 (moderate-complex) → 1.6x multiplier
- Integration: 3 systems → +50%
- Contingency: Well-defined → +15%

**Calculation**:
```
Base = 3000
After complexity = 3000 × 1.6 = 4800
After integration = 4800 × 1.5 = 7200
After contingency = 7200 × 1.15 = 8280 tokens
```

**Final Estimate**: 8300 tokens (rounded)

### Time Estimation

**Base Formula**:
```
Estimated Time (hours) = (Complexity_Score × 0.5) + Overhead + Contingency
```

**Overhead Factors**:
- Research/planning: +0.5 hours (if unknowns > 5)
- Coordination: +0.25 hours per additional contractor
- Validation: +0.25 hours (always include)
- Documentation: +0.25 hours (if required)

**Contingency Time**:
- Simple task: +15%
- Moderate task: +25%
- Complex task: +35%
- Very complex: +50%

### Example Time Calculation

**Task**: Bootstrap Kubernetes cluster
- Complexity score: 6.5
- Unknowns: 4 (no extra research)
- Single contractor: talos-contractor
- Documentation required

**Calculation**:
```
Base = 6.5 × 0.5 = 3.25 hours
Overhead = 0 (no research) + 0 (single contractor) + 0.25 (validation) + 0.25 (docs) = 0.5 hours
Subtotal = 3.25 + 0.5 = 3.75 hours
Contingency = 3.75 × 1.35 (complex) = 5.06 hours
```

**Final Estimate**: 5 hours (rounded)

---

## Priority Queue Management

### Priority Levels

| Level | Name | SLA | Use Cases |
|-------|------|-----|-----------|
| P0 | **Critical** | < 15 min | Production outage, security incident |
| P1 | **High** | < 1 hour | Production degradation, urgent feature |
| P2 | **Medium** | < 4 hours | Standard operations, scheduled work |
| P3 | **Low** | < 24 hours | Optimizations, nice-to-haves |

### Priority Scoring Algorithm

**Formula**:
```
Priority Score = (Impact × 40%) + (Urgency × 30%) + (Business_Value × 20%) + (Risk × 10%)
```

Each factor scored 1-10.

**Impact** (1-10):
- 1-3: Single user or dev environment
- 4-6: Team or staging environment
- 7-8: Multiple teams or partial production
- 9-10: Company-wide or full production

**Urgency** (1-10):
- 1-3: Can wait weeks
- 4-6: Can wait days
- 7-8: Should complete today
- 9-10: Must complete within hours

**Business Value** (1-10):
- 1-3: Internal tooling, minor improvement
- 4-6: Team productivity, moderate improvement
- 7-8: Customer-facing, significant improvement
- 9-10: Revenue-impacting, critical capability

**Risk** (1-10):
- 1-3: If not done, minimal impact
- 4-6: If not done, inconvenience
- 7-8: If not done, significant problems
- 9-10: If not done, crisis

### Priority Score to Level Mapping

| Score Range | Priority Level | Action |
|-------------|----------------|--------|
| 8.0 - 10.0 | P0 - Critical | Preempt current work, assign immediately |
| 6.0 - 7.9 | P1 - High | Complete current task, then assign |
| 4.0 - 5.9 | P2 - Medium | Add to queue, assign when available |
| 1.0 - 3.9 | P3 - Low | Backlog, schedule during low-load periods |

### Queue Management Rules

**Rule 1: Priority Preemption**
- P0 tasks preempt all lower priority work
- P1 tasks preempt P2/P3, but not P0
- P2/P3 tasks queue normally

**Rule 2: Starvation Prevention**
- If P2 task waits > 8 hours, promote to P1
- If P3 task waits > 48 hours, promote to P2
- Alert GM when task promoted due to age

**Rule 3: Batch Low Priority**
- Group P3 tasks by contractor
- Execute in batches during low-load periods
- Maximize efficiency through batching

**Rule 4: FIFO Within Priority**
- Within same priority level, first-in-first-out
- Exception: Related tasks batched together

### Queue State Tracking

```json
{
  "queue_id": "infra-division-queue",
  "updated_at": "2025-12-09T14:30:00Z",
  "queues": {
    "p0_critical": {
      "count": 0,
      "tasks": []
    },
    "p1_high": {
      "count": 2,
      "tasks": [
        {
          "task_id": "task-001",
          "priority_score": 7.2,
          "wait_time": "25 minutes",
          "contractor": "infrastructure-contractor"
        },
        {
          "task_id": "task-002",
          "priority_score": 6.8,
          "wait_time": "45 minutes",
          "contractor": "infrastructure-contractor"
        }
      ]
    },
    "p2_medium": {
      "count": 5,
      "tasks": []
    },
    "p3_low": {
      "count": 8,
      "tasks": []
    }
  },
  "metrics": {
    "avg_wait_time_p1": "35 minutes",
    "sla_compliance": 0.96,
    "queue_depth_trend": "stable"
  }
}
```

---

## Load Balancing Across Contractors

### Load Balancing Strategy

**Objective**: Maximize throughput while respecting contractor capacity and SLA commitments.

### Contractor Capacity Model

```json
{
  "contractor_id": "infrastructure-contractor",
  "capacity": {
    "max_concurrent_tasks": 5,
    "max_token_budget": 25000,
    "max_session_hours": 8
  },
  "current_load": {
    "active_tasks": 3,
    "tokens_allocated": 15000,
    "tokens_remaining": 10000,
    "session_hours_used": 3.5,
    "utilization": 0.60
  },
  "performance": {
    "avg_task_duration": "2 hours",
    "throughput": "2.5 tasks/day",
    "success_rate": 0.96
  }
}
```

### Load Balancing Algorithm

**Step 1: Check Contractor Availability**
```
For each contractor:
  IF utilization < 0.80 AND tokens_remaining > task_estimate:
    Contractor is AVAILABLE
  ELSE IF utilization < 0.90 AND priority >= P1:
    Contractor is AVAILABLE (with preemption)
  ELSE:
    Contractor is OVERLOADED
```

**Step 2: Select Best Contractor**

If multiple contractors available:
```
Score = (1 - utilization) × 0.5 +
        (success_rate) × 0.3 +
        (sla_compliance) × 0.2

Select contractor with highest score
```

**Step 3: Assign or Queue**
```
IF contractor AVAILABLE:
  Assign task to contractor
  Update contractor load
  Update queue metrics
ELSE IF priority == P0:
  Escalate to COO for capacity decision
ELSE:
  Add to queue
  Notify requester of wait time
```

### Load Distribution Patterns

**Pattern 1: Round-Robin** (when contractors interchangeable)
```
Assign to contractor with lowest utilization
Rotate through available contractors
Useful for homogeneous tasks
```

**Pattern 2: Specialization** (when contractors have different expertise)
```
Assign based on expertise match
Accept higher utilization for best fit
Used for domain-specific tasks
```

**Pattern 3: Least-Loaded** (when optimizing throughput)
```
Always assign to contractor with most capacity
Maximize parallel execution
Used during high-load periods
```

### Overload Response

**When contractor utilization > 90%**:

**Option 1: Queue Management**
- Queue new P2/P3 tasks
- Allow P0/P1 to preempt if critical
- Estimate wait time for queued tasks

**Option 2: Task Redistribution**
- If backup contractor available, reassign
- If tasks can be batched, consolidate
- If tasks can be deferred, postpone

**Option 3: Capacity Expansion**
- Escalate to COO for approval
- Temporarily increase token budget
- Add contractor session time
- Only for sustained overload

### Load Balancing Metrics

Track and optimize:

```json
{
  "division": "infrastructure",
  "period": "2025-12-09",
  "load_metrics": {
    "avg_contractor_utilization": 0.68,
    "max_contractor_utilization": 0.85,
    "queue_depth_avg": 3.5,
    "queue_wait_time_avg": "42 minutes",
    "task_throughput": "18 tasks/day",
    "sla_compliance": 0.96,
    "load_imbalance_score": 0.15
  },
  "optimization_opportunities": [
    "Consider task batching for P3 tasks",
    "infrastructure-contractor has capacity for 2 more tasks"
  ]
}
```

**Load Imbalance Score**: Standard deviation of contractor utilizations. Lower is better.
- < 0.10: Well balanced
- 0.10 - 0.20: Acceptable
- > 0.20: Poor balance, investigate

---

## Escalation Criteria

### When to Escalate to COO

**Automatic Escalation Triggers**:

1. **Resource Exhaustion**
   - Division at > 90% token budget
   - All contractors at > 90% utilization
   - Queue depth > 20 tasks

2. **SLA Breach**
   - P0 task not started within 15 minutes
   - P1 task not started within 1 hour
   - 3+ tasks breached SLA in same day

3. **Task Complexity**
   - Complexity score > 8.5
   - Requires > 20k tokens
   - Estimated time > 8 hours

4. **Cross-Division Coordination**
   - Task requires 3+ divisions
   - Division handoff blocked > 1 hour
   - Circular dependency detected

5. **Contractor Issues**
   - Contractor success rate < 85% (last 10 tasks)
   - Contractor unavailable > 2 hours
   - 3+ consecutive task failures

6. **Project Risk**
   - Critical project blocked
   - Timeline slippage > 50%
   - Budget overrun > 20%

### Escalation Format

```json
{
  "escalation_id": "esc-infra-001",
  "from_division": "infrastructure",
  "to": "coo",
  "escalation_type": "resource_exhaustion",
  "severity": "high",
  "created_at": "2025-12-09T14:00:00Z",
  "context": {
    "trigger": "Division at 92% token budget with 6 hours remaining in day",
    "current_state": {
      "token_budget": 20000,
      "tokens_used": 18400,
      "tokens_remaining": 1600,
      "hours_remaining": 6,
      "queued_tasks": 12
    },
    "impact": "Cannot complete 12 queued medium-priority tasks today",
    "business_impact": "Infrastructure provisioning requests delayed 24+ hours"
  },
  "attempted_solutions": [
    {
      "solution": "Deferred all P3 tasks to tomorrow",
      "result": "Reduced queue to 12 from 18, still insufficient"
    },
    {
      "solution": "Optimized task execution for efficiency",
      "result": "Saved ~500 tokens, still 12 tasks queued"
    }
  ],
  "recommendation": "Request additional 5k token allocation for today",
  "justification": "12 medium-priority tasks from development division, blocking their sprint goals",
  "urgency": "4 hours - Development division needs infrastructure by EOD"
}
```

### Escalation Response SLA

| Escalation Type | COO Response SLA | Resolution SLA |
|----------------|------------------|----------------|
| P0 - Critical | < 5 minutes | < 30 minutes |
| High | < 15 minutes | < 2 hours |
| Medium | < 1 hour | < 4 hours |
| Low | < 4 hours | < 24 hours |

### Escalation Best Practices

**Before Escalating**:
1. Attempt at least 2 resolution strategies
2. Document attempted solutions
3. Quantify impact in business terms
4. Provide specific recommendation
5. Set clear urgency/deadline

**When Escalating**:
- Be clear and concise
- Provide full context
- Don't sugarcoat severity
- Offer recommendation
- Request specific action

**After Escalation**:
- Implement COO decision immediately
- Update relevant systems
- Document outcome
- Update knowledge base

---

## Decision Trees for Common Scenarios

### Scenario 1: New Task Received

```
START: Task received
│
├─> Assess task urgency
│   ├─> P0 (Critical)?
│   │   └─> Preempt current work → Assign immediately → Notify COO
│   └─> Continue assessment
│
├─> Calculate complexity score
│   ├─> Score ≤ 3.0 (Simple)?
│   │   └─> Quick path: Assign to available contractor → Execute
│   ├─> Score 3.1-7.0 (Moderate-Complex)?
│   │   └─> Standard path: Score priority → Queue or assign
│   └─> Score > 7.0 (Very Complex)?
│       └─> Complex path: Escalate to COO for planning
│
├─> Identify required contractor(s)
│   ├─> Single contractor needed?
│   │   └─> Check contractor availability
│   │       ├─> Available? → Assign task
│   │       └─> Overloaded? → Queue or escalate
│   └─> Multiple contractors needed?
│       └─> Create coordination plan → Assign to COO for orchestration
│
├─> Estimate resources
│   ├─> Tokens required
│   ├─> Time required
│   └─> Check division budget
│       ├─> Within budget? → Proceed
│       └─> Over budget? → Escalate for approval
│
└─> Execute decision
    ├─> Assign → Update contractor load → Monitor execution
    ├─> Queue → Notify requester → Track wait time
    └─> Escalate → Document escalation → Await COO decision
```

### Scenario 2: Contractor Overloaded

```
START: Contractor at > 90% utilization
│
├─> Assess incoming task priority
│   ├─> P0 (Critical)?
│   │   └─> Immediate action required
│   │       ├─> Preempt lowest priority active task
│   │       ├─> Assign P0 task immediately
│   │       └─> Notify COO of preemption
│   │
│   ├─> P1 (High)?
│   │   └─> Evaluate options
│   │       ├─> Can wait for current task completion? → Queue (short wait)
│   │       ├─> Backup contractor available? → Reassign to backup
│   │       └─> Neither? → Escalate to COO
│   │
│   └─> P2/P3 (Medium/Low)?
│       └─> Add to queue → Notify requester of wait time
│
├─> Check for pattern
│   ├─> Sustained overload (> 2 hours)?
│   │   └─> Escalate to COO for capacity decision
│   │       ├─> Increase contractor budget?
│   │       ├─> Add contractor instance?
│   │       └─> Defer non-critical work?
│   │
│   └─> Temporary spike?
│       └─> Queue management → Wait for capacity
│
└─> Optimize load distribution
    ├─> Batch P3 tasks for later
    ├─> Consolidate similar tasks
    └─> Review task priorities
```

### Scenario 3: Cross-Division Coordination Needed

```
START: Task requires multiple divisions
│
├─> Identify all involved divisions
│   └─> Map dependencies between divisions
│       ├─> Sequential dependencies?
│       │   └─> Create handoff chain: Div A → Div B → Div C
│       │
│       └─> Parallel possible?
│           └─> Coordinate simultaneous work
│
├─> Assess coordination complexity
│   ├─> Simple (2 divisions, clear interface)?
│   │   └─> Direct handoff via handoff files
│   │       ├─> Create handoff to Division B
│   │       ├─> Monitor handoff pickup
│   │       └─> Track completion
│   │
│   └─> Complex (3+ divisions, unclear interfaces)?
│       └─> Escalate to COO for project management
│           └─> COO spawns PM agent to coordinate
│
├─> Create coordination plan
│   ├─> Define handoff points
│   ├─> Set SLAs for each division
│   ├─> Establish status update cadence
│   └─> Plan for blockers/delays
│
└─> Execute coordination
    ├─> Issue initial handoffs
    ├─> Monitor division responses
    ├─> Track overall progress
    └─> Handle exceptions
        ├─> Handoff not picked up → Follow up with division
        ├─> Division blocked → Facilitate resolution
        └─> SLA breach → Escalate to COO
```

### Scenario 4: Budget Exhaustion Imminent

```
START: Division at 85% token budget
│
├─> Calculate remaining capacity
│   ├─> Hours left in day: X
│   ├─> Tokens remaining: Y
│   └─> Queued tasks token estimate: Z
│
├─> Assess budget situation
│   ├─> Y ≥ Z? (Sufficient budget)
│   │   └─> Continue normal operations
│   │       └─> Monitor closely for unexpected usage
│   │
│   └─> Y < Z? (Budget insufficient)
│       └─> Trigger budget optimization mode
│
├─> Optimization strategies
│   ├─> Defer P3 tasks to tomorrow
│   ├─> Consolidate similar tasks (batch efficiency)
│   ├─> Review in-progress tasks for optimization
│   └─> Re-estimate remaining tasks
│
├─> Recalculate after optimization
│   ├─> Now within budget?
│   │   └─> Continue with optimized plan
│   │
│   └─> Still over budget?
│       └─> Escalate to COO
│           ├─> Request additional allocation
│           ├─> Justify with business impact
│           ├─> Provide specific amount needed
│           └─> Explain optimization attempts
│
└─> Execute decision
    ├─> Approved additional budget? → Resume operations
    ├─> Denied? → Defer tasks, notify requesters
    └─> Partial approval? → Re-prioritize, execute critical tasks only
```

---

## Cross-Division Coordination Rules

### Rule 1: Handoff Protocol

**All cross-division work uses structured handoffs**

**Handoff File Location**:
```
/Users/ryandahlberg/Projects/cortex/coordination/divisions/[from-division]/handoffs/[to-division]/[handoff-id].json
```

**Required Fields**:
```json
{
  "handoff_id": "unique-id",
  "from_division": "source-division",
  "to_division": "target-division",
  "handoff_type": "resource_request|task_delegation|status_update|escalation",
  "priority": "p0|p1|p2|p3",
  "created_at": "ISO-8601 timestamp",
  "context": {
    "summary": "Brief description",
    "details": {},
    "requirements": [],
    "acceptance_criteria": [],
    "deadline": "ISO-8601 timestamp (if applicable)"
  },
  "status": "pending|acknowledged|in_progress|completed|blocked"
}
```

### Rule 2: Response Time SLAs

| Priority | Acknowledgment SLA | Completion SLA |
|----------|-------------------|----------------|
| P0 - Critical | < 5 minutes | As negotiated |
| P1 - High | < 30 minutes | As negotiated |
| P2 - Medium | < 2 hours | As negotiated |
| P3 - Low | < 8 hours | As negotiated |

### Rule 3: Dependency Declaration

**When creating handoff that depends on another division**:

```json
{
  "handoff_id": "infra-to-containers-001",
  "dependencies": [
    {
      "type": "blocking",
      "division": "infrastructure",
      "task_id": "task-infra-vm-001",
      "description": "VMs must be provisioned before container deployment",
      "status": "in_progress",
      "estimated_completion": "2025-12-09T16:00:00Z"
    }
  ]
}
```

### Rule 4: Status Update Cadence

**Minimum update frequency for cross-division work**:
- P0 work: Every 15 minutes
- P1 work: Every 30 minutes
- P2 work: Every 2 hours
- P3 work: Daily

**Update via handoff status field**:
```json
{
  "handoff_id": "infra-to-monitoring-001",
  "status": "in_progress",
  "progress_updates": [
    {
      "timestamp": "2025-12-09T14:00:00Z",
      "status": "in_progress",
      "progress_pct": 35,
      "message": "VMs provisioned, configuring networking",
      "estimated_completion": "2025-12-09T16:00:00Z"
    }
  ]
}
```

### Rule 5: Blocker Escalation

**If division cannot complete handoff within SLA**:

1. Update handoff status to "blocked"
2. Document blocker in handoff
3. Notify originating division immediately
4. If blocker not resolved within 1 hour:
   - Escalate to COO
   - Include both divisions in escalation

```json
{
  "handoff_id": "infra-to-security-001",
  "status": "blocked",
  "blocker": {
    "type": "resource_unavailable",
    "description": "Cannot complete security scan - scanner service down",
    "impact": "Cannot proceed with task",
    "detected_at": "2025-12-09T14:30:00Z",
    "resolution_attempts": [
      "Attempted service restart - failed",
      "Checked alternative scanner - also down"
    ],
    "escalated_to_coo": true,
    "escalation_id": "esc-sec-001"
  }
}
```

### Rule 6: Handoff Completion

**When task completed, receiving division must**:

1. Update handoff status to "completed"
2. Attach deliverables or results
3. Confirm acceptance criteria met
4. Provide metrics (time, tokens, quality)

```json
{
  "handoff_id": "infra-to-monitoring-001",
  "status": "completed",
  "completion": {
    "completed_at": "2025-12-09T16:15:00Z",
    "deliverables": [
      {
        "type": "infrastructure",
        "description": "3 VMs provisioned and configured",
        "details": {
          "vms": ["vm-001", "vm-002", "vm-003"],
          "network": "vlan-20",
          "dns": "monitoring.example.com"
        }
      }
    ],
    "acceptance_criteria_met": true,
    "metrics": {
      "time_spent": "2.25 hours",
      "tokens_used": 8500,
      "contractor": "infrastructure-contractor"
    }
  }
}
```

### Rule 7: Coordination Patterns

**Pattern A: Sequential Handoff Chain**
```
Division A → Division B → Division C
- Clear dependency chain
- Each division completes before next starts
- Simple coordination, longer total time
```

**Pattern B: Parallel with Sync Point**
```
Division A ─┐
Division B ─┼→ Sync Point → Division D
Division C ─┘
- Independent work in parallel
- Synchronize before next phase
- Complex coordination, shorter total time
```

**Pattern C: Hub and Spoke**
```
         Division A (Hub)
         /    |    \
Division B  C  D (Spokes)
- Central division coordinates
- Spokes work independently
- Good for distributed work
```

---

## Budget Allocation Logic

### Division Budget Structure

**Daily Token Allocation by Division**:

| Division | Daily Tokens | % of Total | Peak Load Reserve |
|----------|-------------|------------|-------------------|
| Infrastructure | 20,000 | 10% | 3,000 (15%) |
| Containers | 15,000 | 7.5% | 2,250 (15%) |
| Workflows | 12,000 | 6% | 1,800 (15%) |
| Configuration | 10,000 | 5% | 1,500 (15%) |
| Monitoring | 18,000 | 9% | 2,700 (15%) |
| Intelligence | 8,000 | 4% | 1,200 (15%) |

**Total Divisional**: 83,000 tokens/day

### Budget Allocation Algorithm

**Step 1: Reserve Emergency Budget (15%)**
```
Emergency_Reserve = Daily_Budget × 0.15
Available_Budget = Daily_Budget - Emergency_Reserve
```

**Step 2: Allocate by Task Priority**

```json
{
  "priority_allocation": {
    "p0_critical": "40% of available budget",
    "p1_high": "35% of available budget",
    "p2_medium": "20% of available budget",
    "p3_low": "5% of available budget"
  }
}
```

**Step 3: Dynamic Reallocation**

As day progresses, reallocate unused budget:
```
Every 2 hours:
  IF p0_budget_used < p0_budget_allocated:
    Excess = p0_budget_allocated - p0_budget_used
    Reallocate excess proportionally to p1/p2 based on demand
```

### Budget Tracking

```json
{
  "division": "infrastructure",
  "date": "2025-12-09",
  "budget": {
    "total_daily": 20000,
    "emergency_reserve": 3000,
    "available": 17000,
    "allocated": {
      "p0": 6800,
      "p1": 5950,
      "p2": 3400,
      "p3": 850
    },
    "used": {
      "p0": 4200,
      "p1": 3800,
      "p2": 2100,
      "p3": 450,
      "total": 10550
    },
    "remaining": 6450,
    "utilization": 0.62,
    "hours_remaining": 6,
    "burn_rate": "1758 tokens/hour"
  },
  "forecast": {
    "estimated_end_of_day_usage": 17004,
    "projected_overage": 4,
    "confidence": "high",
    "action_needed": false
  }
}
```

### Budget Alerts

**Alert Thresholds**:

| Utilization | Alert Level | Action |
|-------------|-------------|--------|
| 75% | Warning | Monitor closely, optimize ongoing tasks |
| 85% | High | Defer P3 tasks, optimize all operations |
| 90% | Critical | Defer P2/P3 tasks, prepare escalation |
| 95% | Emergency | Stop new work, escalate immediately |

### Budget Optimization Strategies

**Strategy 1: Task Batching**
- Group similar P3 tasks
- Execute in single contractor session
- Reduces overhead (planning, context switching)
- Can save 20-30% tokens

**Strategy 2: Cached Results**
- Store results of expensive operations
- Reuse for similar queries
- Query knowledge base before operations
- Can save 10-15% tokens

**Strategy 3: Efficient Contractor Selection**
- Match task to contractor expertise
- Avoid overqualified contractor (wastes capability)
- Use most efficient contractor for task type
- Can save 5-10% tokens

**Strategy 4: Scope Optimization**
- Review task requirements
- Remove unnecessary steps
- Focus on acceptance criteria only
- Can save 15-25% tokens

### Emergency Budget Use

**Criteria for Using Emergency Reserve**:
1. P0 critical task (production outage)
2. Security incident requiring immediate action
3. Data loss prevention
4. Legal/compliance deadline
5. Approved by COO

**Emergency Budget Tracking**:
```json
{
  "emergency_usage": {
    "date": "2025-12-09",
    "reserve_amount": 3000,
    "used": 1200,
    "remaining": 1800,
    "usages": [
      {
        "timestamp": "2025-12-09T11:30:00Z",
        "amount": 1200,
        "reason": "Production database outage",
        "priority": "p0",
        "approved_by": "coo",
        "outcome": "Database restored, service operational"
      }
    ]
  }
}
```

---

## SLA Definitions Per Task Type

### Infrastructure Tasks

| Task Type | Complexity | SLA (Response) | SLA (Completion) | Token Budget |
|-----------|-----------|----------------|------------------|--------------|
| VM Provision (Single) | 2.5 | < 30 min | < 1 hour | 2-3k |
| VM Provision (Multiple) | 4.0 | < 30 min | < 2 hours | 4-6k |
| Network VLAN Config | 3.5 | < 30 min | < 1.5 hours | 3-4k |
| DNS Record (Simple) | 1.5 | < 15 min | < 30 min | 1-2k |
| DNS + CDN Config | 4.5 | < 1 hour | < 2 hours | 5-7k |
| Full Stack (VM+Net+DNS) | 6.0 | < 1 hour | < 3 hours | 8-12k |
| Multi-Region Setup | 8.0 | < 2 hours | < 6 hours | 15-20k |

### Kubernetes Tasks

| Task Type | Complexity | SLA (Response) | SLA (Completion) | Token Budget |
|-----------|-----------|----------------|------------------|--------------|
| Cluster Bootstrap (Single Node) | 5.0 | < 1 hour | < 2 hours | 6-8k |
| Cluster Bootstrap (HA) | 7.0 | < 1 hour | < 4 hours | 12-15k |
| Node Addition | 3.5 | < 30 min | < 1 hour | 3-5k |
| Cluster Upgrade | 6.5 | < 2 hours | < 4 hours | 10-14k |
| Workload Deployment | 3.0 | < 30 min | < 1 hour | 3-4k |
| Storage Config (CSI) | 5.5 | < 1 hour | < 3 hours | 8-10k |
| Network Policy Setup | 4.5 | < 1 hour | < 2 hours | 5-7k |

### Workflow Automation Tasks

| Task Type | Complexity | SLA (Response) | SLA (Completion) | Token Budget |
|-----------|-----------|----------------|------------------|--------------|
| Simple Workflow (< 5 nodes) | 2.5 | < 30 min | < 1 hour | 2-3k |
| Medium Workflow (5-10 nodes) | 4.5 | < 1 hour | < 2 hours | 5-7k |
| Complex Workflow (> 10 nodes) | 7.0 | < 1 hour | < 4 hours | 10-15k |
| Workflow Modification | 3.0 | < 30 min | < 1 hour | 3-4k |
| Integration Design | 6.0 | < 2 hours | < 4 hours | 8-12k |
| Error Handling Addition | 4.0 | < 1 hour | < 2 hours | 4-6k |

### Priority Adjustments

**SLA Multipliers by Priority**:

| Priority | SLA Multiplier | Example |
|----------|----------------|---------|
| P0 (Critical) | 0.5x | 2-hour SLA becomes 1 hour |
| P1 (High) | 1.0x | Standard SLA |
| P2 (Medium) | 1.5x | 2-hour SLA becomes 3 hours |
| P3 (Low) | 3.0x | 2-hour SLA becomes 6 hours |

### SLA Compliance Tracking

```json
{
  "division": "infrastructure",
  "period": "2025-12-09",
  "sla_metrics": {
    "total_tasks": 45,
    "sla_met": 43,
    "sla_missed": 2,
    "compliance_rate": 0.956,
    "by_priority": {
      "p0": {"total": 2, "met": 2, "rate": 1.0},
      "p1": {"total": 15, "met": 14, "rate": 0.933},
      "p2": {"total": 20, "met": 20, "rate": 1.0},
      "p3": {"total": 8, "met": 7, "rate": 0.875}
    },
    "by_task_type": {
      "vm_provision": {"total": 12, "met": 12, "rate": 1.0},
      "network_config": {"total": 8, "met": 7, "rate": 0.875},
      "dns_config": {"total": 15, "met": 15, "rate": 1.0},
      "full_stack": {"total": 10, "met": 9, "rate": 0.9}
    },
    "missed_sla_details": [
      {
        "task_id": "task-infra-023",
        "type": "network_config",
        "priority": "p1",
        "sla": "1.5 hours",
        "actual": "2.1 hours",
        "variance": "+0.6 hours",
        "reason": "Unexpected firewall rule conflict required debugging"
      }
    ]
  },
  "improvement_actions": [
    "Add firewall validation pre-check to prevent conflicts",
    "Update SLA estimates for network_config to 2 hours"
  ]
}
```

### SLA Exception Handling

**When SLA breach imminent (80% of SLA time elapsed)**:

1. **Assess Remaining Work**
   - Can task complete within SLA?
   - What's blocking completion?

2. **Attempt Acceleration**
   - Allocate more tokens if helpful
   - Add contractor resources if possible
   - Remove unnecessary scope

3. **Communicate Proactively**
   - Notify requester of potential SLA miss
   - Provide new ETA
   - Explain reason for delay

4. **Escalate if Critical**
   - P0/P1 SLA misses: Escalate to COO
   - Explain impact
   - Request guidance/resources

5. **Document and Learn**
   - Record SLA miss reason
   - Update knowledge base
   - Adjust future SLA estimates if pattern

---

## Decision Engine Usage Guide

### For Division GMs

**At Task Receipt**:
1. Run complexity scoring algorithm
2. Use contractor selection matrix
3. Estimate resources (tokens, time)
4. Calculate priority score
5. Execute appropriate decision tree
6. Document decision rationale

**During Execution**:
1. Monitor against SLAs
2. Track budget utilization
3. Rebalance load across contractors
4. Handle escalations per criteria
5. Coordinate cross-division work per rules

**At Task Completion**:
1. Validate SLA compliance
2. Record actual vs estimated resources
3. Update knowledge base
4. Refine future estimates

### For COO

**Use Decision Engine Data For**:
- Division performance assessment
- Budget allocation adjustments
- Capacity planning
- Process optimization
- Escalation response

### Continuous Improvement

**Monthly Review**:
- SLA compliance rates
- Estimation accuracy
- Budget utilization efficiency
- Escalation patterns
- Contractor performance

**Update Decision Engine**:
- Refine complexity weights
- Adjust SLA times based on actuals
- Update resource estimation formulas
- Add new decision trees for emerging patterns
- Incorporate lessons learned

---

## Appendix: Quick Reference Tables

### Complexity Score → Actions

| Score | Classification | Contractor Count | Estimated Time | Estimated Tokens | Escalation |
|-------|----------------|------------------|----------------|------------------|------------|
| 1.0-3.0 | Simple | 1 | < 1h | < 3k | No |
| 3.1-5.0 | Moderate | 1 | 1-2h | 3-6k | No |
| 5.1-7.0 | Complex | 1-2 | 2-4h | 6-12k | If > 6.5 |
| 7.1-8.5 | Very Complex | 2+ | 4-8h | 12-20k | Yes |
| 8.6-10.0 | Extremely Complex | Multiple | 8h+ | 20k+ | Always |

### Priority Score → Queue Level

| Priority Score | Queue Level | SLA | Preemption |
|----------------|-------------|-----|------------|
| 8.0-10.0 | P0 - Critical | 15 min | Yes - All |
| 6.0-7.9 | P1 - High | 1 hour | Yes - P2/P3 |
| 4.0-5.9 | P2 - Medium | 4 hours | No |
| 1.0-3.9 | P3 - Low | 24 hours | No |

### Budget Utilization → Actions

| Utilization | Status | Action Required |
|-------------|--------|-----------------|
| 0-75% | Healthy | Normal operations |
| 75-85% | Warning | Monitor, optimize |
| 85-90% | High | Defer P3, optimize all |
| 90-95% | Critical | Defer P2/P3, prepare escalation |
| 95-100% | Emergency | Stop new work, escalate |

### Contractor Utilization → Load Balancing

| Utilization | Status | Assignment Rules |
|-------------|--------|------------------|
| 0-80% | Available | Assign all priorities |
| 80-90% | Busy | Assign P0/P1 only |
| 90-100% | Overloaded | Queue all, escalate if P0 |

---

## Document Status

**Version**: 1.0.0
**Created**: 2025-12-09
**Last Updated**: 2025-12-09
**Next Review**: 2025-12-16 (weekly)
**Maintained By**: Cortex Development Master

**Change Log**:
- 2025-12-09: Initial version, comprehensive decision engine created

**Integration Status**:
- ✅ Aligned with GM Common Patterns
- ✅ Integrated with Contractor System
- ✅ Compatible with Project Management Playbook
- ✅ Machine-readable companion file created

---

## Usage Notes

This decision engine is designed to be:
- **Prescriptive**: Clear algorithms and rules
- **Adaptable**: Weights and thresholds adjustable
- **Measurable**: All decisions trackable
- **Improvable**: Continuous refinement based on data

GMs should treat this as a decision support tool, not rigid rules. Experience and context matter - use judgment when engine recommendations don't fit situation.

**Remember**: The goal is efficient, effective task routing and resource allocation while maintaining quality and meeting SLAs. The engine helps achieve this systematically.
