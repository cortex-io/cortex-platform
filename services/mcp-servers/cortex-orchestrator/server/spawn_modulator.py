"""Spawn modulator - adaptive throttling to prevent cluster overload."""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import List, Optional
from .models import SpawnDecision, SpawnStatus, BackpressureFactor, AgentSpec

logger = logging.getLogger(__name__)


class SpawnModulator:
    """Adaptive spawn rate control based on cluster state."""

    def __init__(self, awareness_client, config: dict):
        """
        Initialize modulator.

        Args:
            awareness_client: Client for cortex-awareness MCP server
            config: Configuration dict with:
                - base_spawn_rate: Default pods/second (default: 10)
                - max_pending_queue: Max queued requests (default: 100)
        """
        self.awareness = awareness_client

        # Configuration
        self.base_rate = config.get("base_spawn_rate", 10)  # pods per second
        self.max_queue = config.get("max_pending_queue", 100)

        # State
        self.current_rate = self.base_rate
        self.backpressure_signals: List[BackpressureFactor] = []

        # Spawn queue (priority queue)
        self.spawn_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.queue_lock = asyncio.Lock()

        # Track recent failures for backpressure
        self.recent_failures = deque(maxlen=50)

        # Track API latency
        self.api_latency_samples = deque(maxlen=20)

    async def calculate_spawn_rate(self) -> float:
        """
        Dynamically adjust spawn rate based on cluster health.

        Returns:
            Current spawn rate in pods/second
        """
        cluster = await self.awareness.call_tool("get_cluster_capacity")
        pending = await self._get_pending_pod_count()
        recent_failure_count = len([
            f for f in self.recent_failures
            if (datetime.utcnow() - f).total_seconds() < 300  # Last 5 minutes
        ])

        # Backpressure factors (all multiplicative)
        factors = []

        # 1. CPU headroom factor (0.0 to 1.0)
        cpu_percent = cluster.get("allocatable_cpu_percent", 50)
        cpu_factor = min(cpu_percent / 30, 1.0)  # Target 30% minimum headroom
        factors.append(BackpressureFactor(
            name="cpu_headroom",
            value=cpu_factor,
            reason=f"CPU headroom at {cpu_percent}% (target: 30%)"
        ))

        # 2. Pending pod pressure
        pending_factor = max(1.0 - (pending / 50), 0.1)  # Cap at 50 pending
        factors.append(BackpressureFactor(
            name="pending_pressure",
            value=pending_factor,
            reason=f"{pending} pods pending (target: <50)"
        ))

        # 3. Failure rate factor
        if recent_failure_count > 5:
            failure_factor = 0.3  # Aggressive slowdown
            reason = f"{recent_failure_count} recent failures - aggressive throttle"
        elif recent_failure_count > 0:
            failure_factor = 0.7
            reason = f"{recent_failure_count} recent failures - moderate throttle"
        else:
            failure_factor = 1.0
            reason = "No recent failures"
        factors.append(BackpressureFactor(
            name="failure_rate",
            value=failure_factor,
            reason=reason
        ))

        # 4. API server latency factor
        api_latency = await self._measure_api_latency()
        if api_latency > 500:  # ms
            api_factor = 0.5
            reason = f"API latency high ({api_latency}ms) - heavy throttle"
        elif api_latency > 200:
            api_factor = 0.8
            reason = f"API latency elevated ({api_latency}ms) - light throttle"
        else:
            api_factor = 1.0
            reason = f"API latency normal ({api_latency}ms)"
        factors.append(BackpressureFactor(
            name="api_latency",
            value=api_factor,
            reason=reason
        ))

        # Combined rate (multiplicative)
        combined = self.base_rate
        for factor in factors:
            combined *= factor.value

        # Floor of 0.5 pods/sec (don't stop completely)
        self.current_rate = max(combined, 0.5)
        self.backpressure_signals = factors

        logger.info(
            f"Spawn rate adjusted: {self.current_rate:.2f} pods/s "
            f"(base: {self.base_rate}, factors: {[f.value for f in factors]})"
        )

        return self.current_rate

    async def request_spawn(self, agent_spec: AgentSpec) -> SpawnDecision:
        """
        Gate spawn request through modulator.

        Args:
            agent_spec: Agent spawn specification

        Returns:
            SpawnDecision with approval status
        """
        # Refresh spawn rate
        rate = await self.calculate_spawn_rate()

        # Get current queue depth
        queue_depth = self.spawn_queue.qsize()

        # Check if queue is saturated
        if queue_depth >= self.max_queue:
            return SpawnDecision(
                approved=False,
                status=SpawnStatus.REJECTED,
                reason="spawn_queue_saturated",
                retry_after=30.0,  # Try again in 30 seconds
                current_rate=rate,
                backpressure=self.backpressure_signals
            )

        # Calculate wait time based on queue and rate
        wait_time = queue_depth / rate if rate > 0 else 60

        # If wait is too long, queue it
        if wait_time > 30:
            return SpawnDecision(
                approved=False,
                status=SpawnStatus.THROTTLED,
                reason="spawn_rate_limited",
                retry_after=wait_time,
                current_rate=rate,
                queue_position=queue_depth + 1,
                backpressure=self.backpressure_signals
            )

        # Add to queue with priority
        priority = self._calculate_priority(agent_spec)
        await self.spawn_queue.put((priority, agent_spec))

        logger.info(
            f"Spawn request queued: {agent_spec.agent_type} "
            f"(priority: {priority}, queue: {queue_depth + 1})"
        )

        return SpawnDecision(
            approved=True,
            status=SpawnStatus.QUEUED,
            reason="spawn_approved",
            estimated_spawn_time=wait_time,
            current_rate=rate,
            queue_position=queue_depth + 1
        )

    def record_spawn_failure(self):
        """Record a spawn failure for backpressure calculation."""
        self.recent_failures.append(datetime.utcnow())
        logger.warning(f"Spawn failure recorded ({len(self.recent_failures)} recent)")

    def get_backpressure_status(self) -> List[BackpressureFactor]:
        """Get current backpressure signals."""
        return self.backpressure_signals

    def get_queue_depth(self) -> int:
        """Get current spawn queue depth."""
        return self.spawn_queue.qsize()

    async def _get_pending_pod_count(self) -> int:
        """Get count of pending pods in cluster."""
        try:
            pods = await self.awareness.call_tool("get_sibling_pods")
            pending = [p for p in pods if p.get("phase") == "Pending"]
            return len(pending)
        except Exception as e:
            logger.error(f"Failed to get pending pod count: {e}")
            return 0

    async def _measure_api_latency(self) -> int:
        """
        Measure Kubernetes API server latency in milliseconds.

        Returns:
            Latency in milliseconds
        """
        start = datetime.utcnow()
        try:
            # Simple API call to measure latency
            await self.awareness.call_tool("get_self_state")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            # Add to rolling average
            self.api_latency_samples.append(latency)

            # Return average
            if len(self.api_latency_samples) > 0:
                avg = sum(self.api_latency_samples) / len(self.api_latency_samples)
                return int(avg)

            return int(latency)
        except Exception as e:
            logger.error(f"Failed to measure API latency: {e}")
            return 1000  # Assume high latency on error

    def _calculate_priority(self, agent_spec: AgentSpec) -> int:
        """
        Calculate spawn priority (lower number = higher priority).

        Priority factors:
        - User-specified priority (1-10)
        - Replacement spawns get +5 priority
        - Type-specific boosts

        Returns:
            Priority score (0 = highest)
        """
        base_priority = 10 - agent_spec.priority  # Invert (1→9, 10→0)

        # Replacements get priority boost
        if agent_spec.inherited_state:
            base_priority -= 5  # Higher priority

        # Type-specific adjustments
        priority_boosts = {
            "coordinator_master": -3,  # Coordinators are important
            "security_master": -2,
        }

        boost = priority_boosts.get(agent_spec.agent_type, 0)
        return max(0, base_priority + boost)

    async def pause_spawning(self, reason: str):
        """Emergency brake - stop all spawning."""
        logger.warning(f"Spawning PAUSED: {reason}")
        self.current_rate = 0.0
        # Clear backpressure signals except add manual pause
        self.backpressure_signals = [
            BackpressureFactor(
                name="manual_pause",
                value=0.0,
                reason=f"Manual pause: {reason}"
            )
        ]

    async def resume_spawning(self):
        """Resume spawning after pause."""
        logger.info("Spawning RESUMED")
        await self.calculate_spawn_rate()  # Recalculate
