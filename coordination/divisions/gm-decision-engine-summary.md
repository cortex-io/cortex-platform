# GM Decision Engine - Quick Reference

**Files Created**:
- `/Users/ryandahlberg/Projects/cortex/coordination/divisions/gm-decision-engine.md` (42KB, 1,542 lines)
- `/Users/ryandahlberg/Projects/cortex/coordination/divisions/gm-decision-engine.json` (22KB)

---

## What This Is

The GM Decision Engine is a comprehensive decision support system for Division General Managers in the cortex automation system. It provides algorithms, matrices, decision trees, and rules to:

- **Route tasks** to the right contractors efficiently
- **Estimate resources** (tokens and time) accurately
- **Manage priorities** and queue tasks effectively
- **Balance load** across contractors
- **Escalate appropriately** when needed
- **Coordinate across divisions** smoothly

---

## Key Components

### 1. Task Complexity Scoring (1-10 Scale)

**5 Weighted Dimensions**:
- Technical Complexity (30%)
- Integration Points (20%)
- Unknowns/Ambiguity (20%)
- Risk Level (15%)
- Dependencies (15%)

**Score Ranges**:
- 1.0-3.0: Simple (1 contractor, <1h, <3k tokens)
- 3.1-5.0: Moderate (1 contractor, 1-2h, 3-6k tokens)
- 5.1-7.0: Complex (1-2 contractors, 2-4h, 6-12k tokens)
- 7.1-8.5: Very Complex (2+ contractors, 4-8h, 12-20k tokens)
- 8.6-10.0: Extremely Complex (multiple contractors, 8h+, 20k+ tokens)

### 2. Contractor Selection Matrix

**Domain Mapping**:
- VM/Network/DNS → infrastructure-contractor
- Kubernetes → talos-contractor
- Workflows → n8n-contractor

**Selection Criteria**:
- Domain match (50%)
- Current load (30%)
- Success rate (20%)

### 3. Resource Estimation Formulas

**Tokens**:
```
Estimated Tokens = Base_Tokens × Complexity_Multiplier × Integration_Factor × (1 + Contingency)
```

**Time**:
```
Estimated Time = (Complexity_Score × 0.5) + Overhead + (Subtotal × Contingency_Multiplier)
```

### 4. Priority Queue Management

**4 Priority Levels**:
- P0 (Critical): <15min response, production outage
- P1 (High): <1h response, urgent work
- P2 (Medium): <4h response, standard ops
- P3 (Low): <24h response, optimizations

**Priority Score**:
```
Score = (Impact × 40%) + (Urgency × 30%) + (Business_Value × 20%) + (Risk × 10%)
```

### 5. Load Balancing

**Utilization Thresholds**:
- 0-80%: Available (assign all priorities)
- 80-90%: Busy (assign P0/P1 only)
- 90-100%: Overloaded (queue all, escalate if P0)

**3 Patterns**:
- Round-robin (interchangeable contractors)
- Specialization (different expertise)
- Least-loaded (optimizing throughput)

### 6. Escalation Criteria

**Automatic Escalation When**:
- Division at >90% token budget
- All contractors >90% utilization
- Queue depth >20 tasks
- P0 not started in 15 minutes
- Complexity score >8.5
- 3+ divisions required
- Contractor success rate <85%

### 7. Decision Trees

**4 Common Scenarios**:
1. New Task Received
2. Contractor Overloaded
3. Cross-Division Coordination Needed
4. Budget Exhaustion Imminent

Each with step-by-step decision flow.

### 8. Cross-Division Coordination

**Handoff Protocol**:
- Structured JSON files in handoffs directories
- Response SLAs by priority (5min to 8h)
- Status update cadence (15min to 24h)
- 3 coordination patterns (sequential, parallel, hub-spoke)

### 9. Budget Allocation

**Division Budgets** (Daily):
- Infrastructure: 20k tokens (10%)
- Containers: 15k tokens (7.5%)
- Workflows: 12k tokens (6%)
- Configuration: 10k tokens (5%)
- Monitoring: 18k tokens (9%)
- Intelligence: 8k tokens (4%)

**15% Emergency Reserve** for each division

**Allocation by Priority**:
- P0: 40% of available budget
- P1: 35%
- P2: 20%
- P3: 5%

### 10. SLA Definitions

**By Task Type** with complexity scores, response/completion SLAs, and token budgets:
- Infrastructure tasks (7 types)
- Kubernetes tasks (7 types)
- Workflow tasks (6 types)

**SLA Multipliers by Priority**:
- P0: 0.5x (faster)
- P1: 1.0x (standard)
- P2: 1.5x (slower)
- P3: 3.0x (much slower)

---

## Machine-Readable Format

The `gm-decision-engine.json` file contains:

**Data Structures**:
- Complexity scoring weights and thresholds
- Contractor domain mappings
- Resource estimation coefficients
- Priority scoring formulas
- Load balancing rules
- Escalation triggers
- Budget allocation percentages
- SLA definitions by task type
- Performance metrics targets

**Use Cases**:
- Automated decision making
- Dashboard integration
- Metric tracking
- Rule updates
- Integration with GM agents

---

## How to Use

### For GMs at Task Receipt

1. **Calculate complexity score** using 5 dimensions
2. **Select contractor** using domain mapping
3. **Estimate resources** using formulas
4. **Calculate priority** using scoring algorithm
5. **Execute decision tree** based on scenario
6. **Document decision** for learning

### For GMs During Execution

1. **Monitor SLAs** against task definitions
2. **Track budget** utilization
3. **Rebalance load** across contractors
4. **Handle escalations** per criteria
5. **Coordinate divisions** using handoff rules

### For COO

1. **Review metrics** for division performance
2. **Adjust budgets** based on utilization
3. **Plan capacity** using historical data
4. **Optimize processes** based on patterns
5. **Respond to escalations** per SLA

---

## Continuous Improvement

**Monthly Review**:
- SLA compliance rates
- Estimation accuracy
- Budget efficiency
- Escalation patterns
- Contractor performance

**Update Engine**:
- Refine complexity weights
- Adjust SLA times
- Update resource formulas
- Add new decision trees
- Incorporate lessons learned

---

## Integration Points

**Integrates With**:
- GM Common Patterns (coordination framework)
- Contractor System (task execution)
- Project Management Playbook (PM coordination)
- Division Budgets (resource allocation)
- Knowledge Bases (historical data)

**Used By**:
- All Division GMs (task routing and management)
- COO (oversight and optimization)
- Dashboard (metrics and reporting)
- PM Agents (project planning)

---

## Success Criteria

**Good Decision Making When**:
- Complexity scoring accurate (±1 point)
- Resource estimates accurate (±20%)
- SLA compliance >95%
- Budget utilization 70-85%
- Escalations appropriate (not too many, not too few)
- Contractor load balanced (std dev <0.20)

---

## Quick Lookup Tables

### Complexity → Actions
| Score | Classification | Contractors | Time | Tokens | Escalate? |
|-------|----------------|-------------|------|--------|-----------|
| 1-3 | Simple | 1 | <1h | <3k | No |
| 3-5 | Moderate | 1 | 1-2h | 3-6k | No |
| 5-7 | Complex | 1-2 | 2-4h | 6-12k | If >6.5 |
| 7-8.5 | Very Complex | 2+ | 4-8h | 12-20k | Yes |
| 8.6-10 | Extreme | Many | 8h+ | 20k+ | Always |

### Priority → SLA
| Score | Level | Response | Preemption |
|-------|-------|----------|------------|
| 8-10 | P0 Critical | 15 min | All |
| 6-8 | P1 High | 1 hour | P2/P3 |
| 4-6 | P2 Medium | 4 hours | None |
| 1-4 | P3 Low | 24 hours | None |

### Utilization → Actions
| Utilization | Status | Assignment Rules |
|-------------|--------|------------------|
| 0-75% | Healthy | Normal ops |
| 75-85% | Warning | Monitor, optimize |
| 85-90% | High | Defer P3, optimize |
| 90-95% | Critical | Defer P2/P3, escalate prep |
| 95-100% | Emergency | Stop new work, escalate |

---

**Version**: 1.0.0  
**Created**: 2025-12-09  
**Next Review**: 2025-12-16 (weekly)

**Remember**: This is a decision support tool, not rigid rules. GMs should use judgment and context alongside the engine's recommendations.
