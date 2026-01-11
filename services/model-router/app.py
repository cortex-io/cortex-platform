from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import os
from typing import Optional
import requests

app = FastAPI(title="Cortex Model Router")

# Redis connection for tracking success rates
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-queue.cortex.svc.cluster.local"),
    port=6379,
    decode_responses=True
)

# Cost tracking service
COST_TRACKER_URL = os.getenv("COST_TRACKER_URL", "http://cost-tracker.cortex.svc.cluster.local:8080")

# Model selection criteria
MODEL_HIERARCHY = ["haiku", "sonnet", "opus"]

# Complexity heuristics (simple rule-based for now)
def estimate_complexity(prompt: str, context_size: int = 0) -> str:
    """Estimate task complexity based on prompt and context"""
    prompt_length = len(prompt)
    total_size = prompt_length + context_size

    # Simple heuristics
    if total_size < 500 and not any(keyword in prompt.lower() for keyword in ["analyze", "complex", "detailed", "comprehensive"]):
        return "simple"
    elif total_size < 5000:
        return "medium"
    else:
        return "complex"

def select_model(complexity: str, force_model: Optional[str] = None) -> str:
    """Select cheapest model for complexity level"""
    if force_model and force_model in MODEL_HIERARCHY:
        return force_model

    if complexity == "simple":
        return "haiku"
    elif complexity == "medium":
        return "sonnet"
    else:
        return "opus"

class RouteRequest(BaseModel):
    prompt: str
    context_size: int = 0
    force_model: Optional[str] = None

class RouteResponse(BaseModel):
    selected_model: str
    complexity: str
    reasoning: str

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "model-router"}

@app.post("/route", response_model=RouteResponse)
async def route_request(request: RouteRequest):
    """Route request to appropriate model"""
    # Estimate complexity
    complexity = estimate_complexity(request.prompt, request.context_size)

    # Select model
    selected_model = select_model(complexity, request.force_model)

    # Build reasoning
    if request.force_model:
        reasoning = f"User forced model: {request.force_model}"
    else:
        reasoning = f"Complexity: {complexity}, prompt size: {len(request.prompt)}, context: {request.context_size}"

    # Track routing decision
    key = f"routing:{selected_model}:total"
    redis_client.incr(key)

    return RouteResponse(
        selected_model=selected_model,
        complexity=complexity,
        reasoning=reasoning
    )

@app.post("/feedback")
async def track_feedback(model: str, success: bool):
    """Track model success/failure for learning"""
    success_key = f"routing:{model}:success"
    failure_key = f"routing:{model}:failure"

    if success:
        redis_client.incr(success_key)
    else:
        redis_client.incr(failure_key)

    return {"status": "tracked", "model": model, "success": success}

@app.get("/stats")
async def get_routing_stats():
    """Get routing statistics"""
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

    return stats

@app.get("/savings")
async def estimate_savings():
    """Estimate cost savings from intelligent routing"""
    # If all requests went to opus vs actual routing
    total_requests = 0
    actual_distribution = {}

    for model in MODEL_HIERARCHY:
        routed = int(redis_client.get(f"routing:{model}:total") or 0)
        actual_distribution[model] = routed
        total_requests += routed

    if total_requests == 0:
        return {"message": "No routing data yet"}

    # Estimate savings (assuming average 1000 tokens per request)
    # If all went to opus: 15 + 75 = 90 cents per million tokens
    # Actual: weighted average based on distribution
    opus_cost = 90  # cents per million tokens
    haiku_cost = 1.5  # 0.25 + 1.25
    sonnet_cost = 18  # 3 + 15

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
        "distribution": actual_distribution
    }
