#!/usr/bin/env python3
"""
CheckMK MCP Server
Exposes CheckMK REST API through Model Context Protocol
"""

import os
import json
import logging
from typing import Any, Optional
from functools import wraps

import httpx
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("checkmk-mcp")


class CheckMKConfig(BaseModel):
    """Configuration from environment variables"""
    host: str = Field(default="checkmk.ry-ops.dev")
    site: str = Field(default="cmk")
    username: str = Field(default="automation")
    password: str
    verify_ssl: bool = Field(default=False)
    timeout: int = Field(default=30)

    @classmethod
    def from_env(cls) -> "CheckMKConfig":
        """Load configuration from environment variables"""
        return cls(
            host=os.getenv("CHECKMK_HOST", "checkmk.ry-ops.dev"),
            site=os.getenv("CHECKMK_SITE", "cmk"),
            username=os.getenv("CHECKMK_USERNAME", "automation"),
            password=os.getenv("CHECKMK_PASSWORD", ""),
            verify_ssl=os.getenv("CHECKMK_VERIFY_SSL", "false").lower() == "true",
            timeout=int(os.getenv("CHECKMK_TIMEOUT", "30"))
        )


class CheckMKClient:
    """HTTP client for CheckMK REST API"""

    def __init__(self, config: CheckMKConfig):
        self.config = config
        self.base_url = f"http://{config.host}/{config.site}/check_mk/api/1.0"
        self.client = httpx.Client(
            verify=config.verify_ssl,
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.username} {config.password}",
                "Accept": "application/json"
            }
        )
        logger.info(f"CheckMK client initialized for {self.base_url}")

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Execute GET request"""
        url = f"{self.base_url}{endpoint}"
        logger.info(f"GET {url}")
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Execute POST request"""
        url = f"{self.base_url}{endpoint}"
        logger.info(f"POST {url}")
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def close(self):
        """Close HTTP client"""
        self.client.close()


# Initialize server and client
app = Server("checkmk-mcp")
config = CheckMKConfig.from_env()
client = CheckMKClient(config)


def handle_errors(func):
    """Decorator to handle errors and return TextContent"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPError as e:
            error_msg = f"CheckMK API error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    return wrapper


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available CheckMK MCP tools"""
    return [
        # System/Health Tools
        Tool(
            name="checkmk_get_version",
            description="Get CheckMK version and site information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # Host Tools
        Tool(
            name="checkmk_list_hosts",
            description="List all monitored hosts with status",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "boolean",
                        "description": "Return summary only (default: true)",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="checkmk_get_host",
            description="Get details for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {
                        "type": "string",
                        "description": "Hostname to query"
                    }
                },
                "required": ["host_name"]
            }
        ),

        # Service Tools
        Tool(
            name="checkmk_get_host_services",
            description="Get all services for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {
                        "type": "string",
                        "description": "Hostname to query"
                    },
                    "summary": {
                        "type": "boolean",
                        "description": "Return summary only (default: true)",
                        "default": True
                    }
                },
                "required": ["host_name"]
            }
        ),

        # Problem/Alert Tools
        Tool(
            name="checkmk_get_all_problems",
            description="Get all current problems (non-OK services and down hosts)",
            inputSchema={
                "type": "object",
                "properties": {
                    "unhandled_only": {
                        "type": "boolean",
                        "description": "Show only unhandled problems (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="checkmk_get_host_problems",
            description="Get problems for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {
                        "type": "string",
                        "description": "Hostname to query"
                    }
                },
                "required": ["host_name"]
            }
        ),
    ]


@app.call_tool()
@handle_errors
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution"""

    if name == "checkmk_get_version":
        result = client.get("/version")
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    elif name == "checkmk_list_hosts":
        summary = arguments.get("summary", True)
        # Get all hosts with status
        result = client.get("/domain-types/host/collections/all")

        if summary:
            hosts = result.get("value", [])
            total = len(hosts)
            up = sum(1 for h in hosts if h.get("extensions", {}).get("state") == 0)
            down = sum(1 for h in hosts if h.get("extensions", {}).get("state") == 1)
            unreachable = sum(1 for h in hosts if h.get("extensions", {}).get("state") == 2)

            summary_text = f"""CheckMK Host Summary:
Total Hosts: {total}
- UP: {up}
- DOWN: {down}
- UNREACHABLE: {unreachable}

Hosts:
"""
            for host in hosts:
                name_val = host.get("id", "unknown")
                state = host.get("extensions", {}).get("state", -1)
                state_str = ["UP", "DOWN", "UNREACHABLE"][state] if state in [0, 1, 2] else "UNKNOWN"
                output = host.get("extensions", {}).get("plugin_output", "")
                summary_text += f"  • {name_val}: {state_str}"
                if state != 0:
                    summary_text += f" - {output}"
                summary_text += "\n"

            return [TextContent(type="text", text=summary_text)]
        else:
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

    elif name == "checkmk_get_host":
        host_name = arguments.get("host_name")
        result = client.get(f"/objects/host/{host_name}")
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    elif name == "checkmk_get_host_services":
        host_name = arguments.get("host_name")
        summary = arguments.get("summary", True)
        result = client.get(f"/objects/host/{host_name}/collections/services")

        if summary:
            services = result.get("value", [])
            total = len(services)
            ok = sum(1 for s in services if s.get("extensions", {}).get("state") == 0)
            warn = sum(1 for s in services if s.get("extensions", {}).get("state") == 1)
            crit = sum(1 for s in services if s.get("extensions", {}).get("state") == 2)
            unknown = sum(1 for s in services if s.get("extensions", {}).get("state") == 3)

            summary_text = f"""Services on {host_name}:
Total: {total}
- OK: {ok}
- WARNING: {warn}
- CRITICAL: {crit}
- UNKNOWN: {unknown}

Critical/Warning Services:
"""
            for service in services:
                state = service.get("extensions", {}).get("state", -1)
                if state in [1, 2]:  # WARN or CRIT
                    svc_name = service.get("id", "unknown")
                    state_str = ["OK", "WARNING", "CRITICAL", "UNKNOWN"][state] if state in [0, 1, 2, 3] else "UNKNOWN"
                    output = service.get("extensions", {}).get("plugin_output", "")
                    summary_text += f"  • {svc_name}: {state_str} - {output}\n"

            return [TextContent(type="text", text=summary_text)]
        else:
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

    elif name == "checkmk_get_all_problems":
        unhandled_only = arguments.get("unhandled_only", False)

        # Get all hosts
        hosts_result = client.get("/domain-types/host/collections/all")
        hosts = hosts_result.get("value", [])

        problems_text = "CheckMK Current Problems:\n\n"

        # Check for down hosts
        down_hosts = [h for h in hosts if h.get("extensions", {}).get("state") != 0]
        if down_hosts:
            problems_text += f"DOWN/UNREACHABLE HOSTS ({len(down_hosts)}):\n"
            for host in down_hosts:
                name = host.get("id", "unknown")
                state = host.get("extensions", {}).get("state", -1)
                state_str = ["UP", "DOWN", "UNREACHABLE"][state] if state in [0, 1, 2] else "UNKNOWN"
                output = host.get("extensions", {}).get("plugin_output", "")
                problems_text += f"  • {name}: {state_str} - {output}\n"

        # Check for problem services (iterate through hosts)
        problem_services = []
        for host in hosts:
            host_name = host.get("id")
            try:
                services_result = client.get(f"/objects/host/{host_name}/collections/services")
                services = services_result.get("value", [])
                for service in services:
                    state = service.get("extensions", {}).get("state", 0)
                    if state != 0:  # Not OK
                        problem_services.append({
                            "host": host_name,
                            "service": service.get("id", "unknown"),
                            "state": state,
                            "output": service.get("extensions", {}).get("plugin_output", "")
                        })
            except Exception as e:
                logger.error(f"Error getting services for {host_name}: {e}")

        if problem_services:
            problems_text += f"\nPROBLEM SERVICES ({len(problem_services)}):\n"
            for prob in problem_services[:20]:  # Limit to 20 to avoid token limits
                state_str = ["OK", "WARNING", "CRITICAL", "UNKNOWN"][prob["state"]] if prob["state"] in [0, 1, 2, 3] else "UNKNOWN"
                problems_text += f"  • {prob['host']}/{prob['service']}: {state_str} - {prob['output']}\n"

            if len(problem_services) > 20:
                problems_text += f"\n... and {len(problem_services) - 20} more problem services\n"

        if not down_hosts and not problem_services:
            problems_text += "✅ No problems found! All systems operational.\n"

        return [TextContent(type="text", text=problems_text)]

    elif name == "checkmk_get_host_problems":
        host_name = arguments.get("host_name")

        # Get host status
        host_result = client.get(f"/objects/host/{host_name}")
        host_state = host_result.get("extensions", {}).get("state", 0)

        problems_text = f"Problems on {host_name}:\n\n"

        if host_state != 0:
            state_str = ["UP", "DOWN", "UNREACHABLE"][host_state] if host_state in [0, 1, 2] else "UNKNOWN"
            output = host_result.get("extensions", {}).get("plugin_output", "")
            problems_text += f"HOST STATUS: {state_str} - {output}\n\n"

        # Get service problems
        services_result = client.get(f"/objects/host/{host_name}/collections/services")
        services = services_result.get("value", [])
        problem_services = [s for s in services if s.get("extensions", {}).get("state") != 0]

        if problem_services:
            problems_text += f"PROBLEM SERVICES ({len(problem_services)}):\n"
            for service in problem_services:
                svc_name = service.get("id", "unknown")
                state = service.get("extensions", {}).get("state", -1)
                state_str = ["OK", "WARNING", "CRITICAL", "UNKNOWN"][state] if state in [0, 1, 2, 3] else "UNKNOWN"
                output = service.get("extensions", {}).get("plugin_output", "")
                problems_text += f"  • {svc_name}: {state_str} - {output}\n"

        if host_state == 0 and not problem_services:
            problems_text += "✅ No problems found on this host.\n"

        return [TextContent(type="text", text=problems_text)]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run MCP server"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
