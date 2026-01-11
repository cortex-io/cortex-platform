"""Pod swapper - self-healing replacement of stuck pods."""

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict
from .models import SwapResult, SwapOutcome, AgentSpec
from .stuck_detector import StuckPodDetector
from .spawn_modulator import SpawnModulator

logger = logging.getLogger(__name__)


class PodSwapper:
    """Replace stuck pods with fresh instances."""

    def __init__(
        self,
        detector: StuckPodDetector,
        modulator: SpawnModulator,
        k8s_client,
        config: dict = None
    ):
        """
        Initialize swapper.

        Args:
            detector: StuckPodDetector instance
            modulator: SpawnModulator instance
            k8s_client: Kubernetes API client
            config: Configuration dict with:
                - max_swap_retries: Max retries before escalation (default: 2)
                - grace_period: Pod deletion grace period (default: 10)
        """
        self.detector = detector
        self.modulator = modulator
        self.k8s = k8s_client

        config = config or {}
        self.max_retries = config.get("max_swap_retries", 2)
        self.grace_period = config.get("grace_period", 10)

        # Swap history for preventing loops
        self.swap_history: deque = deque(maxlen=100)

    async def evaluate_and_swap(self, pod_name: str) -> SwapResult:
        """
        Evaluate pod and swap if stuck.

        Args:
            pod_name: Name of pod to evaluate

        Returns:
            SwapResult with outcome
        """
        # Check liveness
        liveness = await self.detector.check_pod_liveness(pod_name)

        if not liveness.stuck:
            return SwapResult(
                swapped=False,
                outcome=SwapOutcome.SKIPPED,
                original_pod=pod_name,
                reason="pod_healthy"
            )

        # Check if stuck long enough
        if liveness.stuck_duration < self.detector.stuck_timeout:
            return SwapResult(
                swapped=False,
                outcome=SwapOutcome.SKIPPED,
                original_pod=pod_name,
                reason=f"stuck_timeout_not_reached ({liveness.stuck_duration}s < {self.detector.stuck_timeout}s)"
            )

        # Check for repeated failures (swap loop)
        recent_swaps = self._get_recent_swaps(pod_name, minutes=5)

        if len(recent_swaps) >= self.max_retries:
            # Persistent issue - escalate instead of swap
            logger.error(
                f"Pod {pod_name} has been swapped {len(recent_swaps)} times recently. "
                f"Escalating instead of swapping again."
            )
            return SwapResult(
                swapped=False,
                outcome=SwapOutcome.ESCALATED,
                original_pod=pod_name,
                reason="repeated_failures",
                action="escalate",
                recommendation=(
                    "Investigate root cause - pod failing repeatedly. "
                    "Check logs, resource constraints, external dependencies."
                )
            )

        # Capture agent state before killing
        agent_state = await self._capture_agent_state(pod_name)

        # Get pod metadata for replacement
        pod_metadata = await self._get_pod_metadata(pod_name)

        # Request replacement through modulator (respects backpressure)
        spawn_decision = await self.modulator.request_spawn(
            AgentSpec(
                agent_type=pod_metadata["agent_type"],
                task_id=pod_metadata.get("task_id", "unknown"),
                priority=10,  # Replacements get highest priority
                inherited_state=agent_state,
                node_affinity=pod_metadata.get("node")
            )
        )

        if not spawn_decision.approved:
            return SwapResult(
                swapped=False,
                outcome=SwapOutcome.FAILED,
                original_pod=pod_name,
                reason="spawn_throttled",
                recommendation=f"Retry after {spawn_decision.retry_after}s"
            )

        # Kill stuck pod
        logger.info(f"Swapping stuck pod {pod_name} (stuck for {liveness.stuck_duration}s)")
        await self._delete_pod(pod_name, grace_period=self.grace_period)

        # Record swap
        swap_entry = {
            "timestamp": datetime.utcnow(),
            "original_pod": pod_name,
            "replacement_requested": True,
            "stuck_duration": liveness.stuck_duration,
            "signals": liveness.signals,
            "state_preserved": agent_state is not None,
        }
        self.swap_history.append(swap_entry)

        logger.info(f"Swapped stuck pod {pod_name} successfully")

        return SwapResult(
            swapped=True,
            outcome=SwapOutcome.SUCCESS,
            original_pod=pod_name,
            replacement_pod=None,  # Will be filled in by spawner
            stuck_duration=liveness.stuck_duration,
            state_preserved=agent_state is not None
        )

    async def force_swap(self, pod_name: str, reason: str) -> SwapResult:
        """
        Manually force swap a pod (bypass liveness check).

        Use for emergency intervention.
        """
        logger.warning(f"FORCE SWAP requested for {pod_name}: {reason}")

        # Skip liveness check, go straight to swap
        agent_state = await self._capture_agent_state(pod_name)
        pod_metadata = await self._get_pod_metadata(pod_name)

        await self._delete_pod(pod_name, grace_period=self.grace_period)

        # Request replacement
        spawn_decision = await self.modulator.request_spawn(
            AgentSpec(
                agent_type=pod_metadata["agent_type"],
                task_id=pod_metadata.get("task_id", "unknown"),
                priority=10,
                inherited_state=agent_state
            )
        )

        self.swap_history.append({
            "timestamp": datetime.utcnow(),
            "original_pod": pod_name,
            "manual_swap": True,
            "reason": reason,
        })

        return SwapResult(
            swapped=True,
            outcome=SwapOutcome.SUCCESS,
            original_pod=pod_name,
            stuck_duration=0,
            state_preserved=agent_state is not None,
            reason=f"manual_swap: {reason}"
        )

    def get_swap_history(self, minutes: int = 60) -> list:
        """Get recent swap events."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            entry for entry in self.swap_history
            if entry["timestamp"] > cutoff
        ]

    async def _capture_agent_state(self, pod_name: str) -> Optional[Dict]:
        """
        Try to capture agent state before termination.

        Args:
            pod_name: Pod to capture state from

        Returns:
            Agent state dict if captured, None otherwise
        """
        try:
            # Try to send checkpoint signal to pod
            # Give it 5 seconds to respond
            import asyncio
            result = await asyncio.wait_for(
                self._send_checkpoint_signal(pod_name),
                timeout=5.0
            )
            logger.info(f"Captured state from {pod_name}")
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Pod {pod_name} too stuck to respond to checkpoint signal")
            # Try to scrape state from storage as fallback
            return await self._scrape_state_from_storage(pod_name)

        except Exception as e:
            logger.error(f"Failed to capture state from {pod_name}: {e}")
            return None

    async def _send_checkpoint_signal(self, pod_name: str) -> Optional[Dict]:
        """
        Send SIGUSR1 to pod to trigger checkpoint.

        Assumes agent has signal handler for SIGUSR1 that writes state.
        """
        # TODO: Implement signal sending via k8s exec
        # kubectl exec <pod> -- kill -USR1 1
        return None

    async def _scrape_state_from_storage(self, pod_name: str) -> Optional[Dict]:
        """
        Try to scrape state from persistent storage.

        If agent checkpoints to Redis, database, or file, try to read it.
        """
        # TODO: Implement state scraping from storage backends
        # - Check Redis for agent state
        # - Check MongoDB for task state
        # - Check PVC for checkpoint files
        return None

    async def _get_pod_metadata(self, pod_name: str) -> Dict:
        """
        Get pod metadata for replacement.

        Returns:
            Dict with agent_type, task_id, node, etc.
        """
        # Get pod from k8s API
        pod = await self.k8s.get_pod(pod_name)

        metadata = {
            "agent_type": pod.metadata.labels.get("agent-type", "unknown"),
            "task_id": pod.metadata.labels.get("task-id"),
            "node": pod.spec.node_name,
            "namespace": pod.metadata.namespace,
        }

        return metadata

    async def _delete_pod(self, pod_name: str, grace_period: int = 10):
        """
        Delete pod with grace period.

        Args:
            pod_name: Pod to delete
            grace_period: Seconds to wait before force kill
        """
        logger.info(f"Deleting stuck pod {pod_name} (grace period: {grace_period}s)")
        await self.k8s.delete_pod(pod_name, grace_period_seconds=grace_period)

    def _get_recent_swaps(self, pod_name: str, minutes: int = 5) -> list:
        """
        Get recent swaps for a pod (to detect loops).

        Args:
            pod_name: Pod to check
            minutes: Time window

        Returns:
            List of swap entries
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        # Match by pod name prefix (handles random suffixes)
        pod_prefix = "-".join(pod_name.split("-")[:-1])  # Remove random suffix

        return [
            entry for entry in self.swap_history
            if entry["timestamp"] > cutoff
            and entry["original_pod"].startswith(pod_prefix)
        ]
