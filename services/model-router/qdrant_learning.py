"""
Qdrant Learning Layer for Cortex Model Router

This module provides the learning foundation for adaptive model selection.
It stores query embeddings with model selection decisions and outcomes to enable
similarity-based routing that improves over time.

Architecture:
    Prompt → Embed → Search similar → Select model (or use heuristic)
         ↓
    Store in Qdrant: prompt_embedding + model_selection + outcome
         ↓
    Future similar prompts → reuse learned selection (skip heuristics)

Collections:
    - model_selections: Prompt embeddings with model selections
    - model_outcomes: Links selection to execution outcome for learning

Key Insight: The heuristic-based complexity estimation is often wrong.
A prompt that "looks complex" may actually work fine with Haiku if we've
seen similar prompts succeed with it before.
"""

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

# Optional: structured logging if available
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
    collection_selections: str = "model_selections"
    collection_outcomes: str = "model_outcomes"

    # Similarity thresholds
    similarity_threshold: float = 0.75  # Min score to reuse selection
    confidence_threshold: float = 0.80  # Min confidence for auto-routing

    # Learning parameters
    min_success_rate: float = 0.8  # Min success rate to trust a selection
    min_samples: int = 3  # Min samples before trusting a pattern

    @classmethod
    def from_env(cls) -> "QdrantConfig":
        """Load configuration from environment."""
        return cls(
            url=os.getenv("QDRANT_URL", "http://cortex-qdrant.cortex-system:6333"),
            collection_selections=os.getenv("QDRANT_COLLECTION_SELECTIONS", "model_selections"),
            collection_outcomes=os.getenv("QDRANT_COLLECTION_OUTCOMES", "model_outcomes"),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.75")),
            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.80")),
        )


@dataclass
class ModelSelection:
    """A model selection decision to store/retrieve from Qdrant."""
    selection_id: str
    prompt_text: str
    prompt_embedding: List[float]
    selected_model: str  # haiku, sonnet, opus
    selection_method: str  # heuristic, similarity, forced
    estimated_complexity: str  # simple, medium, complex
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelOutcome:
    """The outcome of a model selection."""
    outcome_id: str
    selection_id: str  # Links to ModelSelection
    success: bool
    latency_ms: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error_type: Optional[str] = None  # rate_limit, context_exceeded, model_error
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimilarSelection:
    """A similar past model selection found in Qdrant."""
    selection_id: str
    prompt_preview: str
    similarity: float
    selected_model: str
    success_rate: float
    sample_count: int
    avg_latency_ms: float


# =============================================================================
# Embedding Client
# =============================================================================

class EmbeddingClient:
    """Client for generating prompt embeddings."""

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
    """Client for Qdrant-based model selection learning."""

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

            # Ensure collections exist
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
            (self.config.collection_selections, 384),
            (self.config.collection_outcomes, 384)
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

    async def find_similar_selection(
        self,
        prompt: str,
    ) -> Optional[SimilarSelection]:
        """
        Find a similar past model selection for the prompt.

        Returns the best matching selection if:
        - Similarity > threshold
        - Success rate > min_success_rate
        - Sample count > min_samples
        """
        if not self._initialized:
            return None

        try:
            start = time.time()
            embedding = await self._embedding.embed(prompt[:2000])  # Truncate for embedding
            embed_time = (time.time() - start) * 1000

            resp = await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_selections}/points/search",
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
                    similar = SimilarSelection(
                        selection_id=payload.get("selection_id", str(result.get("id"))),
                        prompt_preview=payload.get("prompt_preview", "")[:100],
                        similarity=result.get("score", 0),
                        selected_model=payload.get("selected_model", ""),
                        success_rate=success_rate,
                        sample_count=sample_count,
                        avg_latency_ms=payload.get("avg_latency_ms", 0),
                    )

                    log.info(
                        "similar_selection_found",
                        similarity=round(similar.similarity, 3),
                        model=similar.selected_model,
                        success_rate=round(similar.success_rate, 2),
                        samples=similar.sample_count,
                        embed_ms=round(embed_time, 1)
                    )
                    return similar

            return None

        except Exception as e:
            log.error("find_similar_selection_error", error=str(e))
            return None

    async def store_selection(self, selection: ModelSelection) -> bool:
        """Store a model selection in Qdrant."""
        if not self._initialized:
            return False

        try:
            point = {
                "id": selection.selection_id,
                "vector": selection.prompt_embedding,
                "payload": {
                    "selection_id": selection.selection_id,
                    "prompt_preview": selection.prompt_text[:200],
                    "selected_model": selection.selected_model,
                    "selection_method": selection.selection_method,
                    "estimated_complexity": selection.estimated_complexity,
                    "confidence": selection.confidence,
                    "timestamp": selection.timestamp.isoformat(),
                    "success": None,
                    "success_rate": 0.0,
                    "sample_count": 1,
                    "avg_latency_ms": 0,
                    **selection.metadata,
                }
            }

            resp = await self._http.put(
                f"{self.config.url}/collections/{self.config.collection_selections}/points",
                json={"points": [point]},
                params={"wait": "true"}
            )

            return resp.status_code in [200, 201]

        except Exception as e:
            log.error("store_selection_error", error=str(e))
            return False

    async def store_outcome(self, outcome: ModelOutcome) -> bool:
        """Store the outcome of a model selection."""
        if not self._initialized:
            return False

        try:
            await self._update_selection_stats(outcome)

            outcome_point = {
                "id": outcome.outcome_id,
                "vector": [0.0] * 384,
                "payload": {
                    "outcome_id": outcome.outcome_id,
                    "selection_id": outcome.selection_id,
                    "success": outcome.success,
                    "latency_ms": outcome.latency_ms,
                    "input_tokens": outcome.input_tokens,
                    "output_tokens": outcome.output_tokens,
                    "error_type": outcome.error_type,
                    "timestamp": outcome.timestamp.isoformat(),
                }
            }

            resp = await self._http.put(
                f"{self.config.url}/collections/{self.config.collection_outcomes}/points",
                json={"points": [outcome_point]},
                params={"wait": "true"}
            )

            return resp.status_code in [200, 201]

        except Exception as e:
            log.error("store_outcome_error", error=str(e))
            return False

    async def _update_selection_stats(self, outcome: ModelOutcome) -> None:
        """Update success rate and latency stats for a selection."""
        try:
            resp = await self._http.get(
                f"{self.config.url}/collections/{self.config.collection_selections}/points/{outcome.selection_id}"
            )

            if resp.status_code != 200:
                return

            payload = resp.json().get("result", {}).get("payload", {})

            old_count = payload.get("sample_count", 0)
            old_success_rate = payload.get("success_rate", 0)
            old_avg_latency = payload.get("avg_latency_ms", 0)

            new_count = old_count + 1
            new_success_rate = ((old_success_rate * old_count) + (1 if outcome.success else 0)) / new_count
            new_avg_latency = ((old_avg_latency * old_count) + outcome.latency_ms) / new_count

            await self._http.post(
                f"{self.config.url}/collections/{self.config.collection_selections}/points/payload",
                json={
                    "points": [outcome.selection_id],
                    "payload": {
                        "success": outcome.success,
                        "success_rate": new_success_rate,
                        "sample_count": new_count,
                        "avg_latency_ms": new_avg_latency,
                    }
                }
            )

        except Exception as e:
            log.error("update_selection_stats_error", error=str(e))

    async def close(self) -> None:
        """Close the client."""
        await self._http.aclose()
        await self._embedding.close()


# =============================================================================
# Helper Functions
# =============================================================================

def generate_selection_id() -> str:
    """Generate a unique selection ID."""
    return str(uuid.uuid4())


def generate_outcome_id() -> str:
    """Generate a unique outcome ID."""
    return str(uuid.uuid4())
