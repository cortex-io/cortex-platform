"""Tests for DynamicPodLimiter."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from server.dynamic_limiter import DynamicPodLimiter
from server.models import ResourceProfile


@pytest.fixture
def mock_awareness():
    """Mock awareness client."""
    awareness = AsyncMock()
    awareness.call_tool = AsyncMock()
    return awareness


@pytest.fixture
def limiter(mock_awareness):
    """Create limiter instance."""
    config = {
        "cpu_headroom_percent": 30,
        "memory_headroom_percent": 30,
        "absolute_min_pods": 5,
        "absolute_max_pods": 500,
        "agent_profiles": {
            "test_agent": ResourceProfile(cpu_millicores=200, memory_mb=256)
        }
    }
    return DynamicPodLimiter(mock_awareness, config)


@pytest.mark.asyncio
async def test_calculate_current_limit_cpu_constrained(limiter, mock_awareness):
    """Test limit calculation when CPU is limiting resource."""
    # Mock cluster state
    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {
            "total_allocatable_cpu_millicores": 8000,
            "total_allocatable_memory_mb": 32768,
            "available_cpu_millicores": 4000,
            "available_memory_mb": 16384,
        },
        # get_sibling_pods (current count)
        [
            {"phase": "Running", "cpu_millicores": 200, "memory_mb": 256},
            {"phase": "Running", "cpu_millicores": 200, "memory_mb": 256},
        ],
        # get_sibling_pods (for average calculation)
        [
            {"phase": "Running", "cpu_millicores": 200, "memory_mb": 256},
            {"phase": "Running", "cpu_millicores": 200, "memory_mb": 256},
        ],
        # get_sibling_pods (for memory average)
        [
            {"phase": "Running", "cpu_millicores": 200, "memory_mb": 256},
            {"phase": "Running", "cpu_millicores": 200, "memory_mb": 256},
        ],
        # get_recent_events (for stability)
        []
    ]

    limit = await limiter.calculate_current_limit()

    # Usable CPU: 8000 * 0.7 = 5600
    # Average CPU: 200
    # CPU limit: 5600 / 200 = 28
    # Usable memory: 32768 * 0.7 = 22937
    # Average memory: 256
    # Memory limit: 22937 / 256 = 89
    # Limiting resource: CPU (28 < 89)

    assert limit.current_count == 2
    assert limit.calculated_limit == 28
    assert limit.limiting_resource == "cpu"
    assert limit.headroom == 26
    assert limit.can_scale_up is True
    assert limit.stability_factor == 1.0


@pytest.mark.asyncio
async def test_calculate_current_limit_memory_constrained(limiter, mock_awareness):
    """Test limit calculation when memory is limiting resource."""
    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {
            "total_allocatable_cpu_millicores": 8000,
            "total_allocatable_memory_mb": 4096,  # Low memory
            "available_cpu_millicores": 4000,
            "available_memory_mb": 2048,
        },
        # get_sibling_pods (current count)
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        # get_sibling_pods (for average calculation)
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        # get_sibling_pods (for memory average)
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        # get_recent_events (for stability)
        []
    ]

    limit = await limiter.calculate_current_limit()

    # Usable memory: 4096 * 0.7 = 2867
    # Average memory: 256
    # Memory limit: 2867 / 256 = 11
    # Limiting resource: memory

    assert limit.limiting_resource == "memory"
    assert limit.calculated_limit == 11


@pytest.mark.asyncio
async def test_calculate_current_limit_with_instability(limiter, mock_awareness):
    """Test limit reduction during cluster instability."""
    mock_awareness.call_tool.side_effect = [
        # get_cluster_capacity
        {
            "total_allocatable_cpu_millicores": 8000,
            "total_allocatable_memory_mb": 16384,
        },
        # get_sibling_pods (current count)
        [],
        # get_sibling_pods (for average calculation)
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        # get_sibling_pods (for memory average)
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        # get_recent_events (10 errors = low stability)
        [{"type": "Warning"}] * 10
    ]

    limit = await limiter.calculate_current_limit()

    # Stability should be 1.0 - (10 * 0.05) = 0.5
    # This triggers 20% reduction
    assert limit.stability_factor == 0.5


@pytest.mark.asyncio
async def test_should_allow_spawn_approved(limiter, mock_awareness):
    """Test spawn approval when resources available."""
    mock_awareness.call_tool.side_effect = [
        # calculate_current_limit calls
        {"total_allocatable_cpu_millicores": 8000, "total_allocatable_memory_mb": 16384},
        [],  # get_sibling_pods
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        [],  # get_recent_events
        # get_cluster_capacity for resource check
        {
            "available_cpu_millicores": 4000,
            "available_memory_mb": 8192,
        }
    ]

    allowed, reason = await limiter.should_allow_spawn("test_agent")

    assert allowed is True
    assert reason == "approved"


@pytest.mark.asyncio
async def test_should_allow_spawn_at_limit(limiter, mock_awareness):
    """Test spawn rejection when at capacity."""
    # Mock that we're at the limit
    mock_awareness.call_tool.side_effect = [
        # calculate_current_limit
        {"total_allocatable_cpu_millicores": 400, "total_allocatable_memory_mb": 512},  # Very small
        [{"phase": "Running"}] * 1,  # 1 pod running
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        [],  # get_recent_events
    ]

    allowed, reason = await limiter.should_allow_spawn("test_agent")

    assert allowed is False
    assert reason == "at_dynamic_limit"


@pytest.mark.asyncio
async def test_should_allow_spawn_insufficient_cpu(limiter, mock_awareness):
    """Test spawn rejection when CPU insufficient."""
    mock_awareness.call_tool.side_effect = [
        # calculate_current_limit
        {"total_allocatable_cpu_millicores": 8000, "total_allocatable_memory_mb": 16384},
        [],
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        [{"phase": "Running", "cpu_millicores": 200, "memory_mb": 256}],
        [],
        # get_cluster_capacity for resource check
        {
            "available_cpu_millicores": 100,  # Not enough (need 240 = 200 * 1.2)
            "available_memory_mb": 8192,
        }
    ]

    allowed, reason = await limiter.should_allow_spawn("test_agent")

    assert allowed is False
    assert reason == "insufficient_cpu"


@pytest.mark.asyncio
async def test_set_resource_profile(limiter):
    """Test updating resource profile."""
    limiter.set_resource_profile("new_agent", 500, 1024)

    profile = limiter.get_resource_profile("new_agent")
    assert profile.cpu_millicores == 500
    assert profile.memory_mb == 1024


def test_get_resource_profile_default(limiter):
    """Test getting default profile for unknown agent."""
    profile = limiter.get_resource_profile("unknown_agent")
    assert profile.cpu_millicores == 200
    assert profile.memory_mb == 256
