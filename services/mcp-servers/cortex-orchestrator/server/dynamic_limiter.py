"""Dynamic pod limiter - capacity-based pod limits without hard caps."""

import logging
from typing import Dict, Tuple
from .models import PodLimit, ResourceProfile

logger = logging.getLogger(__name__)


class DynamicPodLimiter:
    """Calculate pod limits based on actual cluster capacity."""

    def __init__(self, awareness_client, config: dict):
        """
        Initialize limiter.

        Args:
            awareness_client: Client for cortex-awareness MCP server
            config: Configuration dict with:
                - cpu_headroom_percent: Reserve % for system (default: 30)
                - memory_headroom_percent: Reserve % for system (default: 30)
                - absolute_min_pods: Safety floor (default: 5)
                - absolute_max_pods: Safety ceiling (default: 500)
                - agent_profiles: Dict of agent types to ResourceProfile
        """
        self.awareness = awareness_client

        # Configuration
        self.cpu_headroom = config.get("cpu_headroom_percent", 30) / 100
        self.memory_headroom = config.get("memory_headroom_percent", 30) / 100
        self.absolute_min = config.get("absolute_min_pods", 5)
        self.absolute_max = config.get("absolute_max_pods", 500)

        # Resource profiles per agent type
        self.profiles: Dict[str, ResourceProfile] = config.get("agent_profiles", {})

        # Default profile if type not specified
        self.default_profile = ResourceProfile(
            cpu_millicores=200,
            memory_mb=256
        )

        # Track historical usage for better averages
        self.usage_history = []
        self.max_history_entries = 100

    async def calculate_current_limit(self) -> PodLimit:
        """
        Calculate how many pods we can run right now.

        Returns:
            PodLimit with calculated capacity
        """
        # Get cluster state from awareness
        cluster = await self.awareness.call_tool("get_cluster_capacity")
        current_pods = await self._get_cortex_pod_count()

        # Total allocatable resources
        total_cpu = cluster["total_allocatable_cpu_millicores"]
        total_memory = cluster["total_allocatable_memory_mb"]

        # Available after headroom reservation
        usable_cpu = total_cpu * (1 - self.cpu_headroom)
        usable_memory = total_memory * (1 - self.memory_headroom)

        # Calculate limits based on average pod usage
        avg_cpu_per_pod = await self._calculate_average_cpu_usage()
        avg_memory_per_pod = await self._calculate_average_memory_usage()

        # Prevent division by zero
        if avg_cpu_per_pod == 0 or avg_memory_per_pod == 0:
            logger.warning("Zero average resource usage, using profile defaults")
            avg_cpu_per_pod = self.default_profile.cpu_millicores
            avg_memory_per_pod = self.default_profile.memory_mb

        # Calculate limit per resource
        cpu_limit = int(usable_cpu / avg_cpu_per_pod)
        memory_limit = int(usable_memory / avg_memory_per_pod)

        # Limiting resource is the lower of the two
        if cpu_limit < memory_limit:
            calculated_limit = cpu_limit
            limiting_resource = "cpu"
        else:
            calculated_limit = memory_limit
            limiting_resource = "memory"

        # Apply safety rails
        calculated_limit = max(self.absolute_min, min(calculated_limit, self.absolute_max))

        # Adjust for cluster stability
        stability = await self._assess_stability()
        if stability < 0.7:
            # Reduce limit during instability
            logger.info(f"Cluster stability low ({stability:.2f}), reducing limit by 20%")
            calculated_limit = int(calculated_limit * 0.8)

        headroom = max(0, calculated_limit - current_pods)

        return PodLimit(
            current_count=current_pods,
            calculated_limit=calculated_limit,
            limiting_resource=limiting_resource,
            headroom=headroom,
            stability_factor=stability,
            can_scale_up=current_pods < calculated_limit,
            recommendation=self._generate_recommendation(
                current_pods,
                calculated_limit,
                limiting_resource
            )
        )

    async def should_allow_spawn(self, agent_type: str) -> Tuple[bool, str]:
        """
        Check if spawning a specific agent type is allowed.

        Args:
            agent_type: Type of agent to spawn

        Returns:
            (allowed: bool, reason: str)
        """
        # Get current limit
        limit = await self.calculate_current_limit()

        # Check if we're under the limit
        if limit.current_count >= limit.calculated_limit:
            return False, "at_dynamic_limit"

        # Check if this specific agent type would fit
        profile = self.profiles.get(agent_type, self.default_profile)
        cluster = await self.awareness.call_tool("get_cluster_capacity")

        available_cpu = cluster["available_cpu_millicores"]
        available_memory = cluster["available_memory_mb"]

        # Need 20% buffer for safety
        required_cpu = profile.cpu_millicores * 1.2
        required_memory = profile.memory_mb * 1.2

        if available_cpu < required_cpu:
            return False, "insufficient_cpu"

        if available_memory < required_memory:
            return False, "insufficient_memory"

        return True, "approved"

    def get_resource_profile(self, agent_type: str) -> ResourceProfile:
        """Get resource requirements for an agent type."""
        return self.profiles.get(agent_type, self.default_profile)

    def set_resource_profile(self, agent_type: str, cpu: int, memory: int):
        """Update resource profile for an agent type."""
        self.profiles[agent_type] = ResourceProfile(
            cpu_millicores=cpu,
            memory_mb=memory
        )
        logger.info(f"Updated profile for {agent_type}: {cpu}m CPU, {memory}Mi memory")

    async def _get_cortex_pod_count(self) -> int:
        """Get count of Cortex-managed pods."""
        pods = await self.awareness.call_tool("get_sibling_pods")
        return len([p for p in pods if p.get("phase") == "Running"])

    async def _calculate_average_cpu_usage(self) -> int:
        """Calculate average CPU usage per pod in millicores."""
        pods = await self.awareness.call_tool("get_sibling_pods")

        if not pods:
            return self.default_profile.cpu_millicores

        total_cpu = sum(p.get("cpu_millicores", 0) for p in pods)
        avg = total_cpu / len(pods) if len(pods) > 0 else 0

        # Add to history for rolling average
        self.usage_history.append({"cpu": avg})
        if len(self.usage_history) > self.max_history_entries:
            self.usage_history.pop(0)

        # Use historical average if available
        if len(self.usage_history) >= 10:
            historical_avg = sum(h["cpu"] for h in self.usage_history) / len(self.usage_history)
            return int(historical_avg)

        return int(avg) if avg > 0 else self.default_profile.cpu_millicores

    async def _calculate_average_memory_usage(self) -> int:
        """Calculate average memory usage per pod in MB."""
        pods = await self.awareness.call_tool("get_sibling_pods")

        if not pods:
            return self.default_profile.memory_mb

        total_memory = sum(p.get("memory_mb", 0) for p in pods)
        avg = total_memory / len(pods) if len(pods) > 0 else 0

        return int(avg) if avg > 0 else self.default_profile.memory_mb

    async def _assess_stability(self) -> float:
        """
        Assess cluster stability based on recent failures.

        Returns:
            Stability score 0.0-1.0 (1.0 = fully stable)
        """
        # Get recent events from awareness
        events = await self.awareness.call_tool("get_recent_events", {"minutes": 15})

        # Count error/warning events
        errors = len([e for e in events if e.get("type") == "Warning" or e.get("type") == "Error"])

        # Penalty for errors (max 30% reduction)
        error_penalty = min(errors * 0.05, 0.3)

        stability = 1.0 - error_penalty
        return max(0.0, min(1.0, stability))

    def _generate_recommendation(self, current: int, limit: int, limiting_resource: str) -> str:
        """Generate actionable recommendation based on utilization."""
        if limit == 0:
            return "Cannot calculate limit - check cluster state"

        utilization = current / limit

        if utilization > 0.95:
            return f"Critical: At capacity ({limiting_resource} constrained). Add nodes or reduce workload."
        elif utilization > 0.85:
            return f"Warning: Near capacity ({limiting_resource} constrained). Consider scaling cluster."
        elif utilization > 0.70:
            return "Healthy utilization. Monitor for growth."
        elif utilization < 0.30:
            return "Significant headroom available. Can handle burst workloads."
        else:
            return "Normal operating range."
