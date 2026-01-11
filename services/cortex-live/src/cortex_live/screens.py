"""Screen definitions for Cortex Live"""

from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, DataTable, Static, Input, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual.reactive import reactive
from datetime import datetime, timezone
from typing import List, Optional
from kubernetes import client
import logging

from .api import KubernetesClient
from .widgets import LoadingIndicator

logger = logging.getLogger(__name__)


class PodsScreen(Screen):
    """Screen showing all pods in a table"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    CSS = """
    PodsScreen {
        background: $surface;
    }

    DataTable {
        height: 1fr;
        margin: 1 2;
    }

    #pods-header {
        dock: top;
        height: 3;
        background: $boost;
        padding: 1 2;
    }
    """

    def __init__(self, k8s_client: KubernetesClient):
        super().__init__()
        self.k8s_client = k8s_client
        self.table: Optional[DataTable] = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("PODS VIEW - All Namespaces", id="pods-header-label"),
            id="pods-header"
        )
        yield DataTable()
        yield Footer()

    def on_mount(self):
        """Initialize the pods table"""
        self.table = self.query_one(DataTable)
        self.table.cursor_type = "row"
        self.table.zebra_stripes = True

        # Add columns
        self.table.add_column("Namespace", width=20)
        self.table.add_column("Name", width=40)
        self.table.add_column("Status", width=12)
        self.table.add_column("Restarts", width=10)
        self.table.add_column("Age", width=12)
        self.table.add_column("Node", width=20)

        # Load data
        self.refresh_pods()

        # Set up auto-refresh
        self.set_interval(2, self.refresh_pods)

    def refresh_pods(self):
        """Refresh pods data"""
        try:
            if not self.table:
                return

            pods = self.k8s_client.get_pods()

            # Clear existing rows
            self.table.clear()

            # Add rows
            for pod in sorted(pods, key=lambda p: (p.metadata.namespace, p.metadata.name)):
                namespace = pod.metadata.namespace
                name = pod.metadata.name
                status = pod.status.phase if pod.status else "Unknown"

                # Get restart count
                restarts = 0
                if pod.status and pod.status.container_statuses:
                    restarts = sum(c.restart_count for c in pod.status.container_statuses)

                # Calculate age
                age = "Unknown"
                if pod.metadata.creation_timestamp:
                    delta = datetime.now(timezone.utc) - pod.metadata.creation_timestamp
                    if delta.days > 0:
                        age = f"{delta.days}d"
                    elif delta.seconds > 3600:
                        age = f"{delta.seconds // 3600}h"
                    elif delta.seconds > 60:
                        age = f"{delta.seconds // 60}m"
                    else:
                        age = f"{delta.seconds}s"

                node = pod.spec.node_name if pod.spec else "N/A"

                self.table.add_row(
                    namespace,
                    name,
                    status,
                    str(restarts),
                    age,
                    node or "N/A"
                )

        except Exception as e:
            logger.error(f"Failed to refresh pods: {e}")


class NodesScreen(Screen):
    """Screen showing detailed node information"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    CSS = """
    NodesScreen {
        background: $surface;
    }

    DataTable {
        height: 1fr;
        margin: 1 2;
    }

    #nodes-header {
        dock: top;
        height: 3;
        background: $boost;
        padding: 1 2;
    }
    """

    def __init__(self, k8s_client: KubernetesClient, prom_client):
        super().__init__()
        self.k8s_client = k8s_client
        self.prom_client = prom_client
        self.table: Optional[DataTable] = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("NODES VIEW - Cluster Nodes", id="nodes-header-label"),
            id="nodes-header"
        )
        yield DataTable()
        yield Footer()

    def on_mount(self):
        """Initialize the nodes table"""
        self.table = self.query_one(DataTable)
        self.table.cursor_type = "row"
        self.table.zebra_stripes = True

        # Add columns
        self.table.add_column("Name", width=20)
        self.table.add_column("Status", width=12)
        self.table.add_column("Roles", width=15)
        self.table.add_column("CPU", width=10)
        self.table.add_column("Memory", width=10)
        self.table.add_column("Pods", width=10)
        self.table.add_column("Age", width=12)

        # Load data
        self.refresh_nodes()

        # Set up auto-refresh
        self.set_interval(2, self.refresh_nodes)

    def refresh_nodes(self):
        """Refresh nodes data"""
        try:
            if not self.table:
                return

            nodes = self.k8s_client.get_nodes()
            pods = self.k8s_client.get_pods()

            # Clear existing rows
            self.table.clear()

            # Add rows
            for node in nodes:
                name = node.metadata.name

                # Status
                status = "Unknown"
                if node.status and node.status.conditions:
                    for condition in node.status.conditions:
                        if condition.type == "Ready":
                            status = "Ready" if condition.status == "True" else "NotReady"
                            break

                # Roles
                roles = []
                if node.metadata.labels:
                    for key, value in node.metadata.labels.items():
                        if "node-role.kubernetes.io/" in key:
                            role = key.split("/")[1]
                            roles.append(role)
                roles_str = ",".join(roles) if roles else "worker"

                # Get metrics from Prometheus
                metrics = self.prom_client.get_node_metrics(name)
                cpu = f"{metrics['cpu']}%"
                mem = f"{metrics['mem']}%"

                # Count pods on this node
                pod_count = sum(1 for p in pods if p.spec and p.spec.node_name == name)

                # Calculate age
                age = "Unknown"
                if node.metadata.creation_timestamp:
                    delta = datetime.now(timezone.utc) - node.metadata.creation_timestamp
                    if delta.days > 0:
                        age = f"{delta.days}d"
                    else:
                        age = f"{delta.seconds // 3600}h"

                self.table.add_row(
                    name,
                    status,
                    roles_str,
                    cpu,
                    mem,
                    str(pod_count),
                    age
                )

        except Exception as e:
            logger.error(f"Failed to refresh nodes: {e}")


class AgentsScreen(Screen):
    """Screen showing all Kubernetes Jobs (agents)"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
        Binding("a", "filter_active", "Active"),
        Binding("c", "filter_completed", "Completed"),
        Binding("f", "filter_failed", "Failed"),
        Binding("x", "filter_all", "All"),
    ]

    CSS = """
    AgentsScreen {
        background: $surface;
    }

    DataTable {
        height: 1fr;
        margin: 1 2;
    }

    #agents-header {
        dock: top;
        height: 3;
        background: $boost;
        padding: 1 2;
    }
    """

    def __init__(self, k8s_client: KubernetesClient):
        super().__init__()
        self.k8s_client = k8s_client
        self.table: Optional[DataTable] = None
        self.filter = "all"  # all, active, completed, failed

    def compose(self) -> ComposeResult:
        yield Container(
            Label("AGENTS VIEW - Kubernetes Jobs (Filter: All)", id="agents-header-label"),
            id="agents-header"
        )
        yield DataTable()
        yield Footer()

    def on_mount(self):
        """Initialize the agents table"""
        self.table = self.query_one(DataTable)
        self.table.cursor_type = "row"
        self.table.zebra_stripes = True

        # Add columns
        self.table.add_column("Namespace", width=20)
        self.table.add_column("Name", width=40)
        self.table.add_column("Status", width=15)
        self.table.add_column("Completions", width=15)
        self.table.add_column("Duration", width=12)

        # Load data
        self.refresh_agents()

        # Set up auto-refresh
        self.set_interval(2, self.refresh_agents)

    def refresh_agents(self):
        """Refresh agents data"""
        try:
            if not self.table:
                return

            jobs = self.k8s_client.get_jobs()

            # Clear existing rows
            self.table.clear()

            # Filter and add rows
            for job in sorted(jobs, key=lambda j: (j.metadata.namespace, j.metadata.name)):
                namespace = job.metadata.namespace
                name = job.metadata.name

                # Determine status
                status = "Unknown"
                if job.status:
                    if job.status.active and job.status.active > 0:
                        status = "Active"
                    elif job.status.succeeded and job.status.succeeded > 0:
                        status = "Completed"
                    elif job.status.failed and job.status.failed > 0:
                        status = "Failed"

                # Apply filter
                if self.filter != "all":
                    if self.filter == "active" and status != "Active":
                        continue
                    elif self.filter == "completed" and status != "Completed":
                        continue
                    elif self.filter == "failed" and status != "Failed":
                        continue

                # Completions
                completions = "0/0"
                if job.status:
                    succeeded = job.status.succeeded or 0
                    total = job.spec.completions or 1
                    completions = f"{succeeded}/{total}"

                # Duration
                duration = "N/A"
                if job.status and job.status.start_time:
                    end_time = job.status.completion_time or datetime.now(timezone.utc)
                    delta = end_time - job.status.start_time
                    if delta.seconds > 3600:
                        duration = f"{delta.seconds // 3600}h"
                    elif delta.seconds > 60:
                        duration = f"{delta.seconds // 60}m"
                    else:
                        duration = f"{delta.seconds}s"

                self.table.add_row(
                    namespace,
                    name,
                    status,
                    completions,
                    duration
                )

        except Exception as e:
            logger.error(f"Failed to refresh agents: {e}")

    def action_filter_active(self):
        """Filter to show only active jobs"""
        self.filter = "active"
        self._update_header()
        self.refresh_agents()

    def action_filter_completed(self):
        """Filter to show only completed jobs"""
        self.filter = "completed"
        self._update_header()
        self.refresh_agents()

    def action_filter_failed(self):
        """Filter to show only failed jobs"""
        self.filter = "failed"
        self._update_header()
        self.refresh_agents()

    def action_filter_all(self):
        """Show all jobs"""
        self.filter = "all"
        self._update_header()
        self.refresh_agents()

    def _update_header(self):
        """Update header to show current filter"""
        header = self.query_one("#agents-header-label", Label)
        header.update(f"AGENTS VIEW - Kubernetes Jobs (Filter: {self.filter.capitalize()})")


class LogsScreen(Screen):
    """Screen showing pod logs"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    CSS = """
    LogsScreen {
        background: $surface;
    }

    #logs-container {
        height: 1fr;
        margin: 1 2;
    }

    #pod-selector {
        height: auto;
        margin-bottom: 1;
    }

    DataTable {
        height: 15;
    }

    #logs-content {
        height: 1fr;
        border: solid $boost;
        padding: 1;
        overflow-y: scroll;
    }

    #logs-header {
        dock: top;
        height: 3;
        background: $boost;
        padding: 1 2;
    }
    """

    def __init__(self, k8s_client: KubernetesClient):
        super().__init__()
        self.k8s_client = k8s_client
        self.table: Optional[DataTable] = None
        self.logs_display: Optional[Static] = None
        self.selected_pod: Optional[client.V1Pod] = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("LOGS VIEW - Select a Pod", id="logs-header-label"),
            id="logs-header"
        )
        with Vertical(id="logs-container"):
            with Container(id="pod-selector"):
                yield DataTable()
            yield Static("", id="logs-content")
        yield Footer()

    def on_mount(self):
        """Initialize the logs view"""
        self.table = self.query_one(DataTable)
        self.logs_display = self.query_one("#logs-content", Static)

        self.table.cursor_type = "row"
        self.table.zebra_stripes = True

        # Add columns
        self.table.add_column("Namespace", width=20)
        self.table.add_column("Pod Name", width=50)
        self.table.add_column("Status", width=12)

        # Load pods
        self.refresh_pod_list()

    def refresh_pod_list(self):
        """Refresh the list of pods"""
        try:
            if not self.table:
                return

            pods = self.k8s_client.get_pods()

            # Clear existing rows
            self.table.clear()

            # Add rows
            for pod in sorted(pods, key=lambda p: (p.metadata.namespace, p.metadata.name)):
                status = pod.status.phase if pod.status else "Unknown"
                self.table.add_row(
                    pod.metadata.namespace,
                    pod.metadata.name,
                    status,
                    key=f"{pod.metadata.namespace}/{pod.metadata.name}"
                )

        except Exception as e:
            logger.error(f"Failed to refresh pod list: {e}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle pod selection"""
        try:
            # Get the selected row key (namespace/name)
            row_key = event.row_key.value
            namespace, name = row_key.split("/")

            # Find the pod
            pods = self.k8s_client.get_pods(namespace=namespace)
            selected_pod = next((p for p in pods if p.metadata.name == name), None)

            if selected_pod:
                self.selected_pod = selected_pod
                self._load_logs()

        except Exception as e:
            logger.error(f"Failed to handle pod selection: {e}")

    def _load_logs(self):
        """Load logs for the selected pod"""
        if not self.selected_pod or not self.logs_display:
            return

        try:
            namespace = self.selected_pod.metadata.namespace
            name = self.selected_pod.metadata.name

            # Update header
            header = self.query_one("#logs-header-label", Label)
            header.update(f"LOGS VIEW - {namespace}/{name}")

            # Get containers
            containers = self.k8s_client.get_pod_containers(self.selected_pod)
            container = containers[0] if containers else None

            # Get logs
            logs = self.k8s_client.get_pod_logs(
                name=name,
                namespace=namespace,
                container=container,
                tail_lines=100
            )

            self.logs_display.update(logs)

            # Set up auto-refresh
            if hasattr(self, '_log_refresh_timer'):
                self._log_refresh_timer.stop()
            self._log_refresh_timer = self.set_interval(2, self._refresh_logs)

        except Exception as e:
            logger.error(f"Failed to load logs: {e}")
            if self.logs_display:
                self.logs_display.update(f"Error loading logs: {e}")

    def _refresh_logs(self):
        """Refresh logs for the selected pod"""
        if self.selected_pod:
            self._load_logs()


class SearchScreen(Screen):
    """Screen for searching across resources"""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    CSS = """
    SearchScreen {
        background: $surface;
    }

    #search-container {
        height: 1fr;
        margin: 1 2;
    }

    #search-input-container {
        height: auto;
        margin-bottom: 1;
    }

    Input {
        margin: 1 0;
    }

    DataTable {
        height: 1fr;
    }

    #search-header {
        dock: top;
        height: 3;
        background: $boost;
        padding: 1 2;
    }
    """

    def __init__(self, k8s_client: KubernetesClient):
        super().__init__()
        self.k8s_client = k8s_client
        self.table: Optional[DataTable] = None
        self.search_input: Optional[Input] = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("SEARCH - Enter search term and press Enter", id="search-header-label"),
            id="search-header"
        )
        with Vertical(id="search-container"):
            with Container(id="search-input-container"):
                yield Input(placeholder="Search pods, nodes, namespaces, events...")
            yield DataTable()
        yield Footer()

    def on_mount(self):
        """Initialize the search view"""
        self.search_input = self.query_one(Input)
        self.table = self.query_one(DataTable)

        self.table.cursor_type = "row"
        self.table.zebra_stripes = True

        # Add columns
        self.table.add_column("Type", width=15)
        self.table.add_column("Namespace", width=20)
        self.table.add_column("Name", width=50)
        self.table.add_column("Status", width=15)

        # Focus input
        self.search_input.focus()

    def on_input_submitted(self, event: Input.Submitted):
        """Handle search submission"""
        query = event.value.lower().strip()
        if not query:
            return

        self.perform_search(query)

    def perform_search(self, query: str):
        """Perform search across resources"""
        try:
            if not self.table:
                return

            # Clear existing rows
            self.table.clear()

            # Search pods
            pods = self.k8s_client.get_pods()
            for pod in pods:
                if (query in pod.metadata.name.lower() or
                    query in pod.metadata.namespace.lower()):
                    status = pod.status.phase if pod.status else "Unknown"
                    self.table.add_row(
                        "Pod",
                        pod.metadata.namespace,
                        pod.metadata.name,
                        status
                    )

            # Search nodes
            nodes = self.k8s_client.get_nodes()
            for node in nodes:
                if query in node.metadata.name.lower():
                    status = "Unknown"
                    if node.status and node.status.conditions:
                        for condition in node.status.conditions:
                            if condition.type == "Ready":
                                status = "Ready" if condition.status == "True" else "NotReady"
                                break
                    self.table.add_row(
                        "Node",
                        "-",
                        node.metadata.name,
                        status
                    )

            # Search events
            events = self.k8s_client.get_events()
            for event in events[:20]:  # Limit to 20 events
                if (query in event.involved_object.name.lower() or
                    query in event.involved_object.namespace.lower()):
                    self.table.add_row(
                        "Event",
                        event.involved_object.namespace,
                        event.involved_object.name,
                        event.reason or "N/A"
                    )

        except Exception as e:
            logger.error(f"Search failed: {e}")
