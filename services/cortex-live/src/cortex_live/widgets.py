"""Custom widgets for Cortex Live"""

from textual.widgets import Static
from textual.reactive import reactive
from typing import Dict, List


class StatusBar(Static):
    """Top status bar"""
    node_count = reactive(0)

    def render(self) -> str:
        return f"CORTEX LIVE{' ' * 50}▲ {self.node_count} nodes | k3s"


class ClusterPulse(Static):
    """Cluster pulse metrics"""
    metrics = reactive({"cpu": 68, "mem": 41, "pods_ready": 0, "pods_total": 0, "events_per_min": 12})

    def render(self) -> str:
        m = self.metrics
        cpu_bar = self._make_bar(m.get("cpu", 0), 20)
        mem_bar = self._make_bar(m.get("mem", 0), 20)

        return f"""┌─ CLUSTER PULSE ──────────────────────────────────────────────┐
│ {cpu_bar}  CPU {m.get('cpu', 0)}%    Pods: {m.get('pods_ready', 0)}/{m.get('pods_total', 0)} ready  │
│ {mem_bar}  MEM {m.get('mem', 0)}%    Events: {m.get('events_per_min', 0)}/min         │
└──────────────────────────────────────────────────────────────┘"""

    def _make_bar(self, pct: int, width: int = 20) -> str:
        filled = int((pct / 100) * width)
        return "█" * filled + "░" * (width - filled)


class LiveEvents(Static):
    """Live events stream"""
    events = reactive([])

    def render(self) -> str:
        lines = ["┌─ LIVE EVENTS ────────────────────────────────────────────────┐"]
        for event in self.events[-5:]:
            lines.append(f"│ {event:<62} │")
        while len(lines) < 7:
            lines.append("│" + " " * 62 + " │")
        lines.append("└──────────────────────────────────────────────────────────────┘")
        return "\n".join(lines)


class AgentsPanel(Static):
    """Agents metrics panel"""
    stats = reactive({"active": 0, "spawning": 0, "completed": 0, "failed": 0, "total": 0, "success": 0})

    def render(self) -> str:
        s = self.stats
        return f"""┌─ AGENTS ─────────────────────┐
│ Active:       {s.get('active', 0):>14} │
│ Spawning:     {s.get('spawning', 0):>14} │
│ Completed:    {s.get('completed', 0):>14} │
│ Failed:       {s.get('failed', 0):>14} │
│ ────────────────────────── │
│ Total:        {s.get('total', 0):>14} │
│ Success:      {s.get('success', 0):>13}% │
└──────────────────────────────┘"""


class NodesPanel(Static):
    """Nodes panel with metrics"""
    nodes = reactive({})

    def render(self) -> str:
        lines = ["┌─ NODES ──────────────────────────────────┐"]
        for name, data in list(self.nodes.items())[:4]:
            cpu_bar = self._make_bar(data.get("cpu", 0), 8)
            mem_bar = self._make_bar(data.get("mem", 0), 8)
            lines.append(f"│ ■ {name:<10} {cpu_bar} {data.get('cpu', 0):>2}%  {mem_bar} {data.get('mem', 0):>2}% │")
        while len(lines) < 5:
            lines.append("│" + " " * 44 + " │")
        lines.append("└──────────────────────────────────────────┘")
        return "\n".join(lines)

    def _make_bar(self, pct: int, width: int = 8) -> str:
        filled = int((pct / 100) * width)
        return "█" * filled + "░" * (width - filled)


class LoadingIndicator(Static):
    """Simple loading indicator"""

    def __init__(self, message: str = "Loading..."):
        super().__init__()
        self.message = message

    def render(self) -> str:
        return f"\n\n    {self.message}\n\n"
