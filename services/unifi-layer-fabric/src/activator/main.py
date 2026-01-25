"""
Cortex Activator - Query Router and Layer Orchestrator

This is the always-on brain of the Layer Fabric. It:
1. Receives queries from users/APIs (HTTP) OR Cortex master (Redis Streams)
2. Routes based on keywords (fast path, no LLM)
3. Wakes appropriate layers via KEDA
4. Proxies requests to execution layers
5. Handles failover (API → SSH)
6. Reports results back to Cortex via Redis Streams

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
from enum import Enum
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog

from cortex_integration import CortexClient, CortexConfig, CortexMessage, AgentStatus

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
    global cortex_client

    log.info("activator_starting", cortex_enabled=CORTEX_ENABLED)

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
    Core query processing logic.

    This function handles the actual routing and execution,
    used by both HTTP endpoint and Cortex task handler.
    """
    start = time.time()
    cold_starts = []
    layers_activated = []

    log.info("query_processing", query=request.query[:100])

    # Step 1: Try keyword routing (fast path)
    rule = query_router.classify(request.query)

    if rule:
        QUERIES_TOTAL.labels(route_type="keyword", layer=f"execution-unifi-{rule.execution}").inc()

        # Determine execution layer
        exec_layer = f"execution-unifi-{rule.execution}"

        # Wake execution layer if needed
        if not await layer_manager.ensure_ready(exec_layer):
            return QueryResponse(
                success=False,
                error=f"Layer {exec_layer} failed to become ready",
                latency_ms=int((time.time() - start) * 1000)
            )

        if layer_manager.states[exec_layer] == LayerState.WARMING:
            cold_starts.append(exec_layer)
        layers_activated.append(exec_layer)

        # Execute the action
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{LAYERS[exec_layer].endpoint}/execute",
                    json={
                        "tool": rule.tool,
                        "query": request.query,
                        "site": request.site,
                        "context": request.context
                    }
                )
                result = resp.json()
        except Exception as e:
            log.error("execution_failed", layer=exec_layer, error=str(e))

            # Failover to SSH if API fails
            if rule.execution == "api":
                log.info("failover_to_ssh", original_layer=exec_layer)
                # TODO: Implement SSH failover

            return QueryResponse(
                success=False,
                error=str(e),
                layers_activated=layers_activated,
                latency_ms=int((time.time() - start) * 1000),
                cold_starts=cold_starts
            )

        return QueryResponse(
            success=True,
            result=result,
            layers_activated=layers_activated,
            latency_ms=int((time.time() - start) * 1000),
            cold_starts=cold_starts
        )

    # Step 2: No keyword match - need reasoning
    QUERIES_TOTAL.labels(route_type="reasoning", layer="reasoning-slm").inc()

    # Check if query is complex enough for full SLM
    if query_router.needs_reasoning(request.query):
        reasoning_layer = "reasoning-slm"
    else:
        reasoning_layer = "reasoning-classifier"

    # Wake reasoning layer
    if not await layer_manager.ensure_ready(reasoning_layer):
        return QueryResponse(
            success=False,
            error=f"Layer {reasoning_layer} failed to become ready",
            latency_ms=int((time.time() - start) * 1000)
        )

    if layer_manager.states[reasoning_layer] == LayerState.WARMING:
        cold_starts.append(reasoning_layer)
    layers_activated.append(reasoning_layer)

    # Get tool selection from reasoning layer
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LAYERS[reasoning_layer].endpoint}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": request.query}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            reasoning_result = resp.json()
            # Parse tool call from response
            # TODO: Implement proper parsing
    except Exception as e:
        log.error("reasoning_failed", layer=reasoning_layer, error=str(e))
        return QueryResponse(
            success=False,
            error=str(e),
            layers_activated=layers_activated,
            latency_ms=int((time.time() - start) * 1000),
            cold_starts=cold_starts
        )

    return QueryResponse(
        success=True,
        result={"message": "Query processed via reasoning layer"},
        layers_activated=layers_activated,
        latency_ms=int((time.time() - start) * 1000),
        cold_starts=cold_starts
    )


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
