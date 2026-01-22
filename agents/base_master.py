"""
Base class for Master agents.

Masters orchestrate workers:
- Route tasks to appropriate workers
- Spawn workers as needed
- Monitor worker health
- Aggregate results

Masters do NOT converse with Claude API - that's the workers' job.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from agents.lifecycle import AgentLifecycle, SpawnMode
from agents.messaging import AgentMessage, MessageBroker, MessagePriority
from agents.registry import AgentInfo, AgentRegistry, AgentStatus, AgentType


logger = logging.getLogger(__name__)


class BaseMaster(ABC):
    """
    Base class for all Master agents.

    Responsibilities:
    - Task routing and delegation
    - Worker lifecycle management
    - Result aggregation
    - Health monitoring

    Subclasses must implement:
    - route_task(): Determine which worker should handle a task
    - process_result(): Handle results from workers
    - get_capabilities(): Define master's capabilities
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        redis_url: str = "redis://localhost:6379",
        spawn_mode: SpawnMode = SpawnMode.SUBPROCESS,
        namespace: str = "cortex-system",
        heartbeat_interval: int = 30,
    ):
        """
        Initialize Master agent.

        Args:
            agent_id: Unique agent identifier
            name: Human-readable name
            redis_url: Redis connection URL
            spawn_mode: How to spawn workers
            namespace: Kubernetes namespace (for K8s mode)
            heartbeat_interval: Seconds between heartbeats
        """
        self.agent_id = agent_id
        self.name = name
        self.redis_url = redis_url
        self.spawn_mode = spawn_mode
        self.namespace = namespace
        self.heartbeat_interval = heartbeat_interval

        # Core components
        self.broker = MessageBroker(redis_url=redis_url)
        self.registry = AgentRegistry(redis_url=redis_url)
        self.lifecycle = AgentLifecycle(spawn_mode=spawn_mode, namespace=namespace)

        # Master's task stream
        self.task_stream = f"agent:tasks:{self.agent_id}"
        self.consumer_group = f"{self.agent_id}-group"
        self.consumer_name = f"{self.agent_id}-consumer"

        # State tracking
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._consume_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

    @abstractmethod
    async def route_task(self, message: AgentMessage) -> Optional[str]:
        """
        Determine which worker should handle this task.

        Args:
            message: Incoming task message

        Returns:
            Worker agent_id if a worker should handle this,
            None if master should handle directly
        """
        pass

    @abstractmethod
    async def process_result(self, message: AgentMessage) -> None:
        """
        Process result from a worker.

        Args:
            message: Result message from worker
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities this master provides.

        Returns:
            List of capability strings
        """
        pass

    async def start(self) -> None:
        """Start the master agent."""
        logger.info(f"Starting master agent: {self.name} ({self.agent_id})")

        # Connect to infrastructure
        await self.broker.connect()
        await self.registry.connect()

        # Register in registry
        agent_info = AgentInfo(
            agent_id=self.agent_id,
            agent_type=AgentType.MASTER,
            name=self.name,
            status=AgentStatus.STARTING,
            capabilities=self.get_capabilities(),
            stream=self.task_stream,
        )
        await self.registry.register(agent_info)

        # Create consumer group for task stream
        await self.broker.create_consumer_group(
            self.task_stream, self.consumer_group, start_id="$"
        )

        # Start background tasks
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._consume_task = asyncio.create_task(self._consume_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        # Mark as ready
        await self.registry.update_status(self.agent_id, AgentStatus.READY)
        logger.info(f"Master agent {self.name} is ready")

    async def stop(self) -> None:
        """Stop the master agent."""
        logger.info(f"Stopping master agent: {self.name}")
        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._consume_task:
            self._consume_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()

        # Wait for tasks to complete
        tasks = [t for t in [self._heartbeat_task, self._consume_task, self._monitor_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Cleanup workers
        await self.lifecycle.cleanup_all()

        # Update status and deregister
        await self.registry.update_status(self.agent_id, AgentStatus.STOPPED)
        await self.registry.deregister(self.agent_id)

        # Disconnect
        await self.broker.disconnect()
        await self.registry.disconnect()

        logger.info(f"Master agent {self.name} stopped")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to registry."""
        while self._running:
            try:
                await self.registry.heartbeat(self.agent_id)
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _consume_loop(self) -> None:
        """Consume and process tasks from stream."""
        logger.info(f"Starting task consumer for {self.task_stream}")

        try:
            async for message in self.broker.consume(
                self.task_stream,
                self.consumer_group,
                self.consumer_name,
                count=10,
                auto_ack=False,
            ):
                try:
                    await self._handle_task(message)
                    # Acknowledge after successful processing
                    await self.broker.ack(self.task_stream, self.consumer_group, message.message_id)
                except Exception as e:
                    logger.error(f"Error handling task {message.message_id}: {e}")
                    # Don't ack - let it retry

        except asyncio.CancelledError:
            logger.info("Task consumer cancelled")

    async def _handle_task(self, message: AgentMessage) -> None:
        """
        Handle an incoming task message.

        Routes to worker or processes directly.
        """
        logger.info(f"Received task: {message.task_type} from {message.sender}")

        await self.registry.update_status(self.agent_id, AgentStatus.BUSY)

        try:
            # Check if this is a result from a worker
            if message.task_type.endswith("_result"):
                await self.process_result(message)
                return

            # Route to worker or handle directly
            worker_id = await self.route_task(message)

            if worker_id:
                # Forward to worker
                await self._delegate_to_worker(worker_id, message)
            else:
                # Handle directly (subclass responsibility)
                await self._handle_task_directly(message)

        finally:
            await self.registry.update_status(self.agent_id, AgentStatus.READY)
            await self.registry.increment_task_count(self.agent_id)

    async def _delegate_to_worker(self, worker_id: str, message: AgentMessage) -> None:
        """
        Delegate task to a specific worker.

        Args:
            worker_id: Target worker agent ID
            message: Task message to forward
        """
        # Get worker info
        worker_info = await self.registry.get_agent(worker_id)
        if not worker_info:
            logger.error(f"Worker {worker_id} not found in registry")
            return

        # Forward message to worker's stream
        forwarded_message = AgentMessage(
            stream=worker_info.stream,
            sender=self.agent_id,
            recipient=worker_id,
            task_type=message.task_type,
            payload=message.payload,
            priority=message.priority,
            metadata={
                **message.metadata,
                "original_sender": message.sender,
                "routed_by": self.agent_id,
            },
        )

        await self.broker.publish(forwarded_message)
        logger.info(f"Delegated task to worker {worker_id}")

    async def _handle_task_directly(self, message: AgentMessage) -> None:
        """
        Handle task directly (master processes without delegating).

        Default implementation logs a warning. Override in subclass if needed.
        """
        logger.warning(f"No worker found for task {message.task_type}, and direct handling not implemented")

    async def _monitor_loop(self) -> None:
        """Monitor worker health and spawn/terminate as needed."""
        while self._running:
            try:
                # Check worker health
                health_status = await self.lifecycle.monitor_workers()

                for agent_id, is_alive in health_status.items():
                    if not is_alive:
                        logger.warning(f"Worker {agent_id} is dead, cleaning up")
                        await self.registry.deregister(agent_id)

                # Cleanup stale agents in registry
                await self.registry.cleanup_stale_agents()

                # Wait before next check
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(30)

    async def spawn_worker(
        self,
        worker_id: str,
        worker_class: str,
        capabilities: List[str],
        env_vars: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Spawn a new worker agent.

        Args:
            worker_id: Unique worker ID
            worker_class: Python module path for worker
            capabilities: Worker capabilities
            env_vars: Environment variables to pass

        Returns:
            True if spawn succeeded
        """
        logger.info(f"Spawning worker: {worker_id} ({worker_class})")

        # Add Redis URL to env vars
        env_vars = env_vars or {}
        env_vars["REDIS_URL"] = self.redis_url

        # Spawn via lifecycle manager
        success = await self.lifecycle.spawn_worker(
            agent_id=worker_id,
            worker_class=worker_class,
            env_vars=env_vars,
        )

        if success:
            logger.info(f"Successfully spawned worker {worker_id}")
        else:
            logger.error(f"Failed to spawn worker {worker_id}")

        return success

    async def find_available_worker(self, capability: str) -> Optional[str]:
        """
        Find an available worker with the specified capability.

        Args:
            capability: Required capability

        Returns:
            Worker agent_id if found, None otherwise
        """
        workers = await self.registry.find_workers_by_capability(capability)

        # Filter by status
        available = [
            w for w in workers
            if w.status in (AgentStatus.READY, AgentStatus.IDLE)
        ]

        if available:
            # Return worker with lowest task count
            worker = min(available, key=lambda w: w.task_count)
            return worker.agent_id

        return None

    async def send_message(
        self,
        recipient: str,
        task_type: str,
        payload: Dict,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """
        Send a message to another agent.

        Args:
            recipient: Target agent ID
            task_type: Type of task
            payload: Task data
            priority: Message priority

        Returns:
            Message ID
        """
        # Get recipient info to determine stream
        recipient_info = await self.registry.get_agent(recipient)
        if not recipient_info:
            raise ValueError(f"Recipient agent {recipient} not found")

        message = AgentMessage(
            stream=recipient_info.stream,
            sender=self.agent_id,
            recipient=recipient,
            task_type=task_type,
            payload=payload,
            priority=priority,
        )

        message_id = await self.broker.publish(message)
        logger.info(f"Sent message {message_id} to {recipient}")
        return message_id
