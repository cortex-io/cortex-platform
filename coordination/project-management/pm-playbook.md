# Project Manager Playbook

## Purpose

This playbook provides proven patterns, strategies, and examples for PM agents managing projects in the Cortex automation system. Use these patterns to coordinate effectively, avoid common pitfalls, and deliver projects successfully.

## Common Project Patterns

### Pattern 1: Sequential Multi-Division

**When to Use**: Tasks across divisions must occur in strict sequence due to dependencies.

**Example**: Security audit must complete before production deployment.

**Structure**:
```
Phase 1: Security (Division A)
  └─> Phase 2: Infrastructure (Division B)
      └─> Phase 3: Monitoring (Division C)
```

**Coordination Strategy**:
1. Issue handoff to Division A immediately
2. Monitor Division A progress closely
3. Pre-notify Division B of incoming work
4. Upon Division A completion, immediately handoff to Division B
5. Continue pattern through all divisions

**Timeline Optimization**:
- Use wait time to prepare next phase
- Pre-validate division readiness
- Buffer time between phases for handoff (15 min)

**Risk**: Delays cascade. Mitigate by tight monitoring and early escalation.

---

### Pattern 2: Parallel Multi-Division

**When to Use**: Independent work can occur simultaneously across divisions.

**Example**: Frontend, backend, and database work with no cross-dependencies.

**Structure**:
```
Phase 1: Parallel Execution
├─> Division A: Frontend
├─> Division B: Backend
└─> Division C: Database

Phase 2: Integration
└─> Division D: Integration Testing
```

**Coordination Strategy**:
1. Issue all handoffs simultaneously at project start
2. Monitor all divisions independently
3. Track completion rates across divisions
4. Identify lagging divisions early
5. Once all complete, move to integration phase

**Timeline Optimization**:
- Maximize parallelism to compress schedule
- Allocate more resources to critical path
- Plan integration phase while execution ongoing

**Risk**: Integration issues. Mitigate with clear interfaces and early integration tests.

---

### Pattern 3: Wave-Based Execution

**When to Use**: Multiple iterations of similar work across divisions.

**Example**: Deploy to dev, staging, then production environments.

**Structure**:
```
Wave 1 (Dev):
├─> Infrastructure setup
├─> Application deployment
└─> Validation

Wave 2 (Staging):
├─> Infrastructure setup
├─> Application deployment
└─> Validation

Wave 3 (Production):
├─> Infrastructure setup
├─> Application deployment
└─> Validation
```

**Coordination Strategy**:
1. Complete full wave before starting next
2. Learn from each wave, adjust approach
3. Increase validation rigor with each wave
4. Use same divisions across waves for consistency

**Timeline Optimization**:
- Compress later waves using learnings
- Automate repetitive tasks after Wave 1
- Overlap planning for Wave N+1 with execution of Wave N

**Risk**: Wave 1 issues repeat. Mitigate with thorough wave retrospectives.

---

### Pattern 4: Hub-and-Spoke

**When to Use**: One central component with multiple dependent services.

**Example**: Deploy core API, then multiple microservices that depend on it.

**Structure**:
```
Hub: Core API (Division A)
  ├─> Spoke 1: Auth Service (Division B)
  ├─> Spoke 2: Data Service (Division C)
  ├─> Spoke 3: Notification Service (Division D)
  └─> Spoke 4: Analytics Service (Division E)
```

**Coordination Strategy**:
1. Prioritize hub completion
2. Pre-coordinate with all spoke divisions
3. Once hub deployed, fan out to all spokes in parallel
4. Monitor spoke progress independently
5. Handle spoke issues without blocking other spokes

**Timeline Optimization**:
- Get hub done fast, then full parallelism
- Provide hub interface docs to spokes early
- Allow spokes to start dev work before hub complete

**Risk**: Hub changes break spokes. Mitigate with interface versioning.

---

### Pattern 5: Exploratory with Pivot

**When to Use**: Unclear best approach, need to try options and select winner.

**Example**: Performance optimization - try multiple strategies, keep best.

**Structure**:
```
Phase 1: Exploration (Parallel)
├─> Approach A (Worker 1)
├─> Approach B (Worker 2)
└─> Approach C (Worker 3)

Phase 2: Evaluation
└─> Compare results, select winner

Phase 3: Implement Winner
└─> Full implementation of selected approach
```

**Coordination Strategy**:
1. Define clear evaluation criteria upfront
2. Spawn multiple workers/tasks in parallel
3. Set time box for exploration (e.g., 2 hours)
4. Evaluate all results objectively
5. Commit to winning approach fully

**Timeline Optimization**:
- Keep exploration time-boxed
- Ensure evaluation criteria are measurable
- Quick decision, fast pivot

**Risk**: Analysis paralysis. Mitigate with strict time boxes and decision criteria.

---

## Multi-Division Coordination Examples

### Example 1: Full-Stack Feature Deployment

**Divisions Involved**: Development, Security, Infrastructure, Documentation

**Objective**: Deploy new payment processing feature to production.

**Coordination Flow**:

```
┌─────────────────────────────────────────────────────┐
│ PM: Payment Feature Deployment Project              │
└─────────────────────────────────────────────────────┘

Phase 1: Development (Parallel)
├─> Dev Task 1: Backend payment API (2h, 8k tokens)
├─> Dev Task 2: Frontend payment UI (2h, 7k tokens)
└─> Dev Task 3: Database schema updates (1h, 3k tokens)

Phase 2: Security Review (Sequential after Dev)
├─> Sec Task 1: Code security audit (1h, 4k tokens)
├─> Sec Task 2: PCI compliance check (1h, 4k tokens)
└─> Sec Task 3: Penetration testing (1.5h, 6k tokens)

Phase 3: Infrastructure (After Security Pass)
├─> Infra Task 1: Deploy to staging (0.5h, 2k tokens)
├─> Infra Task 2: Run integration tests (1h, 3k tokens)
├─> Infra Task 3: Deploy to production (0.5h, 2k tokens)
└─> Infra Task 4: Monitor rollout (1h, 2k tokens)

Phase 4: Documentation (Parallel with Infra)
├─> Doc Task 1: API documentation (1h, 3k tokens)
├─> Doc Task 2: User guide (1h, 3k tokens)
└─> Doc Task 3: Runbook (0.5h, 2k tokens)
```

**Total Estimated Time**: 8 hours (with parallelism)
**Total Token Budget**: 50k tokens

**Key Coordination Points**:
1. **Hour 0**: Kick off all Phase 1 dev tasks in parallel
2. **Hour 2**: Dev tasks complete, immediately handoff to security
3. **Hour 2-5**: Security review, doc team starts work in parallel
4. **Hour 5**: Security pass, handoff to infrastructure
5. **Hour 5-7**: Infrastructure deployment
6. **Hour 7**: Documentation complete, infra monitoring ongoing
7. **Hour 8**: Project complete, PM closure phase

**Handoff Sequence**:
```bash
# Hour 0: Kick off development
pm-to-dev-backend.json
pm-to-dev-frontend.json
pm-to-dev-database.json

# Hour 2: Handoff to security
dev-to-pm-backend-complete.json
dev-to-pm-frontend-complete.json
dev-to-pm-database-complete.json
pm-to-sec-audit.json
pm-to-sec-compliance.json
pm-to-sec-pentest.json

# Hour 2: Also kick off documentation (parallel)
pm-to-doc-api.json
pm-to-doc-userguide.json
pm-to-doc-runbook.json

# Hour 5: Handoff to infrastructure
sec-to-pm-audit-pass.json
sec-to-pm-compliance-pass.json
sec-to-pm-pentest-pass.json
pm-to-infra-staging.json

# Hour 6: Infrastructure continues
infra-to-pm-staging-complete.json
pm-to-infra-integration-tests.json

# Hour 7: Production deployment
infra-to-pm-tests-pass.json
pm-to-infra-production-deploy.json

# Hour 8: Project complete
infra-to-pm-deploy-complete.json
doc-to-pm-docs-complete.json
pm-to-coordinator-project-complete.json
```

**Risk Management**:
- Risk 1: Security audit finds critical issue
  - Mitigation: Allocate 4h buffer for fixes, loop back to dev
- Risk 2: Integration tests fail in staging
  - Mitigation: Rollback capability, debug budget of 2h

---

### Example 2: Infrastructure Migration

**Divisions Involved**: Infrastructure, Security, Data, Monitoring

**Objective**: Migrate production workloads from AWS to GCP.

**Coordination Flow**:

```
Phase 1: Assessment & Planning
├─> Infra: Current state assessment (1h)
├─> Security: Compliance requirements (1h)
└─> Data: Data migration strategy (1h)

Phase 2: Setup (Sequential, foundations first)
├─> Infra: GCP project setup (0.5h)
├─> Security: IAM and network policies (1h)
├─> Infra: VPC and networking (1h)
└─> Monitoring: Observability stack (1.5h)

Phase 3: Migration (Wave-based)
Wave 1 (Non-critical services, 10%):
├─> Data: Migrate databases (2h)
├─> Infra: Deploy services (1.5h)
└─> Monitoring: Validate metrics (0.5h)

Wave 2 (Secondary services, 40%):
├─> Data: Migrate databases (3h)
├─> Infra: Deploy services (2.5h)
└─> Monitoring: Validate metrics (0.5h)

Wave 3 (Critical services, 50%):
├─> Data: Migrate databases (4h)
├─> Infra: Deploy services (3h)
└─> Monitoring: Validate metrics (1h)

Phase 4: Cutover & Validation
├─> Infra: DNS cutover (0.5h)
├─> Monitoring: Traffic validation (1h)
└─> Security: Post-migration audit (1h)
```

**Total Estimated Time**: 24 hours over multiple sessions
**Total Token Budget**: 120k tokens

**PM Strategy**:
- Break into 3 separate PM sessions (8h each)
- Session 1: Assessment + Setup
- Session 2: Waves 1 & 2
- Session 3: Wave 3 + Cutover

**Critical Success Factor**: No data loss during migration.
**Rollback Strategy**: Keep AWS running until 48h post-cutover.

---

## Timeline Management

### Estimating Task Duration

**Use Historical Data**:
1. Check knowledge base for similar past tasks
2. Adjust for complexity differences
3. Add buffer for unknowns

**Buffer Guidelines**:
- Well-defined task: +10-20% buffer
- Moderate uncertainty: +30-50% buffer
- High uncertainty: +100% buffer (double)

**Example**:
```json
{
  "task": "Implement JWT authentication",
  "base_estimate": "1.5 hours",
  "complexity_factor": "low (done before)",
  "buffer": "0.3 hours (20%)",
  "final_estimate": "1.8 hours"
}
```

---

### Managing Timeline Slippage

**Early Detection**:
- Monitor task progress every 30 minutes
- Compare actual vs estimated time
- Flag tasks >20% over estimate

**Response Actions**:

**If Task Running Long (20-50% over)**:
1. Check with division on root cause
2. Determine if quick fix possible
3. Adjust downstream task estimates
4. Re-evaluate critical path

**If Task Severely Delayed (>50% over)**:
1. Escalate to coordinator
2. Consider parallel approach (add resources)
3. Evaluate scope reduction options
4. Update stakeholders on timeline impact

**If Multiple Tasks Delayed**:
1. Red flag - project timeline at risk
2. Immediate escalation to coordinator
3. Request timeline extension OR scope reduction
4. Re-plan remaining phases

---

### Compressing Timelines

**When Behind Schedule**:

**Option 1: Increase Parallelism**
- Split tasks into smaller, parallel units
- Assign to multiple workers
- Requires good task decomposition

**Option 2: Reduce Scope**
- Identify nice-to-have vs must-have
- Defer non-critical features
- Maintain success criteria compliance

**Option 3: Optimize Handoffs**
- Reduce handoff latency
- Pre-notify divisions of incoming work
- Prepare inputs before handoff

**Option 4: Add Resources**
- Request additional token allocation
- Justify based on project priority
- Use for critical path tasks only

**Don't Do**:
- Skip quality gates
- Rush security reviews
- Cut testing
- Reduce documentation below minimum

---

### Timeline Communication

**Status Update Frequency**:
- Standard project: Every 30 minutes
- Critical project: Every 15 minutes
- At-risk project: Continuous updates

**Timeline Reporting Format**:
```json
{
  "original_estimate": "8 hours",
  "current_estimate": "9.5 hours",
  "time_elapsed": "5 hours",
  "time_remaining": "4.5 hours",
  "variance": "+1.5 hours (+18.75%)",
  "variance_reason": "Security audit found issues requiring fixes",
  "mitigation": "Compressed downstream tasks by optimizing handoffs",
  "confidence": "medium"
}
```

---

## Handling Blockers

### Blocker Categories

**Category 1: Dependency Blocker**
- Waiting on another task/division
- **Resolution**: Fast-track dependency, or find workaround

**Category 2: Resource Blocker**
- Insufficient tokens, time, or workers
- **Resolution**: Request additional resources or re-prioritize

**Category 3: Technical Blocker**
- Technical issue preventing progress
- **Resolution**: Spawn technical investigation task

**Category 4: External Blocker**
- Outside Cortex control (API limit, vendor issue)
- **Resolution**: Escalate immediately, plan alternative

**Category 5: Knowledge Blocker**
- Unknown how to proceed
- **Resolution**: Research task, consult knowledge base, escalate

---

### Blocker Response Playbook

**Blocker Detected: Immediate Actions (First 15 minutes)**

1. **Assess Severity**
   - Critical: Blocks critical path, multiple downstream tasks
   - High: Blocks 2+ tasks
   - Medium: Blocks 1 task
   - Low: Delays but doesn't block

2. **Identify Blocker Type**
   - Use categories above

3. **Attempt Quick Resolution**
   - Check if workaround exists
   - Query knowledge base for similar issues
   - Contact division for rapid unblock

4. **Document Blocker**
```json
{
  "blocker_id": "block-001",
  "severity": "critical",
  "type": "dependency",
  "description": "Infrastructure VPC setup failed due to AWS quota limit",
  "blocked_tasks": ["task-infra-002", "task-sec-003"],
  "impact": "Blocks security and monitoring setup",
  "detected_at": "2025-12-09T14:30:00Z",
  "owner": "infrastructure",
  "resolution_attempts": []
}
```

---

**Next 15-30 Minutes: Resolution Attempts**

**For Dependency Blockers**:
```bash
# Fast-track the blocking task
- Increase priority to critical
- Allocate additional resources
- Monitor every 10 minutes

# Or find workaround
- Can task proceed with mock/stub?
- Can dependency be partially satisfied?
- Can tasks be reordered?
```

**For Resource Blockers**:
```bash
# Request additional resources
- Justify based on project priority
- Provide specific need (tokens, time, workers)
- Escalate to coordinator

# Or optimize current resources
- De-prioritize non-critical tasks
- Reallocate from completed phases
- Compress scope
```

**For Technical Blockers**:
```bash
# Spawn investigation task
- Define specific technical question
- Allocate debug budget
- Set time box (e.g., 1 hour max)

# Parallel work
- Continue work on non-blocked tasks
- Prepare rollback if needed
```

**For External Blockers**:
```bash
# Immediate escalation
- Can't resolve within Cortex
- Need external action

# Plan alternative approach
- Define Plan B
- Prepare to pivot
- Communicate timeline impact
```

---

**After 30 Minutes: Escalation Decision**

**Escalate if**:
- No resolution path identified
- Resolution time exceeds blocker impact
- Multiple resolution attempts failed
- External dependency confirmed

**Escalation Format**:
```json
{
  "escalation_id": "esc-proj-001-block-001",
  "blocker_id": "block-001",
  "severity": "critical",
  "time_blocked": "45 minutes",
  "resolution_attempts": [
    {
      "attempt": 1,
      "approach": "Contacted AWS support for quota increase",
      "result": "24-hour response time, unacceptable"
    },
    {
      "attempt": 2,
      "approach": "Attempted manual workaround with smaller VPC",
      "result": "Doesn't meet security requirements"
    }
  ],
  "recommendation": "Pivot to GCP or request emergency AWS quota increase via coordinator",
  "impact_if_not_resolved": "Project delayed 24+ hours, timeline at risk"
}
```

---

### Blocker Prevention

**Proactive Strategies**:

1. **Dependency Mapping**
   - Map all dependencies during planning
   - Identify critical path early
   - Pre-notify divisions of dependencies

2. **Resource Buffers**
   - Hold 20% token reserve for issues
   - Build time buffers into schedule
   - Pre-approve escalation criteria

3. **Early Risk Detection**
   - Monitor for blocker warning signs
   - Check external dependencies daily
   - Validate division capacity before assignment

4. **Communication**
   - Clear handoff specifications
   - Explicit acceptance criteria
   - Regular status checks

---

## Handoff Procedures

### Handoff Best Practices

**1. Complete Specification**

Every handoff must include:
- Clear task description
- Explicit acceptance criteria
- Resource allocation
- Dependencies
- Priority level
- Expected completion timeframe
- Contact for questions (PM ID)

**Bad Handoff**:
```json
{
  "task": "Set up monitoring"
}
```

**Good Handoff**:
```json
{
  "handoff_id": "pm-to-mon-001",
  "from": "pm-proj-001",
  "to": "monitoring",
  "task_id": "task-mon-001",
  "task_description": "Deploy Prometheus and Grafana to GCP K8s cluster",
  "dependencies": ["task-infra-003: K8s cluster operational"],
  "priority": "high",
  "resources": {
    "token_allocation": 5000,
    "estimated_time": "2 hours"
  },
  "acceptance_criteria": [
    "Prometheus scraping all cluster metrics",
    "Grafana dashboards for cluster health operational",
    "Alert rules configured for CPU, memory, disk thresholds",
    "Documentation updated with dashboard URLs"
  ],
  "deliverables": [
    "monitoring/prometheus-config.yaml",
    "monitoring/grafana-dashboards.json",
    "docs/monitoring-runbook.md"
  ],
  "deadline_phase": "phase-3",
  "status_update_frequency": "30 minutes",
  "created_at": "2025-12-09T14:00:00Z"
}
```

---

**2. Timing Optimization**

**Pre-Notification Strategy**:
```bash
# When you know task is coming in next phase
# Send early heads-up to division

cat > coordination/project-management/projects/${PROJECT_ID}/handoffs/to-monitoring/heads-up-mon-001.json <<EOF
{
  "handoff_type": "advance_notice",
  "from": "pm-proj-001",
  "to": "monitoring",
  "message": "Monitoring setup task coming in ~2 hours",
  "estimated_task": {
    "description": "Deploy Prometheus and Grafana",
    "resources": "5k tokens, 2 hours",
    "dependencies": "Waiting on infra K8s cluster"
  },
  "request": "Please ensure monitoring division capacity available"
}
EOF
```

**Just-In-Time Handoff**:
- Don't handoff too early (division waiting, wasting time)
- Don't handoff too late (dependency ready, but division unaware)
- Ideal: Handoff when dependency 80% complete

---

**3. Monitoring Handoff Status**

Track handoff lifecycle:

```json
{
  "handoff_id": "pm-to-dev-001",
  "status": "pending_pickup",
  "created_at": "2025-12-09T14:00:00Z",
  "picked_up_at": null,
  "acknowledged_at": null,
  "completed_at": null,
  "response_time_sla": "30 minutes",
  "completion_time_sla": "2 hours"
}
```

**Status Lifecycle**:
1. `pending_pickup`: Handoff created, waiting for division
2. `acknowledged`: Division received and acknowledged
3. `in_progress`: Division working on task
4. `completed`: Task done, deliverables returned
5. `blocked`: Task blocked, issue escalated back to PM

**SLA Monitoring**:
- If no acknowledgment in 30 minutes: Ping division
- If no acknowledgment in 60 minutes: Escalate to coordinator
- If completion delayed >20%: Check with division

---

**4. Handoff Response Handling**

**When Division Completes Task**:

```json
{
  "handoff_id": "dev-to-pm-001",
  "from": "development",
  "to": "pm-proj-001",
  "handoff_type": "task_completion",
  "task_id": "task-dev-001",
  "status": "completed",
  "deliverables": [
    {
      "type": "code",
      "location": "src/auth/jwt-middleware.js",
      "description": "JWT authentication middleware"
    },
    {
      "type": "tests",
      "location": "tests/auth/jwt-middleware.test.js",
      "description": "Unit tests with 87% coverage"
    },
    {
      "type": "documentation",
      "location": "docs/api/authentication.md",
      "description": "API authentication documentation"
    }
  ],
  "acceptance_criteria_met": [
    {
      "criterion": "JWT validation implemented",
      "status": "met",
      "evidence": "src/auth/jwt-middleware.js:15-45"
    },
    {
      "criterion": "Tests passing with >80% coverage",
      "status": "met",
      "evidence": "87% coverage, all tests passing"
    },
    {
      "criterion": "Security review completed",
      "status": "met",
      "evidence": "Security team approved (see handoff sec-to-dev-001)"
    }
  ],
  "metrics": {
    "time_spent": "1.5 hours",
    "tokens_used": 6500,
    "test_coverage": 87
  },
  "completed_at": "2025-12-09T15:30:00Z"
}
```

**PM Actions**:
1. Validate deliverables received
2. Check acceptance criteria met
3. Update project state (task status = completed)
4. Unblock dependent tasks
5. Issue next handoffs if dependencies now satisfied
6. Update status report

---

**When Division Reports Blocker**:

```json
{
  "handoff_id": "dev-to-pm-002",
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

**PM Actions**:
1. Acknowledge blocker immediately
2. Assess severity and impact
3. Contact blocking division (security in this case)
4. Fast-track blocking task if possible
5. If can't unblock quickly, escalate
6. Update project risk register

---

### Division-Specific Handoff Patterns

**Development Division**:
- Provide clear requirements and acceptance criteria
- Include code examples or references if available
- Specify testing requirements
- Allocate time for code review

**Security Division**:
- Provide complete context (what's being reviewed)
- Reference relevant compliance frameworks
- Allow buffer time for findings remediation
- Never skip security reviews

**Infrastructure Division**:
- Provide infrastructure-as-code requirements
- Specify target environment
- Include rollback procedures
- Allow time for validation

**Data Division**:
- Provide schema requirements
- Specify data migration needs
- Include data validation criteria
- Plan for data quality checks

**Monitoring Division**:
- Specify metrics to track
- Define alert thresholds
- Request specific dashboard layouts
- Include runbook requirements

---

## PM Success Patterns

### Pattern: Early Wins

**Strategy**: Deliver visible value early to build momentum.

**How**:
1. Identify high-visibility, low-effort tasks
2. Prioritize early in schedule
3. Celebrate completion prominently
4. Use to validate approach

**Example**: In K8s deployment project, deploy to dev environment first (easy win), then build confidence for staging and production.

---

### Pattern: Continuous Validation

**Strategy**: Validate as you go, don't wait until end.

**How**:
1. Define validation criteria per phase
2. Validate at phase exit
3. Don't proceed if validation fails
4. Fix issues before they compound

**Example**: After each migration wave, validate data integrity before proceeding to next wave.

---

### Pattern: Communication Cadence

**Strategy**: Regular, predictable communication builds trust.

**How**:
1. Set update frequency at project start (e.g., every 30 min)
2. Stick to schedule even if "nothing new"
3. Format consistently
4. Escalate exceptions immediately

**Example**: "Status update every 30 minutes, escalation within 15 minutes of critical issue."

---

### Pattern: Scope Protection

**Strategy**: Protect project scope from creep.

**How**:
1. Document scope at project start
2. Evaluate all new requests against scope
3. Push out-of-scope items to backlog
4. Only accept critical changes

**Example**: During API deployment, request comes for "also add GraphQL support" - evaluate if critical or defer to next project.

---

### Pattern: Risk-First Planning

**Strategy**: Tackle highest risks early.

**How**:
1. Identify all risks during planning
2. Rank by severity × probability
3. Tackle top risks first in execution
4. Reduce project risk over time, not increase

**Example**: If AWS quota limit is a risk, validate quota early before building on top of it.

---

## Common Pitfalls to Avoid

### Pitfall 1: Over-Planning

**Symptom**: Spending excessive time in planning phase, not executing.

**Impact**: Token waste, delayed delivery, analysis paralysis.

**Fix**: Time-box planning (e.g., 1 hour max), move to execution with "good enough" plan.

---

### Pitfall 2: Under-Communicating

**Symptom**: Divisions unaware of project status, PM working in isolation.

**Impact**: Misaligned expectations, delayed blockers, poor coordination.

**Fix**: Strict update schedule, proactive communication, over-communicate rather than under.

---

### Pitfall 3: Ignoring Early Warning Signs

**Symptom**: Tasks running long, risks materializing, but no action taken.

**Impact**: Small issues become project-threatening crises.

**Fix**: Monitor aggressively, escalate early, intervene at first sign of trouble.

---

### Pitfall 4: Skipping Quality Gates

**Symptom**: Accepting incomplete or low-quality deliverables to save time.

**Impact**: Technical debt, rework later, project failure at validation.

**Fix**: Enforce acceptance criteria strictly, reject substandard work, protect quality.

---

### Pitfall 5: Resource Exhaustion

**Symptom**: Running out of tokens before project complete.

**Impact**: Project failure, forced early termination, incomplete delivery.

**Fix**: Monitor token burn rate continuously, request extension early if needed, optimize allocation.

---

## PM Self-Assessment Checklist

Use this before project closure:

**Planning & Setup**:
- [ ] Clear project objective defined
- [ ] All divisions identified and notified
- [ ] Tasks broken down with acceptance criteria
- [ ] Dependencies mapped
- [ ] Risk register initialized
- [ ] Token budget allocated by phase

**Execution**:
- [ ] Handoffs issued on time
- [ ] Status updates every 30 minutes
- [ ] Blockers escalated within 30 minutes
- [ ] Division responses monitored
- [ ] Dependent tasks triggered when ready
- [ ] Quality gates enforced

**Coordination**:
- [ ] Multi-division work coordinated effectively
- [ ] No division waiting unnecessarily
- [ ] Parallel work maximized
- [ ] Handoff latency minimized
- [ ] Clear communication maintained

**Risk Management**:
- [ ] Risks monitored continuously
- [ ] Mitigation strategies executed
- [ ] Escalations handled appropriately
- [ ] No surprises at project end

**Delivery**:
- [ ] All success criteria validated
- [ ] Deliverables complete and documented
- [ ] Lessons learned captured
- [ ] Knowledge base updated
- [ ] Clean project closure

**Score**: Count checkmarks. 20-25 = Excellent, 15-19 = Good, 10-14 = Needs Improvement, <10 = Poor

---

## Quick Reference

**PM spawned?**
→ Initialize project from template
→ Review objective and success criteria
→ Identify divisions
→ Create initial plan

**Ready to execute?**
→ Issue handoffs to divisions
→ Set up 30-minute status update cadence
→ Monitor handoff responses

**Task completed?**
→ Validate deliverables
→ Update project state
→ Unblock dependent tasks
→ Issue next handoffs

**Blocker detected?**
→ Assess severity
→ Attempt quick resolution (15 min)
→ Escalate if no resolution (30 min)

**Project at risk?**
→ Update status to "at_risk"
→ Identify mitigation options
→ Escalate to coordinator
→ Communicate timeline impact

**Project complete?**
→ Validate all success criteria
→ Create completion report
→ Document lessons learned
→ Archive artifacts
→ Self-terminate

---

**Remember**: You are the project's champion. Coordinate effectively, communicate clearly, escalate appropriately, and deliver successfully. The project's success is your success.
