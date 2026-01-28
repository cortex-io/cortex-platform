"""
Cortex Model Router

Intelligently routes prompts to the most cost-effective model.
Uses similarity-based learning to improve over time.

Routing Cascade:
    1. Forced model (if specified) - bypass all routing
    2. Similarity lookup (Qdrant) - reuse proven selections
    3. Heuristic estimation - fallback complexity analysis
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import redis
import os
from typing import Optional
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

# Learning imports
try:
    from qdrant_learning import (
        QdrantConfig, QdrantLearningClient,
        ModelSelection, ModelOutcome, SimilarSelection,
        generate_selection_id, generate_outcome_id
    )
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False

# =============================================================================
# Configuration
# =============================================================================

LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "true").lower() == "true"

# Global learning client
qdrant_learning: Optional["QdrantLearningClient"] = None


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup."""
    global qdrant_learning

    # Startup
    if LEARNING_ENABLED and LEARNING_AVAILABLE:
        try:
            config = QdrantConfig.from_env()
            qdrant_learning = QdrantLearningClient(config)
            if await qdrant_learning.initialize():
                print(f"[Learning] Qdrant learning initialized at {config.url}")
            else:
                print("[Learning] Qdrant not available - using heuristics only")
                qdrant_learning = None
        except Exception as e:
            print(f"[Learning] Failed to initialize: {e}")
            qdrant_learning = None
    else:
        print("[Learning] Disabled or not available")

    yield

    # Shutdown
    if qdrant_learning:
        await qdrant_learning.close()


app = FastAPI(title="Cortex Model Router", lifespan=lifespan)


# =============================================================================
# Redis Connection
# =============================================================================

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-queue.cortex.svc.cluster.local"),
    port=6379,
    decode_responses=True
)

COST_TRACKER_URL = os.getenv("COST_TRACKER_URL", "http://cost-tracker.cortex.svc.cluster.local:8080")

MODEL_HIERARCHY = ["haiku", "sonnet", "opus"]


# =============================================================================
# Complexity Estimation (Heuristic Fallback)
# =============================================================================

def estimate_complexity(prompt: str, context_size: int = 0) -> str:
    """Estimate task complexity based on prompt and context."""
    prompt_length = len(prompt)
    total_size = prompt_length + context_size

    complexity_keywords = ["analyze", "complex", "detailed", "comprehensive", "investigate", "explain why"]

    if total_size < 500 and not any(keyword in prompt.lower() for keyword in complexity_keywords):
        return "simple"
    elif total_size < 5000:
        return "medium"
    else:
        return "complex"


def select_model_heuristic(complexity: str, force_model: Optional[str] = None) -> str:
    """Select cheapest model for complexity level using heuristics."""
    if force_model and force_model in MODEL_HIERARCHY:
        return force_model

    if complexity == "simple":
        return "haiku"
    elif complexity == "medium":
        return "sonnet"
    else:
        return "opus"


# =============================================================================
# API Models
# =============================================================================

class RouteRequest(BaseModel):
    prompt: str
    context_size: int = 0
    force_model: Optional[str] = None


class RouteResponse(BaseModel):
    selected_model: str
    complexity: str
    reasoning: str
    selection_id: Optional[str] = None  # For tracking/feedback
    selection_method: str = "heuristic"  # heuristic, similarity, forced
    confidence: Optional[float] = None


class FeedbackRequest(BaseModel):
    selection_id: str
    success: bool
    latency_ms: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error_type: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "model-router",
        "learning_enabled": qdrant_learning is not None
    }


@app.post("/route", response_model=RouteResponse)
async def route_request(request: RouteRequest, background_tasks: BackgroundTasks):
    """Route request to appropriate model using learning + heuristics."""

    # Estimate complexity for all paths
    complexity = estimate_complexity(request.prompt, request.context_size)

    # Path 1: Forced model
    if request.force_model:
        if request.force_model not in MODEL_HIERARCHY:
            raise HTTPException(status_code=400, detail=f"Invalid model: {request.force_model}")

        selection_id = generate_selection_id() if LEARNING_AVAILABLE else None

        # Track the forced selection
        redis_client.incr(f"routing:{request.force_model}:total")

        # Store for learning if enabled
        if qdrant_learning and selection_id:
            background_tasks.add_task(
                store_selection_async,
                selection_id,
                request.prompt,
                request.force_model,
                "forced",
                complexity,
                1.0
            )

        return RouteResponse(
            selected_model=request.force_model,
            complexity=complexity,
            reasoning=f"User forced model: {request.force_model}",
            selection_id=selection_id,
            selection_method="forced",
            confidence=1.0
        )

    # Path 2: Similarity-based selection (if learning enabled)
    if qdrant_learning:
        similar = await qdrant_learning.find_similar_selection(request.prompt)

        if similar:
            selection_id = generate_selection_id()

            # Track the selection
            redis_client.incr(f"routing:{similar.selected_model}:total")
            redis_client.incr(f"routing:similarity:total")

            # Store the new selection
            background_tasks.add_task(
                store_selection_async,
                selection_id,
                request.prompt,
                similar.selected_model,
                "similarity",
                complexity,
                similar.similarity
            )

            return RouteResponse(
                selected_model=similar.selected_model,
                complexity=complexity,
                reasoning=f"Similar prompt succeeded with {similar.selected_model} (similarity: {similar.similarity:.2f}, success rate: {similar.success_rate:.0%})",
                selection_id=selection_id,
                selection_method="similarity",
                confidence=similar.similarity
            )

    # Path 3: Heuristic fallback
    selected_model = select_model_heuristic(complexity)
    selection_id = generate_selection_id() if LEARNING_AVAILABLE else None

    # Track routing decision
    redis_client.incr(f"routing:{selected_model}:total")
    redis_client.incr(f"routing:heuristic:total")

    # Store for learning
    if qdrant_learning and selection_id:
        background_tasks.add_task(
            store_selection_async,
            selection_id,
            request.prompt,
            selected_model,
            "heuristic",
            complexity,
            0.7  # Lower confidence for heuristic
        )

    return RouteResponse(
        selected_model=selected_model,
        complexity=complexity,
        reasoning=f"Heuristic: {complexity} complexity, prompt size: {len(request.prompt)}, context: {request.context_size}",
        selection_id=selection_id,
        selection_method="heuristic",
        confidence=0.7
    )


async def store_selection_async(
    selection_id: str,
    prompt: str,
    model: str,
    method: str,
    complexity: str,
    confidence: float
):
    """Background task to store selection in Qdrant."""
    if not qdrant_learning:
        return

    try:
        embedding = await qdrant_learning._embedding.embed(prompt[:2000])
        selection = ModelSelection(
            selection_id=selection_id,
            prompt_text=prompt,
            prompt_embedding=embedding,
            selected_model=model,
            selection_method=method,
            estimated_complexity=complexity,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )
        await qdrant_learning.store_selection(selection)
    except Exception as e:
        print(f"[Learning] Failed to store selection: {e}")


@app.post("/feedback")
async def track_feedback(request: FeedbackRequest):
    """Track model success/failure for learning."""

    # Legacy tracking
    success_key = f"routing:{request.selection_id.split('-')[0] if '-' in request.selection_id else 'unknown'}:success"
    failure_key = f"routing:{request.selection_id.split('-')[0] if '-' in request.selection_id else 'unknown'}:failure"

    if request.success:
        redis_client.incr(success_key)
    else:
        redis_client.incr(failure_key)

    # Learning tracking
    if qdrant_learning and request.selection_id:
        outcome = ModelOutcome(
            outcome_id=generate_outcome_id(),
            selection_id=request.selection_id,
            success=request.success,
            latency_ms=request.latency_ms,
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            error_type=request.error_type,
            timestamp=datetime.utcnow()
        )
        await qdrant_learning.store_outcome(outcome)

    return {"status": "tracked", "selection_id": request.selection_id, "success": request.success}


@app.get("/stats")
async def get_routing_stats():
    """Get routing statistics including learning stats."""
    stats = {}

    for model in MODEL_HIERARCHY:
        total = int(redis_client.get(f"routing:{model}:total") or 0)
        success = int(redis_client.get(f"routing:{model}:success") or 0)
        failure = int(redis_client.get(f"routing:{model}:failure") or 0)

        success_rate = (success / (success + failure) * 100) if (success + failure) > 0 else 0

        stats[model] = {
            "total_routed": total,
            "success": success,
            "failure": failure,
            "success_rate": round(success_rate, 2)
        }

    # Add learning stats
    stats["learning"] = {
        "enabled": qdrant_learning is not None,
        "similarity_routes": int(redis_client.get("routing:similarity:total") or 0),
        "heuristic_routes": int(redis_client.get("routing:heuristic:total") or 0),
    }

    return stats


@app.get("/savings")
async def estimate_savings():
    """Estimate cost savings from intelligent routing."""
    total_requests = 0
    actual_distribution = {}

    for model in MODEL_HIERARCHY:
        routed = int(redis_client.get(f"routing:{model}:total") or 0)
        actual_distribution[model] = routed
        total_requests += routed

    if total_requests == 0:
        return {"message": "No routing data yet"}

    # Cost estimates (cents per million tokens)
    opus_cost = 90
    haiku_cost = 1.5
    sonnet_cost = 18

    all_opus_cost = (total_requests * 1000 / 1_000_000) * opus_cost
    actual_cost = 0
    actual_cost += (actual_distribution.get("haiku", 0) * 1000 / 1_000_000) * haiku_cost
    actual_cost += (actual_distribution.get("sonnet", 0) * 1000 / 1_000_000) * sonnet_cost
    actual_cost += (actual_distribution.get("opus", 0) * 1000 / 1_000_000) * opus_cost

    savings = all_opus_cost - actual_cost
    savings_percent = (savings / all_opus_cost * 100) if all_opus_cost > 0 else 0

    return {
        "total_requests": total_requests,
        "if_all_opus_usd": round(all_opus_cost / 100, 4),
        "actual_cost_usd": round(actual_cost / 100, 4),
        "savings_usd": round(savings / 100, 4),
        "savings_percent": round(savings_percent, 2),
        "distribution": actual_distribution,
        "learning_stats": {
            "similarity_routes": int(redis_client.get("routing:similarity:total") or 0),
            "heuristic_routes": int(redis_client.get("routing:heuristic:total") or 0),
        }
    }
