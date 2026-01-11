"""Prometheus client for fetching metrics"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from prometheus_api_client import PrometheusConnect
from app.config import settings

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for querying Prometheus metrics"""

    def __init__(self):
        self.prom = PrometheusConnect(
            url=settings.prometheus_url,
            disable_ssl=True
        )

    def get_node_cpu_usage(self, days: int = 30) -> pd.DataFrame:
        """Get historical node CPU usage"""
        query = '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
        return self._fetch_metric_range(query, days)

    def get_node_memory_usage(self, days: int = 30) -> pd.DataFrame:
        """Get historical node memory usage"""
        query = '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))'
        return self._fetch_metric_range(query, days)

    def get_node_disk_usage(self, days: int = 30) -> pd.DataFrame:
        """Get historical node disk usage"""
        query = '100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)'
        return self._fetch_metric_range(query, days)

    def get_pod_cpu_usage(self, namespace: Optional[str] = None, days: int = 30) -> pd.DataFrame:
        """Get historical pod CPU usage"""
        if namespace:
            query = f'sum by (pod, namespace) (rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))'
        else:
            query = 'sum by (pod, namespace) (rate(container_cpu_usage_seconds_total[5m]))'
        return self._fetch_metric_range(query, days)

    def get_pod_memory_usage(self, namespace: Optional[str] = None, days: int = 30) -> pd.DataFrame:
        """Get historical pod memory usage"""
        if namespace:
            query = f'sum by (pod, namespace) (container_memory_usage_bytes{{namespace="{namespace}"}})'
        else:
            query = 'sum by (pod, namespace) (container_memory_usage_bytes)'
        return self._fetch_metric_range(query, days)

    def get_network_traffic(self, days: int = 30) -> pd.DataFrame:
        """Get historical network traffic"""
        query = 'sum by (instance) (rate(node_network_receive_bytes_total[5m]) + rate(node_network_transmit_bytes_total[5m]))'
        return self._fetch_metric_range(query, days)

    def get_pvc_usage(self, days: int = 30) -> pd.DataFrame:
        """Get historical PVC usage"""
        query = '100 * (kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes)'
        return self._fetch_metric_range(query, days)

    def get_request_rate(self, namespace: Optional[str] = None, days: int = 30) -> pd.DataFrame:
        """Get historical request rates"""
        if namespace:
            query = f'sum by (namespace, service) (rate(http_requests_total{{namespace="{namespace}"}}[5m]))'
        else:
            query = 'sum by (namespace, service) (rate(http_requests_total[5m]))'
        return self._fetch_metric_range(query, days)

    def _fetch_metric_range(self, query: str, days: int) -> pd.DataFrame:
        """Fetch metric data for a time range"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            logger.info(f"Fetching metric: {query} from {start_time} to {end_time}")

            metric_data = self.prom.custom_query_range(
                query=query,
                start_time=start_time,
                end_time=end_time,
                step='5m'
            )

            if not metric_data:
                logger.warning(f"No data returned for query: {query}")
                return pd.DataFrame()

            # Convert to DataFrame
            dfs = []
            for metric in metric_data:
                labels = metric.get('metric', {})
                values = metric.get('values', [])

                if not values:
                    continue

                df = pd.DataFrame(values, columns=['timestamp', 'value'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df['value'] = pd.to_numeric(df['value'], errors='coerce')

                # Add label columns
                for key, val in labels.items():
                    df[key] = val

                dfs.append(df)

            if not dfs:
                return pd.DataFrame()

            result = pd.concat(dfs, ignore_index=True)
            result = result.sort_values('timestamp')

            logger.info(f"Fetched {len(result)} data points")
            return result

        except Exception as e:
            logger.error(f"Error fetching metric: {e}")
            return pd.DataFrame()

    def get_current_value(self, query: str) -> Optional[float]:
        """Get current value for a metric"""
        try:
            result = self.prom.custom_query(query)
            if result and len(result) > 0:
                return float(result[0]['value'][1])
            return None
        except Exception as e:
            logger.error(f"Error fetching current value: {e}")
            return None

    def health_check(self) -> bool:
        """Check if Prometheus is accessible"""
        try:
            self.prom.custom_query('up')
            return True
        except Exception as e:
            logger.error(f"Prometheus health check failed: {e}")
            return False
