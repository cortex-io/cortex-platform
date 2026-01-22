"""Pytest configuration and fixtures for agent tests."""

import asyncio
from typing import AsyncGenerator

import pytest
import fakeredis.aioredis


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_client() -> AsyncGenerator:
    """Provide a fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield client
    await client.flushall()
    await client.close()


@pytest.fixture
def redis_url() -> str:
    """Redis URL for testing."""
    return "redis://localhost:6379"


@pytest.fixture
def anthropic_api_key() -> str:
    """Mock Anthropic API key."""
    return "sk-ant-test-key"
