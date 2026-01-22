"""Tests for BaseWorker class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.base_worker import BaseWorker
from agents.messaging import AgentMessage


class TestWorker(BaseWorker):
    """Concrete worker for testing."""

    def get_capabilities(self):
        return ["test_capability"]

    def get_system_prompt(self):
        return "Test system prompt"

    async def process_task(self, message):
        return {"result": "test_result"}


@pytest.mark.asyncio
class TestBaseWorker:
    """Test BaseWorker functionality."""

    async def test_worker_initialization(self, redis_url, anthropic_api_key):
        """Test worker initialization."""
        worker = TestWorker(
            agent_id="test-worker-001",
            name="Test Worker",
            master_id="test-master",
            redis_url=redis_url,
            anthropic_api_key=anthropic_api_key,
        )

        assert worker.agent_id == "test-worker-001"
        assert worker.name == "Test Worker"
        assert worker.master_id == "test-master"
        assert worker.task_stream == "agent:tasks:test-worker-001"

    async def test_worker_capabilities(self):
        """Test getting worker capabilities."""
        worker = TestWorker(
            agent_id="test-worker",
            name="Test",
            master_id="master",
        )

        capabilities = worker.get_capabilities()
        assert "test_capability" in capabilities

    async def test_worker_system_prompt(self):
        """Test getting system prompt."""
        worker = TestWorker(
            agent_id="test-worker",
            name="Test",
            master_id="master",
        )

        prompt = worker.get_system_prompt()
        assert "Test system prompt" in prompt

    @patch("agents.base_worker.AsyncAnthropic")
    async def test_ask_claude(self, mock_anthropic, redis_url, anthropic_api_key):
        """Test asking Claude a question."""
        # Mock Claude API response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Claude response")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        worker = TestWorker(
            agent_id="test-worker",
            name="Test",
            master_id="master",
            redis_url=redis_url,
            anthropic_api_key=anthropic_api_key,
        )

        response = await worker.ask_claude("Test question")
        assert response == "Claude response"
        assert worker.get_conversation_length() == 2  # user + assistant

    async def test_conversation_history(self):
        """Test conversation history management."""
        worker = TestWorker(
            agent_id="test-worker",
            name="Test",
            master_id="master",
        )

        assert worker.get_conversation_length() == 0

        # Add some messages to history
        worker._conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        assert worker.get_conversation_length() == 2

        # Clear conversation
        worker.clear_conversation()
        assert worker.get_conversation_length() == 0
