# RAG Integration Guide for Security Master

## Overview

The Security Master now has access to a Retrieval Augmented Generation (RAG) system that provides context from past security tasks and remediation patterns.

## Integration Points

### 1. Before Starting Vulnerability Scans

Before spawning scan workers, query RAG for similar past scans:

```bash
# Source RAG library
source /Users/ryandahlberg/Projects/cortex/scripts/lib/rag.sh

# Query for similar security scans
SCAN_CONTEXT=$(query_rag_for_master "security" "vulnerability scan dependencies CVE" 5)

# Use context to inform scan strategy
echo "$SCAN_CONTEXT"
```

### 2. CVE Remediation Patterns

When a CVE is detected, retrieve past remediation strategies:

```bash
# Query for similar CVE fixes
CVE_ID="CVE-2024-1234"
REMEDIATION_CONTEXT=$(query_rag "fix $CVE_ID vulnerability" 3 "security")

# Extract successful remediation patterns
echo "$REMEDIATION_CONTEXT" | jq -r '.[] |
    "Past Fix [\(.score * 100 | round)%]: \(.outcome)"'
```

### 3. Worker Context Augmentation

When spawning security workers, augment their context with RAG results:

```bash
TASK_DESC="Scan npm dependencies for vulnerabilities"

# Get augmented context
RAG_CONTEXT=$(augment_master_context "security" "$TASK_DESC")

# Create worker spec with RAG context
cat > worker-spec.json <<EOF
{
  "worker_id": "sec-worker-${WORKER_UUID}",
  "worker_type": "scan-worker",
  "parent_master": "security",
  "task_id": "${TASK_ID}",
  "context": {
    "task": "${TASK_DESC}",
    "rag_context": ${RAG_CONTEXT},
    "knowledge_base_refs": {
      "cve_database": "coordination/masters/security/knowledge-base/cve-patterns.jsonl",
      "remediation_strategies": "coordination/masters/security/knowledge-base/remediation-strategies.json"
    }
  }
}
EOF
```

### 4. Post-Task Learning

After completing security tasks, index outcomes for future retrieval:

```bash
# After successful CVE remediation
TASK_ID="task-security-cve-2024-1234"
DESCRIPTION="Fixed CVE-2024-1234 in express dependency"
OUTCOME="Updated express from 4.17.1 to 4.18.2, ran tests, verified no regressions"

# Index for future retrieval
index_current_task "$TASK_ID" "$DESCRIPTION" "$OUTCOME"

# Or use auto-indexing
auto_index_completed_task "coordination/tasks/${TASK_ID}.json"
```

## Query Examples

### Example 1: Finding Similar Vulnerability Scans

```bash
query_rag_for_master "security" "npm audit high severity vulnerabilities" 5
```

Output:
```
=== RAG Retrieved Context ===
Query: npm audit high severity vulnerabilities
Master: security

[92%] task-security-npm-audit-2024-10
  Description: Scan npm dependencies for high/critical CVEs
  Outcome: Found 3 high severity issues in lodash, axios, express. Updated all to latest versions.

[88%] task-security-dep-audit-2024-09
  Description: Audit JavaScript dependencies for security issues
  Outcome: Detected prototype pollution in lodash 4.17.19. Upgraded to 4.17.21.

[85%] task-security-supply-chain-2024-08
  Description: Supply chain security audit of npm packages
  Outcome: Implemented package-lock.json verification and dependency pinning strategy.
=== End RAG Context ===
```

### Example 2: Retrieving Code Patterns

```bash
query_patterns_for_implementation "dependency update script bash" 3
```

Output:
```
=== Relevant Code Patterns ===
Query: dependency update script bash

[95%] dependency_update_automation
  Description: Safe dependency update with rollback
  Code:
#!/bin/bash
# Update dependency with backup
cp package.json package.json.backup
npm update lodash
npm audit fix
if npm test; then
    rm package.json.backup
else
    mv package.json.backup package.json
    npm install
fi
=== End Code Patterns ===
```

## Performance Benefits

1. **Faster Remediation**: Retrieve proven fix strategies instead of researching from scratch
2. **Pattern Recognition**: Identify recurring vulnerability patterns across projects
3. **Consistent Approach**: Use successful past approaches for similar issues
4. **Learning System**: Every security task improves future performance

## Best Practices

1. **Always Query Before Action**: Check RAG for similar tasks before starting new security work
2. **Use Specific Queries**: More specific queries yield better results
   - Good: "fix SQL injection in user input validation"
   - Bad: "security issue"

3. **Filter by Master**: Always filter by "security" master for security-specific context
4. **Index All Outcomes**: Index both successful and failed attempts (mark with success flag)
5. **Update Patterns**: After discovering new vulnerability patterns, add to code patterns index

## Integration Checklist

- [ ] Source RAG library in security master scripts
- [ ] Query RAG before vulnerability scans
- [ ] Augment worker context with RAG results
- [ ] Index completed security tasks
- [ ] Add successful remediation patterns to pattern index
- [ ] Monitor RAG retrieval latency (<100ms target)
- [ ] Review RAG stats periodically

## Monitoring

Check RAG system health:

```bash
rag_stats
```

Expected output:
```json
{
  "task_index_size": 47,
  "pattern_index_size": 12,
  "task_metadata_count": 47,
  "pattern_metadata_count": 12
}
```

## Troubleshooting

**Issue**: RAG returns no results
- **Solution**: Check if indexes are initialized: `rag_is_initialized`
- **Solution**: Rebuild indexes: `rebuild_rag_index`

**Issue**: Results not relevant
- **Solution**: Make query more specific
- **Solution**: Add filters: `query_rag "query" 5 "security"`

**Issue**: Slow retrieval (>100ms)
- **Solution**: Reduce top_k parameter
- **Solution**: Check index size with `rag_stats`
