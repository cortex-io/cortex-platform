# Cortex + Claude Code Terminal Integration

## Executive Summary

Replace the web chat interface with Claude Code as the native terminal interface to Cortex, while preserving all existing chat-layer-fabric intelligence and routing. Claude Code becomes a **consumer** of Cortex, not a parallel path.

**Key Principle**: Claude Code calls Cortex, Cortex decides how to respond (cache, pattern, Qdrant, DMR, or Anthropic API).

---

## Current State Documentation

### Chat Layer Fabric (PRESERVE)

```
Namespace: cortex-chat
Entry Point: POST http://chat-activator.cortex-chat:8080/chat

Request Flow:
┌─────────────────────────────────────────────────────────────────┐
│                      CHAT ACTIVATOR                             │
│                   (Always-on, 2 replicas)                       │
│                                                                 │
│  Tier 0: Cache ────────────────────────────────────> Response   │
│     │ (miss)                                                    │
│     ▼                                                           │
│  Tier 1: Keyword Pattern ──────────────────────────> Response   │
│     │ (miss)                                                    │
│     ▼                                                           │
│  Tier 2: Qdrant Similarity (0.92 threshold) ───────> Response   │
│     │ (miss)                                                    │
│     ▼                                                           │
│  Complexity Scoring (0-100)                                     │
│     │                                                           │
│     ├─ 0-50: Tier 3 → DMR (Phi-4 local) ───────────> Response   │
│     │                                                           │
│     └─ 51-100: Tier 4 → Claude Code ───────────────> Response   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Components:
- chat-activator: Routing, complexity scoring, intent classification
- chat-qdrant: Vector memory (routing_patterns, conversations, tool_patterns)
- reasoning-dmr: Local Phi-4 inference via Docker Model Runner
- execution-claude-code: Anthropic API calls (WILL BE MODIFIED)
- chat-telemetry: Metrics and learning feedback
```

**What We Keep**:
- Activator routing logic
- Qdrant collections and similarity search
- DMR for local inference
- KEDA scaling configuration
- Prometheus metrics
- All Helm charts and K8s manifests

**What We Disconnect**:
- `execution-claude-code` layer's direct Anthropic calls
- Web-facing API endpoint (keep internal only)

---

### MCP Servers (PRESERVE + EXTEND)

```
Current MCP Gateway: cortex-mcp-server.cortex-system:3000

MoE Routing Keywords → System:
├── network/wifi/vlan → UniFi
├── vm/container/hypervisor → Proxmox
├── security/threat/cve → Sandfly
├── vulnerability/dependabot → GitHub Security
├── pod/deployment/kubectl → Kubernetes
├── workflow/automation → n8n
├── vpn/wireguard/mesh → Tailscale
└── blog/knowledge → School

Available Tools (100+):
├── cortex.* (3) - query, get_status, learn_today
├── kubernetes.* (12) - cluster, pods, deployments, services, logs
├── proxmox.* (20) - nodes, VMs, containers, snapshots
├── sandfly.* (30) - hosts, forensics, scans, alerts, rules
├── unifi.* (varies) - networks, devices, clients
├── n8n.* (5) - workflows, executions
└── github-security.* (10) - vulnerabilities, repos
```

**What We Extend**:
- Add `cortex.chat.complete` tool (routes through fabric)
- Add `cortex.memory.*` tools (Qdrant access)
- Add `cortex.agents.*` tools (agent framework)
- Add `cortex.context.*` tools (state injection)

---

### Cortex Live TUI (EXTEND)

```
Location: /services/cortex-live/
Framework: Textual (Python)
Theme: Amber monochrome (#ffb000)

Current Screens:
├── Dashboard (main) - ClusterPulse, NodesPanel, PodDistribution, LiveEvents
├── Pods (p) - DataTable with all pods
├── Nodes (n) - DataTable with node metrics
├── Agents (a) - K8s Jobs status
├── Logs (l) - Pod log viewer
└── Search (/) - Pod/node/event search

Data Sources:
├── PrometheusClient - CPU, memory, network, disk metrics
└── KubernetesClient - Pods, nodes, jobs, events, logs
```

**What We Add**:
- Chat screen (c) - Claude Code integration
- Context-aware prompts from current view
- Session state sync

---

### Agent Framework (EXPOSE VIA MCP)

```
Architecture: Master-Worker via Redis Streams

┌─────────────────────────────────┐
│     Coordinator Master          │
│     (Routes to divisions)       │
└───────────────┬─────────────────┘
                │
    ┌───────────┼───────────┬─────────────┐
    ▼           ▼           ▼             ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐
│Security│ │ Infra  │ │  CI/CD   │ │ Inventory │
│ Master │ │ Master │ │  Master  │ │  Master   │
└───┬────┘ └────────┘ └──────────┘ └───────────┘
    │
    ├── Sandfly Worker (Claude + MCP tools)
    └── GitHub Security Worker

Communication: Redis Streams (publish/consume/ack)
Registry: Redis hashes with 30s heartbeat
Deployment: K8s Jobs with TTL
```

**What We Expose**:
- `cortex.agents.submit` - Submit task to agent
- `cortex.agents.list` - List available agents
- `cortex.agents.status` - Get agent status
- `cortex.agents.result` - Get task result

---

## Architecture: Claude Code as Cortex Native

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           K3S CLUSTER                                   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    CORTEX LIVE POD                                │  │
│  │                    (with Claude Code)                             │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │                   tmux session                              │  │  │
│  │  │                                                             │  │  │
│  │  │  ┌─────────────────────────────────────────────────────┐   │  │  │
│  │  │  │              CLAUDE CODE CLI                        │   │  │  │
│  │  │  │                                                     │   │  │  │
│  │  │  │  MCP Servers:                                       │   │  │  │
│  │  │  │  ├── cortex-unified (NEW - the brain)               │   │  │  │
│  │  │  │  │   ├── cortex.chat.complete → Chat Fabric         │   │  │  │
│  │  │  │  │   ├── cortex.context.* → State injection         │   │  │  │
│  │  │  │  │   ├── cortex.memory.* → Qdrant                   │   │  │  │
│  │  │  │  │   └── cortex.agents.* → Agent framework          │   │  │  │
│  │  │  │  │                                                  │   │  │  │
│  │  │  │  ├── kubernetes → K8s operations                    │   │  │  │
│  │  │  │  ├── proxmox → VM operations                        │   │  │  │
│  │  │  │  ├── sandfly → Security operations                  │   │  │  │
│  │  │  │  ├── unifi → Network operations                     │   │  │  │
│  │  │  │  └── n8n → Workflow automation                      │   │  │  │
│  │  │  │                                                     │   │  │  │
│  │  │  └─────────────────────────────────────────────────────┘   │  │  │
│  │  │                                                             │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │              CORTEX LIVE TUI (optional view)               │  │  │
│  │  │              Dashboard | Pods | Nodes | Chat | ...         │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                 CORTEX-UNIFIED MCP SERVER                         │  │
│  │                 (Routes to appropriate backend)                   │  │
│  │                                                                   │  │
│  │  cortex.chat.complete ──┬──> Chat Activator ──> Tier 0-4         │  │
│  │                         │                                         │  │
│  │  cortex.context.get ────┼──> Prometheus + K8s API                │  │
│  │                         │                                         │  │
│  │  cortex.memory.* ───────┼──> Qdrant (cortex-chat)                │  │
│  │                         │                                         │  │
│  │  cortex.agents.* ───────┼──> Redis Streams + Registry            │  │
│  │                         │                                         │  │
│  │  cortex.k8s.* ──────────┼──> Kubernetes MCP Server               │  │
│  │  cortex.proxmox.* ──────┼──> Proxmox MCP Server                  │  │
│  │  cortex.sandfly.* ──────┼──> Sandfly MCP Server                  │  │
│  │  cortex.unifi.* ────────┼──> UniFi MCP Server                    │  │
│  │  cortex.n8n.* ──────────┴──> n8n MCP Server                      │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│              ┌───────────────┼───────────────┐                          │
│              ▼               ▼               ▼                          │
│  ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐               │
│  │  Chat Fabric    │ │   Qdrant    │ │  Agent Masters  │               │
│  │  (cortex-chat)  │ │   (memory)  │ │  + Workers      │               │
│  │                 │ │             │ │  (Redis)        │               │
│  │  ├─ Activator   │ │             │ │                 │               │
│  │  ├─ DMR (Phi-4) │ │             │ │                 │               │
│  │  └─ Telemetry   │ │             │ │                 │               │
│  └─────────────────┘ └─────────────┘ └─────────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                    ▲
                    │ SSH over Tailscale
                    │
            ┌───────────────┐
            │   Termius     │
            │   (anywhere)  │
            └───────────────┘
```

---

## The Key Innovation: cortex.chat.complete

This MCP tool makes Claude Code a **Cortex citizen**:

```python
@mcp_tool("cortex.chat.complete")
async def chat_complete(
    message: str,
    context: Optional[dict] = None,
    force_tier: Optional[str] = None  # "cache", "pattern", "similarity", "dmr", "anthropic"
) -> ChatResponse:
    """
    Route a chat message through Cortex intelligence cascade.

    Claude Code calls this instead of Anthropic API directly.
    Cortex decides the optimal response path.
    """

    # 1. Enrich context with current Cortex state
    enriched_context = await inject_cortex_context(context)

    # 2. Route through Chat Activator
    response = await http_client.post(
        "http://chat-activator.cortex-chat:8080/chat",
        json={
            "message": message,
            "context": enriched_context,
            "force_tier": force_tier
        }
    )

    # 3. Return with routing metadata
    return ChatResponse(
        content=response["response"],
        tier_used=response["metadata"]["route_tier"],
        model_used=response["metadata"]["model_used"],
        cost_usd=response["metadata"]["cost_usd"],
        latency_ms=response["metadata"]["latency_ms"]
    )
```

**Why This Matters**:
- Simple queries (greetings, status checks) → Cache/Pattern/DMR (free, fast)
- Complex queries → Anthropic API (paid, but smart)
- Claude Code gets full Cortex context automatically
- All queries recorded in Qdrant for learning

---

## Implementation Phases

### Phase 1: Cortex Unified MCP Server (P0)

**New Service**: `/services/mcp-servers/cortex-unified/`

**Tools to Implement**:

| Tool | Backend | Purpose |
|------|---------|---------|
| `cortex.chat.complete` | Chat Activator | Route messages through fabric |
| `cortex.context.cluster` | Prometheus + K8s | Current cluster state |
| `cortex.context.alerts` | Sandfly | Active security alerts |
| `cortex.context.inject` | Aggregator | Full context for session start |
| `cortex.memory.recall` | Qdrant | Conversation history |
| `cortex.memory.store` | Qdrant | Save decisions/patterns |
| `cortex.memory.search` | Qdrant | Similarity search |
| `cortex.agents.submit` | Redis Streams | Submit task to agent |
| `cortex.agents.list` | Redis Registry | List available agents |
| `cortex.agents.status` | Redis Registry | Get agent status |

**Passthrough Tools** (route to existing MCP servers):
- `cortex.k8s.*` → kubernetes-mcp-server
- `cortex.proxmox.*` → proxmox-mcp-server
- `cortex.sandfly.*` → sandfly-mcp-server
- `cortex.unifi.*` → unifi-mcp-server
- `cortex.n8n.*` → n8n-mcp-server

**Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cortex-unified-mcp
  namespace: cortex-system
spec:
  replicas: 2  # HA
  template:
    spec:
      containers:
      - name: mcp-server
        image: ghcr.io/ry-ops/cortex-unified-mcp:v0.1.0
        ports:
        - containerPort: 3000  # MCP
        - containerPort: 8080  # Health
        env:
        - name: CHAT_ACTIVATOR_URL
          value: "http://chat-activator.cortex-chat:8080"
        - name: QDRANT_URL
          value: "http://chat-qdrant.cortex-chat:6333"
        - name: REDIS_URL
          value: "redis://redis.cortex-system:6379"
        - name: PROMETHEUS_URL
          value: "http://prometheus-server.cortex-system:80"
```

---

### Phase 2: Cortex Live Terminal Pod (P1)

**New Deployment**: Runs Claude Code + tmux + Cortex Live TUI

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

# Install Node.js for Claude Code
RUN apt-get update && apt-get install -y \
    nodejs npm tmux openssh-server curl

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Cortex Live
COPY services/cortex-live /app/cortex-live
RUN pip install /app/cortex-live

# Configure Claude Code MCP servers
COPY claude-code-config.json /root/.config/claude-code/config.json

# tmux configuration for mouse scrolling
RUN echo "set -g mouse on" > /root/.tmux.conf

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

CMD ["/entrypoint.sh"]
```

**Claude Code Config** (`claude-code-config.json`):
```json
{
  "mcpServers": {
    "cortex-unified": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client",
               "http://cortex-unified-mcp.cortex-system:3000"]
    }
  },
  "model": "claude-sonnet-4-20250514",
  "maxTurns": 25
}
```

**Tailscale Sidecar**:
```yaml
containers:
- name: tailscale
  image: tailscale/tailscale:latest
  securityContext:
    capabilities:
      add: ["NET_ADMIN"]
  env:
  - name: TS_AUTHKEY
    valueFrom:
      secretKeyRef:
        name: tailscale-auth
        key: authkey
  - name: TS_HOSTNAME
    value: "cortex-terminal"
```

---

### Phase 3: Chat Fabric Modifications (P1)

**Modify**: `execution-claude-code` layer

**Change**: Instead of calling Anthropic directly, it becomes a passthrough that the unified MCP can invoke when needed.

**New Flow**:
```
Claude Code CLI
    │
    ▼
cortex.chat.complete (MCP tool)
    │
    ▼
Chat Activator (routing)
    │
    ├─ Tier 0-2: Direct response (no API)
    │
    └─ Tier 3-4:
        │
        ├─ DMR (local Phi-4)
        │
        └─ Anthropic API (via execution-claude-code,
           but now Claude Code is the client)
```

**Key Insight**: The `execution-claude-code` layer still exists for the fabric's internal use, but Claude Code terminal sessions route through `cortex.chat.complete` which decides whether to use DMR or escalate.

---

### Phase 4: Cortex Live Chat Integration (P2)

**Modify**: `/services/cortex-live/`

**Add ChatScreen**:
```python
class ChatScreen(Screen):
    """Claude Code chat integrated into Cortex Live TUI"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+l", "clear_chat", "Clear"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(id="chat-history"),
            id="chat-container"
        )
        yield Input(
            placeholder="Ask Cortex anything...",
            id="chat-input"
        )
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        # Get current context from dashboard
        context = self.app.get_current_context()

        # Call cortex.chat.complete via MCP
        response = await self.mcp_client.call(
            "cortex.chat.complete",
            message=event.value,
            context=context
        )

        # Display response
        self.display_message("user", event.value)
        self.display_message("cortex", response.content)
```

**Context Awareness**:
- If viewing Pods screen → inject pod list into context
- If viewing Logs screen → inject recent logs
- If viewing Nodes screen → inject node metrics
- If alert is selected → inject alert details

---

### Phase 5: Session Persistence (P2)

**tmux Session Management**:

**On Session Start**:
```bash
#!/bin/bash
# /entrypoint.sh

# Start tmux session
tmux new-session -d -s cortex

# Inject Cortex context
tmux send-keys -t cortex "claude --mcp-server cortex-unified" Enter

# Auto-run context injection
tmux send-keys -t cortex "/mcp cortex.context.inject" Enter

# Keep alive
tail -f /dev/null
```

**On Detach** (via tmux hook):
```bash
# ~/.tmux.conf
set-hook -g client-detached 'run-shell "cortex-session-save"'
```

**cortex-session-save script**:
```bash
#!/bin/bash
# Save conversation to Qdrant
curl -X POST http://cortex-unified-mcp:8080/session/save \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$TMUX_SESSION\", \"timestamp\": \"$(date -Iseconds)\"}"
```

**On Reattach**:
```bash
# Restore context from Qdrant
claude --mcp-server cortex-unified --resume-session $TMUX_SESSION
```

---

## Disconnection Points

### What Gets Disconnected

1. **Web Chat Endpoint** (optional - keep for API access)
   - `POST /chat` on chat-activator remains, but primary access is terminal

2. **execution-claude-code Direct Anthropic Calls**
   - Still exists but now invoked by fabric routing, not external clients
   - Claude Code terminal → cortex.chat.complete → fabric → (maybe) execution-claude-code

3. **None of the K8s infrastructure** - all preserved

### What Stays Connected

- All Chat Fabric layers (activator, qdrant, dmr, telemetry)
- All MCP servers (kubernetes, proxmox, sandfly, unifi, n8n)
- Agent framework (masters, workers, Redis)
- Prometheus metrics
- KEDA scaling
- Longhorn storage

---

## File Structure

```
/services/
├── mcp-servers/
│   └── cortex-unified/          # NEW - Unified MCP gateway
│       ├── src/
│       │   ├── server.py        # MCP server main
│       │   ├── tools/
│       │   │   ├── chat.py      # cortex.chat.complete
│       │   │   ├── context.py   # cortex.context.*
│       │   │   ├── memory.py    # cortex.memory.*
│       │   │   └── agents.py    # cortex.agents.*
│       │   └── clients/
│       │       ├── chat_activator.py
│       │       ├── qdrant.py
│       │       ├── redis.py
│       │       └── prometheus.py
│       ├── k8s/
│       │   └── deployment.yaml
│       ├── Dockerfile
│       └── pyproject.toml
│
├── cortex-terminal/             # NEW - Terminal access pod
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── claude-code-config.json
│   ├── tmux.conf
│   └── k8s/
│       └── deployment.yaml      # Includes Tailscale sidecar
│
├── cortex-live/                 # MODIFIED - Add chat screen
│   └── src/cortex_live/
│       ├── screens.py           # Add ChatScreen
│       └── chat_client.py       # MCP client wrapper
│
└── chat-layer-fabric/           # PRESERVED - No changes needed
    └── (all existing structure)
```

---

## Success Criteria

1. **SSH via Tailscale** → tmux session → Claude Code with full MCP access
2. **cortex.chat.complete** routes through fabric (visible in tier metadata)
3. **Simple queries** hit cache/pattern/DMR (zero API cost)
4. **Complex queries** escalate to Anthropic (tracked cost)
5. **Session survives disconnect** (phone dies, reattach from laptop)
6. **Cortex Live TUI** has working Chat tab with context awareness
7. **All existing MCP tools** accessible via cortex-unified passthrough
8. **Agent framework** dispatchable via cortex.agents.* tools

---

## Next Steps

1. [ ] Create `/services/mcp-servers/cortex-unified/` skeleton
2. [ ] Implement `cortex.chat.complete` tool
3. [ ] Implement `cortex.context.inject` tool
4. [ ] Create Helm chart for cortex-unified-mcp
5. [ ] Create cortex-terminal Dockerfile
6. [ ] Configure Tailscale sidecar
7. [ ] Test SSH → tmux → Claude Code flow
8. [ ] Add ChatScreen to Cortex Live
9. [ ] Implement session persistence hooks
10. [ ] Documentation and runbooks

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Break existing chat | Keep chat-activator endpoint, add new path |
| MCP server availability | 2 replicas, health probes, circuit breakers |
| Tailscale auth expiry | Use long-lived auth keys, monitor in alerts |
| tmux session corruption | Auto-save state to Qdrant every 60s |
| Cost runaway | Keep existing budget limits in fabric |

---

*Document Version: 1.0*
*Created: 2026-01-29*
*Author: Claude + Ryan*
