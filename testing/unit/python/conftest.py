"""
Global pytest configuration and fixtures for Cortex Python unit tests
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock
from typing import Generator

# Set test environment
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'ERROR'

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.expire.return_value = True
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture
def mock_postgres():
    """Mock PostgreSQL connection for testing"""
    conn_mock = MagicMock()
    cursor_mock = MagicMock()

    cursor_mock.execute.return_value = None
    cursor_mock.fetchone.return_value = None
    cursor_mock.fetchall.return_value = []
    cursor_mock.fetchmany.return_value = []
    cursor_mock.rowcount = 0

    conn_mock.cursor.return_value.__enter__.return_value = cursor_mock
    conn_mock.cursor.return_value.__exit__.return_value = None
    conn_mock.commit.return_value = None
    conn_mock.rollback.return_value = None

    return conn_mock


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing"""
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {}
    response.text = '{}'
    response.content = b'{}'
    client.get.return_value = response
    client.post.return_value = response
    client.put.return_value = response
    client.delete.return_value = response
    return client


@pytest.fixture
def sample_issue_data():
    """Sample issue data for testing"""
    return {
        'id': 'test-issue-123',
        'title': 'Test Issue',
        'description': 'This is a test issue for testing purposes',
        'priority': 'high',
        'status': 'open',
        'created_at': '2025-01-09T12:00:00Z',
        'updated_at': '2025-01-09T12:00:00Z'
    }


@pytest.fixture
def sample_repo_context():
    """Sample repository context data for testing"""
    return {
        'repo_id': 'test-repo-123',
        'name': 'test-repository',
        'language': 'python',
        'framework': 'fastapi',
        'dependencies': ['fastapi', 'pydantic', 'sqlalchemy'],
        'structure': {
            'src': ['main.py', 'models.py', 'routes.py'],
            'tests': ['test_main.py']
        }
    }


@pytest.fixture
def sample_code_generation_request():
    """Sample code generation request for testing"""
    return {
        'request_id': 'test-request-123',
        'issue_id': 'test-issue-123',
        'repo_id': 'test-repo-123',
        'prompt': 'Generate a FastAPI endpoint for user authentication',
        'context': {
            'language': 'python',
            'framework': 'fastapi'
        }
    }


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary test directory"""
    test_dir = tmp_path / "test_workspace"
    test_dir.mkdir()
    return test_dir


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment after each test"""
    yield
    # Cleanup code here if needed


def pytest_configure(config):
    """Pytest configuration hook"""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add unit marker to all tests in unit directory by default
    for item in items:
        if "unit" in str(item.fspath) and "unit" not in item.keywords:
            item.add_marker(pytest.mark.unit)
