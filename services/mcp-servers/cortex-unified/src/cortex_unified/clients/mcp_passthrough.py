"""
MCP Passthrough Client

Routes tool calls to other MCP servers (kubernetes, proxmox, sandfly, unifi, n8n).
"""

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    url: str
    health_path: str = "/health"
    timeout: float = 30.0


# Default MCP server configurations
DEFAULT_MCP_SERVERS = {
    "kubernetes": MCPServerConfig(
        name="kubernetes",
        url=os.getenv("K8S_MCP_URL", "http://kubernetes-mcp-server.cortex-system:3001"),
        timeout=30.0,
    ),
    "proxmox": MCPServerConfig(
        name="proxmox",
        url=os.getenv("PROXMOX_MCP_URL", "http://proxmox-mcp-server.cortex-system:3000"),
        timeout=30.0,
    ),
    "sandfly": MCPServerConfig(
        name="sandfly",
        url=os.getenv("SANDFLY_MCP_URL", "http://sandfly-mcp-server.cortex-system:8080"),
        timeout=30.0,
    ),
    "unifi": MCPServerConfig(
        name="unifi",
        url=os.getenv("UNIFI_MCP_URL", "http://unifi-mcp-server.cortex-system:3000"),
        timeout=30.0,
    ),
    "n8n": MCPServerConfig(
        name="n8n",
        url=os.getenv("N8N_MCP_URL", "http://n8n-mcp-server.cortex-system:3002"),
        timeout=30.0,
    ),
    "cortex": MCPServerConfig(
        name="cortex",
        url=os.getenv("CORTEX_MCP_URL", "http://cortex-mcp-server.cortex-system:3000"),
        timeout=30.0,
    ),
}


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""
    success: bool
    content: Any
    error: Optional[str] = None


class MCPPassthroughClient:
    """HTTP client for passthrough to other MCP servers."""

    def __init__(
        self,
        servers: Optional[dict[str, MCPServerConfig]] = None,
    ):
        self.servers = servers or DEFAULT_MCP_SERVERS
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get configuration for a server."""
        return self.servers.get(server_name)

    async def health_check(self, server_name: str) -> bool:
        """Check if a specific MCP server is healthy."""
        config = self.get_server_config(server_name)
        if not config:
            return False

        client = await self._get_client()

        try:
            response = await client.get(
                f"{config.url}{config.health_path}",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all MCP servers."""
        results = {}
        for server_name in self.servers:
            results[server_name] = await self.health_check(server_name)
        return results

    async def list_tools(self, server_name: str) -> list[dict[str, Any]]:
        """
        List available tools from an MCP server.

        Args:
            server_name: Name of the MCP server

        Returns:
            List of tool definitions
        """
        config = self.get_server_config(server_name)
        if not config:
            logger.warning("unknown_mcp_server", server=server_name)
            return []

        client = await self._get_client()

        try:
            # Try standard MCP endpoint
            response = await client.get(
                f"{config.url}/tools",
                timeout=config.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("tools", data) if isinstance(data, dict) else data

            # Try JSON-RPC style
            response = await client.post(
                f"{config.url}/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                },
                timeout=config.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("result", {}).get("tools", [])

        except Exception as e:
            logger.error(
                "mcp_list_tools_error",
                server=server_name,
                error=str(e),
            )

        return []

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """
        Call a tool on an MCP server.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            MCPToolResult
        """
        config = self.get_server_config(server_name)
        if not config:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Unknown MCP server: {server_name}",
            )

        client = await self._get_client()

        logger.info(
            "mcp_tool_call",
            server=server_name,
            tool=tool_name,
        )

        try:
            # Try execute endpoint first (common pattern)
            response = await client.post(
                f"{config.url}/execute",
                json={
                    "tool": tool_name,
                    "arguments": arguments,
                },
                timeout=config.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return MCPToolResult(
                    success=data.get("success", True),
                    content=data.get("result", data),
                    error=data.get("error"),
                )

            # Try JSON-RPC style
            response = await client.post(
                f"{config.url}/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
                timeout=config.timeout,
            )

            if response.status_code == 200:
                data = response.json()

                if "error" in data:
                    return MCPToolResult(
                        success=False,
                        content=None,
                        error=data["error"].get("message", str(data["error"])),
                    )

                result = data.get("result", {})
                content = result.get("content", [])

                # Extract text content
                if content and isinstance(content, list):
                    text_parts = [
                        c.get("text", str(c))
                        for c in content
                        if isinstance(c, dict)
                    ]
                    return MCPToolResult(
                        success=True,
                        content="\n".join(text_parts) if text_parts else content,
                    )

                return MCPToolResult(success=True, content=result)

            return MCPToolResult(
                success=False,
                content=None,
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except Exception as e:
            logger.error(
                "mcp_tool_call_error",
                server=server_name,
                tool=tool_name,
                error=str(e),
            )
            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
            )

    async def route_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """
        Route a tool call based on tool name prefix.

        Tool names should be in format: server_toolname
        e.g., k8s_list_pods, sandfly_get_hosts

        Args:
            tool_name: Full tool name with prefix
            arguments: Tool arguments

        Returns:
            MCPToolResult
        """
        # Map prefixes to server names
        prefix_map = {
            "k8s": "kubernetes",
            "kubernetes": "kubernetes",
            "proxmox": "proxmox",
            "pve": "proxmox",
            "sandfly": "sandfly",
            "unifi": "unifi",
            "n8n": "n8n",
            "cortex": "cortex",
        }

        # Try to extract prefix
        parts = tool_name.split("_", 1)
        if len(parts) < 2:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Invalid tool name format: {tool_name}. Expected prefix_toolname.",
            )

        prefix = parts[0].lower()
        server_name = prefix_map.get(prefix)

        if not server_name:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Unknown tool prefix: {prefix}. Valid prefixes: {list(prefix_map.keys())}",
            )

        return await self.call_tool(server_name, tool_name, arguments)
