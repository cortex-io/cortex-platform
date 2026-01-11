"""Redis cache manager"""
import json
import logging
from typing import Any, List, Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis cache manager for storing forecasts and models"""

    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self.redis_client = None

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting key {key} from cache: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL"""
        if not self.redis_client:
            return False

        try:
            serialized = json.dumps(value)
            self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Error setting key {key} in cache: {e}")
            return False

    def delete(self, key: str):
        """Delete key from cache"""
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting key {key} from cache: {e}")
            return False

    def get_keys(self, pattern: str) -> List[str]:
        """Get all keys matching pattern"""
        if not self.redis_client:
            return []

        try:
            return [k for k in self.redis_client.scan_iter(match=pattern)]
        except Exception as e:
            logger.error(f"Error getting keys with pattern {pattern}: {e}")
            return []

    def health_check(self) -> bool:
        """Check if Redis is accessible"""
        if not self.redis_client:
            return False

        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
