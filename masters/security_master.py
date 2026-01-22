"""
Security Master - Division GM for security operations.

Manages security workers (Sandfly, GitHub Security, etc.) and coordinates
threat detection, vulnerability scanning, and incident response.
"""

import logging
from typing import Dict, List, Optional

from agents.base_master import BaseMaster
from agents.messaging import AgentMessage, MessagePriority


logger = logging.getLogger(__name__)


class SecurityMaster(BaseMaster):
    """
    Security division master.

    Responsibilities:
    - Manage security workers (Sandfly, GitHub Security, etc.)
    - Coordinate threat detection workflows
    - Aggregate security findings
    - Escalate critical threats
    """

    def __init__(self, **kwargs):
        super().__init__(
            agent_id="security-master",
            name="Security Division GM",
            **kwargs
        )
        self._active_scans: Dict[str, str] = {}  # scan_id -> worker_id

    def get_capabilities(self) -> List[str]:
        """Security master capabilities."""
        return [
            "security_operations",
            "threat_management",
            "vulnerability_scanning",
            "incident_coordination",
        ]

    async def route_task(self, message: AgentMessage) -> Optional[str]:
        """
        Route security tasks to appropriate security workers.

        Task types:
        - scan_host → Sandfly worker
        - analyze_threat → Sandfly worker
        - scan_repository → GitHub Security worker
        - check_vulnerabilities → GitHub Security worker
        """
        task_type = message.task_type
        logger.info(f"Routing security task: {task_type}")

        # Sandfly tasks
        if task_type in ["scan_host", "analyze_threat", "list_findings"]:
            worker_id = await self.find_available_worker("sandfly_api")
            if worker_id:
                # Track active scan
                scan_id = message.payload.get("scan_id", f"scan-{message.message_id}")
                self._active_scans[scan_id] = worker_id
                return worker_id

            logger.warning("No Sandfly workers available, spawning one")
            await self._spawn_sandfly_worker()
            return None

        # GitHub Security tasks
        if task_type in ["scan_repository", "check_vulnerabilities", "list_alerts"]:
            worker_id = await self.find_available_worker("github_security")
            if worker_id:
                return worker_id

            logger.warning("No GitHub Security workers available")
            return None

        logger.warning(f"Unknown security task type: {task_type}")
        return None

    async def process_result(self, message: AgentMessage) -> None:
        """
        Process results from security workers.

        Analyzes findings and escalates critical threats to coordinator.
        """
        logger.info(f"Received security result from {message.sender}")

        result = message.payload.get("result", {})
        success = message.payload.get("success", False)
        original_task = message.payload.get("original_task")

        if not success:
            logger.error(f"Security task failed: {result.get('error')}")
            return

        # Process based on task type
        if original_task == "scan_host":
            await self._process_scan_result(message, result)
        elif original_task == "analyze_threat":
            await self._process_threat_analysis(message, result)
        elif original_task == "scan_repository":
            await self._process_repo_scan(message, result)

        # Forward result to original requester if needed
        original_sender = message.metadata.get("original_sender")
        if original_sender and original_sender != self.agent_id:
            try:
                await self.send_message(
                    recipient=original_sender,
                    task_type=f"{original_task}_complete",
                    payload=message.payload,
                )
            except Exception as e:
                logger.error(f"Failed to forward result to {original_sender}: {e}")

    async def _process_scan_result(self, message: AgentMessage, result: Dict) -> None:
        """Process host scan results from Sandfly."""
        findings = result.get("findings", [])
        critical_count = sum(1 for f in findings if f.get("severity") == "critical")

        logger.info(f"Scan complete: {len(findings)} findings, {critical_count} critical")

        # Escalate if critical findings
        if critical_count > 0:
            await self._escalate_critical_findings(findings)

    async def _process_threat_analysis(self, message: AgentMessage, result: Dict) -> None:
        """Process threat analysis results."""
        threat_level = result.get("threat_level", "unknown")
        recommendations = result.get("recommendations", [])

        logger.info(f"Threat analysis complete: level={threat_level}, {len(recommendations)} recommendations")

        if threat_level in ["high", "critical"]:
            await self._escalate_threat(result)

    async def _process_repo_scan(self, message: AgentMessage, result: Dict) -> None:
        """Process repository scan results from GitHub Security."""
        vulnerabilities = result.get("vulnerabilities", [])
        high_severity = sum(1 for v in vulnerabilities if v.get("severity") in ["high", "critical"])

        logger.info(f"Repository scan complete: {len(vulnerabilities)} vulnerabilities, {high_severity} high/critical")

    async def _escalate_critical_findings(self, findings: List[Dict]) -> None:
        """Escalate critical findings to coordinator."""
        critical_findings = [f for f in findings if f.get("severity") == "critical"]

        logger.warning(f"Escalating {len(critical_findings)} critical findings to coordinator")

        try:
            # Send to coordinator master
            await self.send_message(
                recipient="coordinator-master",
                task_type="security_alert",
                payload={
                    "alert_type": "critical_findings",
                    "findings": critical_findings,
                    "source": "sandfly",
                },
                priority=MessagePriority.CRITICAL,
            )
        except Exception as e:
            logger.error(f"Failed to escalate to coordinator: {e}")

    async def _escalate_threat(self, threat_data: Dict) -> None:
        """Escalate high-level threat to coordinator."""
        logger.warning(f"Escalating threat: {threat_data.get('threat_level')}")

        try:
            await self.send_message(
                recipient="coordinator-master",
                task_type="security_alert",
                payload={
                    "alert_type": "high_threat",
                    "threat_data": threat_data,
                },
                priority=MessagePriority.HIGH,
            )
        except Exception as e:
            logger.error(f"Failed to escalate threat: {e}")

    async def _spawn_sandfly_worker(self) -> bool:
        """Spawn a Sandfly worker on demand."""
        import random
        worker_num = random.randint(100, 999)
        worker_id = f"sandfly-worker-{worker_num}"

        return await self.spawn_worker(
            worker_id=worker_id,
            worker_class="workers.sandfly_worker",
            capabilities=["sandfly_api", "threat_analysis"],
            env_vars={
                "SANDFLY_API_URL": "http://sandfly-api.cortex-security.svc.cluster.local",
            },
        )

    async def start(self) -> None:
        """Start security master and spawn initial workers."""
        await super().start()

        # Spawn one Sandfly worker on startup
        logger.info("Spawning initial Sandfly worker")
        await self._spawn_sandfly_worker()


async def main():
    """Run security master."""
    import os
    import signal

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Get config from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Create and start security master
    security_master = SecurityMaster(redis_url=redis_url)

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        import asyncio
        asyncio.create_task(security_master.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start master
    await security_master.start()

    # Keep running
    try:
        while security_master._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await security_master.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
