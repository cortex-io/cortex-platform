"""
Tailscale MCP Server
Network management, device control, ACL, DNS, and exit node management via MCP.

Author: ry-ops
Repository: https://github.com/ry-ops/cortex-platform
"""

import os
import json
import logging
from typing import Any
from functools import wraps

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-tailscale")


class TailscaleConfig(BaseModel):
    """Configuration for Tailscale API connection."""

    api_key: str = Field(default_factory=lambda: os.getenv("TAILSCALE_API_KEY", ""))
    tailnet: str = Field(default_factory=lambda: os.getenv("TAILSCALE_TAILNET", "-"))
    base_url: str = Field(default="https://api.tailscale.com/api/v2")
    timeout: int = Field(default=30)


class TailscaleClient:
    """HTTP client for Tailscale API."""

    def __init__(self, config: TailscaleConfig):
        self.config = config
        self.base_url = config.base_url
        self._client = httpx.Client(timeout=config.timeout)

    def _headers(self) -> dict[str, str]:
        """Get request headers with auth."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

    def _tailnet_url(self, endpoint: str) -> str:
        """Build URL with tailnet."""
        return f"{self.base_url}/tailnet/{self.config.tailnet}{endpoint}"

    async def get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make authenticated GET request."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        response = self._client.get(url, headers=self._headers(), params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, endpoint: str, data: dict | None = None) -> dict:
        """Make authenticated POST request."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        response = self._client.post(url, headers=self._headers(), json=data)
        response.raise_for_status()
        return response.json()

    async def patch(self, endpoint: str, data: dict | None = None) -> dict:
        """Make authenticated PATCH request."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        response = self._client.patch(url, headers=self._headers(), json=data)
        response.raise_for_status()
        return response.json()

    async def delete(self, endpoint: str) -> bool:
        """Make authenticated DELETE request."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        response = self._client.delete(url, headers=self._headers())
        response.raise_for_status()
        return True

    # Device operations
    async def list_devices(self) -> list:
        """List all devices in the tailnet."""
        result = await self.get(self._tailnet_url("/devices"))
        return result.get("devices", [])

    async def get_device(self, device_id: str) -> dict:
        """Get device details."""
        return await self.get(f"/device/{device_id}")

    async def authorize_device(self, device_id: str, authorized: bool = True) -> dict:
        """Authorize or de-authorize a device."""
        return await self.post(f"/device/{device_id}/authorized", {"authorized": authorized})

    async def set_device_tags(self, device_id: str, tags: list[str]) -> dict:
        """Set tags on a device."""
        return await self.post(f"/device/{device_id}/tags", {"tags": tags})

    async def set_device_routes(self, device_id: str, routes: list[str]) -> dict:
        """Set advertised routes on a device (exit node, subnet routes)."""
        return await self.post(f"/device/{device_id}/routes", {"routes": routes})

    async def delete_device(self, device_id: str) -> bool:
        """Delete a device from the tailnet."""
        return await self.delete(f"/device/{device_id}")

    async def get_device_routes(self, device_id: str) -> dict:
        """Get routes for a device."""
        return await self.get(f"/device/{device_id}/routes")

    # DNS operations
    async def get_dns_nameservers(self) -> dict:
        """Get DNS nameservers."""
        return await self.get(self._tailnet_url("/dns/nameservers"))

    async def set_dns_nameservers(self, nameservers: list[str]) -> dict:
        """Set DNS nameservers."""
        return await self.post(self._tailnet_url("/dns/nameservers"), {"dns": nameservers})

    async def get_dns_preferences(self) -> dict:
        """Get DNS preferences (MagicDNS settings)."""
        return await self.get(self._tailnet_url("/dns/preferences"))

    async def set_dns_preferences(self, magic_dns: bool) -> dict:
        """Set DNS preferences (MagicDNS)."""
        return await self.post(self._tailnet_url("/dns/preferences"), {"magicDNS": magic_dns})

    async def get_dns_searchpaths(self) -> dict:
        """Get DNS search paths."""
        return await self.get(self._tailnet_url("/dns/searchpaths"))

    async def set_dns_searchpaths(self, searchpaths: list[str]) -> dict:
        """Set DNS search paths."""
        return await self.post(self._tailnet_url("/dns/searchpaths"), {"searchPaths": searchpaths})

    async def get_split_dns(self) -> dict:
        """Get split DNS configuration."""
        return await self.get(self._tailnet_url("/dns/split-dns"))

    async def set_split_dns(self, split_dns: dict) -> dict:
        """Set split DNS configuration."""
        return await self.patch(self._tailnet_url("/dns/split-dns"), split_dns)

    # ACL operations
    async def get_acl(self) -> dict:
        """Get the current ACL policy."""
        return await self.get(self._tailnet_url("/acl"))

    async def set_acl(self, acl: dict) -> dict:
        """Set the ACL policy."""
        return await self.post(self._tailnet_url("/acl"), acl)

    async def validate_acl(self, acl: dict) -> dict:
        """Validate an ACL policy without applying it."""
        return await self.post(self._tailnet_url("/acl/validate"), acl)

    # Auth key operations
    async def list_keys(self) -> list:
        """List all auth keys."""
        result = await self.get(self._tailnet_url("/keys"))
        return result.get("keys", [])

    async def create_key(self, reusable: bool = False, ephemeral: bool = False,
                         preauthorized: bool = True, tags: list[str] | None = None,
                         expiry_seconds: int = 86400) -> dict:
        """Create a new auth key."""
        data = {
            "capabilities": {
                "devices": {
                    "create": {
                        "reusable": reusable,
                        "ephemeral": ephemeral,
                        "preauthorized": preauthorized,
                        "tags": tags or []
                    }
                }
            },
            "expirySeconds": expiry_seconds
        }
        return await self.post(self._tailnet_url("/keys"), data)

    async def get_key(self, key_id: str) -> dict:
        """Get auth key details."""
        return await self.get(self._tailnet_url(f"/keys/{key_id}"))

    async def delete_key(self, key_id: str) -> bool:
        """Delete an auth key."""
        return await self.delete(self._tailnet_url(f"/keys/{key_id}"))


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("mcp-tailscale")
    config = TailscaleConfig()
    client = TailscaleClient(config)

    # Define tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            # Device tools
            Tool(
                name="tailscale_list_devices",
                description="List all devices in the Tailscale network (tailnet). Shows device name, IP, status, OS, and tags.",
                inputSchema={"type": "object", "properties": {}, "required": []}
            ),
            Tool(
                name="tailscale_get_device",
                description="Get detailed information about a specific device.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID or hostname"}
                    },
                    "required": ["device_id"]
                }
            ),
            Tool(
                name="tailscale_authorize_device",
                description="Authorize or de-authorize a device in the tailnet.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID"},
                        "authorized": {"type": "boolean", "description": "Whether to authorize (true) or de-authorize (false)"}
                    },
                    "required": ["device_id", "authorized"]
                }
            ),
            Tool(
                name="tailscale_set_device_tags",
                description="Set ACL tags on a device (e.g., tag:server, tag:admin).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "List of tags (e.g., ['tag:server', 'tag:admin'])"}
                    },
                    "required": ["device_id", "tags"]
                }
            ),
            Tool(
                name="tailscale_set_device_routes",
                description="Set advertised routes on a device. Use for exit nodes (0.0.0.0/0, ::/0) or subnet routing.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID"},
                        "routes": {"type": "array", "items": {"type": "string"}, "description": "List of CIDR routes (e.g., ['0.0.0.0/0', '192.168.1.0/24'])"}
                    },
                    "required": ["device_id", "routes"]
                }
            ),
            Tool(
                name="tailscale_get_device_routes",
                description="Get advertised and enabled routes for a device.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID"}
                    },
                    "required": ["device_id"]
                }
            ),
            Tool(
                name="tailscale_delete_device",
                description="Remove a device from the tailnet.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID"}
                    },
                    "required": ["device_id"]
                }
            ),
            # DNS tools
            Tool(
                name="tailscale_get_dns",
                description="Get all DNS settings including nameservers, MagicDNS, search paths, and split DNS.",
                inputSchema={"type": "object", "properties": {}, "required": []}
            ),
            Tool(
                name="tailscale_set_dns_nameservers",
                description="Set custom DNS nameservers for the tailnet.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "nameservers": {"type": "array", "items": {"type": "string"}, "description": "List of DNS server IPs (e.g., ['1.1.1.1', '8.8.8.8'])"}
                    },
                    "required": ["nameservers"]
                }
            ),
            Tool(
                name="tailscale_set_magic_dns",
                description="Enable or disable MagicDNS for automatic device hostname resolution.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "description": "Whether to enable MagicDNS"}
                    },
                    "required": ["enabled"]
                }
            ),
            Tool(
                name="tailscale_set_search_paths",
                description="Set DNS search paths for the tailnet.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search_paths": {"type": "array", "items": {"type": "string"}, "description": "List of search domains (e.g., ['home.local', 'corp.example.com'])"}
                    },
                    "required": ["search_paths"]
                }
            ),
            Tool(
                name="tailscale_set_split_dns",
                description="Configure split DNS - route specific domains to specific nameservers.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "split_dns": {"type": "object", "description": "Domain to nameserver mapping (e.g., {'corp.example.com': ['10.0.0.53']})"}
                    },
                    "required": ["split_dns"]
                }
            ),
            # ACL tools
            Tool(
                name="tailscale_get_acl",
                description="Get the current ACL (Access Control List) policy for the tailnet.",
                inputSchema={"type": "object", "properties": {}, "required": []}
            ),
            Tool(
                name="tailscale_validate_acl",
                description="Validate an ACL policy without applying it. Check for syntax errors and policy conflicts.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "acl": {"type": "object", "description": "ACL policy object to validate"}
                    },
                    "required": ["acl"]
                }
            ),
            Tool(
                name="tailscale_set_acl",
                description="Set/update the ACL policy for the tailnet. WARNING: This changes network access rules.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "acl": {"type": "object", "description": "Complete ACL policy object"}
                    },
                    "required": ["acl"]
                }
            ),
            # Auth key tools
            Tool(
                name="tailscale_list_keys",
                description="List all auth keys in the tailnet.",
                inputSchema={"type": "object", "properties": {}, "required": []}
            ),
            Tool(
                name="tailscale_create_key",
                description="Create a new auth key for adding devices to the tailnet.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reusable": {"type": "boolean", "description": "Whether the key can be used multiple times", "default": False},
                        "ephemeral": {"type": "boolean", "description": "Whether devices using this key are ephemeral", "default": False},
                        "preauthorized": {"type": "boolean", "description": "Whether devices are pre-authorized", "default": True},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to apply to devices using this key"},
                        "expiry_seconds": {"type": "integer", "description": "Key expiry time in seconds", "default": 86400}
                    },
                    "required": []
                }
            ),
            Tool(
                name="tailscale_delete_key",
                description="Delete an auth key.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key_id": {"type": "string", "description": "Auth key ID to delete"}
                    },
                    "required": ["key_id"]
                }
            ),
            # Health/status tool
            Tool(
                name="tailscale_health",
                description="Get Tailscale network health status - device counts, online/offline devices, and connectivity overview.",
                inputSchema={"type": "object", "properties": {}, "required": []}
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = await _handle_tool(client, name, arguments)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
            )]
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
        except Exception as e:
            logger.exception(f"Error in tool {name}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    return server


async def _handle_tool(client: TailscaleClient, name: str, args: dict) -> Any:
    """Route tool calls to appropriate handlers."""

    # Device operations
    if name == "tailscale_list_devices":
        devices = await client.list_devices()
        return {
            "total": len(devices),
            "devices": [{
                "id": d.get("id"),
                "name": d.get("name"),
                "hostname": d.get("hostname"),
                "addresses": d.get("addresses", []),
                "os": d.get("os"),
                "user": d.get("user"),
                "authorized": d.get("authorized"),
                "isExternal": d.get("isExternal"),
                "lastSeen": d.get("lastSeen"),
                "tags": d.get("tags", []),
                "keyExpiryDisabled": d.get("keyExpiryDisabled"),
                "blocksIncomingConnections": d.get("blocksIncomingConnections"),
                "clientConnectivity": d.get("clientConnectivity", {}).get("endpoints", [])[:3]  # First 3 endpoints
            } for d in devices]
        }

    elif name == "tailscale_get_device":
        return await client.get_device(args["device_id"])

    elif name == "tailscale_authorize_device":
        return await client.authorize_device(args["device_id"], args["authorized"])

    elif name == "tailscale_set_device_tags":
        return await client.set_device_tags(args["device_id"], args["tags"])

    elif name == "tailscale_set_device_routes":
        return await client.set_device_routes(args["device_id"], args["routes"])

    elif name == "tailscale_get_device_routes":
        return await client.get_device_routes(args["device_id"])

    elif name == "tailscale_delete_device":
        await client.delete_device(args["device_id"])
        return {"success": True, "message": f"Device {args['device_id']} deleted"}

    # DNS operations
    elif name == "tailscale_get_dns":
        nameservers = await client.get_dns_nameservers()
        preferences = await client.get_dns_preferences()
        searchpaths = await client.get_dns_searchpaths()
        split_dns = await client.get_split_dns()
        return {
            "nameservers": nameservers,
            "preferences": preferences,
            "searchPaths": searchpaths,
            "splitDNS": split_dns
        }

    elif name == "tailscale_set_dns_nameservers":
        return await client.set_dns_nameservers(args["nameservers"])

    elif name == "tailscale_set_magic_dns":
        return await client.set_dns_preferences(args["enabled"])

    elif name == "tailscale_set_search_paths":
        return await client.set_dns_searchpaths(args["search_paths"])

    elif name == "tailscale_set_split_dns":
        return await client.set_split_dns(args["split_dns"])

    # ACL operations
    elif name == "tailscale_get_acl":
        return await client.get_acl()

    elif name == "tailscale_validate_acl":
        return await client.validate_acl(args["acl"])

    elif name == "tailscale_set_acl":
        return await client.set_acl(args["acl"])

    # Auth key operations
    elif name == "tailscale_list_keys":
        return await client.list_keys()

    elif name == "tailscale_create_key":
        return await client.create_key(
            reusable=args.get("reusable", False),
            ephemeral=args.get("ephemeral", False),
            preauthorized=args.get("preauthorized", True),
            tags=args.get("tags"),
            expiry_seconds=args.get("expiry_seconds", 86400)
        )

    elif name == "tailscale_delete_key":
        await client.delete_key(args["key_id"])
        return {"success": True, "message": f"Key {args['key_id']} deleted"}

    # Health/status
    elif name == "tailscale_health":
        devices = await client.list_devices()
        now_online = [d for d in devices if d.get("lastSeen") and not d.get("isExternal")]
        authorized = [d for d in devices if d.get("authorized")]
        exit_nodes = [d for d in devices if any("0.0.0.0/0" in r for r in d.get("enabledRoutes", []))]

        return {
            "healthy": True,
            "summary": {
                "total_devices": len(devices),
                "authorized_devices": len(authorized),
                "external_devices": len([d for d in devices if d.get("isExternal")]),
                "exit_nodes": len(exit_nodes)
            },
            "devices_by_os": _count_by_key(devices, "os"),
            "exit_nodes": [{
                "name": d.get("name"),
                "addresses": d.get("addresses", []),
                "lastSeen": d.get("lastSeen")
            } for d in exit_nodes]
        }

    else:
        raise ValueError(f"Unknown tool: {name}")


def _count_by_key(items: list, key: str) -> dict:
    """Count items by a key value."""
    counts = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


async def main():
    """Main entry point."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
