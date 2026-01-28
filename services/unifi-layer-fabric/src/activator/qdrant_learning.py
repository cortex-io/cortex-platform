"""
Qdrant Learning Layer for Cortex Activator

This module provides the learning foundation for adaptive query routing.
It stores query embeddings with routing decisions and outcomes to enable
similarity-based routing that improves over time.

Architecture:
    Query → Embed → Search similar → Route (or learn new)
         ↓
    Store in Qdrant: query_embedding + routing_decision + outcome
         ↓
    Future similar queries → reuse learned routing (skip LLM)

Collections:
    - routing_queries: Query embeddings with routing decisions
    - routing_outcomes: Links query to execution outcome for learning

Embedding Model: all-MiniLM-L6-v2 (384 dimensions)
    - Fast inference (~5ms per query)
    - Good semantic similarity for short queries
    - Small memory footprint
"""

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog

log = structlog.get_logger()


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class QdrantConfig:
    """Configuration for Qdrant learning layer."""
    url: str = "http://unifi-cortex-qdrant.cortex-unifi:6333"
    collection_queries: str = "routing_queries"
    collection_outcomes: str = "routing_outcomes"

    # Similarity thresholds
    similarity_threshold: float = 0.92  # Min score to reuse routing
    confidence_threshold: float = 0.85  # Min confidence for auto-routing

    # Learning parameters
    min_success_rate: float = 0.8  # Min success rate to trust a routing
    min_samples: int = 3  # Min samples before trusting a pattern

    # Embedding service (if using external)
    embedding_url: Optional[str] = None  # If None, use local model

    @classmethod
    def from_env(cls) -> "QdrantConfig":
        """Load configuration from environment."""
        return cls(
            url=os.getenv("QDRANT_URL", "http://unifi-cortex-qdrant.cortex-unifi:6333"),
            collection_queries=os.getenv("QDRANT_COLLECTION_QUERIES", "routing_queries"),
            collection_outcomes=os.getenv("QDRANT_COLLECTION_OUTCOMES", "routing_outcomes"),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.92")),
            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.85")),
            embedding_url=os.getenv("EMBEDDING_SERVICE_URL"),
        )


class RouteType(str, Enum):
    """How a query was routed."""
    CACHE = "cache"          # Exact cache hit
    KEYWORD = "keyword"      # Pattern match
    SIMILARITY = "similarity"  # Qdrant similarity
    CLASSIFIER = "classifier"  # Lightweight classifier
    SLM = "slm"              # Full reasoning


@dataclass
class RoutingDecision:
    """A routing decision to store/retrieve from Qdrant."""
    query_id: str
    query_text: str
    query_embedding: List[float]
    route_type: RouteType
    tool: str
    execution_layer: str  # api, ssh, reasoning-classifier, reasoning-slm
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingOutcome:
    """The outcome of a routed query."""
    outcome_id: str
    query_id: str  # Links to RoutingDecision
    success: bool
    latency_ms: int
    error_type: Optional[str] = None  # timeout, tool_error, layer_unavailable
    result_summary: Optional[str] = None
    user_feedback: Optional[str] = None  # positive, negative
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimilarRoute:
    """A similar past route found in Qdrant."""
    query_id: str
    query_text: str
    similarity: float
    route_type: RouteType
    tool: str
    execution_layer: str
    success_rate: float
    sample_count: int
    avg_latency_ms: float


# =============================================================================
# Embedding Client
# =============================================================================

class EmbeddingClient:
    """
    Client for generating query embeddings.

    Uses sentence-transformers locally or can call external embedding service.
    """

    def __init__(self, config: QdrantConfig):
        self.config = config
        self._model = None
        self._http = httpx.AsyncClient(timeout=10.0)

    async def initialize(self) -> None:
        """Initialize the embedding model."""
        if self.config.embedding_url:
            log.info("embedding_client_external", url=self.config.embedding_url)
        else:
            # Lazy load sentence-transformers to avoid startup delay
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer('all-MiniLM-L6-v2')
                log.info("embedding_client_local", model="all-MiniLM-L6-v2")
            except ImportError:
                log.warning("sentence_transformers_not_available")
                # Will fall back to simple hash-based pseudo-embeddings

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self.config.embedding_url:
            return await self._embed_remote(text)
        elif self._model:
            return await self._embed_local(text)
        else:
            return self._embed_fallback(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if self.config.embedding_url:
            return [await self._embed_remote(t) for t in texts]
        elif self._model:
            return await self._embed_local_batch(texts)
        else:
            return [self._embed_fallback(t) for t in texts]

    async def _embed_remote(self, text: str) -> List[float]:
        """Get embedding from external service."""
        try:
            resp = await self._http.post(
                f"{self.config.embedding_url}/embed",
                json={"text": text}
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as e:
            log.error("embedding_remote_error", error=str(e))
            return self._embed_fallback(text)

    async def _embed_local(self, text: str) -> List[float]:
        """Get embedding from local model."""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self._model.encode(text, convert_to_numpy=True).tolist()
        )
        return embedding

    async def _embed_local_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from local model in batch."""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._model.encode(texts, convert_to_numpy=True).tolist()
        )
        return embeddings

    def _embed_fallback(self, text: str) -> List[float]:
        """
        Fallback pseudo-embedding based on text hash.
        Not semantically meaningful, but allows basic deduplication.
        """
        import hashlib
        # Create deterministic pseudo-random embedding from hash
        h = hashlib.sha384(text.lower().encode()).digest()
        # Convert bytes to floats in [-1, 1]
        embedding = [(b - 128) / 128.0 for b in h]
        return embedding

    async def close(self) -> None:
        """Close HTTP client."""
        await self._http.aclose()


# =============================================================================
# Qdrant Learning Client
# =============================================================================

class QdrantLearningClient:
    """
    Client for Qdrant-based query routing learning.

    Provides:
    - Similarity search for past successful routes
    - Storage of new routing decisions and outcomes
    - Success rate calculation for routing patterns
    - Learning from user feedback
    """

    def __init__(self, config: QdrantConfig):
        self.config = config
        self._http = httpx.AsyncClient(timeout=30.0)
        self._embedding = EmbeddingClient(config)
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the learning client."""
        try:
            # Check Qdrant connectivity
            resp = await self._http.get(f"{self.config.url}/readyz")
            if resp.status_code != 200:
                log.warning("qdrant_not_ready", status=resp.status_code)
                return False

            # Initialize embedding client
            await self._embedding.initialize()

            # Verify collections exist
            for collection in [self.config.collection_queries, self.config.collection_outcomes]:
                resp = await self._http.get(f"{self.config.url}/collections/{collection}")
                if resp.status_code != 200:
                    log.warning("qdrant_collection_missing", collection=collection)
                    # Collections will be created by init job

            self._initialized = True
            log.info("qdrant_learning_initialized", url=self.config.url)
            return True

        except Exception as e:
            log.error("qdrant_learning_init_error", error=str(e))
            return False

    # -------------------------------------------------------------------------
    # Similarity Search
    # -------------------------------------------------------------------------

    async def find_similar_route(
        self,
        query: str,
        min_success_rate: Optional[float] = None,
    ) -> Optional[SimilarRoute]:
        """
        Find a similar past route for the query.

        Returns the best matching route if:
        - Similarity > threshold
        - Success rate > min_success_rate
        - Sample count > min_samples

        Args:
            query: The user query to route
            min_success_rate: Minimum success rate to trust (default from config)

        Returns:
            SimilarRoute if found, None otherwise
        """
        if not self._initialized:
            return None

        min_success = min_success_rate or self.config.min_success_rate

        try:
            # Embed the query
            start = time.time()
            embedding = await self._embedding.embed(query)
            embed_time = (time.time() - start) * 1000

            # Search Qdrant
            search_start = time.time()
            resp = await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_queries}/points/search",
                json={
                    "vector": embedding,
                    "limit": 5,
                    "with_payload": True,
                    "score_threshold": self.config.similarity_threshold,
                    "filter": {
                        "must": [
                            {"key": "success", "match": {"value": True}}
                        ]
                    }
                }
            )
            search_time = (time.time() - search_start) * 1000

            if resp.status_code != 200:
                log.warning("qdrant_search_error", status=resp.status_code)
                return None

            results = resp.json().get("result", [])

            if not results:
                log.debug(
                    "no_similar_route_found",
                    query=query[:50],
                    embed_ms=round(embed_time, 1),
                    search_ms=round(search_time, 1)
                )
                return None

            # Find best result with sufficient success rate
            for result in results:
                payload = result.get("payload", {})
                success_rate = payload.get("success_rate", 0)
                sample_count = payload.get("sample_count", 0)

                if success_rate >= min_success and sample_count >= self.config.min_samples:
                    similar = SimilarRoute(
                        query_id=payload.get("query_id", str(result.get("id"))),
                        query_text=payload.get("query_text", ""),
                        similarity=result.get("score", 0),
                        route_type=RouteType(payload.get("route_type", "similarity")),
                        tool=payload.get("tool", ""),
                        execution_layer=payload.get("execution_layer", ""),
                        success_rate=success_rate,
                        sample_count=sample_count,
                        avg_latency_ms=payload.get("avg_latency_ms", 0),
                    )

                    log.info(
                        "similar_route_found",
                        query=query[:50],
                        similarity=round(similar.similarity, 3),
                        tool=similar.tool,
                        success_rate=round(similar.success_rate, 2),
                        samples=similar.sample_count,
                        embed_ms=round(embed_time, 1),
                        search_ms=round(search_time, 1)
                    )
                    return similar

            log.debug(
                "similar_routes_insufficient",
                query=query[:50],
                candidates=len(results),
                min_success=min_success
            )
            return None

        except Exception as e:
            log.error("find_similar_route_error", error=str(e), query=query[:50])
            return None

    # -------------------------------------------------------------------------
    # Store Routing Decision
    # -------------------------------------------------------------------------

    async def store_routing(self, decision: RoutingDecision) -> bool:
        """
        Store a routing decision in Qdrant.

        This is called after a query is routed, before execution.
        The outcome will be linked later via store_outcome().
        """
        if not self._initialized:
            return False

        try:
            point = {
                "id": decision.query_id,
                "vector": decision.query_embedding,
                "payload": {
                    "query_id": decision.query_id,
                    "query_text": decision.query_text,
                    "route_type": decision.route_type.value,
                    "tool": decision.tool,
                    "execution_layer": decision.execution_layer,
                    "confidence": decision.confidence,
                    "timestamp": decision.timestamp.isoformat(),
                    "success": None,  # Updated by outcome
                    "success_rate": 0.0,
                    "sample_count": 1,
                    "avg_latency_ms": 0,
                    **decision.metadata,
                }
            }

            resp = await self._http.put(
                f"{self.config.url}/collections/{self.config.collection_queries}/points",
                json={"points": [point]},
                params={"wait": "true"}
            )

            if resp.status_code not in [200, 201]:
                log.warning("store_routing_error", status=resp.status_code)
                return False

            log.debug(
                "routing_stored",
                query_id=decision.query_id,
                route_type=decision.route_type.value,
                tool=decision.tool
            )
            return True

        except Exception as e:
            log.error("store_routing_error", error=str(e))
            return False

    # -------------------------------------------------------------------------
    # Store Outcome
    # -------------------------------------------------------------------------

    async def store_outcome(self, outcome: RoutingOutcome) -> bool:
        """
        Store the outcome of a routed query.

        This updates the routing_queries point with success/latency
        and stores a detailed outcome record.
        """
        if not self._initialized:
            return False

        try:
            # Update the routing_queries point
            await self._update_routing_stats(outcome)

            # Store detailed outcome
            outcome_point = {
                "id": outcome.outcome_id,
                "vector": [0.0] * 384,  # Placeholder - outcomes don't need similarity search
                "payload": {
                    "outcome_id": outcome.outcome_id,
                    "query_id": outcome.query_id,
                    "success": outcome.success,
                    "latency_ms": outcome.latency_ms,
                    "error_type": outcome.error_type,
                    "result_summary": outcome.result_summary,
                    "user_feedback": outcome.user_feedback,
                    "timestamp": outcome.timestamp.isoformat(),
                }
            }

            resp = await self._http.put(
                f"{self.config.url}/collections/{self.config.collection_outcomes}/points",
                json={"points": [outcome_point]},
                params={"wait": "true"}
            )

            if resp.status_code not in [200, 201]:
                log.warning("store_outcome_error", status=resp.status_code)
                return False

            log.debug(
                "outcome_stored",
                query_id=outcome.query_id,
                success=outcome.success,
                latency_ms=outcome.latency_ms
            )
            return True

        except Exception as e:
            log.error("store_outcome_error", error=str(e))
            return False

    async def _update_routing_stats(self, outcome: RoutingOutcome) -> None:
        """Update success rate and latency stats for a routing."""
        try:
            # Get current stats
            resp = await self._http.get(
                f"{self.config.url}/collections/{self.config.collection_queries}/points/{outcome.query_id}"
            )

            if resp.status_code != 200:
                return

            point = resp.json().get("result", {})
            payload = point.get("payload", {})

            # Calculate new stats
            old_count = payload.get("sample_count", 0)
            old_success_rate = payload.get("success_rate", 0)
            old_avg_latency = payload.get("avg_latency_ms", 0)

            new_count = old_count + 1
            new_success_rate = ((old_success_rate * old_count) + (1 if outcome.success else 0)) / new_count
            new_avg_latency = ((old_avg_latency * old_count) + outcome.latency_ms) / new_count

            # Update payload
            await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_queries}/points/payload",
                json={
                    "points": [outcome.query_id],
                    "payload": {
                        "success": outcome.success,
                        "success_rate": new_success_rate,
                        "sample_count": new_count,
                        "avg_latency_ms": new_avg_latency,
                    }
                }
            )

        except Exception as e:
            log.error("update_routing_stats_error", error=str(e))

    # -------------------------------------------------------------------------
    # User Feedback
    # -------------------------------------------------------------------------

    async def record_feedback(
        self,
        query_id: str,
        feedback: str  # positive, negative
    ) -> bool:
        """
        Record user feedback for a routing decision.

        Positive feedback increases success rate confidence.
        Negative feedback decreases it and may trigger re-learning.
        """
        if not self._initialized:
            return False

        try:
            # Find the outcome for this query
            resp = await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_outcomes}/points/scroll",
                json={
                    "filter": {
                        "must": [
                            {"key": "query_id", "match": {"value": query_id}}
                        ]
                    },
                    "limit": 1,
                    "with_payload": True
                }
            )

            if resp.status_code != 200:
                return False

            points = resp.json().get("result", {}).get("points", [])
            if not points:
                return False

            # Update feedback
            outcome_id = points[0].get("id")
            await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_outcomes}/points/payload",
                json={
                    "points": [outcome_id],
                    "payload": {"user_feedback": feedback}
                }
            )

            # Adjust routing success rate based on feedback
            if feedback == "negative":
                # Decrease success rate to reduce future reuse
                await self._http.post(
                    f"{self.config.url}/collections/{self.config.collection_queries}/points/payload",
                    json={
                        "points": [query_id],
                        "payload": {"success_rate_adjustment": -0.1}
                    }
                )

            log.info("feedback_recorded", query_id=query_id, feedback=feedback)
            return True

        except Exception as e:
            log.error("record_feedback_error", error=str(e))
            return False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def close(self) -> None:
        """Close the client."""
        await self._http.aclose()
        await self._embedding.close()
        log.info("qdrant_learning_closed")


# =============================================================================
# Helper Functions
# =============================================================================

def generate_query_id() -> str:
    """Generate a unique query ID (UUID format for Qdrant compatibility)."""
    return str(uuid.uuid4())


def generate_outcome_id() -> str:
    """Generate a unique outcome ID (UUID format for Qdrant compatibility)."""
    return str(uuid.uuid4())
