# Cortex Unified MCP Server

The brain of Cortex for Claude Code integration. This MCP server unifies all Cortex capabilities under a single interface, routing queries through the Chat Layer Fabric for intelligent cost optimization.

## Architecture

```
Claude Code CLI
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│               CORTEX UNIFIED MCP SERVER                     │
│                                                             │
│  Tools:                                                     │
│  ├── cortex_chat_complete     → Chat Fabric (Tier 0-4)     │
│  ├── cortex_chat_analyze      → Query analysis             │
│  ├── cortex_chat_status       → Fabric health              │
│  │                                                          │
│  ├── cortex_context_cluster   → Prometheus metrics         │
│  ├── cortex_context_nodes     → Node metrics               │
│  ├── cortex_context_alerts    → Active alerts              │
│  ├── cortex_context_inject    → Full context (session start)│
│  │                                                          │
│  ├── cortex_memory_recall     → Conversation history       │
│  ├── cortex_memory_store      → Save messages              │
│  ├── cortex_memory_search     → Similarity search          │
│  │                                                          │
│  ├── cortex_agents_list       → List agents                │
│  ├── cortex_agents_submit     → Submit task                │
│  └── cortex_agents_*          → Agent framework            │
│                                                             │
│  Passthrough:                                               │
│  ├── k8s_*                    → Kubernetes MCP             │
│  ├── proxmox_*                → Proxmox MCP                │
│  ├── sandfly_*                → Sandfly MCP                │
│  ├── unifi_*                  → UniFi MCP                  │
│  └── n8n_*                    → n8n MCP                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND SERVICES                         │
│                                                             │
│  ├── Chat Activator (cortex-chat)                          │
│  │   └── Routes: Cache → Pattern → Qdrant → DMR → Anthropic│
│  │                                                          │
│  ├── Qdrant (cortex-chat)                                  │
│  │   └── Conversation memory, routing patterns             │
│  │                                                          │
│  ├── Prometheus (cortex-system)                            │
│  │   └── Cluster metrics, node metrics, alerts             │
│  │                                                          │
│  ├── Redis (cortex-system)                                 │
│  │   └── Agent registry, task streams                      │
│  │                                                          │
│  └── MCP Servers (cortex-system)                           │
│      └── kubernetes, proxmox, sandfly, unifi, n8n          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Tool: `cortex_chat_complete`

This is THE way for Claude Code to communicate with Cortex. Instead of calling Anthropic API directly, Claude Code calls this tool, and Cortex decides the optimal response path:

| Tier | Source | Cost | Latency |
|------|--------|------|---------|
| 0 | Cache | Free | <1ms |
| 1 | Keyword Pattern | Free | <10ms |
| 2 | Qdrant Similarity | Free | <50ms |
| 3 | DMR (Phi-4) | Free | ~500ms |
| 4 | Anthropic API | Paid | ~2-5s |

**80%+ of queries are handled by Tier 0-3** (free, fast).

## Usage

### Local Development

```bash
# Install dependencies
pip install -e .

# Run the server
cortex-unified

# Or with debug logging
LOG_LEVEL=10 cortex-unified
```

### Claude Code Configuration

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "cortex-unified": {
      "command": "cortex-unified"
    }
  }
}
```

Or for K8s deployment:

```json
{
  "mcpServers": {
    "cortex-unified": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://cortex-unified-mcp.cortex-system:3000"]
    }
  }
}
```

### Session Start Workflow

When starting a new Claude Code session, inject Cortex context:

```
> Use cortex_context_inject to see the cluster state
```

This provides:
- Cluster CPU/memory/pod status
- Node health
- Active alerts
- Problem pods
- MCP server availability

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_ACTIVATOR_URL` | `http://chat-activator.cortex-chat:8080` | Chat Fabric endpoint |
| `QDRANT_URL` | `http://chat-qdrant.cortex-chat:6333` | Vector memory endpoint |
| `PROMETHEUS_URL` | `http://prometheus-server.cortex-system:80` | Metrics endpoint |
| `REDIS_URL` | `redis://redis.cortex-system:6379` | Agent framework endpoint |
| `LOG_LEVEL` | `20` | Logging level (10=DEBUG, 20=INFO) |

## Tool Reference

### Chat Tools

- `cortex_chat_complete` - Route message through intelligence cascade
- `cortex_chat_analyze` - Analyze query without executing
- `cortex_chat_status` - Check fabric health

### Context Tools

- `cortex_context_cluster` - Get cluster metrics
- `cortex_context_nodes` - Get node metrics
- `cortex_context_alerts` - Get active alerts
- `cortex_context_pods_problems` - Get problem pods
- `cortex_context_inject` - Full context injection
- `cortex_context_mcp_health` - MCP server health

### Memory Tools

- `cortex_memory_recall` - Recall conversation history
- `cortex_memory_store` - Store message
- `cortex_memory_list_sessions` - List sessions
- `cortex_memory_delete_session` - Delete session
- `cortex_memory_search` - Similarity search
- `cortex_memory_health` - Check Qdrant health

### Agent Tools

- `cortex_agents_list` - List registered agents
- `cortex_agents_status` - Get agent status
- `cortex_agents_submit` - Submit task (async)
- `cortex_agents_submit_and_wait` - Submit and wait for result
- `cortex_agents_find_worker` - Find available worker
- `cortex_agents_health` - Check Redis health

### Passthrough Tools

Any tool with prefix `k8s_`, `proxmox_`, `sandfly_`, `unifi_`, or `n8n_` is automatically routed to the corresponding MCP server.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/

# Format
ruff format src/
```

## License

MIT
