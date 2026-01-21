#!/usr/bin/env python3
"""
Cortex Memory Service - Session Continuity and Infrastructure State Management
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("memory-service")


# ============================================================================
# Models
# ============================================================================


class EventType(str, Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    DECISION = "decision"
    ACTION = "action"
    GIT_COMMIT = "git_commit"
    DEPLOYMENT = "deployment"
    STACK_ACTIVATION = "stack_activation"
    SCALE_EVENT = "scale_event"
    POD_LIFECYCLE = "pod_lifecycle"
    CONFIG_CHANGE = "config_change"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"
    ERROR = "error"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TodoItem(BaseModel):
    content: str
    status: str
    active_form: Optional[str] = None


class Decision(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    decision: str
    rationale: Optional[str] = None
    alternatives: Optional[List[str]] = None
    outcome: Optional[str] = None


class Action(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    action_type: str
    description: str
    details: Optional[Dict[str, Any]] = None
    result: Optional[str] = None


class SessionCreate(BaseModel):
    working_directory: Optional[str] = None
    current_task: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionUpdate(BaseModel):
    working_directory: Optional[str] = None
    current_task: Optional[str] = None
    active_files: Optional[List[str]] = None
    todo_list: Optional[List[TodoItem]] = None
    blockers: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionSummary(BaseModel):
    session_id: str
    summary: str
    key_decisions: List[str]
    accomplishments: List[str]
    pending_tasks: List[str]
    blockers: List[str]
    next_steps: List[str]


class Session(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    working_directory: Optional[str] = None
    current_task: Optional[str] = None
    active_files: List[str] = []
    decisions: List[Decision] = []
    actions: List[Action] = []
    todo_list: List[TodoItem] = []
    blockers: List[str] = []
    next_steps: List[str] = []
    summary: Optional[str] = None
    metadata: Dict[str, Any] = {}


class TimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: EventType
    source: str
    description: str
    details: Optional[Dict[str, Any]] = None
    caused_by: Optional[str] = None
    affected_components: List[str] = []
    severity: Severity = Severity.LOW


class TimelineEventCreate(BaseModel):
    event_type: EventType
    source: str
    description: str
    details: Optional[Dict[str, Any]] = None
    caused_by: Optional[str] = None
    affected_components: List[str] = []
    severity: Severity = Severity.LOW


class NodeInfo(BaseModel):
    name: str
    status: str
    roles: List[str]
    cpu_capacity: str
    memory_capacity: str
    conditions: Dict[str, str]


class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ready: bool
    restarts: int
    node: Optional[str]
    containers: List[str]
    age_seconds: float


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    available_replicas: int
    conditions: List[Dict[str, str]]


class ServiceInfo(BaseModel):
    name: str
    namespace: str
    type: str
    cluster_ip: Optional[str]
    ports: List[Dict[str, Any]]


class MCPServerInfo(BaseModel):
    name: str
    namespace: str
    status: str
    restarts: int
    port: Optional[int]
    url: Optional[str]


class InfrastructureState(BaseModel):
    timestamp: datetime
    nodes: List[NodeInfo]
    pods: List[PodInfo]
    deployments: List[DeploymentInfo]
    services: List[ServiceInfo]
    mcp_servers: List[MCPServerInfo]
    health_summary: Dict[str, int]


class InfrastructureDiff(BaseModel):
    since: datetime
    until: datetime
    added: Dict[str, List[str]]
    removed: Dict[str, List[str]]
    changed: Dict[str, List[Dict[str, Any]]]


class HealthSummary(BaseModel):
    healthy: int
    degraded: int
    critical: int
    unknown: int
    details: Dict[str, List[str]]


class CorrelationRequest(BaseModel):
    symptom: str
    timeframe: str = "24h"


class CorrelationResult(BaseModel):
    symptom: str
    probable_cause: Optional[TimelineEvent]
    related_events: List[TimelineEvent]
    confidence: float


# ============================================================================
# Memory Service
# ============================================================================


class MemoryService:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self.k8s_core: Optional[client.CoreV1Api] = None
        self.k8s_apps: Optional[client.AppsV1Api] = None
        self._collector_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        logger.info("Starting Memory Service...")

        # Connect to Redis
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        await self.redis.ping()
        logger.info("Connected to Redis")

        # Connect to Kubernetes
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.k8s_core = client.CoreV1Api()
        self.k8s_apps = client.AppsV1Api()
        logger.info("Connected to Kubernetes")

        # Start infrastructure collector
        self._running = True
        self._collector_task = asyncio.create_task(self._collect_loop())

        logger.info("Memory Service started")

    async def stop(self):
        logger.info("Stopping Memory Service...")
        self._running = False
        if self._collector_task:
            self._collector_task.cancel()
            try:
                await self._collector_task
            except asyncio.CancelledError:
                pass
        if self.redis:
            await self.redis.close()

    # ========================================================================
    # Session Management
    # ========================================================================

    async def create_session(self, data: SessionCreate) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            started_at=datetime.now(),
            working_directory=data.working_directory,
            current_task=data.current_task,
            metadata=data.metadata or {},
        )

        # Store in Redis
        await self.redis.hset(
            "memory:sessions",
            session.session_id,
            session.model_dump_json(),
        )

        # Set as current session
        await self.redis.set("memory:current_session", session.session_id)

        # Record timeline event
        await self.record_event(TimelineEventCreate(
            event_type=EventType.SESSION_START,
            source="memory-service",
            description=f"Session started: {session.session_id}",
            details={"current_task": data.current_task},
            affected_components=["memory-service"],
        ))

        logger.info(f"Created session: {session.session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        data = await self.redis.hget("memory:sessions", session_id)
        if data:
            return Session.model_validate_json(data)
        return None

    async def get_current_session(self) -> Optional[Session]:
        session_id = await self.redis.get("memory:current_session")
        if session_id:
            return await self.get_session(session_id)

        # Try to find most recent session within 24 hours
        sessions = await self.list_sessions(limit=1)
        if sessions:
            recent = sessions[0]
            age = datetime.now() - recent.started_at
            if age < timedelta(hours=24):
                return recent
        return None

    async def update_session(self, session_id: str, data: SessionUpdate) -> Session:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Update fields
        if data.working_directory is not None:
            session.working_directory = data.working_directory
        if data.current_task is not None:
            session.current_task = data.current_task
        if data.active_files is not None:
            session.active_files = data.active_files
        if data.todo_list is not None:
            session.todo_list = data.todo_list
        if data.blockers is not None:
            session.blockers = data.blockers
        if data.next_steps is not None:
            session.next_steps = data.next_steps
        if data.metadata is not None:
            session.metadata.update(data.metadata)

        # Store updated session
        await self.redis.hset(
            "memory:sessions",
            session_id,
            session.model_dump_json(),
        )

        return session

    async def end_session(self, session_id: str, summary: str) -> Session:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.ended_at = datetime.now()
        session.summary = summary

        await self.redis.hset(
            "memory:sessions",
            session_id,
            session.model_dump_json(),
        )

        # Clear current session
        current = await self.redis.get("memory:current_session")
        if current == session_id:
            await self.redis.delete("memory:current_session")

        # Record timeline event
        await self.record_event(TimelineEventCreate(
            event_type=EventType.SESSION_END,
            source="memory-service",
            description=f"Session ended: {session_id}",
            details={"summary": summary},
            affected_components=["memory-service"],
        ))

        logger.info(f"Ended session: {session_id}")
        return session

    async def list_sessions(
        self,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> List[Session]:
        all_data = await self.redis.hgetall("memory:sessions")
        sessions = [Session.model_validate_json(d) for d in all_data.values()]

        # Filter by time
        if since:
            sessions = [s for s in sessions if s.started_at >= since]

        # Sort by start time, most recent first
        sessions.sort(key=lambda s: s.started_at, reverse=True)

        return sessions[:limit]

    async def get_session_summary(self, session_id: str) -> SessionSummary:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return SessionSummary(
            session_id=session.session_id,
            summary=session.summary or f"Working on: {session.current_task}",
            key_decisions=[d.decision for d in session.decisions[-5:]],
            accomplishments=[
                a.description
                for a in session.actions
                if a.result == "success"
            ][-5:],
            pending_tasks=[
                t.content for t in session.todo_list if t.status == "pending"
            ],
            blockers=session.blockers,
            next_steps=session.next_steps,
        )

    async def record_decision(
        self,
        session_id: str,
        decision: str,
        rationale: Optional[str] = None,
        alternatives: Optional[List[str]] = None,
    ) -> Decision:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        d = Decision(
            decision=decision,
            rationale=rationale,
            alternatives=alternatives,
        )
        session.decisions.append(d)

        await self.redis.hset(
            "memory:sessions",
            session_id,
            session.model_dump_json(),
        )

        # Record timeline event
        await self.record_event(TimelineEventCreate(
            event_type=EventType.DECISION,
            source="memory-service",
            description=decision,
            details={"rationale": rationale, "alternatives": alternatives},
            affected_components=[],
        ))

        return d

    async def record_action(
        self,
        session_id: str,
        action_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
    ) -> Action:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        a = Action(
            action_type=action_type,
            description=description,
            details=details,
            result=result,
        )
        session.actions.append(a)

        await self.redis.hset(
            "memory:sessions",
            session_id,
            session.model_dump_json(),
        )

        # Record timeline event
        await self.record_event(TimelineEventCreate(
            event_type=EventType.ACTION,
            source="memory-service",
            description=description,
            details=details,
            affected_components=[],
        ))

        return a

    # ========================================================================
    # Infrastructure State
    # ========================================================================

    async def collect_infrastructure_state(self) -> InfrastructureState:
        nodes = await self._collect_nodes()
        pods = await self._collect_pods()
        deployments = await self._collect_deployments()
        services = await self._collect_services()
        mcp_servers = self._identify_mcp_servers(pods)

        # Calculate health summary
        health = self._calculate_health(pods, deployments)

        state = InfrastructureState(
            timestamp=datetime.now(),
            nodes=nodes,
            pods=pods,
            deployments=deployments,
            services=services,
            mcp_servers=mcp_servers,
            health_summary=health,
        )

        # Store in Redis
        await self.redis.set(
            "memory:infrastructure:current",
            state.model_dump_json(),
        )

        # Store snapshot for history
        await self.redis.lpush(
            "memory:infrastructure:snapshots",
            state.model_dump_json(),
        )
        await self.redis.ltrim("memory:infrastructure:snapshots", 0, 999)

        return state

    async def _collect_nodes(self) -> List[NodeInfo]:
        nodes = []
        try:
            node_list = self.k8s_core.list_node()
            for n in node_list.items:
                roles = []
                for label, value in (n.metadata.labels or {}).items():
                    if "node-role.kubernetes.io/" in label:
                        roles.append(label.split("/")[-1])

                conditions = {}
                for c in n.status.conditions or []:
                    conditions[c.type] = c.status

                nodes.append(NodeInfo(
                    name=n.metadata.name,
                    status="Ready" if conditions.get("Ready") == "True" else "NotReady",
                    roles=roles or ["worker"],
                    cpu_capacity=n.status.capacity.get("cpu", "unknown"),
                    memory_capacity=n.status.capacity.get("memory", "unknown"),
                    conditions=conditions,
                ))
        except ApiException as e:
            logger.error(f"Failed to list nodes: {e}")
        return nodes

    async def _collect_pods(self) -> List[PodInfo]:
        pods = []
        try:
            pod_list = self.k8s_core.list_pod_for_all_namespaces()
            for p in pod_list.items:
                restarts = 0
                containers = []
                for cs in p.status.container_statuses or []:
                    restarts += cs.restart_count
                    containers.append(cs.name)

                age = (datetime.now(p.metadata.creation_timestamp.tzinfo) -
                       p.metadata.creation_timestamp).total_seconds()

                ready = all(
                    cs.ready for cs in (p.status.container_statuses or [])
                )

                pods.append(PodInfo(
                    name=p.metadata.name,
                    namespace=p.metadata.namespace,
                    status=p.status.phase,
                    ready=ready and p.status.phase == "Running",
                    restarts=restarts,
                    node=p.spec.node_name,
                    containers=containers,
                    age_seconds=age,
                ))
        except ApiException as e:
            logger.error(f"Failed to list pods: {e}")
        return pods

    async def _collect_deployments(self) -> List[DeploymentInfo]:
        deployments = []
        try:
            dep_list = self.k8s_apps.list_deployment_for_all_namespaces()
            for d in dep_list.items:
                conditions = []
                for c in d.status.conditions or []:
                    conditions.append({
                        "type": c.type,
                        "status": c.status,
                        "reason": c.reason,
                    })

                deployments.append(DeploymentInfo(
                    name=d.metadata.name,
                    namespace=d.metadata.namespace,
                    replicas=d.spec.replicas or 0,
                    ready_replicas=d.status.ready_replicas or 0,
                    available_replicas=d.status.available_replicas or 0,
                    conditions=conditions,
                ))
        except ApiException as e:
            logger.error(f"Failed to list deployments: {e}")
        return deployments

    async def _collect_services(self) -> List[ServiceInfo]:
        services = []
        try:
            svc_list = self.k8s_core.list_service_for_all_namespaces()
            for s in svc_list.items:
                ports = []
                for p in s.spec.ports or []:
                    ports.append({
                        "name": p.name,
                        "port": p.port,
                        "target_port": str(p.target_port),
                        "protocol": p.protocol,
                    })

                services.append(ServiceInfo(
                    name=s.metadata.name,
                    namespace=s.metadata.namespace,
                    type=s.spec.type,
                    cluster_ip=s.spec.cluster_ip,
                    ports=ports,
                ))
        except ApiException as e:
            logger.error(f"Failed to list services: {e}")
        return services

    def _identify_mcp_servers(self, pods: List[PodInfo]) -> List[MCPServerInfo]:
        mcp_servers = []
        for p in pods:
            if "mcp" in p.name.lower():
                port = None
                url = None

                # Infer port from common patterns
                if "3000" in p.name or "mcp-server" in p.name:
                    port = 3000
                elif "8765" in p.name or "desktop" in p.name:
                    port = 8765

                if port and p.ready:
                    url = f"http://{p.name}.{p.namespace}.svc.cluster.local:{port}"

                mcp_servers.append(MCPServerInfo(
                    name=p.name.rsplit("-", 2)[0] if "-" in p.name else p.name,
                    namespace=p.namespace,
                    status=p.status if p.ready else "Unhealthy",
                    restarts=p.restarts,
                    port=port,
                    url=url,
                ))
        return mcp_servers

    def _calculate_health(
        self,
        pods: List[PodInfo],
        deployments: List[DeploymentInfo],
    ) -> Dict[str, int]:
        healthy = 0
        degraded = 0
        critical = 0
        unknown = 0

        for p in pods:
            if p.ready and p.status == "Running":
                healthy += 1
            elif p.status in ["Pending", "ContainerCreating"]:
                degraded += 1
            elif p.status in ["Failed", "Error", "CrashLoopBackOff"]:
                critical += 1
            else:
                unknown += 1

        return {
            "healthy": healthy,
            "degraded": degraded,
            "critical": critical,
            "unknown": unknown,
        }

    async def get_infrastructure_state(self) -> Optional[InfrastructureState]:
        data = await self.redis.get("memory:infrastructure:current")
        if data:
            return InfrastructureState.model_validate_json(data)
        return None

    async def get_infrastructure_diff(
        self,
        since: datetime,
    ) -> InfrastructureDiff:
        current = await self.get_infrastructure_state()
        if not current:
            return InfrastructureDiff(
                since=since,
                until=datetime.now(),
                added={},
                removed={},
                changed={},
            )

        # Get snapshots since the given time
        snapshots = await self.redis.lrange("memory:infrastructure:snapshots", 0, -1)
        previous = None
        for s in snapshots:
            state = InfrastructureState.model_validate_json(s)
            if state.timestamp <= since:
                previous = state
                break

        if not previous:
            return InfrastructureDiff(
                since=since,
                until=current.timestamp,
                added={},
                removed={},
                changed={},
            )

        # Calculate diff
        added = {"pods": [], "deployments": [], "services": []}
        removed = {"pods": [], "deployments": [], "services": []}
        changed = {"pods": [], "deployments": []}

        current_pods = {p.name: p for p in current.pods}
        previous_pods = {p.name: p for p in previous.pods}

        for name in current_pods:
            if name not in previous_pods:
                added["pods"].append(name)
        for name in previous_pods:
            if name not in current_pods:
                removed["pods"].append(name)

        current_deps = {d.name: d for d in current.deployments}
        previous_deps = {d.name: d for d in previous.deployments}

        for name in current_deps:
            if name not in previous_deps:
                added["deployments"].append(name)
            elif current_deps[name].replicas != previous_deps[name].replicas:
                changed["deployments"].append({
                    "name": name,
                    "old_replicas": previous_deps[name].replicas,
                    "new_replicas": current_deps[name].replicas,
                })

        return InfrastructureDiff(
            since=since,
            until=current.timestamp,
            added=added,
            removed=removed,
            changed=changed,
        )

    async def get_health_summary(self) -> HealthSummary:
        state = await self.get_infrastructure_state()
        if not state:
            return HealthSummary(
                healthy=0,
                degraded=0,
                critical=0,
                unknown=0,
                details={},
            )

        details = {
            "healthy": [],
            "degraded": [],
            "critical": [],
        }

        for p in state.pods:
            if p.ready and p.status == "Running":
                pass  # Don't list all healthy pods
            elif p.status in ["Pending", "ContainerCreating"]:
                details["degraded"].append(f"{p.namespace}/{p.name}")
            elif p.restarts > 10 or p.status in ["Failed", "Error"]:
                details["critical"].append(f"{p.namespace}/{p.name}")

        return HealthSummary(
            healthy=state.health_summary.get("healthy", 0),
            degraded=state.health_summary.get("degraded", 0),
            critical=state.health_summary.get("critical", 0),
            unknown=state.health_summary.get("unknown", 0),
            details=details,
        )

    async def get_component_state(self, name: str) -> Optional[Dict[str, Any]]:
        state = await self.get_infrastructure_state()
        if not state:
            return None

        # Search in pods
        for p in state.pods:
            if name in p.name:
                return {
                    "type": "pod",
                    "name": p.name,
                    "namespace": p.namespace,
                    "status": p.status,
                    "ready": p.ready,
                    "restarts": p.restarts,
                }

        # Search in deployments
        for d in state.deployments:
            if name in d.name:
                return {
                    "type": "deployment",
                    "name": d.name,
                    "namespace": d.namespace,
                    "replicas": d.replicas,
                    "ready_replicas": d.ready_replicas,
                }

        # Search in MCP servers
        for m in state.mcp_servers:
            if name in m.name:
                return {
                    "type": "mcp_server",
                    "name": m.name,
                    "namespace": m.namespace,
                    "status": m.status,
                    "restarts": m.restarts,
                    "url": m.url,
                }

        return None

    async def _collect_loop(self):
        while self._running:
            try:
                await self.collect_infrastructure_state()
                logger.debug("Collected infrastructure state")
            except Exception as e:
                logger.error(f"Collection error: {e}")
            await asyncio.sleep(30)

    # ========================================================================
    # Timeline Events
    # ========================================================================

    async def record_event(self, data: TimelineEventCreate) -> TimelineEvent:
        event = TimelineEvent(
            event_type=data.event_type,
            source=data.source,
            description=data.description,
            details=data.details,
            caused_by=data.caused_by,
            affected_components=data.affected_components,
            severity=data.severity,
        )

        # Store in Redis (sorted set by timestamp)
        await self.redis.zadd(
            "memory:timeline",
            {event.model_dump_json(): event.timestamp.timestamp()},
        )

        # Also store by component for quick lookup
        for component in event.affected_components:
            await self.redis.lpush(
                f"memory:timeline:component:{component}",
                event.model_dump_json(),
            )
            await self.redis.ltrim(f"memory:timeline:component:{component}", 0, 499)

        return event

    async def get_timeline(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> List[TimelineEvent]:
        start_ts = start.timestamp() if start else 0
        end_ts = end.timestamp() if end else float("inf")

        raw_events = await self.redis.zrangebyscore(
            "memory:timeline",
            start_ts,
            end_ts,
            withscores=False,
        )

        events = []
        for raw in raw_events:
            event = TimelineEvent.model_validate_json(raw)
            if event_type is None or event.event_type == event_type:
                events.append(event)

        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        # Scan timeline for event
        raw_events = await self.redis.zrange("memory:timeline", 0, -1)
        for raw in raw_events:
            event = TimelineEvent.model_validate_json(raw)
            if event.event_id == event_id:
                return event
        return None

    async def get_component_timeline(
        self,
        component: str,
        limit: int = 50,
    ) -> List[TimelineEvent]:
        raw_events = await self.redis.lrange(
            f"memory:timeline:component:{component}",
            0,
            limit - 1,
        )
        return [TimelineEvent.model_validate_json(e) for e in raw_events]

    async def correlate_events(
        self,
        symptom: str,
        timeframe_str: str,
    ) -> CorrelationResult:
        # Parse timeframe
        hours = 24
        if timeframe_str.endswith("h"):
            hours = int(timeframe_str[:-1])
        elif timeframe_str.endswith("d"):
            hours = int(timeframe_str[:-1]) * 24

        timeframe = timedelta(hours=hours)
        end = datetime.now()
        start = end - timeframe

        events = await self.get_timeline(start=start, end=end, limit=200)

        # Score events by relevance
        scored = []
        symptom_lower = symptom.lower()
        symptom_words = set(symptom_lower.split())

        for event in events:
            score = 0.0

            # Time proximity
            time_delta = (end - event.timestamp).total_seconds()
            score += max(0, 1 - time_delta / (hours * 3600))

            # Description match
            desc_lower = event.description.lower()
            overlap = len(symptom_words & set(desc_lower.split()))
            score += overlap * 0.3

            # Component match
            for comp in event.affected_components:
                if comp.lower() in symptom_lower:
                    score += 0.5

            # Event type relevance
            if event.event_type in [
                EventType.DEPLOYMENT,
                EventType.CONFIG_CHANGE,
                EventType.GIT_COMMIT,
            ]:
                score += 0.2

            if score > 0.1:
                scored.append((score, event))

        scored.sort(reverse=True)

        return CorrelationResult(
            symptom=symptom,
            probable_cause=scored[0][1] if scored else None,
            related_events=[e for _, e in scored[:10]],
            confidence=scored[0][0] if scored else 0.0,
        )


# ============================================================================
# FastAPI Application
# ============================================================================

memory: Optional[MemoryService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory
    memory = MemoryService(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
    )
    await memory.start()
    yield
    await memory.stop()


app = FastAPI(
    title="Cortex Memory Service",
    version="1.0.0",
    lifespan=lifespan,
)


# Health endpoints
@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    if memory and memory.redis:
        try:
            await memory.redis.ping()
            return {"status": "ready"}
        except Exception:
            pass
    raise HTTPException(503, "Not ready")


# Session endpoints
@app.post("/memory/sessions")
async def create_session(data: SessionCreate):
    session = await memory.create_session(data)
    return session


@app.get("/memory/sessions")
async def list_sessions(
    limit: int = Query(10, ge=1, le=100),
    since: Optional[str] = None,
):
    since_dt = None
    if since:
        since_dt = datetime.fromisoformat(since)
    sessions = await memory.list_sessions(limit=limit, since=since_dt)
    return {"sessions": sessions}


@app.get("/memory/sessions/current")
async def get_current_session():
    session = await memory.get_current_session()
    if not session:
        raise HTTPException(404, "No current session")
    return session


@app.get("/memory/sessions/{session_id}")
async def get_session(session_id: str):
    session = await memory.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@app.put("/memory/sessions/{session_id}")
async def update_session(session_id: str, data: SessionUpdate):
    try:
        session = await memory.update_session(session_id, data)
        return session
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/memory/sessions/{session_id}/end")
async def end_session(session_id: str, summary: str = ""):
    try:
        session = await memory.end_session(session_id, summary)
        return session
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/memory/sessions/{session_id}/summary")
async def get_session_summary(session_id: str):
    try:
        summary = await memory.get_session_summary(session_id)
        return summary
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/memory/sessions/{session_id}/decision")
async def record_decision(
    session_id: str,
    decision: str,
    rationale: Optional[str] = None,
    alternatives: Optional[List[str]] = None,
):
    try:
        d = await memory.record_decision(
            session_id,
            decision,
            rationale,
            alternatives,
        )
        return d
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/memory/sessions/{session_id}/action")
async def record_action(
    session_id: str,
    action_type: str,
    description: str,
    details: Optional[Dict[str, Any]] = None,
    result: Optional[str] = None,
):
    try:
        a = await memory.record_action(
            session_id,
            action_type,
            description,
            details,
            result,
        )
        return a
    except ValueError as e:
        raise HTTPException(404, str(e))


# Infrastructure endpoints
@app.get("/memory/infrastructure/current")
async def get_infrastructure():
    state = await memory.get_infrastructure_state()
    if not state:
        # Collect now if not available
        state = await memory.collect_infrastructure_state()
    return state


@app.get("/memory/infrastructure/component/{name}")
async def get_component(name: str):
    state = await memory.get_component_state(name)
    if not state:
        raise HTTPException(404, f"Component not found: {name}")
    return state


@app.get("/memory/infrastructure/diff")
async def get_infrastructure_diff(since: str):
    since_dt = datetime.fromisoformat(since)
    diff = await memory.get_infrastructure_diff(since_dt)
    return diff


@app.get("/memory/infrastructure/health")
async def get_health():
    return await memory.get_health_summary()


# Timeline endpoints
@app.get("/memory/timeline")
async def get_timeline(
    start: Optional[str] = None,
    end: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    event_type = EventType(type) if type else None

    events = await memory.get_timeline(
        start=start_dt,
        end=end_dt,
        event_type=event_type,
        limit=limit,
    )
    return {"events": events}


@app.get("/memory/timeline/event/{event_id}")
async def get_event(event_id: str):
    event = await memory.get_event(event_id)
    if not event:
        raise HTTPException(404, f"Event not found: {event_id}")
    return event


@app.get("/memory/timeline/component/{name}")
async def get_component_timeline(name: str, limit: int = Query(50, ge=1, le=500)):
    events = await memory.get_component_timeline(name, limit)
    return {"component": name, "events": events}


@app.post("/memory/timeline/event")
async def create_event(data: TimelineEventCreate):
    event = await memory.record_event(data)
    return event


@app.post("/memory/timeline/correlate")
async def correlate(data: CorrelationRequest):
    result = await memory.correlate_events(data.symptom, data.timeframe)
    return result


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    state = await memory.get_infrastructure_state()
    sessions = await memory.list_sessions(limit=100)

    timeline_size = await memory.redis.zcard("memory:timeline")

    return {
        "sessions": {
            "total": len(sessions),
            "active": sum(1 for s in sessions if s.ended_at is None),
        },
        "infrastructure": {
            "nodes": len(state.nodes) if state else 0,
            "pods": len(state.pods) if state else 0,
            "mcp_servers": len(state.mcp_servers) if state else 0,
        },
        "timeline": {
            "total_events": timeline_size,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
