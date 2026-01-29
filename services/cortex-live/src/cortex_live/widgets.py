"""Custom widgets for Cortex Live"""

from textual.widgets import Static
from textual.reactive import reactive
from typing import Dict, List
from rich.text import Text
from rich.console import Console


class StatusBar(Static):
    """Top status bar"""
    node_count = reactive(0)
    api_latency = reactive(0)

    def render(self) -> Text:
        text = Text()
        text.append("⬢ ", style="bold cyan")
        text.append("CORTEX", style="bold cyan")
        text.append(" LIVE", style="bold white")
        text.append(" " * 35)

        # API latency indicator
        latency = self.api_latency
        if latency > 0:
            latency_color = "bold green" if latency < 100 else "bold yellow" if latency < 500 else "bold red"
            text.append("⚡ ", style="bold yellow")
            text.append(f"{latency}ms", style=latency_color)
            text.append(" │ ", style="dim white")

        text.append("▲ ", style="bold cyan")
        text.append(f"{self.node_count} nodes", style="white")
        text.append(" │ ", style="dim white")
        text.append("k3s", style="bold magenta")
        return text


class ClusterPulse(Static):
    """Cluster pulse metrics"""
    metrics = reactive({"cpu": 68, "mem": 41, "pods_ready": 0, "pods_total": 0, "events_per_min": 12, "network_in": 0, "network_out": 0})

    BORDER_WIDTH = 64  # Fixed border width

    def render(self) -> Text:
        m = self.metrics
        text = Text()

        # Top border
        text.append("┏", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┓\n", style="bold cyan")

        # Title
        line = " ◉ CLUSTER PULSE"
        text.append("┃", style="bold cyan")
        text.append(line, style="bold white")
        text.append(" " * (self.BORDER_WIDTH - len(line)), style="")
        text.append("┃\n", style="bold cyan")

        # Separator
        text.append("┣", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="cyan")
        text.append("┫\n", style="bold cyan")

        # CPU bar line
        cpu_pct = m.get('cpu', 0)
        cpu_bar = self._make_bar(cpu_pct, 24)
        cpu_color = self._get_color(cpu_pct)

        line_content = f" {cpu_bar} CPU {cpu_pct:>3}%    Pods {m.get('pods_ready', 0)}/{m.get('pods_total', 0)} ready  "
        text.append("┃", style="bold cyan")
        text.append(" ", style="")
        text.append(cpu_bar, style=cpu_color)
        text.append(" CPU ", style="bold white")
        text.append(f"{cpu_pct:>3}%", style=cpu_color)
        text.append("    Pods ", style="dim white")
        text.append(f"{m.get('pods_ready', 0)}", style="bold green")
        text.append("/", style="dim white")
        text.append(f"{m.get('pods_total', 0)}", style="bold white")
        text.append(" ready", style="dim white")
        # Calculate padding needed
        content_len = len(cpu_bar) + len(f" CPU {cpu_pct:>3}%    Pods {m.get('pods_ready', 0)}/{m.get('pods_total', 0)} ready")
        padding = self.BORDER_WIDTH - content_len - 1
        text.append(" " * padding, style="")
        text.append("┃\n", style="bold cyan")

        # MEM bar line
        mem_pct = m.get('mem', 0)
        mem_bar = self._make_bar(mem_pct, 24)
        mem_color = self._get_color(mem_pct)

        text.append("┃", style="bold cyan")
        text.append(" ", style="")
        text.append(mem_bar, style=mem_color)
        text.append(" MEM ", style="bold white")
        text.append(f"{mem_pct:>3}%", style=mem_color)
        text.append("    Events ", style="dim white")
        text.append(f"{m.get('events_per_min', 0)}", style="bold yellow")
        text.append("/min", style="dim white")
        # Calculate padding
        content_len = len(mem_bar) + len(f" MEM {mem_pct:>3}%    Events {m.get('events_per_min', 0)}/min")
        padding = self.BORDER_WIDTH - content_len - 1
        text.append(" " * padding, style="")
        text.append("┃\n", style="bold cyan")

        # Network I/O line
        net_in = m.get('network_in', 0)
        net_out = m.get('network_out', 0)
        text.append("┃", style="bold cyan")
        text.append(f" ↓ ", style="bold green")
        text.append(f"{self._format_bytes(net_in)}/s", style="bold green")
        text.append("  ", style="")
        text.append(f"↑ ", style="bold magenta")
        text.append(f"{self._format_bytes(net_out)}/s", style="bold magenta")
        content_len = len(f" ↓ {self._format_bytes(net_in)}/s  ↑ {self._format_bytes(net_out)}/s")
        padding = self.BORDER_WIDTH - content_len
        text.append(" " * padding, style="")
        text.append("┃\n", style="bold cyan")

        # Bottom border
        text.append("┗", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┛", style="bold cyan")

        return text

    def _make_bar(self, pct: int, width: int = 24) -> str:
        filled = int((pct / 100) * width)
        return "█" * filled + "░" * (width - filled)

    def _get_color(self, pct: int) -> str:
        """Return color based on percentage"""
        if pct < 50:
            return "bold green"
        elif pct < 75:
            return "bold yellow"
        else:
            return "bold red"

    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}TB"


class LiveEvents(Static):
    """Live events stream"""
    events = reactive([])

    BORDER_WIDTH = 64  # Fixed border width
    MAX_EVENTS = 5

    def render(self) -> Text:
        text = Text()

        # Top border
        text.append("┏", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┓\n", style="bold cyan")

        # Title
        title = " ⚡ LIVE EVENTS"
        text.append("┃", style="bold cyan")
        text.append(title, style="bold white")
        text.append(" " * (self.BORDER_WIDTH - len(title)), style="")
        text.append("┃\n", style="bold cyan")

        # Separator
        text.append("┣", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="cyan")
        text.append("┫\n", style="bold cyan")

        # Events - fixed number of rows
        event_list = self.events[-self.MAX_EVENTS:] if self.events else []

        for i in range(self.MAX_EVENTS):
            text.append("┃", style="bold cyan")

            if i < len(event_list):
                event = event_list[i]
                # Truncate event if too long, pad if too short
                if len(event) > self.BORDER_WIDTH:
                    event = event[:self.BORDER_WIDTH - 3] + "..."

                # Parse and colorize event with fixed width
                if "●" in event:
                    parts = event.split("●", 1)
                    text.append(parts[0], style="dim white")
                    text.append("●", style="bold green")
                    if len(parts) > 1:
                        text.append(parts[1], style="white")
                elif "!" in event:
                    parts = event.split("!", 1)
                    text.append(parts[0], style="dim white")
                    text.append("!", style="bold yellow")
                    if len(parts) > 1:
                        text.append(parts[1], style="white")
                else:
                    text.append(f" {event}", style="white")

                # Calculate actual visible length and pad
                actual_len = len(event)
                padding = self.BORDER_WIDTH - actual_len
                if padding > 0:
                    text.append(" " * padding, style="")
            else:
                # Empty line
                text.append(" " * self.BORDER_WIDTH, style="")

            text.append("┃\n", style="bold cyan")

        # Bottom border
        text.append("┗", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┛", style="bold cyan")

        return text


class AgentsPanel(Static):
    """Agents metrics panel"""
    stats = reactive({"active": 0, "spawning": 0, "completed": 0, "failed": 0, "total": 0, "success": 0, "namespaces": 0})

    BORDER_WIDTH = 32  # Fixed border width

    def render(self) -> Text:
        s = self.stats
        text = Text()

        # Top border
        text.append("┏", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┓\n", style="bold cyan")

        # Title
        title = " ⚙ AGENTS"
        text.append("┃", style="bold cyan")
        text.append(title, style="bold white")
        text.append(" " * (self.BORDER_WIDTH - len(title)), style="")
        text.append("┃\n", style="bold cyan")

        # Separator
        text.append("┣", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="cyan")
        text.append("┫\n", style="bold cyan")

        # Stats - fixed layout
        lines = [
            (" Active:     ", s.get('active', 0), "bold green"),
            (" Spawning:   ", s.get('spawning', 0), "bold yellow"),
            (" Completed:  ", s.get('completed', 0), "bold blue"),
            (" Failed:     ", s.get('failed', 0), "bold red"),
        ]

        for label, value, color in lines:
            text.append("┃", style="bold cyan")
            text.append(label, style="dim white")
            value_str = f"{value:>16}"
            text.append(value_str, style=color)
            padding = self.BORDER_WIDTH - len(label) - len(value_str)
            text.append(" " * padding, style="")
            text.append("┃\n", style="bold cyan")

        # Separator
        text.append("┣", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="cyan")
        text.append("┫\n", style="bold cyan")

        # Totals
        text.append("┃", style="bold cyan")
        label = " Total:      "
        value_str = f"{s.get('total', 0):>16}"
        text.append(label, style="bold white")
        text.append(value_str, style="bold white")
        padding = self.BORDER_WIDTH - len(label) - len(value_str)
        text.append(" " * padding, style="")
        text.append("┃\n", style="bold cyan")

        # Success rate
        success = s.get('success', 0)
        success_color = "bold green" if success > 80 else "bold yellow" if success > 50 else "bold red"
        text.append("┃", style="bold cyan")
        label = " Success:    "
        value_str = f"{success:>15}%"
        text.append(label, style="bold white")
        text.append(value_str, style=success_color)
        padding = self.BORDER_WIDTH - len(label) - len(value_str)
        text.append(" " * padding, style="")
        text.append("┃\n", style="bold cyan")

        # Namespaces
        text.append("┃", style="bold cyan")
        label = " Namespaces: "
        value_str = f"{s.get('namespaces', 0):>16}"
        text.append(label, style="dim white")
        text.append(value_str, style="bold cyan")
        padding = self.BORDER_WIDTH - len(label) - len(value_str)
        text.append(" " * padding, style="")
        text.append("┃\n", style="bold cyan")

        # Bottom border
        text.append("┗", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┛", style="bold cyan")

        return text


class NodesPanel(Static):
    """Nodes panel with metrics"""
    nodes = reactive({})

    BORDER_WIDTH = 56  # Fixed border width (increased for disk)
    MAX_NODES = 4

    def render(self) -> Text:
        text = Text()

        # Top border
        text.append("┏", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┓\n", style="bold cyan")

        # Title with legend
        title = " ⬢ NODES"
        text.append("┃", style="bold cyan")
        text.append(title, style="bold white")
        text.append(" " * (self.BORDER_WIDTH - len(title)), style="")
        text.append("┃\n", style="bold cyan")

        # Separator
        text.append("┣", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="cyan")
        text.append("┫\n", style="bold cyan")

        # Node rows - fixed number
        node_list = list(self.nodes.items())[:self.MAX_NODES]

        for i in range(self.MAX_NODES):
            text.append("┃", style="bold cyan")

            if i < len(node_list):
                name, data = node_list[i]
                cpu_pct = data.get("cpu", 0)
                mem_pct = data.get("mem", 0)
                disk_pct = data.get("disk", 0)
                cpu_bar = self._make_bar(cpu_pct, 6)
                mem_bar = self._make_bar(mem_pct, 6)
                disk_bar = self._make_bar(disk_pct, 6)

                cpu_color = self._get_color(cpu_pct)
                mem_color = self._get_color(mem_pct)
                disk_color = self._get_color(disk_pct)

                # Format: ◆ name       ██████ 67%  ██████ 54%  ██████ 45%
                text.append(" ◆ ", style="bold magenta")
                text.append(f"{name:<10}", style="bold white")
                text.append(" ", style="")
                text.append(cpu_bar, style=cpu_color)
                text.append(f" {cpu_pct:>2}%", style=cpu_color)
                text.append("  ", style="")
                text.append(mem_bar, style=mem_color)
                text.append(f" {mem_pct:>2}%", style=mem_color)
                text.append("  ", style="")
                text.append(disk_bar, style=disk_color)
                text.append(f" {disk_pct:>2}%", style=disk_color)

                # Calculate total content length
                content = f" ◆ {name:<10} {cpu_bar} {cpu_pct:>2}%  {mem_bar} {mem_pct:>2}%  {disk_bar} {disk_pct:>2}%"
                content_len = len(content)
                padding = self.BORDER_WIDTH - content_len
                text.append(" " * padding, style="")
            else:
                # Empty line
                text.append(" " * self.BORDER_WIDTH, style="")

            text.append("┃\n", style="bold cyan")

        # Bottom border
        text.append("┗", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┛", style="bold cyan")

        return text

    def _make_bar(self, pct: int, width: int = 6) -> str:
        filled = int((pct / 100) * width)
        return "█" * filled + "░" * (width - filled)

    def _get_color(self, pct: int) -> str:
        """Return color based on percentage"""
        if pct < 50:
            return "bold green"
        elif pct < 75:
            return "bold yellow"
        else:
            return "bold red"


class PodDistribution(Static):
    """Pod distribution by namespace"""
    distribution = reactive({})

    BORDER_WIDTH = 64  # Fixed border width
    MAX_NAMESPACES = 5

    def render(self) -> Text:
        text = Text()

        # Top border
        text.append("┏", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┓\n", style="bold cyan")

        # Title
        title = " 📦 POD DISTRIBUTION"
        text.append("┃", style="bold cyan")
        text.append(title, style="bold white")
        text.append(" " * (self.BORDER_WIDTH - len(title)), style="")
        text.append("┃\n", style="bold cyan")

        # Separator
        text.append("┣", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="cyan")
        text.append("┫\n", style="bold cyan")

        # Namespace rows - top 5
        dist_list = list(self.distribution.items())[:self.MAX_NAMESPACES]
        total_pods = sum(self.distribution.values()) if self.distribution else 1

        for i in range(self.MAX_NAMESPACES):
            text.append("┃", style="bold cyan")

            if i < len(dist_list):
                namespace, count = dist_list[i]
                # Truncate long namespace names
                if len(namespace) > 18:
                    namespace = namespace[:15] + "..."

                percentage = int((count / total_pods) * 100) if total_pods > 0 else 0
                bar_width = 30
                bar = self._make_bar(percentage, bar_width)

                # Build the line with exact widths
                ns_part = f" {namespace:<18}"  # 19 chars
                bar_part = bar  # 30 chars
                pct_part = f" {percentage:>3}%"  # 5 chars
                pods_part = f" ({count} pods)"  # variable length

                # Calculate remaining space
                used = 19 + 30 + 5 + len(pods_part)
                padding = self.BORDER_WIDTH - used

                # Render with proper spacing
                text.append(ns_part, style="bold white")
                text.append(" ", style="")
                text.append(bar_part, style="bold cyan")
                text.append(pct_part, style="bold cyan")
                text.append(pods_part, style="dim white")
                if padding > 0:
                    text.append(" " * padding, style="")
            else:
                # Empty line
                text.append(" " * self.BORDER_WIDTH, style="")

            text.append("┃\n", style="bold cyan")

        # Bottom border
        text.append("┗", style="bold cyan")
        text.append("━" * self.BORDER_WIDTH, style="bold cyan")
        text.append("┛", style="bold cyan")

        return text

    def _make_bar(self, pct: int, width: int = 30) -> str:
        filled = int((pct / 100) * width)
        return "█" * filled + "░" * (width - filled)


class LoadingIndicator(Static):
    """Simple loading indicator"""

    def __init__(self, message: str = "Loading..."):
        super().__init__()
        self.message = message

    def render(self) -> str:
        return f"\n\n    {self.message}\n\n"
