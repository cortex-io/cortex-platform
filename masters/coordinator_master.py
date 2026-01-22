"""
Coordinator Master - Top-level routing and orchestration.

This master receives tasks and routes them to appropriate division masters
or workers based on task type and system load.
"""

import logging
from typing import List, Optional

from agents.base_master import BaseMaster
from agents.messaging import AgentMessage


logger = logging.getLogger(__name__)


class CoordinatorMaster(BaseMaster):
    """
    Top-level coordinator master.

    Responsibilities:
    - Route incoming requests to appropriate division masters
    - Load balancing across divisions
    - High-level task orchestration
    - System health monitoring
    """

    def __init__(self, **kwargs):
        super().__init__(
            agent_id="coordinator-master",
            name="Cortex Coordinator",
            **kwargs
        )

    def get_capabilities(self) -> List[str]:
        """Coordinator can handle any task type and route appropriately."""
        return [
            "task_routing",
            "load_balancing",
            "orchestration",
            "system_monitoring",
        ]

    async def route_task(self, message: AgentMessage) -> Optional[str]:
        """
        Route task to appropriate worker or division master.

        Routing logic:
        - Security tasks → security-master or security workers
        - Infrastructure tasks → infrastructure workers
        - Unknown tasks → log warning and handle directly
        """
        task_type = message.task_type
        logger.info(f"Routing task: {task_type}")

        # Security-related tasks
        if any(keyword in task_type.lower() for keyword in ["security", "threat", "vulnerability", "sandfly"]):
            # Try to find security master first
            security_master = await self.registry.get_agent("security-master")
            if security_master:
                return security_master.agent_id

            # Fall back to finding a security worker
            worker_id = await self.find_available_worker("security_operations")
            if worker_id:
                return worker_id

            logger.warning(f"No security agents available for task: {task_type}")
            return None

        # GitHub-related tasks
        if "github" in task_type.lower():
            worker_id = await self.find_available_worker("github_security")
            if worker_id:
                return worker_id

        # Default: try to find any available worker
        logger.warning(f"No specific routing for task type: {task_type}")
        return None

    async def process_result(self, message: AgentMessage) -> None:
        """
        Process results from workers or division masters.

        Aggregates results and may forward to original requester.
        """
        logger.info(f"Received result from {message.sender}")

        result = message.payload.get("result", {})
        success = message.payload.get("success", False)
        original_sender = message.metadata.get("original_sender")

        if success:
            logger.info(f"Task completed successfully: {message.payload.get('original_task')}")
        else:
            logger.error(f"Task failed: {result.get('error')}")

        # If there was an original sender (external system), forward result
        if original_sender and original_sender != self.agent_id:
            try:
                await self.send_message(
                    recipient=original_sender,
                    task_type=f"{message.payload.get('original_task')}_complete",
                    payload=message.payload,
                )
            except Exception as e:
                logger.error(f"Failed to forward result to {original_sender}: {e}")

    async def spawn_security_division(self) -> bool:
        """
        Spawn the security division: security master + workers.

        Returns:
            True if spawn succeeded
        """
        logger.info("Spawning security division")

        # Spawn security master
        success = await self.spawn_worker(
            worker_id="security-master",
            worker_class="masters.security_master",
            capabilities=["security_operations", "threat_management"],
        )

        if not success:
            logger.error("Failed to spawn security master")
            return False

        logger.info("Security division spawned successfully")
        return True

    async def spawn_sandfly_worker(self) -> bool:
        """
        Spawn a Sandfly security worker.

        Returns:
            True if spawn succeeded
        """
        logger.info("Spawning Sandfly worker")

        success = await self.spawn_worker(
            worker_id="sandfly-worker-001",
            worker_class="workers.sandfly_worker",
            capabilities=["sandfly_api", "threat_analysis"],
            env_vars={
                "SANDFLY_API_URL": "http://sandfly-api.cortex-security.svc.cluster.local",
            },
        )

        if not success:
            logger.error("Failed to spawn Sandfly worker")
            return False

        logger.info("Sandfly worker spawned successfully")
        return True


async def main():
    """Run coordinator master."""
    import os
    import signal

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Get config from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Create and start coordinator
    coordinator = CoordinatorMaster(redis_url=redis_url)

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        import asyncio
        asyncio.create_task(coordinator.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start coordinator
    await coordinator.start()

    # Keep running
    try:
        while coordinator._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await coordinator.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
