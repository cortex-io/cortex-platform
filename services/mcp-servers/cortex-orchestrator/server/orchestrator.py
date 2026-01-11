"""Main Cortex Orchestrator MCP server - intelligent pod lifecycle management."""

import asyncio
import logging
from typing import Optional
# MCP server disabled temporarily - using FastAPI instead
# from mcp.server import Server
from .dynamic_limiter import DynamicPodLimiter
from .spawn_modulator import SpawnModulator
from .stuck_detector import StuckPodDetector
from .pod_swapper import PodSwapper
from .models import (
    AgentSpec, OrchestrationStatus, ResourceProfile,
    SpawnStatistics, BackpressureFactor
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CortexOrchestrator:
    """
    Intelligent orchestration for Cortex agent lifecycle.

    Combines:
    - Dynamic pod limiting (capacity-based, not hard caps)
    - Adaptive spawn throttling (prevents thundering herd)
    - Stuck pod detection and self-healing swaps
    """

    def __init__(self, awareness_client, k8s_client, commit_relay_client=None, config: dict = None):
        """
        Initialize orchestrator.

        Args:
            awareness_client: cortex-awareness MCP client
            k8s_client: Kubernetes API client
            commit_relay_client: Optional commit-relay client for task progress
            config: Configuration dictionary
        """
        # self.server = Server("cortex-orchestrator")
        self.awareness = awareness_client
        self.k8s = k8s_client
        self.commit_relay = commit_relay_client

        config = config or {}

        # Initialize components
        self.limiter = DynamicPodLimiter(awareness_client, config)
        self.modulator = SpawnModulator(awareness_client, config)
        self.detector = StuckPodDetector(awareness_client, commit_relay_client, config)
        self.swapper = PodSwapper(self.detector, self.modulator, k8s_client, config)

        # Background tasks
        self.monitoring_task: Optional[asyncio.Task] = None

        # Register MCP tools - disabled for now
        # self._setup_tools()

    def _setup_tools(self):
        """Register all MCP tools - DISABLED temporarily."""
        logger.info("MCP tool registration disabled - using direct API calls")
        pass

        # === Orchestration Control ===

        # @self.server.tool()
        async def spawn_agent(agent_spec: dict) -> dict:
            """
            Spawn an agent with intelligent throttling.

            Args:
                agent_spec: {
                    "agent_type": str,
                    "task_id": str,
                    "priority": int (1-10),
                    "estimated_duration": int (seconds, optional),
                    "resource_override": {"cpu": int, "memory": int} (optional)
                }

            Returns:
                Spawn decision with status and timing
            """
            spec = AgentSpec(
                agent_type=agent_spec["agent_type"],
                task_id=agent_spec["task_id"],
                priority=agent_spec.get("priority", 5),
                estimated_duration=agent_spec.get("estimated_duration"),
                resource_override=(
                    ResourceProfile(**agent_spec["resource_override"])
                    if "resource_override" in agent_spec else None
                )
            )

            decision = await self.modulator.request_spawn(spec)

            return {
                "approved": decision.approved,
                "status": decision.status.value,
                "reason": decision.reason,
                "estimated_spawn_time": decision.estimated_spawn_time,
                "current_rate": decision.current_rate,
                "queue_position": decision.queue_position,
                "backpressure": [
                    {"name": f.name, "value": f.value, "reason": f.reason}
                    for f in decision.backpressure
                ]
            }

        @self.server.tool()
        async def get_orchestration_status() -> dict:
            """Get overall orchestrator health and status."""
            limit = await self.limiter.calculate_current_limit()
            rate = await self.modulator.calculate_spawn_rate()
            stuck_pods = await self.detector.get_stuck_pods()

            status = OrchestrationStatus(
                active_agents=limit.current_count,
                capacity_limit=limit.calculated_limit,
                headroom=limit.headroom,
                current_spawn_rate=rate,
                stuck_pods=len(stuck_pods),
                queued_tasks=self.modulator.get_queue_depth(),
                health=self._assess_health(limit, stuck_pods),
                recommendations=self._generate_recommendations(limit, rate, stuck_pods)
            )

            return {
                "active_agents": status.active_agents,
                "capacity_limit": status.capacity_limit,
                "headroom": status.headroom,
                "current_spawn_rate": status.current_spawn_rate,
                "stuck_pods": status.stuck_pods,
                "queued_tasks": status.queued_tasks,
                "health": status.health,
                "recommendations": status.recommendations,
                "timestamp": status.timestamp.isoformat()
            }

        @self.server.tool()
        async def pause_spawning(reason: str) -> dict:
            """Emergency brake - stop all spawning."""
            await self.modulator.pause_spawning(reason)
            return {"paused": True, "reason": reason}

        @self.server.tool()
        async def resume_spawning() -> dict:
            """Resume spawning after pause."""
            await self.modulator.resume_spawning()
            return {"resumed": True, "current_rate": self.modulator.current_rate}

        # === Capacity Management ===

        @self.server.tool()
        async def calculate_current_limit() -> dict:
            """Get dynamic pod limit based on cluster capacity."""
            limit = await self.limiter.calculate_current_limit()
            return {
                "current_count": limit.current_count,
                "calculated_limit": limit.calculated_limit,
                "limiting_resource": limit.limiting_resource,
                "headroom": limit.headroom,
                "stability_factor": limit.stability_factor,
                "can_scale_up": limit.can_scale_up,
                "recommendation": limit.recommendation
            }

        @self.server.tool()
        async def should_allow_spawn(agent_type: str) -> dict:
            """Pre-flight check if spawn is allowed for agent type."""
            allowed, reason = await self.limiter.should_allow_spawn(agent_type)
            return {"allowed": allowed, "reason": reason}

        @self.server.tool()
        async def get_resource_profiles() -> dict:
            """Get resource requirements for all agent types."""
            return {
                agent_type: {
                    "cpu_millicores": profile.cpu_millicores,
                    "memory_mb": profile.memory_mb
                }
                for agent_type, profile in self.limiter.profiles.items()
            }

        @self.server.tool()
        async def set_resource_profile(agent_type: str, cpu: int, memory: int) -> dict:
            """Update resource profile for an agent type."""
            self.limiter.set_resource_profile(agent_type, cpu, memory)
            return {"updated": True, "agent_type": agent_type, "cpu": cpu, "memory": memory}

        # === Spawn Modulation ===

        @self.server.tool()
        async def calculate_spawn_rate() -> dict:
            """Get current adaptive spawn rate."""
            rate = await self.modulator.calculate_spawn_rate()
            return {
                "current_rate": rate,
                "base_rate": self.modulator.base_rate,
                "backpressure": [
                    {"name": f.name, "value": f.value, "reason": f.reason}
                    for f in self.modulator.backpressure_signals
                ]
            }

        @self.server.tool()
        async def get_backpressure_status() -> dict:
            """Get active backpressure signals."""
            signals = self.modulator.get_backpressure_status()
            return {
                "signals": [
                    {"name": s.name, "value": s.value, "reason": s.reason}
                    for s in signals
                ]
            }

        @self.server.tool()
        async def get_queue_depth() -> dict:
            """Get pending spawn request count."""
            depth = self.modulator.get_queue_depth()
            return {"queue_depth": depth}

        # === Self-Healing ===

        @self.server.tool()
        async def check_pod_liveness(pod_name: str) -> dict:
            """Multi-signal liveness check for a pod."""
            liveness = await self.detector.check_pod_liveness(pod_name)
            return {
                "pod_name": liveness.pod_name,
                "score": liveness.score,
                "stuck": liveness.stuck,
                "stuck_duration": liveness.stuck_duration,
                "signals": {
                    "k8s_ready": liveness.signals.k8s_ready,
                    "recent_logs": liveness.signals.recent_logs,
                    "cpu_activity": liveness.signals.cpu_activity,
                    "network_activity": liveness.signals.network_activity,
                    "task_progress": liveness.signals.task_progress
                },
                "assessment_time": liveness.assessment_time.isoformat()
            }

        @self.server.tool()
        async def evaluate_and_swap(pod_name: str) -> dict:
            """Evaluate pod and swap if stuck."""
            result = await self.swapper.evaluate_and_swap(pod_name)
            return {
                "swapped": result.swapped,
                "outcome": result.outcome.value,
                "original_pod": result.original_pod,
                "replacement_pod": result.replacement_pod,
                "stuck_duration": result.stuck_duration,
                "state_preserved": result.state_preserved,
                "reason": result.reason,
                "recommendation": result.recommendation
            }

        @self.server.tool()
        async def get_stuck_pods() -> dict:
            """List all stuck pods."""
            stuck = await self.detector.get_stuck_pods()
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

        @self.server.tool()
        async def get_swap_history(minutes: int = 60) -> dict:
            """Get recent swap events."""
            history = self.swapper.get_swap_history(minutes)
            return {
                "count": len(history),
                "swaps": [
                    {
                        "timestamp": entry["timestamp"].isoformat(),
                        "original_pod": entry["original_pod"],
                        "stuck_duration": entry.get("stuck_duration", 0),
                        "state_preserved": entry.get("state_preserved", False)
                    }
                    for entry in history
                ]
            }

        @self.server.tool()
        async def force_swap(pod_name: str, reason: str) -> dict:
            """Manually force swap a pod (emergency use)."""
            result = await self.swapper.force_swap(pod_name, reason)
            return {
                "swapped": result.swapped,
                "outcome": result.outcome.value,
                "reason": result.reason
            }

    async def start_monitoring(self):
        """Start background monitoring tasks."""
        logger.info("Starting orchestrator background monitoring")
        self.monitoring_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop background monitoring."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """
        Background loop to:
        - Check for stuck pods
        - Auto-swap if stuck >5min
        - Log health metrics
        """
        while True:
            try:
                await asyncio.sleep(60)  # Every minute

                # Check for stuck pods
                stuck = await self.detector.get_stuck_pods()

                if stuck:
                    logger.warning(f"Found {len(stuck)} stuck pods")
                    for stuck_pod in stuck:
                        # Auto-swap if stuck >5min
                        if stuck_pod.stuck_duration > 300:
                            logger.info(f"Auto-swapping stuck pod: {stuck_pod.pod_name}")
                            result = await self.swapper.evaluate_and_swap(stuck_pod.pod_name)
                            if result.swapped:
                                logger.info(f"Successfully swapped {stuck_pod.pod_name}")

                # Log health status
                status = await self.server.call_tool("get_orchestration_status")
                logger.info(
                    f"Orchestrator health: {status['health']} "
                    f"(agents: {status['active_agents']}/{status['capacity_limit']}, "
                    f"rate: {status['current_spawn_rate']:.1f}/s, "
                    f"queue: {status['queued_tasks']})"
                )

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    def _assess_health(self, limit, stuck_pods) -> str:
        """Assess overall orchestrator health."""
        issues = 0

        # Check capacity utilization
        if limit.current_count >= limit.calculated_limit:
            issues += 1

        # Check stuck pods
        if len(stuck_pods) > 5:
            issues += 2  # Stuck pods are serious

        # Check stability
        if limit.stability_factor < 0.7:
            issues += 1

        if issues == 0:
            return "healthy"
        elif issues <= 2:
            return "degraded"
        else:
            return "unhealthy"

    def _generate_recommendations(self, limit, rate, stuck_pods) -> list:
        """Generate actionable recommendations."""
        recommendations = []

        if limit.current_count >= limit.calculated_limit * 0.9:
            recommendations.append(
                f"Near capacity ({limit.limiting_resource} constrained). "
                "Consider scaling cluster or reducing agent concurrency."
            )

        if len(stuck_pods) > 3:
            recommendations.append(
                f"{len(stuck_pods)} pods stuck. "
                "Check for task deadlocks or external dependency issues."
            )

        if rate < self.modulator.base_rate * 0.5:
            recommendations.append(
                "Spawn rate heavily throttled. "
                "Check backpressure signals and cluster health."
            )

        if not recommendations:
            recommendations.append("System operating normally.")

        return recommendations


# Convenience function for creating orchestrator
async def create_orchestrator(
    awareness_url: str,
    k8s_config_path: Optional[str] = None,
    commit_relay_url: Optional[str] = None,
    config: Optional[dict] = None
) -> CortexOrchestrator:
    """
    Create and initialize orchestrator.

    Args:
        awareness_url: URL for cortex-awareness MCP server
        k8s_config_path: Path to kubeconfig (None for in-cluster)
        commit_relay_url: Optional URL for commit-relay API
        config: Optional configuration override

    Returns:
        Initialized CortexOrchestrator
    """
    # TODO: Initialize clients
    # awareness_client = MCPClient(awareness_url)
    # k8s_client = KubernetesClient(k8s_config_path)
    # commit_relay_client = CommitRelayClient(commit_relay_url) if commit_relay_url else None

    # orchestrator = CortexOrchestrator(
    #     awareness_client=awareness_client,
    #     k8s_client=k8s_client,
    #     commit_relay_client=commit_relay_client,
    #     config=config
    # )

    # await orchestrator.start_monitoring()
    # return orchestrator

    raise NotImplementedError("Client initialization pending")
