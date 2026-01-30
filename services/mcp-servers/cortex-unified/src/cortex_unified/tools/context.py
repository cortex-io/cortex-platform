"""
cortex.context.* tools

Injects Cortex state into Claude Code sessions.
"""

import json
from dataclasses import asdict
from typing import Any

from mcp.types import Tool, TextContent

from ..clients.prometheus import PrometheusClient, ClusterMetrics
from ..clients.mcp_passthrough import MCPPassthroughClient

# Global client instances (initialized in server)
_prometheus_client: PrometheusClient | None = None
_mcp_client: MCPPassthroughClient | None = None


def set_context_clients(
    prometheus: PrometheusClient,
    mcp: MCPPassthroughClient,
):
    """Set the global client instances."""
    global _prometheus_client, _mcp_client
    _prometheus_client = prometheus
    _mcp_client = mcp


CONTEXT_TOOLS = [
    Tool(
        name="cortex_context_cluster",
        description="""Get current cluster state for context.

Returns:
- CPU and memory usage (cluster-wide)
- Pod and node counts
- Events per minute
- Network I/O rates

Use this at session start to understand the cluster's current state.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="cortex_context_nodes",
        description="""Get per-node metrics for context.

Returns CPU, memory, disk usage and pod count for each node.
Useful for identifying hot spots or resource pressure.""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of nodes to return (default: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    ),
    Tool(
        name="cortex_context_alerts",
        description="""Get active alerts for context.

Returns currently firing alerts from Prometheus/Alertmanager.
Critical for understanding if something is wrong right now.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="cortex_context_pods_problems",
        description="""Get pods that are not running normally.

Returns pods in CrashLoopBackOff, Pending, Failed, or with unready containers.
Essential for identifying issues to investigate.""",
        inputSchema={
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Filter to specific namespace (default: all)"
                }
            },
            "required": []
        }
    ),
    Tool(
        name="cortex_context_inject",
        description="""Get full Cortex context injection for session start.

Combines cluster metrics, node status, active alerts, and problem pods
into a single context payload. Use this when starting a new session
to give Claude full awareness of the current state.

This is the recommended way to start a Cortex session.""",
        inputSchema={
            "type": "object",
            "properties": {
                "include_nodes": {
                    "type": "boolean",
                    "description": "Include per-node metrics (default: true)",
                    "default": True
                },
                "include_alerts": {
                    "type": "boolean",
                    "description": "Include active alerts (default: true)",
                    "default": True
                },
                "include_problems": {
                    "type": "boolean",
                    "description": "Include problem pods (default: true)",
                    "default": True
                }
            },
            "required": []
        }
    ),
    Tool(
        name="cortex_context_mcp_health",
        description="""Check health of all MCP servers.

Returns health status of: kubernetes, proxmox, sandfly, unifi, n8n, cortex.
Useful for knowing which systems are available for operations.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


async def handle_context_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle context tool calls."""
    if _prometheus_client is None or _mcp_client is None:
        return [TextContent(
            type="text",
            text="Error: Context clients not initialized"
        )]

    if name == "cortex_context_cluster":
        metrics = await _prometheus_client.get_cluster_metrics()

        result = f"""Cluster Metrics:
  CPU Usage: {metrics.cpu_usage_percent:.1f}%
  Memory Usage: {metrics.memory_usage_percent:.1f}%
  Pod Count: {metrics.pod_count}
  Node Count: {metrics.node_count}
  Events/min: {metrics.events_per_minute:.1f}
  Network RX: {_format_bytes(metrics.network_receive_bytes)}/s
  Network TX: {_format_bytes(metrics.network_transmit_bytes)}/s"""

        return [TextContent(type="text", text=result)]

    elif name == "cortex_context_nodes":
        limit = arguments.get("limit", 10)
        nodes = await _prometheus_client.get_node_metrics()

        if not nodes:
            return [TextContent(type="text", text="No node metrics available")]

        lines = ["Node Metrics:"]
        for node in nodes[:limit]:
            lines.append(
                f"  {node.name}: CPU={node.cpu_percent:.1f}% "
                f"MEM={node.memory_percent:.1f}% "
                f"DISK={node.disk_percent:.1f}% "
                f"Pods={node.pod_count}"
            )

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "cortex_context_alerts":
        alerts = await _prometheus_client.get_alerts()

        if not alerts:
            return [TextContent(type="text", text="No active alerts")]

        lines = [f"Active Alerts ({len(alerts)}):"]
        for alert in alerts:
            severity = alert.get("severity", "unknown").upper()
            name = alert.get("name", "unknown")
            summary = alert.get("summary", "No summary")
            lines.append(f"  [{severity}] {name}: {summary}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "cortex_context_pods_problems":
        namespace = arguments.get("namespace")

        # Use kubernetes MCP server to get problem pods
        result = await _mcp_client.call_tool(
            "kubernetes",
            "k8s_get_pod_problems",
            {"namespace": namespace} if namespace else {},
        )

        if not result.success:
            return [TextContent(
                type="text",
                text=f"Error getting problem pods: {result.error}"
            )]

        return [TextContent(type="text", text=str(result.content))]

    elif name == "cortex_context_inject":
        include_nodes = arguments.get("include_nodes", True)
        include_alerts = arguments.get("include_alerts", True)
        include_problems = arguments.get("include_problems", True)

        sections = []

        # Cluster metrics
        metrics = await _prometheus_client.get_cluster_metrics()
        sections.append(f"""CLUSTER STATE:
  CPU: {metrics.cpu_usage_percent:.1f}% | Memory: {metrics.memory_usage_percent:.1f}%
  Pods: {metrics.pod_count} | Nodes: {metrics.node_count}
  Events/min: {metrics.events_per_minute:.1f}""")

        # Node metrics
        if include_nodes:
            nodes = await _prometheus_client.get_node_metrics()
            if nodes:
                node_lines = ["NODE STATUS:"]
                for node in nodes[:5]:  # Top 5 nodes
                    status = "OK"
                    if node.cpu_percent > 80 or node.memory_percent > 80:
                        status = "PRESSURE"
                    if node.cpu_percent > 95 or node.memory_percent > 95:
                        status = "CRITICAL"
                    node_lines.append(
                        f"  {node.name}: {status} "
                        f"(CPU={node.cpu_percent:.0f}% MEM={node.memory_percent:.0f}%)"
                    )
                sections.append("\n".join(node_lines))

        # Alerts
        if include_alerts:
            alerts = await _prometheus_client.get_alerts()
            if alerts:
                alert_lines = [f"ACTIVE ALERTS ({len(alerts)}):"]
                for alert in alerts[:10]:  # Top 10 alerts
                    severity = alert.get("severity", "?")[0].upper()
                    name = alert.get("name", "unknown")
                    alert_lines.append(f"  [{severity}] {name}")
                sections.append("\n".join(alert_lines))
            else:
                sections.append("ALERTS: None")

        # Problem pods
        if include_problems:
            result = await _mcp_client.call_tool(
                "kubernetes",
                "k8s_get_pod_problems",
                {},
            )
            if result.success and result.content:
                content = str(result.content)
                if "No pod problems" not in content:
                    sections.append(f"PROBLEM PODS:\n{content}")
                else:
                    sections.append("PROBLEM PODS: None")

        # MCP server health
        health = await _mcp_client.health_check_all()
        healthy = [k for k, v in health.items() if v]
        unhealthy = [k for k, v in health.items() if not v]

        mcp_status = f"MCP SERVERS: {len(healthy)} healthy"
        if unhealthy:
            mcp_status += f", {len(unhealthy)} down ({', '.join(unhealthy)})"
        sections.append(mcp_status)

        # Combine all sections
        full_context = "\n\n".join(sections)

        return [TextContent(
            type="text",
            text=f"=== CORTEX CONTEXT INJECTION ===\n\n{full_context}\n\n=== END CONTEXT ==="
        )]

    elif name == "cortex_context_mcp_health":
        health = await _mcp_client.health_check_all()

        lines = ["MCP Server Health:"]
        for server, is_healthy in sorted(health.items()):
            status = "healthy" if is_healthy else "DOWN"
            icon = "+" if is_healthy else "X"
            lines.append(f"  [{icon}] {server}: {status}")

        return [TextContent(type="text", text="\n".join(lines))]

    return [TextContent(type="text", text=f"Unknown context tool: {name}")]


def _format_bytes(bytes_per_sec: float) -> str:
    """Format bytes/sec to human readable."""
    if bytes_per_sec >= 1_000_000_000:
        return f"{bytes_per_sec / 1_000_000_000:.1f} GB"
    if bytes_per_sec >= 1_000_000:
        return f"{bytes_per_sec / 1_000_000:.1f} MB"
    if bytes_per_sec >= 1_000:
        return f"{bytes_per_sec / 1_000:.1f} KB"
    return f"{bytes_per_sec:.0f} B"
