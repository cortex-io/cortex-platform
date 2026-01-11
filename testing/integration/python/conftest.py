"""
Global pytest configuration and fixtures for Cortex Python integration tests with testcontainers
"""
import os
import sys
import pytest
import time
from typing import Generator
from testcontainers.redis import RedisContainer
from testcontainers.postgres import PostgresContainer

# Set test environment
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'INFO'

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture(scope="session")
def redis_container():
    """Start Redis container for the test session"""
    container = RedisContainer("redis:7-alpine")
    container.start()

    # Set environment variables
    os.environ['REDIS_HOST'] = container.get_container_host_ip()
    os.environ['REDIS_PORT'] = container.get_exposed_port(6379)

    yield container

    container.stop()


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for the test session"""
    container = PostgresContainer(
        "postgres:16-alpine",
        username="cortex_test",
        password="cortex_test_password",
        dbname="cortex_test"
    )
    container.start()

    # Set environment variables
    os.environ['POSTGRES_HOST'] = container.get_container_host_ip()
    os.environ['POSTGRES_PORT'] = container.get_exposed_port(5432)
    os.environ['POSTGRES_DB'] = 'cortex_test'
    os.environ['POSTGRES_USER'] = 'cortex_test'
    os.environ['POSTGRES_PASSWORD'] = 'cortex_test_password'

    yield container

    container.stop()


@pytest.fixture
def redis_client(redis_container):
    """Get Redis client connected to test container"""
    import redis

    client = redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        db=0,
        decode_responses=True
    )

    yield client

    # Cleanup: flush all data after test
    client.flushall()
    client.close()


@pytest.fixture
def postgres_connection(postgres_container):
    """Get PostgreSQL connection to test container"""
    import psycopg2

    conn = psycopg2.connect(
        host=postgres_container.get_container_host_ip(),
        port=postgres_container.get_exposed_port(5432),
        database='cortex_test',
        user='cortex_test',
        password='cortex_test_password'
    )

    yield conn

    # Cleanup: rollback any uncommitted transactions
    conn.rollback()
    conn.close()


@pytest.fixture
def sample_issue_data():
    """Sample issue data for integration testing"""
    return {
        'id': 'integration-test-issue-123',
        'title': 'Integration Test Issue',
        'description': 'This is an integration test issue with full context',
        'priority': 'high',
        'status': 'open',
        'labels': ['bug', 'backend'],
        'created_at': '2025-01-09T12:00:00Z',
        'updated_at': '2025-01-09T12:00:00Z'
    }


@pytest.fixture
def sample_repo_context():
    """Sample repository context for integration testing"""
    return {
        'repo_id': 'integration-test-repo-123',
        'name': 'test-repository',
        'url': 'https://github.com/test/repo',
        'language': 'python',
        'framework': 'fastapi',
        'dependencies': ['fastapi==0.109.0', 'pydantic==2.5.3', 'sqlalchemy==2.0.25'],
        'structure': {
            'src': ['main.py', 'models.py', 'routes.py', 'database.py'],
            'tests': ['test_main.py', 'test_models.py']
        }
    }


def wait_for_condition(condition, timeout=5, interval=0.1):
    """Wait for a condition to be true"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def wait_helper():
    """Provide wait helper function"""
    return wait_for_condition
