"""
Reasoning DMR Layer - Local LLM via Docker Model Runner

This layer provides local LLM inference using Docker Model Runner,
exposing an OpenAI-compatible API for the chat activator.

Key features:
- Zero API costs for inference
- Privacy-preserving (queries never leave the cluster)
- Fast inference with optimized GGUF models
- Automatic model management via DMR

Supported models:
- microsoft/phi-4 (default)
- Qwen/Qwen2.5-7B-Instruct
- meta-llama/Llama-3.2-3B-Instruct
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog

log = structlog.get_logger()

# =============================================================================
# Configuration
# =============================================================================

DMR_ENDPOINT = os.getenv("DMR_ENDPOINT", "http://localhost:12434/v1")
DMR_MODEL = os.getenv("DMR_MODEL", "microsoft/phi-4")
DMR_CONTEXT_LENGTH = int(os.getenv("DMR_CONTEXT_LENGTH", "4096"))
DMR_TEMPERATURE = float(os.getenv("DMR_TEMPERATURE", "0.1"))


# =============================================================================
# Metrics
# =============================================================================

INFERENCE_TOTAL = Counter(
    'cortex_dmr_inference_total',
    'Total inference requests',
    ['model', 'status']
)

INFERENCE_LATENCY = Histogram(
    'cortex_dmr_inference_latency_seconds',
    'Inference latency',
    ['model'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

TOKENS_TOTAL = Counter(
    'cortex_dmr_tokens_total',
    'Total tokens processed',
    ['model', 'direction']  # input, output
)

MODEL_LOADED = Gauge(
    'cortex_dmr_model_loaded',
    'Whether the model is loaded',
    ['model']
)


# =============================================================================
# Models
# =============================================================================

class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


# =============================================================================
# DMR Client
# =============================================================================

class DMRClient:
    """Client for Docker Model Runner."""

    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint
        self.model = model
        self.http = httpx.AsyncClient(timeout=120.0)
        self.model_loaded = False
        self.log = structlog.get_logger()

    async def check_health(self) -> bool:
        """Check if DMR is available and model is loaded."""
        try:
            resp = await self.http.get(f"{self.endpoint}/models")
            if resp.status_code == 200:
                models = resp.json()
                # Check if our model is available
                model_names = [m.get("id", "") for m in models.get("data", [])]
                self.model_loaded = any(self.model in name for name in model_names)
                MODEL_LOADED.labels(model=self.model).set(1 if self.model_loaded else 0)
                return True
        except Exception as e:
            self.log.warning("dmr_health_check_failed", error=str(e))

        MODEL_LOADED.labels(model=self.model).set(0)
        return False

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Send completion request to DMR."""
        start = time.time()
        model = request.model or self.model

        try:
            # Build messages with system prompt if not present
            messages = [m.model_dump() for m in request.messages]
            if not any(m["role"] == "system" for m in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": self._get_system_prompt()
                })

            # Send to DMR
            resp = await self.http.post(
                f"{self.endpoint}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stop": request.stop,
                }
            )

            latency = time.time() - start
            INFERENCE_LATENCY.labels(model=model).observe(latency)

            if resp.status_code != 200:
                INFERENCE_TOTAL.labels(model=model, status="error").inc()
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"DMR error: {resp.text}"
                )

            result = resp.json()
            INFERENCE_TOTAL.labels(model=model, status="success").inc()

            # Track tokens
            usage = result.get("usage", {})
            TOKENS_TOTAL.labels(model=model, direction="input").inc(
                usage.get("prompt_tokens", 0)
            )
            TOKENS_TOTAL.labels(model=model, direction="output").inc(
                usage.get("completion_tokens", 0)
            )

            self.log.info(
                "inference_complete",
                model=model,
                latency_ms=int(latency * 1000),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0)
            )

            return ChatCompletionResponse(
                id=result.get("id", f"chatcmpl-{int(time.time())}"),
                created=result.get("created", int(time.time())),
                model=model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=result["choices"][0]["message"]["content"]
                        ),
                        finish_reason=result["choices"][0].get("finish_reason", "stop")
                    )
                ],
                usage=Usage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0)
                )
            )

        except httpx.RequestError as e:
            INFERENCE_TOTAL.labels(model=model, status="error").inc()
            self.log.error("dmr_request_failed", error=str(e))
            raise HTTPException(status_code=503, detail=f"DMR unavailable: {str(e)}")

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the model."""
        return """You are Cortex Chat, an AI infrastructure assistant for the Cortex platform.

Your capabilities:
- Kubernetes cluster management and troubleshooting
- Infrastructure monitoring and analysis
- DevOps automation guidance
- System status queries

Guidelines:
- Be concise and direct
- Provide actionable information
- If you need to execute commands or make changes, describe what should be done
- For complex multi-step tasks, outline the steps clearly
- If you're uncertain, say so rather than guessing
- Use markdown formatting for code blocks and structured output

Current context: You're running locally via Docker Model Runner (Phi-4).
For complex agentic tasks, you may recommend escalation to Claude Code."""

    async def close(self):
        await self.http.aclose()


# =============================================================================
# FastAPI Application
# =============================================================================

dmr_client: Optional[DMRClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global dmr_client

    log.info(
        "reasoning_dmr_starting",
        endpoint=DMR_ENDPOINT,
        model=DMR_MODEL
    )

    dmr_client = DMRClient(DMR_ENDPOINT, DMR_MODEL)

    # Check DMR health
    if await dmr_client.check_health():
        log.info("dmr_connected", model=DMR_MODEL, loaded=dmr_client.model_loaded)
    else:
        log.warning("dmr_not_available", endpoint=DMR_ENDPOINT)

    yield

    log.info("reasoning_dmr_shutdown")
    if dmr_client:
        await dmr_client.close()


app = FastAPI(
    title="Reasoning DMR",
    description="Local LLM inference via Docker Model Runner",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# HTTP Endpoints
# =============================================================================

@app.get("/health")
async def health():
    """Basic health check."""
    dmr_available = await dmr_client.check_health() if dmr_client else False
    return {
        "status": "healthy" if dmr_available else "degraded",
        "service": "reasoning-dmr",
        "dmr_available": dmr_available,
        "model": DMR_MODEL,
        "model_loaded": dmr_client.model_loaded if dmr_client else False,
    }


@app.get("/ready")
async def ready():
    """Readiness check - DMR must be available."""
    if not dmr_client or not await dmr_client.check_health():
        raise HTTPException(503, detail="DMR not available")
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


# OpenAI-compatible endpoints
@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    return {
        "object": "list",
        "data": [
            {
                "id": DMR_MODEL,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "docker-model-runner",
            }
        ]
    }


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """Chat completions endpoint (OpenAI-compatible)."""
    if not dmr_client:
        raise HTTPException(503, detail="DMR client not initialized")

    return await dmr_client.complete(request)


# Simplified endpoint for activator
@app.post("/complete")
async def simple_complete(query: str, context: Optional[Dict[str, Any]] = None):
    """Simplified completion endpoint for the activator."""
    if not dmr_client:
        raise HTTPException(503, detail="DMR client not initialized")

    request = ChatCompletionRequest(
        messages=[Message(role="user", content=query)],
        temperature=DMR_TEMPERATURE,
        max_tokens=1024,
    )

    response = await dmr_client.complete(request)
    return {
        "response": response.choices[0].message.content,
        "model": response.model,
        "tokens": response.usage.model_dump(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
