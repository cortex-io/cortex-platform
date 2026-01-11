"""
Sandfly Security MCP Server
Agentless Linux intrusion detection and incident response via MCP.

Author: ry-ops
Repository: https://github.com/ry-ops/mcp-sandfly
"""

import os
import logging
from datetime import datetime
from typing import Any
from functools import wraps

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-sandfly")


class SandflyConfig(BaseModel):
    """Configuration for Sandfly API connection."""
    
    host: str = Field(default_factory=lambda: os.getenv("SANDFLY_HOST", ""))
    username: str = Field(default_factory=lambda: os.getenv("SANDFLY_USERNAME", ""))
    password: str = Field(default_factory=lambda: os.getenv("SANDFLY_PASSWORD", ""))
    verify_ssl: bool = Field(default_factory=lambda: os.getenv("SANDFLY_VERIFY_SSL", "true").lower() == "true")
    timeout: int = Field(default=30)


class SandflyClient:
    """HTTP client for Sandfly API."""
    
    def __init__(self, config: SandflyConfig):
        self.config = config
        self.base_url = f"https://{config.host}/v4"
        self.token: str | None = None
        self.token_expiry: datetime | None = None
        self._client = httpx.Client(
            verify=config.verify_ssl,
            timeout=config.timeout
        )
    
    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return
        
        response = self._client.post(
            f"{self.base_url}/auth/login",
            json={"username": self.config.username, "password": self.config.password}
        )
        response.raise_for_status()
        data = response.json()
        self.token = data.get("access_token")
        # Token typically valid for 1 hour, refresh at 50 minutes
        self.token_expiry = datetime.now().replace(minute=datetime.now().minute + 50)
    
    def _headers(self) -> dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    async def get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make authenticated GET request."""
        await self._ensure_authenticated()
        response = self._client.get(
            f"{self.base_url}{endpoint}",
            headers=self._headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def post(self, endpoint: str, data: dict | None = None) -> dict:
        """Make authenticated POST request."""
        await self._ensure_authenticated()
        response = self._client.post(
            f"{self.base_url}{endpoint}",
            headers=self._headers(),
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    async def put(self, endpoint: str, data: dict | None = None) -> dict:
        """Make authenticated PUT request."""
        await self._ensure_authenticated()
        response = self._client.put(
            f"{self.base_url}{endpoint}",
            headers=self._headers(),
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    async def delete(self, endpoint: str, data: dict | None = None) -> dict:
        """Make authenticated DELETE request."""
        await self._ensure_authenticated()
        response = self._client.delete(
            f"{self.base_url}{endpoint}",
            headers=self._headers(),
            json=data
        )
        response.raise_for_status()
        return response.json()


# Initialize server and client
server = Server("mcp-sandfly")
config = SandflyConfig()
client = SandflyClient(config)


def tool_handler(func):
    """Decorator for tool handlers with error handling."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return [TextContent(type="text", text=str(result))]
        except httpx.HTTPStatusError as e:
            error_msg = f"API Error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    return wrapper


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS = [
    # --- Authentication & System ---
    Tool(
        name="sandfly_get_version",
        description="Get Sandfly server version and system information",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_get_license",
        description="Get current Sandfly license information",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_get_config",
        description="Get current Sandfly server configuration",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    
    # --- Hosts ---
    Tool(
        name="sandfly_list_hosts",
        description="List all registered hosts being monitored by Sandfly",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "boolean",
                    "description": "Return summary view (recommended)",
                    "default": True
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for pagination",
                    "default": 1
                },
                "size": {
                    "type": "integer",
                    "description": "Results per page",
                    "default": 100
                }
            },
            "required": []
        }
    ),
    Tool(
        name="sandfly_get_host",
        description="Get detailed information about a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID or sequence ID to retrieve"
                },
                "summary": {
                    "type": "boolean",
                    "description": "Return summary view",
                    "default": True
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_add_hosts",
        description="Add new hosts to Sandfly for monitoring",
        inputSchema={
            "type": "object",
            "properties": {
                "ip_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of IP addresses or CIDR ranges to scan"
                },
                "credentials_id": {
                    "type": "string",
                    "description": "Credential ID to use for SSH connections"
                },
                "ssh_port": {
                    "type": "integer",
                    "description": "SSH port number",
                    "default": 22
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to apply to discovered hosts"
                }
            },
            "required": ["ip_list", "credentials_id"]
        }
    ),
    Tool(
        name="sandfly_delete_host",
        description="Delete a host from Sandfly monitoring",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to delete"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_processes",
        description="Get running processes on a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get processes for"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_users",
        description="Get user accounts on a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get users for"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_listeners",
        description="Get network listeners on a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get listeners for"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_services",
        description="Get systemd services on a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get services for"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_scheduled_tasks",
        description="Get scheduled tasks (cron, at, systemd timers) on a host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get scheduled tasks for"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_kernel_modules",
        description="Get loaded kernel modules on a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get kernel modules for"
                }
            },
            "required": ["host_id"]
        }
    ),
    
    # --- Credentials ---
    Tool(
        name="sandfly_list_credentials",
        description="List all SSH credentials configured in Sandfly",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_add_credential",
        description="Add SSH credentials for host scanning",
        inputSchema={
            "type": "object",
            "properties": {
                "credentials_id": {
                    "type": "string",
                    "description": "Unique identifier for the credential"
                },
                "username": {
                    "type": "string",
                    "description": "SSH username"
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (optional if using key)"
                },
                "ssh_key": {
                    "type": "string",
                    "description": "SSH private key content (optional if using password)"
                },
                "ssh_key_password": {
                    "type": "string",
                    "description": "Password for encrypted SSH key"
                }
            },
            "required": ["credentials_id", "username"]
        }
    ),
    Tool(
        name="sandfly_delete_credential",
        description="Delete SSH credentials from Sandfly",
        inputSchema={
            "type": "object",
            "properties": {
                "credentials_id": {
                    "type": "string",
                    "description": "Credential ID to delete"
                }
            },
            "required": ["credentials_id"]
        }
    ),
    
    # --- Scanning ---
    Tool(
        name="sandfly_start_scan",
        description="Start a scan on specified hosts with specified sandflies",
        inputSchema={
            "type": "object",
            "properties": {
                "host_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of host IDs to scan"
                },
                "sandflies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of sandfly names to run (empty for all active)"
                }
            },
            "required": ["host_ids"]
        }
    ),
    Tool(
        name="sandfly_get_scan_errors",
        description="Get scan error log",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "boolean",
                    "description": "Return summary only",
                    "default": False
                }
            },
            "required": []
        }
    ),
    
    # --- Results ---
    Tool(
        name="sandfly_get_results",
        description="Search and retrieve scan results with filters",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Filter by host ID"
                },
                "sandfly_name": {
                    "type": "string",
                    "description": "Filter by sandfly name"
                },
                "status": {
                    "type": "string",
                    "enum": ["alert", "pass", "error"],
                    "description": "Filter by result status"
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Filter by severity level"
                },
                "page": {
                    "type": "integer",
                    "description": "Page number",
                    "default": 1
                },
                "size": {
                    "type": "integer",
                    "description": "Results per page",
                    "default": 100
                }
            },
            "required": []
        }
    ),
    Tool(
        name="sandfly_get_result",
        description="Get a specific scan result by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "result_id": {
                    "type": "string",
                    "description": "Result ID to retrieve"
                }
            },
            "required": ["result_id"]
        }
    ),
    Tool(
        name="sandfly_get_host_result_summary",
        description="Get results grouped by sandfly for a specific host",
        inputSchema={
            "type": "object",
            "properties": {
                "host_id": {
                    "type": "string",
                    "description": "Host ID to get result summary for"
                }
            },
            "required": ["host_id"]
        }
    ),
    Tool(
        name="sandfly_delete_result",
        description="Delete a specific scan result",
        inputSchema={
            "type": "object",
            "properties": {
                "result_id": {
                    "type": "string",
                    "description": "Result ID to delete"
                }
            },
            "required": ["result_id"]
        }
    ),
    
    # --- Sandflies (Detection Rules) ---
    Tool(
        name="sandfly_list_sandflies",
        description="List all available sandfly detection rules",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "boolean",
                    "description": "Return summary view",
                    "default": True
                },
                "no_templates": {
                    "type": "boolean",
                    "description": "Exclude template sandflies",
                    "default": False
                }
            },
            "required": []
        }
    ),
    Tool(
        name="sandfly_get_sandfly",
        description="Get details of a specific sandfly detection rule",
        inputSchema={
            "type": "object",
            "properties": {
                "sandfly_name": {
                    "type": "string",
                    "description": "Name of the sandfly to retrieve"
                }
            },
            "required": ["sandfly_name"]
        }
    ),
    Tool(
        name="sandfly_activate_sandfly",
        description="Activate a sandfly detection rule",
        inputSchema={
            "type": "object",
            "properties": {
                "sandfly_name": {
                    "type": "string",
                    "description": "Name of the sandfly to activate"
                }
            },
            "required": ["sandfly_name"]
        }
    ),
    Tool(
        name="sandfly_deactivate_sandfly",
        description="Deactivate a sandfly detection rule",
        inputSchema={
            "type": "object",
            "properties": {
                "sandfly_name": {
                    "type": "string",
                    "description": "Name of the sandfly to deactivate"
                }
            },
            "required": ["sandfly_name"]
        }
    ),
    
    # --- Schedules ---
    Tool(
        name="sandfly_list_schedules",
        description="List all scan schedules",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_get_schedule",
        description="Get details of a specific schedule",
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_name": {
                    "type": "string",
                    "description": "Name of the schedule to retrieve"
                }
            },
            "required": ["schedule_name"]
        }
    ),
    Tool(
        name="sandfly_add_schedule",
        description="Create a new scan schedule",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Schedule name"
                },
                "schedule_type": {
                    "type": "string",
                    "enum": ["scan", "discovery"],
                    "description": "Type of schedule"
                },
                "cron": {
                    "type": "string",
                    "description": "Cron expression (e.g., '0 */4 * * *' for every 4 hours)"
                },
                "host_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to select hosts for scanning"
                },
                "sandflies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sandfly names to run (empty for all active)"
                },
                "active": {
                    "type": "boolean",
                    "description": "Whether schedule is active",
                    "default": True
                }
            },
            "required": ["name", "schedule_type", "cron"]
        }
    ),
    Tool(
        name="sandfly_run_schedule",
        description="Manually trigger a scheduled scan to run now",
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_name": {
                    "type": "string",
                    "description": "Name of the schedule to run"
                },
                "mode": {
                    "type": "string",
                    "enum": ["immediate", "trickle"],
                    "description": "Execution mode",
                    "default": "immediate"
                }
            },
            "required": ["schedule_name"]
        }
    ),
    Tool(
        name="sandfly_pause_schedule",
        description="Pause a schedule",
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_name": {
                    "type": "string",
                    "description": "Name of the schedule to pause"
                }
            },
            "required": ["schedule_name"]
        }
    ),
    Tool(
        name="sandfly_unpause_schedule",
        description="Unpause a schedule",
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_name": {
                    "type": "string",
                    "description": "Name of the schedule to unpause"
                }
            },
            "required": ["schedule_name"]
        }
    ),
    Tool(
        name="sandfly_delete_schedule",
        description="Delete a schedule",
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_name": {
                    "type": "string",
                    "description": "Name of the schedule to delete"
                }
            },
            "required": ["schedule_name"]
        }
    ),
    
    # --- Jump Hosts ---
    Tool(
        name="sandfly_list_jump_hosts",
        description="List all configured jump hosts (SSH bastion hosts)",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_add_jump_host",
        description="Add a jump host for accessing isolated networks",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Jump host name"
                },
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP of the jump host"
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port",
                    "default": 22
                },
                "credentials_id": {
                    "type": "string",
                    "description": "Credential ID for the jump host"
                }
            },
            "required": ["name", "hostname", "credentials_id"]
        }
    ),
    Tool(
        name="sandfly_delete_jump_host",
        description="Delete a jump host",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Jump host name to delete"
                }
            },
            "required": ["name"]
        }
    ),
    
    # --- Notifications ---
    Tool(
        name="sandfly_list_notifications",
        description="List all notification configurations",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_add_notification",
        description="Add a new notification configuration (webhook, email, syslog)",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Notification name"
                },
                "type": {
                    "type": "string",
                    "enum": ["webhook", "email", "syslog"],
                    "description": "Notification type"
                },
                "url": {
                    "type": "string",
                    "description": "Webhook URL (for webhook type)"
                },
                "email": {
                    "type": "string",
                    "description": "Email address (for email type)"
                },
                "syslog_host": {
                    "type": "string",
                    "description": "Syslog host (for syslog type)"
                },
                "syslog_port": {
                    "type": "integer",
                    "description": "Syslog port",
                    "default": 514
                },
                "severity_filter": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Severity levels to notify on"
                },
                "active": {
                    "type": "boolean",
                    "description": "Whether notification is active",
                    "default": True
                }
            },
            "required": ["name", "type"]
        }
    ),
    Tool(
        name="sandfly_test_notification",
        description="Send a test notification",
        inputSchema={
            "type": "object",
            "properties": {
                "notification_id": {
                    "type": "integer",
                    "description": "Notification ID to test"
                }
            },
            "required": ["notification_id"]
        }
    ),
    
    # --- Reports ---
    Tool(
        name="sandfly_get_host_snapshot",
        description="Get a snapshot report of all hosts",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="sandfly_get_scan_performance",
        description="Get scan performance report",
        inputSchema={
            "type": "object",
            "properties": {
                "begin": {
                    "type": "string",
                    "description": "Start datetime (ISO format)"
                },
                "end": {
                    "type": "string",
                    "description": "End datetime (ISO format)"
                }
            },
            "required": []
        }
    ),
    
    # --- Audit Log ---
    Tool(
        name="sandfly_get_audit_log",
        description="Get the audit log of system activities",
        inputSchema={
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Page number",
                    "default": 1
                }
            },
            "required": []
        }
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    # --- Authentication & System ---
    if name == "sandfly_get_version":
        return await handle_get_version()
    elif name == "sandfly_get_license":
        return await handle_get_license()
    elif name == "sandfly_get_config":
        return await handle_get_config()
    
    # --- Hosts ---
    elif name == "sandfly_list_hosts":
        return await handle_list_hosts(arguments)
    elif name == "sandfly_get_host":
        return await handle_get_host(arguments)
    elif name == "sandfly_add_hosts":
        return await handle_add_hosts(arguments)
    elif name == "sandfly_delete_host":
        return await handle_delete_host(arguments)
    elif name == "sandfly_get_host_processes":
        return await handle_get_host_processes(arguments)
    elif name == "sandfly_get_host_users":
        return await handle_get_host_users(arguments)
    elif name == "sandfly_get_host_listeners":
        return await handle_get_host_listeners(arguments)
    elif name == "sandfly_get_host_services":
        return await handle_get_host_services(arguments)
    elif name == "sandfly_get_host_scheduled_tasks":
        return await handle_get_host_scheduled_tasks(arguments)
    elif name == "sandfly_get_host_kernel_modules":
        return await handle_get_host_kernel_modules(arguments)
    
    # --- Credentials ---
    elif name == "sandfly_list_credentials":
        return await handle_list_credentials()
    elif name == "sandfly_add_credential":
        return await handle_add_credential(arguments)
    elif name == "sandfly_delete_credential":
        return await handle_delete_credential(arguments)
    
    # --- Scanning ---
    elif name == "sandfly_start_scan":
        return await handle_start_scan(arguments)
    elif name == "sandfly_get_scan_errors":
        return await handle_get_scan_errors(arguments)
    
    # --- Results ---
    elif name == "sandfly_get_results":
        return await handle_get_results(arguments)
    elif name == "sandfly_get_result":
        return await handle_get_result(arguments)
    elif name == "sandfly_get_host_result_summary":
        return await handle_get_host_result_summary(arguments)
    elif name == "sandfly_delete_result":
        return await handle_delete_result(arguments)
    
    # --- Sandflies ---
    elif name == "sandfly_list_sandflies":
        return await handle_list_sandflies(arguments)
    elif name == "sandfly_get_sandfly":
        return await handle_get_sandfly(arguments)
    elif name == "sandfly_activate_sandfly":
        return await handle_activate_sandfly(arguments)
    elif name == "sandfly_deactivate_sandfly":
        return await handle_deactivate_sandfly(arguments)
    
    # --- Schedules ---
    elif name == "sandfly_list_schedules":
        return await handle_list_schedules()
    elif name == "sandfly_get_schedule":
        return await handle_get_schedule(arguments)
    elif name == "sandfly_add_schedule":
        return await handle_add_schedule(arguments)
    elif name == "sandfly_run_schedule":
        return await handle_run_schedule(arguments)
    elif name == "sandfly_pause_schedule":
        return await handle_pause_schedule(arguments)
    elif name == "sandfly_unpause_schedule":
        return await handle_unpause_schedule(arguments)
    elif name == "sandfly_delete_schedule":
        return await handle_delete_schedule(arguments)
    
    # --- Jump Hosts ---
    elif name == "sandfly_list_jump_hosts":
        return await handle_list_jump_hosts()
    elif name == "sandfly_add_jump_host":
        return await handle_add_jump_host(arguments)
    elif name == "sandfly_delete_jump_host":
        return await handle_delete_jump_host(arguments)
    
    # --- Notifications ---
    elif name == "sandfly_list_notifications":
        return await handle_list_notifications()
    elif name == "sandfly_add_notification":
        return await handle_add_notification(arguments)
    elif name == "sandfly_test_notification":
        return await handle_test_notification(arguments)
    
    # --- Reports ---
    elif name == "sandfly_get_host_snapshot":
        return await handle_get_host_snapshot()
    elif name == "sandfly_get_scan_performance":
        return await handle_get_scan_performance(arguments)
    
    # --- Audit ---
    elif name == "sandfly_get_audit_log":
        return await handle_get_audit_log(arguments)
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# =============================================================================
# Tool Handlers
# =============================================================================

@tool_handler
async def handle_get_version():
    """Get Sandfly version."""
    # Version is typically in the auth response or a dedicated endpoint
    await client._ensure_authenticated()
    return {"status": "connected", "message": "Successfully authenticated to Sandfly server"}


@tool_handler
async def handle_get_license():
    """Get license information."""
    return await client.get("/license")


@tool_handler
async def handle_get_config():
    """Get server configuration."""
    return await client.get("/config")


@tool_handler
async def handle_list_hosts(args: dict):
    """List all hosts."""
    params = {
        "summary": args.get("summary", True),
        "page": args.get("page", 1),
        "size": args.get("size", 100)
    }
    return await client.get("/hosts", params=params)


@tool_handler
async def handle_get_host(args: dict):
    """Get specific host."""
    host_id = args["host_id"]
    params = {"summary": args.get("summary", True)}
    return await client.get(f"/hosts/{host_id}", params=params)


@tool_handler
async def handle_add_hosts(args: dict):
    """Add hosts for monitoring."""
    data = {
        "ip_list": args["ip_list"],
        "credentials_id": args["credentials_id"],
        "ssh_port": args.get("ssh_port", 22),
        "tags": args.get("tags", [])
    }
    return await client.post("/hosts", data=data)


@tool_handler
async def handle_delete_host(args: dict):
    """Delete a host."""
    return await client.delete(f"/hosts/{args['host_id']}")


@tool_handler
async def handle_get_host_processes(args: dict):
    """Get host processes."""
    return await client.get(f"/hosts/{args['host_id']}/info/processes")


@tool_handler
async def handle_get_host_users(args: dict):
    """Get host users."""
    return await client.get(f"/hosts/{args['host_id']}/info/users")


@tool_handler
async def handle_get_host_listeners(args: dict):
    """Get host network listeners."""
    return await client.get(f"/hosts/{args['host_id']}/info/listeners")


@tool_handler
async def handle_get_host_services(args: dict):
    """Get host systemd services."""
    return await client.get(f"/hosts/{args['host_id']}/info/services")


@tool_handler
async def handle_get_host_scheduled_tasks(args: dict):
    """Get host scheduled tasks."""
    return await client.get(f"/hosts/{args['host_id']}/info/scheduledtasks")


@tool_handler
async def handle_get_host_kernel_modules(args: dict):
    """Get host kernel modules."""
    return await client.get(f"/hosts/{args['host_id']}/info/kernelmodules")


@tool_handler
async def handle_list_credentials():
    """List credentials."""
    return await client.get("/credentials")


@tool_handler
async def handle_add_credential(args: dict):
    """Add SSH credential."""
    cred_id = args["credentials_id"]
    data = {
        "username": args["username"],
        "password": args.get("password"),
        "ssh_key": args.get("ssh_key"),
        "ssh_key_password": args.get("ssh_key_password")
    }
    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}
    return await client.post(f"/credentials/{cred_id}", data=data)


@tool_handler
async def handle_delete_credential(args: dict):
    """Delete credential."""
    return await client.delete(f"/credentials/{args['credentials_id']}")


@tool_handler
async def handle_start_scan(args: dict):
    """Start a scan."""
    data = {
        "host_ids": args["host_ids"],
        "sandflies": args.get("sandflies", [])
    }
    return await client.post("/scan", data=data)


@tool_handler
async def handle_get_scan_errors(args: dict):
    """Get scan errors."""
    params = {"summary": args.get("summary", False)}
    return await client.get("/errors", params=params)


@tool_handler
async def handle_get_results(args: dict):
    """Get scan results."""
    filter_items = []
    
    if args.get("host_id"):
        filter_items.append({"field": "host_id", "operator": "equals", "value": args["host_id"]})
    if args.get("sandfly_name"):
        filter_items.append({"field": "sandfly_name", "operator": "equals", "value": args["sandfly_name"]})
    if args.get("status"):
        filter_items.append({"field": "status", "operator": "equals", "value": args["status"]})
    if args.get("severity"):
        filter_items.append({"field": "severity", "operator": "equals", "value": args["severity"]})
    
    data = {
        "filter": {
            "items": filter_items,
            "logicOperator": "and"
        },
        "page": args.get("page", 1),
        "size": args.get("size", 100),
        "summary": True
    }
    return await client.post("/results", data=data)


@tool_handler
async def handle_get_result(args: dict):
    """Get specific result."""
    return await client.get(f"/results/{args['result_id']}")


@tool_handler
async def handle_get_host_result_summary(args: dict):
    """Get host result summary."""
    return await client.get(f"/resultsummary/host/{args['host_id']}")


@tool_handler
async def handle_delete_result(args: dict):
    """Delete result."""
    return await client.delete(f"/results/{args['result_id']}")


@tool_handler
async def handle_list_sandflies(args: dict):
    """List sandflies."""
    params = {
        "summary": args.get("summary", True),
        "noTemplates": args.get("no_templates", False)
    }
    return await client.get("/sandflies", params=params)


@tool_handler
async def handle_get_sandfly(args: dict):
    """Get specific sandfly."""
    return await client.get(f"/sandflies/name/{args['sandfly_name']}")


@tool_handler
async def handle_activate_sandfly(args: dict):
    """Activate sandfly."""
    return await client.put(f"/sandflies/name/{args['sandfly_name']}/activate")


@tool_handler
async def handle_deactivate_sandfly(args: dict):
    """Deactivate sandfly."""
    return await client.put(f"/sandflies/name/{args['sandfly_name']}/deactivate")


@tool_handler
async def handle_list_schedules():
    """List schedules."""
    return await client.get("/schedule")


@tool_handler
async def handle_get_schedule(args: dict):
    """Get specific schedule."""
    return await client.get(f"/schedule/{args['schedule_name']}")


@tool_handler
async def handle_add_schedule(args: dict):
    """Add schedule."""
    data = {
        "name": args["name"],
        "schedule_type": args["schedule_type"],
        "cron": args["cron"],
        "host_tags": args.get("host_tags", []),
        "sandflies": args.get("sandflies", []),
        "active": args.get("active", True)
    }
    return await client.post("/schedule", data=data)


@tool_handler
async def handle_run_schedule(args: dict):
    """Run schedule now."""
    mode = args.get("mode", "immediate")
    return await client.post(f"/schedule/run/{args['schedule_name']}?mode={mode}")


@tool_handler
async def handle_pause_schedule(args: dict):
    """Pause schedule."""
    return await client.put(f"/schedule/pause/{args['schedule_name']}")


@tool_handler
async def handle_unpause_schedule(args: dict):
    """Unpause schedule."""
    return await client.put(f"/schedule/unpause/{args['schedule_name']}")


@tool_handler
async def handle_delete_schedule(args: dict):
    """Delete schedule."""
    return await client.delete(f"/schedule/{args['schedule_name']}")


@tool_handler
async def handle_list_jump_hosts():
    """List jump hosts."""
    return await client.get("/jumphosts")


@tool_handler
async def handle_add_jump_host(args: dict):
    """Add jump host."""
    name = args["name"]
    data = {
        "hostname": args["hostname"],
        "port": args.get("port", 22),
        "credentials_id": args["credentials_id"]
    }
    return await client.post(f"/jumphosts/{name}", data=data)


@tool_handler
async def handle_delete_jump_host(args: dict):
    """Delete jump host."""
    return await client.delete(f"/jumphosts/{args['name']}")


@tool_handler
async def handle_list_notifications():
    """List notifications."""
    return await client.get("/notifications")


@tool_handler
async def handle_add_notification(args: dict):
    """Add notification."""
    data = {
        "name": args["name"],
        "type": args["type"],
        "active": args.get("active", True),
        "severity_filter": args.get("severity_filter", [])
    }
    
    if args["type"] == "webhook":
        data["url"] = args.get("url")
    elif args["type"] == "email":
        data["email"] = args.get("email")
    elif args["type"] == "syslog":
        data["syslog_host"] = args.get("syslog_host")
        data["syslog_port"] = args.get("syslog_port", 514)
    
    return await client.post("/notifications", data=data)


@tool_handler
async def handle_test_notification(args: dict):
    """Test notification."""
    return await client.post(f"/notifications/test/{args['notification_id']}")


@tool_handler
async def handle_get_host_snapshot():
    """Get host snapshot report."""
    return await client.get("/reports/host_snapshot")


@tool_handler
async def handle_get_scan_performance(args: dict):
    """Get scan performance report."""
    params = {}
    if args.get("begin"):
        params["begin"] = args["begin"]
    if args.get("end"):
        params["end"] = args["end"]
    return await client.get("/reports/scan_performance", params=params)


@tool_handler
async def handle_get_audit_log(args: dict):
    """Get audit log."""
    params = {"page": args.get("page", 1)}
    return await client.get("/audit", params=params)


async def main():
    """Run the MCP server."""
    logger.info("Starting Sandfly Security MCP Server")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
