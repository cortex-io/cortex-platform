"""
Cortex Platform Integration for UniFi Layer Fabric

Integrates the Layer Fabric with Cortex's Redis Streams messaging
and agent registry. The Activator acts as a "worker" from Cortex's
perspective, receiving tasks via Redis Streams and managing its own
internal layers via HTTP.

Architecture:
    Cortex Master
         │
         │ Redis Streams (cortex.network.*)
         ▼
    UniFi Activator (this) ─── registers as worker
         │
         │ Internal HTTP
         ▼
    Layers (reasoning, execution, memory, telemetry)
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import redis.asyncio as redis
import structlog


log = structlog.get_logger()


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class CortexConfig:
    """Configuration for Cortex integration."""
    redis_url: str = "redis://redis.cortex-system.svc.cluster.local:6379"
    agent_id: str = field(default_factory=lambda: f"unifi-fabric-{uuid.uuid4().hex[:8]}")
    agent_name: str = "unifi-layer-fabric"

    # Streams
    task_stream: str = "cortex.network.tasks"
    result_stream: str = "cortex.results"
    consumer_group: str = "unifi-fabric-group"

    # Registry
    registry_prefix: str = "cortex:agents"
    heartbeat_interval: int = 30
    heartbeat_timeout: int = 120

    # Capabilities this fabric provides
    capabilities: List[str] = field(default_factory=lambda: [
        "unifi_network",
        "client_management",
        "device_management",
        "network_diagnostics",
        "firewall_management",
        "wifi_management",
    ])

    @classmethod
    def from_env(cls) -> "CortexConfig":
        """Load configuration from environment variables."""
        return cls(
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            agent_id=os.getenv("AGENT_ID", f"unifi-fabric-{uuid.uuid4().hex[:8]}"),
            agent_name=os.getenv("AGENT_NAME", "unifi-layer-fabric"),
            task_stream=os.getenv("CORTEX_TASK_STREAM", "cortex.network.tasks"),
            result_stream=os.getenv("CORTEX_RESULT_STREAM", "cortex.results"),
            consumer_group=os.getenv("CORTEX_CONSUMER_GROUP", "unifi-fabric-group"),
            heartbeat_interval=int(os.getenv("HEARTBEAT_INTERVAL", "30")),
        )


# =============================================================================
# Message Types
# =============================================================================

class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CortexMessage:
    """Message format for Cortex Redis Streams."""
    stream: str
    sender: str
    recipient: str
    task_type: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    message_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        """Convert to Redis-compatible dictionary."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "task_type": self.task_type,
            "payload": json.dumps(self.payload),
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_redis(cls, message_id: str, data: Dict[bytes, bytes], stream: str = "") -> "CortexMessage":
        """Create from Redis stream entry."""
        decoded = {k.decode() if isinstance(k, bytes) else k:
                   v.decode() if isinstance(v, bytes) else v
                   for k, v in data.items()}
        return cls(
            message_id=message_id,
            stream=stream,
            sender=decoded["sender"],
            recipient=decoded["recipient"],
            task_type=decoded["task_type"],
            payload=json.loads(decoded["payload"]),
            priority=MessagePriority(decoded.get("priority", "normal")),
            timestamp=datetime.fromisoformat(decoded["timestamp"]),
            metadata=json.loads(decoded.get("metadata", "{}")),
        )


class AgentStatus(str, Enum):
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"


# =============================================================================
# Cortex Integration Client
# =============================================================================

class CortexClient:
    """
    Client for integrating with Cortex platform.

    Handles:
    - Redis connection management
    - Agent registration and heartbeats
    - Message consumption from task streams
    - Result publishing to result streams
    """

    def __init__(self, config: CortexConfig):
        self.config = config
        self._client: Optional[redis.Redis] = None
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._consume_task: Optional[asyncio.Task] = None
        self._task_handler: Optional[Callable] = None
        self._status = AgentStatus.STARTING

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._client is None:
            self._client = await redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=False
            )
            log.info("cortex_connected", redis_url=self.config.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            log.info("cortex_disconnected")

    # -------------------------------------------------------------------------
    # Agent Registry
    # -------------------------------------------------------------------------

    async def register(self) -> bool:
        """Register this fabric as a Cortex agent."""
        if not self._client:
            raise RuntimeError("Not connected to Redis")

        key = f"{self.config.registry_prefix}:{self.config.agent_id}"

        agent_data = {
            "agent_id": self.config.agent_id,
            "agent_type": "worker",  # Fabric acts as a worker
            "name": self.config.agent_name,
            "status": self._status.value,
            "capabilities": ",".join(self.config.capabilities),
            "stream": self.config.task_stream,
            "metadata": json.dumps({"fabric_type": "unifi-layer-fabric"}),
            "registered_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow().isoformat(),
            "task_count": "0",
            "version": "0.1.0",
        }

        await self._client.hset(key, mapping=agent_data)
        await self._client.expire(key, self.config.heartbeat_timeout * 2)

        # Add to type set
        type_set = f"{self.config.registry_prefix}:type:worker"
        await self._client.sadd(type_set, self.config.agent_id)

        # Add to status set
        status_set = f"{self.config.registry_prefix}:status:{self._status.value}"
        await self._client.sadd(status_set, self.config.agent_id)

        log.info(
            "cortex_registered",
            agent_id=self.config.agent_id,
            capabilities=self.config.capabilities
        )
        return True

    async def deregister(self) -> bool:
        """Deregister from Cortex."""
        if not self._client:
            return False

        key = f"{self.config.registry_prefix}:{self.config.agent_id}"

        # Remove from sets
        type_set = f"{self.config.registry_prefix}:type:worker"
        await self._client.srem(type_set, self.config.agent_id)

        status_set = f"{self.config.registry_prefix}:status:{self._status.value}"
        await self._client.srem(status_set, self.config.agent_id)

        # Delete agent key
        await self._client.delete(key)

        log.info("cortex_deregistered", agent_id=self.config.agent_id)
        return True

    async def update_status(self, status: AgentStatus) -> None:
        """Update agent status in registry."""
        if not self._client:
            return

        key = f"{self.config.registry_prefix}:{self.config.agent_id}"

        # Remove from old status set
        old_status_set = f"{self.config.registry_prefix}:status:{self._status.value}"
        await self._client.srem(old_status_set, self.config.agent_id)

        # Add to new status set
        new_status_set = f"{self.config.registry_prefix}:status:{status.value}"
        await self._client.sadd(new_status_set, self.config.agent_id)

        # Update in hash
        await self._client.hset(key, "status", status.value)

        self._status = status
        log.debug("cortex_status_updated", status=status.value)

    async def heartbeat(self) -> None:
        """Send heartbeat to registry."""
        if not self._client:
            return

        key = f"{self.config.registry_prefix}:{self.config.agent_id}"
        await self._client.hset(key, "last_heartbeat", datetime.utcnow().isoformat())
        await self._client.expire(key, self.config.heartbeat_timeout * 2)
        log.debug("cortex_heartbeat_sent")

    async def increment_task_count(self) -> int:
        """Increment task count."""
        if not self._client:
            return 0
        key = f"{self.config.registry_prefix}:{self.config.agent_id}"
        return await self._client.hincrby(key, "task_count", 1)

    # -------------------------------------------------------------------------
    # Message Handling
    # -------------------------------------------------------------------------

    async def create_consumer_group(self) -> bool:
        """Create consumer group for task stream."""
        if not self._client:
            raise RuntimeError("Not connected to Redis")

        try:
            await self._client.xgroup_create(
                self.config.task_stream,
                self.config.consumer_group,
                id="$",
                mkstream=True
            )
            log.info(
                "cortex_consumer_group_created",
                stream=self.config.task_stream,
                group=self.config.consumer_group
            )
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                log.debug("cortex_consumer_group_exists", group=self.config.consumer_group)
                return False
            raise

    async def consume_tasks(self, count: int = 10) -> AsyncIterator[CortexMessage]:
        """Consume tasks from the task stream."""
        if not self._client:
            raise RuntimeError("Not connected to Redis")

        consumer_name = f"{self.config.agent_id}-consumer"

        while self._running:
            try:
                result = await self._client.xreadgroup(
                    self.config.consumer_group,
                    consumer_name,
                    {self.config.task_stream: ">"},
                    count=count,
                    block=5000,
                )

                if not result:
                    continue

                for stream_name, messages in result:
                    for message_id, data in messages:
                        msg_id = message_id.decode() if isinstance(message_id, bytes) else message_id
                        try:
                            message = CortexMessage.from_redis(
                                msg_id,
                                data,
                                stream=self.config.task_stream
                            )
                            yield message
                        except Exception as e:
                            log.error("cortex_message_parse_error", error=str(e), message_id=msg_id)

            except asyncio.CancelledError:
                log.info("cortex_consumer_cancelled")
                break
            except Exception as e:
                log.error("cortex_consume_error", error=str(e))
                await asyncio.sleep(1)

    async def ack_message(self, message_id: str) -> None:
        """Acknowledge a processed message."""
        if not self._client:
            return
        await self._client.xack(
            self.config.task_stream,
            self.config.consumer_group,
            message_id
        )

    async def publish_result(
        self,
        original_message: CortexMessage,
        result: Dict[str, Any],
        success: bool,
        layers_activated: List[str] = None,
        latency_ms: int = 0,
    ) -> str:
        """Publish result back to Cortex."""
        if not self._client:
            raise RuntimeError("Not connected to Redis")

        result_message = CortexMessage(
            stream=self.config.result_stream,
            sender=self.config.agent_id,
            recipient=original_message.sender,
            task_type=f"{original_message.task_type}_result",
            payload={
                "success": success,
                "result": result,
                "original_task": original_message.task_type,
                "layers_activated": layers_activated or [],
                "latency_ms": latency_ms,
            },
            priority=original_message.priority,
            metadata={
                "original_message_id": original_message.message_id,
                "fabric": "unifi-layer-fabric",
            },
        )

        message_id = await self._client.xadd(
            self.config.result_stream,
            result_message.to_dict(),
            maxlen=10000,
        )

        log.info(
            "cortex_result_published",
            message_id=message_id,
            success=success,
            latency_ms=latency_ms
        )

        return message_id.decode() if isinstance(message_id, bytes) else message_id

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self, task_handler: Callable) -> None:
        """
        Start the Cortex integration.

        Args:
            task_handler: Async function to handle incoming tasks.
                         Signature: async def handler(message: CortexMessage) -> Dict[str, Any]
        """
        self._task_handler = task_handler
        self._running = True

        # Connect and register
        await self.connect()
        await self.register()
        await self.create_consumer_group()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._consume_task = asyncio.create_task(self._consume_loop())

        # Mark as ready
        await self.update_status(AgentStatus.READY)

        log.info(
            "cortex_integration_started",
            agent_id=self.config.agent_id,
            task_stream=self.config.task_stream
        )

    async def stop(self) -> None:
        """Stop the Cortex integration."""
        log.info("cortex_integration_stopping")
        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._consume_task:
            self._consume_task.cancel()

        # Wait for tasks
        tasks = [t for t in [self._heartbeat_task, self._consume_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Deregister and disconnect
        await self.update_status(AgentStatus.STOPPED)
        await self.deregister()
        await self.disconnect()

        log.info("cortex_integration_stopped")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self._running:
            try:
                await self.heartbeat()
                await asyncio.sleep(self.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("cortex_heartbeat_error", error=str(e))
                await asyncio.sleep(5)

    async def _consume_loop(self) -> None:
        """Consume and process tasks."""
        async for message in self.consume_tasks():
            if not self._running:
                break

            try:
                await self.update_status(AgentStatus.BUSY)

                log.info(
                    "cortex_task_received",
                    task_type=message.task_type,
                    sender=message.sender,
                    message_id=message.message_id
                )

                # Process via handler
                if self._task_handler:
                    result = await self._task_handler(message)

                    # Publish result
                    await self.publish_result(
                        original_message=message,
                        result=result.get("result", {}),
                        success=result.get("success", False),
                        layers_activated=result.get("layers_activated", []),
                        latency_ms=result.get("latency_ms", 0),
                    )

                # Acknowledge
                await self.ack_message(message.message_id)
                await self.increment_task_count()

            except Exception as e:
                log.error(
                    "cortex_task_error",
                    error=str(e),
                    message_id=message.message_id
                )

            finally:
                await self.update_status(AgentStatus.READY)
