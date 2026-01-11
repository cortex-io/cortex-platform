"""Stuck pod detector - multi-signal liveness beyond k8s probes."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from .models import LivenessState, LivenessSignals

logger = logging.getLogger(__name__)


class StuckPodDetector:
    """Detect pods that are not crashing but also not making progress."""

    def __init__(self, awareness_client, commit_relay_client=None, config: dict = None):
        """
        Initialize detector.

        Args:
            awareness_client: Client for cortex-awareness MCP server
            commit_relay_client: Optional client for commit-relay agent state
            config: Configuration dict with:
                - liveness_check_interval: Seconds between checks (default: 60)
                - stuck_threshold: Score threshold for stuck (default: 0.4)
                - stuck_timeout: Seconds stuck before swap (default: 300)
        """
        self.awareness = awareness_client
        self.commit_relay = commit_relay_client

        config = config or {}
        self.check_interval = config.get("liveness_check_interval", 60)
        self.stuck_threshold = config.get("stuck_threshold", 0.4)
        self.stuck_timeout = config.get("stuck_timeout", 300)

        # Cache liveness state to detect duration
        self.liveness_cache: Dict[str, LivenessState] = {}

        # Signal weights (sum to 1.0)
        self.weights = {
            "k8s_ready": 0.20,
            "recent_logs": 0.20,
            "cpu_activity": 0.15,
            "network_activity": 0.15,
            "task_progress": 0.30,  # Most important
        }

    async def check_pod_liveness(self, pod_name: str) -> LivenessState:
        """
        Multi-signal liveness detection beyond k8s probes.

        Args:
            pod_name: Name of pod to check

        Returns:
            LivenessState with score and signals
        """
        # Get pod state from awareness
        state = await self.awareness.call_tool("get_pod_state", {"pod_name": pod_name})

        # Collect all signals
        signals = LivenessSignals(
            k8s_ready=await self._check_k8s_ready(state),
            recent_logs=await self._has_recent_logs(pod_name, minutes=5),
            cpu_activity=await self._has_cpu_activity(state),
            network_activity=await self._has_network_activity(pod_name),
            task_progress=await self._check_task_progress(pod_name)
        )

        # Calculate weighted score
        score = sum(
            self.weights[signal_name] * (1.0 if getattr(signals, signal_name) else 0.0)
            for signal_name in self.weights.keys()
        )

        # Determine if stuck
        stuck = score < self.stuck_threshold

        # Calculate stuck duration
        stuck_duration = self._calculate_stuck_duration(pod_name, stuck)

        liveness = LivenessState(
            pod_name=pod_name,
            score=score,
            signals=signals,
            stuck=stuck,
            stuck_duration=stuck_duration,
            assessment_time=datetime.utcnow()
        )

        # Update cache
        self.liveness_cache[pod_name] = liveness

        if stuck:
            logger.warning(
                f"Pod {pod_name} appears stuck (score: {score:.2f}, duration: {stuck_duration}s). "
                f"Signals: {signals}"
            )

        return liveness

    async def get_stuck_pods(self) -> list[LivenessState]:
        """Get list of all stuck pods."""
        # Get all cortex pods
        pods = await self.awareness.call_tool("get_sibling_pods")

        stuck_pods = []
        for pod in pods:
            if pod.get("phase") == "Running":
                liveness = await self.check_pod_liveness(pod["name"])
                if liveness.stuck and liveness.stuck_duration > self.stuck_timeout:
                    stuck_pods.append(liveness)

        return stuck_pods

    async def _check_k8s_ready(self, pod_state: dict) -> bool:
        """Check if pod passes k8s Ready condition."""
        conditions = pod_state.get("conditions", {})
        return conditions.get("Ready") == "True"

    async def _has_recent_logs(self, pod_name: str, minutes: int = 5) -> bool:
        """
        Check if pod has emitted logs recently.

        Args:
            pod_name: Pod to check
            minutes: Time window for "recent"

        Returns:
            True if logs found in last N minutes
        """
        try:
            # Get recent logs via awareness
            logs = await self.awareness.call_tool(
                "get_pod_logs",
                {"pod_name": pod_name, "since_seconds": minutes * 60, "tail": 10}
            )

            # If we got any logs, pod is emitting output
            return len(logs) > 0

        except Exception as e:
            logger.debug(f"Failed to check logs for {pod_name}: {e}")
            return False

    async def _has_cpu_activity(self, pod_state: dict) -> bool:
        """
        Check if pod is consuming CPU (>1 millicore).

        A stuck pod often has 0 CPU because it's blocked on I/O or deadlocked.
        """
        cpu_millicores = pod_state.get("cpu_millicores", 0)
        return cpu_millicores > 1

    async def _has_network_activity(self, pod_name: str) -> bool:
        """
        Check for recent network activity.

        This is a proxy for "is the pod doing work" since agents
        typically call APIs, databases, etc.
        """
        # TODO: Implement network activity check
        # Could use:
        # - Pod network metrics from prometheus
        # - Connection count from netstat
        # - Traffic bytes from cAdvisor

        # For now, return True (skip this signal)
        return True

    async def _check_task_progress(self, pod_name: str) -> bool:
        """
        Check if agent is making progress on its task.

        This is the MOST IMPORTANT signal for commit-relay agents.
        """
        if not self.commit_relay:
            # No commit-relay integration, can't check
            return True

        try:
            # Convert pod name to agent ID
            agent_id = self._pod_to_agent_id(pod_name)

            # Query commit-relay for agent state
            agent_state = await self.commit_relay.get_agent_state(agent_id)

            if not agent_state:
                logger.warning(f"No agent state found for {pod_name}")
                return False

            # Check for progress indicators
            last_action = agent_state.get("last_action_at")
            if last_action:
                age = (datetime.utcnow() - last_action).total_seconds()
                # Action within last 5 minutes = making progress
                return age < 300

            # Check for task completion
            if agent_state.get("status") == "completed":
                return True  # Task done, pod is healthy

            # No recent action, task not complete = stuck
            return False

        except Exception as e:
            logger.error(f"Failed to check task progress for {pod_name}: {e}")
            return False

    def _pod_to_agent_id(self, pod_name: str) -> str:
        """
        Convert pod name to agent ID.

        Assumes naming convention: {agent-type}-{agent-id}-{random}
        Example: code-agent-abc123-xyz456 → abc123
        """
        parts = pod_name.split("-")
        if len(parts) >= 3:
            return parts[-2]  # Second to last part
        return pod_name

    def _calculate_stuck_duration(self, pod_name: str, currently_stuck: bool) -> int:
        """
        Calculate how long a pod has been stuck.

        Args:
            pod_name: Pod to check
            currently_stuck: Is it stuck right now?

        Returns:
            Duration in seconds (0 if not stuck or first time stuck)
        """
        if not currently_stuck:
            # Not stuck, clear cache
            if pod_name in self.liveness_cache:
                del self.liveness_cache[pod_name]
            return 0

        # Check if we've seen it stuck before
        cached = self.liveness_cache.get(pod_name)
        if cached and cached.stuck:
            # Still stuck, calculate duration since first stuck
            duration = (datetime.utcnow() - cached.assessment_time).total_seconds()
            return int(duration)

        # First time seeing it stuck
        return 0
