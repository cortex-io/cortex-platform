# Advanced Prompting Techniques in Cortex

This document explains how Cortex leverages advanced prompting techniques for autonomous AI orchestration.

## Overview

Cortex implements several advanced prompting strategies at the **system level**. While individual users craft prompts for single AI interactions, Cortex applies these same principles across hundreds of coordinated agents.

## Core Principle: Clarity of Thought

> **"If you can't explain it clearly yourself, you can't prompt it effectively."**

This principle underpins every aspect of Cortex's design:

- **Clear task descriptions** → Agents know exactly what to do
- **Explicit routing logic** → Right specialist for every job
- **Well-defined personas** → Each master has a clear domain
- **Concrete success criteria** → System knows when tasks are complete

## Techniques Implemented in Cortex

### 1. Tree of Thought (Multi-Path Evaluation)

**In single-agent AI**: User generates multiple approaches and evaluates them.

**In Cortex**: The coordinator automatically:
1. Analyzes each incoming task
2. Considers multiple routing options
3. Evaluates confidence scores for each master
4. Selects the optimal path based on learned patterns

**Implementation**: `coordination/masters/coordinator/lib/moe-router.sh`

```bash
# Cortex evaluates multiple routing paths
evaluate_routing_options() {
  local task="$1"

  # Generate confidence scores for each master
  local security_confidence=$(calculate_confidence "security" "$task")
  local development_confidence=$(calculate_confidence "development" "$task")
  local cicd_confidence=$(calculate_confidence "cicd" "$task")

  # Select path with highest confidence
  select_optimal_master "$task" "$security_confidence" "$development_confidence" "$cicd_confidence"
}
```

**Learning Loop**: After task completion, Cortex updates routing confidence based on outcomes.

### 2. Playoff Method (Adversarial Validation)

**In single-agent AI**: User creates competing personas that critique each other.

**In Cortex**: Multiple workers collaborate and validate each other's work:

1. **Parallel Execution**: Multiple workers can tackle the same task
2. **Cross-Validation**: Workers review each other's outputs
3. **Master Oversight**: Masters validate worker results
4. **Quality Gates**: Governance system enforces standards

**Example Flow**:
```
Task: "Implement authentication feature"

Development Master:
├── Worker 1 (Implementation): Writes initial code
├── Worker 2 (Review): Reviews code for logic errors
├── Worker 3 (Security): Checks for vulnerabilities
└── Master: Synthesizes feedback, approves final version
```

### 3. Continuous Learning (Prompt Refinement)

**In single-agent AI**: Users manually refine prompts based on results.

**In Cortex**: System automatically improves routing and task handling:

- **Pattern Extraction**: Identifies successful task patterns
- **Confidence Updates**: Adjusts routing based on outcomes
- **Failure Analysis**: Learns from unsuccessful attempts
- **Knowledge Base**: Maintains history of routing decisions

**Implementation**: `llm-mesh/moe-learning/`

### 4. Persona Specialization

**In single-agent AI**: User defines a persona for the AI to adopt.

**In Cortex**: Each master is a specialized persona with:

- **Domain Expertise**: Security, Development, CI/CD, Inventory
- **Specific Tools**: Tailored capabilities for each domain
- **Knowledge Context**: Historical performance in their specialty
- **Decision Authority**: Autonomy within their domain

**Master Personas**:

| Master | Domain | Specialization |
|--------|--------|----------------|
| Security Master | Security | Vulnerability scanning, CVE remediation, audits |
| Development Master | Development | Feature implementation, bug fixes, refactoring |
| CI/CD Master | CI/CD | Build automation, testing, deployment |
| Inventory Master | Documentation | Repository cataloging, dependency tracking |
| Coordinator Master | Orchestration | Task routing, master coordination |

### 5. Chain of Thought (Explicit Reasoning)

**In single-agent AI**: User requests step-by-step reasoning.

**In Cortex**: Every operation is broken into explicit steps:

```json
{
  "task_id": "task-001",
  "reasoning": {
    "step1": "Analyzed task description for security keywords",
    "step2": "Calculated confidence scores for each master",
    "step3": "Security master had 0.85 confidence (CVE-related task)",
    "step4": "Routed to security-master",
    "decision": "Task contains CVE identifier and vulnerability keywords"
  }
}
```

**Benefit**: Full audit trail of decision-making for every task.

### 6. Context Management

**In single-agent AI**: User provides relevant context in the prompt.

**In Cortex**: System maintains rich context automatically:

- **Task History**: Previous similar tasks and outcomes
- **Worker State**: Current workload and availability
- **System Health**: Resource usage and performance metrics
- **Learned Patterns**: Historical routing decisions
- **Failure Patterns**: Known issues and their resolutions

**Context Sources**:
- `coordination/knowledge-base/learned-patterns/`
- `coordination/metrics/`
- `coordination/patterns/`
- `coordination/events/`

## Applying These Techniques

### For Users Interacting with Cortex

When submitting tasks to Cortex, apply clarity principles:

**Poor Task Description**:
```
"Fix the authentication"
```

**Good Task Description**:
```
"Fix authentication bug: users can't log in after password reset.
Error: 'Invalid session token'
Affects: /api/auth/reset-password endpoint
Steps to reproduce: Reset password → Click link → Enter new password → Login fails"
```

### For Developers Extending Cortex

When adding new masters or workers:

1. **Define Clear Responsibilities**
   - What domain does this master own?
   - What types of tasks should route here?
   - What tools does it need?

2. **Establish Success Criteria**
   - How do we know a task succeeded?
   - What metrics indicate quality?
   - When should we retry vs. fail?

3. **Document Decision Logic**
   - Why did we choose this approach?
   - What alternatives were considered?
   - What are the trade-offs?

## Meta-Skill: System Thinking

Just as good prompting requires clear thinking, good AI orchestration requires **clear system thinking**:

- **Decomposition**: Break complex operations into clear steps
- **Boundaries**: Define what each component is responsible for
- **Interfaces**: Specify how components communicate
- **Observability**: Make the system's reasoning visible
- **Feedback**: Learn from outcomes continuously

## Comparison: Single-Agent vs. Cortex

| Aspect | Single-Agent AI | Cortex (Multi-Agent) |
|--------|----------------|---------------------|
| **Tree of Thought** | User generates multiple approaches | Automatic multi-path evaluation |
| **Playoff Method** | User creates competing personas | Multiple workers + cross-validation |
| **Learning** | User refines prompts manually | System learns automatically |
| **Persona** | User defines one persona | Multiple specialized masters |
| **Context** | User provides context | System maintains rich context |
| **Scale** | 1 conversation | 100+ coordinated agents |

## Best Practices

### 1. Start with Clarity

Before implementing any feature:
- Describe it clearly in plain English
- Red team it from different angles
- Document the decision-making process

### 2. Design for Observability

Make reasoning visible:
- Log routing decisions
- Track confidence scores
- Record task outcomes
- Monitor pattern emergence

### 3. Embrace Iteration

Don't expect perfection on first attempt:
- Start with simple routing rules
- Monitor outcomes
- Refine based on real data
- Let the system learn

### 4. Maintain the Knowledge Base

Cortex gets smarter over time:
- Review routing decisions periodically
- Analyze failure patterns
- Update confidence thresholds
- Prune outdated patterns

## Resources

### Internal Documentation
- [MoE Learning System](../llm-mesh/moe-learning/README.md)
- [Routing Algorithm](../coordination/masters/coordinator/lib/moe-router.sh)
- [Knowledge Base](../coordination/knowledge-base/)

### External Resources
- [Advanced Prompting Guide](https://ry-ops.dev/posts/mastering-ai-prompting-techniques-that-actually-work)
- [Prompt Library](https://ry-ops.dev/prompt-library)
- [Anthropic Prompting Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)

## Examples

### Example 1: Security Task Routing

**Task Input**:
```
"Scan repository for CVE-2024-12345 vulnerability"
```

**Cortex Process**:
1. **Analysis**: Detects "CVE" keyword + "scan" + "vulnerability"
2. **Tree of Thought**: Evaluates security (0.92), development (0.45), inventory (0.38)
3. **Decision**: Routes to security-master (highest confidence)
4. **Execution**: Security master spawns scan-worker
5. **Learning**: Records successful pattern for future CVE tasks

### Example 2: Multi-Master Collaboration

**Task Input**:
```
"Implement new API endpoint for user authentication with full test coverage and deployment"
```

**Cortex Process**:
1. **Decomposition**: Breaks into sub-tasks
   - Feature implementation (development-master)
   - Test automation (cicd-master)
   - Deployment (cicd-master)
2. **Parallel Execution**: Multiple masters work concurrently
3. **Validation**: Each master validates their component
4. **Integration**: Coordinator ensures components work together

## Conclusion

Cortex doesn't just use AI - it **orchestrates AI at scale** using the same principles that make individual prompting effective:

- **Clarity** in task definitions
- **Structure** in decision-making
- **Learning** from outcomes
- **Validation** through multiple perspectives

The result: An autonomous system that gets smarter with every task.

---

*For more on prompting techniques, see the [Advanced Prompting Guide](https://ry-ops.dev/posts/mastering-ai-prompting-techniques-that-actually-work)*
