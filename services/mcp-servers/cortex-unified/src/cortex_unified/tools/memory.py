"""
cortex.memory.* tools

Conversation history and pattern storage via Qdrant.
"""

from typing import Any

from mcp.types import Tool, TextContent

from ..clients.qdrant import QdrantClient

# Global client instance (initialized in server)
_qdrant_client: QdrantClient | None = None


def set_memory_client(client: QdrantClient):
    """Set the global Qdrant client instance."""
    global _qdrant_client
    _qdrant_client = client


MEMORY_TOOLS = [
    Tool(
        name="cortex_memory_recall",
        description="""Recall conversation history for a session.

Returns past messages in chronological order.
Use this to restore context after reconnecting or to review what was discussed.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to recall"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum messages to return (default: 50)",
                    "default": 50
                }
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="cortex_memory_store",
        description="""Store a message in conversation memory.

Saves a message to Qdrant for future recall.
Messages are associated with a session_id for organization.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to store under"
                },
                "role": {
                    "type": "string",
                    "enum": ["user", "assistant"],
                    "description": "Who sent the message"
                },
                "content": {
                    "type": "string",
                    "description": "The message content"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata (tier_used, cost, etc.)"
                }
            },
            "required": ["session_id", "role", "content"]
        }
    ),
    Tool(
        name="cortex_memory_list_sessions",
        description="""List all conversation sessions.

Returns a list of session IDs that have stored conversations.
Useful for finding past sessions to resume.""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum sessions to return (default: 100)",
                    "default": 100
                }
            },
            "required": []
        }
    ),
    Tool(
        name="cortex_memory_delete_session",
        description="""Delete a conversation session.

Removes all messages for the specified session.
Use with caution - this is irreversible.""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to delete"
                }
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="cortex_memory_search",
        description="""Search for similar past conversations.

Uses vector similarity to find past messages related to a query.
Useful for finding how similar questions were answered before.""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 5)",
                    "default": 5
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum similarity score 0-1 (default: 0.8)",
                    "default": 0.8
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="cortex_memory_health",
        description="""Check if memory system (Qdrant) is healthy.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


async def handle_memory_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle memory tool calls."""
    if _qdrant_client is None:
        return [TextContent(
            type="text",
            text="Error: Memory client not initialized"
        )]

    if name == "cortex_memory_recall":
        session_id = arguments["session_id"]
        limit = arguments.get("limit", 50)

        entries = await _qdrant_client.recall_conversation(session_id, limit)

        if not entries:
            return [TextContent(
                type="text",
                text=f"No conversation history found for session: {session_id}"
            )]

        lines = [f"Conversation History ({len(entries)} messages):"]
        for entry in entries:
            timestamp = entry.timestamp.strftime("%H:%M:%S")
            role = entry.role.upper()
            content_preview = entry.content[:200]
            if len(entry.content) > 200:
                content_preview += "..."
            lines.append(f"[{timestamp}] {role}: {content_preview}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "cortex_memory_store":
        session_id = arguments["session_id"]
        role = arguments["role"]
        content = arguments["content"]
        metadata = arguments.get("metadata", {})

        try:
            point_id = await _qdrant_client.store_conversation(
                session_id=session_id,
                role=role,
                content=content,
                metadata=metadata,
            )
            return [TextContent(
                type="text",
                text=f"Stored message in session {session_id} (id: {point_id})"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error storing message: {str(e)}"
            )]

    elif name == "cortex_memory_list_sessions":
        limit = arguments.get("limit", 100)
        sessions = await _qdrant_client.list_sessions(limit)

        if not sessions:
            return [TextContent(type="text", text="No sessions found")]

        lines = [f"Sessions ({len(sessions)}):"]
        for sid in sessions:
            lines.append(f"  - {sid}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "cortex_memory_delete_session":
        session_id = arguments["session_id"]
        success = await _qdrant_client.delete_session(session_id)

        if success:
            return [TextContent(
                type="text",
                text=f"Deleted session: {session_id}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"Failed to delete session: {session_id}"
            )]

    elif name == "cortex_memory_search":
        query = arguments["query"]
        limit = arguments.get("limit", 5)
        threshold = arguments.get("threshold", 0.8)

        # Note: In production, you'd compute embeddings for the query
        # For now, we return a placeholder response
        return [TextContent(
            type="text",
            text=f"Search for '{query}' requires embedding computation. "
                 f"This feature will be fully implemented with the embedding service.\n"
                 f"Parameters: limit={limit}, threshold={threshold}"
        )]

    elif name == "cortex_memory_health":
        healthy = await _qdrant_client.health_check()
        status = "healthy" if healthy else "unhealthy"
        return [TextContent(
            type="text",
            text=f"Memory system (Qdrant): {status}"
        )]

    return [TextContent(type="text", text=f"Unknown memory tool: {name}")]
