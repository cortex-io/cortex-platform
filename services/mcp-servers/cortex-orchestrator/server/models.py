"""Data models for Cortex Orchestrator."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class SpawnStatus(Enum):
    """Spawn request status."""
    APPROVED = "approved"
    QUEUED = "queued"
    THROTTLED = "throttled"
    REJECTED = "rejected"


class SwapOutcome(Enum):
    """Pod swap result."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ESCALATED = "escalated"


@dataclass
class ResourceProfile:
    """Resource requirements for an agent type."""
    cpu_millicores: int
    memory_mb: int
    ephemeral_storage_mb: Optional[int] = None
    gpu: int = 0


@dataclass
class PodLimit:
    """Dynamic pod limit calculation result."""
    current_count: int
    calculated_limit: int
    limiting_resource: str  # "cpu" or "memory"
    headroom: int
    stability_factor: float  # 0.0-1.0
    can_scale_up: bool
    recommendation: str


@dataclass
class BackpressureFactor:
    """Individual backpressure signal."""
    name: str
    value: float  # 0.0-1.0 (1.0 = no pressure)
    reason: str


@dataclass
class SpawnDecision:
    """Result of spawn request evaluation."""
    approved: bool
    status: SpawnStatus
    reason: str
    estimated_spawn_time: Optional[float] = None  # seconds
    current_rate: Optional[float] = None  # pods/second
    queue_position: Optional[int] = None
    retry_after: Optional[float] = None  # seconds
    backpressure: List[BackpressureFactor] = field(default_factory=list)


@dataclass
class LivenessSignals:
    """Multi-signal liveness detection."""
    k8s_ready: bool
    recent_logs: bool
    cpu_activity: bool
    network_activity: bool
    task_progress: bool


@dataclass
class LivenessState:
    """Pod liveness assessment."""
    pod_name: str
    score: float  # 0.0-1.0
    signals: LivenessSignals
    stuck: bool
    stuck_duration: int  # seconds
    assessment_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SwapResult:
    """Pod swap operation result."""
    swapped: bool
    outcome: SwapOutcome
    original_pod: str
    replacement_pod: Optional[str] = None
    stuck_duration: Optional[int] = None
    state_preserved: bool = False
    reason: str = ""
    action: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class AgentSpec:
    """Agent spawn specification."""
    agent_type: str
    task_id: str
    priority: int = 5  # 1-10, 10 highest
    estimated_duration: Optional[int] = None  # seconds
    resource_override: Optional[ResourceProfile] = None
    node_affinity: Optional[str] = None
    inherited_state: Optional[Dict] = None  # For swaps


@dataclass
class OrchestrationStatus:
    """Overall orchestrator health status."""
    active_agents: int
    capacity_limit: int
    headroom: int
    current_spawn_rate: float
    stuck_pods: int
    queued_tasks: int
    health: str  # "healthy", "degraded", "unhealthy"
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SwapHistoryEntry:
    """Historical swap event."""
    timestamp: datetime
    original_pod: str
    replacement_pod: Optional[str]
    outcome: SwapOutcome
    stuck_duration: int
    signals: LivenessSignals
    state_preserved: bool


@dataclass
class SpawnStatistics:
    """Spawn success metrics."""
    total_requests: int
    approved: int
    queued: int
    rejected: int
    success_rate: float
    average_spawn_time: float
    average_queue_time: float
    peak_spawn_rate: float
    period_hours: int
