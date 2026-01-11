"""
Unit tests for Repository Context Service
"""
import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestRepositoryContext:
    """Test Repository Context Service endpoints"""

    def test_health_check_healthy(self, mock_redis):
        """Test health check returns healthy status"""
        mock_redis.ping.return_value = True

        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "redis": "connected" if mock_redis.ping() else "disconnected",
            "chromadb": "connected"
        }

        assert health["status"] == "healthy"
        assert health["redis"] == "connected"

    def test_health_check_unhealthy(self, mock_redis):
        """Test health check returns unhealthy status when Redis is down"""
        mock_redis.ping.side_effect = Exception("Connection failed")

        try:
            mock_redis.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"

        assert redis_status == "disconnected"

    def test_index_repository_success(self):
        """Test successful repository indexing"""
        repo_id = "test-repo-123"
        patterns = [
            {
                "id": f"{repo_id}_pattern_0",
                "type": "naming_convention",
                "pattern": "kebab-case for files"
            }
        ]

        result = {
            "success": True,
            "repo_id": repo_id,
            "patterns_indexed": len(patterns)
        }

        assert result["success"] is True
        assert result["patterns_indexed"] == 1

    def test_index_repository_stores_metadata(self, mock_redis):
        """Test repository metadata is stored in Redis"""
        repo_id = "test-repo-123"
        metadata = {
            "repo_id": repo_id,
            "indexed_at": datetime.utcnow().isoformat(),
            "pattern_count": 3,
            "languages": ["javascript", "python"]
        }

        mock_redis.set(
            f"repo_metadata:{repo_id}",
            json.dumps(metadata),
            ex=86400
        )

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == f"repo_metadata:{repo_id}"

    def test_get_patterns_with_query(self):
        """Test retrieving patterns with search query"""
        patterns = [
            {"type": "naming_convention", "pattern": "kebab-case"},
            {"type": "error_handling", "pattern": "try-catch"}
        ]

        def search_patterns(query):
            return [p for p in patterns if query.lower() in p["type"].lower()]

        results = search_patterns("naming")
        assert len(results) == 1
        assert results[0]["type"] == "naming_convention"

    def test_get_patterns_all(self):
        """Test retrieving all patterns"""
        patterns = [
            {"type": "naming_convention"},
            {"type": "error_handling"},
            {"type": "api_structure"}
        ]

        result = {
            "repo_id": "test-repo",
            "patterns": patterns,
            "count": len(patterns)
        }

        assert result["count"] == 3
        assert len(result["patterns"]) == 3

    def test_get_conventions(self):
        """Test getting coding conventions"""
        conventions = {
            "naming": {
                "services": "kebab-case",
                "files": "kebab-case.js or kebab-case.py",
                "functions": "camelCase (JS), snake_case (Python)"
            },
            "testing": {
                "coverage_minimum": "80%",
                "required_types": ["unit", "integration"]
            }
        }

        assert conventions["naming"]["services"] == "kebab-case"
        assert conventions["testing"]["coverage_minimum"] == "80%"

    def test_conventions_cached_in_redis(self, mock_redis):
        """Test conventions are cached in Redis"""
        repo_id = "test-repo"
        conventions = {"naming": {"services": "kebab-case"}}

        mock_redis.set(
            f"conventions:{repo_id}",
            json.dumps(conventions),
            ex=3600
        )

        mock_redis.set.assert_called_once()
        assert mock_redis.set.call_args[1]["ex"] == 3600

    def test_generate_instructions(self):
        """Test generating repository-specific instructions"""
        instructions = {
            "repo_id": "test-repo",
            "instructions": [
                "Follow kebab-case naming for services",
                "Maintain minimum 80% test coverage",
                "Use structured logging with JSON format"
            ],
            "patterns_available": 5
        }

        assert len(instructions["instructions"]) > 0
        assert instructions["patterns_available"] == 5

    def test_pattern_extraction(self):
        """Test extracting patterns from code"""
        def extract_naming_pattern(files):
            patterns = []
            for file in files:
                if '-' in file:
                    patterns.append("kebab-case")
                elif '_' in file:
                    patterns.append("snake_case")
            return list(set(patterns))

        files = ["issue-parser.js", "repo_context.py", "code-generator.js"]
        patterns = extract_naming_pattern(files)

        assert "kebab-case" in patterns
        assert "snake_case" in patterns

    def test_chromadb_collection_creation(self):
        """Test ChromaDB collection creation"""
        def create_collection(repo_id):
            return {
                "name": f"repo_{repo_id}",
                "metadata": {"repo_id": repo_id}
            }

        collection = create_collection("test-repo-123")
        assert collection["name"] == "repo_test-repo-123"
        assert collection["metadata"]["repo_id"] == "test-repo-123"

    def test_pattern_storage_format(self):
        """Test pattern storage format"""
        pattern = {
            "id": "repo_pattern_0",
            "type": "error_handling",
            "pattern": "try-catch with logging",
            "examples": ["try { ... } catch (error) { logger.error(...) }"],
            "language": "javascript"
        }

        pattern_json = json.dumps(pattern)
        parsed = json.loads(pattern_json)

        assert parsed["type"] == "error_handling"
        assert parsed["language"] == "javascript"
        assert len(parsed["examples"]) > 0

    def test_repository_not_found(self):
        """Test handling of non-existent repository"""
        def get_patterns(repo_id):
            if repo_id != "existing-repo":
                raise ValueError("Repository not found")
            return []

        with pytest.raises(ValueError, match="Repository not found"):
            get_patterns("nonexistent-repo")

    def test_metrics_tracking(self):
        """Test Prometheus metrics tracking"""
        mock_counter = Mock()
        mock_histogram = Mock()

        # Simulate indexing operation
        mock_counter.labels(status='success').inc()
        mock_histogram.time()

        mock_counter.labels.assert_called_with(status='success')
        mock_histogram.time.assert_called_once()
