"""
Redis Streams-based messaging layer for inter-agent communication.

Provides a clean abstraction over Redis Streams for:
- Publishing messages to agent queues
- Consuming messages from streams
- Consumer groups for load balancing
- Message acknowledgment and retry logic
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

import redis.asyncio as redis


logger = logging.getLogger(__name__)


class MessagePriority(str, Enum):
    """Priority levels for agent messages."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentMessage:
    """
    Represents a message sent between agents.

    Attributes:
        message_id: Unique message identifier (set by Redis)
        stream: Redis stream name (e.g., "agent:tasks:sandfly")
        sender: Agent ID of the sender
        recipient: Target agent ID or pattern
        task_type: Type of task (e.g., "scan_host", "analyze_findings")
        payload: Task-specific data
        priority: Message priority level
        timestamp: Message creation timestamp
        metadata: Additional metadata
    """

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
        """Convert message to Redis-compatible dictionary (strings only)."""
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
    def from_redis(cls, message_id: str, data: Dict[bytes, bytes]) -> "AgentMessage":
        """Create AgentMessage from Redis stream entry."""
        decoded = {k.decode(): v.decode() for k, v in data.items()}
        return cls(
            message_id=message_id,
            stream=decoded.get("stream", ""),
            sender=decoded["sender"],
            recipient=decoded["recipient"],
            task_type=decoded["task_type"],
            payload=json.loads(decoded["payload"]),
            priority=MessagePriority(decoded.get("priority", "normal")),
            timestamp=datetime.fromisoformat(decoded["timestamp"]),
            metadata=json.loads(decoded.get("metadata", "{}")),
        )


class MessageBroker:
    """
    Redis Streams message broker for agent communication.

    Provides async methods for publishing and consuming messages.
    Supports consumer groups for load balancing across multiple workers.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_stream_length: int = 10000,
        block_ms: int = 5000,
    ):
        """
        Initialize message broker.

        Args:
            redis_url: Redis connection URL
            max_stream_length: Maximum messages to keep in each stream (MAXLEN)
            block_ms: Blocking timeout for XREADGROUP (milliseconds)
        """
        self.redis_url = redis_url
        self.max_stream_length = max_stream_length
        self.block_ms = block_ms
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._client is None:
            self._client = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=False
            )
            logger.info(f"Connected to Redis at {self.redis_url}")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Redis")

    async def publish(self, message: AgentMessage) -> str:
        """
        Publish a message to a stream.

        Args:
            message: The message to publish

        Returns:
            Message ID assigned by Redis

        Raises:
            RuntimeError: If not connected to Redis
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        message_id = await self._client.xadd(
            message.stream,
            message.to_dict(),
            maxlen=self.max_stream_length,
            approximate=True,
        )
        message.message_id = message_id.decode() if isinstance(message_id, bytes) else message_id
        logger.debug(f"Published message {message.message_id} to {message.stream}")
        return message.message_id

    async def create_consumer_group(
        self, stream: str, group: str, start_id: str = "0"
    ) -> bool:
        """
        Create a consumer group for a stream.

        Args:
            stream: Stream name
            group: Consumer group name
            start_id: Starting message ID (0 = from beginning, $ = new messages only)

        Returns:
            True if group was created, False if it already exists
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        try:
            await self._client.xgroup_create(stream, group, id=start_id, mkstream=True)
            logger.info(f"Created consumer group '{group}' for stream '{stream}'")
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer group '{group}' already exists for '{stream}'")
                return False
            raise

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        auto_ack: bool = False,
    ) -> AsyncIterator[AgentMessage]:
        """
        Consume messages from a stream using consumer group.

        Args:
            stream: Stream name to consume from
            group: Consumer group name
            consumer: Consumer name (unique within group)
            count: Maximum messages to read per iteration
            auto_ack: Automatically acknowledge messages after yielding

        Yields:
            AgentMessage objects from the stream

        Raises:
            RuntimeError: If not connected to Redis
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        # Ensure consumer group exists
        await self.create_consumer_group(stream, group, start_id="$")

        logger.info(f"Consumer '{consumer}' started consuming from '{stream}' in group '{group}'")

        while True:
            try:
                # Read messages from stream
                result = await self._client.xreadgroup(
                    group,
                    consumer,
                    {stream: ">"},
                    count=count,
                    block=self.block_ms,
                )

                if not result:
                    await asyncio.sleep(0.1)  # Brief pause if no messages
                    continue

                for stream_name, messages in result:
                    for message_id, data in messages:
                        msg_id = message_id.decode() if isinstance(message_id, bytes) else message_id
                        try:
                            message = AgentMessage.from_redis(msg_id, data)
                            message.stream = stream
                            yield message

                            if auto_ack:
                                await self.ack(stream, group, msg_id)
                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                            # Don't ack malformed messages
                            continue

            except asyncio.CancelledError:
                logger.info(f"Consumer '{consumer}' cancelled")
                break
            except Exception as e:
                logger.error(f"Error consuming from stream '{stream}': {e}")
                await asyncio.sleep(1)  # Backoff on error

    async def ack(self, stream: str, group: str, *message_ids: str) -> int:
        """
        Acknowledge message processing.

        Args:
            stream: Stream name
            group: Consumer group name
            message_ids: Message IDs to acknowledge

        Returns:
            Number of messages acknowledged
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        count = await self._client.xack(stream, group, *message_ids)
        logger.debug(f"Acknowledged {count} messages in stream '{stream}'")
        return count

    async def get_pending_messages(
        self, stream: str, group: str, consumer: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pending (unacknowledged) messages for a consumer group.

        Args:
            stream: Stream name
            group: Consumer group name
            consumer: Optional specific consumer name

        Returns:
            List of pending message info dictionaries
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        pending = await self._client.xpending(stream, group)
        return pending

    async def claim_abandoned_messages(
        self, stream: str, group: str, consumer: str, min_idle_time_ms: int = 60000
    ) -> List[AgentMessage]:
        """
        Claim messages that have been pending for too long (abandoned).

        Args:
            stream: Stream name
            group: Consumer group name
            consumer: Consumer name claiming the messages
            min_idle_time_ms: Minimum idle time in milliseconds (default: 60 seconds)

        Returns:
            List of claimed messages
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        # Get pending messages
        pending = await self._client.xpending_range(
            stream, group, "-", "+", count=100
        )

        claimed_messages = []
        for item in pending:
            message_id = item["message_id"]
            idle_time = item["time_since_delivered"]

            if idle_time >= min_idle_time_ms:
                # Claim the message
                result = await self._client.xclaim(
                    stream, group, consumer, min_idle_time_ms, [message_id]
                )
                if result:
                    for msg_id, data in result:
                        msg = AgentMessage.from_redis(
                            msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                            data
                        )
                        msg.stream = stream
                        claimed_messages.append(msg)

        if claimed_messages:
            logger.info(f"Claimed {len(claimed_messages)} abandoned messages")

        return claimed_messages

    async def get_stream_info(self, stream: str) -> Dict[str, Any]:
        """
        Get information about a stream.

        Args:
            stream: Stream name

        Returns:
            Stream info dictionary
        """
        if not self._client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        info = await self._client.xinfo_stream(stream)
        return info
