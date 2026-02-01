"""c-top - Cortex Operations Dashboard

htop-style monitoring for the Cortex platform.
Uses Textual's theming system for full theme support.
Uses content markup with $variable syntax for dynamic theme colors.
"""

import logging
import os
from datetime import datetime
from typing import Optional
from collections import deque

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static, Footer
from textual.binding import Binding
from textual.reactive import reactive

from .layers import (
    ClusterLayer,
    NetworkLayer,
    WorkersLayer,
    FabricLayer,
    ActivityStream,
)
from .clients import (
    KubernetesClient,
    PrometheusClient,
    RedisClient,
    TailscaleClient,
    MCPClient,
    UniFiClient,
)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StatusBar(Static):
    """Top status bar with layer tabs - uses content markup for theme colors"""

    current_layer = reactive(1)
    cluster_name = reactive("cortex")
    api_latency = reactive(0)
    connected = reactive(False)

    def render(self) -> str:
        """Render using markup strings with $variable syntax for theme colors"""
        parts = []

        # Logo
        parts.append("[bold $primary] ⬢ C-TOP[/]  ")

        # Layer tabs
        layers = [
            (1, "cluster"),
            (2, "network"),
            (3, "workers"),
            (4, "fabric"),
        ]

        for num, name in layers:
            if num == self.current_layer:
                # Need to escape the [ for the tab display
                parts.append(f"[bold $primary reverse]\\[{num}:{name}][/]")
            else:
                parts.append(f"[$text-muted] {num}:{name} [/]")

        # Spacer
        parts.append(" " * 20)

        # Connection status
        if self.connected:
            parts.append("[bold $success]● [/]")
        else:
            parts.append("[$text-muted]○ [/]")

        # API latency
        if self.api_latency > 0:
            if self.api_latency < 100:
                latency_style = "$primary"
            elif self.api_latency < 500:
                latency_style = "$warning"
            else:
                latency_style = "$error"
            parts.append(f"[{latency_style}]⚡{self.api_latency}ms[/]")
        else:
            parts.append("[$text-muted]⚡--ms[/]")

        parts.append("  ")

        # Cluster name
        parts.append(f"[bold $primary]cluster:{self.cluster_name}[/]")

        # Timestamp
        now = datetime.now().strftime("%H:%M:%S")
        parts.append(f"[$text-muted]  {now}[/]")

        return "".join(parts)


class CTop(App):
    """c-top - Cortex Operations Dashboard"""

    # Use Textual's CSS variables for theming
    CSS = """
    Screen {
        background: $background;
    }

    StatusBar {
        dock: top;
        height: 1;
        background: $surface;
        color: $text;
    }

    #layer-container {
        height: 1fr;
        margin: 1 1;
    }

    ClusterLayer, NetworkLayer, WorkersLayer, FabricLayer {
        height: auto;
        background: $background;
        color: $text;
    }

    ActivityStream {
        dock: bottom;
        height: 6;
        background: $background;
        color: $text;
        margin: 0 1;
    }

    Footer {
        background: $surface;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "quit", show=True),
        Binding("1", "layer_1", "cluster", show=True),
        Binding("2", "layer_2", "network", show=True),
        Binding("3", "layer_3", "workers", show=True),
        Binding("4", "layer_4", "fabric", show=True),
        Binding("r", "refresh", "refresh", show=True),
    ]

    # Enable command palette features
    ENABLE_COMMAND_PALETTE = True

    current_layer = reactive(1)

    def __init__(self):
        super().__init__()
        self.k8s: Optional[KubernetesClient] = None
        self.prom: Optional[PrometheusClient] = None
        self.redis: Optional[RedisClient] = None
        self.tailscale: Optional[TailscaleClient] = None
        self.mcp: Optional[MCPClient] = None
        self.unifi: Optional[UniFiClient] = None

        # History for sparklines
        self.cpu_history = deque(maxlen=10)
        self.mem_history = deque(maxlen=10)

        # Activity events
        self.activity_events = deque(maxlen=50)

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Container(id="layer-container"):
            yield ClusterLayer(id="layer-1")
            yield NetworkLayer(id="layer-2")
            yield WorkersLayer(id="layer-3")
            yield FabricLayer(id="layer-4")
        yield ActivityStream()
        yield Footer()

    def on_mount(self):
        """Initialize clients and start updates"""
        # Show only the default layer
        self._show_layer(1)

        # Initialize clients with staggered loading
        self.call_later(self._init_phase_1)

    def _init_phase_1(self):
        """Phase 1: Essential clients (fast)"""
        try:
            self.k8s = KubernetesClient()
            self.query_one(StatusBar).connected = True
            self.add_activity("c-top", "connected", "kubernetes API ready")
            logger.info("Kubernetes client initialized")
        except Exception as e:
            logger.error(f"Failed to init K8s: {e}")
            self.add_activity("c-top", "error", f"k8s connection failed: {e}")

        # Start fast refresh for visible layer
        self.set_interval(1, self._update_current_layer)

        # Schedule phase 2
        self.call_later(self._init_phase_2)

    def _init_phase_2(self):
        """Phase 2: Extended clients (parallel)"""
        try:
            self.prom = PrometheusClient()
            if self.prom.prom:
                self.add_activity("c-top", "connected", "prometheus metrics ready")
        except Exception as e:
            logger.warning(f"Prometheus init failed: {e}")

        try:
            self.redis = RedisClient()
            if self.redis.client:
                self.add_activity("c-top", "connected", "redis agent registry ready")
        except Exception as e:
            logger.warning(f"Redis init failed: {e}")

        # Initialize Tailscale client
        try:
            self.tailscale = TailscaleClient()
            if self.tailscale.available:
                self.add_activity("c-top", "connected", "tailscale mesh ready")
        except Exception as e:
            logger.warning(f"Tailscale init failed: {e}")

        # Initialize MCP client (discovers from Claude config + K8s)
        try:
            self.mcp = MCPClient(k8s_client=self.k8s)
            server_count = len(self.mcp.servers)
            if server_count > 0:
                self.add_activity("c-top", "discovered", f"{server_count} MCP servers found")
        except Exception as e:
            logger.warning(f"MCP discovery failed: {e}")

        # Initialize UniFi client (optional - requires API key)
        # Set UNIFI_API_KEY environment variable to enable UniFi monitoring
        # Get your API key from: https://unifi.ui.com → Settings → API
        unifi_api_key = os.environ.get("UNIFI_API_KEY", "")
        if unifi_api_key:
            try:
                self.unifi = UniFiClient(api_key=unifi_api_key)
                if self.unifi.available:
                    self.add_activity("c-top", "connected", "unifi cloud api ready")
            except Exception as e:
                logger.warning(f"UniFi init failed: {e}")

        # Start slower refresh for background data
        self.set_interval(2, self._update_background)

    def _show_layer(self, layer_num: int):
        """Show only the specified layer"""
        for i in range(1, 5):
            widget = self.query_one(f"#layer-{i}")
            widget.display = (i == layer_num)

        self.query_one(StatusBar).current_layer = layer_num
        self.current_layer = layer_num

    def _update_current_layer(self):
        """Update the currently visible layer (fast refresh)"""
        try:
            if self.current_layer == 1:
                self._update_cluster_layer()
            elif self.current_layer == 2:
                self._update_network_layer()
            elif self.current_layer == 3:
                self._update_workers_layer()
            elif self.current_layer == 4:
                self._update_fabric_layer()

            # Always update activity stream
            self._update_activity_stream()

            # Update API latency
            if self.prom:
                latency = self.prom.get_api_latency()
                self.query_one(StatusBar).api_latency = latency

        except Exception as e:
            logger.error(f"Update error: {e}")

    def _update_background(self):
        """Update background data for non-visible layers"""
        # Pre-fetch data for quick layer switching
        pass

    def _update_cluster_layer(self):
        """Update cluster layer data"""
        if not self.k8s:
            return

        layer = self.query_one("#layer-1", ClusterLayer)

        # Get metrics
        cpu = self.prom.get_cluster_cpu() if self.prom else 0
        mem = self.prom.get_cluster_memory() if self.prom else 0
        disk = self.prom.get_cluster_disk() if self.prom else 0
        network = self.prom.get_network_io() if self.prom else {"in": 0, "out": 0}

        # Update history
        self.cpu_history.append(cpu)
        self.mem_history.append(mem)

        # Get pod/job counts
        pods = self.k8s.get_pods()
        ready = sum(1 for p in pods if p.status.phase == "Running")
        jobs = self.k8s.get_jobs()
        active_jobs = sum(1 for j in jobs if j.status.active and j.status.active > 0)

        layer.metrics = {
            "cpu": cpu,
            "mem": mem,
            "disk": disk,
            "network_in": network["in"],
            "network_out": network["out"],
            "pods_ready": ready,
            "pods_total": len(pods),
            "jobs_active": active_jobs,
        }

        layer.history = {
            "cpu": self.cpu_history,
            "mem": self.mem_history,
        }

        # Get services
        services = self.k8s.get_services("cortex-system")
        layer.services = services

        # Get nodes
        nodes = self.k8s.get_nodes()
        node_data = {}
        for node in nodes[:4]:
            name = node.metadata.name
            if self.prom:
                metrics = self.prom.get_node_metrics(name)
                node_data[name] = metrics
        layer.nodes = node_data

    def _update_network_layer(self):
        """Update network layer data"""
        layer = self.query_one("#layer-2", NetworkLayer)

        # Get Tailscale mesh data
        if self.tailscale and self.tailscale.available:
            mesh_data = self.tailscale.get_mesh_summary()
            peers_for_display = []
            for p in mesh_data.get("peers", [])[:6]:  # Limit to 6 peers
                peers_for_display.append({
                    "name": p.get("name", "unknown"),
                    "online": p.get("online", False),
                    "latency": 0,  # Would need to ping for actual latency
                    "connection_type": p.get("connection_type", "unknown"),
                })
            layer.mesh = {
                "peers": peers_for_display,
                "status": "connected" if mesh_data.get("connected") else "disconnected",
                "total_peers": mesh_data.get("total_peers", 0),
                "online_peers": mesh_data.get("online_peers", 0),
            }
        else:
            layer.mesh = {
                "peers": [],
                "status": "unavailable",
            }

        # Get UniFi data (if configured)
        if self.unifi and self.unifi.available:
            unifi_data = self.unifi.get_dashboard_summary()
            layer.unifi = {
                "available": True,
                "sites": unifi_data.get("sites", []),
                "total_clients": unifi_data.get("total_clients", 0),
                "wifi_clients": unifi_data.get("wifi_clients", 0),
                "wired_clients": unifi_data.get("wired_clients", 0),
                "total_devices": unifi_data.get("total_devices", 0),
                "console": unifi_data.get("console"),
            }
        else:
            layer.unifi = {"available": False}

    def _update_workers_layer(self):
        """Update workers layer data"""
        layer = self.query_one("#layer-3", WorkersLayer)

        workers = []
        stats = {"active": 0, "idle": 0, "completed_hr": 0, "avg_time": 0}

        if self.redis and self.redis.client:
            # Get agents from Redis registry
            agents = self.redis.get_agents()
            for agent in agents:
                workers.append({
                    "id": agent.get("agent_id", "")[:6],
                    "status": agent.get("status", "unknown"),
                    "agent_type": agent.get("agent_type", "worker"),
                    "current_task": agent.get("current_task", "-"),
                    "cpu": 0,  # Would need metrics for this
                    "mem": "0M",
                    "time": "00:00",
                })

            worker_stats = self.redis.get_worker_stats()
            stats.update(worker_stats)

        # If no Redis data, fall back to K8s jobs
        if not workers and self.k8s:
            jobs = self.k8s.get_jobs()
            for job in jobs[:12]:
                status = "busy"
                if job.status.succeeded and job.status.succeeded > 0:
                    status = "completed"
                elif job.status.failed and job.status.failed > 0:
                    status = "failed"
                elif not job.status.active or job.status.active == 0:
                    status = "idle"

                workers.append({
                    "id": job.metadata.name[:6],
                    "status": status,
                    "agent_type": job.metadata.labels.get("app", "job")[:20] if job.metadata.labels else "job",
                    "current_task": job.metadata.namespace,
                    "cpu": 0,
                    "mem": "0M",
                    "time": "00:00",
                })

            # Calculate stats from jobs
            stats["active"] = sum(1 for j in jobs if j.status.active and j.status.active > 0)
            stats["idle"] = sum(1 for j in jobs if not j.status.active or j.status.active == 0)

        layer.worker_list = workers
        layer.stats = stats
        layer.queue_depth = {"high": 0, "normal": 0, "low": 0}

    def _update_fabric_layer(self):
        """Update fabric layer data"""
        layer = self.query_one("#layer-4", FabricLayer)

        # Get MCP servers from discovery
        if self.mcp:
            layer.mcp_servers = self.mcp.get_servers()
        else:
            layer.mcp_servers = []

        # Tool invocations would come from Prometheus metrics if available
        layer.tool_invocations = []
        if self.prom and self.prom.prom:
            try:
                # Query for MCP tool invocations if metrics exist
                query = 'topk(5, sum by (tool) (rate(mcp_tool_invocations_total[5m])))'
                result = self.prom.prom.custom_query(query)
                for r in result:
                    tool_name = r.get("metric", {}).get("tool", "unknown")
                    count = int(float(r.get("value", [0, 0])[1]) * 300)  # 5min count
                    layer.tool_invocations.append({"name": tool_name, "count": count})
            except Exception:
                pass

        layer.qdrant = {
            "collections": [
                {"name": "routing_patterns", "vectors": 0, "dimensions": 384, "p99_ms": 0},
                {"name": "conversations", "vectors": 0, "dimensions": 384, "p99_ms": 0},
                {"name": "tool_patterns", "vectors": 0, "dimensions": 384, "p99_ms": 0},
            ],
            "memory": "0GB",
        }

        layer.routing = {
            "cache_hit": 0,
            "similarity": 0,
            "escalate": 0,
        }

    def _update_activity_stream(self):
        """Update the activity stream"""
        stream = self.query_one(ActivityStream)
        stream.events = list(self.activity_events)
        stream.rate = len(self.activity_events)

    def add_activity(self, source: str, action: str, detail: str):
        """Add an activity event to the stream"""
        now = datetime.now().strftime("%H:%M:%S")
        self.activity_events.appendleft({
            "timestamp": now,
            "source": source,
            "action": action,
            "detail": detail,
        })

    # Layer switching actions
    def action_layer_1(self):
        self._show_layer(1)
        self.add_activity("c-top", "layer:switch", "viewing cluster layer")

    def action_layer_2(self):
        self._show_layer(2)
        self.add_activity("c-top", "layer:switch", "viewing network layer")

    def action_layer_3(self):
        self._show_layer(3)
        self.add_activity("c-top", "layer:switch", "viewing workers layer")

    def action_layer_4(self):
        self._show_layer(4)
        self.add_activity("c-top", "layer:switch", "viewing fabric layer")

    def action_refresh(self):
        """Force refresh current layer"""
        self._update_current_layer()
        self.add_activity("c-top", "refresh", "manual refresh triggered")


def main():
    """Main entry point"""
    app = CTop()
    app.run()


if __name__ == "__main__":
    main()
