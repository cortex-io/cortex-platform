#!/usr/bin/env python3
"""
n8n MCP Server
Exposes n8n workflow automation API through Model Context Protocol
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
logger = logging.getLogger("n8n-mcp")


class N8nConfig(BaseModel):
    """Configuration from environment variables"""
    host: str = Field(default="n8n.ry-ops.dev")
    port: int = Field(default=5678)
    api_key: str
    verify_ssl: bool = Field(default=False)
    timeout: int = Field(default=30)

    @classmethod
    def from_env(cls) -> "N8nConfig":
        """Load configuration from environment variables"""
        return cls(
            host=os.getenv("N8N_HOST", "n8n.ry-ops.dev"),
            port=int(os.getenv("N8N_PORT", "5678")),
            api_key=os.getenv("N8N_API_KEY", ""),
            verify_ssl=os.getenv("N8N_VERIFY_SSL", "false").lower() == "true",
            timeout=int(os.getenv("N8N_TIMEOUT", "30"))
        )


class N8nClient:
    """HTTP client for n8n REST API"""

    def __init__(self, config: N8nConfig):
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}/api/v1"
        self.client = httpx.Client(
            verify=config.verify_ssl,
            timeout=config.timeout,
            headers={
                "X-N8N-API-KEY": config.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        logger.info(f"n8n client initialized for {self.base_url}")

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
app = Server("n8n-mcp")
config = N8nConfig.from_env()
client = N8nClient(config)


def handle_errors(func):
    """Decorator to handle errors and return TextContent"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPError as e:
            error_msg = f"n8n API error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    return wrapper


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available n8n MCP tools"""
    return [
        # Workflow Tools
        Tool(
            name="n8n_list_workflows",
            description="List all workflows with their status (active/inactive)",
            inputSchema={
                "type": "object",
                "properties": {
                    "active": {
                        "type": "boolean",
                        "description": "Filter by active status (omit for all)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="n8n_get_workflow",
            description="Get detailed information about a specific workflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to query"
                    }
                },
                "required": ["workflow_id"]
            }
        ),
        Tool(
            name="n8n_execute_workflow",
            description="Trigger execution of a workflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to execute"
                    },
                    "data": {
                        "type": "object",
                        "description": "Optional input data for the workflow execution"
                    }
                },
                "required": ["workflow_id"]
            }
        ),

        # Execution Tools
        Tool(
            name="n8n_list_executions",
            description="List workflow executions with status",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Filter by workflow ID (omit for all)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: success, error, waiting, running",
                        "enum": ["success", "error", "waiting", "running"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="n8n_get_execution",
            description="Get detailed information about a specific execution",
            inputSchema={
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Execution ID to query"
                    }
                },
                "required": ["execution_id"]
            }
        ),
    ]


@app.call_tool()
@handle_errors
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution"""

    if name == "n8n_list_workflows":
        active_filter = arguments.get("active")

        # Get all workflows
        result = client.get("/workflows")
        workflows = result.get("data", [])

        # Filter by active status if specified
        if active_filter is not None:
            workflows = [w for w in workflows if w.get("active") == active_filter]

        # Format output
        total = len(workflows)
        active_count = sum(1 for w in workflows if w.get("active"))
        inactive_count = total - active_count

        summary_text = f"""n8n Workflows Summary:
Total Workflows: {total}
- Active: {active_count}
- Inactive: {inactive_count}

Workflows:
"""
        for workflow in workflows:
            wf_id = workflow.get("id", "unknown")
            wf_name = workflow.get("name", "Unnamed")
            is_active = workflow.get("active", False)
            status = "ACTIVE" if is_active else "INACTIVE"
            tags = workflow.get("tags", [])
            tags_str = f" [{', '.join(t.get('name', '') for t in tags)}]" if tags else ""
            summary_text += f"  • {wf_name} (ID: {wf_id}): {status}{tags_str}\n"

        return [TextContent(type="text", text=summary_text)]

    elif name == "n8n_get_workflow":
        workflow_id = arguments.get("workflow_id")
        result = client.get(f"/workflows/{workflow_id}")

        wf_data = result.get("data", {})
        wf_name = wf_data.get("name", "Unnamed")
        wf_active = wf_data.get("active", False)
        wf_nodes = wf_data.get("nodes", [])
        wf_connections = wf_data.get("connections", {})
        wf_tags = wf_data.get("tags", [])
        wf_created = wf_data.get("createdAt", "Unknown")
        wf_updated = wf_data.get("updatedAt", "Unknown")

        detail_text = f"""Workflow Details:
Name: {wf_name}
ID: {workflow_id}
Status: {"ACTIVE" if wf_active else "INACTIVE"}
Created: {wf_created}
Updated: {wf_updated}
Tags: {', '.join(t.get('name', '') for t in wf_tags) if wf_tags else 'None'}

Nodes ({len(wf_nodes)}):
"""
        for node in wf_nodes:
            node_name = node.get("name", "Unknown")
            node_type = node.get("type", "Unknown")
            detail_text += f"  • {node_name} ({node_type})\n"

        return [TextContent(type="text", text=detail_text)]

    elif name == "n8n_execute_workflow":
        workflow_id = arguments.get("workflow_id")
        data = arguments.get("data", {})

        # Execute workflow
        result = client.post(f"/workflows/{workflow_id}/activate", data={})

        # Get workflow info
        workflow = client.get(f"/workflows/{workflow_id}")
        wf_name = workflow.get("data", {}).get("name", "Unknown")

        return [TextContent(
            type="text",
            text=f"Workflow '{wf_name}' (ID: {workflow_id}) has been activated and will execute based on its trigger configuration.\n\nNote: For webhook-based workflows, you need to trigger them via their webhook URL. For manual workflows, use the n8n UI to execute."
        )]

    elif name == "n8n_list_executions":
        workflow_id = arguments.get("workflow_id")
        status_filter = arguments.get("status")
        limit = arguments.get("limit", 20)

        # Build query parameters
        params = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status_filter:
            params["status"] = status_filter

        # Get executions
        result = client.get("/executions", params=params)
        executions = result.get("data", [])

        if not executions:
            return [TextContent(
                type="text",
                text="No executions found matching the criteria."
            )]

        # Count by status
        success_count = sum(1 for e in executions if e.get("finished") and not e.get("stoppedAt"))
        error_count = sum(1 for e in executions if e.get("stoppedAt"))
        running_count = sum(1 for e in executions if not e.get("finished") and not e.get("stoppedAt"))

        summary_text = f"""n8n Executions Summary:
Total: {len(executions)}
- Success: {success_count}
- Error: {error_count}
- Running: {running_count}

Recent Executions:
"""
        for execution in executions[:limit]:
            exec_id = execution.get("id", "unknown")
            wf_name = execution.get("workflowData", {}).get("name", "Unknown")
            started = execution.get("startedAt", "Unknown")
            finished = execution.get("finished", False)
            stopped = execution.get("stoppedAt")

            if stopped:
                status = "ERROR"
            elif finished:
                status = "SUCCESS"
            else:
                status = "RUNNING"

            summary_text += f"  • {wf_name} (ID: {exec_id}): {status} - Started: {started}\n"

        return [TextContent(type="text", text=summary_text)]

    elif name == "n8n_get_execution":
        execution_id = arguments.get("execution_id")
        result = client.get(f"/executions/{execution_id}")

        exec_data = result.get("data", {})
        wf_name = exec_data.get("workflowData", {}).get("name", "Unknown")
        wf_id = exec_data.get("workflowId", "Unknown")
        started = exec_data.get("startedAt", "Unknown")
        finished_flag = exec_data.get("finished", False)
        stopped = exec_data.get("stoppedAt")
        mode = exec_data.get("mode", "Unknown")

        if stopped:
            status = "ERROR"
            ended = stopped
        elif finished_flag:
            status = "SUCCESS"
            ended = exec_data.get("finishedAt", "Unknown")
        else:
            status = "RUNNING"
            ended = "N/A"

        detail_text = f"""Execution Details:
Workflow: {wf_name} (ID: {wf_id})
Execution ID: {execution_id}
Status: {status}
Mode: {mode}
Started: {started}
Ended: {ended}

Execution Data:
{json.dumps(exec_data.get("data", {}), indent=2)}
"""
        return [TextContent(type="text", text=detail_text)]

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
