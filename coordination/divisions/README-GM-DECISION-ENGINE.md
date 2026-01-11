# GM Decision Engine Documentation Index

**Location**: `/Users/ryandahlberg/Projects/cortex/coordination/divisions/`
**Created**: 2025-12-09
**Version**: 1.0.0

---

## Overview

The GM Decision Engine is a comprehensive decision support system for Division General Managers in the cortex automation system. It provides systematic approaches to task routing, resource estimation, priority management, and cross-division coordination.

## Files in This Package

### 1. Main Documentation
**File**: `gm-decision-engine.md` (42KB, 1,542 lines)
**Purpose**: Complete decision engine specification with algorithms, matrices, and decision trees

**Contains**:
- Task complexity scoring algorithm (1-10 scale with 5 weighted dimensions)
- Contractor selection matrix (domain mapping and availability checks)
- Resource estimation formulas (tokens and time)
- Priority queue management (P0-P3 with scoring algorithm)
- Load balancing across contractors (utilization thresholds and patterns)
- Escalation criteria (automatic triggers and response SLAs)
- Decision trees for 4 common scenarios
- Cross-division coordination rules (handoff protocol and patterns)
- Budget allocation logic (division budgets and optimization)
- SLA definitions per task type (infrastructure, K8s, workflows)

### 2. Machine-Readable Rules
**File**: `gm-decision-engine.json` (22KB, 780 lines)
**Purpose**: Structured data for automated decision making and system integration

**Contains**:
- Complexity scoring weights and thresholds
- Contractor domain mappings and capacity models
- Resource estimation coefficients and multipliers
- Priority scoring formulas and queue rules
- Load balancing algorithms and thresholds
- Escalation triggers and response SLAs
- Budget allocation percentages by division and priority
- SLA definitions with token budgets and time estimates
- Performance metrics targets

**JSON Structure** (15 top-level sections):
```
- complexity_scoring
- contractor_selection
- resource_estimation
- priority_management
- load_balancing
- escalation_criteria
- cross_division_coordination
- budget_allocation
- sla_definitions
- metrics
- continuous_improvement
- version
- description
- created
- last_updated
```

### 3. Quick Reference
**File**: `gm-decision-engine-summary.md` (7.3KB, 285 lines)
**Purpose**: Executive summary and quick lookup tables for GMs

**Contains**:
- Component overview (10 key components)
- Quick lookup tables (complexity→actions, priority→SLA, utilization→actions)
- Usage guide (for GMs, COO, PM agents)
- Integration points (with other cortex systems)
- Success criteria (target metrics)

### 4. Visual Diagrams
**File**: `gm-decision-engine-flow.txt` (16KB, 315 lines)
**Purpose**: ASCII diagrams showing decision flows and processes

**Contains**:
- Task flow diagram (end-to-end processing)
- Load balancing flow (utilization-based routing)
- Budget management flow (allocation and tracking)
- Cross-division coordination flow (handoff process)
- Escalation decision flow (when and how to escalate)
- Continuous improvement cycle (metrics and optimization)

---

## Key Concepts

### Task Complexity Scoring (1-10 Scale)

**Formula**:
```
Complexity = (Technical × 0.30) + (Integration × 0.20) + 
             (Unknowns × 0.20) + (Risk × 0.15) + 
             (Dependencies × 0.15)
```

**Classifications**:
- Simple (1.0-3.0): Single contractor, <1h, <3k tokens
- Moderate (3.1-5.0): Single contractor, 1-2h, 3-6k tokens
- Complex (5.1-7.0): 1-2 contractors, 2-4h, 6-12k tokens
- Very Complex (7.1-8.5): Multiple contractors, 4-8h, 12-20k tokens
- Extremely Complex (8.6-10.0): Many contractors, 8h+, 20k+ tokens

### Priority System (P0-P3)

**Priority Score Formula**:
```
Score = (Impact × 40%) + (Urgency × 30%) + 
        (Business_Value × 20%) + (Risk × 10%)
```

**Priority Levels**:
- P0 (Critical): 8.0-10.0 score, <15min response, production outage
- P1 (High): 6.0-7.9 score, <1h response, urgent work
- P2 (Medium): 4.0-5.9 score, <4h response, standard ops
- P3 (Low): 1.0-3.9 score, <24h response, optimizations

### Resource Estimation

**Token Estimation**:
```
Tokens = Base_Tokens × Complexity_Multiplier × 
         Integration_Factor × (1 + Contingency)
```

**Time Estimation**:
```
Time (hours) = (Complexity_Score × 0.5) + Overhead + 
               (Subtotal × Contingency_Multiplier)
```

### Contractor Selection

**Domain Mapping**:
- VM/Network/DNS → infrastructure-contractor
- Kubernetes clusters → talos-contractor
- Workflow automation → n8n-contractor

**Availability Thresholds**:
- 0-80% utilization: Available (assign all)
- 80-90% utilization: Busy (assign P0/P1 only)
- 90-100% utilization: Overloaded (queue all, escalate if P0)

---

## Usage Examples

### Example 1: Simple Task
**Task**: Create DNS A record
- Technical: 2, Integration: 2, Unknowns: 1, Risk: 3, Dependencies: 1
- Complexity Score: 1.8 (Simple)
- Contractor: infrastructure-contractor
- Estimated: 30 minutes, 2k tokens
- Priority: P2 (standard)
- Decision: Assign immediately if contractor available

### Example 2: Complex Task
**Task**: Deploy full application stack (VM + Network + DNS + Storage)
- Technical: 6, Integration: 7, Unknowns: 5, Risk: 7, Dependencies: 6
- Complexity Score: 6.2 (Complex)
- Contractor: infrastructure-contractor (primary)
- Estimated: 3-4 hours, 10-12k tokens
- Priority: P1 (production deployment)
- Decision: Check availability, assign or escalate if overloaded

### Example 3: Very Complex Task
**Task**: Design new authentication system
- Technical: 9, Integration: 8, Unknowns: 8, Risk: 10, Dependencies: 7
- Complexity Score: 8.5 (Very Complex)
- Contractors: Multiple (infra + talos + n8n)
- Estimated: 6-8 hours, 18-22k tokens
- Priority: P0 (critical capability)
- Decision: Escalate to COO for project planning

---

## Integration Points

### With GM Common Patterns
- Uses handoff protocol defined in GM Common
- Follows token budget structure from GM Common
- Applies cross-division coordination rules
- Reports to COO per GM Common guidelines

### With Contractor System
- Routes tasks based on contractor expertise
- Tracks contractor load and availability
- Monitors contractor performance metrics
- Updates contractor knowledge bases with outcomes

### With Project Management
- Provides complexity scoring for PM agents
- Estimates resources for project planning
- Defines SLAs for project timelines
- Supplies decision trees for common PM scenarios

### With Dashboard
- Exports metrics for visualization
- Provides queue depth and wait time data
- Reports SLA compliance rates
- Tracks budget utilization trends

---

## Performance Targets

**Target Metrics**:
- SLA compliance: >95%
- Estimation accuracy: >85% (within ±20%)
- Budget utilization: 70-85% (not too low, not too high)
- Contractor success rate: >95%
- Average queue wait time: <45 minutes
- Load imbalance score: <0.20

**Alert Thresholds**:
- 75% utilization: Warning (monitor closely)
- 85% utilization: High (optimize operations)
- 90% utilization: Critical (defer low-priority work)
- 95% utilization: Emergency (stop new work, escalate)

---

## Continuous Improvement

**Review Frequency**:
- **Daily**: Budget utilization, SLA compliance, queue depths
- **Weekly**: Estimation accuracy, contractor performance, wait times
- **Monthly**: All metrics, trend analysis, optimization opportunities

**Update Triggers**:
- Monthly review cycle
- Significant pattern changes
- New contractor additions
- SLA compliance below target
- Estimation accuracy below target

**Refinement Areas**:
- Complexity scoring weights
- Resource estimation formulas
- SLA time adjustments
- Priority scoring weights
- Budget allocation percentages

---

## Getting Started

### For Division GMs

1. **Read Main Documentation**
   - Start with `gm-decision-engine.md`
   - Focus on sections relevant to your division
   - Study decision trees for common scenarios

2. **Use Quick Reference**
   - Keep `gm-decision-engine-summary.md` handy
   - Reference lookup tables during operations
   - Follow usage guide for task receipt and execution

3. **Integrate into Workflow**
   - Apply complexity scoring to incoming tasks
   - Use contractor selection matrix for routing
   - Track against SLA definitions
   - Report metrics per dashboard requirements

### For COO

1. **Understand System Design**
   - Review all documentation for complete picture
   - Note escalation criteria and response SLAs
   - Understand budget allocation logic

2. **Monitor Performance**
   - Track division metrics from `gm-decision-engine.json`
   - Review escalations and resolutions
   - Identify optimization opportunities

3. **Optimize Operations**
   - Adjust budgets based on utilization trends
   - Update SLAs based on actual performance
   - Refine algorithms using historical data

### For PM Agents

1. **Use for Project Planning**
   - Apply complexity scoring to project tasks
   - Use resource estimation for timeline planning
   - Reference SLA definitions for task scheduling

2. **Leverage Decision Trees**
   - Follow cross-division coordination flows
   - Apply escalation criteria to blockers
   - Use budget management strategies

---

## Support and Questions

**For Issues**:
- Escalate to COO per escalation criteria
- Document issues in knowledge base
- Request engine updates if patterns not covered

**For Improvements**:
- Submit suggestions during monthly review
- Document successful patterns
- Share optimization techniques

**For Training**:
- Review visual diagrams in `gm-decision-engine-flow.txt`
- Study examples in main documentation
- Practice with low-complexity tasks first

---

## Version History

**1.0.0** (2025-12-09)
- Initial release
- Complete decision engine specification
- Machine-readable rules (JSON)
- Quick reference guide
- Visual flow diagrams
- Integration with existing cortex systems

**Next Review**: 2025-12-16 (weekly review)
**Next Major Update**: 2025-01-09 (monthly optimization)

---

## File Locations

All files located in:
```
/Users/ryandahlberg/Projects/cortex/coordination/divisions/
```

**Files**:
- `gm-decision-engine.md` - Main documentation (read first)
- `gm-decision-engine.json` - Machine-readable rules
- `gm-decision-engine-summary.md` - Quick reference
- `gm-decision-engine-flow.txt` - Visual diagrams
- `README-GM-DECISION-ENGINE.md` - This file

**Related Files**:
- `gm-templates/gm-common.md` - GM coordination patterns
- `../contractors/` - Contractor specifications
- `../project-management/pm-playbook.md` - PM coordination

---

## Summary

The GM Decision Engine provides systematic, measurable approaches to:
1. Scoring task complexity objectively
2. Selecting the right contractor for each task
3. Estimating resources accurately
4. Managing priorities and queues effectively
5. Balancing load across contractors
6. Escalating appropriately when needed
7. Coordinating across divisions smoothly
8. Allocating budgets efficiently
9. Defining and meeting SLAs consistently
10. Continuously improving through metrics and learning

This is a living system - it improves through use, measurement, and refinement. GMs should treat it as a decision support tool that augments their judgment, not as rigid rules that replace thinking.

**Goal**: Maximize efficiency and effectiveness of the cortex automation system through systematic, data-driven decision making.
