# Cortex System Prompts

This directory contains all versioned system prompts for Cortex master agents and worker agents.

## Directory Structure

```
coordination/prompts/
├── README.md (this file)
├── masters/              # Master agent prompts
│   ├── coordinator.md
│   ├── development.md
│   ├── security.md
│   ├── inventory.md
│   └── cicd.md
└── workers/              # Worker agent prompts
    ├── implementation-worker.md
    ├── scan-worker.md
    ├── fix-worker.md
    ├── test-worker.md
    ├── review-worker.md
    ├── pr-worker.md
    ├── documentation-worker.md
    ├── analysis-worker.md
    └── catalog-worker.md
```

## Versioning Guidelines

### Version Format

All prompts follow semantic versioning:

```
v{MAJOR}.{MINOR}.{PATCH}
```

Example: `v2.1.3`

- **MAJOR**: Breaking changes to agent behavior, interface changes
- **MINOR**: New features, capabilities added (backward compatible)
- **PATCH**: Bug fixes, clarifications, minor improvements

### Version Header

Each prompt file MUST include a version header at the top:

```markdown
# {Agent Name} - System Prompt

**Agent Type**: Master Agent | Worker
**Version**: v2.1.0
**Last Updated**: 2025-11-27
**Architecture**: Master-Worker System
**Token Budget**: {token_allocation}

---
```

### Changelog

Each prompt file MUST include a changelog section at the bottom:

```markdown
## Changelog

### v2.1.0 (2025-11-27)
- Added RAG context retrieval capabilities
- Enhanced worker spawning with context augmentation
- Improved error handling guidelines

### v2.0.0 (2025-11-15)
- Migrated to execution manager architecture
- Breaking change: Worker spawning now via EM for complex tasks
- Updated token budget allocation

### v1.0.0 (2025-11-01)
- Initial release
```

## Template Variables

Prompts support template variables that are replaced at runtime:

- `{{WORKER_ID}}` - Unique worker identifier
- `{{TASK_ID}}` - Associated task identifier
- `{{MASTER_ID}}` - Parent master identifier
- `{{TOKEN_BUDGET}}` - Allocated token budget
- `{{REPOSITORY}}` - Target repository
- `{{TASK_DESCRIPTION}}` - Task description from spec
- `{{WORKER_SPEC_PATH}}` - Path to worker specification file
- `{{KNOWLEDGE_BASE_PATH}}` - Path to relevant knowledge base entries

## Prompt Loading

### From Scripts

Master spawn scripts load prompts from this directory:

```bash
# Load master prompt
PROMPT_FILE="coordination/prompts/masters/development.md"
PROMPT_CONTENT=$(cat "$PROMPT_FILE")

# Replace template variables
PROMPT_CONTENT="${PROMPT_CONTENT//\{\{MASTER_ID\}\}/$MASTER_ID}"
PROMPT_CONTENT="${PROMPT_CONTENT//\{\{SESSION_ID\}\}/$SESSION_ID}"
```

### From Worker Specs

Worker specs reference prompt templates:

```json
{
  "worker_id": "worker-impl-001",
  "prompt_template": "coordination/prompts/workers/implementation-worker.md",
  "prompt_variables": {
    "WORKER_ID": "worker-impl-001",
    "TASK_ID": "task-500",
    "TOKEN_BUDGET": "10000"
  }
}
```

## Creating New Prompts

### 1. Create from Template

Copy the appropriate template:

```bash
# For workers
cp coordination/prompts/workers/_TEMPLATE.md \
   coordination/prompts/workers/new-worker.md

# For masters
cp coordination/prompts/masters/_TEMPLATE.md \
   coordination/prompts/masters/new-master.md
```

### 2. Fill Required Sections

All prompts MUST include:

1. **Header**: Agent type, version, budget
2. **Identity**: Clear agent role definition
3. **Core Responsibilities**: Specific duties
4. **Workflow**: Step-by-step process
5. **Deliverables**: Expected outputs
6. **Success Criteria**: Definition of done
7. **Changelog**: Version history

### 3. Add Template Variables

Mark all runtime-replaceable values:

```markdown
Your worker ID is: {{WORKER_ID}}
Your task: {{TASK_DESCRIPTION}}
Token budget: {{TOKEN_BUDGET}}
```

### 4. Version and Update

- Set initial version to `v1.0.0`
- Add changelog entry
- Update "Last Updated" date

### 5. Register in Spawn Scripts

Update the appropriate spawn script to reference the new prompt:

```bash
# In spawn-worker.sh or run-master.sh
PROMPT_TEMPLATE="coordination/prompts/workers/new-worker.md"
```

## Updating Existing Prompts

### 1. Increment Version

Determine version bump based on change type:

- **Breaking change** (agent behavior changes): Bump MAJOR
- **New feature** (added capability): Bump MINOR
- **Bug fix/clarification**: Bump PATCH

### 2. Update Header

```markdown
**Version**: v2.2.0  # <-- Update this
**Last Updated**: 2025-11-27  # <-- Update this
```

### 3. Add Changelog Entry

```markdown
## Changelog

### v2.2.0 (2025-11-27)
- Added: New capability X
- Changed: Improved workflow step 3
- Fixed: Clarified ambiguous instruction in section Y
```

### 4. Test Changes

Before committing:

1. Spawn test worker/master with updated prompt
2. Verify expected behavior
3. Confirm template variables replaced correctly
4. Check no regressions in existing functionality

### 5. Commit with Conventional Format

```bash
git add coordination/prompts/workers/implementation-worker.md
git commit -m "feat(prompts): update implementation-worker to v2.2.0

- Added RAG context retrieval
- Enhanced error handling
- Improved test coverage requirements"
```

## Prompt Quality Standards

### Clarity
- Use clear, direct language
- Avoid ambiguity
- Provide examples for complex concepts

### Completeness
- Cover all expected scenarios
- Include error handling
- Define edge cases

### Consistency
- Follow established format
- Use consistent terminology
- Maintain tone across prompts

### Testability
- Define measurable success criteria
- Specify expected deliverables
- Include verification steps

## Best Practices

### 1. Single Responsibility

Each prompt should define ONE agent role:

```markdown
# Good
"You are a scan-worker specialized in security vulnerability detection"

# Bad
"You are a scan-worker that also fixes issues and writes documentation"
```

### 2. Explicit Instructions

Be specific about expected behavior:

```markdown
# Good
"Run `npm audit` and parse JSON output. Report vulnerabilities with severity ≥ HIGH."

# Bad
"Check for security issues"
```

### 3. Bounded Scope

Clearly define limits:

```markdown
**What you DO:**
- Scan dependencies for vulnerabilities
- Generate structured vulnerability report
- Suggest remediation steps

**What you DON'T do:**
- Apply fixes (that's fix-worker's job)
- Make deployment decisions (that's master's job)
- Modify code outside scan scope
```

### 4. Context Provision

Provide necessary context:

```markdown
**Your Context:**
- Repository: {{REPOSITORY}}
- Task ID: {{TASK_ID}}
- Master: {{MASTER_ID}}
- Knowledge Base: {{KNOWLEDGE_BASE_PATH}}
- Previous similar scans: (loaded from RAG)
```

### 5. Error Handling

Define failure scenarios:

```markdown
**If scan fails:**
1. Log error details to worker log
2. Update worker status to "failed"
3. Create failure report with:
   - Error message
   - Stack trace
   - Attempted remediation
   - Escalation recommendation
```

## Migration from Legacy Prompts

### 1. Identify Legacy Prompts

Check for hardcoded prompts in scripts:

```bash
# Find embedded prompts
grep -r "SYSTEM_PROMPT=" scripts/
grep -r "cat <<EOF" scripts/ | grep -i prompt
```

### 2. Extract to Files

Move embedded prompts to files:

```bash
# Before (in script)
SYSTEM_PROMPT="You are a worker that..."

# After
PROMPT_FILE="coordination/prompts/workers/worker.md"
SYSTEM_PROMPT=$(cat "$PROMPT_FILE")
```

### 3. Add Version Control

- Set initial version `v1.0.0`
- Document current state in changelog
- Add header with metadata

### 4. Update References

Change spawn scripts to load from files:

```bash
# Old
claude --prompt "You are a scan worker..."

# New
PROMPT_TEMPLATE="coordination/prompts/workers/scan-worker.md"
claude --prompt-file "$PROMPT_TEMPLATE"
```

## Validation

### Automated Checks

Run validation script to check prompt quality:

```bash
./scripts/validate-prompts.sh
```

Checks:
- Version header present
- Changelog exists
- Required sections present
- Template variables valid
- Markdown syntax correct

### Manual Review

Before merging prompt changes:

1. Peer review for clarity
2. Test with actual worker/master spawn
3. Verify backward compatibility (or document breaking changes)
4. Update related documentation

## Rollback Procedure

If a prompt version causes issues:

### 1. Identify Problem Version

```bash
# Check current version
head -10 coordination/prompts/workers/scan-worker.md | grep Version
```

### 2. Revert to Previous Version

```bash
# Git history
git log --oneline coordination/prompts/workers/scan-worker.md

# Revert specific commit
git revert <commit-hash>

# Or restore from specific version
git checkout <previous-commit-hash> -- coordination/prompts/workers/scan-worker.md
```

### 3. Update Version

Increment patch version and add rollback entry:

```markdown
### v2.1.1 (2025-11-27)
- Rollback: Reverted v2.1.0 changes due to worker spawn failures
- Restored: v2.0.5 behavior (stable)
```

### 4. Test and Deploy

- Verify rollback resolves issue
- Spawn test worker
- Monitor for regressions
- Commit rollback

## Support

For questions about prompts:

1. Check this README first
2. Review existing prompts for examples
3. Consult `docs/AGENT-ARCHITECTURE.md`
4. Ask in #cortex-development

---

**Last Updated**: 2025-11-27
**Maintained by**: Cortex Development Team
