"""
Cortex Activator - Query Router and Layer Orchestrator

This is the always-on brain of the Layer Fabric. It:
1. Receives queries from users/APIs (HTTP) OR Cortex master (Redis Streams)
2. Routes based on keywords (fast path, no LLM)
3. **NEW: Routes based on Qdrant similarity (learned from past successes)**
4. Wakes appropriate layers via KEDA
5. Proxies requests to execution layers
6. Handles failover (API → SSH)
7. Reports results back to Cortex via Redis Streams
8. **NEW: Stores routing decisions and outcomes for learning**

Routing Cascade (exit-early):
    Tier 0: Exact cache (TODO)
    Tier 1: Keyword pattern match (<10ms)
    Tier 2: Qdrant similarity search (<50ms) **NEW**
    Tier 3: Lightweight classifier (5s cold start)
    Tier 4: Full SLM reasoning (12s cold start)

Integration modes:
- Standalone: HTTP API only (CORTEX_ENABLED=false)
- Cortex: Redis Streams + HTTP API (CORTEX_ENABLED=true)
"""

import asyncio
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog

from cortex_integration import CortexClient, CortexConfig, CortexMessage, AgentStatus
from qdrant_learning import (
    QdrantLearningClient,
    QdrantConfig,
    RoutingDecision,
    RoutingOutcome,
    RouteType,
    SimilarRoute,
    generate_query_id,
    generate_outcome_id,
)
from mode_switching import (
    analyze_query,
    score_complexity,
    should_escalate,
    QueryMode,
    ComplexityLevel,
    EscalationReason,
    EscalationContext,
    ModeDecision,
)

# =============================================================================
# Configuration
# =============================================================================

@dataclass
class LayerConfig:
    name: str
    endpoint: str
    health_path: str
    timeout: int = 30


@dataclass 
class RoutingRule:
    pattern: str
    tool: str
    execution: str  # "api" or "ssh"
    requires_confirmation: bool = False
    compiled: Optional[re.Pattern] = None
    
    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE)


# =============================================================================
# Metrics
# =============================================================================

QUERIES_TOTAL = Counter(
    'cortex_activator_queries_total',
    'Total queries received',
    ['route_type', 'layer']
)

COLD_STARTS_TOTAL = Counter(
    'cortex_activator_cold_starts_total',
    'Cold starts triggered',
    ['layer']
)

COLD_START_DURATION = Histogram(
    'cortex_activator_cold_start_seconds',
    'Cold start duration',
    ['layer'],
    buckets=[1, 2, 5, 10, 15, 20, 30, 45, 60]
)

PENDING_REQUESTS = Gauge(
    'cortex_activator_pending_requests',
    'Pending requests waiting for layer',
    ['layer']
)

LAYER_STATUS = Gauge(
    'cortex_activator_layer_up',
    'Layer health status',
    ['layer']
)

# Qdrant learning metrics
SIMILARITY_LOOKUPS = Counter(
    'cortex_activator_similarity_lookups_total',
    'Qdrant similarity lookups',
    ['result']  # hit, miss, error
)

SIMILARITY_LATENCY = Histogram(
    'cortex_activator_similarity_latency_seconds',
    'Qdrant similarity lookup latency',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

ROUTING_STORED = Counter(
    'cortex_activator_routing_stored_total',
    'Routing decisions stored to Qdrant',
    ['route_type']
)

OUTCOMES_STORED = Counter(
    'cortex_activator_outcomes_stored_total',
    'Routing outcomes stored to Qdrant',
    ['success']
)

FEEDBACK_RECEIVED = Counter(
    'cortex_activator_feedback_total',
    'User feedback received',
    ['feedback_type']  # positive, negative, correction
)

# Mode switching metrics (Phase 4)
MODE_DECISIONS = Counter(
    'cortex_activator_mode_decisions_total',
    'Query mode decisions',
    ['mode', 'complexity']  # mode: llm/agent/hybrid, complexity: simple/moderate/complex/expert
)

COMPLEXITY_SCORES = Histogram(
    'cortex_activator_complexity_score',
    'Query complexity scores',
    buckets=[10, 25, 40, 50, 60, 75, 90, 100]
)

ESCALATIONS = Counter(
    'cortex_activator_escalations_total',
    'Query escalations to higher modes',
    ['reason']  # low_confidence, previous_failure, etc.
)


# =============================================================================
# Models
# =============================================================================

class QueryRequest(BaseModel):
    query: str
    context: Optional[dict] = None
    site: str = "default"


class QueryResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    layers_activated: list[str] = []
    latency_ms: int = 0
    cold_starts: list[str] = []
    # Learning metadata
    query_id: Optional[str] = None  # For tracking/feedback
    route_type: Optional[str] = None  # keyword, similarity, classifier, slm
    route_confidence: Optional[float] = None  # How confident we are in the routing
    # Mode switching metadata (Phase 4)
    query_mode: Optional[str] = None  # llm, agent, hybrid
    complexity_level: Optional[str] = None  # simple, moderate, complex, expert
    complexity_score: Optional[int] = None  # 0-100
    recommended_model: Optional[str] = None  # haiku, sonnet, opus
    escalation_reason: Optional[str] = None  # If escalated, why


class FeedbackRequest(BaseModel):
    """User feedback on a query response."""
    query_id: str  # From QueryResponse
    feedback: str  # "positive", "negative", "wrong_tool", "wrong_result"
    correct_tool: Optional[str] = None  # If wrong_tool, what should it have been?
    comment: Optional[str] = None  # Free-form feedback


class FeedbackResponse(BaseModel):
    """Response to feedback submission."""
    accepted: bool
    message: str


class LayerState(Enum):
    COLD = "cold"
    WARMING = "warming"
    WARM = "warm"
    UNHEALTHY = "unhealthy"


# =============================================================================
# Layer Manager
# =============================================================================

class LayerManager:
    """Manages layer health checks and wake-up."""
    
    def __init__(self, layers: dict[str, LayerConfig]):
        self.layers = layers
        self.states: dict[str, LayerState] = {
            name: LayerState.COLD for name in layers
        }
        self.http = httpx.AsyncClient(timeout=5.0)
        self.log = structlog.get_logger()
    
    async def check_health(self, layer_name: str) -> LayerState:
        """Check if a layer is healthy."""
        config = self.layers.get(layer_name)
        if not config:
            return LayerState.UNHEALTHY
        
        try:
            resp = await self.http.get(f"{config.endpoint}{config.health_path}")
            if resp.status_code == 200:
                self.states[layer_name] = LayerState.WARM
                LAYER_STATUS.labels(layer=layer_name).set(1)
                return LayerState.WARM
        except httpx.RequestError:
            pass
        
        self.states[layer_name] = LayerState.COLD
        LAYER_STATUS.labels(layer=layer_name).set(0)
        return LayerState.COLD
    
    async def wait_for_ready(
        self, 
        layer_name: str, 
        timeout: int = 60,
        poll_interval: float = 1.0
    ) -> bool:
        """Wait for a layer to become ready after wake-up."""
        config = self.layers.get(layer_name)
        if not config:
            return False
        
        self.states[layer_name] = LayerState.WARMING
        start = time.time()
        COLD_STARTS_TOTAL.labels(layer=layer_name).inc()
        PENDING_REQUESTS.labels(layer=layer_name).inc()
        
        try:
            while time.time() - start < timeout:
                state = await self.check_health(layer_name)
                if state == LayerState.WARM:
                    duration = time.time() - start
                    COLD_START_DURATION.labels(layer=layer_name).observe(duration)
                    self.log.info(
                        "layer_ready",
                        layer=layer_name,
                        duration_seconds=round(duration, 2)
                    )
                    return True
                await asyncio.sleep(poll_interval)
            
            self.log.warning("layer_timeout", layer=layer_name, timeout=timeout)
            return False
        finally:
            PENDING_REQUESTS.labels(layer=layer_name).dec()
    
    async def ensure_ready(self, layer_name: str) -> bool:
        """Ensure a layer is ready, waiting if necessary."""
        state = await self.check_health(layer_name)
        
        if state == LayerState.WARM:
            return True
        
        if state == LayerState.COLD:
            # KEDA will auto-wake based on metrics, we just need to wait
            return await self.wait_for_ready(layer_name)
        
        return False


# =============================================================================
# Query Router
# =============================================================================

class QueryRouter:
    """Routes queries to appropriate layers based on content."""
    
    def __init__(self, rules: list[RoutingRule]):
        self.rules = rules
        self.log = structlog.get_logger()
    
    def classify(self, query: str) -> Optional[RoutingRule]:
        """Find matching routing rule for a query."""
        query_lower = query.lower()
        
        for rule in self.rules:
            if rule.compiled and rule.compiled.search(query_lower):
                self.log.debug(
                    "route_matched",
                    query=query[:50],
                    pattern=rule.pattern,
                    tool=rule.tool
                )
                return rule
        
        return None
    
    def needs_reasoning(self, query: str) -> bool:
        """Check if query requires LLM reasoning."""
        complexity_keywords = [
            "why", "investigate", "analyze", "figure out",
            "what's wrong", "troubleshoot", "explain", "help me understand"
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in complexity_keywords)


# =============================================================================
# Cortex Integration
# =============================================================================

CORTEX_ENABLED = os.getenv("CORTEX_ENABLED", "true").lower() == "true"
cortex_client: Optional[CortexClient] = None

# =============================================================================
# Qdrant Learning Integration
# =============================================================================

LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "true").lower() == "true"
qdrant_learning: Optional[QdrantLearningClient] = None


async def handle_cortex_task(message: CortexMessage) -> dict:
    """
    Handle a task from Cortex master via Redis Streams.

    Translates Cortex message format to internal query format
    and processes via the same routing logic as HTTP requests.
    """
    start = time.time()

    # Extract query from Cortex message payload
    query = message.payload.get("query", "")
    site = message.payload.get("site", "default")
    context = message.payload.get("context", {})

    log.info(
        "cortex_task_processing",
        task_type=message.task_type,
        query=query[:100]
    )

    # Create internal request
    request = QueryRequest(query=query, site=site, context=context)

    # Process using existing routing logic
    response = await process_query_internal(request)

    latency_ms = int((time.time() - start) * 1000)

    return {
        "success": response.success,
        "result": response.result,
        "error": response.error,
        "layers_activated": response.layers_activated,
        "cold_starts": response.cold_starts,
        "latency_ms": latency_ms,
    }


# =============================================================================
# FastAPI Application
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global cortex_client, qdrant_learning

    log.info("activator_starting", cortex_enabled=CORTEX_ENABLED, learning_enabled=LEARNING_ENABLED)

    # Initialize Qdrant learning layer
    if LEARNING_ENABLED:
        qdrant_config = QdrantConfig.from_env()
        qdrant_learning = QdrantLearningClient(qdrant_config)
        if await qdrant_learning.initialize():
            log.info("qdrant_learning_active", url=qdrant_config.url)
        else:
            log.warning("qdrant_learning_failed_to_initialize")
            qdrant_learning = None

    # Check initial layer states
    for layer_name in LAYERS:
        state = await layer_manager.check_health(layer_name)
        log.info("layer_initial_state", layer=layer_name, state=state.value)

    # Start Cortex integration if enabled
    if CORTEX_ENABLED:
        config = CortexConfig.from_env()
        cortex_client = CortexClient(config)
        await cortex_client.start(task_handler=handle_cortex_task)
        log.info(
            "cortex_integration_active",
            agent_id=config.agent_id,
            task_stream=config.task_stream
        )

    yield

    # Shutdown
    log.info("activator_shutdown_starting")

    if cortex_client:
        await cortex_client.stop()

    if qdrant_learning:
        await qdrant_learning.close()

    await layer_manager.http.aclose()
    log.info("activator_shutdown_complete")


app = FastAPI(
    title="Cortex Activator",
    description="Query router and layer orchestrator for UniFi Layer Fabric",
    version="0.1.0",
    lifespan=lifespan,
)

# These would be loaded from config in production
LAYERS = {
    "reasoning-classifier": LayerConfig(
        name="reasoning-classifier",
        endpoint="http://reasoning-classifier:8080",
        health_path="/health"
    ),
    "reasoning-slm": LayerConfig(
        name="reasoning-slm", 
        endpoint="http://reasoning-slm:8080",
        health_path="/health"
    ),
    "execution-unifi-api": LayerConfig(
        name="execution-unifi-api",
        endpoint="http://execution-unifi-api:8080",
        health_path="/health"
    ),
    "execution-unifi-ssh": LayerConfig(
        name="execution-unifi-ssh",
        endpoint="http://execution-unifi-ssh:8080",
        health_path="/health"
    ),
    "cortex-qdrant": LayerConfig(
        name="cortex-qdrant",
        endpoint="http://cortex-qdrant:6333",
        health_path="/"
    ),
    "cortex-telemetry": LayerConfig(
        name="cortex-telemetry",
        endpoint="http://cortex-telemetry:8080",
        health_path="/health"
    ),
}

ROUTING_RULES = [
    RoutingRule(r"(block|unblock).*client", "client_management", "api"),
    RoutingRule(r"(list|show|get).*client", "get_clients", "api"),
    RoutingRule(r"(restart|reboot).*device", "restart_device", "api", requires_confirmation=True),
    RoutingRule(r"(list|show|get).*device", "get_devices", "api"),
    RoutingRule(r"(create|add).*network", "create_network", "api", requires_confirmation=True),
    RoutingRule(r"(list|show|get).*network", "get_networks", "api"),
    RoutingRule(r"(diagnose|troubleshoot|debug)", "diagnostics", "ssh"),
    RoutingRule(r"(show|get).*(log|logs)", "get_logs", "ssh"),
]

layer_manager = LayerManager(LAYERS)
query_router = QueryRouter(ROUTING_RULES)
log = structlog.get_logger()


# =============================================================================
# Core Query Processing (used by both HTTP and Cortex)
# =============================================================================

async def process_query_internal(request: QueryRequest) -> QueryResponse:
    """
    Core query processing logic with learning-enabled routing cascade and mode switching.

    Phase 4 Integration:
        - Query complexity scoring determines routing approach
        - Mode detection (LLM/Agent/Hybrid) guides execution
        - Auto-escalation on low confidence or failure

    Routing Cascade (exit-early):
        Tier 1: Keyword pattern match (<10ms)
        Tier 2: Qdrant similarity search (<50ms) - LEARNS from past successes
        Tier 3: Lightweight classifier (5s cold start)
        Tier 4: Full SLM reasoning (12s cold start)

    After execution, stores routing decision and outcome for learning.
    """
    start = time.time()
    cold_starts = []
    layers_activated = []
    query_id = generate_query_id()
    route_type = None
    route_confidence = 0.0
    tool_selected = None
    exec_layer = None

    # Phase 4: Analyze query complexity and determine mode
    similar_success_rate = None
    mode_decision = analyze_query(
        query=request.query,
        context=request.context,
        similar_success_rate=similar_success_rate  # Will be populated after similarity check
    )

    # Track mode decision metrics
    MODE_DECISIONS.labels(
        mode=mode_decision.mode.value,
        complexity=mode_decision.complexity.level.value
    ).inc()
    COMPLEXITY_SCORES.observe(mode_decision.complexity.score)

    if mode_decision.escalation_reason:
        ESCALATIONS.labels(reason=mode_decision.escalation_reason.value).inc()

    log.info(
        "query_processing",
        query=request.query[:100],
        query_id=query_id,
        mode=mode_decision.mode.value,
        complexity=mode_decision.complexity.level.value,
        complexity_score=mode_decision.complexity.score
    )

    # =========================================================================
    # TIER 1: Keyword Pattern Match (fast path, <10ms)
    # =========================================================================
    rule = query_router.classify(request.query)

    if rule:
        route_type = RouteType.KEYWORD
        route_confidence = 0.95  # High confidence for pattern match
        tool_selected = rule.tool
        exec_layer = f"execution-unifi-{rule.execution}"

        QUERIES_TOTAL.labels(route_type="keyword", layer=exec_layer).inc()
        log.debug("route_tier1_keyword", tool=tool_selected, layer=exec_layer)

    # =========================================================================
    # TIER 2: Qdrant Similarity Search (<50ms) - Skip LLM if similar past success
    # =========================================================================
    if not rule and qdrant_learning:
        similarity_start = time.time()
        try:
            similar = await qdrant_learning.find_similar_route(request.query)
            similarity_latency = time.time() - similarity_start
            SIMILARITY_LATENCY.observe(similarity_latency)

            if similar:
                SIMILARITY_LOOKUPS.labels(result="hit").inc()
                route_type = RouteType.SIMILARITY
                route_confidence = similar.similarity * similar.success_rate
                tool_selected = similar.tool
                exec_layer = similar.execution_layer

                QUERIES_TOTAL.labels(route_type="similarity", layer=exec_layer).inc()
                log.info(
                    "route_tier2_similarity",
                    tool=tool_selected,
                    layer=exec_layer,
                    similarity=round(similar.similarity, 3),
                    success_rate=round(similar.success_rate, 2),
                    latency_ms=round(similarity_latency * 1000, 1)
                )
            else:
                SIMILARITY_LOOKUPS.labels(result="miss").inc()
        except Exception as e:
            SIMILARITY_LOOKUPS.labels(result="error").inc()
            log.warning("similarity_lookup_error", error=str(e))

    # =========================================================================
    # TIER 3/4: Reasoning Layers (if no keyword or similarity match)
    # =========================================================================
    if not exec_layer:
        # Check if query is complex enough for full SLM
        if query_router.needs_reasoning(request.query):
            reasoning_layer = "reasoning-slm"
            route_type = RouteType.SLM
        else:
            reasoning_layer = "reasoning-classifier"
            route_type = RouteType.CLASSIFIER

        exec_layer = reasoning_layer
        QUERIES_TOTAL.labels(route_type=route_type.value, layer=reasoning_layer).inc()
        log.debug("route_tier3_4_reasoning", layer=reasoning_layer)

    # =========================================================================
    # STORE ROUTING DECISION (before execution)
    # =========================================================================
    embedding = None
    if qdrant_learning and route_type:
        try:
            # Get embedding for storage (we'll need it anyway)
            embedding = await qdrant_learning._embedding.embed(request.query)

            decision = RoutingDecision(
                query_id=query_id,
                query_text=request.query,
                query_embedding=embedding,
                route_type=route_type,
                tool=tool_selected or "unknown",
                execution_layer=exec_layer,
                confidence=route_confidence,
                metadata={
                    "site": request.site,
                    "context_keys": list(request.context.keys()) if request.context else [],
                }
            )
            await qdrant_learning.store_routing(decision)
            ROUTING_STORED.labels(route_type=route_type.value).inc()
        except Exception as e:
            log.warning("store_routing_failed", error=str(e))

    # =========================================================================
    # EXECUTE: Wake layer and run
    # =========================================================================

    # Wake execution layer if needed
    if not await layer_manager.ensure_ready(exec_layer):
        latency_ms = int((time.time() - start) * 1000)
        # Store failed outcome
        await _store_outcome(query_id, False, latency_ms, "layer_unavailable")
        return QueryResponse(
            success=False,
            error=f"Layer {exec_layer} failed to become ready",
            latency_ms=latency_ms,
            query_id=query_id,
            route_type=route_type.value if route_type else None,
            route_confidence=route_confidence,
            # Phase 4 metadata
            query_mode=mode_decision.mode.value,
            complexity_level=mode_decision.complexity.level.value,
            complexity_score=mode_decision.complexity.score,
            recommended_model=mode_decision.recommended_model,
            escalation_reason=mode_decision.escalation_reason.value if mode_decision.escalation_reason else None
        )

    if layer_manager.states[exec_layer] == LayerState.WARMING:
        cold_starts.append(exec_layer)
    layers_activated.append(exec_layer)

    # Execute based on layer type
    result = None
    error = None
    success = False

    try:
        if exec_layer.startswith("execution-unifi-"):
            # Direct execution layer
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{LAYERS[exec_layer].endpoint}/execute",
                    json={
                        "tool": tool_selected or "unknown",
                        "query": request.query,
                        "site": request.site,
                        "context": request.context
                    }
                )
                result = resp.json()
                success = resp.status_code == 200
        else:
            # Reasoning layer
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{LAYERS[exec_layer].endpoint}/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "user", "content": request.query}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500
                    }
                )
                reasoning_result = resp.json()
                result = {"message": "Query processed via reasoning layer", "reasoning": reasoning_result}
                success = True
                # TODO: Parse tool call from response and execute

    except Exception as e:
        log.error("execution_failed", layer=exec_layer, error=str(e))
        error = str(e)

        # Failover to SSH if API fails
        if exec_layer == "execution-unifi-api":
            log.info("failover_to_ssh", original_layer=exec_layer)
            # TODO: Implement SSH failover

    latency_ms = int((time.time() - start) * 1000)

    # =========================================================================
    # STORE OUTCOME (for learning)
    # =========================================================================
    error_type = None if success else ("tool_error" if error else "unknown")
    await _store_outcome(query_id, success, latency_ms, error_type)

    return QueryResponse(
        success=success,
        result=result,
        error=error,
        layers_activated=layers_activated,
        latency_ms=latency_ms,
        cold_starts=cold_starts,
        query_id=query_id,
        route_type=route_type.value if route_type else None,
        route_confidence=route_confidence,
        # Phase 4: Mode switching metadata
        query_mode=mode_decision.mode.value,
        complexity_level=mode_decision.complexity.level.value,
        complexity_score=mode_decision.complexity.score,
        recommended_model=mode_decision.recommended_model,
        escalation_reason=mode_decision.escalation_reason.value if mode_decision.escalation_reason else None
    )


async def _store_outcome(
    query_id: str,
    success: bool,
    latency_ms: int,
    error_type: Optional[str] = None
) -> None:
    """Store execution outcome for learning."""
    if not qdrant_learning:
        return

    try:
        outcome = RoutingOutcome(
            outcome_id=generate_outcome_id(),
            query_id=query_id,
            success=success,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        await qdrant_learning.store_outcome(outcome)
        OUTCOMES_STORED.labels(success=str(success).lower()).inc()
    except Exception as e:
        log.warning("store_outcome_failed", error=str(e))


# =============================================================================
# HTTP Endpoints
# =============================================================================

@app.get("/health")
async def health():
    """Basic health check - always responds if process is running."""
    return {"status": "healthy", "cortex_enabled": CORTEX_ENABLED}


@app.get("/ready")
async def ready():
    """Readiness check - verifies dependencies are available."""
    # Check that core dependencies are available
    qdrant_state = await layer_manager.check_health("cortex-qdrant")

    status = {
        "status": "ready" if qdrant_state == LayerState.WARM else "not_ready",
        "qdrant": qdrant_state.value,
        "cortex_enabled": CORTEX_ENABLED,
    }

    if cortex_client:
        status["cortex_status"] = cortex_client._status.value

    if qdrant_state != LayerState.WARM:
        raise HTTPException(503, detail=status)

    return status


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/status")
async def status():
    """Detailed status of all layers and Cortex integration."""
    layer_states = {}
    for layer_name in LAYERS:
        state = await layer_manager.check_health(layer_name)
        layer_states[layer_name] = state.value

    response = {
        "activator": "running",
        "cortex_enabled": CORTEX_ENABLED,
        "layers": layer_states,
    }

    if cortex_client:
        response["cortex"] = {
            "agent_id": cortex_client.config.agent_id,
            "status": cortex_client._status.value,
            "task_stream": cortex_client.config.task_stream,
            "capabilities": cortex_client.config.capabilities,
        }

    return response


@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    HTTP endpoint for query processing.

    This is the direct HTTP interface - same logic is also
    available via Cortex Redis Streams when CORTEX_ENABLED=true.
    """
    log.info("http_query_received", query=request.query[:100])
    return await process_query_internal(request)


@app.post("/feedback", response_model=FeedbackResponse)
async def handle_feedback(request: FeedbackRequest):
    """
    Submit feedback on a query response to improve routing.

    Feedback types:
    - "positive": The response was helpful/correct
    - "negative": The response was not helpful
    - "wrong_tool": The right tool wasn't used (provide correct_tool)
    - "wrong_result": The tool was right but result was wrong

    This feedback is stored and used to:
    1. Adjust success rates for similarity routing
    2. Learn correct tool mappings for future queries
    """
    global qdrant_learning

    if not qdrant_learning:
        return FeedbackResponse(
            accepted=False,
            message="Learning is disabled"
        )

    # Map feedback to internal representation
    feedback_map = {
        "positive": "helpful",
        "negative": "not_helpful",
        "wrong_tool": "wrong_tool",
        "wrong_result": "wrong_result"
    }

    if request.feedback not in feedback_map:
        return FeedbackResponse(
            accepted=False,
            message=f"Invalid feedback type. Use: {list(feedback_map.keys())}"
        )

    user_feedback = feedback_map[request.feedback]

    # Record the feedback
    try:
        success = await qdrant_learning.record_feedback(
            query_id=request.query_id,
            feedback=user_feedback
        )

        if success:
            FEEDBACK_RECEIVED.labels(feedback_type=request.feedback).inc()
            log.info(
                "feedback_recorded",
                query_id=request.query_id,
                feedback=request.feedback,
                correct_tool=request.correct_tool
            )
            return FeedbackResponse(
                accepted=True,
                message="Feedback recorded. Thank you!"
            )
        else:
            log.warning(
                "feedback_not_found",
                query_id=request.query_id
            )
            return FeedbackResponse(
                accepted=False,
                message=f"Query ID {request.query_id} not found"
            )

    except Exception as e:
        log.error("feedback_error", error=str(e), query_id=request.query_id)
        return FeedbackResponse(
            accepted=False,
            message="Error recording feedback"
        )


# =============================================================================
# Phase 4: Query Analysis Endpoint (for testing/debugging)
# =============================================================================

class AnalyzeRequest(BaseModel):
    """Request for query analysis without execution."""
    query: str
    context: Optional[dict] = None


class AnalyzeResponse(BaseModel):
    """Response from query analysis."""
    query_mode: str
    complexity_level: str
    complexity_score: int
    complexity_factors: dict
    complexity_reasoning: str
    confidence: float
    recommended_model: Optional[str]
    escalation_reason: Optional[str]
    would_route_to: Optional[str]  # Predicted routing layer


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_query_endpoint(request: AnalyzeRequest):
    """
    Analyze a query without executing it.

    Useful for:
    - Testing complexity scoring
    - Understanding mode detection
    - Debugging routing decisions
    - Tuning thresholds

    Returns detailed analysis including complexity factors and routing prediction.
    """
    # Analyze query
    mode_decision = analyze_query(
        query=request.query,
        context=request.context
    )

    # Predict routing (without executing)
    rule = query_router.classify(request.query)
    would_route_to = None

    if rule:
        would_route_to = f"execution-unifi-{rule.execution} (keyword: {rule.tool})"
    elif mode_decision.complexity.level in (ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT):
        would_route_to = "reasoning-slm"
    elif mode_decision.mode == QueryMode.LLM:
        would_route_to = "reasoning-classifier"
    else:
        would_route_to = "similarity-lookup → execution-unifi-api"

    return AnalyzeResponse(
        query_mode=mode_decision.mode.value,
        complexity_level=mode_decision.complexity.level.value,
        complexity_score=mode_decision.complexity.score,
        complexity_factors=mode_decision.complexity.factors,
        complexity_reasoning=mode_decision.complexity.reasoning,
        confidence=mode_decision.confidence,
        recommended_model=mode_decision.recommended_model,
        escalation_reason=mode_decision.escalation_reason.value if mode_decision.escalation_reason else None,
        would_route_to=would_route_to
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
