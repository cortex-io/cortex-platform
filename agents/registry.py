"""
Agent registry for tracking and discovering active agents.

Maintains a Redis-backed registry of all agents (masters and workers)
with their status, capabilities, and health information.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import redis.asyncio as redis


logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"


class AgentType(str, Enum):
    """Type of agent."""

    MASTER = "master"
    WORKER = "worker"


@dataclass
class AgentInfo:
    """
    Information about a registered agent.

    Attributes:
        agent_id: Unique agent identifier
        agent_type: Master or worker
        name: Human-readable agent name
        status: Current agent status
        capabilities: List of capabilities (e.g., ["sandfly_api", "threat_analysis"])
        stream: Redis stream for receiving tasks
        metadata: Additional agent-specific metadata
        registered_at: Registration timestamp
        last_heartbeat: Last heartbeat timestamp
        task_count: Number of tasks processed
        version: Agent version
    """

    agent_id: str
    agent_type: AgentType
    name: str
    status: AgentStatus
    capabilities: List[str]
    stream: str
    metadata: Dict[str, str] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    task_count: int = 0
    version: str = "0.1.0"

    def to_dict(self) -> Dict[str, str]:
        """Convert to Redis hash-compatible dictionary (strings only)."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "status": self.status.value,
            "capabilities": ",".join(self.capabilities),
            "stream": self.stream,
            "metadata": str(self.metadata),
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "task_count": str(self.task_count),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "AgentInfo":
        """Create AgentInfo from Redis hash."""
        return cls(
            agent_id=data["agent_id"],
            agent_type=AgentType(data["agent_type"]),
            name=data["name"],
            status=AgentStatus(data["status"]),
            capabilities=data["capabilities"].split(",") if data["capabilities"] else [],
            stream=data["stream"],
            metadata=eval(data.get("metadata", "{}")),  # Safe for simple dicts
            registered_at=datetime.fromisoformat(data["registered_at"]),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]),
            task_count=int(data.get("task_count", 0)),
            version=data.get("version", "0.1.0"),
        )


class AgentRegistry:
    """
    Redis-backed registry for agent tracking and discovery.

    Stores agent metadata in Redis hashes with automatic expiration
    for dead agents (heartbeat-based).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        registry_prefix: str = "cortex:agents",
        heartbeat_interval_seconds: int = 30,
        heartbeat_timeout_seconds: int = 120,
    ):
        """
        Initialize agent registry.

        Args:
            redis_url: Redis connection URL
            registry_prefix: Key prefix for registry entries
            heartbeat_interval_seconds: How often agents should heartbeat
            heartbeat_timeout_seconds: Consider agent dead after this timeout
        """
        self.redis_url = redis_url
        self.registry_prefix = registry_prefix
        self.heartbeat_interval = heartbeat_interval_seconds
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._client is None:
            self._client = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
            logger.info(f"Registry connected to Redis at {self.redis_url}")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Registry disconnected from Redis")

    def _agent_key(self, agent_id: str) -> str:
        """Generate Redis key for agent."""
        return f"{self.registry_prefix}:{agent_id}"

    async def register(self, agent_info: AgentInfo) -> bool:
        """
        Register a new agent.

        Args:
            agent_info: Agent information to register

        Returns:
            True if registration succeeded

        Raises:
            RuntimeError: If not connected to Redis
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        key = self._agent_key(agent_info.agent_id)
        await self._client.hset(key, mapping=agent_info.to_dict())
        await self._client.expire(key, self.heartbeat_timeout * 2)  # Double timeout for safety

        # Add to type-specific set
        type_set = f"{self.registry_prefix}:type:{agent_info.agent_type.value}"
        await self._client.sadd(type_set, agent_info.agent_id)

        # Add to status-specific set
        status_set = f"{self.registry_prefix}:status:{agent_info.status.value}"
        await self._client.sadd(status_set, agent_info.agent_id)

        logger.info(f"Registered agent: {agent_info.agent_id} ({agent_info.name})")
        return True

    async def deregister(self, agent_id: str) -> bool:
        """
        Deregister an agent.

        Args:
            agent_id: Agent ID to deregister

        Returns:
            True if agent was found and deregistered
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        # Get agent info first to clean up sets
        agent_info = await self.get_agent(agent_id)
        if agent_info:
            # Remove from type set
            type_set = f"{self.registry_prefix}:type:{agent_info.agent_type.value}"
            await self._client.srem(type_set, agent_id)

            # Remove from status set
            status_set = f"{self.registry_prefix}:status:{agent_info.status.value}"
            await self._client.srem(status_set, agent_id)

        # Delete agent key
        key = self._agent_key(agent_id)
        deleted = await self._client.delete(key)

        if deleted:
            logger.info(f"Deregistered agent: {agent_id}")
        return bool(deleted)

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get information about a specific agent.

        Args:
            agent_id: Agent ID to look up

        Returns:
            AgentInfo if found, None otherwise
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        key = self._agent_key(agent_id)
        data = await self._client.hgetall(key)

        if not data:
            return None

        return AgentInfo.from_dict(data)

    async def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """
        Update agent status.

        Args:
            agent_id: Agent ID
            status: New status

        Returns:
            True if update succeeded
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        agent_info = await self.get_agent(agent_id)
        if not agent_info:
            logger.warning(f"Cannot update status for unknown agent: {agent_id}")
            return False

        # Remove from old status set
        old_status_set = f"{self.registry_prefix}:status:{agent_info.status.value}"
        await self._client.srem(old_status_set, agent_id)

        # Add to new status set
        new_status_set = f"{self.registry_prefix}:status:{status.value}"
        await self._client.sadd(new_status_set, agent_id)

        # Update status in hash
        key = self._agent_key(agent_id)
        await self._client.hset(key, "status", status.value)

        logger.debug(f"Updated status for {agent_id}: {agent_info.status} -> {status}")
        return True

    async def heartbeat(self, agent_id: str) -> bool:
        """
        Update agent heartbeat timestamp.

        Args:
            agent_id: Agent ID

        Returns:
            True if heartbeat recorded
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        key = self._agent_key(agent_id)
        exists = await self._client.exists(key)

        if not exists:
            logger.warning(f"Heartbeat for unknown agent: {agent_id}")
            return False

        now = datetime.utcnow().isoformat()
        await self._client.hset(key, "last_heartbeat", now)
        await self._client.expire(key, self.heartbeat_timeout * 2)

        logger.debug(f"Heartbeat received from {agent_id}")
        return True

    async def increment_task_count(self, agent_id: str) -> int:
        """
        Increment task count for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            New task count
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        key = self._agent_key(agent_id)
        new_count = await self._client.hincrby(key, "task_count", 1)
        return new_count

    async def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        status: Optional[AgentStatus] = None,
    ) -> List[AgentInfo]:
        """
        List all registered agents, optionally filtered.

        Args:
            agent_type: Filter by agent type
            status: Filter by status

        Returns:
            List of AgentInfo objects
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        # Determine which agents to fetch
        agent_ids = set()

        if agent_type:
            type_set = f"{self.registry_prefix}:type:{agent_type.value}"
            type_ids = await self._client.smembers(type_set)
            agent_ids.update(type_ids)
        elif status:
            status_set = f"{self.registry_prefix}:status:{status.value}"
            status_ids = await self._client.smembers(status_set)
            agent_ids.update(status_ids)
        else:
            # Get all agent IDs by scanning keys
            pattern = f"{self.registry_prefix}:*"
            async for key in self._client.scan_iter(match=pattern):
                if ":" in key and key.count(":") == 2:  # agent key format
                    agent_id = key.split(":")[-1]
                    agent_ids.add(agent_id)

        # Fetch agent info for each ID
        agents = []
        for agent_id in agent_ids:
            agent_info = await self.get_agent(agent_id)
            if agent_info:
                # Apply status filter if type filter was used
                if agent_type and status and agent_info.status != status:
                    continue
                agents.append(agent_info)

        return agents

    async def find_workers_by_capability(self, capability: str) -> List[AgentInfo]:
        """
        Find all workers with a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of matching worker AgentInfo objects
        """
        workers = await self.list_agents(agent_type=AgentType.WORKER)
        return [w for w in workers if capability in w.capabilities]

    async def cleanup_stale_agents(self) -> int:
        """
        Remove agents that haven't sent heartbeats within timeout.

        Returns:
            Number of agents cleaned up
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        agents = await self.list_agents()
        stale_count = 0
        cutoff = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout)

        for agent in agents:
            if agent.last_heartbeat < cutoff:
                logger.warning(
                    f"Cleaning up stale agent {agent.agent_id} "
                    f"(last heartbeat: {agent.last_heartbeat})"
                )
                await self.deregister(agent.agent_id)
                stale_count += 1

        if stale_count:
            logger.info(f"Cleaned up {stale_count} stale agents")

        return stale_count
