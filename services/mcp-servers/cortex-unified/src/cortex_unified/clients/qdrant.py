"""
Qdrant Client

Provides access to conversation memory and pattern storage.
Collections:
- routing_patterns: Query embeddings + routing decisions
- conversations: Message embeddings for context
- tool_patterns: Successful tool selection patterns
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class ConversationEntry:
    """A single conversation message."""
    id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: dict[str, Any]


@dataclass
class SearchResult:
    """Result from similarity search."""
    id: str
    score: float
    content: str
    metadata: dict[str, Any]


class QdrantClient:
    """HTTP client for Qdrant vector database."""

    COLLECTIONS = {
        "routing_patterns": {
            "vector_size": 384,
            "distance": "Cosine",
        },
        "conversations": {
            "vector_size": 384,
            "distance": "Cosine",
        },
        "tool_patterns": {
            "vector_size": 384,
            "distance": "Cosine",
        },
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or os.getenv(
            "QDRANT_URL",
            "http://chat-qdrant.cortex-chat:6333"
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

    async def health_check(self) -> bool:
        """Check if Qdrant is healthy."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.base_url}/readyz", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def store_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        vector: Optional[list[float]] = None,
    ) -> str:
        """
        Store a conversation message in Qdrant.

        Args:
            session_id: The session/conversation ID
            role: "user" or "assistant"
            content: Message content
            metadata: Optional additional metadata
            vector: Optional pre-computed embedding vector

        Returns:
            The point ID
        """
        client = await self._get_client()

        point_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()

        payload = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            **(metadata or {}),
        }

        # If no vector provided, use a placeholder
        # In production, you'd compute embeddings via a model
        if vector is None:
            # Placeholder: zero vector (should use actual embeddings)
            vector = [0.0] * 384

        try:
            response = await client.put(
                f"{self.base_url}/collections/conversations/points",
                json={
                    "points": [
                        {
                            "id": point_id,
                            "vector": vector,
                            "payload": payload,
                        }
                    ]
                },
            )
            response.raise_for_status()

            logger.debug(
                "conversation_stored",
                point_id=point_id,
                session_id=session_id,
                role=role,
            )

            return point_id

        except Exception as e:
            logger.error(
                "qdrant_store_error",
                error=str(e),
                session_id=session_id,
            )
            raise

    async def recall_conversation(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[ConversationEntry]:
        """
        Recall conversation history for a session.

        Args:
            session_id: The session/conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of conversation entries ordered by timestamp
        """
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/collections/conversations/points/scroll",
                json={
                    "filter": {
                        "must": [
                            {
                                "key": "session_id",
                                "match": {"value": session_id},
                            }
                        ]
                    },
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            entries = []
            for point in data.get("result", {}).get("points", []):
                payload = point.get("payload", {})
                entries.append(ConversationEntry(
                    id=str(point.get("id")),
                    session_id=payload.get("session_id", session_id),
                    role=payload.get("role", "unknown"),
                    content=payload.get("content", ""),
                    timestamp=datetime.fromisoformat(
                        payload.get("timestamp", datetime.utcnow().isoformat())
                    ),
                    metadata={
                        k: v for k, v in payload.items()
                        if k not in ("session_id", "role", "content", "timestamp")
                    },
                ))

            # Sort by timestamp
            entries.sort(key=lambda x: x.timestamp)

            return entries

        except Exception as e:
            logger.error(
                "qdrant_recall_error",
                error=str(e),
                session_id=session_id,
            )
            return []

    async def search_similar(
        self,
        collection: str,
        vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.8,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """
        Search for similar vectors in a collection.

        Args:
            collection: Collection name
            vector: Query vector
            limit: Maximum results
            score_threshold: Minimum similarity score
            filter_conditions: Optional Qdrant filter

        Returns:
            List of search results
        """
        client = await self._get_client()

        try:
            payload = {
                "vector": vector,
                "limit": limit,
                "score_threshold": score_threshold,
                "with_payload": True,
            }

            if filter_conditions:
                payload["filter"] = filter_conditions

            response = await client.post(
                f"{self.base_url}/collections/{collection}/points/search",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for hit in data.get("result", []):
                results.append(SearchResult(
                    id=str(hit.get("id")),
                    score=hit.get("score", 0.0),
                    content=hit.get("payload", {}).get("content", ""),
                    metadata=hit.get("payload", {}),
                ))

            return results

        except Exception as e:
            logger.error(
                "qdrant_search_error",
                error=str(e),
                collection=collection,
            )
            return []

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete all conversation entries for a session.

        Args:
            session_id: The session to delete

        Returns:
            True if successful
        """
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/collections/conversations/points/delete",
                json={
                    "filter": {
                        "must": [
                            {
                                "key": "session_id",
                                "match": {"value": session_id},
                            }
                        ]
                    }
                },
            )
            response.raise_for_status()

            logger.info("session_deleted", session_id=session_id)
            return True

        except Exception as e:
            logger.error(
                "qdrant_delete_error",
                error=str(e),
                session_id=session_id,
            )
            return False

    async def list_sessions(self, limit: int = 100) -> list[str]:
        """
        List all session IDs in the conversations collection.

        Returns:
            List of unique session IDs
        """
        client = await self._get_client()

        try:
            # Scroll through points and collect unique session IDs
            response = await client.post(
                f"{self.base_url}/collections/conversations/points/scroll",
                json={
                    "limit": limit,
                    "with_payload": ["session_id"],
                    "with_vector": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            session_ids = set()
            for point in data.get("result", {}).get("points", []):
                sid = point.get("payload", {}).get("session_id")
                if sid:
                    session_ids.add(sid)

            return sorted(session_ids)

        except Exception as e:
            logger.error("qdrant_list_sessions_error", error=str(e))
            return []
