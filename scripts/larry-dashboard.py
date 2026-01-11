#!/usr/bin/env python3
"""
3-Larry Distributed Orchestration Dashboard
Real-time monitoring of all 3 Larry instances via Redis
"""

import redis
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any

# Terminal colors
class Colors:
    PURPLE = '\033[0;35m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

# Configuration
REDIS_HOST = "redis-cluster.redis-ha.svc.cluster.local"
REDIS_PORT = 6379
REFRESH_INTERVAL = 2  # seconds

class LarryDashboard:
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis.ping()
        except redis.ConnectionError:
            print(f"{Colors.RED}ERROR: Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}{Colors.NC}")
            sys.exit(1)

        self.start_time = None
        self.event_log = []
        self.max_log_entries = 10

    def get_larry_status(self, larry_id: str) -> Dict[str, Any]:
        """Get status for a specific Larry instance."""
        status = {
            'larry_id': larry_id,
            'status': self.redis.get(f"phase:{larry_id}:status") or "unknown",
            'progress': int(self.redis.get(f"phase:{larry_id}:progress") or 0),
            'started_at': self.redis.get(f"phase:{larry_id}:started_at"),
            'completed_at': self.redis.get(f"phase:{larry_id}:completed_at"),
        }

        # Larry-specific metrics
        if larry_id == "larry-01":
            metrics = self.redis.hgetall(f"phase:{larry_id}:metrics")
            status['metrics'] = metrics
        elif larry_id == "larry-02":
            findings = self.redis.hgetall(f"phase:{larry_id}:findings")
            status['findings'] = findings
        elif larry_id == "larry-03":
            status['inventory'] = {
                'assets_discovered': int(self.redis.get(f"phase:{larry_id}:inventory:assets_discovered") or 0),
                'prs_created': int(self.redis.get(f"phase:{larry_id}:development:prs_created") or 0),
                'coverage_increase': self.redis.get(f"phase:{larry_id}:testing:coverage_increase") or "0%"
            }

        return status

    def get_active_tasks(self) -> list:
        """Get all active task locks."""
        tasks = []
        for key in self.redis.scan_iter("task:lock:*"):
            task_id = key.split(":")[-1]
            owner = self.redis.get(key)
            status = self.redis.get(f"task:status:{task_id}")
            tasks.append({
                'task_id': task_id,
                'owner': owner,
                'status': status
            })
        return tasks

    def get_worker_count(self) -> Dict[str, int]:
        """Get worker counts for each Larry."""
        counts = {}
        for larry_id in ["larry-01", "larry-02", "larry-03"]:
            worker_keys = list(self.redis.scan_iter(f"worker:{larry_id}-*"))
            counts[larry_id] = len(worker_keys)
        return counts

    def draw_progress_bar(self, progress: int, width: int = 30) -> str:
        """Draw a text progress bar."""
        filled = int(progress * width / 100)
        empty = width - filled
        bar = "=" * filled + " " * empty
        return f"[{bar}] {progress:3d}%"

    def get_status_color(self, status: str) -> str:
        """Get color for status."""
        colors = {
            'pending': Colors.YELLOW,
            'in_progress': Colors.CYAN,
            'completed': Colors.GREEN,
            'failed': Colors.RED,
            'unknown': Colors.YELLOW
        }
        return colors.get(status, Colors.NC)

    def subscribe_to_events(self):
        """Subscribe to Larry coordination events."""
        pubsub = self.redis.pubsub()
        pubsub.subscribe('larry:coordination', 'larry:alerts')

        # Start listening in background
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    event = json.loads(message['data'])
                    self.event_log.append({
                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                        'channel': message['channel'],
                        'event': event
                    })
                    # Keep only last N entries
                    if len(self.event_log) > self.max_log_entries:
                        self.event_log.pop(0)
                except json.JSONDecodeError:
                    pass

    def render_dashboard(self):
        """Render the complete dashboard."""
        # Clear screen
        print("\033[2J\033[H", end='')

        # Header
        print(f"{Colors.CYAN}{Colors.BOLD}╔════════════════════════════════════════════════════════════════════════════╗{Colors.NC}")
        print(f"{Colors.CYAN}{Colors.BOLD}║          3-LARRY DISTRIBUTED ORCHESTRATION DASHBOARD                      ║{Colors.NC}")
        print(f"{Colors.CYAN}{Colors.BOLD}╚════════════════════════════════════════════════════════════════════════════╝{Colors.NC}")
        print()

        # Timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {Colors.BLUE}Current Time:{Colors.NC} {now}")

        # Calculate elapsed time
        if self.start_time is None:
            # Try to get earliest start time
            earliest = None
            for larry_id in ["larry-01", "larry-02", "larry-03"]:
                started_at = self.redis.get(f"phase:{larry_id}:started_at")
                if started_at:
                    if earliest is None or started_at < earliest:
                        earliest = started_at
            if earliest:
                try:
                    self.start_time = datetime.fromisoformat(earliest.replace('Z', '+00:00'))
                except:
                    pass

        if self.start_time:
            elapsed = (datetime.now() - self.start_time.replace(tzinfo=None)).total_seconds()
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            print(f"  {Colors.BLUE}Elapsed Time:{Colors.NC} {minutes}m {seconds}s / 40m")
        print()

        # Larry status section
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
        print(f"{Colors.BOLD}  LARRY STATUS{Colors.NC}")
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
        print()

        # Larry-01 (Infrastructure)
        larry01 = self.get_larry_status("larry-01")
        status_color = self.get_status_color(larry01['status'])
        print(f"  {Colors.PURPLE}● LARRY-01 (Infrastructure & Database){Colors.NC}")
        print(f"    Status:   {status_color}{larry01['status']:^12}{Colors.NC}")
        print(f"    Progress: {self.draw_progress_bar(larry01['progress'])}")
        if larry01.get('metrics'):
            print(f"    Metrics:  Tasks Completed: {larry01['metrics'].get('tasks_completed', 0)} | Workers Active: {larry01['metrics'].get('workers_active', 0)}")
        print()

        # Larry-02 (Security)
        larry02 = self.get_larry_status("larry-02")
        status_color = self.get_status_color(larry02['status'])
        print(f"  {Colors.RED}● LARRY-02 (Security & Compliance){Colors.NC}")
        print(f"    Status:   {status_color}{larry02['status']:^12}{Colors.NC}")
        print(f"    Progress: {self.draw_progress_bar(larry02['progress'])}")
        if larry02.get('findings'):
            findings = larry02['findings']
            print(f"    Findings: Critical: {findings.get('critical', 0)} | High: {findings.get('high', 0)} | Medium: {findings.get('medium', 0)} | Low: {findings.get('low', 0)}")
        print()

        # Larry-03 (Development)
        larry03 = self.get_larry_status("larry-03")
        status_color = self.get_status_color(larry03['status'])
        print(f"  {Colors.GREEN}● LARRY-03 (Development & Inventory){Colors.NC}")
        print(f"    Status:   {status_color}{larry03['status']:^12}{Colors.NC}")
        print(f"    Progress: {self.draw_progress_bar(larry03['progress'])}")
        if larry03.get('inventory'):
            inv = larry03['inventory']
            print(f"    Metrics:  Assets: {inv['assets_discovered']} | PRs: {inv['prs_created']} | Coverage: {inv['coverage_increase']}")
        print()

        # Active tasks
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
        print(f"{Colors.BOLD}  ACTIVE TASKS{Colors.NC}")
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
        print()

        tasks = self.get_active_tasks()
        if tasks:
            for task in tasks[:10]:  # Show max 10 tasks
                owner_color = Colors.PURPLE if task['owner'] == 'larry-01' else Colors.RED if task['owner'] == 'larry-02' else Colors.GREEN
                status_color = self.get_status_color(task['status'])
                print(f"  {owner_color}[{task['owner']}]{Colors.NC} {task['task_id']:40} {status_color}{task['status']}{Colors.NC}")
        else:
            print(f"  {Colors.YELLOW}No active tasks{Colors.NC}")
        print()

        # Event log
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
        print(f"{Colors.BOLD}  RECENT EVENTS{Colors.NC}")
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
        print()

        if self.event_log:
            for entry in reversed(self.event_log[-10:]):  # Show last 10 events
                event = entry['event']
                channel_color = Colors.CYAN if entry['channel'] == 'larry:coordination' else Colors.RED
                from_color = Colors.PURPLE if event.get('from') == 'larry-01' else Colors.RED if event.get('from') == 'larry-02' else Colors.GREEN

                timestamp = entry['timestamp']
                event_type = event.get('event', 'unknown')
                message = event.get('message', '')

                print(f"  {Colors.BLUE}[{timestamp}]{Colors.NC} {channel_color}[{entry['channel'].split(':')[1]}]{Colors.NC} {from_color}[{event.get('from', 'unknown')}]{Colors.NC} {event_type}")
                if message:
                    print(f"    → {message}")
        else:
            print(f"  {Colors.YELLOW}No events yet{Colors.NC}")
        print()

        # Footer
        print(f"{Colors.CYAN}Press Ctrl+C to exit | Refreshing every {REFRESH_INTERVAL}s{Colors.NC}")

    def run(self):
        """Main dashboard loop."""
        print(f"{Colors.CYAN}Starting 3-Larry Dashboard...{Colors.NC}")
        print(f"{Colors.CYAN}Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...{Colors.NC}")

        try:
            while True:
                self.render_dashboard()
                time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            print(f"\n\n{Colors.CYAN}Dashboard stopped.{Colors.NC}")
            sys.exit(0)

def main():
    dashboard = LarryDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
