"""
Redis-backed operation log and branch locking.

Two concerns:
  - OpLog: every git write (commit/push/revert/merge) is recorded with caller,
    repo, branch, commit hash, timestamp. Queryable by repo or caller.
  - BranchLock: a distributed lock per (repo, branch) so implementation-worker
    and health-monitor cannot race on cortex-gitops/main simultaneously.
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import redis.asyncio as redis
import structlog

log = structlog.get_logger()

OP_LOG_KEY = "git-steer:ops"           # ZADD score=epoch, member=op_id
OP_DATA_PREFIX = "git-steer:op:"       # HASH per op
LOCK_PREFIX = "git-steer:lock:"        # STRING with caller, TTL 120s


class GitSteerStore:
    def __init__(self, url: Optional[str] = None):
        self._url = url or os.getenv("REDIS_URL")
        self._r: Optional[redis.Redis] = None
        self._available = False

    async def connect(self):
        if not self._url:
            log.warning("git_steer_store_no_redis", msg="Redis URL not set — op log and locking disabled")
            return
        try:
            self._r = redis.from_url(self._url, decode_responses=True)
            await self._r.ping()
            self._available = True
            log.info("git_steer_store_connected", url=self._url)
        except Exception as e:
            log.warning("git_steer_store_unavailable", error=str(e))

    async def close(self):
        if self._r:
            await self._r.aclose()
            self._r = None
            self._available = False

    # -------------------------------------------------------------------------
    # Operation log
    # -------------------------------------------------------------------------

    async def log_op(
        self,
        op_type: str,           # e.g. "commit", "push", "revert", "create_pr"
        repo: str,
        branch: str,
        caller: str,            # e.g. "implementation-worker", "human", "claude-code"
        result: dict,           # whatever the operation returned
        error: Optional[str] = None,
    ) -> str:
        op_id = str(uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "op_id": op_id,
            "op_type": op_type,
            "repo": repo,
            "branch": branch,
            "caller": caller,
            "timestamp": now.isoformat(),
            "result": json.dumps(result),
            "error": error or "",
        }
        if self._available and self._r:
            try:
                pipe = self._r.pipeline()
                pipe.hset(f"{OP_DATA_PREFIX}{op_id}", mapping=record)
                pipe.expire(f"{OP_DATA_PREFIX}{op_id}", 86400 * 30)  # 30-day TTL
                pipe.zadd(OP_LOG_KEY, {op_id: now.timestamp()})
                await pipe.execute()
            except Exception as e:
                log.warning("git_steer_log_op_error", error=str(e))
        return op_id

    async def get_ops(
        self,
        repo: Optional[str] = None,
        caller: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        if not self._available or not self._r:
            return []
        try:
            op_ids = await self._r.zrevrange(OP_LOG_KEY, 0, limit * 3 - 1)
            ops = []
            for op_id in op_ids:
                data = await self._r.hgetall(f"{OP_DATA_PREFIX}{op_id}")
                if not data:
                    continue
                if repo and data.get("repo") != repo:
                    continue
                if caller and data.get("caller") != caller:
                    continue
                ops.append(data)
                if len(ops) >= limit:
                    break
            return ops
        except Exception as e:
            log.warning("git_steer_get_ops_error", error=str(e))
            return []

    # -------------------------------------------------------------------------
    # Branch locking
    # -------------------------------------------------------------------------

    @asynccontextmanager
    async def branch_lock(self, repo: str, branch: str, caller: str, ttl: int = 120):
        """
        Async context manager that acquires a per-(repo, branch) lock.
        Raises RuntimeError if the lock is already held.
        Degrades gracefully (no-op) when Redis is unavailable.
        """
        lock_key = f"{LOCK_PREFIX}{repo}:{branch}"
        acquired = False
        if self._available and self._r:
            try:
                acquired = await self._r.set(
                    lock_key, caller, nx=True, ex=ttl
                )
                if not acquired:
                    holder = await self._r.get(lock_key)
                    raise RuntimeError(
                        f"Branch {repo}/{branch} is locked by '{holder}'. "
                        f"Wait for that operation to complete."
                    )
            except RuntimeError:
                raise
            except Exception as e:
                log.warning("git_steer_lock_error", error=str(e))
                acquired = False  # degrade gracefully
        try:
            yield
        finally:
            if acquired and self._available and self._r:
                try:
                    await self._r.delete(lock_key)
                except Exception:
                    pass

    async def get_lock_status(self, repo: str, branch: str) -> Optional[str]:
        """Return the caller holding the lock, or None if unlocked."""
        if not self._available or not self._r:
            return None
        key = f"{LOCK_PREFIX}{repo}:{branch}"
        try:
            return await self._r.get(key)
        except Exception:
            return None
