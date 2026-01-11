from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import os
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

app = FastAPI(title="Cortex Cost Tracker")

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-queue.cortex.svc.cluster.local"),
    port=6379,
    decode_responses=True
)

# Anthropic pricing (per million tokens)
PRICING = {
    "haiku": {"input": 0.25, "output": 1.25},
    "sonnet": {"input": 3.00, "output": 15.00},
    "opus": {"input": 15.00, "output": 75.00}
}

class ModelUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: str

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "cost-tracker"}

@app.post("/track")
async def track_usage(usage: ModelUsage):
    """Track model usage"""
    # Store in Redis with timestamp
    key = f"usage:{usage.model}:{datetime.now().strftime('%Y-%m-%d')}"

    # Increment token counters
    redis_client.hincrby(key, "input_tokens", usage.input_tokens)
    redis_client.hincrby(key, "output_tokens", usage.output_tokens)
    redis_client.hincrby(key, "requests", 1)

    # Set expiry to 90 days
    redis_client.expire(key, 90 * 24 * 3600)

    return {"status": "tracked", "model": usage.model}

@app.get("/costs/today")
async def get_today_costs():
    """Get today's costs breakdown"""
    today = datetime.now().strftime('%Y-%m-%d')
    costs = {}
    total_cost = 0

    for model in ["haiku", "sonnet", "opus"]:
        key = f"usage:{model}:{today}"
        data = redis_client.hgetall(key)

        if data:
            input_tokens = int(data.get("input_tokens", 0))
            output_tokens = int(data.get("output_tokens", 0))
            requests = int(data.get("requests", 0))

            # Calculate cost
            input_cost = (input_tokens / 1_000_000) * PRICING[model]["input"]
            output_cost = (output_tokens / 1_000_000) * PRICING[model]["output"]
            model_cost = input_cost + output_cost

            costs[model] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "requests": requests,
                "cost_usd": round(model_cost, 4)
            }
            total_cost += model_cost

    return {
        "date": today,
        "models": costs,
        "total_cost_usd": round(total_cost, 4)
    }

@app.get("/costs/monthly")
async def get_monthly_costs():
    """Get current month's costs"""
    today = datetime.now()
    start_of_month = today.replace(day=1)

    monthly_total = 0
    daily_costs = []

    # Get last 30 days
    for i in range(30):
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        day_cost = 0

        for model in ["haiku", "sonnet", "opus"]:
            key = f"usage:{model}:{date}"
            data = redis_client.hgetall(key)

            if data:
                input_tokens = int(data.get("input_tokens", 0))
                output_tokens = int(data.get("output_tokens", 0))

                input_cost = (input_tokens / 1_000_000) * PRICING[model]["input"]
                output_cost = (output_tokens / 1_000_000) * PRICING[model]["output"]
                day_cost += input_cost + output_cost

        if day_cost > 0:
            daily_costs.append({"date": date, "cost_usd": round(day_cost, 4)})
        monthly_total += day_cost

    # Project monthly total
    days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
    days_elapsed = today.day
    projected_monthly = (monthly_total / days_elapsed) * days_in_month if days_elapsed > 0 else 0

    return {
        "month": today.strftime('%Y-%m'),
        "days_elapsed": days_elapsed,
        "actual_cost_usd": round(monthly_total, 2),
        "projected_monthly_usd": round(projected_monthly, 2),
        "daily_breakdown": daily_costs[:7]  # Last 7 days
    }

@app.get("/stats")
async def get_stats():
    """Get usage statistics"""
    today = datetime.now().strftime('%Y-%m-%d')
    stats = {}

    for model in ["haiku", "sonnet", "opus"]:
        key = f"usage:{model}:{today}"
        data = redis_client.hgetall(key)

        if data:
            stats[model] = {
                "requests": int(data.get("requests", 0)),
                "input_tokens": int(data.get("input_tokens", 0)),
                "output_tokens": int(data.get("output_tokens", 0))
            }

    return {"date": today, "models": stats}
