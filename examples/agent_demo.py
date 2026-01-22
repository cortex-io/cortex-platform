#!/usr/bin/env python3
"""
Cortex Agent Framework Demo

Demonstrates the agent framework with a simple example:
1. Start coordinator master
2. Coordinator spawns a security master
3. Security master spawns a Sandfly worker
4. Send a task through the chain: coordinator → security → sandfly → Claude

This is a proof-of-concept showing the full agent lifecycle.
"""

import asyncio
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.messaging import MessageBroker, AgentMessage, MessagePriority
from agents.registry import AgentRegistry
from masters.coordinator_master import CoordinatorMaster


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


async def demo():
    """Run the agent framework demo."""
    logger.info("=" * 80)
    logger.info("Cortex Agent Framework Demo")
    logger.info("=" * 80)

    # Configuration
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    if not anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set!")
        logger.info("Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        return

    # Step 1: Start coordinator master
    logger.info("\n[Step 1] Starting Coordinator Master...")
    coordinator = CoordinatorMaster(redis_url=redis_url)
    await coordinator.start()
    logger.info("✓ Coordinator master ready")

    await asyncio.sleep(2)  # Let it initialize

    # Step 2: Spawn security division
    logger.info("\n[Step 2] Spawning Security Division...")
    success = await coordinator.spawn_security_division()
    if success:
        logger.info("✓ Security master spawned")
    else:
        logger.error("✗ Failed to spawn security master")
        await coordinator.stop()
        return

    await asyncio.sleep(3)  # Let security master initialize

    # Step 3: Check registry
    logger.info("\n[Step 3] Checking Agent Registry...")
    registry = AgentRegistry(redis_url=redis_url)
    await registry.connect()

    agents = await registry.list_agents()
    logger.info(f"Found {len(agents)} registered agents:")
    for agent in agents:
        logger.info(f"  - {agent.name} ({agent.agent_id}): {agent.status.value}")

    await registry.disconnect()

    # Step 4: Send a task to coordinator
    logger.info("\n[Step 4] Sending security task to coordinator...")

    broker = MessageBroker(redis_url=redis_url)
    await broker.connect()

    task_message = AgentMessage(
        stream="agent:tasks:coordinator-master",
        sender="demo-client",
        recipient="coordinator-master",
        task_type="scan_host",
        payload={
            "host_id": "web-server-01",
            "severity": "all",
        },
        priority=MessagePriority.NORMAL,
    )

    message_id = await broker.publish(task_message)
    logger.info(f"✓ Task published: {message_id}")

    # Step 5: Wait for processing
    logger.info("\n[Step 5] Waiting for task processing...")
    logger.info("(In production, this would be handled asynchronously)")
    await asyncio.sleep(10)

    # Step 6: Check for results (simplified - in real system would listen on result stream)
    logger.info("\n[Step 6] Task processing complete")
    logger.info("Check the agent logs to see the full conversation flow:")
    logger.info("  coordinator-master → security-master → sandfly-worker → Claude API")

    await broker.disconnect()

    # Cleanup
    logger.info("\n[Cleanup] Stopping all agents...")
    await coordinator.stop()

    logger.info("\n" + "=" * 80)
    logger.info("Demo Complete!")
    logger.info("=" * 80)
    logger.info("\nKey takeaways:")
    logger.info("1. Masters route tasks to workers")
    logger.info("2. Workers use Claude API to accomplish tasks")
    logger.info("3. Redis Streams handles all messaging")
    logger.info("4. Registry tracks all agents with heartbeats")
    logger.info("5. Lifecycle manager spawns/terminates agents")
    logger.info("\nNext steps:")
    logger.info("- Check ~/cortex-platform/agents/README.md for full documentation")
    logger.info("- Run tests: pytest tests/agents/ -v")
    logger.info("- Build your own agents by extending BaseMaster/BaseWorker")


async def main():
    """Main entry point."""
    try:
        await demo()
    except KeyboardInterrupt:
        logger.info("\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
