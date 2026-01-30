"""
cortex.agents.* tools

Dispatch tasks to the Cortex agent framework via Redis.
"""

from typing import Any

from mcp.types import Tool, TextContent

from ..clients.redis_client import RedisClient, AgentType

# Global client instance (initialized in server)
_redis_client: RedisClient | None = None


def set_agents_client(client: RedisClient):
    """Set the global Redis client instance."""
    global _redis_client
    _redis_client = client


AGENT_TOOLS = [
    Tool(
        name="cortex_agents_list",
        description="""List registered agents in the framework.

Returns all masters and workers with their status and capabilities.
Use this to see what agents are available for task dispatch.""",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["master", "worker", "all"],
                    "description": "Filter by agent type (default: all)",
                    "default": "all"
                },
                "capability": {
                    "type": "string",
                    "description": "Filter by capability (e.g., 'sandfly_api', 'kubernetes')"
                }
            },
            "required": []
        }
    ),
    Tool(
        name="cortex_agents_status",
        description="""Get detailed status of a specific agent.

Returns agent info including status, capabilities, task count, and last heartbeat.""",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to query"
                }
            },
            "required": ["agent_id"]
        }
    ),
    Tool(
        name="cortex_agents_submit",
        description="""Submit a task to an agent.

Sends a task to the specified agent's Redis stream.
The agent will process it asynchronously.

Common task types:
- scan_host (sandfly worker)
- analyze_threat (sandfly worker)
- list_findings (sandfly worker)
- security_audit (security master)""",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Target agent ID"
                },
                "task_type": {
                    "type": "string",
                    "description": "Type of task to execute"
                },
                "payload": {
                    "type": "object",
                    "description": "Task payload/arguments"
                },
                "priority": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": "Priority: 1=normal, 2=high, 3=urgent",
                    "default": 1
                }
            },
            "required": ["agent_id", "task_type", "payload"]
        }
    ),
    Tool(
        name="cortex_agents_submit_and_wait",
        description="""Submit a task and wait for the result.

Like cortex_agents_submit but blocks until the task completes.
Use for synchronous operations where you need the result immediately.""",
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Target agent ID"
                },
                "task_type": {
                    "type": "string",
                    "description": "Type of task to execute"
                },
                "payload": {
                    "type": "object",
                    "description": "Task payload/arguments"
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in seconds (default: 60)",
                    "default": 60
                }
            },
            "required": ["agent_id", "task_type", "payload"]
        }
    ),
    Tool(
        name="cortex_agents_find_worker",
        description="""Find an available worker with a specific capability.

Searches for workers that are IDLE or READY with the requested capability.
Returns the first matching worker.""",
        inputSchema={
            "type": "object",
            "properties": {
                "capability": {
                    "type": "string",
                    "description": "Required capability (e.g., 'sandfly_api')"
                }
            },
            "required": ["capability"]
        }
    ),
    Tool(
        name="cortex_agents_health",
        description="""Check if agent framework (Redis) is healthy.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


async def handle_agent_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle agent tool calls."""
    if _redis_client is None:
        return [TextContent(
            type="text",
            text="Error: Agents client not initialized"
        )]

    if name == "cortex_agents_list":
        agent_type_str = arguments.get("type", "all")
        capability = arguments.get("capability")

        agent_type = None
        if agent_type_str == "master":
            agent_type = AgentType.MASTER
        elif agent_type_str == "worker":
            agent_type = AgentType.WORKER

        agents = await _redis_client.list_agents(
            agent_type=agent_type,
            capability=capability,
        )

        if not agents:
            return [TextContent(
                type="text",
                text="No agents found matching criteria"
            )]

        lines = [f"Agents ({len(agents)}):"]
        for agent in agents:
            status_icon = {
                "ready": "+",
                "idle": "~",
                "busy": "*",
                "starting": "^",
                "unhealthy": "!",
                "stopping": "-",
                "stopped": "X",
            }.get(agent.status.value, "?")

            lines.append(
                f"  [{status_icon}] {agent.agent_id} ({agent.agent_type.value})"
            )
            lines.append(f"      Status: {agent.status.value}")
            lines.append(f"      Capabilities: {', '.join(agent.capabilities)}")
            lines.append(f"      Tasks: {agent.task_count}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "cortex_agents_status":
        agent_id = arguments["agent_id"]
        agent = await _redis_client.get_agent(agent_id)

        if agent is None:
            return [TextContent(
                type="text",
                text=f"Agent not found: {agent_id}"
            )]

        result = f"""Agent: {agent.agent_id}
  Type: {agent.agent_type.value}
  Status: {agent.status.value}
  Capabilities: {', '.join(agent.capabilities)}
  Stream: {agent.stream}
  Task Count: {agent.task_count}
  Last Heartbeat: {agent.last_heartbeat.isoformat()}
  Metadata: {agent.metadata}"""

        return [TextContent(type="text", text=result)]

    elif name == "cortex_agents_submit":
        agent_id = arguments["agent_id"]
        task_type = arguments["task_type"]
        payload = arguments["payload"]
        priority = arguments.get("priority", 1)

        try:
            task_id = await _redis_client.submit_task(
                agent_id=agent_id,
                task_type=task_type,
                payload=payload,
                priority=priority,
            )
            return [TextContent(
                type="text",
                text=f"Task submitted successfully\n"
                     f"  Task ID: {task_id}\n"
                     f"  Agent: {agent_id}\n"
                     f"  Type: {task_type}\n"
                     f"  Priority: {priority}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error submitting task: {str(e)}"
            )]

    elif name == "cortex_agents_submit_and_wait":
        agent_id = arguments["agent_id"]
        task_type = arguments["task_type"]
        payload = arguments["payload"]
        timeout = arguments.get("timeout", 60)

        result = await _redis_client.submit_task_and_wait(
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
            timeout=timeout,
        )

        if result.success:
            return [TextContent(
                type="text",
                text=f"Task completed successfully\n"
                     f"  Task ID: {result.task_id}\n"
                     f"  Duration: {result.duration_ms}ms\n"
                     f"  Result: {result.result}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"Task failed\n"
                     f"  Task ID: {result.task_id}\n"
                     f"  Error: {result.error}"
            )]

    elif name == "cortex_agents_find_worker":
        capability = arguments["capability"]
        worker = await _redis_client.find_available_worker(capability)

        if worker is None:
            return [TextContent(
                type="text",
                text=f"No available worker found with capability: {capability}"
            )]

        return [TextContent(
            type="text",
            text=f"Found worker: {worker.agent_id}\n"
                 f"  Status: {worker.status.value}\n"
                 f"  Capabilities: {', '.join(worker.capabilities)}\n"
                 f"  Stream: {worker.stream}"
        )]

    elif name == "cortex_agents_health":
        healthy = await _redis_client.health_check()
        status = "healthy" if healthy else "unhealthy"
        return [TextContent(
            type="text",
            text=f"Agent framework (Redis): {status}"
        )]

    return [TextContent(type="text", text=f"Unknown agent tool: {name}")]
