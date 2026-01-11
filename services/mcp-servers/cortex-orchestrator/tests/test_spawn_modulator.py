"""Tests for SpawnModulator."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from server.spawn_modulator import SpawnModulator
from server.models import AgentSpec, SpawnStatus


@pytest.fixture
def mock_awareness():
    """Mock awareness client."""
    awareness = AsyncMock()
    awareness.call_tool = AsyncMock()
    return awareness


@pytest.fixture
def modulator(mock_awareness):
    """Create modulator instance."""
    config = {
        "base_spawn_rate": 10,
        "max_pending_queue": 100,
    }
    return SpawnModulator(mock_awareness, config)


@pytest.mark.asyncio
async def test_calculate_spawn_rate_healthy(modulator, mock_awareness):
    """Test spawn rate calculation with healthy cluster."""
    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {
            "allocatable_cpu_percent": 50,
        },
        # get_sibling_pods (pending count)
        [{"phase": "Running"}] * 10,  # 0 pending
        # get_self_state (API latency)
        {}
    ]

    rate = await modulator.calculate_spawn_rate()

    # All factors at 1.0:
    # - CPU: min(50/30, 1.0) = 1.0
    # - Pending: max(1.0 - (0/50), 0.1) = 1.0
    # - Failures: 1.0 (no recent failures)
    # - API: 1.0 (latency normal)
    # Rate: 10 * 1.0 * 1.0 * 1.0 * 1.0 = 10.0
    assert rate == 10.0


@pytest.mark.asyncio
async def test_calculate_spawn_rate_low_cpu(modulator, mock_awareness):
    """Test spawn rate throttling with low CPU headroom."""
    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {
            "allocatable_cpu_percent": 15,  # Low headroom
        },
        # get_sibling_pods
        [],
        # get_self_state
        {}
    ]

    rate = await modulator.calculate_spawn_rate()

    # CPU factor: min(15/30, 1.0) = 0.5
    # Rate: 10 * 0.5 * 1.0 * 1.0 * 1.0 = 5.0
    assert rate == 5.0


@pytest.mark.asyncio
async def test_calculate_spawn_rate_high_pending(modulator, mock_awareness):
    """Test spawn rate throttling with high pending pod count."""
    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {
            "allocatable_cpu_percent": 50,
        },
        # get_sibling_pods (40 pending)
        [{"phase": "Pending"}] * 40,
        # get_self_state
        {}
    ]

    rate = await modulator.calculate_spawn_rate()

    # Pending factor: max(1.0 - (40/50), 0.1) = 0.2
    # Rate: 10 * 1.0 * 0.2 * 1.0 * 1.0 = 2.0
    assert rate == 2.0


@pytest.mark.asyncio
async def test_calculate_spawn_rate_with_failures(modulator, mock_awareness):
    """Test spawn rate throttling after failures."""
    # Record 3 failures
    for _ in range(3):
        modulator.record_spawn_failure()

    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {"allocatable_cpu_percent": 50},
        # get_sibling_pods
        [],
        # get_self_state
        {}
    ]

    rate = await modulator.calculate_spawn_rate()

    # Failure factor: 0.7 (1-4 failures)
    # Rate: 10 * 1.0 * 1.0 * 0.7 * 1.0 = 7.0
    assert rate == 7.0


@pytest.mark.asyncio
async def test_calculate_spawn_rate_with_many_failures(modulator, mock_awareness):
    """Test aggressive throttling after many failures."""
    # Record 10 failures
    for _ in range(10):
        modulator.record_spawn_failure()

    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]

    rate = await modulator.calculate_spawn_rate()

    # Failure factor: 0.3 (5+ failures = aggressive)
    # Rate: 10 * 1.0 * 1.0 * 0.3 * 1.0 = 3.0
    assert rate == 3.0


@pytest.mark.asyncio
async def test_calculate_spawn_rate_floor(modulator, mock_awareness):
    """Test that spawn rate never goes below 0.5 pods/sec."""
    # Simulate worst-case scenario
    for _ in range(10):
        modulator.record_spawn_failure()

    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 5},  # Very low
        [{"phase": "Pending"}] * 60,  # Many pending
        {}  # Will have high latency from recent failures
    ]

    rate = await modulator.calculate_spawn_rate()

    # Even with all factors at minimum, rate should be >= 0.5
    assert rate >= 0.5


@pytest.mark.asyncio
async def test_request_spawn_approved(modulator, mock_awareness):
    """Test spawn request approval."""
    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]

    spec = AgentSpec(
        agent_type="test_agent",
        task_id="task-123",
        priority=5
    )

    decision = await modulator.request_spawn(spec)

    assert decision.approved is True
    assert decision.status == SpawnStatus.QUEUED
    assert decision.current_rate == 10.0
    assert decision.queue_position == 1


@pytest.mark.asyncio
async def test_request_spawn_queue_saturated(modulator, mock_awareness):
    """Test spawn rejection when queue is full."""
    # Fill queue to max
    for i in range(100):
        spec = AgentSpec(agent_type="test", task_id=f"task-{i}", priority=5)
        await modulator.spawn_queue.put((5, spec))

    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]

    spec = AgentSpec(agent_type="test", task_id="task-overflow", priority=5)
    decision = await modulator.request_spawn(spec)

    assert decision.approved is False
    assert decision.status == SpawnStatus.REJECTED
    assert "saturated" in decision.reason


@pytest.mark.asyncio
async def test_request_spawn_throttled(modulator, mock_awareness):
    """Test spawn throttling when wait time is long."""
    # Slow down rate significantly
    for _ in range(10):
        modulator.record_spawn_failure()

    # Add items to queue
    for i in range(50):
        spec = AgentSpec(agent_type="test", task_id=f"task-{i}", priority=5)
        await modulator.spawn_queue.put((5, spec))

    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 10},
        [{"phase": "Pending"}] * 40,
        {}
    ]

    spec = AgentSpec(agent_type="test", task_id="task-new", priority=5)
    decision = await modulator.request_spawn(spec)

    # With very low rate and 50 in queue, wait time will exceed 30s
    assert decision.status == SpawnStatus.THROTTLED


@pytest.mark.asyncio
async def test_pause_and_resume_spawning(modulator, mock_awareness):
    """Test emergency pause and resume."""
    await modulator.pause_spawning("Emergency maintenance")

    assert modulator.current_rate == 0.0
    assert len(modulator.backpressure_signals) == 1
    assert modulator.backpressure_signals[0].name == "manual_pause"

    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]

    await modulator.resume_spawning()
    assert modulator.current_rate > 0.0


def test_get_backpressure_status(modulator):
    """Test getting backpressure status."""
    signals = modulator.get_backpressure_status()
    assert isinstance(signals, list)


def test_get_queue_depth(modulator):
    """Test queue depth reporting."""
    depth = modulator.get_queue_depth()
    assert depth == 0


@pytest.mark.asyncio
async def test_priority_calculation_replacement(modulator, mock_awareness):
    """Test that replacement spawns get priority boost."""
    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]

    # Regular spawn
    spec1 = AgentSpec(agent_type="test", task_id="task-1", priority=5)
    await modulator.request_spawn(spec1)

    # Replacement spawn (has inherited state)
    spec2 = AgentSpec(
        agent_type="test",
        task_id="task-2",
        priority=5,
        inherited_state={"previous": "state"}
    )

    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]
    await modulator.request_spawn(spec2)

    # Get items from queue
    priority1, _ = await modulator.spawn_queue.get()
    priority2, _ = await modulator.spawn_queue.get()

    # Replacement should have lower priority number (higher priority)
    assert priority2 < priority1


@pytest.mark.asyncio
async def test_priority_calculation_coordinator(modulator, mock_awareness):
    """Test that coordinator agents get priority boost."""
    mock_awareness.call_tool.side_effect = [
        {"allocatable_cpu_percent": 50},
        [],
        {},
        {"allocatable_cpu_percent": 50},
        [],
        {}
    ]

    # Regular agent
    spec1 = AgentSpec(agent_type="test_agent", task_id="task-1", priority=5)
    await modulator.request_spawn(spec1)

    # Coordinator agent
    spec2 = AgentSpec(agent_type="coordinator_master", task_id="task-2", priority=5)
    await modulator.request_spawn(spec2)

    priority1, _ = await modulator.spawn_queue.get()
    priority2, _ = await modulator.spawn_queue.get()

    # Coordinator should have lower priority number (higher priority)
    assert priority2 < priority1
