#!/usr/bin/env python3
"""
Kubernetes MCP Server
Exposes Kubernetes API through Model Context Protocol
"""

import os
import json
import logging
from typing import Any, Optional
from functools import wraps

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kubernetes-mcp")


class K8sConfig(BaseModel):
    """Configuration from environment variables"""
    in_cluster: bool = Field(default=True)
    kubeconfig_path: Optional[str] = Field(default=None)

    @classmethod
    def from_env(cls) -> "K8sConfig":
        """Load configuration from environment variables"""
        return cls(
            in_cluster=os.getenv("K8S_IN_CLUSTER", "true").lower() == "true",
            kubeconfig_path=os.getenv("KUBECONFIG")
        )


# Initialize server
app = Server("kubernetes-mcp")
k8s_config = K8sConfig.from_env()

# Load Kubernetes config
if k8s_config.in_cluster:
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes config")
else:
    config.load_kube_config(config_file=k8s_config.kubeconfig_path)
    logger.info(f"Loaded kubeconfig from {k8s_config.kubeconfig_path or 'default location'}")

# Initialize clients
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
batch_v1 = client.BatchV1Api()


def handle_errors(func):
    """Decorator to handle errors and return TextContent"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ApiException as e:
            error_msg = f"Kubernetes API error: {e.status} - {e.reason}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    return wrapper


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available Kubernetes MCP tools"""
    return [
        # Cluster Info
        Tool(
            name="k8s_get_cluster_info",
            description="Get Kubernetes cluster information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # Namespace Tools
        Tool(
            name="k8s_list_namespaces",
            description="List all namespaces in the cluster",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # Pod Tools
        Tool(
            name="k8s_list_pods",
            description="List pods in a namespace or all namespaces",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to query (omit for all namespaces)"
                    },
                    "label_selector": {
                        "type": "string",
                        "description": "Label selector (e.g., 'app=nginx')"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="k8s_get_pod",
            description="Get details for a specific pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Pod name"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace"
                    }
                },
                "required": ["name", "namespace"]
            }
        ),
        Tool(
            name="k8s_get_pod_logs",
            description="Get logs from a pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Pod name"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace"
                    },
                    "container": {
                        "type": "string",
                        "description": "Container name (for multi-container pods)"
                    },
                    "tail_lines": {
                        "type": "integer",
                        "description": "Number of lines to tail (default: 100)",
                        "default": 100
                    }
                },
                "required": ["name", "namespace"]
            }
        ),

        # Deployment Tools
        Tool(
            name="k8s_list_deployments",
            description="List deployments in a namespace or all namespaces",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to query (omit for all namespaces)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="k8s_get_deployment",
            description="Get details for a specific deployment",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Deployment name"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace"
                    }
                },
                "required": ["name", "namespace"]
            }
        ),

        # Service Tools
        Tool(
            name="k8s_list_services",
            description="List services in a namespace or all namespaces",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to query (omit for all namespaces)"
                    }
                },
                "required": []
            }
        ),

        # Node Tools
        Tool(
            name="k8s_list_nodes",
            description="List all nodes in the cluster with status",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="k8s_get_node",
            description="Get details for a specific node",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Node name"
                    }
                },
                "required": ["name"]
            }
        ),

        # Resource Monitoring
        Tool(
            name="k8s_get_pod_problems",
            description="Get pods that are not running or have issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to check (omit for all namespaces)"
                    }
                },
                "required": []
            }
        ),
    ]


@app.call_tool()
@handle_errors
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution"""

    if name == "k8s_get_cluster_info":
        version = client.VersionApi().get_code()
        return [TextContent(
            type="text",
            text=f"""Kubernetes Cluster Info:
Version: {version.git_version}
Platform: {version.platform}
"""
        )]

    elif name == "k8s_list_namespaces":
        namespaces = v1.list_namespace()
        ns_list = "\n".join([f"  • {ns.metadata.name}" for ns in namespaces.items])
        return [TextContent(
            type="text",
            text=f"""Namespaces ({len(namespaces.items)}):
{ns_list}
"""
        )]

    elif name == "k8s_list_pods":
        namespace = arguments.get("namespace")
        label_selector = arguments.get("label_selector")

        if namespace:
            pods = v1.list_namespaced_pod(namespace, label_selector=label_selector)
        else:
            pods = v1.list_pod_for_all_namespaces(label_selector=label_selector)

        result = f"Pods ({len(pods.items)}):\n"
        for pod in pods.items:
            status = pod.status.phase
            ns = pod.metadata.namespace
            name = pod.metadata.name
            result += f"  • {ns}/{name}: {status}\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_get_pod":
        name_arg = arguments.get("name")
        namespace = arguments.get("namespace")

        pod = v1.read_namespaced_pod(name_arg, namespace)

        result = f"""Pod: {pod.metadata.namespace}/{pod.metadata.name}
Status: {pod.status.phase}
Node: {pod.spec.node_name}
IP: {pod.status.pod_ip}
Started: {pod.status.start_time}

Containers:
"""
        for container_status in pod.status.container_statuses or []:
            result += f"  • {container_status.name}: "
            if container_status.state.running:
                result += f"Running (started {container_status.state.running.started_at})\n"
            elif container_status.state.waiting:
                result += f"Waiting ({container_status.state.waiting.reason})\n"
            elif container_status.state.terminated:
                result += f"Terminated ({container_status.state.terminated.reason})\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_get_pod_logs":
        name_arg = arguments.get("name")
        namespace = arguments.get("namespace")
        container = arguments.get("container")
        tail_lines = arguments.get("tail_lines", 100)

        logs = v1.read_namespaced_pod_log(
            name_arg,
            namespace,
            container=container,
            tail_lines=tail_lines
        )

        return [TextContent(
            type="text",
            text=f"Logs for {namespace}/{name_arg}:\n\n{logs}"
        )]

    elif name == "k8s_list_deployments":
        namespace = arguments.get("namespace")

        if namespace:
            deployments = apps_v1.list_namespaced_deployment(namespace)
        else:
            deployments = apps_v1.list_deployment_for_all_namespaces()

        result = f"Deployments ({len(deployments.items)}):\n"
        for dep in deployments.items:
            ns = dep.metadata.namespace
            name = dep.metadata.name
            replicas = dep.status.replicas or 0
            ready = dep.status.ready_replicas or 0
            result += f"  • {ns}/{name}: {ready}/{replicas} ready\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_get_deployment":
        name_arg = arguments.get("name")
        namespace = arguments.get("namespace")

        deployment = apps_v1.read_namespaced_deployment(name_arg, namespace)

        result = f"""Deployment: {deployment.metadata.namespace}/{deployment.metadata.name}
Replicas: {deployment.status.ready_replicas or 0}/{deployment.status.replicas or 0} ready
Available: {deployment.status.available_replicas or 0}
Updated: {deployment.status.updated_replicas or 0}
Strategy: {deployment.spec.strategy.type}

Conditions:
"""
        for condition in deployment.status.conditions or []:
            result += f"  • {condition.type}: {condition.status} - {condition.message or 'N/A'}\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_list_services":
        namespace = arguments.get("namespace")

        if namespace:
            services = v1.list_namespaced_service(namespace)
        else:
            services = v1.list_service_for_all_namespaces()

        result = f"Services ({len(services.items)}):\n"
        for svc in services.items:
            ns = svc.metadata.namespace
            name = svc.metadata.name
            svc_type = svc.spec.type
            cluster_ip = svc.spec.cluster_ip
            result += f"  • {ns}/{name}: {svc_type} ({cluster_ip})\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_list_nodes":
        nodes = v1.list_node()

        result = f"Nodes ({len(nodes.items)}):\n"
        for node in nodes.items:
            name = node.metadata.name
            ready = "NotReady"
            for condition in node.status.conditions:
                if condition.type == "Ready":
                    ready = "Ready" if condition.status == "True" else "NotReady"
            version = node.status.node_info.kubelet_version
            result += f"  • {name}: {ready} (v{version})\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_get_node":
        name_arg = arguments.get("name")

        node = v1.read_node(name_arg)

        result = f"""Node: {node.metadata.name}
Kubelet Version: {node.status.node_info.kubelet_version}
OS: {node.status.node_info.os_image}
Kernel: {node.status.node_info.kernel_version}
Container Runtime: {node.status.node_info.container_runtime_version}

Conditions:
"""
        for condition in node.status.conditions:
            result += f"  • {condition.type}: {condition.status} - {condition.message}\n"

        result += "\nCapacity:\n"
        for key, value in node.status.capacity.items():
            result += f"  • {key}: {value}\n"

        return [TextContent(type="text", text=result)]

    elif name == "k8s_get_pod_problems":
        namespace = arguments.get("namespace")

        if namespace:
            pods = v1.list_namespaced_pod(namespace)
        else:
            pods = v1.list_pod_for_all_namespaces()

        problem_pods = []
        for pod in pods.items:
            phase = pod.status.phase
            if phase not in ["Running", "Succeeded"]:
                problem_pods.append({
                    "namespace": pod.metadata.namespace,
                    "name": pod.metadata.name,
                    "phase": phase,
                    "reason": pod.status.reason or "Unknown"
                })
            elif pod.status.container_statuses:
                for container_status in pod.status.container_statuses:
                    if not container_status.ready:
                        problem_pods.append({
                            "namespace": pod.metadata.namespace,
                            "name": pod.metadata.name,
                            "phase": "ContainerNotReady",
                            "reason": f"Container {container_status.name} not ready"
                        })
                        break

        if not problem_pods:
            return [TextContent(
                type="text",
                text="✅ No pod problems found! All pods are running normally."
            )]

        result = f"Problem Pods ({len(problem_pods)}):\n"
        for prob in problem_pods:
            result += f"  • {prob['namespace']}/{prob['name']}: {prob['phase']} - {prob['reason']}\n"

        return [TextContent(type="text", text=result)]

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
