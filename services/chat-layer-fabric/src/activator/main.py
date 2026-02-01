"""
Chat Activator - Query Router and Layer Orchestrator for Chat Layer Fabric

This is the always-on brain of the Chat Layer Fabric. It:
1. Receives chat messages from users/APIs
2. Classifies intent and complexity (fast path, no LLM)
3. Routes based on Qdrant similarity (learned from past successes)
4. Wakes appropriate layers via KEDA
5. Proxies requests to execution layers
6. Handles escalation cascade (local -> DMR -> Claude Code)
7. Stores routing decisions and outcomes for learning

Intelligence Cascade (exit-early):
    Tier 0: Exact cache (recent identical query)
    Tier 1: Keyword pattern match (<10ms)
    Tier 2: Qdrant similarity search (<50ms)
    Tier 3: Local DMR reasoning (~500ms)
    Tier 4: Claude Code execution (~2-5s)
"""

import asyncio
import os
import re
import time
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog
import redis.asyncio as redis
import json

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
class RoutingConfig:
    """Configuration for routing decisions."""
    # Complexity thresholds (0-100)
    local_threshold: int = 50       # <50 = simple, use cached/pattern
    dmr_threshold: int = 75         # 50-75 = moderate, use local DMR
    claude_threshold: int = 100     # >75 = complex, use Claude Code

    # Similarity matching
    similarity_threshold: float = 0.92
    confidence_threshold: float = 0.85

    # Escalation triggers
    escalate_on_uncertain: bool = True
    escalate_on_tool_need: bool = True
    escalate_on_multi_step: bool = True

    @classmethod
    def from_env(cls) -> "RoutingConfig":
        return cls(
            local_threshold=int(os.getenv("LOCAL_THRESHOLD", "50")),
            dmr_threshold=int(os.getenv("DMR_THRESHOLD", "75")),
            claude_threshold=int(os.getenv("CLAUDE_THRESHOLD", "100")),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.92")),
            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.85")),
        )


# =============================================================================
# Enums
# =============================================================================

class RouteTier(str, Enum):
    CACHE = "cache"
    KEYWORD = "keyword"
    SIMILARITY = "similarity"
    DMR = "dmr"
    CLAUDE_CODE = "claude_code"


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"           # 0-30: Direct answer, no reasoning
    MODERATE = "moderate"       # 31-50: Some reasoning, single tool
    COMPLEX = "complex"         # 51-75: Multi-step, multiple tools
    AGENTIC = "agentic"         # 76-100: Full agentic workflow


class LayerState(Enum):
    COLD = "cold"
    WARMING = "warming"
    WARM = "warm"
    UNHEALTHY = "unhealthy"


# =============================================================================
# Metrics
# =============================================================================

QUERIES_TOTAL = Counter(
    'cortex_chat_queries_total',
    'Total chat queries received',
    ['tier', 'complexity']
)

ROUTING_LATENCY = Histogram(
    'cortex_chat_routing_latency_seconds',
    'Routing decision latency',
    ['tier'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

RESPONSE_LATENCY = Histogram(
    'cortex_chat_response_latency_seconds',
    'Total response latency',
    ['tier'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

COST_USD = Counter(
    'cortex_chat_cost_usd_total',
    'Estimated cost in USD',
    ['tier', 'model']
)

LAYER_STATUS = Gauge(
    'cortex_chat_layer_up',
    'Layer health status',
    ['layer']
)

COLD_STARTS = Counter(
    'cortex_chat_cold_starts_total',
    'Cold starts triggered',
    ['layer']
)

SIMILARITY_HITS = Counter(
    'cortex_chat_similarity_hits_total',
    'Successful similarity matches'
)

ESCALATIONS = Counter(
    'cortex_chat_escalations_total',
    'Query escalations to higher tier',
    ['from_tier', 'to_tier', 'reason']
)


# =============================================================================
# Models
# =============================================================================

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    user: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    conversation_id: str
    metadata: Dict[str, Any] = {}


class ComplexityScore(BaseModel):
    score: int  # 0-100
    level: ComplexityLevel
    factors: Dict[str, int]  # What contributed to the score
    reasoning: str


# =============================================================================
# Complexity Analyzer
# =============================================================================

class ComplexityAnalyzer:
    """Analyzes query complexity to determine routing tier."""

    # Patterns that indicate simple queries (low complexity)
    SIMPLE_PATTERNS = [
        (r"^(hi|hello|hey|thanks|thank you|ok|okay)[\s!.]*$", -30),
        (r"^what (is|are) (the )?(status|state) of", -20),
        (r"^(list|show|get|display) (all )?\w+$", -15),
        (r"^how many", -10),
        (r"^(yes|no|confirm|cancel)$", -25),
    ]

    # Patterns that indicate complex queries (high complexity)
    COMPLEX_PATTERNS = [
        (r"\b(investigate|analyze|debug|troubleshoot)\b", 25),
        (r"\b(fix|repair|resolve|correct)\b", 20),
        (r"\b(why|explain|understand)\b", 15),
        (r"\b(create|build|implement|deploy)\b", 20),
        (r"\b(compare|contrast|evaluate)\b", 15),
        (r"\b(optimize|improve|enhance)\b", 20),
        (r"\b(multiple|several|all|each)\b", 10),
        (r"\b(and then|after that|next)\b", 15),  # Multi-step indicators
        (r"\b(if|when|unless|otherwise)\b", 10),  # Conditional logic
    ]

    # Tool-requiring patterns
    TOOL_PATTERNS = [
        (r"\b(kubectl|helm|docker|git)\b", 20),
        (r"\b(pod|deployment|service|namespace)\b", 15),
        (r"\b(file|directory|code|script)\b", 15),
        (r"\b(api|endpoint|request|response)\b", 15),
        (r"\b(database|query|sql)\b", 15),
    ]

    def __init__(self):
        self.simple_compiled = [(re.compile(p, re.I), s) for p, s in self.SIMPLE_PATTERNS]
        self.complex_compiled = [(re.compile(p, re.I), s) for p, s in self.COMPLEX_PATTERNS]
        self.tool_compiled = [(re.compile(p, re.I), s) for p, s in self.TOOL_PATTERNS]
        self.log = structlog.get_logger()

    def analyze(self, query: str, context: Optional[Dict] = None) -> ComplexityScore:
        """Analyze query complexity and return a score."""
        base_score = 40  # Start at moderate
        factors = {}

        # Length factor
        word_count = len(query.split())
        if word_count < 5:
            factors["short_query"] = -10
            base_score -= 10
        elif word_count > 30:
            factors["long_query"] = 15
            base_score += 15
        elif word_count > 50:
            factors["very_long_query"] = 25
            base_score += 25

        # Simple pattern matching
        for pattern, adjustment in self.simple_compiled:
            if pattern.search(query):
                factors["simple_pattern"] = adjustment
                base_score += adjustment
                break  # Only apply first match

        # Complex pattern matching
        for pattern, adjustment in self.complex_compiled:
            if pattern.search(query):
                key = f"complex_{pattern.pattern[:20]}"
                factors[key] = adjustment
                base_score += adjustment

        # Tool-requiring patterns
        tool_score = 0
        for pattern, adjustment in self.tool_compiled:
            if pattern.search(query):
                tool_score += adjustment
        if tool_score > 0:
            factors["tool_required"] = min(tool_score, 30)
            base_score += min(tool_score, 30)

        # Question marks indicate inquiry (slightly more complex)
        if "?" in query:
            if query.count("?") > 1:
                factors["multiple_questions"] = 10
                base_score += 10

        # Context awareness
        if context:
            if context.get("previous_failure"):
                factors["retry_after_failure"] = 15
                base_score += 15
            if context.get("conversation_length", 0) > 5:
                factors["long_conversation"] = 10
                base_score += 10

        # Clamp score
        final_score = max(0, min(100, base_score))

        # Determine level
        if final_score <= 30:
            level = ComplexityLevel.SIMPLE
        elif final_score <= 50:
            level = ComplexityLevel.MODERATE
        elif final_score <= 75:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.AGENTIC

        # Generate reasoning
        top_factors = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        reasoning = f"Score {final_score} ({level.value})"
        if top_factors:
            reasoning += f" due to: {', '.join(f[0] for f in top_factors)}"

        return ComplexityScore(
            score=final_score,
            level=level,
            factors=factors,
            reasoning=reasoning
        )


# =============================================================================
# Intent Classifier
# =============================================================================

class IntentClassifier:
    """Fast keyword-based intent classification."""

    INTENTS = {
        "status_query": [
            r"(what|show|list|get).*(status|state|health)",
            r"(is|are).*(running|healthy|up|down)",
            r"(check|verify).*(status|health)",
        ],
        "list_query": [
            r"^(list|show|get|display)\s",
            r"what (are|is) (the|all)",
        ],
        "action_request": [
            r"(create|delete|update|restart|deploy)",
            r"(fix|repair|resolve|patch)",
            r"(add|remove|modify|change)",
        ],
        "investigation": [
            r"(why|how come|explain)",
            r"(investigate|analyze|debug|troubleshoot)",
            r"(what happened|what went wrong)",
        ],
        "help_request": [
            r"(help|assist|guide)",
            r"(how (do|can|should) i)",
            r"(what is|what are|what does)",
        ],
        "greeting": [
            r"^(hi|hello|hey|good morning|good afternoon|good evening)",
            r"^(thanks|thank you|cheers)",
        ],
        "confirmation": [
            r"^(yes|no|ok|okay|sure|confirm|cancel|abort)$",
        ],
    }

    def __init__(self):
        self.compiled = {
            intent: [re.compile(p, re.I) for p in patterns]
            for intent, patterns in self.INTENTS.items()
        }

    def classify(self, query: str) -> tuple[str, float]:
        """Classify query intent. Returns (intent, confidence)."""
        query_lower = query.lower().strip()

        for intent, patterns in self.compiled.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    # Higher confidence for more specific matches
                    confidence = 0.9 if intent in ["greeting", "confirmation"] else 0.75
                    return intent, confidence

        return "unknown", 0.5


# =============================================================================
# Layer Manager
# =============================================================================

class LayerManager:
    """Manages layer health checks and wake-up."""

    def __init__(self, layers: Dict[str, LayerConfig]):
        self.layers = layers
        self.states: Dict[str, LayerState] = {
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
        COLD_STARTS.labels(layer=layer_name).inc()

        while time.time() - start < timeout:
            state = await self.check_health(layer_name)
            if state == LayerState.WARM:
                duration = time.time() - start
                self.log.info(
                    "layer_ready",
                    layer=layer_name,
                    duration_seconds=round(duration, 2)
                )
                return True
            await asyncio.sleep(poll_interval)

        self.log.warning("layer_timeout", layer=layer_name, timeout=timeout)
        return False

    async def ensure_ready(self, layer_name: str) -> bool:
        """Ensure a layer is ready, waiting if necessary."""
        state = await self.check_health(layer_name)

        if state == LayerState.WARM:
            return True

        if state == LayerState.COLD:
            return await self.wait_for_ready(layer_name)

        return False

    async def close(self):
        await self.http.aclose()


# =============================================================================
# Query Cache
# =============================================================================

class QueryCache:
    """Simple in-memory cache for recent queries."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple[str, float]] = {}

    def _hash_query(self, query: str) -> str:
        """Create cache key from query."""
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, query: str) -> Optional[str]:
        """Get cached response if exists and not expired."""
        key = self._hash_query(query)
        if key in self.cache:
            response, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return response
            else:
                del self.cache[key]
        return None

    def set(self, query: str, response: str):
        """Cache a response."""
        # Evict oldest if full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]

        key = self._hash_query(query)
        self.cache[key] = (response, time.time())


# =============================================================================
# Chat Router
# =============================================================================

class ChatRouter:
    """Routes chat queries through the intelligence cascade."""

    def __init__(
        self,
        config: RoutingConfig,
        layer_manager: LayerManager,
        complexity_analyzer: ComplexityAnalyzer,
        intent_classifier: IntentClassifier,
        cache: QueryCache,
    ):
        self.config = config
        self.layers = layer_manager
        self.complexity = complexity_analyzer
        self.intent = intent_classifier
        self.cache = cache
        self.http = httpx.AsyncClient(timeout=60.0)
        self.log = structlog.get_logger()

        # Qdrant client (initialized async)
        self.qdrant_url = os.getenv("QDRANT_URL", "http://chat-qdrant:6333")
        self.qdrant_available = False

    async def initialize(self):
        """Initialize async components."""
        try:
            resp = await self.http.get(f"{self.qdrant_url}/readyz", timeout=5.0)
            self.qdrant_available = resp.status_code == 200
            self.log.info("qdrant_status", available=self.qdrant_available)
        except Exception as e:
            self.log.warning("qdrant_unavailable", error=str(e))

    async def route(self, request: ChatRequest) -> ChatResponse:
        """Route a chat request through the intelligence cascade."""
        start = time.time()
        query = request.message
        conversation_id = request.conversation_id or f"conv-{int(time.time())}"

        self.log.info(
            "routing_query",
            query=query[:100],
            conversation_id=conversation_id
        )

        # Analyze complexity first
        complexity = self.complexity.analyze(query, request.context)
        intent, intent_confidence = self.intent.classify(query)

        self.log.debug(
            "query_analyzed",
            complexity_score=complexity.score,
            complexity_level=complexity.level.value,
            intent=intent,
            intent_confidence=intent_confidence
        )

        # =======================================================================
        # TIER 0: Cache Check
        # =======================================================================
        cached_response = self.cache.get(query)
        if cached_response:
            latency = time.time() - start
            QUERIES_TOTAL.labels(tier="cache", complexity=complexity.level.value).inc()
            ROUTING_LATENCY.labels(tier="cache").observe(latency)

            return ChatResponse(
                success=True,
                response=cached_response,
                conversation_id=conversation_id,
                metadata={
                    "route_tier": "cache",
                    "latency_ms": int(latency * 1000),
                    "complexity_score": complexity.score,
                    "complexity_level": complexity.level.value,
                    "cost_usd": 0.0,
                }
            )

        # =======================================================================
        # TIER 1: Handle Simple Patterns
        # =======================================================================
        if intent == "greeting":
            response = await self._handle_greeting(query)
            latency = time.time() - start
            QUERIES_TOTAL.labels(tier="keyword", complexity="simple").inc()
            self.cache.set(query, response)

            return ChatResponse(
                success=True,
                response=response,
                conversation_id=conversation_id,
                metadata={
                    "route_tier": "keyword",
                    "intent": intent,
                    "latency_ms": int(latency * 1000),
                    "cost_usd": 0.0,
                }
            )

        if intent == "confirmation":
            # Handle confirmations based on conversation context
            response = "Understood. How can I help you further?"
            latency = time.time() - start
            QUERIES_TOTAL.labels(tier="keyword", complexity="simple").inc()

            return ChatResponse(
                success=True,
                response=response,
                conversation_id=conversation_id,
                metadata={
                    "route_tier": "keyword",
                    "intent": intent,
                    "latency_ms": int(latency * 1000),
                    "cost_usd": 0.0,
                }
            )

        # =======================================================================
        # TIER 2: Similarity Search (if Qdrant available)
        # =======================================================================
        if self.qdrant_available and complexity.score < self.config.dmr_threshold:
            similar_response = await self._find_similar(query)
            if similar_response:
                latency = time.time() - start
                QUERIES_TOTAL.labels(tier="similarity", complexity=complexity.level.value).inc()
                SIMILARITY_HITS.inc()
                self.cache.set(query, similar_response)

                return ChatResponse(
                    success=True,
                    response=similar_response,
                    conversation_id=conversation_id,
                    metadata={
                        "route_tier": "similarity",
                        "latency_ms": int(latency * 1000),
                        "complexity_score": complexity.score,
                        "cost_usd": 0.0,
                    }
                )

        # =======================================================================
        # TIER 3: Local DMR Reasoning
        # =======================================================================
        if complexity.score <= self.config.dmr_threshold:
            dmr_response = await self._route_to_dmr(query, request.context)
            if dmr_response:
                latency = time.time() - start
                QUERIES_TOTAL.labels(tier="dmr", complexity=complexity.level.value).inc()
                RESPONSE_LATENCY.labels(tier="dmr").observe(latency)
                self.cache.set(query, dmr_response)

                return ChatResponse(
                    success=True,
                    response=dmr_response,
                    conversation_id=conversation_id,
                    metadata={
                        "route_tier": "dmr",
                        "model_used": "phi-4",
                        "latency_ms": int(latency * 1000),
                        "complexity_score": complexity.score,
                        "cost_usd": 0.0,
                        "layers_activated": ["reasoning-dmr"],
                    }
                )

        # =======================================================================
        # TIER 4: Claude Code Execution
        # =======================================================================
        self.log.info(
            "escalating_to_claude_code",
            complexity_score=complexity.score,
            reason=complexity.reasoning
        )
        ESCALATIONS.labels(from_tier="dmr", to_tier="claude_code", reason="complexity").inc()

        claude_response = await self._route_to_claude_code(query, request.context)
        latency = time.time() - start
        QUERIES_TOTAL.labels(tier="claude_code", complexity=complexity.level.value).inc()
        RESPONSE_LATENCY.labels(tier="claude_code").observe(latency)

        # Estimate cost (rough: $0.003 per 1k input tokens, $0.015 per 1k output tokens)
        estimated_cost = 0.003  # Minimum charge
        COST_USD.labels(tier="claude_code", model="claude-sonnet").inc(estimated_cost)

        return ChatResponse(
            success=claude_response is not None,
            response=claude_response or "I encountered an issue processing your request.",
            conversation_id=conversation_id,
            metadata={
                "route_tier": "claude_code",
                "model_used": "claude-sonnet-4-20250514",
                "latency_ms": int(latency * 1000),
                "complexity_score": complexity.score,
                "complexity_level": complexity.level.value,
                "cost_usd": estimated_cost,
                "layers_activated": ["reasoning-dmr", "execution-claude-code"],
                "escalation_reason": complexity.reasoning,
            }
        )

    async def _handle_greeting(self, query: str) -> str:
        """Handle greeting messages."""
        greetings = [
            "Hello! I'm Cortex Chat, your AI infrastructure assistant. How can I help you today?",
            "Hi there! What would you like me to help you with?",
            "Hey! I'm here to help with your infrastructure needs. What's on your mind?",
        ]
        # Use query hash to get consistent greeting
        idx = hash(query) % len(greetings)
        return greetings[idx]

    async def _find_similar(self, query: str) -> Optional[str]:
        """Find similar past query in Qdrant."""
        try:
            # TODO: Implement actual Qdrant similarity search
            # This would embed the query and search for similar successful responses
            pass
        except Exception as e:
            self.log.warning("similarity_search_failed", error=str(e))
        return None

    async def _route_to_dmr(self, query: str, context: Optional[Dict]) -> Optional[str]:
        """Route query to Docker Model Runner for local inference."""
        try:
            # Ensure DMR layer is ready
            if not await self.layers.ensure_ready("reasoning-dmr"):
                self.log.warning("dmr_layer_not_ready")
                return None

            dmr_endpoint = os.getenv("DMR_ENDPOINT", "http://reasoning-dmr:8080")

            # Use OpenAI-compatible API
            resp = await self.http.post(
                f"{dmr_endpoint}/v1/chat/completions",
                json={
                    "model": "phi-4",
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are Cortex Chat, an AI infrastructure assistant.
You help users with Kubernetes, infrastructure, and DevOps tasks.
Be concise and helpful. If you don't know something, say so.
For complex tasks that require executing commands or making changes,
suggest what should be done but note you may need to escalate."""
                        },
                        {"role": "user", "content": query}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                },
                timeout=30.0
            )

            if resp.status_code == 200:
                result = resp.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            self.log.error("dmr_routing_failed", error=str(e))

        return None

    async def _route_to_claude_code(self, query: str, context: Optional[Dict]) -> Optional[str]:
        """Route query to Claude Code for complex/agentic tasks."""
        try:
            # Ensure Claude Code layer is ready
            if not await self.layers.ensure_ready("execution-claude-code"):
                self.log.warning("claude_code_layer_not_ready")
                return None

            claude_endpoint = os.getenv(
                "CLAUDE_CODE_ENDPOINT",
                "http://execution-claude-code:8080"
            )

            resp = await self.http.post(
                f"{claude_endpoint}/execute",
                json={
                    "query": query,
                    "context": context or {},
                    "mcp_servers": ["kubernetes", "cortex"],
                },
                timeout=120.0  # Claude Code tasks may take longer
            )

            if resp.status_code == 200:
                result = resp.json()
                return result.get("response")

        except Exception as e:
            self.log.error("claude_code_routing_failed", error=str(e))

        return None

    async def close(self):
        await self.http.aclose()


# =============================================================================
# FastAPI Application
# =============================================================================

log = structlog.get_logger()

# Layer configurations
LAYERS = {
    "chat-qdrant": LayerConfig(
        name="chat-qdrant",
        endpoint="http://chat-qdrant:6333",
        health_path="/readyz"
    ),
    "reasoning-dmr": LayerConfig(
        name="reasoning-dmr",
        endpoint="http://reasoning-dmr:8080",
        health_path="/health"
    ),
    "execution-local-response": LayerConfig(
        name="execution-local-response",
        endpoint="http://execution-local-response:8080",
        health_path="/health"
    ),
    "execution-claude-code": LayerConfig(
        name="execution-claude-code",
        endpoint="http://execution-claude-code:8080",
        health_path="/health"
    ),
    "chat-telemetry": LayerConfig(
        name="chat-telemetry",
        endpoint="http://chat-telemetry:8080",
        health_path="/health"
    ),
}

# Initialize components
layer_manager = LayerManager(LAYERS)
complexity_analyzer = ComplexityAnalyzer()
intent_classifier = IntentClassifier()
query_cache = QueryCache()
routing_config = RoutingConfig.from_env()

router = ChatRouter(
    config=routing_config,
    layer_manager=layer_manager,
    complexity_analyzer=complexity_analyzer,
    intent_classifier=intent_classifier,
    cache=query_cache,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    log.info("chat_activator_starting")

    # Initialize router
    await router.initialize()

    # Check initial layer states
    for layer_name in LAYERS:
        state = await layer_manager.check_health(layer_name)
        log.info("layer_initial_state", layer=layer_name, state=state.value)

    yield

    # Shutdown
    log.info("chat_activator_shutdown")
    await router.close()
    await layer_manager.close()


app = FastAPI(
    title="Chat Activator",
    description="Query router and layer orchestrator for Chat Layer Fabric",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# HTTP Endpoints
# =============================================================================

@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy", "service": "chat-activator"}


@app.get("/ready")
async def ready():
    """Readiness check - verifies Qdrant is available."""
    qdrant_state = await layer_manager.check_health("chat-qdrant")

    status = {
        "status": "ready" if qdrant_state == LayerState.WARM else "not_ready",
        "qdrant": qdrant_state.value,
    }

    if qdrant_state != LayerState.WARM:
        raise HTTPException(503, detail=status)

    return status


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/status")
async def status():
    """Detailed status of all layers."""
    layer_states = {}
    for layer_name in LAYERS:
        state = await layer_manager.check_health(layer_name)
        layer_states[layer_name] = state.value

    return {
        "activator": "running",
        "layers": layer_states,
        "cache_size": len(query_cache.cache),
        "qdrant_available": router.qdrant_available,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint."""
    log.info("chat_request", message=request.message[:100])
    return await router.route(request)


@app.post("/analyze")
async def analyze(request: ChatRequest):
    """Analyze a query without executing it."""
    complexity = complexity_analyzer.analyze(request.message, request.context)
    intent, confidence = intent_classifier.classify(request.message)

    return {
        "complexity": {
            "score": complexity.score,
            "level": complexity.level.value,
            "factors": complexity.factors,
            "reasoning": complexity.reasoning,
        },
        "intent": {
            "type": intent,
            "confidence": confidence,
        },
        "predicted_tier": (
            "cache" if complexity.score < 20 else
            "dmr" if complexity.score <= routing_config.dmr_threshold else
            "claude_code"
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
