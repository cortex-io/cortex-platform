# PM State Machine

## Overview

The PM State Machine defines the formal state model for project execution in the Cortex automation system. It provides deterministic state transitions, checkpoint validation, rollback procedures, and progress tracking for all PM-managed projects.

## Purpose

- **Predictable Execution**: Define clear states and valid transitions
- **Progress Tracking**: Enable real-time visibility into project status
- **Quality Gates**: Enforce validation at critical checkpoints
- **Failure Recovery**: Provide rollback mechanisms for failed states
- **Resource Management**: Track and optimize resource allocation across states
- **Escalation Clarity**: Define when and how to escalate issues

---

## State Definitions

### 1. INITIATED

**Description**: Project spawned, PM agent created, initial setup in progress.

**Entry Conditions**:
- Coordinator master creates PM spawn request
- PM agent receives spawn notification
- Project ID assigned

**Responsibilities**:
- Create project directory structure
- Initialize project state file from template
- Load PM template and playbook
- Identify divisions involved
- Set up handoff directories

**Success Criteria**:
- Project directory created
- Project state file initialized
- PM ready to begin planning

**Exit Conditions**:
- All project directories created
- Project metadata populated
- PM acknowledges ready status to coordinator

**Valid Transitions**:
- `INITIATED → PLANNING` (normal progression)
- `INITIATED → FAILED` (setup failure, resource unavailable)

**Typical Duration**: 5-10 minutes

**Token Allocation**: 1-2% of total budget (500-1000 tokens for 50k budget)

---

### 2. PLANNING

**Description**: Requirements analysis, task breakdown, dependency mapping, resource allocation.

**Entry Conditions**:
- Project state = INITIATED
- PM agent ready
- Project objective defined

**Responsibilities**:
- Break down project objective into phases
- Define tasks with acceptance criteria
- Map dependencies between tasks
- Allocate token budget across tasks and phases
- Identify and document risks
- Create milestone schedule
- Notify all divisions of upcoming work

**Success Criteria**:
- All tasks defined with acceptance criteria
- Dependencies mapped in dependency graph
- Token allocation approved (within budget)
- Risk register initialized
- All divisions notified

**Exit Conditions**:
- Detailed task breakdown complete
- Resource allocation approved
- Dependency map validated
- At least one task ready to execute (no blocking dependencies)

**Valid Transitions**:
- `PLANNING → EXECUTING` (plan approved, ready to execute)
- `PLANNING → INITIATED` (rollback: plan rejected, needs re-scoping)
- `PLANNING → FAILED` (critical planning failure, project not viable)

**Checkpoints**:
- **CP-PLAN-01**: Task breakdown completeness
  - All divisions assigned at least one task
  - Each task has acceptance criteria
  - Token allocation sums to <= total budget
- **CP-PLAN-02**: Dependency validation
  - No circular dependencies
  - At least one task has no blockers (can start immediately)
  - Critical path identified
- **CP-PLAN-03**: Risk assessment
  - High/critical risks have mitigation strategies
  - Risk owners assigned
  - Monitoring frequency defined

**Typical Duration**: 30-60 minutes

**Token Allocation**: 4-6% of total budget (2000-3000 tokens for 50k budget)

---

### 3. EXECUTING

**Description**: Active task execution, division coordination, progress monitoring.

**Entry Conditions**:
- Project state = PLANNING
- All planning checkpoints passed
- At least one task ready to execute

**Responsibilities**:
- Issue task handoffs to divisions
- Monitor task progress continuously
- Track milestone completion
- Manage blockers and dependencies
- Update project state after each event
- Provide status updates every 30 minutes
- Enforce quality gates
- Reallocate resources as needed
- Escalate critical issues

**Sub-States** (internal execution states):
- `EXECUTING.ACTIVE`: Tasks in progress, normal operation
- `EXECUTING.BLOCKED`: One or more tasks blocked, resolution in progress
- `EXECUTING.AT_RISK`: Timeline or resources at risk, mitigation active
- `EXECUTING.RECOVERING`: Recovering from blocker or failed task

**Success Criteria**:
- All tasks completed successfully
- All deliverables received and validated
- All milestones achieved
- Quality gates passed
- No critical blockers remaining

**Exit Conditions**:
- 100% of tasks status = completed
- All acceptance criteria met
- All division handoffs returned with deliverables
- Resource utilization within budget (+10% tolerance)

**Valid Transitions**:
- `EXECUTING → VALIDATING` (all tasks complete, ready for validation)
- `EXECUTING → PLANNING` (rollback: major scope change, re-planning needed)
- `EXECUTING → FAILED` (critical failure, cannot recover)

**Checkpoints** (evaluated every 30 minutes):
- **CP-EXEC-01**: Progress tracking
  - % tasks completed vs. timeline
  - Burn rate (tokens/hour) vs. allocation
  - Milestone achievement rate
- **CP-EXEC-02**: Blocker management
  - No blocker unresolved >30 minutes
  - Critical path not blocked
  - Escalations responded to within SLA
- **CP-EXEC-03**: Quality enforcement
  - Deliverables meet acceptance criteria
  - No quality gates bypassed
  - Rework rate <20%
- **CP-EXEC-04**: Resource tracking
  - Token usage <90% of allocation
  - Reserve buffer maintained (10-20%)
  - Division capacity not over-allocated

**Typical Duration**: 60-80% of total project time (4-6 hours for 8h project)

**Token Allocation**: 70-80% of total budget (35k-40k tokens for 50k budget)

---

### 4. VALIDATING

**Description**: Final validation of deliverables, success criteria, and project outcomes.

**Entry Conditions**:
- Project state = EXECUTING
- All tasks status = completed
- All deliverables received

**Responsibilities**:
- Validate each success criterion
- Run final quality checks
- Verify all deliverables present and complete
- Check documentation completeness
- Validate resource usage within budget
- Identify any gaps or issues

**Success Criteria**:
- All success criteria validated (weighted score >= 80%)
- All deliverables meet specifications
- Documentation complete
- No critical issues outstanding

**Exit Conditions**:
- Success criteria score >= minimum_success_score (typically 80%)
- All deliverables validated
- No blocking issues

**Valid Transitions**:
- `VALIDATING → COMPLETE` (validation passed, project successful)
- `VALIDATING → EXECUTING` (rollback: validation failed, remediation needed)
- `VALIDATING → FAILED` (validation failed critically, cannot remediate)

**Checkpoints**:
- **CP-VAL-01**: Success criteria validation
  - Each criterion status = passed or waived (with justification)
  - Weighted score calculated
  - Score >= minimum threshold
- **CP-VAL-02**: Deliverable completeness
  - All expected deliverables present
  - Deliverables meet specifications
  - Documentation complete
- **CP-VAL-03**: Resource compliance
  - Token usage <= budget (+10% tolerance allowed)
  - Time spent <= estimated duration (+20% tolerance)
  - No division over-utilized

**Typical Duration**: 15-30 minutes

**Token Allocation**: 8-10% of total budget (4k-5k tokens for 50k budget)

---

### 5. COMPLETE

**Description**: Project successfully completed, closure activities, knowledge capture.

**Entry Conditions**:
- Project state = VALIDATING
- All validation checkpoints passed
- Success criteria met

**Responsibilities**:
- Create project completion report
- Document lessons learned
- Update knowledge base with patterns and outcomes
- Archive project artifacts
- Report final status to coordinator
- Clean up handoff directories
- Mark project state as completed
- Self-terminate PM agent

**Success Criteria**:
- Completion report created
- Lessons learned documented
- Knowledge base updated
- Artifacts archived
- Final status reported

**Exit Conditions**:
- All closure deliverables complete
- Coordinator acknowledges completion
- PM agent ready to terminate

**Valid Transitions**:
- `COMPLETE → [TERMINATED]` (PM agent terminates)

**Checkpoints**:
- **CP-COMPLETE-01**: Documentation completeness
  - Completion report generated
  - Lessons learned captured
  - Knowledge base entries created
- **CP-COMPLETE-02**: Archival
  - All artifacts archived in correct locations
  - Project state file finalized
  - Handoff directories cleaned

**Typical Duration**: 15-30 minutes

**Token Allocation**: 6-8% of total budget (3k-4k tokens for 50k budget)

---

### 6. FAILED

**Description**: Project failed to complete successfully, post-mortem and cleanup.

**Entry Conditions**:
- Critical failure from any state
- Unable to meet minimum success criteria
- Resource exhaustion with work incomplete
- Unrecoverable blocker

**Responsibilities**:
- Document failure reason
- Create incident report
- Capture partial deliverables
- Document lessons learned (especially failures)
- Identify root cause
- Recommend remediation or retry strategy
- Archive partial work
- Report failure to coordinator
- Self-terminate PM agent

**Success Criteria** (for failure handling):
- Failure documented with root cause
- Incident report created
- Lessons learned captured
- Partial work archived
- Coordinator notified

**Exit Conditions**:
- Failure documentation complete
- Coordinator acknowledges failure
- PM agent ready to terminate

**Valid Transitions**:
- `FAILED → [TERMINATED]` (PM agent terminates)

**Checkpoints**:
- **CP-FAIL-01**: Incident documentation
  - Failure reason documented
  - Root cause identified
  - Timeline of events captured
- **CP-FAIL-02**: Recovery plan
  - Partial deliverables identified
  - Retry strategy recommended
  - Lessons for future projects captured

**Typical Duration**: 15-30 minutes

**Token Allocation**: Reserve buffer (5-10% of budget)

---

## State Transition Diagram

```
                    ┌──────────────┐
                    │  INITIATED   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
              ┌─────┤   PLANNING   │
              │     └──────┬───────┘
              │            │
              │            ▼
              │     ┌──────────────┐
              │  ┌──┤  EXECUTING   ├──┐
              │  │  └──────┬───────┘  │
              │  │         │          │
              │  │         ▼          │
              │  │  ┌──────────────┐  │
              │  └──┤  VALIDATING  ├──┘
              │     └──────┬───────┘
              │            │
              │            ├──────────┐
              │            │          │
              │            ▼          ▼
              │     ┌──────────┐  ┌──────┐
              └────▶│  FAILED  │  │COMPLETE│
                    └──────────┘  └──────┘
                         │            │
                         │            │
                         ▼            ▼
                    ┌────────────────────┐
                    │   [TERMINATED]     │
                    └────────────────────┘
```

**Legend**:
- Solid lines: Normal forward progression
- Dashed lines: Rollback transitions
- Terminal states: COMPLETE, FAILED

---

## Transition Rules

### Rule 1: Forward Progression

**States**: INITIATED → PLANNING → EXECUTING → VALIDATING → COMPLETE

**Requirements**:
- All checkpoints in current state must pass
- Exit conditions must be satisfied
- No critical blockers preventing transition

**Validation**:
```json
{
  "transition": "PLANNING → EXECUTING",
  "validation": {
    "checkpoints_passed": ["CP-PLAN-01", "CP-PLAN-02", "CP-PLAN-03"],
    "exit_conditions_met": true,
    "blockers": [],
    "approved_by": "pm-agent-self-validation"
  }
}
```

---

### Rule 2: Rollback to Previous State

**Allowed Rollbacks**:
- `EXECUTING → PLANNING`: Major scope change or re-planning needed
- `VALIDATING → EXECUTING`: Validation failed, remediation needed

**Requirements**:
- Rollback reason documented
- Remediation plan created
- Re-entry conditions defined

**Validation**:
```json
{
  "transition": "VALIDATING → EXECUTING",
  "transition_type": "rollback",
  "reason": "Success criteria sc-002 failed: Security scan found 3 critical vulnerabilities",
  "remediation_plan": {
    "tasks": [
      {
        "task_id": "task-remediation-001",
        "description": "Fix critical vulnerabilities identified in security scan",
        "assigned_to": "security",
        "estimated_time": "1 hour",
        "token_allocation": 3000
      }
    ],
    "re_validation_required": true
  }
}
```

---

### Rule 3: Failure Transition

**From Any State → FAILED**

**Triggers**:
- Critical blocker unresolved >2 hours
- Resource exhaustion (tokens <5%, work >20% incomplete)
- Division unresponsive >3 hours
- Unrecoverable technical failure
- Coordinator-initiated abort

**Requirements**:
- Failure reason documented
- Root cause identified
- Escalation to coordinator

**Validation**:
```json
{
  "transition": "EXECUTING → FAILED",
  "transition_type": "failure",
  "trigger": "resource_exhaustion",
  "details": {
    "reason": "Token budget exhausted with 35% of tasks incomplete",
    "tokens_used": 48500,
    "tokens_budget": 50000,
    "tasks_completed": 10,
    "tasks_total": 16,
    "completion_percentage": 62.5
  },
  "escalation_id": "esc-proj-001-003",
  "root_cause": "Task complexity underestimated during planning phase"
}
```

---

### Rule 4: Re-Entry Conditions

**After Rollback, Re-Entry Requires**:

**Rollback from VALIDATING → EXECUTING**:
- Remediation tasks defined
- Resources allocated for remediation
- Re-validation plan created
- Estimated time to fix defined

**Rollback from EXECUTING → PLANNING**:
- Scope change documented and approved
- New planning assumptions defined
- Resource reallocation approved
- Timeline impact assessed

---

### Rule 5: State Immutability

**Once in COMPLETE or FAILED**:
- State cannot change
- No rollback allowed
- PM agent must terminate
- New project required for retry

---

## Checkpoint Definitions

### Checkpoint Structure

```json
{
  "checkpoint_id": "CP-EXEC-01",
  "checkpoint_name": "Progress Tracking",
  "state": "EXECUTING",
  "frequency": "every_status_update",
  "mandatory": true,
  "validation_criteria": [
    {
      "criterion": "tasks_completed_percentage",
      "operator": ">=",
      "expected_value": "timeline_percentage - 10%",
      "severity": "warning"
    },
    {
      "criterion": "token_burn_rate",
      "operator": "<=",
      "expected_value": "budget_allocation_rate + 20%",
      "severity": "critical"
    }
  ],
  "failure_action": "escalate_if_critical",
  "success_action": "continue"
}
```

### Checkpoint Evaluation

**Evaluation Frequency**:
- **INITIATED**: Once at state entry
- **PLANNING**: Once at state exit
- **EXECUTING**: Every 30 minutes (status update cycle)
- **VALIDATING**: Once per success criterion
- **COMPLETE**: Once at state entry
- **FAILED**: Once at state entry

**Checkpoint Status**:
- `PASSED`: All criteria met, proceed
- `WARNING`: Some criteria not met, monitor closely
- `FAILED`: Critical criteria not met, block transition or escalate

**Example Checkpoint Evaluation**:
```json
{
  "checkpoint_id": "CP-EXEC-01",
  "evaluated_at": "2025-12-09T15:30:00Z",
  "status": "WARNING",
  "criteria_results": [
    {
      "criterion": "tasks_completed_percentage",
      "expected": ">=50%",
      "actual": "45%",
      "status": "WARNING",
      "reason": "5% behind schedule due to blocker in task-infra-003"
    },
    {
      "criterion": "token_burn_rate",
      "expected": "<=6500 tokens/hour",
      "actual": "6200 tokens/hour",
      "status": "PASSED"
    }
  ],
  "overall_status": "WARNING",
  "action_taken": "Monitor closely, escalate if falls >10% behind",
  "next_evaluation": "2025-12-09T16:00:00Z"
}
```

---

## Rollback Triggers and Procedures

### Trigger 1: Validation Failure

**Condition**: Success criteria score < minimum_success_score

**Procedure**:
1. Identify failed criteria
2. Assess if remediation is feasible
3. If feasible:
   - Create remediation tasks
   - Allocate resources from reserve
   - Rollback to EXECUTING state
   - Execute remediation tasks
   - Return to VALIDATING state
4. If not feasible:
   - Document failure reason
   - Transition to FAILED state

**Example**:
```json
{
  "rollback_trigger": "validation_failure",
  "from_state": "VALIDATING",
  "to_state": "EXECUTING",
  "triggered_at": "2025-12-09T16:00:00Z",
  "reason": "Success criteria sc-002 failed: Security scan found critical vulnerabilities",
  "failed_criteria": [
    {
      "criterion_id": "sc-002",
      "description": "All security scans pass with no critical findings",
      "actual_result": "3 critical vulnerabilities found",
      "weight": 25
    }
  ],
  "remediation_feasible": true,
  "remediation_plan": {
    "tasks": [
      {
        "task_id": "task-remediation-001",
        "description": "Fix SQL injection vulnerability in auth module",
        "priority": "critical",
        "estimated_time": "30 minutes",
        "token_allocation": 2000
      },
      {
        "task_id": "task-remediation-002",
        "description": "Fix XSS vulnerability in user input handling",
        "priority": "critical",
        "estimated_time": "20 minutes",
        "token_allocation": 1500
      }
    ],
    "total_estimated_time": "1 hour",
    "total_token_allocation": 3500,
    "tokens_available_in_reserve": 5000,
    "feasibility": "FEASIBLE"
  }
}
```

---

### Trigger 2: Scope Change

**Condition**: Major change to project objective or constraints during execution

**Procedure**:
1. Document scope change request
2. Assess impact on current plan
3. If impact >30% of work:
   - Pause current execution
   - Rollback to PLANNING state
   - Re-plan with new scope
   - Get coordinator approval
   - Resume execution
4. If impact <30%:
   - Adjust tasks inline
   - Continue execution

**Example**:
```json
{
  "rollback_trigger": "scope_change",
  "from_state": "EXECUTING",
  "to_state": "PLANNING",
  "triggered_at": "2025-12-09T15:00:00Z",
  "scope_change": {
    "description": "Add multi-region deployment capability",
    "requested_by": "coordinator",
    "impact_assessment": {
      "additional_tasks": 6,
      "additional_divisions": 1,
      "additional_time": "4 hours",
      "additional_tokens": 15000,
      "impact_percentage": 45
    },
    "justification": "Business requirement changed, multi-region now critical",
    "approval_required": true,
    "approved_by": "coordinator",
    "approved_at": "2025-12-09T15:05:00Z"
  },
  "rollback_actions": [
    "Pause all non-critical tasks",
    "Preserve completed work",
    "Re-plan with additional requirements",
    "Get resource extension approval",
    "Resume execution with updated plan"
  ]
}
```

---

### Trigger 3: Resource Exhaustion

**Condition**: Token usage >90% with work >20% incomplete

**Procedure**:
1. Assess remaining work
2. Calculate tokens needed to complete
3. If additional tokens <20% of original budget:
   - Request extension from coordinator
   - If approved, continue
   - If denied, rollback or fail
4. If additional tokens >20%:
   - Escalate to coordinator
   - Evaluate scope reduction
   - Or transition to FAILED

**Example**:
```json
{
  "rollback_trigger": "resource_exhaustion",
  "from_state": "EXECUTING",
  "triggered_at": "2025-12-09T16:30:00Z",
  "resource_status": {
    "tokens_budget": 50000,
    "tokens_used": 46000,
    "tokens_remaining": 4000,
    "usage_percentage": 92,
    "tasks_completed": 12,
    "tasks_total": 16,
    "completion_percentage": 75,
    "work_remaining_percentage": 25
  },
  "assessment": {
    "tokens_needed_to_complete": 8000,
    "tokens_shortfall": 4000,
    "extension_percentage": 8,
    "extension_within_tolerance": true
  },
  "action": "request_extension",
  "extension_request": {
    "requested_tokens": 8000,
    "justification": "Task complexity higher than estimated, all tasks critical",
    "approval_status": "pending",
    "fallback_plan": "Reduce documentation scope if extension denied"
  }
}
```

---

### Trigger 4: Critical Blocker

**Condition**: Task blocked >1 hour on critical path

**Procedure**:
1. Assess blocker severity and impact
2. Attempt resolution within 30 minutes
3. If unresolved:
   - Escalate to coordinator
   - Evaluate workarounds
   - Consider rollback to re-plan
4. If blocker unresolved >2 hours:
   - Mandatory escalation
   - Consider transition to FAILED

**Example**:
```json
{
  "rollback_trigger": "critical_blocker",
  "from_state": "EXECUTING",
  "triggered_at": "2025-12-09T14:00:00Z",
  "blocker": {
    "blocker_id": "block-001",
    "severity": "critical",
    "task_id": "task-infra-002",
    "task_name": "Provision production VPC",
    "description": "Cloud provider API rate limit exceeded, cannot provision VPC",
    "time_blocked": "90 minutes",
    "critical_path": true,
    "blocked_tasks_count": 4,
    "impact": "Blocks security configuration, monitoring setup, and deployment"
  },
  "resolution_attempts": [
    {
      "attempt": 1,
      "approach": "Contact cloud provider support for rate limit increase",
      "result": "24-hour response time, unacceptable",
      "duration": "30 minutes"
    },
    {
      "attempt": 2,
      "approach": "Use smaller VPC configuration to stay under limits",
      "result": "Does not meet security requirements",
      "duration": "20 minutes"
    }
  ],
  "escalation": {
    "escalation_id": "esc-proj-001-block-001",
    "escalated_to": "coordinator",
    "escalated_at": "2025-12-09T14:30:00Z",
    "recommendation": "Pivot to alternative cloud provider OR request emergency rate limit increase",
    "decision_required_by": "2025-12-09T15:00:00Z"
  }
}
```

---

## Progress Tracking Metrics

### Primary Metrics

#### 1. Schedule Performance Index (SPI)

**Formula**: `SPI = Tasks Completed / Tasks Planned (at this point in timeline)`

**Interpretation**:
- `SPI > 1.0`: Ahead of schedule
- `SPI = 1.0`: On schedule
- `SPI < 1.0`: Behind schedule

**Example**:
```json
{
  "metric": "schedule_performance_index",
  "timestamp": "2025-12-09T15:00:00Z",
  "elapsed_time": "5 hours",
  "total_estimated_time": "8 hours",
  "timeline_percentage": 62.5,
  "tasks_planned_by_now": 10,
  "tasks_completed": 9,
  "spi": 0.9,
  "status": "slightly_behind",
  "variance": "-10%",
  "action": "Monitor closely, identify bottlenecks"
}
```

---

#### 2. Cost Performance Index (CPI)

**Formula**: `CPI = Token Budget Allocation / Tokens Used (at this point)`

**Interpretation**:
- `CPI > 1.0`: Under budget (efficient)
- `CPI = 1.0`: On budget
- `CPI < 1.0`: Over budget

**Example**:
```json
{
  "metric": "cost_performance_index",
  "timestamp": "2025-12-09T15:00:00Z",
  "elapsed_time": "5 hours",
  "total_estimated_time": "8 hours",
  "timeline_percentage": 62.5,
  "expected_token_usage": 31250,
  "actual_token_usage": 33000,
  "cpi": 0.947,
  "status": "slightly_over_budget",
  "variance": "+5.6%",
  "action": "Optimize remaining tasks, consider reserve usage"
}
```

---

#### 3. Milestone Achievement Rate

**Formula**: `MAR = Milestones Completed / Milestones Planned (at this point)`

**Example**:
```json
{
  "metric": "milestone_achievement_rate",
  "timestamp": "2025-12-09T15:00:00Z",
  "milestones_total": 5,
  "milestones_planned_by_now": 3,
  "milestones_completed": 2,
  "mar": 0.667,
  "status": "at_risk",
  "variance": "-33%",
  "missed_milestones": [
    {
      "milestone_id": "milestone-3",
      "name": "Security Configuration Complete",
      "planned_completion": "2025-12-09T14:00:00Z",
      "actual_status": "in_progress",
      "delay": "1 hour",
      "reason": "Blocker in infrastructure VPC setup"
    }
  ]
}
```

---

#### 4. Quality Gate Pass Rate

**Formula**: `QGPR = Quality Gates Passed / Quality Gates Evaluated`

**Example**:
```json
{
  "metric": "quality_gate_pass_rate",
  "timestamp": "2025-12-09T15:00:00Z",
  "quality_gates_total": 12,
  "quality_gates_evaluated": 8,
  "quality_gates_passed": 7,
  "quality_gates_failed": 1,
  "qgpr": 0.875,
  "status": "good",
  "failed_gates": [
    {
      "gate_id": "qg-sec-001",
      "task_id": "task-dev-003",
      "gate_name": "Security code review",
      "failure_reason": "SQL injection vulnerability found",
      "remediation_status": "in_progress"
    }
  ]
}
```

---

### Secondary Metrics

#### 5. Blocker Resolution Time (BRT)

**Average time to resolve blockers**

**Example**:
```json
{
  "metric": "blocker_resolution_time",
  "timestamp": "2025-12-09T15:00:00Z",
  "blockers_total": 3,
  "blockers_resolved": 2,
  "blockers_active": 1,
  "average_resolution_time": "35 minutes",
  "sla_target": "30 minutes",
  "sla_compliance": 66.7,
  "status": "needs_improvement"
}
```

---

#### 6. Division Response Time (DRT)

**Average time for divisions to acknowledge and complete tasks**

**Example**:
```json
{
  "metric": "division_response_time",
  "timestamp": "2025-12-09T15:00:00Z",
  "divisions": [
    {
      "division": "development",
      "handoffs_sent": 5,
      "avg_acknowledgment_time": "15 minutes",
      "avg_completion_time": "1.8 hours",
      "sla_compliance": 100,
      "status": "excellent"
    },
    {
      "division": "security",
      "handoffs_sent": 3,
      "avg_acknowledgment_time": "45 minutes",
      "avg_completion_time": "2.2 hours",
      "sla_compliance": 67,
      "status": "needs_improvement"
    }
  ]
}
```

---

#### 7. Rework Rate

**Percentage of tasks requiring rework due to quality issues**

**Example**:
```json
{
  "metric": "rework_rate",
  "timestamp": "2025-12-09T15:00:00Z",
  "tasks_completed": 12,
  "tasks_requiring_rework": 2,
  "rework_rate": 16.7,
  "threshold": 20,
  "status": "acceptable",
  "rework_tasks": [
    {
      "task_id": "task-dev-002",
      "reason": "Failed security review",
      "rework_time": "45 minutes",
      "rework_tokens": 2000
    }
  ]
}
```

---

### Metric Collection Frequency

| Metric | Frequency | State |
|--------|-----------|-------|
| SPI | Every status update (30 min) | EXECUTING |
| CPI | Every status update (30 min) | EXECUTING |
| MAR | On milestone events | All states |
| QGPR | On quality gate events | EXECUTING, VALIDATING |
| BRT | On blocker resolution | EXECUTING |
| DRT | On handoff completion | EXECUTING |
| Rework Rate | On task completion | EXECUTING |

---

## Blocker Escalation Paths

### Escalation Levels

#### Level 1: PM Self-Resolution (0-30 minutes)

**Actions**:
- Assess blocker severity
- Attempt quick resolution
- Contact blocking division directly
- Evaluate workarounds
- Reallocate resources if needed

**No Escalation Needed If**: Blocker resolved within 30 minutes

---

#### Level 2: Division Master Escalation (30-60 minutes)

**Trigger**: Blocker unresolved after 30 minutes

**Actions**:
- Escalate to division master
- Request prioritization
- Provide additional resources
- Evaluate alternative approaches
- Update risk register

**Escalation Format**:
```json
{
  "escalation_level": 2,
  "escalated_to": "development_master",
  "blocker_id": "block-002",
  "time_blocked": "35 minutes",
  "request": "Prioritize task-dev-004, blocking critical path",
  "additional_resources": {
    "tokens": 2000,
    "workers": "spawn_additional_worker_if_needed"
  }
}
```

---

#### Level 3: Coordinator Master Escalation (60-120 minutes)

**Trigger**: Blocker unresolved after 60 minutes OR critical blocker

**Actions**:
- Escalate to coordinator master
- Provide full context and impact analysis
- Request architectural decision if needed
- Request cross-division coordination
- Consider scope changes

**Escalation Format**:
```json
{
  "escalation_level": 3,
  "escalated_to": "coordinator",
  "blocker_id": "block-003",
  "time_blocked": "75 minutes",
  "severity": "critical",
  "impact": {
    "blocked_tasks": 5,
    "critical_path_blocked": true,
    "timeline_impact": "+2 hours",
    "divisions_affected": ["infrastructure", "security", "monitoring"]
  },
  "resolution_attempts": [
    {
      "level": 1,
      "duration": "30 minutes",
      "result": "failed"
    },
    {
      "level": 2,
      "duration": "30 minutes",
      "result": "failed"
    }
  ],
  "recommendation": "Architectural decision needed: Change cloud provider OR request emergency quota increase",
  "decision_required_by": "2025-12-09T16:00:00Z"
}
```

---

#### Level 4: Meta-Agent Escalation (>120 minutes OR project-threatening)

**Trigger**:
- Blocker unresolved after 2 hours
- Project failure imminent
- Requires system-level intervention

**Actions**:
- Escalate to cortex meta-agent
- Request system-level intervention
- Consider project suspension
- Evaluate alternative strategies

**Escalation Format**:
```json
{
  "escalation_level": 4,
  "escalated_to": "cortex_meta_agent",
  "blocker_id": "block-004",
  "time_blocked": "135 minutes",
  "severity": "critical",
  "project_at_risk": true,
  "impact": {
    "project_failure_probability": 85,
    "timeline_impact": "project cannot complete",
    "resource_waste": "30k tokens already invested"
  },
  "request": "System-level intervention required, project cannot proceed without resolution",
  "options": [
    "Suspend project and retry with different approach",
    "Pivot to alternative solution",
    "Abort project and document learnings"
  ]
}
```

---

### Escalation Decision Matrix

| Blocker Type | Severity | Time Blocked | Escalation Level | Action |
|--------------|----------|--------------|------------------|--------|
| Dependency | Low | <30 min | 1 | PM self-resolve |
| Dependency | Medium | 30-60 min | 2 | Division master |
| Dependency | High | 60-120 min | 3 | Coordinator |
| Dependency | Critical | >120 min | 4 | Meta-agent |
| Resource | Low | <30 min | 1 | PM self-resolve |
| Resource | Medium | 30-60 min | 2 | Division master |
| Resource | High | Any | 3 | Coordinator |
| Resource | Critical | Any | 3 | Coordinator |
| Technical | Low | <60 min | 1-2 | PM/Division |
| Technical | Medium | 60-120 min | 2-3 | Division/Coordinator |
| Technical | High | Any | 3 | Coordinator |
| Technical | Critical | Any | 3-4 | Coordinator/Meta |
| External | Any | Any | 3 | Coordinator |

---

## Resource Reallocation During Execution

### Reallocation Triggers

1. **Task Complexity Higher Than Estimated**
   - Actual tokens used >120% of allocation
   - Estimated time exceeded significantly

2. **Division Ahead of Schedule**
   - Tasks completed faster than planned
   - Tokens under-utilized

3. **Critical Path Priority Shift**
   - New task becomes critical
   - Needs additional resources to unblock

4. **Blocker Resolution Requires Resources**
   - Unexpected rework needed
   - Remediation tasks created

---

### Reallocation Procedures

#### Procedure 1: Reallocate from Completed Phases

**When**: Tasks in a phase complete under budget

**Steps**:
1. Calculate tokens saved in completed phase
2. Add to reserve pool
3. Reallocate to active tasks as needed

**Example**:
```json
{
  "reallocation_id": "realloc-001",
  "timestamp": "2025-12-09T14:00:00Z",
  "source_phase": "phase-2",
  "source_phase_allocation": 3000,
  "source_phase_actual": 2400,
  "tokens_saved": 600,
  "reallocation_target": "reserve_pool",
  "reserve_pool_before": 5000,
  "reserve_pool_after": 5600,
  "reason": "Planning phase completed efficiently, adding savings to reserve"
}
```

---

#### Procedure 2: Reallocate from Low-Priority to High-Priority

**When**: Critical task needs more resources, non-critical tasks can be reduced

**Steps**:
1. Identify low-priority tasks
2. Evaluate scope reduction options
3. Reallocate tokens to critical task
4. Update task expectations

**Example**:
```json
{
  "reallocation_id": "realloc-002",
  "timestamp": "2025-12-09T15:00:00Z",
  "source_task": "task-doc-003",
  "source_task_priority": "low",
  "source_task_allocation": 3000,
  "source_task_new_allocation": 2000,
  "tokens_reallocated": 1000,
  "target_task": "task-sec-002",
  "target_task_priority": "critical",
  "target_task_old_allocation": 4000,
  "target_task_new_allocation": 5000,
  "reason": "Security review more complex than estimated, reducing documentation scope to compensate"
}
```

---

#### Procedure 3: Borrow from Reserve Pool

**When**: Unexpected work requires additional resources

**Steps**:
1. Assess reserve pool balance
2. Evaluate if reserve is sufficient
3. Allocate from reserve to task
4. Update reserve tracking

**Example**:
```json
{
  "reallocation_id": "realloc-003",
  "timestamp": "2025-12-09T16:00:00Z",
  "source": "reserve_pool",
  "reserve_pool_before": 5600,
  "tokens_allocated": 2000,
  "reserve_pool_after": 3600,
  "target_task": "task-remediation-001",
  "reason": "Unplanned remediation task for security vulnerabilities",
  "reserve_threshold": "10% of total budget",
  "reserve_status": "adequate",
  "warning": "Reserve at 7.2% of budget, monitor closely"
}
```

---

### Reallocation Constraints

1. **Reserve Minimum**: Always maintain 5% of total budget in reserve
2. **Task Minimum**: Don't reduce task allocation below 50% of estimate
3. **Approval Required**: Reallocations >20% of budget require coordinator approval
4. **Documentation**: All reallocations must be documented with justification

---

## Parallel vs Sequential Task Handling

### Parallel Execution

**When to Use**:
- Tasks have no dependencies on each other
- Different divisions can work independently
- Objective is to minimize timeline

**Benefits**:
- Compressed schedule
- Maximum throughput
- Division parallelism

**Risks**:
- Integration issues
- Resource contention
- Coordination overhead

**Example**:
```json
{
  "execution_pattern": "parallel",
  "tasks": [
    {
      "task_id": "task-dev-001",
      "division": "development",
      "start_time": "2025-12-09T14:00:00Z",
      "dependencies": []
    },
    {
      "task_id": "task-sec-001",
      "division": "security",
      "start_time": "2025-12-09T14:00:00Z",
      "dependencies": []
    },
    {
      "task_id": "task-infra-001",
      "division": "infrastructure",
      "start_time": "2025-12-09T14:00:00Z",
      "dependencies": []
    }
  ],
  "coordination_strategy": "Independent execution, integration phase after all complete",
  "estimated_timeline": "2 hours (vs 6 hours sequential)"
}
```

---

### Sequential Execution

**When to Use**:
- Tasks have strict dependencies
- Output of one task feeds next task
- Quality gates between tasks

**Benefits**:
- Clear dependencies
- Early error detection
- Incremental validation

**Risks**:
- Longer timeline
- Delays cascade
- Division idle time

**Example**:
```json
{
  "execution_pattern": "sequential",
  "tasks": [
    {
      "task_id": "task-dev-002",
      "division": "development",
      "start_time": "2025-12-09T14:00:00Z",
      "dependencies": [],
      "completion_time": "2025-12-09T16:00:00Z"
    },
    {
      "task_id": "task-sec-002",
      "division": "security",
      "start_time": "2025-12-09T16:00:00Z",
      "dependencies": ["task-dev-002"],
      "completion_time": "2025-12-09T17:30:00Z"
    },
    {
      "task_id": "task-infra-002",
      "division": "infrastructure",
      "start_time": "2025-12-09T17:30:00Z",
      "dependencies": ["task-sec-002"],
      "completion_time": "2025-12-09T19:00:00Z"
    }
  ],
  "coordination_strategy": "Each task validated before next begins",
  "estimated_timeline": "5 hours"
}
```

---

### Hybrid Execution (Wave-Based)

**When to Use**:
- Mix of dependent and independent work
- Multiple iterations or environments
- Want balance of speed and quality

**Pattern**:
- Parallel execution within waves
- Sequential progression between waves
- Validation gates between waves

**Example**:
```json
{
  "execution_pattern": "hybrid_wave_based",
  "waves": [
    {
      "wave_id": "wave-1",
      "wave_name": "Development Environment",
      "execution_mode": "parallel",
      "tasks": ["task-dev-001", "task-sec-001", "task-infra-001"],
      "validation_gate": "Dev environment validated",
      "estimated_duration": "2 hours"
    },
    {
      "wave_id": "wave-2",
      "wave_name": "Staging Environment",
      "execution_mode": "parallel",
      "tasks": ["task-dev-002", "task-sec-002", "task-infra-002"],
      "dependencies": ["wave-1"],
      "validation_gate": "Staging environment validated",
      "estimated_duration": "2 hours"
    },
    {
      "wave_id": "wave-3",
      "wave_name": "Production Environment",
      "execution_mode": "sequential",
      "tasks": ["task-infra-003", "task-sec-003", "task-mon-003"],
      "dependencies": ["wave-2"],
      "validation_gate": "Production deployed and validated",
      "estimated_duration": "3 hours"
    }
  ],
  "total_estimated_timeline": "7 hours (vs 9 hours fully sequential, 4 hours fully parallel)"
}
```

---

## Dependency Management

### Dependency Types

#### 1. Blocking Dependency (Hard)

**Definition**: Task B cannot start until Task A is 100% complete

**Symbol**: `A → B`

**Example**:
```json
{
  "dependency_id": "dep-001",
  "type": "blocking",
  "from_task": "task-infra-001",
  "from_task_name": "Provision VPC",
  "to_task": "task-sec-001",
  "to_task_name": "Configure firewall rules",
  "description": "VPC must exist before firewall rules can be configured",
  "status": "active",
  "blocking_until": "task-infra-001 status = completed"
}
```

---

#### 2. Soft Dependency

**Definition**: Task B can start, but may need to adjust based on Task A

**Symbol**: `A ⇢ B`

**Example**:
```json
{
  "dependency_id": "dep-002",
  "type": "soft",
  "from_task": "task-dev-001",
  "from_task_name": "Design API schema",
  "to_task": "task-doc-001",
  "to_task_name": "Write API documentation",
  "description": "Documentation can start with draft schema, will update when final schema ready",
  "status": "active",
  "coordination_note": "Doc team start with draft, will iterate"
}
```

---

#### 3. External Dependency

**Definition**: Task depends on external system or approval outside PM control

**Symbol**: `[EXT] → A`

**Example**:
```json
{
  "dependency_id": "dep-003",
  "type": "external",
  "external_system": "Cloud Provider Quota Approval",
  "to_task": "task-infra-002",
  "to_task_name": "Deploy production cluster",
  "description": "Cannot deploy until cloud provider approves quota increase",
  "status": "active",
  "external_status_check": "Manual check with cloud provider",
  "estimated_resolution": "2025-12-09T18:00:00Z",
  "risk_level": "high"
}
```

---

### Dependency Graph

**Representation**:
```
task-dev-001 ───────┐
                    ▼
task-infra-001 → task-sec-001 → task-mon-001
                    ▲
task-data-001 ──────┘
```

**Graph Properties**:
- **Critical Path**: Longest path through dependency graph
- **Parallel Branches**: Tasks with no dependencies can run in parallel
- **Bottlenecks**: Tasks with many dependents

**Critical Path Identification**:
```json
{
  "critical_path": [
    "task-infra-001",
    "task-sec-001",
    "task-mon-001"
  ],
  "critical_path_duration": "5 hours",
  "total_project_duration": "5 hours",
  "critical_path_tasks_percentage": 37.5,
  "monitoring": "Monitor critical path tasks closely, any delay impacts overall timeline"
}
```

---

### Dependency Validation

**Pre-Execution Validation**:
1. Check for circular dependencies
2. Ensure at least one task has no blockers (can start immediately)
3. Validate external dependencies have monitoring

**Example Validation**:
```json
{
  "dependency_validation": {
    "circular_dependencies_found": false,
    "tasks_with_no_blockers": 3,
    "external_dependencies_count": 1,
    "external_dependencies_monitored": true,
    "validation_status": "PASSED",
    "warnings": [
      "External dependency dep-003 may delay timeline by up to 4 hours"
    ]
  }
}
```

---

### Dependency Resolution Flow

**When Dependency Resolved**:
1. Blocking task completes
2. PM updates dependency status to "resolved"
3. PM checks dependent tasks
4. If all dependencies resolved, task becomes "ready"
5. PM immediately issues handoff to appropriate division

**Example Flow**:
```json
{
  "dependency_resolution_event": {
    "timestamp": "2025-12-09T16:00:00Z",
    "dependency_id": "dep-001",
    "from_task": "task-infra-001",
    "from_task_status": "completed",
    "to_task": "task-sec-001",
    "to_task_status_before": "blocked",
    "to_task_status_after": "ready",
    "action_taken": "Issue handoff to security division",
    "handoff_id": "pm-to-sec-001",
    "handoff_issued_at": "2025-12-09T16:01:00Z"
  }
}
```

---

## Completion Criteria Per State

### INITIATED → PLANNING

**Required**:
- [ ] Project directory created
- [ ] Project state file initialized from template
- [ ] PM agent loaded template and playbook
- [ ] All divisions identified
- [ ] Handoff directories created
- [ ] PM reports ready status to coordinator

**Validation**:
```bash
# Check directory structure
test -d "coordination/project-management/projects/${PROJECT_ID}"
test -f "coordination/project-management/projects/${PROJECT_ID}/project-state.json"
test -d "coordination/project-management/projects/${PROJECT_ID}/handoffs"

# Check state file
jq '.project_metadata.status == "initiated"' project-state.json
jq '.current_phase == "initiation"' project-state.json
```

---

### PLANNING → EXECUTING

**Required**:
- [ ] All tasks defined with acceptance criteria
- [ ] Dependencies mapped (no circular dependencies)
- [ ] Token allocation sums to <= total budget
- [ ] All divisions notified of upcoming tasks
- [ ] Risk register initialized with mitigation strategies
- [ ] At least one task ready to execute (no blocking dependencies)
- [ ] Milestone schedule created

**Validation**:
```bash
# Check all tasks have acceptance criteria
jq '.tasks | all(.acceptance_criteria | length > 0)' project-state.json

# Check token allocation
ALLOCATED=$(jq '.resource_allocation.tokens_allocated' project-state.json)
BUDGET=$(jq '.resource_allocation.total_token_budget' project-state.json)
test $ALLOCATED -le $BUDGET

# Check for circular dependencies
# (Requires custom validation logic)

# Check at least one ready task
jq '.tasks | any(.status == "ready" or (.dependencies | length == 0))' project-state.json
```

---

### EXECUTING → VALIDATING

**Required**:
- [ ] All tasks status = completed
- [ ] All deliverables received and logged
- [ ] All quality gates passed
- [ ] No critical blockers remaining
- [ ] All milestones achieved
- [ ] Resource usage within budget (+10% tolerance)

**Validation**:
```bash
# Check all tasks completed
jq '.tasks | all(.status == "completed")' project-state.json

# Check all deliverables received
jq '.tasks | all(.deliverables | length > 0)' project-state.json

# Check no critical blockers
jq '.blockers | all(.status == "resolved")' project-state.json

# Check resource usage
USED=$(jq '.resource_allocation.tokens_used' project-state.json)
BUDGET=$(jq '.resource_allocation.total_token_budget' project-state.json)
TOLERANCE=$(echo "$BUDGET * 1.1" | bc)
test $USED -le $TOLERANCE
```

---

### VALIDATING → COMPLETE

**Required**:
- [ ] All success criteria validated
- [ ] Success criteria weighted score >= minimum_success_score (80%)
- [ ] All deliverables validated and archived
- [ ] Documentation complete
- [ ] No critical issues outstanding
- [ ] Final metrics calculated

**Validation**:
```bash
# Check success criteria score
SCORE=$(jq '.success_criteria | map(select(.status == "passed") | .weight) | add' project-state.json)
MIN_SCORE=$(jq '.minimum_success_score' project-state.json)
test $SCORE -ge $MIN_SCORE

# Check all criteria evaluated
jq '.success_criteria | all(.status != "pending")' project-state.json

# Check documentation
jq '.artifacts.documents | length > 0' project-state.json
```

---

### COMPLETE (Final State)

**Required**:
- [ ] Project completion report created
- [ ] Lessons learned documented
- [ ] Knowledge base updated
- [ ] All artifacts archived
- [ ] Final status reported to coordinator
- [ ] Handoff directories cleaned
- [ ] PM agent ready to terminate

**Validation**:
```bash
# Check completion report
test -f "coordination/project-management/projects/${PROJECT_ID}/artifacts/reports/completion-report.json"

# Check lessons learned
jq '.lessons_learned | length > 0' project-state.json

# Check knowledge base updates
# (Check knowledge base has new entries)

# Check artifacts archived
jq '.artifacts | (.deliverables | length > 0) and (.documents | length > 0) and (.reports | length > 0)' project-state.json
```

---

## State Machine Implementation

### State Management Functions

```bash
#!/bin/bash
# pm-state-machine-functions.sh

# Get current state
get_current_state() {
  local project_id=$1
  jq -r '.project_metadata.status' "coordination/project-management/projects/${project_id}/project-state.json"
}

# Validate state transition
validate_transition() {
  local project_id=$1
  local from_state=$2
  local to_state=$3

  # Load transition rules
  local valid_transitions=$(jq -r \
    ".transition_rules[] | select(.from_state == \"$from_state\" and .to_state == \"$to_state\") | .allowed" \
    coordination/project-management/pm-state-machine.json)

  if [[ "$valid_transitions" == "true" ]]; then
    return 0
  else
    return 1
  fi
}

# Execute state transition
transition_state() {
  local project_id=$1
  local from_state=$2
  local to_state=$3
  local reason=$4

  # Validate transition
  if ! validate_transition "$project_id" "$from_state" "$to_state"; then
    echo "ERROR: Invalid transition $from_state → $to_state"
    return 1
  fi

  # Execute transition
  jq --arg to_state "$to_state" \
     --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --arg reason "$reason" \
     '.project_metadata.status = $to_state |
      .project_metadata.state_changed_at = $timestamp |
      .state_transitions += [{
        "from": $from_state,
        "to": $to_state,
        "timestamp": $timestamp,
        "reason": $reason
      }]' \
     "coordination/project-management/projects/${project_id}/project-state.json" > tmp.json

  mv tmp.json "coordination/project-management/projects/${project_id}/project-state.json"

  echo "State transition: $from_state → $to_state"
}

# Evaluate checkpoint
evaluate_checkpoint() {
  local project_id=$1
  local checkpoint_id=$2

  # Load checkpoint configuration
  local checkpoint=$(jq \
    ".checkpoints[] | select(.checkpoint_id == \"$checkpoint_id\")" \
    coordination/project-management/pm-state-machine.json)

  # Evaluate criteria (implementation depends on specific checkpoint)
  # Return: PASSED, WARNING, or FAILED
}

# Check if can proceed to next state
can_proceed() {
  local project_id=$1
  local current_state=$2

  # Get checkpoints for current state
  local checkpoints=$(jq -r \
    ".checkpoints[] | select(.state == \"$current_state\" and .mandatory == true) | .checkpoint_id" \
    coordination/project-management/pm-state-machine.json)

  # Evaluate all mandatory checkpoints
  for cp in $checkpoints; do
    local result=$(evaluate_checkpoint "$project_id" "$cp")
    if [[ "$result" == "FAILED" ]]; then
      echo "Cannot proceed: Checkpoint $cp failed"
      return 1
    fi
  done

  return 0
}
```

---

## Dashboard Integration

### State Visualization

**Dashboard displays**:
- Current state with visual indicator
- Time in current state
- Progress through states (progress bar)
- Next state and transition conditions

**Example Dashboard Data**:
```json
{
  "project_id": "proj-001",
  "current_state": "EXECUTING",
  "current_state_icon": "⚙️",
  "current_state_color": "#3498db",
  "time_in_state": "3 hours 45 minutes",
  "state_progress": {
    "states_completed": ["INITIATED", "PLANNING"],
    "current_state": "EXECUTING",
    "states_remaining": ["VALIDATING", "COMPLETE"],
    "overall_progress_percentage": 60
  },
  "next_state": "VALIDATING",
  "transition_conditions": {
    "all_tasks_completed": "8/12 (67%)",
    "quality_gates_passed": "6/8 (75%)",
    "blockers_resolved": "2/3 (67%)",
    "ready_to_transition": false
  },
  "checkpoints": {
    "CP-EXEC-01": "WARNING",
    "CP-EXEC-02": "PASSED",
    "CP-EXEC-03": "PASSED",
    "CP-EXEC-04": "WARNING"
  }
}
```

---

## Summary

The PM State Machine provides:

1. **Six Well-Defined States**: INITIATED, PLANNING, EXECUTING, VALIDATING, COMPLETE, FAILED
2. **Clear Transition Rules**: Valid transitions with validation and rollback support
3. **Checkpoint System**: 15+ checkpoints ensuring quality at each stage
4. **Rollback Procedures**: 4 rollback triggers with detailed remediation processes
5. **Progress Metrics**: 7 primary metrics tracking schedule, cost, quality
6. **Escalation Framework**: 4-level escalation with decision matrix
7. **Resource Management**: Dynamic reallocation during execution
8. **Dependency Handling**: Blocking, soft, and external dependencies with critical path analysis
9. **Completion Criteria**: Clear exit conditions for each state transition

This state machine enables predictable, measurable, and recoverable project execution in the Cortex system.

---

## Version

**PM State Machine Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintained By**: Cortex Development Master

## Related Documentation

- `/coordination/project-management/pm-template.md` - PM agent specification
- `/coordination/project-management/pm-playbook.md` - Execution patterns
- `/coordination/project-management/project-template.json` - Project schema
- `/coordination/project-management/pm-state-machine.json` - State machine configuration
