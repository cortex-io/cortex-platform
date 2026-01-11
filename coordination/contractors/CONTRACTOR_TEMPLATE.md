# {CONTRACTOR_NAME}-contractor Template

Use this template to create new contractor agents for the Cortex ecosystem.

## Files to Create

1. `{name}-contractor.md` - Agent definition and expertise guide
2. `{name}-contractor-knowledge.json` - Structured knowledge base
3. `{name}-contractor-quick-reference.md` - Quick start guide (optional)

## Agent Definition Template ({name}-contractor.md)

```markdown
# {Name}-contractor Agent

## Agent Identity

**Role**: {Role Description}
**Type**: Contractor Agent
**Specialization**: {What this contractor specializes in}
**Expertise Level**: Expert in {domains}

## Purpose

{2-3 paragraphs explaining what this contractor does, why it's needed, and how it differs from just calling APIs directly}

## Core Knowledge Domains

### 1. {Domain 1}
{Detailed knowledge in this area}

### 2. {Domain 2}
{Detailed knowledge in this area}

### 3. {Domain 3}
{Detailed knowledge in this area}

## Using the {tool-name}-mcp-server Tools

The {name}-contractor has access to the following MCP server tools:

### Tool: {tool_name}
{Description and examples}

## {Domain} Best Practices

### 1. {Practice Category 1}
{Details}

### 2. {Practice Category 2}
{Details}

## Common {Task} Templates

### Template 1: {Template Name}
{Code example and explanation}

### Template 2: {Template Name}
{Code example and explanation}

## Example Prompts and Responses

### Prompt 1: "{Example user request}"

**Response Strategy:**
1. {Step 1}
2. {Step 2}
3. {Step 3}

**Implementation:**
{Details of what the contractor would provide}

## Integration with Cortex Ecosystem

### Coordination with Other Masters
{How this contractor works with Development, CI/CD, Security, Inventory masters}

### Knowledge Base Contribution
{What gets recorded and where}

### Handoff Format
{Example handoff JSON}

## Quality Standards

### Pre-Deployment Checklist
- [ ] {Checklist item 1}
- [ ] {Checklist item 2}
...

## Anti-Patterns to Avoid

### 1. {Anti-pattern}
{Explanation and solution}

## Success Metrics
{How to measure contractor effectiveness}

## Resources

**Knowledge Base**: `/Users/ryandahlberg/Projects/cortex/coordination/contractors/{name}-contractor-knowledge.json`
**Documentation**: {Links to official docs}
**MCP Server**: {MCP server name}

---

**Version**: 1.0.0
**Created**: {date}
**Maintained by**: Cortex Development Master
```

## Knowledge Base Template ({name}-contractor-knowledge.json)

```json
{
  "version": "1.0.0",
  "created_at": "YYYY-MM-DDTHH:mm:ssZ",
  "description": "Knowledge base for {name}-contractor: {brief description}",

  "{domain}_patterns": {
    "{pattern_name}": {
      "name": "{Pattern Name}",
      "use_cases": [
        "Use case 1",
        "Use case 2"
      ],
      "core_components": [
        "Component 1",
        "Component 2"
      ],
      "pattern": {
        "step_1": {
          "description": "What this step does",
          "considerations": [
            "Important consideration 1",
            "Important consideration 2"
          ]
        },
        "step_2": {
          "description": "What this step does",
          "implementation": "Code or config example"
        }
      },
      "error_handling": {
        "strategy": "Error handling approach",
        "implementation": [
          "Implementation detail 1",
          "Implementation detail 2"
        ]
      },
      "example_code": {
        "example_1": "// Code example",
        "example_2": "// Code example"
      }
    }
  },

  "{tool}_recommendations": {
    "by_use_case": {
      "use_case_1": {
        "primary": "Primary tool/method",
        "alternatives": ["Alternative 1", "Alternative 2"],
        "tips": [
          "Tip 1",
          "Tip 2"
        ]
      }
    },
    "performance_tips": {
      "general": [
        "General tip 1",
        "General tip 2"
      ],
      "specific_area": [
        "Specific tip 1",
        "Specific tip 2"
      ]
    }
  },

  "error_handling_patterns": {
    "retry_logic": {
      "description": "When and how to retry",
      "implementation": {
        "method": "Code or config",
        "code": "// Example implementation"
      },
      "use_cases": [
        "Use case 1",
        "Use case 2"
      ]
    }
  },

  "integration_patterns": {
    "pattern_name": {
      "description": "What this integration pattern does",
      "implementation": "How to implement",
      "example": "// Code example"
    }
  },

  "security_best_practices": {
    "category_1": [
      "Best practice 1",
      "Best practice 2"
    ],
    "category_2": [
      "Best practice 1",
      "Best practice 2"
    ]
  },

  "monitoring_and_observability": {
    "what_to_monitor": [
      "Metric 1",
      "Metric 2"
    ],
    "alerting": {
      "critical_alerts": [
        "Alert condition 1",
        "Alert condition 2"
      ],
      "warning_alerts": [
        "Alert condition 1",
        "Alert condition 2"
      ]
    }
  },

  "testing_strategies": {
    "test_type_1": {
      "description": "What to test",
      "approach": "How to test"
    }
  },

  "deployment_patterns": {
    "pattern_name": {
      "description": "Deployment approach",
      "steps": [
        "Step 1",
        "Step 2"
      ]
    }
  },

  "common_mistakes": {
    "anti_patterns": [
      {
        "mistake": "Common mistake",
        "solution": "How to fix it"
      }
    ]
  },

  "reusable_code_snippets": {
    "snippet_name": "// Reusable code example",
    "snippet_name_2": "// Another reusable code example"
  },

  "learning_outcomes": {
    "successful_patterns": [],
    "failed_approaches": [],
    "optimization_insights": [],
    "integration_learnings": []
  }
}
```

## Quick Reference Template ({name}-contractor-quick-reference.md)

```markdown
# {Name}-contractor Quick Reference

## When to Use {Name}-contractor

Use the {name}-contractor when you need to:
- {Use case 1}
- {Use case 2}
- {Use case 3}

## Available {Domain} Patterns

| Pattern | Use Case | Complexity |
|---------|----------|------------|
| **{pattern_1}** | {Description} | Low/Medium/High |
| **{pattern_2}** | {Description} | Low/Medium/High |

## Quick Start Examples

### Request {Task Type 1}
```
"{Example user request}"
```

### Request {Task Type 2}
```
"{Example user request}"
```

## Common Patterns

### {Pattern Category}
```
{Pattern description and quick example}
```

## Knowledge Base Contents

The contractor knows about:
- X {domain} patterns
- Y {tool} recommendations
- Z error handling strategies
...

## MCP Server Tools Available

The contractor can use these {tool}-mcp-server tools:
- `tool_1` - {Description}
- `tool_2` - {Description}

## Response Format

When you request {task}, you'll get:
1. {Deliverable 1}
2. {Deliverable 2}
3. {Deliverable 3}

## Best Practices Checklist

Before requesting {task}:
- [ ] {Requirement 1}
- [ ] {Requirement 2}

Contractor will ensure:
- [ ] {Quality standard 1}
- [ ] {Quality standard 2}

## Resources

- **Agent Definition**: `/Users/ryandahlberg/Projects/cortex/coordination/contractors/{name}-contractor.md`
- **Knowledge Base**: `/Users/ryandahlberg/Projects/cortex/coordination/contractors/{name}-contractor-knowledge.json`
- **Official Docs**: {URL}

---

**Version**: 1.0.0
**Last Updated**: {date}
```

## Implementation Checklist

When creating a new contractor:

- [ ] Create agent definition markdown file
- [ ] Create comprehensive knowledge base JSON
- [ ] Create quick reference guide (optional but recommended)
- [ ] Update contractors/README.md with new contractor entry
- [ ] Test contractor with example prompts
- [ ] Document MCP server tools and usage
- [ ] Define handoff patterns with masters
- [ ] Set up knowledge base update workflow
- [ ] Define success metrics
- [ ] Create example interactions

## Knowledge Base Structure Guidelines

A good contractor knowledge base should include:

1. **Patterns Library** (3-5 major patterns)
   - Use cases
   - Implementation steps
   - Code examples
   - Error handling

2. **Tool Recommendations** (by use case)
   - Primary tools
   - Alternatives
   - Tips and tricks

3. **Error Handling** (3-5 strategies)
   - When to use
   - Implementation
   - Examples

4. **Integration Patterns** (3-5 patterns)
   - Authentication
   - State management
   - Async processing

5. **Security Best Practices**
   - Credential management
   - Input validation
   - Data protection

6. **Monitoring and Observability**
   - What to log
   - What to monitor
   - Alert conditions

7. **Testing Strategies**
   - Unit tests
   - Integration tests
   - E2E tests

8. **Deployment Patterns**
   - Environment management
   - Version control
   - Rollback procedures

9. **Common Mistakes**
   - Anti-patterns
   - Solutions

10. **Reusable Code Snippets**
    - Frequently used code
    - Tested examples

11. **Learning Outcomes** (grows over time)
    - Successful patterns
    - Failed approaches
    - Optimization insights

## Naming Conventions

- Contractor file: `{domain}-contractor.md`
- Knowledge base: `{domain}-contractor-knowledge.json`
- Quick reference: `{domain}-contractor-quick-reference.md`
- Domain should be lowercase with hyphens (e.g., `n8n`, `talos`, `infrastructure`)

## Size Guidelines

- Agent Definition: 10-20 KB (detailed but readable)
- Knowledge Base: 20-40 KB (comprehensive patterns and examples)
- Quick Reference: 5-10 KB (essential info only)

## Maintenance

Contractors should be updated when:
- New MCP server capabilities are added
- New patterns are discovered
- Best practices evolve
- Integration patterns change
- Common mistakes are identified

Update the `version` field and add entries to `learning_outcomes` section.

---

**Template Version**: 1.0.0
**Created**: 2025-12-09
**Usage**: Copy this template when creating new contractor agents
