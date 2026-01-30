# Cortex Terminal

Claude Code + tmux running in K3s, accessible from anywhere via Tailscale.

## Overview

This is your "forever terminal" for Cortex. It provides:

- **Claude Code CLI** with full MCP access to all Cortex capabilities
- **tmux** for session persistence (survives disconnects)
- **Tailscale** for secure remote access from anywhere
- **Cortex Live TUI** for cluster monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CORTEX TERMINAL POD                     │
│                     (cortex-system namespace)               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 TERMINAL CONTAINER                   │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │              tmux session: cortex            │   │   │
│  │  │                                              │   │   │
│  │  │  ┌────────────────────────────────────────┐  │   │   │
│  │  │  │           CLAUDE CODE CLI              │  │   │   │
│  │  │  │                                        │  │   │   │
│  │  │  │  MCP: cortex-unified                   │  │   │   │
│  │  │  │  ├── cortex_chat_complete              │  │   │   │
│  │  │  │  ├── cortex_context_*                  │  │   │   │
│  │  │  │  ├── cortex_memory_*                   │  │   │   │
│  │  │  │  ├── cortex_agents_*                   │  │   │   │
│  │  │  │  └── k8s_*, proxmox_*, sandfly_*, ...  │  │   │   │
│  │  │  │                                        │  │   │   │
│  │  │  └────────────────────────────────────────┘  │   │   │
│  │  │                                              │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              TAILSCALE SIDECAR                       │   │
│  │                                                      │   │
│  │  Hostname: cortex-terminal                           │   │
│  │  Access: tailscale ssh cortex-terminal               │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ Tailscale Mesh VPN
         │
┌─────────────────┐
│ Termius App     │
│ (iOS/Android)   │
│                 │
│ or              │
│                 │
│ Any SSH Client  │
│ (laptop/desktop)│
└─────────────────┘
```

## Quick Start

### 1. Deploy to K3s

```bash
# Ensure you have the Anthropic API key secret
kubectl create secret generic cortex-chat-secrets \
  --namespace cortex-system \
  --from-literal=anthropic-api-key=sk-ant-...

# Ensure you have Tailscale auth key (optional)
kubectl create secret generic tailscale-auth \
  --namespace cortex-system \
  --from-literal=authkey=tskey-auth-...

# Deploy
kubectl apply -f k8s/deployment.yaml
```

### 2. Connect via Tailscale

```bash
# From any device on your tailnet
tailscale ssh cortex-terminal
```

Or use Termius app on mobile:
1. Add host: `cortex-terminal`
2. Connect via Tailscale

### 3. Attach to tmux Session

```bash
# Once connected
tmux attach -t cortex
```

### 4. Start Claude Code

```bash
# Inside tmux
claude

# First command - inject Cortex context
> Use cortex_context_inject to see cluster state
```

## Access Methods

### Via kubectl (direct)

```bash
kubectl exec -it -n cortex-system deploy/cortex-terminal -c terminal -- bash

# Then attach to tmux
tmux attach -t cortex
```

### Via Tailscale SSH

```bash
tailscale ssh cortex-terminal

# Attach to tmux
tmux attach -t cortex
```

### Via Termius (mobile)

1. Install Termius on iOS/Android
2. Add new host:
   - Hostname: `cortex-terminal` (via Tailscale)
   - Or add Tailscale as a gateway
3. Connect and run `tmux attach -t cortex`

## tmux Commands

| Command | Description |
|---------|-------------|
| `tmux attach -t cortex` | Attach to session |
| `Ctrl+b d` | Detach from session |
| `Ctrl+b c` | Create new window |
| `Ctrl+b n` | Next window |
| `Ctrl+b p` | Previous window |
| `Ctrl+b \|` | Split pane vertically |
| `Ctrl+b -` | Split pane horizontally |
| `Ctrl+b z` | Toggle pane zoom |

Mouse scrolling is enabled - just scroll with your mouse/trackpad.

## Session Persistence

- Sessions survive network disconnects
- Sessions survive pod restarts (home directory is persistent)
- Conversation history is stored in Qdrant
- Use `cortex_memory_recall` to restore context

## Workflow Example

```bash
# 1. Connect from phone
tailscale ssh cortex-terminal

# 2. Attach to session
tmux attach -t cortex

# 3. Start Claude Code
claude

# 4. Inject context
> Use cortex_context_inject

# 5. Ask about your infrastructure
> What pods are having problems?

# 6. Detach when done (Ctrl+b d)

# 7. Later, reconnect from laptop
tmux attach -t cortex
# Context is preserved!
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SSH` | `false` | Enable SSH daemon |
| `ANTHROPIC_API_KEY` | (from secret) | Claude API key |

### Claude Code Config

Located at `/home/cortex/.config/claude-code/config.json`:

```json
{
  "mcpServers": {
    "cortex-unified": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://cortex-unified-mcp.cortex-system:3000"]
    }
  },
  "model": "claude-sonnet-4-20250514",
  "maxTurns": 25
}
```

## Storage

- `/home/cortex` - Persistent (5Gi PVC)
- Tailscale state - Persistent (100Mi PVC)

## Security

- Non-root user (`cortex`, UID 1000)
- Password authentication disabled
- Read-only access to cluster resources
- Tailscale handles authentication
- API key stored in K8s secret

## Troubleshooting

### Can't connect via Tailscale

```bash
# Check Tailscale sidecar logs
kubectl logs -n cortex-system deploy/cortex-terminal -c tailscale

# Verify Tailscale auth key is set
kubectl get secret tailscale-auth -n cortex-system
```

### Claude Code not finding MCP server

```bash
# Check if cortex-unified-mcp is running
kubectl get pods -n cortex-system -l app.kubernetes.io/name=cortex-unified-mcp

# Check service endpoint
kubectl get svc cortex-unified-mcp -n cortex-system
```

### Session not persisting

```bash
# Check PVC is bound
kubectl get pvc -n cortex-system cortex-terminal-home

# Check home directory permissions
kubectl exec -n cortex-system deploy/cortex-terminal -c terminal -- ls -la /home/cortex
```

## License

MIT
