"""Tests for StuckPodDetector."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from server.stuck_detector import StuckPodDetector


@pytest.fixture
def mock_awareness():
    """Mock awareness client."""
    awareness = AsyncMock()
    awareness.call_tool = AsyncMock()
    return awareness


@pytest.fixture
def mock_commit_relay():
    """Mock commit-relay client."""
    relay = AsyncMock()
    relay.get_agent_state = AsyncMock()
    return relay


@pytest.fixture
def detector(mock_awareness, mock_commit_relay):
    """Create detector instance."""
    config = {
        "liveness_check_interval": 60,
        "stuck_threshold": 0.4,
        "stuck_timeout": 300,
    }
    return StuckPodDetector(mock_awareness, mock_commit_relay, config)


@pytest.mark.asyncio
async def test_check_pod_liveness_healthy(detector, mock_awareness, mock_commit_relay):
    """Test liveness check for healthy pod."""
    mock_awareness.call_tool.side_effect = [
        # get_pod_state
        {
            "conditions": {"Ready": "True"},
            "cpu_millicores": 150,
            "memory_mb": 256,
        },
        # get_pod_logs
        ["log line 1", "log line 2", "log line 3"],
    ]

    mock_commit_relay.get_agent_state.return_value = {
        "last_action_at": datetime.utcnow() - timedelta(seconds=30),
        "status": "running"
    }

    liveness = await detector.check_pod_liveness("test-pod-123")

    # All signals should be True:
    # - k8s_ready: True (20%)
    # - recent_logs: True (20%)
    # - cpu_activity: True (15%)
    # - network_activity: True (15%)
    # - task_progress: True (30%)
    # Score: 1.0

    assert liveness.score == 1.0
    assert liveness.stuck is False
    assert liveness.stuck_duration == 0
    assert liveness.signals.k8s_ready is True
    assert liveness.signals.recent_logs is True
    assert liveness.signals.cpu_activity is True
    assert liveness.signals.task_progress is True


@pytest.mark.asyncio
async def test_check_pod_liveness_stuck_no_progress(detector, mock_awareness, mock_commit_relay):
    """Test liveness check for stuck pod with no task progress."""
    mock_awareness.call_tool.side_effect = [
        # get_pod_state
        {
            "conditions": {"Ready": "True"},
            "cpu_millicores": 150,
        },
        # get_pod_logs
        ["log line"],
    ]

    # No recent action = stuck
    mock_commit_relay.get_agent_state.return_value = {
        "last_action_at": datetime.utcnow() - timedelta(seconds=600),  # 10 minutes ago
        "status": "running"
    }

    liveness = await detector.check_pod_liveness("test-pod-123")

    # task_progress will be False (30% missing)
    # Score: 0.20 + 0.20 + 0.15 + 0.15 + 0.0 = 0.70
    # But wait, score should be lower because task_progress is False
    # Actually: 0.70 > 0.4, so not stuck

    # Let me recalculate: if task_progress is False, we lose 30%
    # 0.20 + 0.20 + 0.15 + 0.15 = 0.70 (still above threshold)

    assert liveness.signals.task_progress is False
    assert liveness.score == 0.70


@pytest.mark.asyncio
async def test_check_pod_liveness_stuck_no_logs(detector, mock_awareness, mock_commit_relay):
    """Test liveness check for stuck pod with no recent logs."""
    mock_awareness.call_tool.side_effect = [
        # get_pod_state
        {
            "conditions": {"Ready": "True"},
            "cpu_millicores": 1,  # Very low CPU
        },
        # get_pod_logs (empty)
        [],
    ]

    # No recent action
    mock_commit_relay.get_agent_state.return_value = {
        "last_action_at": datetime.utcnow() - timedelta(seconds=600),
        "status": "running"
    }

    liveness = await detector.check_pod_liveness("test-pod-123")

    # Missing signals:
    # - recent_logs: False (20%)
    # - cpu_activity: False (15%)
    # - task_progress: False (30%)
    # Score: 0.20 + 0.15 = 0.35 (below 0.4 threshold)

    assert liveness.score == 0.35
    assert liveness.stuck is True
    assert liveness.signals.recent_logs is False
    assert liveness.signals.cpu_activity is False
    assert liveness.signals.task_progress is False


@pytest.mark.asyncio
async def test_check_pod_liveness_stuck_not_ready(detector, mock_awareness, mock_commit_relay):
    """Test liveness check for pod that's not k8s Ready."""
    mock_awareness.call_tool.side_effect = [
        # get_pod_state
        {
            "conditions": {"Ready": "False"},  # Not ready
            "cpu_millicores": 0,
        },
        # get_pod_logs
        [],
    ]

    mock_commit_relay.get_agent_state.return_value = None  # No state

    liveness = await detector.check_pod_liveness("test-pod-123")

    # All signals False except network_activity (defaults to True)
    # Score: 0.15 = 0.15 (well below threshold)

    assert liveness.score == 0.15
    assert liveness.stuck is True


@pytest.mark.asyncio
async def test_check_pod_liveness_no_commit_relay(detector, mock_awareness):
    """Test liveness check without commit-relay integration."""
    detector.commit_relay = None

    mock_awareness.call_tool.side_effect = [
        # get_pod_state
        {
            "conditions": {"Ready": "True"},
            "cpu_millicores": 150,
        },
        # get_pod_logs
        ["log line"],
    ]

    liveness = await detector.check_pod_liveness("test-pod-123")

    # task_progress defaults to True when no commit-relay
    assert liveness.signals.task_progress is True


@pytest.mark.asyncio
async def test_stuck_duration_tracking(detector, mock_awareness, mock_commit_relay):
    """Test that stuck duration increases over multiple checks."""
    # First check - pod is stuck
    mock_awareness.call_tool.side_effect = [
        {"conditions": {"Ready": "False"}, "cpu_millicores": 0},
        [],
    ]
    mock_commit_relay.get_agent_state.return_value = None

    liveness1 = await detector.check_pod_liveness("test-pod-123")
    assert liveness1.stuck is True
    assert liveness1.stuck_duration == 0  # First time stuck

    # Second check - still stuck (simulate time passing)
    import asyncio
    await asyncio.sleep(0.1)

    mock_awareness.call_tool.side_effect = [
        {"conditions": {"Ready": "False"}, "cpu_millicores": 0},
        [],
    ]
    mock_commit_relay.get_agent_state.return_value = None

    liveness2 = await detector.check_pod_liveness("test-pod-123")
    assert liveness2.stuck is True
    assert liveness2.stuck_duration > 0  # Duration increased


@pytest.mark.asyncio
async def test_stuck_duration_reset_when_healthy(detector, mock_awareness, mock_commit_relay):
    """Test that stuck duration resets when pod becomes healthy."""
    # First check - stuck
    mock_awareness.call_tool.side_effect = [
        {"conditions": {"Ready": "False"}, "cpu_millicores": 0},
        [],
    ]
    mock_commit_relay.get_agent_state.return_value = None

    liveness1 = await detector.check_pod_liveness("test-pod-123")
    assert liveness1.stuck is True

    # Second check - healthy
    mock_awareness.call_tool.side_effect = [
        {"conditions": {"Ready": "True"}, "cpu_millicores": 150},
        ["logs"],
    ]
    mock_commit_relay.get_agent_state.return_value = {
        "last_action_at": datetime.utcnow(),
        "status": "running"
    }

    liveness2 = await detector.check_pod_liveness("test-pod-123")
    assert liveness2.stuck is False
    assert liveness2.stuck_duration == 0  # Reset


@pytest.mark.asyncio
async def test_get_stuck_pods(detector, mock_awareness, mock_commit_relay):
    """Test getting list of all stuck pods."""
    mock_awareness.call_tool.side_effect = [
        # get_sibling_pods
        [
            {"name": "pod-1", "phase": "Running"},
            {"name": "pod-2", "phase": "Running"},
            {"name": "pod-3", "phase": "Pending"},  # Skip non-running
        ],
        # check_pod_liveness for pod-1
        {"conditions": {"Ready": "True"}, "cpu_millicores": 150},
        ["logs"],
        # check_pod_liveness for pod-2
        {"conditions": {"Ready": "False"}, "cpu_millicores": 0},
        [],
    ]

    # pod-1: healthy
    mock_commit_relay.get_agent_state.side_effect = [
        {"last_action_at": datetime.utcnow(), "status": "running"},
        None,  # pod-2: no state
    ]

    # Manually set stuck_timeout to 0 to test immediately
    detector.stuck_timeout = 0

    stuck_pods = await detector.get_stuck_pods()

    # Only pod-2 should be in list (pod-1 is healthy, pod-3 is pending)
    assert len(stuck_pods) == 1
    assert stuck_pods[0].pod_name == "pod-2"


def test_pod_to_agent_id(detector):
    """Test pod name to agent ID conversion."""
    pod_name = "code-agent-abc123-xyz456"
    agent_id = detector._pod_to_agent_id(pod_name)

    # Should extract second-to-last part
    assert agent_id == "abc123"


def test_pod_to_agent_id_short_name(detector):
    """Test pod name conversion with short name."""
    pod_name = "short"
    agent_id = detector._pod_to_agent_id(pod_name)

    # Should return full name if not enough parts
    assert agent_id == "short"
