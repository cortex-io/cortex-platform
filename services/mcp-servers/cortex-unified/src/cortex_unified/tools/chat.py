"""
cortex.chat.* tools

The core tool: cortex_chat_complete routes through Chat Fabric.
"""

from typing import Any

from mcp.types import Tool, TextContent

from ..clients.chat_activator import ChatActivatorClient

# Global client instance (initialized in server)
_chat_client: ChatActivatorClient | None = None


def set_chat_client(client: ChatActivatorClient):
    """Set the global chat client instance."""
    global _chat_client
    _chat_client = client


CHAT_TOOLS = [
    Tool(
        name="cortex_chat_complete",
        description="""Route a message through Cortex intelligence cascade.

This is THE way to communicate with Cortex. Your message will be routed through:
- Tier 0: Cache (instant, free)
- Tier 1: Keyword patterns (fast, free)
- Tier 2: Qdrant similarity search (fast, free)
- Tier 3: Local DMR/Phi-4 (moderate, free)
- Tier 4: Anthropic API (slower, paid)

Cortex automatically chooses the best tier based on query complexity.
Simple queries are handled locally for speed. Complex queries escalate to Claude.

Use this for ALL questions about your infrastructure, Kubernetes, deployments, etc.
The response includes metadata showing which tier was used and the cost.""",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Your question or request for Cortex"
                },
                "context": {
                    "type": "object",
                    "description": "Optional context (namespace, user, previous_failure, etc.)",
                    "properties": {
                        "namespace": {"type": "string"},
                        "user": {"type": "string"},
                        "previous_failure": {"type": "boolean"},
                        "conversation_length": {"type": "integer"},
                    },
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Optional conversation ID for continuity across messages"
                },
                "force_tier": {
                    "type": "string",
                    "enum": ["cache", "pattern", "similarity", "dmr", "anthropic"],
                    "description": "Force routing to a specific tier (usually leave unset)"
                },
            },
            "required": ["message"]
        }
    ),
    Tool(
        name="cortex_chat_analyze",
        description="""Analyze a query without executing it.

Returns complexity score, intent classification, and predicted routing tier.
Useful for understanding how Cortex will handle a query before sending it.""",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The query to analyze"
                },
                "context": {
                    "type": "object",
                    "description": "Optional context for analysis",
                },
            },
            "required": ["message"]
        }
    ),
    Tool(
        name="cortex_chat_status",
        description="""Get status of Chat Fabric and all its layers.

Shows health of: chat-activator, chat-qdrant, reasoning-dmr, execution-claude-code, chat-telemetry.
Also shows cache size and Qdrant availability.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


async def handle_chat_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle chat tool calls."""
    if _chat_client is None:
        return [TextContent(
            type="text",
            text="Error: Chat client not initialized"
        )]

    if name == "cortex_chat_complete":
        response = await _chat_client.chat_complete(
            message=arguments["message"],
            context=arguments.get("context"),
            conversation_id=arguments.get("conversation_id"),
            force_tier=arguments.get("force_tier"),
        )

        if not response.success:
            return [TextContent(
                type="text",
                text=f"Error: {response.error}"
            )]

        # Format response with metadata
        result = f"""{response.content}

---
Routing: tier={response.tier_used}, model={response.model_used or 'none'}
Cost: ${response.cost_usd:.4f}, Latency: {response.latency_ms}ms
Complexity: {response.complexity_score}/100 ({response.complexity_level})"""

        if response.escalation_reason:
            result += f"\nEscalation: {response.escalation_reason}"

        return [TextContent(type="text", text=result)]

    elif name == "cortex_chat_analyze":
        analysis = await _chat_client.analyze(
            message=arguments["message"],
            context=arguments.get("context"),
        )

        if "error" in analysis:
            return [TextContent(
                type="text",
                text=f"Error: {analysis['error']}"
            )]

        complexity = analysis.get("complexity", {})
        intent = analysis.get("intent", {})
        predicted = analysis.get("predicted_tier", "unknown")

        result = f"""Query Analysis:
  Complexity: {complexity.get('score', 0)}/100 ({complexity.get('level', 'unknown')})
  Reasoning: {complexity.get('reasoning', 'N/A')}
  Factors: {complexity.get('factors', {})}

  Intent: {intent.get('type', 'unknown')} (confidence: {intent.get('confidence', 0):.2f})

  Predicted Tier: {predicted}"""

        return [TextContent(type="text", text=result)]

    elif name == "cortex_chat_status":
        status = await _chat_client.get_status()

        if "error" in status:
            return [TextContent(
                type="text",
                text=f"Error: {status['error']}"
            )]

        layers = status.get("layers", {})
        layer_status = "\n".join(
            f"  {name}: {state}" for name, state in layers.items()
        )

        result = f"""Chat Fabric Status:
  Activator: {status.get('activator', 'unknown')}
  Cache Size: {status.get('cache_size', 0)}
  Qdrant Available: {status.get('qdrant_available', False)}

Layers:
{layer_status}"""

        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown chat tool: {name}")]
