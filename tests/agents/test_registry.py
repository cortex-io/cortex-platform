"""Tests for agent registry."""

import pytest
from datetime import datetime

from agents.registry import AgentInfo, AgentRegistry, AgentStatus, AgentType


@pytest.mark.asyncio
class TestAgentRegistry:
    """Test agent registry operations."""

    async def test_registry_connect(self, redis_url):
        """Test connecting to Redis."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()
        assert registry._client is not None
        await registry.disconnect()

    async def test_register_agent(self, redis_url):
        """Test registering an agent."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        agent_info = AgentInfo(
            agent_id="test-agent-001",
            agent_type=AgentType.WORKER,
            name="Test Worker",
            status=AgentStatus.READY,
            capabilities=["test_capability"],
            stream="agent:tasks:test-agent-001",
        )

        success = await registry.register(agent_info)
        assert success is True

        await registry.disconnect()

    async def test_get_agent(self, redis_url):
        """Test retrieving agent info."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        # Register agent
        agent_info = AgentInfo(
            agent_id="test-agent-002",
            agent_type=AgentType.MASTER,
            name="Test Master",
            status=AgentStatus.READY,
            capabilities=["orchestration"],
            stream="agent:tasks:test-agent-002",
        )
        await registry.register(agent_info)

        # Retrieve agent
        retrieved = await registry.get_agent("test-agent-002")
        assert retrieved is not None
        assert retrieved.agent_id == "test-agent-002"
        assert retrieved.name == "Test Master"
        assert retrieved.agent_type == AgentType.MASTER

        await registry.disconnect()

    async def test_update_status(self, redis_url):
        """Test updating agent status."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        # Register agent
        agent_info = AgentInfo(
            agent_id="test-agent-003",
            agent_type=AgentType.WORKER,
            name="Test Worker",
            status=AgentStatus.READY,
            capabilities=["test"],
            stream="agent:tasks:test-agent-003",
        )
        await registry.register(agent_info)

        # Update status
        success = await registry.update_status("test-agent-003", AgentStatus.BUSY)
        assert success is True

        # Verify update
        retrieved = await registry.get_agent("test-agent-003")
        assert retrieved.status == AgentStatus.BUSY

        await registry.disconnect()

    async def test_heartbeat(self, redis_url):
        """Test agent heartbeat."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        # Register agent
        agent_info = AgentInfo(
            agent_id="test-agent-004",
            agent_type=AgentType.WORKER,
            name="Test Worker",
            status=AgentStatus.READY,
            capabilities=["test"],
            stream="agent:tasks:test-agent-004",
        )
        await registry.register(agent_info)

        # Send heartbeat
        import asyncio
        await asyncio.sleep(1)  # Wait a bit
        success = await registry.heartbeat("test-agent-004")
        assert success is True

        await registry.disconnect()

    async def test_list_agents(self, redis_url):
        """Test listing agents."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        # Register multiple agents
        for i in range(3):
            agent_info = AgentInfo(
                agent_id=f"test-agent-{i}",
                agent_type=AgentType.WORKER if i % 2 == 0 else AgentType.MASTER,
                name=f"Test Agent {i}",
                status=AgentStatus.READY,
                capabilities=["test"],
                stream=f"agent:tasks:test-agent-{i}",
            )
            await registry.register(agent_info)

        # List all agents
        all_agents = await registry.list_agents()
        assert len(all_agents) >= 3

        # List workers only
        workers = await registry.list_agents(agent_type=AgentType.WORKER)
        assert len(workers) >= 2

        # List masters only
        masters = await registry.list_agents(agent_type=AgentType.MASTER)
        assert len(masters) >= 1

        await registry.disconnect()

    async def test_find_workers_by_capability(self, redis_url):
        """Test finding workers by capability."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        # Register workers with different capabilities
        agent1 = AgentInfo(
            agent_id="worker-sandfly",
            agent_type=AgentType.WORKER,
            name="Sandfly Worker",
            status=AgentStatus.READY,
            capabilities=["sandfly_api", "threat_analysis"],
            stream="agent:tasks:worker-sandfly",
        )
        await registry.register(agent1)

        agent2 = AgentInfo(
            agent_id="worker-github",
            agent_type=AgentType.WORKER,
            name="GitHub Worker",
            status=AgentStatus.READY,
            capabilities=["github_security"],
            stream="agent:tasks:worker-github",
        )
        await registry.register(agent2)

        # Find workers with sandfly_api capability
        sandfly_workers = await registry.find_workers_by_capability("sandfly_api")
        assert len(sandfly_workers) == 1
        assert sandfly_workers[0].agent_id == "worker-sandfly"

        # Find workers with github_security capability
        github_workers = await registry.find_workers_by_capability("github_security")
        assert len(github_workers) == 1
        assert github_workers[0].agent_id == "worker-github"

        await registry.disconnect()

    async def test_deregister_agent(self, redis_url):
        """Test deregistering an agent."""
        registry = AgentRegistry(redis_url=redis_url)
        await registry.connect()

        # Register agent
        agent_info = AgentInfo(
            agent_id="test-agent-deregister",
            agent_type=AgentType.WORKER,
            name="Test Worker",
            status=AgentStatus.READY,
            capabilities=["test"],
            stream="agent:tasks:test-agent-deregister",
        )
        await registry.register(agent_info)

        # Deregister
        success = await registry.deregister("test-agent-deregister")
        assert success is True

        # Verify it's gone
        retrieved = await registry.get_agent("test-agent-deregister")
        assert retrieved is None

        await registry.disconnect()
