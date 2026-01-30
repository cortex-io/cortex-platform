"""
Prometheus Client

Fetches cluster metrics for context injection.
"""

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class ClusterMetrics:
    """Cluster-wide metrics."""
    cpu_usage_percent: float
    memory_usage_percent: float
    pod_count: int
    node_count: int
    events_per_minute: float
    network_receive_bytes: float
    network_transmit_bytes: float


@dataclass
class NodeMetrics:
    """Per-node metrics."""
    name: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    pod_count: int


class PrometheusClient:
    """HTTP client for Prometheus metrics."""

    # Common PromQL queries
    QUERIES = {
        "cpu_usage": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
        "memory_usage": "(1 - (sum(node_memory_MemAvailable_bytes) / sum(node_memory_MemTotal_bytes))) * 100",
        "pod_count": "count(kube_pod_info)",
        "node_count": "count(kube_node_info)",
        "events_per_minute": "sum(rate(kubernetes_events_total[5m])) * 60",
        "network_receive": "sum(rate(node_network_receive_bytes_total{device!~\"lo|veth.*|docker.*|flannel.*|cali.*\"}[5m]))",
        "network_transmit": "sum(rate(node_network_transmit_bytes_total{device!~\"lo|veth.*|docker.*|flannel.*|cali.*\"}[5m]))",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or os.getenv(
            "PROMETHEUS_URL",
            "http://prometheus-server.cortex-system:80"
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

    async def _query(self, promql: str) -> Optional[float]:
        """Execute a PromQL instant query and return the value."""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": promql},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return None

            results = data.get("data", {}).get("result", [])
            if not results:
                return None

            # Return first result value
            value = results[0].get("value", [None, None])[1]
            return float(value) if value else None

        except Exception as e:
            logger.warning("prometheus_query_failed", query=promql[:50], error=str(e))
            return None

    async def health_check(self) -> bool:
        """Check if Prometheus is healthy."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.base_url}/-/healthy", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def get_cluster_metrics(self) -> ClusterMetrics:
        """Get cluster-wide metrics."""
        cpu = await self._query(self.QUERIES["cpu_usage"]) or 0.0
        memory = await self._query(self.QUERIES["memory_usage"]) or 0.0
        pods = await self._query(self.QUERIES["pod_count"]) or 0
        nodes = await self._query(self.QUERIES["node_count"]) or 0
        events = await self._query(self.QUERIES["events_per_minute"]) or 0.0
        net_rx = await self._query(self.QUERIES["network_receive"]) or 0.0
        net_tx = await self._query(self.QUERIES["network_transmit"]) or 0.0

        return ClusterMetrics(
            cpu_usage_percent=round(cpu, 2),
            memory_usage_percent=round(memory, 2),
            pod_count=int(pods),
            node_count=int(nodes),
            events_per_minute=round(events, 2),
            network_receive_bytes=round(net_rx, 2),
            network_transmit_bytes=round(net_tx, 2),
        )

    async def get_node_metrics(self) -> list[NodeMetrics]:
        """Get per-node metrics."""
        client = await self._get_client()

        nodes = []

        try:
            # Get node names first
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": "kube_node_info"},
            )
            response.raise_for_status()
            data = response.json()

            node_names = []
            for result in data.get("data", {}).get("result", []):
                name = result.get("metric", {}).get("node")
                if name:
                    node_names.append(name)

            # Get metrics for each node
            for node_name in node_names[:10]:  # Limit to 10 nodes
                cpu_query = f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle",instance=~"{node_name}.*"}}[5m])) * 100)'
                mem_query = f'(1 - (node_memory_MemAvailable_bytes{{instance=~"{node_name}.*"}} / node_memory_MemTotal_bytes{{instance=~"{node_name}.*"}})) * 100'
                disk_query = f'100 - ((node_filesystem_avail_bytes{{instance=~"{node_name}.*",mountpoint="/"}} / node_filesystem_size_bytes{{instance=~"{node_name}.*",mountpoint="/"}}) * 100)'
                pod_query = f'count(kube_pod_info{{node="{node_name}"}})'

                cpu = await self._query(cpu_query) or 0.0
                mem = await self._query(mem_query) or 0.0
                disk = await self._query(disk_query) or 0.0
                pod_count = await self._query(pod_query) or 0

                nodes.append(NodeMetrics(
                    name=node_name,
                    cpu_percent=round(cpu, 2),
                    memory_percent=round(mem, 2),
                    disk_percent=round(disk, 2),
                    pod_count=int(pod_count),
                ))

        except Exception as e:
            logger.error("prometheus_node_metrics_error", error=str(e))

        return nodes

    async def get_alerts(self) -> list[dict[str, Any]]:
        """Get active alerts from Prometheus/Alertmanager."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.base_url}/api/v1/alerts")
            response.raise_for_status()
            data = response.json()

            alerts = []
            for alert in data.get("data", {}).get("alerts", []):
                if alert.get("state") == "firing":
                    alerts.append({
                        "name": alert.get("labels", {}).get("alertname", "unknown"),
                        "severity": alert.get("labels", {}).get("severity", "unknown"),
                        "summary": alert.get("annotations", {}).get("summary", ""),
                        "description": alert.get("annotations", {}).get("description", ""),
                        "active_at": alert.get("activeAt"),
                    })

            return alerts

        except Exception as e:
            logger.warning("prometheus_alerts_error", error=str(e))
            return []

    async def custom_query(self, promql: str) -> list[dict[str, Any]]:
        """Execute a custom PromQL query."""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": promql},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return []

            return data.get("data", {}).get("result", [])

        except Exception as e:
            logger.error("prometheus_custom_query_error", error=str(e))
            return []
