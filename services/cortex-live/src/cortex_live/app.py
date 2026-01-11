"""Main application for Cortex Live"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer
from textual.binding import Binding

from .widgets import (
    StatusBar,
    ClusterPulse,
    LiveEvents,
    AgentsPanel,
    NodesPanel
)
from .screens import (
    PodsScreen,
    NodesScreen,
    AgentsScreen,
    LogsScreen,
    SearchScreen
)
from .api import KubernetesClient, PrometheusClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CortexLive(App):
    """Cortex Live - Real-time k3s cluster monitoring"""

    CSS = """
    Screen {
        background: $surface;
    }

    StatusBar {
        dock: top;
        height: 1;
        background: $boost;
        color: $text;
    }

    ClusterPulse {
        height: 5;
        margin: 1 0;
    }

    LiveEvents {
        height: 9;
        margin: 1 0;
    }

    #bottom-row {
        layout: horizontal;
        height: 9;
        margin: 1 0;
    }

    AgentsPanel {
        width: 33;
        margin-right: 1;
    }

    NodesPanel {
        width: 1fr;
    }

    Footer {
        background: $boost;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "quit", show=True),
        Binding("p", "pods", "pods", show=True),
        Binding("n", "nodes", "nodes", show=True),
        Binding("a", "agents", "agents", show=True),
        Binding("l", "logs", "logs", show=True),
        Binding("/", "search", "search", show=True),
        Binding("r", "refresh", "refresh", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.k8s_client: Optional[KubernetesClient] = None
        self.prom_client: Optional[PrometheusClient] = None

    def compose(self) -> ComposeResult:
        yield StatusBar()
        yield ClusterPulse()
        yield LiveEvents()
        with Container(id="bottom-row"):
            yield AgentsPanel()
            yield NodesPanel()
        yield Footer()

    def on_mount(self):
        """Initialize clients and start updates"""
        try:
            # Initialize Kubernetes client
            self.k8s_client = KubernetesClient()
            logger.info("Kubernetes client initialized")

            # Initialize Prometheus client
            self.prom_client = PrometheusClient()
            logger.info("Prometheus client initialized")

            # Do initial update immediately
            self.call_later(self.update_all)

            # Then set up interval updates
            self.set_interval(2, self.update_all)

        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            self.notify(f"Initialization error: {e}", severity="error")

    def update_all(self):
        """Main update method called every 2 seconds"""
        try:
            if not self.k8s_client or not self.prom_client:
                return

            # Update status bar
            nodes = self.k8s_client.get_nodes()
            self.query_one(StatusBar).node_count = len(nodes)

            # Update cluster pulse with Prometheus metrics
            pods = self.k8s_client.get_pods()
            ready = sum(1 for p in pods if p.status.phase == "Running")
            total = len(pods)

            events = self.k8s_client.get_events()
            recent = [e for e in events if e.last_timestamp]
            events_per_min = len([e for e in recent[:60]]) if len(recent) > 0 else 0

            # Get real CPU and memory from Prometheus
            cpu = self.prom_client.get_cluster_cpu()
            mem = self.prom_client.get_cluster_memory()

            self.query_one(ClusterPulse).metrics = {
                "cpu": cpu,
                "mem": mem,
                "pods_ready": ready,
                "pods_total": total,
                "events_per_min": events_per_min
            }

            # Update live events
            event_lines = []
            for event in events[-5:]:
                ts = datetime.now().strftime("%H:%M:%S")
                icon = "●" if "Running" in str(event.reason) else "!"
                obj = event.involved_object.name[:22]
                reason = str(event.reason)[:15]
                event_lines.append(f"{ts} │ {icon} {obj:<22} │ {reason:<15}")

            self.query_one(LiveEvents).events = event_lines

            # Update agents
            jobs = self.k8s_client.get_jobs()
            active = sum(1 for j in jobs if j.status.active and j.status.active > 0)
            completed = sum(1 for j in jobs if j.status.succeeded and j.status.succeeded > 0)
            failed = sum(1 for j in jobs if j.status.failed and j.status.failed > 0)
            total_jobs = len(jobs)
            success = int((completed / total_jobs * 100)) if total_jobs > 0 else 0

            self.query_one(AgentsPanel).stats = {
                "active": active,
                "spawning": 0,
                "completed": completed,
                "failed": failed,
                "total": total_jobs,
                "success": success
            }

            # Update nodes with Prometheus metrics
            node_data = {}
            for node in nodes[:4]:
                name = node.metadata.name.replace("k3s-", "")[:10]
                metrics = self.prom_client.get_node_metrics(node.metadata.name)
                node_data[name] = metrics

            self.query_one(NodesPanel).nodes = node_data

        except Exception as e:
            logger.error(f"Update error: {e}")
            self.notify(f"Update error: {str(e)[:50]}", severity="error")

    def action_pods(self) -> None:
        """Show pods view"""
        if self.k8s_client:
            self.push_screen(PodsScreen(self.k8s_client))
        else:
            self.notify("Kubernetes client not initialized", severity="error")

    def action_nodes(self) -> None:
        """Show nodes view"""
        if self.k8s_client and self.prom_client:
            self.push_screen(NodesScreen(self.k8s_client, self.prom_client))
        else:
            self.notify("Clients not initialized", severity="error")

    def action_agents(self) -> None:
        """Show agents view"""
        if self.k8s_client:
            self.push_screen(AgentsScreen(self.k8s_client))
        else:
            self.notify("Kubernetes client not initialized", severity="error")

    def action_logs(self) -> None:
        """Show logs view"""
        if self.k8s_client:
            self.push_screen(LogsScreen(self.k8s_client))
        else:
            self.notify("Kubernetes client not initialized", severity="error")

    def action_search(self) -> None:
        """Show search view"""
        if self.k8s_client:
            self.push_screen(SearchScreen(self.k8s_client))
        else:
            self.notify("Kubernetes client not initialized", severity="error")

    def action_refresh(self) -> None:
        """Force refresh all data"""
        self.notify("Refreshing...")
        self.update_all()


def main():
    """Main entry point"""
    app = CortexLive()
    app.run()


if __name__ == "__main__":
    main()
