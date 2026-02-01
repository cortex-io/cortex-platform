# Chat Layer Fabric

**Serverless AI Chat with Docker Model Runner + Claude Code.**

Local-first intelligence. Claude Code when you need it. Zero cloud costs for 80% of queries.

## Architecture

```
+------------------------------------------------------------------------------+
|                              USER QUERY                                       |
|                  "What pods are failing in the cortex namespace?"            |
+--------------------------------------+---------------------------------------+
                                       |
                                       v
+------------------------------------------------------------------------------+
|                       CHAT ACTIVATOR (Always On)                              |
|  +------------------------------------------------------------------------+  |
|  | 1. Intent Classification: "status query" + "kubernetes"                |  |
|  | 2. Complexity Score: 35/100 (simple lookup, no reasoning needed)       |  |
|  | 3. Route Decision: LOCAL (similarity match or simple response)         |  |
|  | 4. Wake: execution-local-response                                      |  |
|  +------------------------------------------------------------------------+  |
+--------------------------------------+---------------------------------------+
                                       |
         +-----------------------------+-----------------------------+
         v                             v                             v
+------------------+       +------------------+       +------------------+
| REASONING-DMR    |       | CHAT-QDRANT      |       | EXECUTION-LOCAL  |
| (Docker Model    |       | (Always On)      |       | (Fast Response)  |
|  Runner)         |       +------------------+       +------------------+
+------------------+       | - Conversations  |       | - Status queries |
| - Phi-4 / Qwen   |       | - Patterns       |       | - Simple lookups |
| - Local LLM      |       | - Tool mappings  |       | - Cached answers |
| - OpenAI API     |       | - Embeddings     |       |                  |
|                  |       |                  |       | KEDA: 0->1       |
| KEDA: 0->1       |       | PVC-backed       |       | ~200MB warm      |
| ~4GB warm        |       | ~512MB           |       +--------+---------+
+--------+---------+       +--------+---------+                |
         |                          |                          |
         +-------------+------------+------------+-------------+
                       |                         |
                       v                         v
+------------------------------------------------------------------------------+
|                    EXECUTION-CLAUDE-CODE (Scale to Zero)                      |
|  +------------------------------------------------------------------------+  |
|  | For complex queries requiring:                                         |  |
|  | - Multi-step reasoning                                                 |  |
|  | - Code execution                                                       |  |
|  | - Tool orchestration                                                   |  |
|  | - Agentic workflows                                                    |  |
|  |                                                                        |  |
|  | Uses: Docker Model Runner running Claude Code CLI                      |  |
|  | Memory: ~2GB (Claude Code + context)                                   |  |
|  | Cold Start: ~8s                                                        |  |
|  +------------------------------------------------------------------------+  |
+--------------------------------------+---------------------------------------+
                                       |
                                       v
+------------------------------------------------------------------------------+
|                          CHAT TELEMETRY LAYER                                 |
|  Query -> Route -> Outcome -> Qdrant (learning) + Prometheus (metrics)       |
+------------------------------------------------------------------------------+
```

## The Intelligence Cascade

```
Query arrives
     |
     v
+------------------+
| Tier 0: Cache    |  <1ms   - Exact match (recent identical query)
+--------+---------+
         | miss
         v
+------------------+
| Tier 1: Keyword  |  <10ms  - Pattern match ("list pods", "show status")
+--------+---------+
         | miss
         v
+------------------+
| Tier 2: Qdrant   |  <50ms  - Similarity to past successful queries
|    Similarity    |          Uses learned patterns from history
+--------+---------+
         | miss
         v
+------------------+
| Tier 3: Local    |  ~500ms - Docker Model Runner (Phi-4/Qwen)
|    DMR Reason    |          Fast local inference, no API cost
+--------+---------+
         | complex/uncertain
         v
+------------------+
| Tier 4: Claude   |  ~2-5s  - Claude Code for agentic tasks
|      Code        |          Full reasoning, tool use, code execution
+------------------+
```

## Layers

| Layer | Purpose | Memory | Cold Start | Scale |
|-------|---------|--------|------------|-------|
| `chat-activator` | Route queries, wake layers, orchestrate | 128MB | Always on | 2 replicas |
| `chat-qdrant` | Vector memory, conversation history, patterns | 512MB | Always on | 1 replica |
| `reasoning-dmr` | Local LLM via Docker Model Runner | 4GB | ~12s | 0->1 |
| `execution-local-response` | Simple queries, cached responses | 256MB | ~3s | 0->1 |
| `execution-claude-code` | Complex queries via Claude Code | 2GB | ~8s | 0->1 |
| `chat-telemetry` | Metrics, audit, learning feedback | 128MB | ~2s | 0->1 |

**Total when idle:** ~640MB
**Total when active (local):** ~5GB
**Total when active (Claude Code):** ~7GB
**API Cost when local:** $0

## Key Innovation: Docker Model Runner Integration

The `reasoning-dmr` layer uses Docker Model Runner to provide:

1. **OpenAI-Compatible API** at `localhost:12434/v1`
2. **Local Model Inference** with Phi-4, Qwen, or other GGUF models
3. **Zero API Costs** for the majority of queries
4. **Privacy** - queries never leave the cluster

```yaml
# reasoning-dmr deployment
env:
  - name: DMR_MODEL
    value: "microsoft/phi-4"
  - name: DMR_ENDPOINT
    value: "http://localhost:12434/v1"
  - name: OPENAI_API_BASE
    value: "http://localhost:12434/v1"
```

## Claude Code Integration

For complex queries that exceed local model capabilities, we escalate to Claude Code running inside the cluster:

```python
# execution-claude-code layer
async def execute_claude_code(query: str, context: dict) -> dict:
    """
    Execute query using Claude Code CLI.

    Claude Code has access to:
    - MCP servers (kubernetes, sandfly, proxmox, etc.)
    - File system (read-only codebase access)
    - Tool execution
    """
    result = await claude_code.execute(
        prompt=query,
        context=context,
        mcp_servers=["kubernetes", "cortex"],
        timeout=60
    )
    return result
```

## Quick Start

### Prerequisites

- Kubernetes cluster (k3s recommended)
- KEDA installed with HTTP Add-on
- ArgoCD for GitOps deployment
- Docker Model Runner available in cluster
- Anthropic API key (for Claude Code escalation)

### Deploy with ArgoCD

```bash
# Add the ApplicationSet
kubectl apply -f argocd/applicationset.yaml
```

### Deploy with Helm (manual)

```bash
# Create namespace
kubectl create namespace cortex-chat

# Create secrets
kubectl create secret generic chat-credentials \
  --namespace cortex-chat \
  --from-literal=anthropic-api-key="YOUR_KEY"

# Install layers (order matters)
helm install chat-qdrant ./charts/chat-qdrant -n cortex-chat
helm install chat-activator ./charts/chat-activator -n cortex-chat
helm install reasoning-dmr ./charts/reasoning-dmr -n cortex-chat
helm install execution-local-response ./charts/execution-local-response -n cortex-chat
helm install execution-claude-code ./charts/execution-claude-code -n cortex-chat
helm install chat-telemetry ./charts/chat-telemetry -n cortex-chat
```

## API

### Chat Endpoint

```bash
POST http://chat-activator.cortex-chat:8080/chat
Content-Type: application/json

{
  "message": "What pods are failing in the cortex namespace?",
  "conversation_id": "conv-abc123",
  "context": {
    "user": "ryan",
    "namespace": "cortex"
  }
}
```

### Response

```json
{
  "success": true,
  "response": "There are 2 pods in CrashLoopBackOff in the cortex namespace:\n- moe-router-abc123 (OOMKilled)\n- blog-writer-def456 (ImagePullBackOff)",
  "conversation_id": "conv-abc123",
  "metadata": {
    "route_tier": "local",
    "model_used": "phi-4",
    "latency_ms": 450,
    "cost_usd": 0.0,
    "layers_activated": ["reasoning-dmr", "execution-local-response"]
  }
}
```

### Escalation Example

```json
{
  "message": "Investigate why the moe-router keeps crashing and fix it",
  "conversation_id": "conv-abc123"
}
```

```json
{
  "success": true,
  "response": "I analyzed the moe-router crashes and found the issue...\n\n**Root Cause:** Memory limit too low for Qdrant connection pooling...\n\n**Fix Applied:** Updated deployment to increase memory from 256Mi to 512Mi...",
  "conversation_id": "conv-abc123",
  "metadata": {
    "route_tier": "claude-code",
    "model_used": "claude-sonnet-4-20250514",
    "latency_ms": 4200,
    "cost_usd": 0.003,
    "layers_activated": ["reasoning-dmr", "execution-claude-code"],
    "tools_used": ["kubectl", "logs", "edit"],
    "escalation_reason": "agentic_task"
  }
}
```

## Learning Loop

Every interaction improves future routing:

1. **Query Classification** - Intent + complexity scoring
2. **Routing Decision** - Which tier/layer to use
3. **Execution** - Run query through selected path
4. **Outcome Capture** - Success/failure, latency, cost
5. **Pattern Storage** - Embed query + outcome in Qdrant
6. **Future Matching** - Similar queries reuse learned routes

Over time:
- More queries resolve locally (Tier 1-3)
- Fewer escalations to Claude Code (Tier 4)
- Cost approaches $0 for routine operations
- Response times improve

## Monitoring

```
# Activator
cortex_chat_queries_total{tier="local|claude_code"}
cortex_chat_routing_latency_seconds{tier="keyword|similarity|dmr"}
cortex_chat_cost_usd_total{model="phi-4|claude-sonnet"}

# DMR
cortex_dmr_inference_seconds{model="phi-4"}
cortex_dmr_tokens_total{direction="input|output"}

# Claude Code
cortex_claude_code_executions_total{status="success|failure"}
cortex_claude_code_tools_used_total{tool="kubectl|edit|..."}

# Learning
cortex_chat_similarity_hits_total
cortex_chat_pattern_confidence{pattern="high|medium|low"}
```

## Configuration

### Routing Thresholds

```yaml
routing:
  # Complexity score thresholds
  localThreshold: 50      # <50 = local response
  dmrThreshold: 75        # 50-75 = DMR reasoning
  claudeThreshold: 100    # >75 = Claude Code

  # Similarity matching
  similarityThreshold: 0.92  # Min similarity for reuse
  confidenceThreshold: 0.85  # Min confidence for auto-route

  # Escalation triggers
  escalateOnUncertain: true
  escalateOnToolNeed: true
  escalateOnMultiStep: true
```

### Model Selection

```yaml
models:
  local:
    primary: "microsoft/phi-4"
    fallback: "Qwen/Qwen2.5-7B-Instruct"
    contextLength: 4096

  claude:
    model: "claude-sonnet-4-20250514"
    maxTokens: 4096
    temperature: 0.1
```

## License

MIT
