"""Layer widgets for c-top - the four monitoring layers

Uses Textual's theming system for full theme support.
Returns markup strings with $variable syntax for dynamic theme colors.
"""

from textual.widgets import Static
from textual.reactive import reactive
from typing import Dict, List, Any, Optional
from collections import deque


# Sparkline characters (8 levels)
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: List[int], width: int = 10) -> str:
    """Generate a sparkline from a list of values (0-100)"""
    if not values:
        return "░" * width

    # Take last `width` values
    vals = list(values)[-width:]

    # Pad with zeros if needed
    while len(vals) < width:
        vals.insert(0, 0)

    # Map to sparkline characters
    result = ""
    for v in vals:
        idx = min(7, max(0, int(v / 100 * 7)))
        result += SPARK_CHARS[idx]

    return result


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f}TB"


def make_bar(pct: int, width: int = 20) -> str:
    """Create a progress bar"""
    filled = int((pct / 100) * width)
    return "█" * filled + "░" * (width - filled)


def get_pct_style(pct: int) -> str:
    """Return markup style based on percentage threshold"""
    if pct < 50:
        return "bold $primary"
    elif pct < 75:
        return "$warning"
    else:
        return "bold $error"


class ClusterLayer(Static):
    """Layer 1: Cluster resources, services, and chat layer metrics"""

    metrics = reactive({
        "cpu": 0, "mem": 0, "disk": 0,
        "network_in": 0, "network_out": 0,
        "pods_ready": 0, "pods_total": 0,
        "jobs_active": 0,
    })
    nodes = reactive({})
    services = reactive([])
    history = reactive({
        "cpu": deque(maxlen=10),
        "mem": deque(maxlen=10),
    })

    def render(self) -> str:
        """Render using markup strings with $variable syntax for theme colors"""
        m = self.metrics
        lines = []

        # Column width constants for alignment
        LEFT_COL_WIDTH = 41  # Width of cluster resources column before ║
        RIGHT_COL_WIDTH = 38  # Width of services column after ║

        # ═══ CLUSTER RESOURCES ═══════════════════╦═══ SERVICES ═════════════════════════
        lines.append(
            "[dim $text-muted]═══ [/][bold $primary]CLUSTER RESOURCES[/]"
            "[dim $text-muted] ════════════════════════╦═══ [/][bold $primary]SERVICES[/]"
            "[dim $text-muted] ══════════════════════════════[/]"
        )

        # CPU line: " cpu [████████████████████│100%] ▁▂▃▄▅▆▇█▁▂"
        # Format: 5 (label) + 26 (bar+pct) + 10 (spark) = 41 chars
        cpu = m.get("cpu", 0)
        cpu_bar = make_bar(cpu, 20)
        cpu_spark = sparkline(list(self.history.get("cpu", [])))
        cpu_style = get_pct_style(cpu)

        svc_line = self._format_service(0)
        lines.append(
            f"[bold $primary] cpu [/][{cpu_style}]\\[{cpu_bar}│{cpu:>3}%][/]"
            f"[$secondary] {cpu_spark}[/][dim $text-muted] ║[/]{svc_line}"
        )

        # MEM line
        mem = m.get("mem", 0)
        mem_bar = make_bar(mem, 20)
        mem_spark = sparkline(list(self.history.get("mem", [])))
        mem_style = get_pct_style(mem)

        svc_line = self._format_service(1)
        lines.append(
            f"[bold $primary] mem [/][{mem_style}]\\[{mem_bar}│{mem:>3}%][/]"
            f"[$secondary] {mem_spark}[/][dim $text-muted] ║[/]{svc_line}"
        )

        # DISK line (no sparkline, use spaces to match width)
        disk = m.get("disk", 0)
        disk_bar = make_bar(disk, 20)
        disk_style = get_pct_style(disk)

        svc_line = self._format_service(2)
        lines.append(
            f"[bold $primary] dsk [/][{disk_style}]\\[{disk_bar}│{disk:>3}%][/]"
            f"[$secondary] {'':10}[/][dim $text-muted] ║[/]{svc_line}"
        )

        # Network line - format to match same width: 41 chars
        # " net  ↓    0.0B/s  ↑    0.0B/s        "
        net_in = m.get("network_in", 0)
        net_out = m.get("network_out", 0)
        svc_line = self._format_service(3)
        lines.append(
            f"[bold $primary] net [/][$secondary] ↓{format_bytes(net_in):>8}/s ↑{format_bytes(net_out):>8}/s[/]"
            f"[dim $text-muted]     ║[/]{svc_line}"
        )

        # Summary line
        lines.append("[dim $text-muted]─────────────────────────────────────────╨" + "─" * 38 + "[/]")

        pods_ready = m.get("pods_ready", 0)
        pods_total = m.get("pods_total", 0)
        jobs = m.get("jobs_active", 0)

        lines.append(
            f"[dim $text-muted] pods: [/][bold $primary]{pods_ready}/{pods_total}[/]"
            f"[dim $text-muted]   jobs: [/][bold $primary]{jobs}[/][dim $text-muted] active[/]"
            f"[dim $text-muted]                    │ nodes: [/][bold $primary]{len(self.nodes)}[/]"
        )

        return "\n".join(lines)

    def _format_service(self, idx: int) -> str:
        """Format a service line with markup"""
        if idx >= len(self.services):
            return ""
        svc = self.services[idx]
        name = svc.get("name", "")[:16]
        ready = svc.get("ready", 0)
        total = svc.get("total", 0)
        is_ready = ready == total and total > 0
        status = "●" if is_ready else "○"
        status_style = "bold $success" if is_ready else "$warning"
        return f"[bold $primary] {name:<16} [/][{status_style}]{status}[/][$secondary] {ready}/{total}[/]"


class NetworkLayer(Static):
    """Layer 2: Tailscale mesh and UniFi network"""

    mesh = reactive({
        "peers": [],
        "status": "disconnected",
        "total_peers": 0,
        "online_peers": 0,
    })
    unifi = reactive({
        "available": False,
        "sites": [],
        "total_clients": 0,
        "console": None,
    })

    def render(self) -> str:
        """Render using markup strings with $variable syntax for theme colors"""
        lines = []

        # Tailscale section header with status
        mesh_status = self.mesh.get("status", "unknown")
        if mesh_status == "connected":
            status_icon = "●"
            status_style = "bold $success"
        elif mesh_status == "unavailable":
            status_icon = "○"
            status_style = "dim $text-muted"
        else:
            status_icon = "◐"
            status_style = "$warning"

        total_peers = self.mesh.get("total_peers", 0)
        online_peers = self.mesh.get("online_peers", 0)

        lines.append(
            f"[dim $text-muted]═══ [/][{status_style}]{status_icon}[/] [bold $primary]TAILSCALE MESH[/]"
            f"[dim $text-muted] ═══════════════════════════════════════════════════ [/]"
            f"[$secondary]{online_peers}/{total_peers} online[/]"
        )

        # Mesh peers visualization
        peers = self.mesh.get("peers", [])
        if peers:
            # Show connected peers with connection type indicator
            peer_line = ""
            for i, peer in enumerate(peers[:6]):  # Show up to 6 peers
                name = peer.get("name", "unknown")[:12]
                latency = peer.get("latency", 0)
                is_online = peer.get("online", False)
                conn_type = peer.get("connection_type", "unknown")

                # Status icon with connection type
                if is_online:
                    if conn_type == "direct":
                        status = "●"  # Solid = direct
                        status_style = "bold $success"
                    else:
                        status = "◉"  # Ring = relay
                        status_style = "$warning"
                else:
                    status = "○"
                    status_style = "dim $text-muted"

                latency_str = f"{latency:>3}ms" if latency > 0 else "  --"
                peer_line += f"  [{status_style}]{status}[/] [bold $primary]{name:<12}[/][$secondary]{latency_str}[/]"

                if (i + 1) % 3 == 0:
                    lines.append(peer_line)
                    peer_line = ""
                else:
                    peer_line += "  "
            if peer_line:
                lines.append(peer_line)
        elif mesh_status == "unavailable":
            lines.append("  [dim $text-muted]\\[ tailscale CLI not available ][/]")
        else:
            lines.append("  [dim $text-muted]\\[ no peers found ][/]")

        # UniFi section (if available)
        if self.unifi.get("available", False):
            lines.append("")

            # Get console info
            console = self.unifi.get("console", {}) or {}
            console_name = console.get("model", "UniFi")
            console_state = console.get("state", "unknown")
            console_icon = "●" if console_state == "connected" else "○"
            console_style = "bold $success" if console_state == "connected" else "dim $text-muted"

            lines.append(
                f"[dim $text-muted]═══ [/][{console_style}]{console_icon}[/] [bold $primary]UNIFI NETWORK[/]"
                f"[dim $text-muted] ({console_name}) ══════════════════════════════════════════════════════[/]"
            )

            # Show each site
            sites = self.unifi.get("sites", [])
            for site in sites[:3]:  # Show up to 3 sites
                site_name = site.get("name", "Unknown")[:20]
                isp_name = site.get("isp_name", "Unknown")[:15]

                # Client counts
                wifi_clients = site.get("wifi_clients", 0)
                wired_clients = site.get("wired_clients", 0)
                total_clients = site.get("total_clients", 0)

                # Device counts
                total_devices = site.get("total_devices", 0)
                online_devices = site.get("online_devices", 0)

                # Network configuration counts
                networks = site.get("networks", 0)
                wlans = site.get("wlans", 0)

                # Security
                ips_mode = site.get("ips_mode", "off")
                ips_rules = site.get("ips_rules", 0)

                # LAN IP (gateway LAN address)
                lan_ip = site.get("lan_ip", "N/A") or "N/A"

                # Site header line
                lines.append(
                    f"[bold $primary] {site_name:<20}[/]"
                    f"[dim $text-muted] ISP: [/][$secondary]{isp_name:<15}[/]"
                    f"[dim $text-muted] LAN: [/][$secondary]{lan_ip}[/]"
                )

                # Clients & Devices line
                lines.append(
                    f"[dim $text-muted]   clients: [/][bold $primary]{total_clients:>3}[/]"
                    f"[dim $text-muted] (wifi:[/][$secondary]{wifi_clients}[/]"
                    f"[dim $text-muted] wired:[/][$secondary]{wired_clients}[/][dim $text-muted])[/]"
                    f"[dim $text-muted]   devices: [/][bold $primary]{online_devices}/{total_devices}[/]"
                )

                # Networks & Security line
                ips_style = "bold $success" if ips_mode != "off" else "dim $text-muted"
                ips_display = f"{ips_mode}" if ips_mode != "off" else "off"

                # Format IPS rules count
                if ips_rules >= 1000:
                    rules_str = f"{ips_rules/1000:.0f}K"
                else:
                    rules_str = str(ips_rules)

                lines.append(
                    f"[dim $text-muted]   networks: [/][bold $primary]{networks}[/]"
                    f"[dim $text-muted]   wlans: [/][bold $primary]{wlans}[/]"
                    f"[dim $text-muted]   IPS: [/][{ips_style}]{ips_display}[/]"
                    f"[dim $text-muted] ({rules_str} rules)[/]"
                )

        return "\n".join(lines)


class WorkersLayer(Static):
    """Layer 3: htop-style agent/task process list"""

    worker_list = reactive([])  # Renamed from 'workers' to avoid shadowing Textual's workers
    queue_depth = reactive({"high": 0, "normal": 0, "low": 0})
    stats = reactive({"active": 0, "idle": 0, "completed_hr": 0, "avg_time": 0})

    def render(self) -> str:
        """Render using markup strings with $variable syntax for theme colors"""
        lines = []

        # Header
        lines.append("[bold $primary]  ID     STATE    AGENT                  TASK                           CPU   MEM   TIME[/]")
        lines.append("[dim $text-muted]" + "─" * 95 + "[/]")

        # Worker rows (htop style)
        workers = self.worker_list or []

        # Show up to 12 workers
        for worker in workers[:12]:
            wid = worker.get("id", "")[:6]
            state = worker.get("status", "unknown")
            agent = worker.get("agent_type", "worker")[:20]
            task = worker.get("current_task", "-")[:30]
            cpu = worker.get("cpu", 0)
            mem = worker.get("mem", "0M")
            time_str = worker.get("time", "00:00")

            # State icon and style
            if state == "busy":
                state_icon = "◉ run "
                state_style = "bold $primary"
            elif state in ("ready", "idle"):
                state_icon = "◎ idle"
                state_style = "$secondary"
            elif state == "completed":
                state_icon = "✓ done"
                state_style = "dim $text-muted"
            elif state == "failed":
                state_icon = "✗ fail"
                state_style = "bold $error"
            else:
                state_icon = "? " + state[:4]
                state_style = "dim $text-muted"

            cpu_style = get_pct_style(cpu) if cpu > 0 else "dim $text-muted"

            lines.append(
                f"[dim $text-muted] {wid:<6} [/][{state_style}]{state_icon} [/]"
                f"[bold $primary] {agent:<20} [/][$secondary] {task:<30} [/]"
                f"[{cpu_style}] {cpu:>3}%[/][$secondary] {mem:>5}[/][dim $text-muted] {time_str:>6}[/]"
            )

        # Pad with empty rows if needed
        for _ in range(max(0, 8 - len(workers))):
            lines.append(" " * 95)

        # Separator
        lines.append("[dim $text-muted]" + "─" * 95 + "[/]")

        # Summary stats
        s = self.stats
        q = self.queue_depth
        high_style = "bold $error" if q.get('high', 0) > 0 else "dim $text-muted"

        lines.append(
            f"[dim $text-muted] active: [/][bold $primary]{s.get('active', 0)}[/]"
            f"[dim $text-muted]   idle: [/][$secondary]{s.get('idle', 0)}[/]"
            f"[dim $text-muted]   completed/hr: [/][bold $primary]{s.get('completed_hr', 0)}[/]"
            f"[dim $text-muted]   avg: [/][$secondary]{s.get('avg_time', 0)}s[/]"
            f"[dim $text-muted]   │ queue: [/][{high_style}]high:{q.get('high', 0)} [/]"
            f"[$secondary]norm:{q.get('normal', 0)} [/][dim $text-muted]low:{q.get('low', 0)}[/]"
        )

        return "\n".join(lines)


class FabricLayer(Static):
    """Layer 4: MCP servers, Qdrant collections, routing patterns"""

    mcp_servers = reactive([])
    tool_invocations = reactive([])
    qdrant = reactive({
        "collections": [],
        "memory": "0GB",
    })
    routing = reactive({
        "cache_hit": 0,
        "keyword": 0,
        "similarity": 0,
        "escalate": 0,
    })

    def render(self) -> str:
        """Render using markup strings with $variable syntax for theme colors"""
        lines = []

        # Column width constants for alignment
        LEFT_COL_WIDTH = 41  # Width before ║

        # MCP Servers section
        lines.append(
            "[dim $text-muted]═══ [/][bold $primary]MCP SERVERS[/]"
            "[dim $text-muted] ═════════════════════════════╦═══ [/][bold $primary]TOOL INVOCATIONS (5min)[/]"
            "[dim $text-muted] ══════════════════[/]"
        )

        servers = self.mcp_servers or []
        tools = self.tool_invocations or []

        max_rows = max(len(servers), len(tools), 5)

        for i in range(max_rows):
            left_col = ""
            right_col = ""

            # MCP server column (fixed 41 chars)
            if i < len(servers):
                srv = servers[i]
                name = srv.get("name", "")[:20]
                status = "●" if srv.get("connected", False) else "○"
                tool_count = srv.get("tools", 0)
                status_style = "bold $success" if srv.get("connected") else "dim $text-muted"
                source = srv.get("source", "")[:8]

                left_col = f" [{status_style}]{status}[/] [bold $primary]{name:<20}[/][$secondary] {source:<8}[/][dim $text-muted] {tool_count:>2}t[/]"
            else:
                left_col = f"{'':41}"

            # Tool invocation column
            if i < len(tools):
                tool = tools[i]
                name = tool.get("name", "")[:22]
                count = tool.get("count", 0)
                bar_width = min(8, int(count / 20))  # Scale to max 8 chars
                bar = "█" * bar_width + "░" * (8 - bar_width)

                right_col = f"[$secondary]{name:<22}[/][bold $primary] {bar} {count:>4}[/]"
            else:
                right_col = ""

            lines.append(f"{left_col}[dim $text-muted] ║[/] {right_col}")

        # Separator
        lines.append(
            "[dim $text-muted]═══ [/][bold $primary]QDRANT[/]"
            "[dim $text-muted] ════════════════════════════════╬═══ [/][bold $primary]ROUTING PATTERNS[/]"
            "[dim $text-muted] ═══════════════════════[/]"
        )

        # Qdrant collections
        collections = self.qdrant.get("collections", [])
        r = self.routing

        routing_data = [
            ("cache_hit", r.get("cache_hit", 0), "bold $primary"),
            ("similarity", r.get("similarity", 0), "$secondary"),
            ("escalate", r.get("escalate", 0), "dim $text-muted"),
        ]

        max_qdrant_rows = max(len(collections), len(routing_data), 3)

        for i in range(max_qdrant_rows):
            left_col = ""
            right_col = ""

            # Qdrant collection column
            if i < len(collections):
                coll = collections[i]
                name = coll.get("name", "")[:16]
                vectors = coll.get("vectors", 0)
                dim = coll.get("dimensions", 0)
                p99 = coll.get("p99_ms", 0)

                # Format vector count
                if vectors >= 1000000:
                    vec_str = f"{vectors/1000000:.1f}M"
                elif vectors >= 1000:
                    vec_str = f"{vectors/1000:.0f}K"
                else:
                    vec_str = f"{vectors}"

                left_col = f"[bold $primary] {name:<16}[/][$secondary] {vec_str:>5}[/][dim $text-muted] {dim}d p99:{p99:>2}ms[/]"
            else:
                left_col = f"{'':41}"

            # Routing pattern column
            if i < len(routing_data):
                rname, pct, style = routing_data[i]
                bar = make_bar(pct, 10)
                right_col = f"[$secondary]{rname:<12}[/][{style}] {bar} {pct:>3}%[/]"

            lines.append(f"{left_col}[dim $text-muted] ║[/] {right_col}")

        # Memory summary
        lines.append(f"[dim $text-muted] memory: [/][bold $primary]{self.qdrant.get('memory', '0GB')}[/]")

        return "\n".join(lines)


class ActivityStream(Static):
    """Persistent activity stream shown across all layers"""

    events = reactive([])
    rate = reactive(0)  # events per hour

    MAX_EVENTS = 4

    def render(self) -> str:
        """Render using markup strings with $variable syntax for theme colors"""
        lines = []

        # Header with rate
        lines.append(
            "[dim $text-muted]═══ [/][bold $primary]⚡ ACTIVITY[/]"
            "[dim $text-muted] ══════════════════════════════════════════════════════════════ [/]"
            f"[$secondary]{self.rate}/hr[/][dim $text-muted] ═══[/]"
        )

        # Event rows
        events = self.events or []

        for i in range(self.MAX_EVENTS):
            if i < len(events):
                ev = events[i]
                ts = ev.get("timestamp", "")
                source = ev.get("source", "")[:12]
                action = ev.get("action", "")[:12]
                detail = ev.get("detail", "")[:50]

                # Most recent event is brighter
                if i == 0:
                    style = "bold $primary"
                elif i == 1:
                    style = "$secondary"
                else:
                    style = "dim $text-muted"

                lines.append(
                    f"[dim $text-muted] {ts} │ [/][{style}]{source:<12}[/]"
                    f"[dim $text-muted] │ [/][{style}]{action:<12}[/]"
                    f"[dim $text-muted] │ [/][{style}]{detail}[/]"
                )
            else:
                lines.append("")

        return "\n".join(lines)
