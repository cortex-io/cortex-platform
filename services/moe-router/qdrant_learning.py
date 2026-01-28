"""
Qdrant Learning Layer for MoE Router

This module provides the learning foundation for expert routing and
improvement evaluation. It stores query embeddings with routing decisions
to enable similarity-based routing that improves over time.

Collections:
    - expert_routing: Query embeddings with expert assignments
    - improvement_evaluations: Evaluation outcomes for learning

Key Insight: Some queries consistently route to the same expert domain.
By learning from past successful routings, we can skip the LLM-based
classification for common query patterns.
"""

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

try:
    import structlog
    log = structlog.get_logger()
except ImportError:
    import logging
    log = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class QdrantConfig:
    """Configuration for Qdrant learning layer."""
    url: str = "http://cortex-qdrant.cortex-system:6333"
    collection_routing: str = "expert_routing"
    collection_evaluations: str = "improvement_evaluations"

    # Similarity thresholds
    similarity_threshold: float = 0.75
    confidence_threshold: float = 0.80

    # Learning parameters
    min_success_rate: float = 0.8
    min_samples: int = 3

    @classmethod
    def from_env(cls) -> "QdrantConfig":
        """Load configuration from environment."""
        return cls(
            url=os.getenv("QDRANT_URL", "http://cortex-qdrant.cortex-system:6333"),
            collection_routing=os.getenv("QDRANT_COLLECTION_ROUTING", "expert_routing"),
            collection_evaluations=os.getenv("QDRANT_COLLECTION_EVALUATIONS", "improvement_evaluations"),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.75")),
            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.80")),
        )


@dataclass
class ExpertRouting:
    """An expert routing decision to store/retrieve from Qdrant."""
    routing_id: str
    query_text: str
    query_embedding: List[float]
    expert: str  # general, infrastructure, security, automation, etc.
    routing_method: str  # llm, similarity, keyword
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationOutcome:
    """The outcome of an improvement evaluation."""
    outcome_id: str
    routing_id: str
    recommended_action: str  # auto_approve, review, reject
    priority: str  # high, medium, low
    success: bool  # Was the evaluation helpful?
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimilarRouting:
    """A similar past expert routing found in Qdrant."""
    routing_id: str
    query_preview: str
    similarity: float
    expert: str
    success_rate: float
    sample_count: int


# =============================================================================
# Embedding Client
# =============================================================================

class EmbeddingClient:
    """Client for generating query embeddings."""

    def __init__(self, config: QdrantConfig):
        self.config = config
        self._model = None
        self._http = httpx.AsyncClient(timeout=10.0)
        self._embedding_url = os.getenv("EMBEDDING_SERVICE_URL")

    async def initialize(self) -> None:
        """Initialize the embedding model."""
        if self._embedding_url:
            log.info("embedding_client_external", url=self._embedding_url)
        else:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer('all-MiniLM-L6-v2')
                log.info("embedding_client_local", model="all-MiniLM-L6-v2")
            except ImportError:
                log.warning("sentence_transformers_not_available")

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self._embedding_url:
            return await self._embed_remote(text)
        elif self._model:
            return await self._embed_local(text)
        else:
            return self._embed_fallback(text)

    async def _embed_remote(self, text: str) -> List[float]:
        """Get embedding from external service."""
        try:
            resp = await self._http.post(
                f"{self._embedding_url}/embed",
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

    def _embed_fallback(self, text: str) -> List[float]:
        """Fallback pseudo-embedding based on text hash."""
        import hashlib
        h = hashlib.sha384(text.lower().encode()).digest()
        embedding = [(b - 128) / 128.0 for b in h]
        return embedding

    async def close(self) -> None:
        """Close HTTP client."""
        await self._http.aclose()


# =============================================================================
# Qdrant Learning Client
# =============================================================================

class QdrantLearningClient:
    """Client for Qdrant-based expert routing learning."""

    def __init__(self, config: QdrantConfig):
        self.config = config
        self._http = httpx.AsyncClient(timeout=30.0)
        self._embedding = EmbeddingClient(config)
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the learning client."""
        try:
            resp = await self._http.get(f"{self.config.url}/readyz")
            if resp.status_code != 200:
                log.warning("qdrant_not_ready", status=resp.status_code)
                return False

            await self._embedding.initialize()
            await self._ensure_collections()

            self._initialized = True
            log.info("qdrant_learning_initialized", url=self.config.url)
            return True

        except Exception as e:
            log.error("qdrant_learning_init_error", error=str(e))
            return False

    async def _ensure_collections(self) -> None:
        """Create collections if they don't exist."""
        for collection, vector_size in [
            (self.config.collection_routing, 384),
            (self.config.collection_evaluations, 384)
        ]:
            resp = await self._http.get(f"{self.config.url}/collections/{collection}")
            if resp.status_code == 404:
                await self._http.put(
                    f"{self.config.url}/collections/{collection}",
                    json={
                        "vectors": {"size": vector_size, "distance": "Cosine"},
                        "on_disk_payload": True
                    }
                )
                log.info("qdrant_collection_created", collection=collection)

    async def find_similar_routing(
        self,
        query: str,
    ) -> Optional[SimilarRouting]:
        """Find a similar past expert routing for the query."""
        if not self._initialized:
            return None

        try:
            embedding = await self._embedding.embed(query[:2000])

            resp = await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_routing}/points/search",
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

            if resp.status_code != 200:
                return None

            results = resp.json().get("result", [])
            if not results:
                return None

            for result in results:
                payload = result.get("payload", {})
                success_rate = payload.get("success_rate", 0)
                sample_count = payload.get("sample_count", 0)

                if success_rate >= self.config.min_success_rate and sample_count >= self.config.min_samples:
                    return SimilarRouting(
                        routing_id=payload.get("routing_id", str(result.get("id"))),
                        query_preview=payload.get("query_preview", "")[:100],
                        similarity=result.get("score", 0),
                        expert=payload.get("expert", "general"),
                        success_rate=success_rate,
                        sample_count=sample_count,
                    )

            return None

        except Exception as e:
            log.error("find_similar_routing_error", error=str(e))
            return None

    async def store_routing(self, routing: ExpertRouting) -> bool:
        """Store an expert routing decision in Qdrant."""
        if not self._initialized:
            return False

        try:
            point = {
                "id": routing.routing_id,
                "vector": routing.query_embedding,
                "payload": {
                    "routing_id": routing.routing_id,
                    "query_preview": routing.query_text[:200],
                    "expert": routing.expert,
                    "routing_method": routing.routing_method,
                    "confidence": routing.confidence,
                    "timestamp": routing.timestamp.isoformat(),
                    "success": None,
                    "success_rate": 0.0,
                    "sample_count": 1,
                    **routing.metadata,
                }
            }

            resp = await self._http.put(
                f"{self.config.url}/collections/{self.config.collection_routing}/points",
                json={"points": [point]},
                params={"wait": "true"}
            )

            return resp.status_code in [200, 201]

        except Exception as e:
            log.error("store_routing_error", error=str(e))
            return False

    async def store_evaluation_outcome(self, outcome: EvaluationOutcome) -> bool:
        """Store the outcome of an evaluation."""
        if not self._initialized:
            return False

        try:
            await self._update_routing_stats(outcome)

            outcome_point = {
                "id": outcome.outcome_id,
                "vector": [0.0] * 384,
                "payload": {
                    "outcome_id": outcome.outcome_id,
                    "routing_id": outcome.routing_id,
                    "recommended_action": outcome.recommended_action,
                    "priority": outcome.priority,
                    "success": outcome.success,
                    "timestamp": outcome.timestamp.isoformat(),
                }
            }

            resp = await self._http.put(
                f"{self.config.url}/collections/{self.config.collection_evaluations}/points",
                json={"points": [outcome_point]},
                params={"wait": "true"}
            )

            return resp.status_code in [200, 201]

        except Exception as e:
            log.error("store_evaluation_outcome_error", error=str(e))
            return False

    async def _update_routing_stats(self, outcome: EvaluationOutcome) -> None:
        """Update success rate stats for a routing."""
        try:
            resp = await self._http.get(
                f"{self.config.url}/collections/{self.config.collection_routing}/points/{outcome.routing_id}"
            )

            if resp.status_code != 200:
                return

            payload = resp.json().get("result", {}).get("payload", {})

            old_count = payload.get("sample_count", 0)
            old_success_rate = payload.get("success_rate", 0)

            new_count = old_count + 1
            new_success_rate = ((old_success_rate * old_count) + (1 if outcome.success else 0)) / new_count

            await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_routing}/points/payload",
                json={
                    "points": [outcome.routing_id],
                    "payload": {
                        "success": outcome.success,
                        "success_rate": new_success_rate,
                        "sample_count": new_count,
                    }
                }
            )

        except Exception as e:
            log.error("update_routing_stats_error", error=str(e))

    async def close(self) -> None:
        """Close the client."""
        await self._http.aclose()
        await self._embedding.close()


# =============================================================================
# Helper Functions
# =============================================================================

def generate_routing_id() -> str:
    """Generate a unique routing ID."""
    return str(uuid.uuid4())


def generate_outcome_id() -> str:
    """Generate a unique outcome ID."""
    return str(uuid.uuid4())
