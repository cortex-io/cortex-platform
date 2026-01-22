"""Tests for messaging layer (Redis Streams)."""

import pytest
from datetime import datetime

from agents.messaging import AgentMessage, MessageBroker, MessagePriority


class TestAgentMessage:
    """Test AgentMessage serialization and deserialization."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = AgentMessage(
            stream="test:stream",
            sender="agent-1",
            recipient="agent-2",
            task_type="test_task",
            payload={"key": "value"},
            priority=MessagePriority.HIGH,
        )

        assert msg.sender == "agent-1"
        assert msg.recipient == "agent-2"
        assert msg.task_type == "test_task"
        assert msg.priority == MessagePriority.HIGH

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = AgentMessage(
            stream="test:stream",
            sender="agent-1",
            recipient="agent-2",
            task_type="test_task",
            payload={"key": "value"},
        )

        data = msg.to_dict()
        assert data["sender"] == "agent-1"
        assert data["recipient"] == "agent-2"
        assert data["task_type"] == "test_task"
        assert "payload" in data

    def test_message_from_redis(self):
        """Test message deserialization from Redis."""
        redis_data = {
            b"sender": b"agent-1",
            b"recipient": b"agent-2",
            b"task_type": b"test_task",
            b"payload": b'{"key": "value"}',
            b"priority": b"normal",
            b"timestamp": datetime.utcnow().isoformat().encode(),
            b"metadata": b"{}",
        }

        msg = AgentMessage.from_redis("msg-001", redis_data)
        assert msg.sender == "agent-1"
        assert msg.recipient == "agent-2"
        assert msg.payload == {"key": "value"}


@pytest.mark.asyncio
class TestMessageBroker:
    """Test MessageBroker Redis Streams operations."""

    async def test_broker_connect(self, redis_url):
        """Test connecting to Redis."""
        broker = MessageBroker(redis_url=redis_url)
        await broker.connect()
        assert broker._client is not None
        await broker.disconnect()

    async def test_publish_message(self, redis_url):
        """Test publishing a message."""
        broker = MessageBroker(redis_url=redis_url)
        await broker.connect()

        msg = AgentMessage(
            stream="test:stream",
            sender="agent-1",
            recipient="agent-2",
            task_type="test_task",
            payload={"data": "test"},
        )

        message_id = await broker.publish(msg)
        assert message_id is not None
        assert msg.message_id == message_id

        await broker.disconnect()

    async def test_create_consumer_group(self, redis_url):
        """Test creating consumer group."""
        broker = MessageBroker(redis_url=redis_url)
        await broker.connect()

        created = await broker.create_consumer_group("test:stream", "test-group")
        assert created is True

        # Second call should return False (already exists)
        created_again = await broker.create_consumer_group("test:stream", "test-group")
        assert created_again is False

        await broker.disconnect()

    async def test_publish_and_consume(self, redis_url):
        """Test publishing and consuming messages."""
        broker = MessageBroker(redis_url=redis_url)
        await broker.connect()

        # Publish a message
        msg = AgentMessage(
            stream="test:stream",
            sender="agent-1",
            recipient="agent-2",
            task_type="test_task",
            payload={"data": "test"},
        )
        await broker.publish(msg)

        # Consume the message
        messages = []
        async for received_msg in broker.consume(
            "test:stream",
            "test-group",
            "consumer-1",
            count=1,
            auto_ack=True,
        ):
            messages.append(received_msg)
            break  # Only get one message

        assert len(messages) == 1
        assert messages[0].sender == "agent-1"
        assert messages[0].task_type == "test_task"

        await broker.disconnect()
