# Cortex Quickstart Guide

Get Cortex and its MCP servers running in 10 minutes.

## What is Cortex?

Cortex is a multi-agent AI system for autonomous GitHub repository management. It uses a master-worker architecture where master agents (Coordinator, Development, Security, Inventory, CI/CD) route tasks to specialized workers that handle implementation, testing, scanning, fixes, and documentation.

**MCP Servers** expose Cortex capabilities to Claude Desktop and other AI agents, letting you interact with Cortex through natural language.

## Prerequisites

- **Python 3.10+** with `uv` package manager
- **Node.js 18+** for dashboard and MCP servers
- **Claude Desktop** for MCP integration
- **Git** for version control
- **Anthropic API Key** for Claude agents

## Quick Setup

### 1. Clone and Configure

```bash
git clone https://github.com/ry-ops/cortex.git
cd cortex

# Configure environment
cp .env.example .env
# Edit .env and add your keys:
# ANTHROPIC_API_KEY=your-key
# API_KEY=dashboard-key
```

### 2. Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Optional: Python SDK for ML features
cd python-sdk && python3 -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -r requirements.txt && cd ..
```

### 3. Configure Claude Desktop MCP

Edit your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "cortex-coordinator": {
      "command": "node",
      "args": ["/absolute/path/to/cortex/mcp-server/index.js"],
      "env": {
        "CORTEX_HOME": "/absolute/path/to/cortex",
        "MASTER_TYPE": "coordinator"
      }
    },
    "cortex-development": {
      "command": "node",
      "args": ["/absolute/path/to/cortex/mcp-server/index.js"],
      "env": {
        "CORTEX_HOME": "/absolute/path/to/cortex",
        "MASTER_TYPE": "development"
      }
    },
    "cortex-security": {
      "command": "node",
      "args": ["/absolute/path/to/cortex/mcp-server/index.js"],
      "env": {
        "CORTEX_HOME": "/absolute/path/to/cortex",
        "MASTER_TYPE": "security"
      }
    },
    "cortex-inventory": {
      "command": "node",
      "args": ["/absolute/path/to/cortex/mcp-server/index.js"],
      "env": {
        "CORTEX_HOME": "/absolute/path/to/cortex",
        "MASTER_TYPE": "inventory"
      }
    },
    "cortex-cicd": {
      "command": "node",
      "args": ["/absolute/path/to/cortex/mcp-server/index.js"],
      "env": {
        "CORTEX_HOME": "/absolute/path/to/cortex",
        "MASTER_TYPE": "cicd"
      }
    }
  }
}
```

Replace `/absolute/path/to/cortex` with your actual installation path.

### 4. Start Cortex

```bash
# Start coordinator
./scripts/run-coordinator-master.sh

# In separate terminals, start other masters:
./scripts/run-development-master.sh
./scripts/run-security-master.sh

# Check status
./scripts/status-check.sh
```

### 5. Verify MCP in Claude Desktop

Restart Claude Desktop and look for the hammer icon. Try: **"Show me the current Cortex task queue"**

## First Commands to Try

### Via Claude Desktop (MCP)

- "Show me the current Cortex task queue"
- "What workers are currently active?"
- "Route this task: Implement user authentication"
- "Show me the coordinator master state"

### Via Terminal

```bash
# View coordination files
cat coordination/task-queue.json | jq
cat coordination/worker-pool.json | jq

# Monitor system
./scripts/system-live.sh
./scripts/worker-status.sh
```

## MCP Servers Overview

| Server | Purpose | Key Tools |
|--------|---------|-----------|
| **coordinator** | Task routing (MoE) | `route_task` |
| **development** | Features, bugs, refactoring | `spawn_worker`, `get_task_queue` |
| **security** | CVE scanning, fixes | `scan_repository`, `fix_vulnerability` |
| **inventory** | Repository cataloging | `catalog_repository`, `generate_docs` |
| **cicd** | Build automation | `run_build`, `deploy_artifact` |

## Troubleshooting

**MCP not showing in Claude Desktop?**
```bash
# Test MCP server manually
node mcp-server/index.js
# Verify absolute paths in config, restart Claude Desktop
```

**Token budget errors?**
```bash
cat coordination/token-budget.json | jq
# Budget resets daily (270k tokens)
```

**Workers not spawning?**
```bash
./scripts/daemon-control.sh status
./scripts/daemon-control.sh restart
```

**Port conflicts?**
```bash
lsof -i :9000  # Default dashboard port
# Change in .env: API_PORT=9001
```

## What's Next?

### Documentation
- [Master-Worker Architecture](./master-worker-architecture.md) - Technical deep dive
- [API Reference](./API-REFERENCE.md) - REST API docs
- [Agent Guide](./agent-guide.md) - Build custom agents
- [Coordination Protocol](./coordination-protocol.md) - File-based coordination

### Advanced Features
- [ML/AI Architecture](./ML-AI-ARCHITECTURE.md) - Neural routing
- [Observability Pipeline](../README.md#observability-pipeline) - Event processing
- [RAG System](./rag-system.md) - Vector search
- [Governance Framework](../GOVERNANCE-ARCHITECTURE.md) - Policies

### Operations
- [Monitoring Guide](./QUICK-START-MONITORING.md)
- [Event-Driven Architecture](./EVENT-DRIVEN-ARCHITECTURE.md)

## Minimal Setup (No ML)

For simplest setup without ML dependencies:

```bash
# .env
ANTHROPIC_API_KEY=your-key
API_KEY=dashboard-key
SEMANTIC_ROUTING_ENABLED=false
PYTORCH_ROUTING_ENABLED=false
RAG_ENABLED=false
```

Gets you basic keyword routing with full core functionality.

---

**Time to Running**: 10 minutes | **Daily Token Budget**: 270k | **Success Rate**: 94%+
