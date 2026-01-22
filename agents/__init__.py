"""
Cortex Agent Framework

A Python-first agent framework for Cortex's agentic architecture.

This package provides:
- BaseMaster: Base class for master agents (routing, spawning workers)
- BaseWorker: Base class for worker agents (Claude API conversations, MCP tools)
- Messaging: Redis Streams-based inter-agent messaging
- Registry: Agent tracking and discovery
- Lifecycle: Agent spawning, monitoring, and termination

Architecture:
    Masters → spawn workers → workers converse with Claude API
    Redis Streams for task queues and inter-agent communication
    Full async/await support with asyncio
"""

from agents.base_master import BaseMaster
from agents.base_worker import BaseWorker
from agents.messaging import AgentMessage, MessageBroker
from agents.registry import AgentRegistry, AgentStatus
from agents.lifecycle import AgentLifecycle, SpawnMode

__all__ = [
    "BaseMaster",
    "BaseWorker",
    "AgentMessage",
    "MessageBroker",
    "AgentRegistry",
    "AgentStatus",
    "AgentLifecycle",
    "SpawnMode",
]

__version__ = "0.1.0"
