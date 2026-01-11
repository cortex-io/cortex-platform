# RAG Integration Guide for Development Master

## Overview

The Development Master uses RAG to retrieve implementation patterns, successful code architectures, and past feature development approaches for better decision-making.

## Integration Points

### 1. Feature Planning Phase

Before implementing new features, query for similar past implementations:

```bash
# Source RAG library
source /Users/ryandahlberg/Projects/cortex/scripts/lib/rag.sh

# Query for similar feature implementations
FEATURE="user authentication with JWT"
IMPL_CONTEXT=$(query_rag_for_master "development" "$FEATURE" 5)

# Review past approaches
echo "$IMPL_CONTEXT"
```

### 2. Code Pattern Retrieval

Retrieve proven code patterns for specific implementations:

```bash
# Query for authentication patterns
AUTH_PATTERNS=$(query_patterns_for_implementation "JWT authentication middleware express" 3)

# Use patterns to guide implementation
echo "$AUTH_PATTERNS"
```

### 3. Bug Fix Strategy

When fixing bugs, learn from past similar fixes:

```bash
BUG_DESC="race condition in async database operations"

# Find similar bug fixes
BUG_FIXES=$(query_rag "$BUG_DESC" 3 "development")

# Extract successful approaches
echo "$BUG_FIXES" | jq -r '.[] |
    "[\(.score * 100 | round)%] \(.task_id): \(.outcome)"'
```

### 4. Worker Spawning with RAG Context

Augment worker context with relevant patterns:

```bash
TASK_DESC="Implement user authentication with JWT tokens"

# Get RAG context
RAG_CONTEXT=$(augment_master_context "development" "$TASK_DESC")

# Spawn worker with augmented context
cat > coordination/workers/dev-worker-${WORKER_ID}.json <<EOF
{
  "worker_id": "dev-worker-${WORKER_ID}",
  "worker_type": "feature-implementer",
  "parent_master": "development",
  "task_id": "${TASK_ID}",
  "context": {
    "task": "${TASK_DESC}",
    "rag_context": ${RAG_CONTEXT},
    "implementation_guidance": "Use RAG context for proven patterns"
  },
  "resources": {
    "token_allocation": 15000,
    "time_limit_minutes": 60
  }
}
EOF
```

### 5. Post-Implementation Learning

After completing development tasks, index the implementation:

```bash
# Index successful implementation
TASK_ID="task-dev-auth-system"
DESCRIPTION="Implemented JWT authentication with refresh tokens"
OUTCOME="Created AuthMiddleware, JWT service, token refresh endpoint. Tests: 95% coverage. Used express-jwt library."

index_current_task "$TASK_ID" "$DESCRIPTION" "$OUTCOME"

# Index code pattern
python3 /Users/ryandahlberg/Projects/cortex/llm-mesh/rag/indexer.py index-pattern \
    --pattern-type "authentication" \
    --description "JWT middleware with refresh tokens" \
    --code "$(cat src/middleware/auth.js)"
```

## Query Examples

### Example 1: Feature Implementation History

```bash
query_rag_for_master "development" "REST API with Express.js" 5
```

Output:
```
=== RAG Retrieved Context ===
Query: REST API with Express.js
Master: development

[94%] task-dev-api-users-2024-10
  Description: Build user management REST API
  Outcome: Implemented CRUD endpoints with express-validator, JWT auth, and PostgreSQL. Tests: 98% coverage.

[91%] task-dev-api-products-2024-09
  Description: Create product catalog API
  Outcome: Built RESTful API with pagination, filtering, and sorting. Used express-async-errors for clean error handling.

[87%] task-dev-api-auth-2024-08
  Description: Implement authentication API endpoints
  Outcome: Created login, logout, refresh token endpoints. Integrated bcrypt for password hashing.
=== End RAG Context ===
```

### Example 2: Refactoring Patterns

```bash
query_patterns_for_implementation "database connection pooling node.js" 2
```

Output:
```
=== Relevant Code Patterns ===
Query: database connection pooling node.js

[96%] database_connection_pool
  Description: PostgreSQL connection pool with retry logic
  Code:
const { Pool } = require('pg');
const pool = new Pool({
  max: 20,
  connectionTimeoutMillis: 3000,
  idleTimeoutMillis: 30000
});

pool.on('error', (err) => {
  console.error('Unexpected pool error', err);
});

module.exports = pool;

[89%] mongodb_connection_pattern
  Description: MongoDB connection with automatic reconnection
  Code:
const mongoose = require('mongoose');
mongoose.connect(process.env.MONGO_URI, {
  maxPoolSize: 10,
  serverSelectionTimeoutMS: 5000,
  socketTimeoutMS: 45000
});
=== End Code Patterns ===
```

## Use Cases

### 1. Architecture Decisions

Query for similar architectural patterns before making decisions:

```bash
# Planning microservices architecture
query_rag "microservices architecture node.js communication" 5 "development"

# Results guide service boundary decisions
```

### 2. Technology Selection

Learn from past technology choices:

```bash
# Choosing database
query_rag "PostgreSQL vs MongoDB for user data" 3 "development"

# Review outcomes of past choices
```

### 3. Testing Strategies

Retrieve successful testing approaches:

```bash
# Find effective testing patterns
query_patterns_for_implementation "integration testing jest supertest" 3
```

### 4. Performance Optimization

Learn from past optimization work:

```bash
# Query optimization history
query_rag "optimize slow database queries PostgreSQL" 5 "development"
```

## Worker Type Specific Integration

### Feature Implementer Workers

```bash
# Before spawning feature-implementer
FEATURE_QUERY="implement ${FEATURE_NAME}"
SIMILAR_FEATURES=$(query_rag "$FEATURE_QUERY" 3 "development")

# Include in worker spec context.similar_implementations
```

### Bug Fixer Workers

```bash
# Before spawning bug-fixer
BUG_QUERY="fix ${BUG_TYPE} bug"
SIMILAR_FIXES=$(query_rag "$BUG_QUERY" 3 "development")

# Include in worker spec context.past_similar_fixes
```

### Refactorer Workers

```bash
# Before spawning refactorer
REFACTOR_QUERY="refactor ${CODE_AREA} improve ${QUALITY_ASPECT}"
REFACTOR_PATTERNS=$(query_patterns_for_implementation "$REFACTOR_QUERY" 2)

# Include in worker spec context.refactoring_patterns
```

### Optimizer Workers

```bash
# Before spawning optimizer
OPTIM_QUERY="optimize ${PERFORMANCE_AREA}"
OPTIM_HISTORY=$(query_rag "$OPTIM_QUERY" 3 "development")

# Include in worker spec context.optimization_strategies
```

## Pattern Indexing

Index successful code patterns after implementation:

```bash
# Example: Index authentication pattern
cat > /tmp/auth-pattern.json <<EOF
{
  "pattern_type": "authentication",
  "code": "$(cat src/middleware/auth.js)",
  "description": "JWT authentication middleware with role-based access control",
  "metadata": {
    "language": "javascript",
    "framework": "express",
    "success_rate": 0.98,
    "test_coverage": 0.95,
    "applicable_to": ["web_api", "microservices"]
  }
}
EOF

# Index using Python API
python3 << 'PYEOF'
import json
import sys
sys.path.insert(0, '/Users/ryandahlberg/Projects/cortex/llm-mesh/rag')
from indexer import RAGIndexer

with open('/tmp/auth-pattern.json') as f:
    pattern = json.load(f)

indexer = RAGIndexer()
idx = indexer.index_code_pattern(
    pattern_type=pattern['pattern_type'],
    code=pattern['code'],
    description=pattern['description'],
    metadata=pattern['metadata']
)
indexer.save()
print(f"Indexed pattern at index {idx}")
PYEOF
```

## Performance Metrics

Track RAG impact on development tasks:

```bash
# Before RAG
BASELINE_TIME=180  # minutes for feature implementation

# After RAG (with pattern retrieval)
WITH_RAG_TIME=120  # minutes for similar feature

IMPROVEMENT=$(( (BASELINE_TIME - WITH_RAG_TIME) * 100 / BASELINE_TIME ))
echo "RAG improved implementation speed by ${IMPROVEMENT}%"
```

## Best Practices

1. **Query Early**: Always check RAG before starting implementation
2. **Specific Queries**: Include technology stack in queries
   - Good: "authentication JWT express bcrypt"
   - Bad: "auth"
3. **Learn from Failures**: Index failed approaches with success=false
4. **Update Patterns**: Regularly update successful patterns
5. **Context Size**: Limit RAG context to avoid token overflow (max 3-5 results)

## Integration Checklist

- [ ] Source RAG library in development master scripts
- [ ] Query before feature implementation
- [ ] Query before refactoring
- [ ] Query before bug fixes
- [ ] Augment all worker contexts with RAG
- [ ] Index completed implementations
- [ ] Index successful code patterns
- [ ] Monitor retrieval performance
- [ ] Track decision quality improvement

## Monitoring

Check development-specific RAG stats:

```bash
# Get all stats
rag_stats

# Get development master tasks only
query_rag ".*" 100 "development" | jq 'length'
```

## Expected Improvements

With RAG integration, expect:

- 5-10% reduction in implementation time
- 15-20% reduction in bugs (using proven patterns)
- Higher code quality (following successful patterns)
- More consistent architecture (learned from past)
- Faster onboarding (patterns document best practices)

## Troubleshooting

**Issue**: Retrieved patterns not applicable
- **Solution**: Add more metadata filters (language, framework)
- **Solution**: Increase query specificity

**Issue**: No similar implementations found
- **Solution**: Broaden query terms
- **Solution**: Check if similar tasks were indexed

**Issue**: RAG context too large for worker token budget
- **Solution**: Reduce top_k to 2-3
- **Solution**: Extract only key points from outcomes
