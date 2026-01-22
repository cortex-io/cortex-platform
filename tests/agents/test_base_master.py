"""Tests for BaseMaster class."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.base_master import BaseMaster
from agents.messaging import AgentMessage


class TestMaster(BaseMaster):
    """Concrete master for testing."""

    def get_capabilities(self):
        return ["test_routing"]

    async def route_task(self, message):
        # Simple routing: if task_type contains "worker", route to worker-001
        if "worker" in message.task_type:
            return "worker-001"
        return None

    async def process_result(self, message):
        # Just log the result
        pass


@pytest.mark.asyncio
class TestBaseMaster:
    """Test BaseMaster functionality."""

    async def test_master_initialization(self, redis_url):
        """Test master initialization."""
        master = TestMaster(
            agent_id="test-master-001",
            name="Test Master",
            redis_url=redis_url,
        )

        assert master.agent_id == "test-master-001"
        assert master.name == "Test Master"
        assert master.task_stream == "agent:tasks:test-master-001"

    async def test_master_capabilities(self):
        """Test getting master capabilities."""
        master = TestMaster(
            agent_id="test-master",
            name="Test",
        )

        capabilities = master.get_capabilities()
        assert "test_routing" in capabilities

    async def test_route_task(self):
        """Test task routing logic."""
        master = TestMaster(
            agent_id="test-master",
            name="Test",
        )

        # Message that should route to worker
        msg1 = AgentMessage(
            stream="test:stream",
            sender="client",
            recipient="test-master",
            task_type="worker_task",
            payload={},
        )

        worker_id = await master.route_task(msg1)
        assert worker_id == "worker-001"

        # Message that master should handle
        msg2 = AgentMessage(
            stream="test:stream",
            sender="client",
            recipient="test-master",
            task_type="master_task",
            payload={},
        )

        worker_id = await master.route_task(msg2)
        assert worker_id is None

    async def test_find_available_worker(self, redis_url):
        """Test finding available worker."""
        master = TestMaster(
            agent_id="test-master",
            name="Test",
            redis_url=redis_url,
        )

        # Connect registry
        await master.registry.connect()

        # Register a worker with test capability
        from agents.registry import AgentInfo, AgentType, AgentStatus

        worker_info = AgentInfo(
            agent_id="test-worker-001",
            agent_type=AgentType.WORKER,
            name="Test Worker",
            status=AgentStatus.READY,
            capabilities=["test_capability"],
            stream="agent:tasks:test-worker-001",
        )
        await master.registry.register(worker_info)

        # Find worker
        worker_id = await master.find_available_worker("test_capability")
        assert worker_id == "test-worker-001"

        # Try to find non-existent capability
        worker_id = await master.find_available_worker("nonexistent")
        assert worker_id is None

        await master.registry.disconnect()
