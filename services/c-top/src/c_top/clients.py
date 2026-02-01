"""API clients for c-top monitoring"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import subprocess
import json
import logging

from kubernetes import client, config
from prometheus_api_client import PrometheusConnect
import redis
import httpx

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for querying Prometheus metrics"""

    def __init__(self, url: str = "http://prometheus-server.cortex-system:80"):
        self.url = url
        self.prom: Optional[PrometheusConnect] = None
        self._initialize()

    def _initialize(self):
        """Initialize Prometheus connection with fallback"""
        try:
            self.prom = PrometheusConnect(url=self.url, disable_ssl=True)
            self.prom.check_prometheus_connection()
            logger.info(f"Connected to Prometheus at {self.url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Prometheus: {e}")
            self.prom = None

    def get_cluster_cpu(self) -> int:
        """Get cluster-wide CPU usage percentage"""
        if not self.prom:
            return 0
        try:
            query = '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
            result = self.prom.custom_query(query)
            if result and len(result) > 0:
                return int(float(result[0]["value"][1]))
        except Exception as e:
            logger.debug(f"CPU query failed: {e}")
        return 0

    def get_cluster_memory(self) -> int:
        """Get cluster-wide memory usage percentage"""
        if not self.prom:
            return 0
        try:
            query = '(1 - (sum(node_memory_MemAvailable_bytes) / sum(node_memory_MemTotal_bytes))) * 100'
            result = self.prom.custom_query(query)
            if result and len(result) > 0:
                return int(float(result[0]["value"][1]))
        except Exception as e:
            logger.debug(f"Memory query failed: {e}")
        return 0

    def get_cluster_disk(self) -> int:
        """Get cluster-wide disk usage percentage"""
        if not self.prom:
            return 0
        try:
            query = '(1 - (sum(node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"}) / sum(node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"}))) * 100'
            result = self.prom.custom_query(query)
            if result and len(result) > 0:
                return int(float(result[0]["value"][1]))
        except Exception as e:
            logger.debug(f"Disk query failed: {e}")
        return 0

    def get_node_metrics(self, node_name: str) -> Dict[str, int]:
        """Get CPU, memory, and disk for a specific node"""
        if not self.prom:
            return {"cpu": 0, "mem": 0, "disk": 0}

        metrics = {"cpu": 0, "mem": 0, "disk": 0}
        try:
            cpu_query = f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle",instance=~"{node_name}.*"}}[5m])) * 100)'
            cpu_result = self.prom.custom_query(cpu_query)
            if cpu_result and len(cpu_result) > 0:
                metrics["cpu"] = int(float(cpu_result[0]["value"][1]))

            mem_query = f'(1 - (node_memory_MemAvailable_bytes{{instance=~"{node_name}.*"}} / node_memory_MemTotal_bytes{{instance=~"{node_name}.*"}})) * 100'
            mem_result = self.prom.custom_query(mem_query)
            if mem_result and len(mem_result) > 0:
                metrics["mem"] = int(float(mem_result[0]["value"][1]))

            disk_query = f'(1 - (node_filesystem_avail_bytes{{instance=~"{node_name}.*",mountpoint="/",fstype!="tmpfs"}} / node_filesystem_size_bytes{{instance=~"{node_name}.*",mountpoint="/",fstype!="tmpfs"}})) * 100'
            disk_result = self.prom.custom_query(disk_query)
            if disk_result and len(disk_result) > 0:
                metrics["disk"] = int(float(disk_result[0]["value"][1]))
        except Exception as e:
            logger.debug(f"Node metrics query failed for {node_name}: {e}")

        return metrics

    def get_network_io(self) -> Dict[str, int]:
        """Get cluster-wide network I/O (bytes per second)"""
        if not self.prom:
            return {"in": 0, "out": 0}

        metrics = {"in": 0, "out": 0}
        try:
            in_query = 'sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|flannel.*|cali.*"}[1m]))'
            in_result = self.prom.custom_query(in_query)
            if in_result and len(in_result) > 0:
                metrics["in"] = int(float(in_result[0]["value"][1]))

            out_query = 'sum(rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|flannel.*|cali.*"}[1m]))'
            out_result = self.prom.custom_query(out_query)
            if out_result and len(out_result) > 0:
                metrics["out"] = int(float(out_result[0]["value"][1]))
        except Exception as e:
            logger.debug(f"Network I/O query failed: {e}")

        return metrics

    def get_api_latency(self) -> int:
        """Get Kubernetes API server request latency (milliseconds)"""
        if not self.prom:
            return 0
        try:
            query = 'histogram_quantile(0.95, sum(rate(apiserver_request_duration_seconds_bucket{verb!="WATCH"}[5m])) by (le)) * 1000'
            result = self.prom.custom_query(query)
            if result and len(result) > 0:
                return int(float(result[0]["value"][1]))
        except Exception as e:
            logger.debug(f"API latency query failed: {e}")
        return 0


class KubernetesClient:
    """Client for querying Kubernetes API"""

    def __init__(self):
        self.v1: Optional[client.CoreV1Api] = None
        self.batch_v1: Optional[client.BatchV1Api] = None
        self._initialize()

    def _initialize(self):
        """Initialize Kubernetes client"""
        try:
            config.load_incluster_config()
        except:
            try:
                config.load_kube_config()
            except Exception as e:
                logger.error(f"Failed to load kubeconfig: {e}")
                raise

        self.v1 = client.CoreV1Api()
        self.batch_v1 = client.BatchV1Api()
        logger.info("Kubernetes client initialized")

    def get_nodes(self) -> List[client.V1Node]:
        """Get all nodes"""
        if not self.v1:
            return []
        return self.v1.list_node().items

    def get_pods(self, namespace: Optional[str] = None) -> List[client.V1Pod]:
        """Get all pods or pods in a specific namespace"""
        if not self.v1:
            return []
        if namespace:
            return self.v1.list_namespaced_pod(namespace).items
        return self.v1.list_pod_for_all_namespaces().items

    def get_jobs(self, namespace: Optional[str] = None) -> List:
        """Get all jobs or jobs in a specific namespace"""
        if not self.batch_v1:
            return []
        if namespace:
            return self.batch_v1.list_namespaced_job(namespace).items
        return self.batch_v1.list_job_for_all_namespaces().items

    def get_events(self, limit: int = 100) -> List:
        """Get recent cluster events"""
        if not self.v1:
            return []
        return self.v1.list_event_for_all_namespaces(limit=limit).items

    def get_pod_distribution(self) -> Dict[str, int]:
        """Get pod count per namespace"""
        if not self.v1:
            return {}
        try:
            pods = self.get_pods()
            distribution = {}
            for pod in pods:
                namespace = pod.metadata.namespace
                distribution[namespace] = distribution.get(namespace, 0) + 1
            return dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True))
        except Exception as e:
            logger.error(f"Failed to get pod distribution: {e}")
            return {}

    def get_services(self, namespace: str = "cortex-system") -> List[Dict[str, Any]]:
        """Get services with their status"""
        if not self.v1:
            return []
        try:
            services = []
            svc_list = self.v1.list_namespaced_service(namespace)
            for svc in svc_list.items:
                # Get pods matching this service
                selector = svc.spec.selector or {}
                label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])

                ready = 0
                total = 0
                if label_selector:
                    pods = self.v1.list_namespaced_pod(namespace, label_selector=label_selector)
                    total = len(pods.items)
                    ready = sum(1 for p in pods.items if p.status.phase == "Running")

                services.append({
                    "name": svc.metadata.name,
                    "ready": ready,
                    "total": total,
                    "type": svc.spec.type,
                })
            return services
        except Exception as e:
            logger.error(f"Failed to get services: {e}")
            return []


class RedisClient:
    """Client for querying Redis agent registry and streams"""

    AGENT_REGISTRY_PREFIX = "cortex:agent:registry:"
    AGENT_STREAM_PREFIX = "cortex:agent:stream:"
    RESULT_PREFIX = "cortex:agent:result:"

    def __init__(self, host: str = "redis.cortex-system", port: int = 6379):
        self.host = host
        self.port = port
        self.client: Optional[redis.Redis] = None
        self._initialize()

    def _initialize(self):
        """Initialize Redis connection"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self.client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self.client = None

    def get_agents(self) -> List[Dict[str, Any]]:
        """Get all registered agents"""
        if not self.client:
            return []

        agents = []
        try:
            # Scan for all agent registry keys
            cursor = 0
            while True:
                cursor, keys = self.client.scan(
                    cursor, match=f"{self.AGENT_REGISTRY_PREFIX}*", count=100
                )
                for key in keys:
                    agent_data = self.client.hgetall(key)
                    if agent_data:
                        # Parse capabilities if stored as JSON
                        if "capabilities" in agent_data:
                            try:
                                agent_data["capabilities"] = json.loads(agent_data["capabilities"])
                            except:
                                agent_data["capabilities"] = []
                        agents.append(agent_data)
                if cursor == 0:
                    break
        except Exception as e:
            logger.debug(f"Failed to get agents: {e}")

        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent by ID"""
        if not self.client:
            return None

        try:
            key = f"{self.AGENT_REGISTRY_PREFIX}{agent_id}"
            agent_data = self.client.hgetall(key)
            if agent_data:
                if "capabilities" in agent_data:
                    try:
                        agent_data["capabilities"] = json.loads(agent_data["capabilities"])
                    except:
                        agent_data["capabilities"] = []
                return agent_data
        except Exception as e:
            logger.debug(f"Failed to get agent {agent_id}: {e}")

        return None

    def get_stream_length(self, agent_id: str) -> int:
        """Get the number of pending messages in an agent's stream"""
        if not self.client:
            return 0

        try:
            key = f"{self.AGENT_STREAM_PREFIX}{agent_id}"
            return self.client.xlen(key)
        except Exception as e:
            logger.debug(f"Failed to get stream length for {agent_id}: {e}")
            return 0

    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent task results"""
        if not self.client:
            return []

        results = []
        try:
            cursor = 0
            while True:
                cursor, keys = self.client.scan(
                    cursor, match=f"{self.RESULT_PREFIX}*", count=100
                )
                for key in keys:
                    result_data = self.client.get(key)
                    if result_data:
                        try:
                            results.append(json.loads(result_data))
                        except:
                            pass
                if cursor == 0 or len(results) >= limit:
                    break
        except Exception as e:
            logger.debug(f"Failed to get recent results: {e}")

        return results[:limit]

    def get_worker_stats(self) -> Dict[str, int]:
        """Get aggregate worker statistics"""
        agents = self.get_agents()

        stats = {
            "active": 0,
            "idle": 0,
            "busy": 0,
            "unhealthy": 0,
            "total": len(agents),
        }

        for agent in agents:
            status = agent.get("status", "unknown")
            if status == "ready" or status == "idle":
                stats["idle"] += 1
            elif status == "busy":
                stats["busy"] += 1
                stats["active"] += 1
            elif status == "unhealthy":
                stats["unhealthy"] += 1
            elif status in ("starting", "stopping"):
                stats["active"] += 1

        return stats


class TailscaleClient:
    """Client for querying Tailscale mesh status via CLI"""

    # Possible CLI locations (PATH, macOS app bundle, Linux)
    CLI_PATHS = [
        "tailscale",  # In PATH
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",  # macOS app
        "/usr/bin/tailscale",  # Linux
        "/usr/local/bin/tailscale",  # Homebrew or manual install
    ]

    def __init__(self):
        self.available = False
        self.cli_path = None
        self._check_availability()

    def _check_availability(self):
        """Check if tailscale CLI is available, trying multiple paths"""
        for cli_path in self.CLI_PATHS:
            try:
                result = subprocess.run(
                    [cli_path, "version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.available = True
                    self.cli_path = cli_path
                    logger.info(f"Tailscale CLI available at {cli_path}")
                    return
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        logger.warning("Tailscale CLI not available at any known location")
        self.available = False

    def get_status(self) -> Dict[str, Any]:
        """Get tailscale status as JSON"""
        if not self.available or not self.cli_path:
            return {}

        try:
            result = subprocess.run(
                [self.cli_path, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.debug(f"Failed to get tailscale status: {e}")

        return {}

    def get_peers(self) -> List[Dict[str, Any]]:
        """Get list of peers with their status"""
        status = self.get_status()
        if not status:
            return []

        peers = []
        peer_map = status.get("Peer", {})

        for peer_key, peer_info in peer_map.items():
            peers.append({
                "id": peer_key[:8],
                "name": peer_info.get("HostName", "unknown"),
                "dns_name": peer_info.get("DNSName", ""),
                "ip": peer_info.get("TailscaleIPs", [None])[0],
                "online": peer_info.get("Online", False),
                "active": peer_info.get("Active", False),
                "relay": peer_info.get("Relay", ""),  # Empty = direct connection
                "connection_type": "relay" if peer_info.get("Relay") else "direct",
                "rx_bytes": peer_info.get("RxBytes", 0),
                "tx_bytes": peer_info.get("TxBytes", 0),
                "os": peer_info.get("OS", ""),
                "last_seen": peer_info.get("LastSeen", ""),
            })

        return peers

    def get_self_status(self) -> Dict[str, Any]:
        """Get this machine's tailscale status"""
        status = self.get_status()
        if not status:
            return {"connected": False}

        return {
            "connected": status.get("BackendState") == "Running",
            "ip": status.get("TailscaleIPs", [None])[0],
            "health": status.get("Health", []),
            "version": status.get("Version", ""),
        }

    def ping_peer(self, peer_ip: str) -> Optional[float]:
        """Ping a peer and return latency in ms"""
        if not self.available:
            return None

        try:
            result = subprocess.run(
                ["tailscale", "ping", "--c", "1", peer_ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse "pong from hostname (IP) via DERP(region) in 45ms"
                # or "pong from hostname (IP) via IP:port in 12ms"
                output = result.stdout
                if "in " in output and "ms" in output:
                    ms_part = output.split("in ")[-1].split("ms")[0]
                    return float(ms_part)
        except (subprocess.TimeoutExpired, ValueError) as e:
            logger.debug(f"Failed to ping {peer_ip}: {e}")

        return None

    def get_mesh_summary(self) -> Dict[str, Any]:
        """Get a summary of the mesh network"""
        peers = self.get_peers()
        self_status = self.get_self_status()

        online_peers = [p for p in peers if p["online"]]
        direct_peers = [p for p in online_peers if p["connection_type"] == "direct"]
        relay_peers = [p for p in online_peers if p["connection_type"] == "relay"]

        return {
            "connected": self_status.get("connected", False),
            "self_ip": self_status.get("ip"),
            "total_peers": len(peers),
            "online_peers": len(online_peers),
            "direct_connections": len(direct_peers),
            "relay_connections": len(relay_peers),
            "peers": peers,
        }


class MCPClient:
    """Client for discovering MCP servers from K8s and local configs"""

    # Default Claude Desktop config location
    CLAUDE_DESKTOP_CONFIG = "~/Library/Application Support/Claude/claude_desktop_config.json"
    MCP_NAMESPACE = "cortex-mcp"

    def __init__(self, k8s_client: Optional["KubernetesClient"] = None):
        self.k8s = k8s_client
        self.servers: List[Dict[str, Any]] = []
        self.available = True
        self._discover_servers()

    def _discover_servers(self):
        """Discover MCP servers from all sources"""
        self.servers = []

        # 1. Discover from Claude Desktop config
        self._discover_from_claude_config()

        # 2. Discover from K8s cortex-mcp namespace
        self._discover_from_k8s()

        logger.info(f"Discovered {len(self.servers)} MCP servers")

    def _discover_from_claude_config(self):
        """Read MCP servers from Claude Desktop config"""
        import os
        config_path = os.path.expanduser(self.CLAUDE_DESKTOP_CONFIG)

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            mcp_servers = config.get("mcpServers", {})
            for name, server_config in mcp_servers.items():
                command = server_config.get("command", "")
                args = server_config.get("args", [])

                # Determine if it's a remote MCP server
                is_remote = "mcp-remote" in args or any("http" in str(a) for a in args)

                self.servers.append({
                    "name": name,
                    "source": "claude-desktop",
                    "connected": True,  # Assume connected if in config
                    "is_hub": name == "cortex-desktop" or "unified" in name.lower(),
                    "tools": 0,  # Would need to query the server
                    "command": command,
                    "remote": is_remote,
                })
                logger.debug(f"Found MCP server from Claude config: {name}")

        except FileNotFoundError:
            logger.debug("Claude Desktop config not found")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude Desktop config: {e}")
        except Exception as e:
            logger.debug(f"Error reading Claude config: {e}")

    def _discover_from_k8s(self):
        """Discover MCP servers from K8s deployments"""
        if not self.k8s or not self.k8s.v1:
            return

        try:
            # Get deployments in cortex-mcp namespace
            apps_v1 = client.AppsV1Api()
            deployments = apps_v1.list_namespaced_deployment(self.MCP_NAMESPACE)

            for dep in deployments.items:
                name = dep.metadata.name
                replicas = dep.status.ready_replicas or 0
                desired = dep.spec.replicas or 0

                # Check if this looks like an MCP server
                if "mcp" in name.lower() or "server" in name.lower():
                    self.servers.append({
                        "name": name,
                        "source": "kubernetes",
                        "connected": replicas > 0,
                        "is_hub": "unified" in name.lower() or "hub" in name.lower(),
                        "tools": 0,  # Would need to query
                        "replicas": replicas,
                        "desired_replicas": desired,
                        "namespace": self.MCP_NAMESPACE,
                    })
                    logger.debug(f"Found MCP server from K8s: {name}")

        except client.ApiException as e:
            if e.status == 404:
                logger.debug(f"Namespace {self.MCP_NAMESPACE} not found")
            else:
                logger.warning(f"Failed to list K8s deployments: {e}")
        except Exception as e:
            logger.debug(f"Error discovering K8s MCP servers: {e}")

    def get_servers(self) -> List[Dict[str, Any]]:
        """Get list of discovered MCP servers"""
        return self.servers

    def get_server_summary(self) -> Dict[str, Any]:
        """Get summary of MCP servers"""
        connected = sum(1 for s in self.servers if s.get("connected"))
        k8s_servers = [s for s in self.servers if s.get("source") == "kubernetes"]
        local_servers = [s for s in self.servers if s.get("source") == "claude-desktop"]

        return {
            "total": len(self.servers),
            "connected": connected,
            "disconnected": len(self.servers) - connected,
            "k8s_count": len(k8s_servers),
            "local_count": len(local_servers),
            "servers": self.servers,
        }

    def refresh(self):
        """Re-discover MCP servers"""
        self._discover_servers()


class UniFiClient:
    """Client for querying UniFi Cloud API (api.ui.com)"""

    API_BASE = "https://api.ui.com/v1"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.available = False
        self.hosts: List[Dict[str, Any]] = []

        if api_key:
            self._check_availability()

    def _check_availability(self):
        """Check if UniFi Cloud API is accessible"""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{self.API_BASE}/hosts",
                    headers={
                        "X-API-KEY": self.api_key,
                        "Accept": "application/json",
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.hosts = data.get("data", [])
                    self.available = True
                    logger.info(f"UniFi Cloud API connected, {len(self.hosts)} hosts found")
                else:
                    logger.warning(f"UniFi API auth failed: {resp.status_code}")
                    self.available = False
        except Exception as e:
            logger.warning(f"Failed to connect to UniFi API: {e}")
            self.available = False

    def _request(self, endpoint: str) -> Dict[str, Any]:
        """Make authenticated request to UniFi Cloud API"""
        if not self.available:
            return {}

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{self.API_BASE}{endpoint}",
                    headers={
                        "X-API-KEY": self.api_key,
                        "Accept": "application/json",
                    }
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 401:
                    self.available = False
                    logger.warning("UniFi API key expired or invalid")
        except Exception as e:
            logger.debug(f"UniFi request failed: {e}")

        return {}

    def get_hosts(self) -> List[Dict[str, Any]]:
        """Get all UniFi hosts (controllers/consoles)"""
        result = self._request("/hosts")
        return result.get("data", [])

    def get_host_devices(self, host_id: str) -> List[Dict[str, Any]]:
        """Get devices for a specific host"""
        result = self._request(f"/hosts/{host_id}/devices")
        return result.get("data", [])

    def get_sites(self) -> List[Dict[str, Any]]:
        """Get all sites across all hosts"""
        result = self._request("/sites")
        return result.get("data", [])

    def get_site_devices(self, site_id: str) -> List[Dict[str, Any]]:
        """Get devices for a specific site"""
        result = self._request(f"/sites/{site_id}/devices")
        return result.get("data", [])

    def get_site_clients(self, site_id: str) -> List[Dict[str, Any]]:
        """Get clients for a specific site"""
        result = self._request(f"/sites/{site_id}/clients")
        return result.get("data", [])

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary data for dashboard from Cloud API"""
        if not self.available:
            return {
                "available": False,
                "sites": [],
                "total_clients": 0,
            }

        # Get sites - statistics are embedded in site data
        sites_data = self.get_sites()

        # Aggregate data across all sites
        sites_list = []
        total_devices = 0
        total_clients = 0
        wifi_clients = 0
        wired_clients = 0
        guest_clients = 0

        for site in sites_data[:5]:
            meta = site.get("meta", {})
            stats = site.get("statistics", {})
            counts = stats.get("counts", {})
            gateway = stats.get("gateway", {})
            isp_info = stats.get("ispInfo", {})
            percentages = stats.get("percentages", {})
            wans = stats.get("wans", {})

            # Site device counts
            site_devices = counts.get("totalDevice", 0)
            site_offline = counts.get("offlineDevice", 0)
            site_wifi_clients = counts.get("wifiClient", 0)
            site_wired_clients = counts.get("wiredClient", 0)
            site_guest_clients = counts.get("guestClient", 0)

            # Configuration counts
            lan_configs = counts.get("lanConfiguration", 0)
            wifi_configs = counts.get("wifiConfiguration", 0)
            wan_configs = counts.get("wanConfiguration", 0)

            # IPS/Security info
            ips_mode = gateway.get("ipsMode", "off")
            ips_rules = gateway.get("ipsSignature", {}).get("rulesCount", 0)
            inspection = gateway.get("inspectionState", "off")

            # WAN info
            wan_info = []
            for wan_name, wan_data in wans.items():
                wan_info.append({
                    "name": wan_name,
                    "ip": wan_data.get("externalIp", ""),
                    "isp": wan_data.get("ispInfo", {}).get("name", "Unknown"),
                })

            site_summary = {
                "name": meta.get("desc", "Unknown"),
                "site_id": site.get("siteId", ""),
                "timezone": meta.get("timezone", ""),
                # Device counts
                "total_devices": site_devices,
                "online_devices": site_devices - site_offline,
                "offline_devices": site_offline,
                "wifi_devices": counts.get("wifiDevice", 0),
                "wired_devices": counts.get("wiredDevice", 0),
                "gateway_devices": counts.get("gatewayDevice", 0),
                # Client counts
                "wifi_clients": site_wifi_clients,
                "wired_clients": site_wired_clients,
                "guest_clients": site_guest_clients,
                "total_clients": site_wifi_clients + site_wired_clients,
                # Network configuration counts
                "networks": lan_configs,  # LAN configurations = networks
                "wlans": wifi_configs,    # WiFi configurations = WLANs
                "wan_configs": wan_configs,
                # Security/Gateway
                "gateway": gateway.get("shortname", ""),
                "ips_mode": ips_mode,
                "ips_rules": ips_rules,
                "inspection": inspection,
                # ISP info
                "isp_name": isp_info.get("name", "Unknown"),
                "isp_org": isp_info.get("organization", ""),
                # Performance
                "tx_retry_pct": percentages.get("txRetry", 0),
                "wan_uptime_pct": percentages.get("wanUptime", 0),
                # WANs
                "wans": wan_info,
            }

            sites_list.append(site_summary)

            # Aggregate totals
            total_devices += site_devices
            total_clients += site_wifi_clients + site_wired_clients
            wifi_clients += site_wifi_clients
            wired_clients += site_wired_clients
            guest_clients += site_guest_clients

        # Get additional info from hosts
        console_info = None
        lan_ip = None
        for host in self.hosts[:1]:
            reported = host.get("reportedState", {})
            hw = reported.get("hardware", {})
            controllers = reported.get("controllers", [])

            # Find LAN IP (private IP from ipAddrs)
            ip_addrs = reported.get("ipAddrs", [])
            for ip in ip_addrs:
                # Check for private IPv4 addresses
                if ip.startswith("10.") or ip.startswith("192.168.") or \
                   (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31):
                    lan_ip = ip
                    break

            # Active controllers
            active_controllers = []
            for c in controllers:
                if c.get("isInstalled") and c.get("isRunning"):
                    active_controllers.append({
                        "name": c.get("name"),
                        "version": c.get("version"),
                        "state": c.get("state"),
                    })

            console_info = {
                "name": hw.get("name", "Console"),
                "model": hw.get("shortname", ""),
                "firmware": hw.get("firmwareVersion", ""),
                "ip": reported.get("ip", ""),
                "lan_ip": lan_ip,
                "state": reported.get("state", "unknown"),
                "controllers": active_controllers,
            }

        # Add LAN IP to sites
        for site in sites_list:
            site["lan_ip"] = lan_ip

        return {
            "available": True,
            "total_hosts": len(self.hosts),
            "total_sites": len(sites_data),
            "sites": sites_list,
            # Aggregated totals
            "total_devices": total_devices,
            "total_clients": total_clients,
            "wifi_clients": wifi_clients,
            "wired_clients": wired_clients,
            "guest_clients": guest_clients,
            # Console info
            "console": console_info,
        }

    def disconnect(self):
        """Clear API key and mark as unavailable"""
        self.api_key = ""
        self.available = False
        self.hosts = []
