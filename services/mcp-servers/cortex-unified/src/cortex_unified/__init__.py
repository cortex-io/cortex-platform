"""
Cortex Unified MCP Server

The brain of Cortex for Claude Code integration. This server exposes:
- cortex.chat.complete - Routes through Chat Fabric (cache → pattern → Qdrant → DMR → Anthropic)
- cortex.context.* - Injects Cortex state into Claude Code sessions
- cortex.memory.* - Conversation history via Qdrant
- cortex.agents.* - Dispatch tasks to agent framework
- Passthrough to all other MCP servers (k8s, proxmox, sandfly, unifi, n8n)
"""

__version__ = "0.1.0"
