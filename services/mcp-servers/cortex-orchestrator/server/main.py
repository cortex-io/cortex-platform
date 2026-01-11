"""Main entry point for Cortex Orchestrator MCP server."""

import asyncio
from datetime import datetime
import logging
import os
import signal
import sys
from typing import Optional

import structlog
import yaml
from kubernetes import client, config
from prometheus_client import start_http_server

from .orchestrator import CortexOrchestrator

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if os.getenv("LOG_FORMAT") == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class MCPAwarenessClient:
    """Client for cortex-awareness MCP server."""

    def __init__(self, url: str):
        self.url = url
        logger.info("awareness_client_initialized", url=url)

    async def call_tool(self, tool_name: str, args: dict = None):
        """Call a tool on the awareness server."""
        # TODO: Implement actual MCP client call
        logger.debug("awareness_tool_call", tool=tool_name, args=args)

        # Mock responses for now
        if tool_name == "get_cluster_capacity":
            return {
                "total_allocatable_cpu_millicores": 8000,
                "total_allocatable_memory_mb": 16384,
                "available_cpu_millicores": 4000,
                "available_memory_mb": 8192,
                "allocatable_cpu_percent": 50,
            }
        elif tool_name == "get_sibling_pods":
            return []
        elif tool_name == "get_pod_state":
            return {
                "conditions": {"Ready": "True"},
                "cpu_millicores": 100,
                "memory_mb": 256,
            }
        elif tool_name == "get_pod_logs":
            return ["log line 1", "log line 2"]
        elif tool_name == "get_recent_events":
            return []
        elif tool_name == "get_self_state":
            return {"status": "ok"}

        return {}


class CommitRelayClient:
    """Client for commit-relay agent state."""

    def __init__(self, url: str):
        self.url = url
        logger.info("commit_relay_client_initialized", url=url)

    async def get_agent_state(self, agent_id: str):
        """Get agent state from commit-relay."""
        # TODO: Implement actual API call
        logger.debug("commit_relay_state_query", agent_id=agent_id)
        return None


class K8sClient:
    """Wrapper for Kubernetes API client."""

    def __init__(self, in_cluster: bool = True):
        if in_cluster:
            config.load_incluster_config()
            logger.info("k8s_client_initialized", mode="in-cluster")
        else:
            config.load_kube_config()
            logger.info("k8s_client_initialized", mode="local-kubeconfig")

        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    async def get_pod(self, pod_name: str, namespace: str = "cortex-system"):
        """Get pod by name."""
        try:
            return self.core_v1.read_namespaced_pod(pod_name, namespace)
        except Exception as e:
            logger.error("pod_get_failed", pod=pod_name, error=str(e))
            raise

    async def delete_pod(self, pod_name: str, namespace: str = "cortex-system",
                        grace_period_seconds: int = 10):
        """Delete pod with grace period."""
        try:
            self.core_v1.delete_namespaced_pod(
                pod_name,
                namespace,
                grace_period_seconds=grace_period_seconds
            )
            logger.info("pod_deleted", pod=pod_name, grace_period=grace_period_seconds)
        except Exception as e:
            logger.error("pod_delete_failed", pod=pod_name, error=str(e))
            raise


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            logger.info("config_loaded", path=config_path)
            return config_data
    except Exception as e:
        logger.error("config_load_failed", path=config_path, error=str(e))
        sys.exit(1)


async def main():
    """Main entry point."""
    logger.info("cortex_orchestrator_starting",
                pod=os.getenv("POD_NAME", "unknown"),
                namespace=os.getenv("POD_NAMESPACE", "unknown"),
                node=os.getenv("NODE_NAME", "unknown"))

    # Load configuration
    config_path = os.getenv("CONFIG_PATH", "/etc/orchestrator/config.yaml")
    config_data = load_config(config_path)

    # Initialize clients
    awareness_url = os.getenv("AWARENESS_URL", "http://cortex-awareness:8080")
    commit_relay_url = os.getenv("COMMIT_RELAY_URL")

    awareness_client = MCPAwarenessClient(awareness_url)
    k8s_client = K8sClient(in_cluster=config_data.get("integration", {}).get("kubernetes", {}).get("in_cluster", True))

    commit_relay_client = None
    if commit_relay_url and config_data.get("integration", {}).get("commit_relay", {}).get("enabled", False):
        commit_relay_client = CommitRelayClient(commit_relay_url)

    # Start Prometheus metrics server
    if config_data.get("observability", {}).get("prometheus", {}).get("enabled", True):
        metrics_port = config_data.get("observability", {}).get("prometheus", {}).get("port", 9090)
        start_http_server(metrics_port)
        logger.info("prometheus_metrics_started", port=metrics_port)

    # Create orchestrator
    orchestrator = CortexOrchestrator(
        awareness_client=awareness_client,
        k8s_client=k8s_client,
        commit_relay_client=commit_relay_client,
        config=config_data
    )

    # Start background monitoring
    await orchestrator.start_monitoring()
    logger.info("orchestrator_monitoring_started")

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run HTTP server for health checks
    try:
        import uvicorn
        from fastapi import FastAPI

        app = FastAPI(title="Cortex Orchestrator")

        @app.get("/health")
        async def health():
            return {"status": "healthy", "service": "cortex-orchestrator"}

        @app.get("/ready")
        async def ready():
            return {"status": "ready", "service": "cortex-orchestrator"}

        @app.get("/status")
        async def status():
            return {
                "status": "running",
                "service": "cortex-orchestrator",
                "monitoring": "active"
            }

        # MCP Tool REST API Endpoints
        @app.post("/tools/get_orchestration_status")
        async def get_orchestration_status_api():
            """Get overall orchestration status"""
            try:
                limit = await orchestrator.limiter.calculate_current_limit()
                rate = await orchestrator.modulator.calculate_spawn_rate()
                stuck_pods = await orchestrator.detector.get_stuck_pods()

                health_val = "healthy"
                if limit.current_count >= limit.calculated_limit or len(stuck_pods) > 5:
                    health_val = "unhealthy"
                elif limit.stability_factor < 0.7 or len(stuck_pods) > 3:
                    health_val = "degraded"

                return {
                    "active_agents": limit.current_count,
                    "capacity_limit": limit.calculated_limit,
                    "headroom": limit.headroom,
                    "current_spawn_rate": rate,
                    "stuck_pods": len(stuck_pods),
                    "queued_tasks": orchestrator.modulator.get_queue_depth(),
                    "health": health_val,
                    "recommendations": [],
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"get_orchestration_status failed: {e}")
                return {"error": str(e)}, 500

        @app.post("/tools/calculate_current_limit")
        async def calculate_current_limit_api():
            """Get current dynamic pod limit"""
            try:
                limit = await orchestrator.limiter.calculate_current_limit()
                return {
                    "current_count": limit.current_count,
                    "calculated_limit": limit.calculated_limit,
                    "limiting_resource": limit.limiting_resource,
                    "headroom": limit.headroom,
                    "stability_factor": limit.stability_factor,
                    "can_scale_up": limit.can_scale_up,
                    "recommendation": limit.recommendation
                }
            except Exception as e:
                logger.error(f"calculate_current_limit failed: {e}")
                return {"error": str(e)}, 500

        @app.post("/tools/calculate_spawn_rate")
        async def calculate_spawn_rate_api():
            """Get current spawn rate"""
            try:
                rate = await orchestrator.modulator.calculate_spawn_rate()
                return {
                    "current_rate": rate,
                    "base_rate": orchestrator.modulator.base_rate,
                    "backpressure": [
                        {"name": f.name, "value": f.value, "reason": f.reason}
                        for f in orchestrator.modulator.backpressure_signals
                    ]
                }
            except Exception as e:
                logger.error(f"calculate_spawn_rate failed: {e}")
                return {"error": str(e)}, 500

        @app.post("/tools/get_stuck_pods")
        async def get_stuck_pods_api():
            """Get list of stuck pods"""
            try:
                stuck = await orchestrator.detector.get_stuck_pods()
                return {
                    "count": len(stuck),
                    "pods": [
                        {
                            "name": s.pod_name,
                            "score": s.score,
                            "stuck_duration": s.stuck_duration,
                            "signals": {
                                "k8s_ready": s.signals.k8s_ready,
                                "recent_logs": s.signals.recent_logs,
                                "cpu_activity": s.signals.cpu_activity,
                                "network_activity": s.signals.network_activity,
                                "task_progress": s.signals.task_progress
                            }
                        }
                        for s in stuck
                    ]
                }
            except Exception as e:
                logger.error(f"get_stuck_pods failed: {e}")
                return {"error": str(e)}, 500

        @app.post("/tools/pause_spawning")
        async def pause_spawning_api(request: dict = None):
            """Pause all spawning"""
            try:
                from fastapi import Request
                body = await request.json() if isinstance(request, Request) else (request or {})
                reason = body.get("reason", "Manual pause via API")
                await orchestrator.modulator.pause_spawning(reason)
                return {"paused": True, "reason": reason}
            except Exception as e:
                logger.error(f"pause_spawning failed: {e}")
                return {"error": str(e)}, 500

        @app.post("/tools/resume_spawning")
        async def resume_spawning_api():
            """Resume spawning"""
            try:
                await orchestrator.modulator.resume_spawning()
                return {"resumed": True, "current_rate": orchestrator.modulator.current_rate}
            except Exception as e:
                logger.error(f"resume_spawning failed: {e}")
                return {"error": str(e)}, 500

        @app.post("/tools/get_queue_depth")
        async def get_queue_depth_api():
            """Get spawn queue depth"""
            try:
                depth = orchestrator.modulator.get_queue_depth()
                return {"queue_depth": depth}
            except Exception as e:
                logger.error(f"get_queue_depth failed: {e}")
                return {"error": str(e)}, 500

        logger.info("http_server_starting", port=8080)

        # Create uvicorn server config
        config_uv = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8080,
            log_config=None,  # Use our own logging
            loop="asyncio"
        )
        server = uvicorn.Server(config_uv)

        # Run server until shutdown
        async def run_server():
            await server.serve()

        async def wait_for_shutdown():
            await shutdown_event.wait()
            await server.shutdown()

        logger.info("mcp_server_started")

        # Run both server and shutdown handler
        await asyncio.gather(run_server(), wait_for_shutdown())

    except Exception as e:
        logger.error("server_error", error=str(e), exc_info=True)
    finally:
        logger.info("orchestrator_shutting_down")
        await orchestrator.stop_monitoring()
        logger.info("orchestrator_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        sys.exit(1)
