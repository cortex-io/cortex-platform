"""
Redis Client

Provides access to agent framework via Redis Streams and Registry.
"""

import os
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class AgentStatus(str, Enum):
    """Agent status states."""
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"


class AgentType(str, Enum):
    """Agent types."""
    MASTER = "master"
    WORKER = "worker"


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    agent_id: str
    agent_type: AgentType
    status: AgentStatus
    capabilities: list[str]
    stream: str
    task_count: int
    last_heartbeat: datetime
    metadata: dict[str, Any]


@dataclass
class TaskMessage:
    """A task message for an agent."""
    task_id: str
    sender: str
    recipient: str
    task_type: str
    payload: dict[str, Any]
    priority: int = 1
    timestamp: Optional[datetime] = None


@dataclass
class TaskResult:
    """Result from an agent task."""
    task_id: str
    success: bool
    result: Any
    error: Optional[str]
    duration_ms: int


class RedisClient:
    """Redis client for agent framework integration."""

    REGISTRY_PREFIX = "cortex:agent:registry:"
    STREAM_PREFIX = "cortex:agent:stream:"
    RESULT_PREFIX = "cortex:agent:result:"

    def __init__(
        self,
        url: Optional[str] = None,
    ):
        self.url = url or os.getenv(
            "REDIS_URL",
            "redis://redis.cortex-system:6379"
        )
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.url, decode_responses=True)
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            r = await self._get_redis()
            await r.ping()
            return True
        except Exception:
            return False

    # =========================================================================
    # Agent Registry
    # =========================================================================

    async def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        capability: Optional[str] = None,
    ) -> list[AgentInfo]:
        """
        List registered agents.

        Args:
            agent_type: Filter by agent type (master/worker)
            capability: Filter by capability

        Returns:
            List of agent info
        """
        r = await self._get_redis()

        try:
            # Scan for all agent registry keys
            agents = []
            async for key in r.scan_iter(f"{self.REGISTRY_PREFIX}*"):
                data = await r.hgetall(key)
                if not data:
                    continue

                info = AgentInfo(
                    agent_id=data.get("agent_id", ""),
                    agent_type=AgentType(data.get("agent_type", "worker")),
                    status=AgentStatus(data.get("status", "unknown")),
                    capabilities=json.loads(data.get("capabilities", "[]")),
                    stream=data.get("stream", ""),
                    task_count=int(data.get("task_count", 0)),
                    last_heartbeat=datetime.fromisoformat(
                        data.get("last_heartbeat", datetime.utcnow().isoformat())
                    ),
                    metadata=json.loads(data.get("metadata", "{}")),
                )

                # Apply filters
                if agent_type and info.agent_type != agent_type:
                    continue
                if capability and capability not in info.capabilities:
                    continue

                agents.append(info)

            return agents

        except Exception as e:
            logger.error("redis_list_agents_error", error=str(e))
            return []

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get info for a specific agent."""
        r = await self._get_redis()

        try:
            data = await r.hgetall(f"{self.REGISTRY_PREFIX}{agent_id}")
            if not data:
                return None

            return AgentInfo(
                agent_id=data.get("agent_id", agent_id),
                agent_type=AgentType(data.get("agent_type", "worker")),
                status=AgentStatus(data.get("status", "unknown")),
                capabilities=json.loads(data.get("capabilities", "[]")),
                stream=data.get("stream", ""),
                task_count=int(data.get("task_count", 0)),
                last_heartbeat=datetime.fromisoformat(
                    data.get("last_heartbeat", datetime.utcnow().isoformat())
                ),
                metadata=json.loads(data.get("metadata", "{}")),
            )

        except Exception as e:
            logger.error("redis_get_agent_error", error=str(e), agent_id=agent_id)
            return None

    async def find_available_worker(
        self,
        capability: str,
    ) -> Optional[AgentInfo]:
        """
        Find an available worker with the specified capability.

        Args:
            capability: Required capability

        Returns:
            AgentInfo if found, None otherwise
        """
        agents = await self.list_agents(
            agent_type=AgentType.WORKER,
            capability=capability,
        )

        # Prefer idle agents, then ready
        for status_priority in [AgentStatus.IDLE, AgentStatus.READY]:
            for agent in agents:
                if agent.status == status_priority:
                    return agent

        return None

    # =========================================================================
    # Task Messaging
    # =========================================================================

    async def submit_task(
        self,
        agent_id: str,
        task_type: str,
        payload: dict[str, Any],
        priority: int = 1,
    ) -> str:
        """
        Submit a task to an agent.

        Args:
            agent_id: Target agent ID
            task_type: Type of task
            payload: Task payload
            priority: Task priority (1=normal, 2=high, 3=urgent)

        Returns:
            Task ID
        """
        r = await self._get_redis()

        task_id = str(uuid4())
        stream = f"{self.STREAM_PREFIX}{agent_id}"

        message = TaskMessage(
            task_id=task_id,
            sender="cortex-unified-mcp",
            recipient=agent_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            timestamp=datetime.utcnow(),
        )

        try:
            # Publish to agent's stream
            await r.xadd(
                stream,
                {
                    "task_id": message.task_id,
                    "sender": message.sender,
                    "recipient": message.recipient,
                    "task_type": message.task_type,
                    "payload": json.dumps(message.payload),
                    "priority": str(message.priority),
                    "timestamp": message.timestamp.isoformat(),
                },
            )

            logger.info(
                "task_submitted",
                task_id=task_id,
                agent_id=agent_id,
                task_type=task_type,
            )

            return task_id

        except Exception as e:
            logger.error(
                "redis_submit_task_error",
                error=str(e),
                agent_id=agent_id,
            )
            raise

    async def get_task_result(
        self,
        task_id: str,
        timeout: float = 60.0,
    ) -> Optional[TaskResult]:
        """
        Wait for and retrieve a task result.

        Args:
            task_id: Task ID to wait for
            timeout: Maximum wait time in seconds

        Returns:
            TaskResult if completed, None if timeout
        """
        r = await self._get_redis()
        result_key = f"{self.RESULT_PREFIX}{task_id}"

        try:
            # Use BLPOP with timeout for blocking wait
            result = await r.blpop(result_key, timeout=int(timeout))

            if result is None:
                return None

            _, data = result
            result_data = json.loads(data)

            return TaskResult(
                task_id=task_id,
                success=result_data.get("success", False),
                result=result_data.get("result"),
                error=result_data.get("error"),
                duration_ms=result_data.get("duration_ms", 0),
            )

        except Exception as e:
            logger.error("redis_get_result_error", error=str(e), task_id=task_id)
            return None

    async def submit_task_and_wait(
        self,
        agent_id: str,
        task_type: str,
        payload: dict[str, Any],
        timeout: float = 60.0,
    ) -> TaskResult:
        """
        Submit a task and wait for the result.

        Args:
            agent_id: Target agent ID
            task_type: Type of task
            payload: Task payload
            timeout: Maximum wait time

        Returns:
            TaskResult
        """
        task_id = await self.submit_task(agent_id, task_type, payload)
        result = await self.get_task_result(task_id, timeout)

        if result is None:
            return TaskResult(
                task_id=task_id,
                success=False,
                result=None,
                error=f"Task timed out after {timeout}s",
                duration_ms=int(timeout * 1000),
            )

        return result
