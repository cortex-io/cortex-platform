"""
Chat Activator Client

Routes queries through the Chat Layer Fabric intelligence cascade:
- Tier 0: Cache
- Tier 1: Keyword patterns
- Tier 2: Qdrant similarity
- Tier 3: DMR (local Phi-4)
- Tier 4: Anthropic API
"""

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class ChatResponse:
    """Response from Chat Activator."""
    success: bool
    content: str
    tier_used: str
    model_used: Optional[str]
    cost_usd: float
    latency_ms: int
    complexity_score: int
    complexity_level: str
    conversation_id: str
    layers_activated: list[str]
    escalation_reason: Optional[str] = None
    error: Optional[str] = None


class ChatActivatorClient:
    """HTTP client for Chat Activator service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url or os.getenv(
            "CHAT_ACTIVATOR_URL",
            "http://chat-activator.cortex-chat:8080"
        )
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat_complete(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        force_tier: Optional[str] = None,
    ) -> ChatResponse:
        """
        Route a message through the Chat Fabric intelligence cascade.

        Args:
            message: The user's message
            context: Optional context (namespace, user, previous_failure, etc.)
            conversation_id: Optional conversation ID for continuity
            force_tier: Optional tier to force ("cache", "pattern", "similarity", "dmr", "anthropic")

        Returns:
            ChatResponse with content and routing metadata
        """
        client = await self._get_client()

        payload = {
            "message": message,
            "context": context or {},
        }

        if conversation_id:
            payload["conversation_id"] = conversation_id

        if force_tier:
            payload["context"]["force_tier"] = force_tier

        try:
            logger.info(
                "chat_activator_request",
                message_preview=message[:100],
                has_context=bool(context),
            )

            response = await client.post(
                f"{self.base_url}/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            metadata = data.get("metadata", {})

            return ChatResponse(
                success=data.get("success", True),
                content=data.get("response", ""),
                tier_used=metadata.get("route_tier", "unknown"),
                model_used=metadata.get("model_used"),
                cost_usd=metadata.get("cost_usd", 0.0),
                latency_ms=metadata.get("latency_ms", 0),
                complexity_score=metadata.get("complexity_score", 0),
                complexity_level=metadata.get("complexity_level", "unknown"),
                conversation_id=data.get("conversation_id", ""),
                layers_activated=metadata.get("layers_activated", []),
                escalation_reason=metadata.get("escalation_reason"),
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "chat_activator_http_error",
                status_code=e.response.status_code,
                detail=str(e),
            )
            return ChatResponse(
                success=False,
                content="",
                tier_used="error",
                model_used=None,
                cost_usd=0.0,
                latency_ms=0,
                complexity_score=0,
                complexity_level="error",
                conversation_id=conversation_id or "",
                layers_activated=[],
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )

        except Exception as e:
            logger.error("chat_activator_error", error=str(e))
            return ChatResponse(
                success=False,
                content="",
                tier_used="error",
                model_used=None,
                cost_usd=0.0,
                latency_ms=0,
                complexity_score=0,
                complexity_level="error",
                conversation_id=conversation_id or "",
                layers_activated=[],
                error=str(e),
            )

    async def analyze(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Analyze a query without executing it.

        Returns complexity score, intent classification, and predicted tier.
        """
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/analyze",
                json={
                    "message": message,
                    "context": context or {},
                },
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("chat_activator_analyze_error", error=str(e))
            return {
                "error": str(e),
                "complexity": {"score": 0, "level": "unknown"},
                "intent": {"type": "unknown", "confidence": 0.0},
                "predicted_tier": "unknown",
            }

    async def health_check(self) -> bool:
        """Check if Chat Activator is healthy."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def get_status(self) -> dict[str, Any]:
        """Get detailed status of Chat Activator and all layers."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.base_url}/status", timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("chat_activator_status_error", error=str(e))
            return {"error": str(e), "activator": "unknown", "layers": {}}
