"""
Cortex Unified MCP Server

The brain of Cortex for Claude Code integration. Exposes all Cortex capabilities
as MCP tools, routing through Chat Fabric for intelligence and cost optimization.

Usage:
    cortex-unified          # HTTP server mode (default for K8s)
    cortex-unified --stdio  # stdio mode (for local Claude Code)

Or via Python:
    python -m cortex_unified.server
"""

import asyncio
import json
import os
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        int(os.getenv("LOG_LEVEL", "20"))  # INFO=20, DEBUG=10
    ),
)

logger = structlog.get_logger()

# Import clients
from .clients.chat_activator import ChatActivatorClient
from .clients.qdrant import QdrantClient
from .clients.prometheus import PrometheusClient
from .clients.redis_client import RedisClient
from .clients.mcp_passthrough import MCPPassthroughClient

# Import tools
from .tools.chat import (
    CHAT_TOOLS,
    handle_chat_tool,
    set_chat_client,
)
from .tools.context import (
    CONTEXT_TOOLS,
    handle_context_tool,
    set_context_clients,
)
from .tools.memory import (
    MEMORY_TOOLS,
    handle_memory_tool,
    set_memory_client,
)
from .tools.agents import (
    AGENT_TOOLS,
    handle_agent_tool,
    set_agents_client,
)


# =============================================================================
# Server Configuration
# =============================================================================

class CortexUnifiedConfig:
    """Configuration loaded from environment variables."""

    def __init__(self):
        # Chat Activator (routes through fabric)
        self.chat_activator_url = os.getenv(
            "CHAT_ACTIVATOR_URL",
            "http://chat-activator.cortex-chat:8080"
        )

        # Qdrant (conversation memory)
        self.qdrant_url = os.getenv(
            "QDRANT_URL",
            "http://chat-qdrant.cortex-chat:6333"
        )

        # Prometheus (cluster metrics)
        self.prometheus_url = os.getenv(
            "PROMETHEUS_URL",
            "http://prometheus-server.cortex-system:80"
        )

        # Redis (agent framework)
        self.redis_url = os.getenv(
            "REDIS_URL",
            "redis://redis.cortex-system:6379"
        )

        # Server info
        self.server_name = "cortex-unified"
        self.server_version = "0.1.0"


# =============================================================================
# MCP Server
# =============================================================================

# Global server instance
server = Server("cortex-unified")

# Global clients (initialized in main)
_config: CortexUnifiedConfig | None = None
_chat_client: ChatActivatorClient | None = None
_qdrant_client: QdrantClient | None = None
_prometheus_client: PrometheusClient | None = None
_redis_client: RedisClient | None = None
_mcp_client: MCPPassthroughClient | None = None


# Combine all tools
ALL_TOOLS = CHAT_TOOLS + CONTEXT_TOOLS + MEMORY_TOOLS + AGENT_TOOLS


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all available tools."""
    return ALL_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to appropriate handlers."""
    logger.debug("tool_call", tool=name)

    # Chat tools (cortex_chat_*)
    if name.startswith("cortex_chat_"):
        return await handle_chat_tool(name, arguments)

    # Context tools (cortex_context_*)
    if name.startswith("cortex_context_"):
        return await handle_context_tool(name, arguments)

    # Memory tools (cortex_memory_*)
    if name.startswith("cortex_memory_"):
        return await handle_memory_tool(name, arguments)

    # Agent tools (cortex_agents_*)
    if name.startswith("cortex_agents_"):
        return await handle_agent_tool(name, arguments)

    # Passthrough to other MCP servers (k8s_*, proxmox_*, sandfly_*, etc.)
    if _mcp_client:
        result = await _mcp_client.route_tool_call(name, arguments)
        if result.success:
            return [TextContent(type="text", text=str(result.content))]
        else:
            return [TextContent(type="text", text=f"Error: {result.error}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# =============================================================================
# Lifecycle
# =============================================================================

async def initialize_clients():
    """Initialize all client connections."""
    global _config, _chat_client, _qdrant_client, _prometheus_client
    global _redis_client, _mcp_client

    logger.info("initializing_clients")

    _config = CortexUnifiedConfig()

    # Initialize clients
    _chat_client = ChatActivatorClient(base_url=_config.chat_activator_url)
    _qdrant_client = QdrantClient(base_url=_config.qdrant_url)
    _prometheus_client = PrometheusClient(base_url=_config.prometheus_url)
    _redis_client = RedisClient(url=_config.redis_url)
    _mcp_client = MCPPassthroughClient()

    # Wire up tool handlers
    set_chat_client(_chat_client)
    set_memory_client(_qdrant_client)
    set_context_clients(_prometheus_client, _mcp_client)
    set_agents_client(_redis_client)

    # Health checks
    chat_healthy = await _chat_client.health_check()
    qdrant_healthy = await _qdrant_client.health_check()
    prometheus_healthy = await _prometheus_client.health_check()
    redis_healthy = await _redis_client.health_check()
    mcp_health = await _mcp_client.health_check_all()

    logger.info(
        "clients_initialized",
        chat_activator=chat_healthy,
        qdrant=qdrant_healthy,
        prometheus=prometheus_healthy,
        redis=redis_healthy,
        mcp_servers=mcp_health,
    )


async def shutdown_clients():
    """Cleanup all client connections."""
    logger.info("shutting_down_clients")

    if _chat_client:
        await _chat_client.close()
    if _qdrant_client:
        await _qdrant_client.close()
    if _prometheus_client:
        await _prometheus_client.close()
    if _redis_client:
        await _redis_client.close()
    if _mcp_client:
        await _mcp_client.close()


# =============================================================================
# HTTP Server for K8s Deployment
# =============================================================================

class MCPHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for JSON-RPC MCP protocol."""

    def log_message(self, format, *args):
        """Override to use structured logging."""
        pass  # Suppress default logging

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == "/ready":
            # Check if clients are initialized
            if _chat_client:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Ready")
            else:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Ready")
        elif self.path == "/tools":
            # Return tool list for debugging
            tools = [{"name": t.name, "description": t.description} for t in ALL_TOOLS]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(tools).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests (MCP JSON-RPC)."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Handle JSON-RPC
        if "jsonrpc" in request:
            self._handle_jsonrpc(request)
        else:
            self.send_error(400, "Expected JSON-RPC request")

    def _handle_jsonrpc(self, request):
        """Handle JSON-RPC 2.0 requests."""
        req_id = request.get("id", 1)
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cortex-unified", "version": "0.1.0"},
                }
            elif method == "tools/list":
                tools_list = []
                for tool in ALL_TOOLS:
                    tools_list.append({
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    })
                result = {"tools": tools_list}
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                # Run async tool call in event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    tool_result = loop.run_until_complete(call_tool(tool_name, arguments))
                    content = [{"type": c.type, "text": c.text} for c in tool_result]
                    result = {"content": content}
                finally:
                    loop.close()
            else:
                raise ValueError(f"Unknown method: {method}")

            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            logger.error("jsonrpc_error", method=method, error=str(e))
            error_response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            }
            self.send_response(200)  # JSON-RPC errors use 200
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode())


def run_http_server(port: int = 3000):
    """Run HTTP server for K8s deployment."""
    logger.info("starting_http_server", port=port)

    # Initialize clients synchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(initialize_clients())

    # Start HTTP server
    httpd = HTTPServer(("0.0.0.0", port), MCPHTTPHandler)
    logger.info("mcp_http_server_ready", port=port)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(shutdown_clients())
        loop.close()


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_stdio_server():
    """Run the MCP server over stdio (for local Claude Code)."""
    logger.info(
        "starting_cortex_unified_mcp",
        version="0.1.0",
        mode="stdio",
    )

    # Initialize clients
    await initialize_clients()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("received_shutdown_signal")
        loop.create_task(shutdown_clients())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        # Run MCP server over stdio
        async with stdio_server() as (read_stream, write_stream):
            logger.info("mcp_server_ready")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await shutdown_clients()


def main():
    """Entry point."""
    # Check for --stdio flag
    if "--stdio" in sys.argv:
        try:
            asyncio.run(run_stdio_server())
        except KeyboardInterrupt:
            logger.info("keyboard_interrupt")
            sys.exit(0)
    else:
        # Default: HTTP server mode for K8s
        port = int(os.getenv("MCP_PORT", "3000"))
        run_http_server(port)


if __name__ == "__main__":
    main()
