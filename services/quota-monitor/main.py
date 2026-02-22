#!/usr/bin/env python3
"""
Cortex ResourceQuota Monitor

Monitors Kubernetes ResourceQuotas and alerts when usage exceeds thresholds.
Integrates with Memory Service for historical tracking.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel
import httpx
import redis.asyncio as redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("quota-monitor")


class QuotaStatus(BaseModel):
    namespace: str
    name: str
    resource: str
    used: str
    hard: str
    percentage: float
    status: str  # ok, warning, critical


class QuotaSummary(BaseModel):
    timestamp: datetime
    total_quotas: int
    ok: int
    warning: int
    critical: int
    quotas: List[QuotaStatus]


class AlertConfig(BaseModel):
    warning_threshold: float = 0.75  # 75%
    critical_threshold: float = 0.90  # 90%


class QuotaMonitor:
    def __init__(
        self,
        memory_service_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        warning_threshold: float = 0.75,
        critical_threshold: float = 0.90,
    ):
        self.memory_service_url = memory_service_url
        self.redis_url = redis_url
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.k8s_core: Optional[client.CoreV1Api] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self._redis: Optional[redis.Redis] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        # Rolling history window: keep 48 samples (48 × 60s = 48 min at 1/min)
        self._history_window = int(os.getenv("QUOTA_HISTORY_WINDOW", "2880"))  # 48h at 1/min

    async def start(self):
        logger.info("Starting Quota Monitor...")

        # Connect to Kubernetes
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.k8s_core = client.CoreV1Api()

        # HTTP client for memory service
        if self.memory_service_url:
            self.http_client = httpx.AsyncClient(timeout=10.0)

        # Connect to Redis for quota history
        if self.redis_url:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
                logger.info("Connected to Redis for quota history")
            except Exception as e:
                logger.warning(f"Redis unavailable, history disabled: {e}")
                self._redis = None

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Quota Monitor started")

    async def stop(self):
        logger.info("Stopping Quota Monitor...")
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        if self.http_client:
            await self.http_client.aclose()
        if self._redis:
            await self._redis.aclose()

    def _parse_quantity(self, quantity: str) -> float:
        """Parse Kubernetes quantity string to float."""
        if not quantity:
            return 0.0

        quantity = str(quantity)

        # Handle memory units
        if quantity.endswith("Ki"):
            return float(quantity[:-2]) * 1024
        elif quantity.endswith("Mi"):
            return float(quantity[:-2]) * 1024 * 1024
        elif quantity.endswith("Gi"):
            return float(quantity[:-2]) * 1024 * 1024 * 1024
        elif quantity.endswith("Ti"):
            return float(quantity[:-2]) * 1024 * 1024 * 1024 * 1024

        # Handle CPU units
        elif quantity.endswith("m"):
            return float(quantity[:-1]) / 1000

        # Plain number
        try:
            return float(quantity)
        except ValueError:
            return 0.0

    async def get_all_quotas(self) -> QuotaSummary:
        """Get status of all ResourceQuotas in the cluster."""
        quotas = []
        ok = 0
        warning = 0
        critical = 0

        try:
            quota_list = self.k8s_core.list_resource_quota_for_all_namespaces()

            for rq in quota_list.items:
                namespace = rq.metadata.namespace
                name = rq.metadata.name

                used = rq.status.used or {}
                hard = rq.status.hard or {}

                for resource, hard_value in hard.items():
                    used_value = used.get(resource, "0")

                    hard_num = self._parse_quantity(hard_value)
                    used_num = self._parse_quantity(used_value)

                    if hard_num > 0:
                        percentage = used_num / hard_num
                    else:
                        percentage = 0.0

                    # Determine status
                    if percentage >= self.critical_threshold:
                        status = "critical"
                        critical += 1
                    elif percentage >= self.warning_threshold:
                        status = "warning"
                        warning += 1
                    else:
                        status = "ok"
                        ok += 1

                    quotas.append(QuotaStatus(
                        namespace=namespace,
                        name=name,
                        resource=resource,
                        used=used_value,
                        hard=hard_value,
                        percentage=round(percentage * 100, 2),
                        status=status,
                    ))

        except ApiException as e:
            logger.error(f"Failed to list quotas: {e}")

        # Sort by percentage descending
        quotas.sort(key=lambda q: q.percentage, reverse=True)

        return QuotaSummary(
            timestamp=datetime.now(),
            total_quotas=len(quotas),
            ok=ok,
            warning=warning,
            critical=critical,
            quotas=quotas,
        )

    async def get_namespace_quota(self, namespace: str) -> List[QuotaStatus]:
        """Get quota status for a specific namespace."""
        quotas = []

        try:
            quota_list = self.k8s_core.list_namespaced_resource_quota(namespace)

            for rq in quota_list.items:
                used = rq.status.used or {}
                hard = rq.status.hard or {}

                for resource, hard_value in hard.items():
                    used_value = used.get(resource, "0")

                    hard_num = self._parse_quantity(hard_value)
                    used_num = self._parse_quantity(used_value)

                    if hard_num > 0:
                        percentage = used_num / hard_num
                    else:
                        percentage = 0.0

                    if percentage >= self.critical_threshold:
                        status = "critical"
                    elif percentage >= self.warning_threshold:
                        status = "warning"
                    else:
                        status = "ok"

                    quotas.append(QuotaStatus(
                        namespace=namespace,
                        name=rq.metadata.name,
                        resource=resource,
                        used=used_value,
                        hard=hard_value,
                        percentage=round(percentage * 100, 2),
                        status=status,
                    ))

        except ApiException as e:
            logger.error(f"Failed to get quota for {namespace}: {e}")

        return quotas

    async def check_and_alert(self) -> List[QuotaStatus]:
        """Check quotas and return any that are in warning or critical state."""
        summary = await self.get_all_quotas()

        alerts = [q for q in summary.quotas if q.status in ["warning", "critical"]]

        # Persist rolling quota snapshot to Redis for trend analysis
        if self._redis:
            try:
                ts = summary.timestamp.timestamp()
                snapshot = {
                    "timestamp": summary.timestamp.isoformat(),
                    "total": summary.total_quotas,
                    "ok": summary.ok,
                    "warning": summary.warning,
                    "critical": summary.critical,
                    "quotas": [q.model_dump() for q in summary.quotas],
                }
                pipe = self._redis.pipeline()
                # Sorted set: score = unix timestamp, member = JSON snapshot
                pipe.zadd("quota:history", {json.dumps(snapshot): ts})
                # Trim to configured window
                pipe.zremrangebyrank("quota:history", 0, -(self._history_window + 1))
                # Per-namespace/resource time series for quick trend queries
                for q in summary.quotas:
                    key = f"quota:ts:{q.namespace}:{q.resource}"
                    pipe.zadd(key, {str(q.percentage): ts})
                    pipe.zremrangebyrank(key, 0, -(self._history_window + 1))
                await pipe.execute()
            except Exception as e:
                logger.warning(f"Failed to persist quota history to Redis: {e}")

        if alerts:
            logger.warning(f"Found {len(alerts)} quota alerts:")
            for alert in alerts:
                logger.warning(
                    f"  [{alert.status.upper()}] {alert.namespace}/{alert.name} "
                    f"{alert.resource}: {alert.used}/{alert.hard} ({alert.percentage}%)"
                )

            # Record to memory service if available
            if self.http_client and self.memory_service_url:
                try:
                    for alert in alerts:
                        await self.http_client.post(
                            f"{self.memory_service_url}/memory/timeline/event",
                            json={
                                "event_type": "infrastructure_change",
                                "source": "quota-monitor",
                                "description": f"ResourceQuota {alert.status}: {alert.namespace}/{alert.resource} at {alert.percentage}%",
                                "details": {
                                    "namespace": alert.namespace,
                                    "quota_name": alert.name,
                                    "resource": alert.resource,
                                    "used": alert.used,
                                    "hard": alert.hard,
                                    "percentage": alert.percentage,
                                },
                                "affected_components": [alert.namespace],
                                "severity": "high" if alert.status == "critical" else "medium",
                            },
                        )
                except Exception as e:
                    logger.error(f"Failed to record alert to memory service: {e}")

        return alerts

    async def get_quota_trend(self, namespace: str, resource: str, limit: int = 60) -> List[Dict]:
        """Return recent percentage samples for a namespace/resource from Redis."""
        if not self._redis:
            return []
        key = f"quota:ts:{namespace}:{resource}"
        raw = await self._redis.zrange(key, -limit, -1, withscores=True)
        return [{"percentage": float(member), "timestamp": score} for member, score in raw]

    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                await self.check_and_alert()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            await asyncio.sleep(60)  # Check every minute


# =============================================================================
# FastAPI Application
# =============================================================================

monitor: Optional[QuotaMonitor] = None

app = FastAPI(title="Cortex Quota Monitor", version="1.0.0")


@app.on_event("startup")
async def startup():
    global monitor
    monitor = QuotaMonitor(
        memory_service_url=os.getenv("MEMORY_SERVICE_URL"),
        redis_url=os.getenv("REDIS_URL", "redis://redis-queue:6379"),
        warning_threshold=float(os.getenv("WARNING_THRESHOLD", "0.75")),
        critical_threshold=float(os.getenv("CRITICAL_THRESHOLD", "0.90")),
    )
    await monitor.start()


@app.on_event("shutdown")
async def shutdown():
    if monitor:
        await monitor.stop()


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/quotas")
async def get_quotas():
    """Get all ResourceQuota statuses."""
    return await monitor.get_all_quotas()


@app.get("/quotas/{namespace}")
async def get_namespace_quotas(namespace: str):
    """Get quota status for a specific namespace."""
    quotas = await monitor.get_namespace_quota(namespace)
    if not quotas:
        raise HTTPException(404, f"No quotas found for namespace: {namespace}")
    return {"namespace": namespace, "quotas": quotas}


@app.get("/alerts")
async def get_alerts():
    """Get current quota alerts (warning and critical)."""
    alerts = await monitor.check_and_alert()
    return {
        "alert_count": len(alerts),
        "alerts": alerts,
    }


@app.get("/metrics")
async def get_metrics():
    """Prometheus-compatible metrics endpoint."""
    summary = await monitor.get_all_quotas()

    lines = [
        "# HELP cortex_quota_usage_percent ResourceQuota usage percentage",
        "# TYPE cortex_quota_usage_percent gauge",
    ]

    for q in summary.quotas:
        lines.append(
            f'cortex_quota_usage_percent{{namespace="{q.namespace}",name="{q.name}",resource="{q.resource}"}} {q.percentage}'
        )

    lines.extend([
        "",
        "# HELP cortex_quota_alerts_total Total quota alerts by status",
        "# TYPE cortex_quota_alerts_total gauge",
        f"cortex_quota_alerts_total{{status=\"ok\"}} {summary.ok}",
        f"cortex_quota_alerts_total{{status=\"warning\"}} {summary.warning}",
        f"cortex_quota_alerts_total{{status=\"critical\"}} {summary.critical}",
    ])

    return "\n".join(lines)


@app.get("/history")
async def get_history(limit: int = 60):
    """Get rolling quota snapshot history from Redis (up to `limit` samples)."""
    if not monitor._redis:
        raise HTTPException(503, "Redis unavailable")
    raw = await monitor._redis.zrange("quota:history", -limit, -1, withscores=True)
    snapshots = []
    for member, score in raw:
        snap = json.loads(member)
        snap["_score"] = score
        snapshots.append(snap)
    return {"count": len(snapshots), "snapshots": snapshots}


@app.get("/trend/{namespace}/{resource}")
async def get_trend(namespace: str, resource: str, limit: int = 60):
    """Get percentage trend for a specific namespace/resource."""
    trend = await monitor.get_quota_trend(namespace, resource, limit)
    if not trend:
        raise HTTPException(404, f"No trend data for {namespace}/{resource}")
    return {"namespace": namespace, "resource": resource, "samples": trend}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
