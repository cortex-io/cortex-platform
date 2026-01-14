#!/usr/bin/env python3
"""
Langflow Chat MCP Server
Routes chat messages to appropriate Langflow workflows based on intent detection
"""

import os
import json
import logging
import re
from typing import Any, Optional, Dict, List
from functools import wraps

import httpx
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("langflow-chat-mcp")


class LangflowConfig(BaseModel):
    """Configuration from environment variables"""
    langflow_url: str = Field(default="http://langflow.cortex-system.svc.cluster.local:7860")
    langflow_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)

    @classmethod
    def from_env(cls) -> "LangflowConfig":
        """Load configuration from environment variables"""
        return cls(
            langflow_url=os.getenv("LANGFLOW_URL", "http://langflow.cortex-system.svc.cluster.local:7860"),
            langflow_api_key=os.getenv("LANGFLOW_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )


class WorkflowRouter:
    """Routes user messages to appropriate Langflow workflows"""

    # Workflow ID mapping (will be populated after workflows are imported)
    WORKFLOWS = {
        "daily_brief": {
            "patterns": [r"\b(hello|hi|hey|greetings?)\b"],
            "description": "Daily status brief with weather and infrastructure",
            "flow_id": None  # To be filled after import
        },
        "k8s_health": {
            "patterns": [r"\b(kubernetes|k8s|pods?|cluster|deployment|service)\b"],
            "description": "Kubernetes cluster health monitoring",
            "flow_id": None
        },
        "security_scan": {
            "patterns": [r"\b(security|vulnerabilit(y|ies)|scan|cve|github)\b"],
            "description": "Security vulnerability scanning",
            "flow_id": None
        },
        "cost_analysis": {
            "patterns": [r"\b(cost|spend(ing)?|budget|expense|dollar)\b"],
            "description": "Cost tracking and analysis",
            "flow_id": None
        },
        "log_analysis": {
            "patterns": [r"\b(log|error|anomal(y|ies)|debug|trace)\b"],
            "description": "Log pattern analysis",
            "flow_id": None
        },
        "deployment_check": {
            "patterns": [r"\b(deploy(ment)?|release|rollout|validate)\b"],
            "description": "Pre-deployment validation",
            "flow_id": None
        },
        "service_health": {
            "patterns": [r"\b(health|status|dashboard|monitor|uptime)\b"],
            "description": "Service health dashboard",
            "flow_id": None
        },
        "infrastructure": {
            "patterns": [r"\b(proxmox|vm|virtual machine|infrastructure|server)\b"],
            "description": "Infrastructure monitoring",
            "flow_id": None
        },
        "alert_analysis": {
            "patterns": [r"\b(alert|notification|warning|incident)\b"],
            "description": "Alert categorization and analysis",
            "flow_id": None
        },
        "documentation": {
            "patterns": [r"\b(document(ation)?|docs|readme|guide)\b"],
            "description": "Auto-documentation generation",
            "flow_id": None
        }
    }

    def __init__(self, config: LangflowConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)

    async def detect_intent(self, message: str) -> str:
        """Detect user intent from message using pattern matching"""
        message_lower = message.lower()

        # Check patterns for each workflow
        for workflow_name, workflow_info in self.WORKFLOWS.items():
            for pattern in workflow_info["patterns"]:
                if re.search(pattern, message_lower):
                    logger.info(f"Intent detected: {workflow_name} (pattern: {pattern})")
                    return workflow_name

        # Default to general chat if no pattern matches
        logger.info("No specific intent detected, using general chat")
        return "general_chat"

    async def route_to_workflow(self, message: str, session_id: str = "default") -> Dict[str, Any]:
        """Route message to appropriate Langflow workflow"""
        intent = await self.detect_intent(message)

        # Get workflow info
        workflow = self.WORKFLOWS.get(intent, {})
        flow_id = workflow.get("flow_id")

        if not flow_id:
            logger.warning(f"No flow_id configured for intent: {intent}")
            return {
                "response": f"I detected you want to {intent.replace('_', ' ')}, but that workflow isn't configured yet. Available workflows: {', '.join(self.WORKFLOWS.keys())}",
                "intent": intent,
                "error": "workflow_not_configured"
            }

        # Call Langflow workflow
        try:
            url = f"{self.config.langflow_url}/api/v1/run/{flow_id}"
            headers = {
                "Content-Type": "application/json"
            }
            if self.config.langflow_api_key:
                headers["x-api-key"] = self.config.langflow_api_key

            payload = {
                "input": message,
                "session_id": session_id,
                "tweaks": {}
            }

            logger.info(f"Calling Langflow workflow {flow_id} for intent: {intent}")
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Workflow {flow_id} completed successfully")

            return {
                "response": result.get("output", str(result)),
                "intent": intent,
                "workflow": workflow.get("description"),
                "flow_id": flow_id
            }

        except httpx.HTTPError as e:
            logger.error(f"Error calling Langflow workflow: {e}")
            return {
                "response": f"Sorry, I encountered an error processing your {intent.replace('_', ' ')} request: {str(e)}",
                "intent": intent,
                "error": str(e)
            }


# Initialize server
app = Server("langflow-chat-mcp")
config = LangflowConfig.from_env()
router = WorkflowRouter(config)


def error_handler(func):
    """Decorator for error handling"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    return wrapper


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="chat",
            description="Route a chat message to the appropriate Langflow workflow based on intent detection",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The user's chat message"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID for conversation context",
                        "default": "default"
                    }
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="get_workflows",
            description="Get list of available Langflow workflows and their triggers",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="set_workflow_id",
            description="Configure a workflow's Langflow flow ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_name": {
                        "type": "string",
                        "description": "Name of the workflow (e.g., 'daily_brief', 'k8s_health')"
                    },
                    "flow_id": {
                        "type": "string",
                        "description": "The Langflow flow ID"
                    }
                },
                "required": ["workflow_name", "flow_id"]
            }
        )
    ]


@app.call_tool()
@error_handler
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""

    if name == "chat":
        message = arguments.get("message")
        session_id = arguments.get("session_id", "default")

        if not message:
            return [TextContent(type="text", text="Error: message is required")]

        result = await router.route_to_workflow(message, session_id)

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    elif name == "get_workflows":
        workflows_info = {
            name: {
                "description": info["description"],
                "patterns": info["patterns"],
                "flow_id": info["flow_id"],
                "configured": info["flow_id"] is not None
            }
            for name, info in router.WORKFLOWS.items()
        }

        return [TextContent(
            type="text",
            text=json.dumps(workflows_info, indent=2)
        )]

    elif name == "set_workflow_id":
        workflow_name = arguments.get("workflow_name")
        flow_id = arguments.get("flow_id")

        if workflow_name not in router.WORKFLOWS:
            return [TextContent(
                type="text",
                text=f"Error: Unknown workflow '{workflow_name}'. Available: {', '.join(router.WORKFLOWS.keys())}"
            )]

        router.WORKFLOWS[workflow_name]["flow_id"] = flow_id

        return [TextContent(
            type="text",
            text=f"Successfully configured {workflow_name} with flow_id: {flow_id}"
        )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Main entry point"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        logger.info("Langflow Chat MCP Server starting...")
        logger.info(f"Langflow URL: {config.langflow_url}")
        logger.info(f"Available workflows: {len(router.WORKFLOWS)}")

        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
