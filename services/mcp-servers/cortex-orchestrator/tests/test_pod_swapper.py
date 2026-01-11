"""Tests for PodSwapper."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from server.pod_swapper import PodSwapper
from server.models import SwapOutcome, AgentSpec, LivenessState, LivenessSignals, SpawnDecision, SpawnStatus


@pytest.fixture
def mock_detector():
    """Mock stuck pod detector."""
    detector = AsyncMock()
    detector.stuck_timeout = 300
    return detector


@pytest.fixture
def mock_modulator():
    """Mock spawn modulator."""
    modulator = AsyncMock()
    return modulator


@pytest.fixture
def mock_k8s():
    """Mock Kubernetes client."""
    k8s = AsyncMock()
    return k8s


@pytest.fixture
def swapper(mock_detector, mock_modulator, mock_k8s):
    """Create swapper instance."""
    config = {
        "max_swap_retries": 2,
        "grace_period": 10,
    }
    return PodSwapper(mock_detector, mock_modulator, mock_k8s, config)


@pytest.mark.asyncio
async def test_evaluate_and_swap_healthy_pod(swapper, mock_detector):
    """Test that healthy pods are not swapped."""
    # Mock healthy pod
    mock_detector.check_pod_liveness.return_value = LivenessState(
        pod_name="test-pod",
        score=0.9,
        signals=LivenessSignals(
            k8s_ready=True,
            recent_logs=True,
            cpu_activity=True,
            network_activity=True,
            task_progress=True
        ),
        stuck=False,
        stuck_duration=0,
        assessment_time=datetime.utcnow()
    )

    result = await swapper.evaluate_and_swap("test-pod")

    assert result.swapped is False
    assert result.outcome == SwapOutcome.SKIPPED
    assert "healthy" in result.reason


@pytest.mark.asyncio
async def test_evaluate_and_swap_stuck_but_timeout_not_reached(swapper, mock_detector):
    """Test that stuck pods below timeout are not swapped."""
    mock_detector.check_pod_liveness.return_value = LivenessState(
        pod_name="test-pod",
        score=0.3,
        signals=LivenessSignals(
            k8s_ready=True,
            recent_logs=False,
            cpu_activity=False,
            network_activity=True,
            task_progress=False
        ),
        stuck=True,
        stuck_duration=120,  # Only 2 minutes stuck (< 300s threshold)
        assessment_time=datetime.utcnow()
    )

    result = await swapper.evaluate_and_swap("test-pod")

    assert result.swapped is False
    assert result.outcome == SwapOutcome.SKIPPED
    assert "timeout_not_reached" in result.reason


@pytest.mark.asyncio
async def test_evaluate_and_swap_success(swapper, mock_detector, mock_modulator, mock_k8s):
    """Test successful pod swap."""
    # Mock stuck pod
    mock_detector.check_pod_liveness.return_value = LivenessState(
        pod_name="test-pod-abc-123",
        score=0.2,
        signals=LivenessSignals(
            k8s_ready=False,
            recent_logs=False,
            cpu_activity=False,
            network_activity=True,
            task_progress=False
        ),
        stuck=True,
        stuck_duration=400,  # >300s threshold
        assessment_time=datetime.utcnow()
    )

    # Mock pod metadata
    mock_pod = MagicMock()
    mock_pod.metadata.labels = {"agent-type": "test_agent", "task-id": "task-123"}
    mock_pod.metadata.namespace = "cortex-system"
    mock_pod.spec.node_name = "node-1"
    mock_k8s.get_pod.return_value = mock_pod

    # Mock spawn approval
    mock_modulator.request_spawn.return_value = SpawnDecision(
        approved=True,
        status=SpawnStatus.QUEUED,
        reason="approved",
        current_rate=10.0
    )

    result = await swapper.evaluate_and_swap("test-pod-abc-123")

    assert result.swapped is True
    assert result.outcome == SwapOutcome.SUCCESS
    assert result.original_pod == "test-pod-abc-123"
    assert result.stuck_duration == 400

    # Verify pod was deleted
    mock_k8s.delete_pod.assert_called_once_with("test-pod-abc-123", grace_period_seconds=10)


@pytest.mark.asyncio
async def test_evaluate_and_swap_spawn_throttled(swapper, mock_detector, mock_modulator, mock_k8s):
    """Test swap failure when spawn is throttled."""
    mock_detector.check_pod_liveness.return_value = LivenessState(
        pod_name="test-pod",
        score=0.2,
        signals=LivenessSignals(False, False, False, True, False),
        stuck=True,
        stuck_duration=400,
        assessment_time=datetime.utcnow()
    )

    mock_pod = MagicMock()
    mock_pod.metadata.labels = {"agent-type": "test_agent"}
    mock_pod.metadata.namespace = "cortex-system"
    mock_k8s.get_pod.return_value = mock_pod

    # Mock spawn rejection
    mock_modulator.request_spawn.return_value = SpawnDecision(
        approved=False,
        status=SpawnStatus.THROTTLED,
        reason="spawn_rate_limited",
        retry_after=30.0,
        current_rate=1.0
    )

    result = await swapper.evaluate_and_swap("test-pod")

    assert result.swapped is False
    assert result.outcome == SwapOutcome.FAILED
    assert "throttled" in result.reason


@pytest.mark.asyncio
async def test_evaluate_and_swap_escalation_on_repeated_failures(swapper, mock_detector, mock_modulator, mock_k8s):
    """Test escalation when pod has been swapped multiple times recently."""
    mock_detector.check_pod_liveness.return_value = LivenessState(
        pod_name="test-pod-abc-123",
        score=0.2,
        signals=LivenessSignals(False, False, False, True, False),
        stuck=True,
        stuck_duration=400,
        assessment_time=datetime.utcnow()
    )

    # Add swap history (3 recent swaps for same pod prefix)
    now = datetime.utcnow()
    for i in range(3):
        swapper.swap_history.append({
            "timestamp": now - timedelta(minutes=i),
            "original_pod": f"test-pod-abc-xyz{i}",
        })

    result = await swapper.evaluate_and_swap("test-pod-abc-456")

    assert result.swapped is False
    assert result.outcome == SwapOutcome.ESCALATED
    assert "repeated_failures" in result.reason
    assert "Investigate root cause" in result.recommendation


@pytest.mark.asyncio
async def test_force_swap(swapper, mock_modulator, mock_k8s):
    """Test manual force swap."""
    mock_pod = MagicMock()
    mock_pod.metadata.labels = {"agent-type": "test_agent"}
    mock_k8s.get_pod.return_value = mock_pod

    mock_modulator.request_spawn.return_value = SpawnDecision(
        approved=True,
        status=SpawnStatus.QUEUED,
        reason="approved",
        current_rate=10.0
    )

    result = await swapper.force_swap("test-pod", "Manual intervention required")

    assert result.swapped is True
    assert result.outcome == SwapOutcome.SUCCESS
    assert "manual_swap" in result.reason

    # Verify pod was deleted
    mock_k8s.delete_pod.assert_called_once()


def test_get_swap_history(swapper):
    """Test swap history retrieval."""
    # Add some swap entries
    now = datetime.utcnow()
    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=10),
        "original_pod": "pod-1",
    })
    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=70),  # Too old
        "original_pod": "pod-2",
    })

    history = swapper.get_swap_history(minutes=60)

    # Should only get pod-1 (within 60 minutes)
    assert len(history) == 1
    assert history[0]["original_pod"] == "pod-1"


def test_get_recent_swaps_by_prefix(swapper):
    """Test getting recent swaps for a pod by prefix matching."""
    now = datetime.utcnow()

    # Add swaps for similar pod names
    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=2),
        "original_pod": "test-pod-abc-123",
    })
    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=3),
        "original_pod": "test-pod-abc-456",
    })
    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=1),
        "original_pod": "other-pod-xyz-789",
    })

    # Query for test-pod-abc-*
    recent = swapper._get_recent_swaps("test-pod-abc-999", minutes=5)

    # Should get 2 swaps (both test-pod-abc-*)
    assert len(recent) == 2
    assert all("test-pod-abc" in swap["original_pod"] for swap in recent)


def test_get_recent_swaps_time_window(swapper):
    """Test that only swaps within time window are returned."""
    now = datetime.utcnow()

    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=3),  # Within window
        "original_pod": "test-pod-abc-123",
    })
    swapper.swap_history.append({
        "timestamp": now - timedelta(minutes=10),  # Outside window
        "original_pod": "test-pod-abc-456",
    })

    recent = swapper._get_recent_swaps("test-pod-abc-789", minutes=5)

    # Should only get 1 swap (within 5 minutes)
    assert len(recent) == 1
    assert recent[0]["timestamp"] == now - timedelta(minutes=3)
