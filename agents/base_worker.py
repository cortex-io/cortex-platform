"""
Base class for Worker agents.

Workers execute tasks using Claude API conversations:
- Receive tasks from masters
- Converse with Claude using Anthropic SDK
- Use MCP tools as needed
- Send results back to masters

This is where the AI magic happens - workers are the ones that actually
talk to Claude to accomplish tasks.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from agents.messaging import AgentMessage, MessageBroker, MessagePriority
from agents.registry import AgentInfo, AgentRegistry, AgentStatus, AgentType


logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """
    Base class for all Worker agents.

    Responsibilities:
    - Execute tasks via Claude API conversations
    - Use MCP tools for specialized operations
    - Report results back to masters
    - Manage conversation context

    Subclasses must implement:
    - process_task(): Handle task-specific logic
    - get_capabilities(): Define worker's capabilities
    - get_system_prompt(): Provide Claude system prompt
    - get_mcp_tools(): Optional MCP tools configuration
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        master_id: str,
        redis_url: str = "redis://localhost:6379",
        anthropic_api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 8192,
        heartbeat_interval: int = 30,
    ):
        """
        Initialize Worker agent.

        Args:
            agent_id: Unique agent identifier
            name: Human-readable name
            master_id: ID of master agent that spawned this worker
            redis_url: Redis connection URL
            anthropic_api_key: Anthropic API key (or use ANTHROPIC_API_KEY env var)
            model: Claude model to use
            max_tokens: Maximum tokens per response
            heartbeat_interval: Seconds between heartbeats
        """
        self.agent_id = agent_id
        self.name = name
        self.master_id = master_id
        self.redis_url = redis_url
        self.model = model
        self.max_tokens = max_tokens
        self.heartbeat_interval = heartbeat_interval

        # Core components
        self.broker = MessageBroker(redis_url=redis_url)
        self.registry = AgentRegistry(redis_url=redis_url)
        self.claude = AsyncAnthropic(api_key=anthropic_api_key)

        # Worker's task stream
        self.task_stream = f"agent:tasks:{self.agent_id}"
        self.consumer_group = f"{self.agent_id}-group"
        self.consumer_name = f"{self.agent_id}-consumer"

        # Conversation context
        self._conversation_history: List[Dict[str, Any]] = []

        # State tracking
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._consume_task: Optional[asyncio.Task] = None

    @abstractmethod
    async def process_task(self, message: AgentMessage) -> Dict[str, Any]:
        """
        Process a task using Claude API.

        This is the core method where workers interact with Claude
        to accomplish their tasks.

        Args:
            message: Task message from master

        Returns:
            Result dictionary to send back to master
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities this worker provides.

        Returns:
            List of capability strings (e.g., ["sandfly_api", "threat_analysis"])
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get system prompt for Claude conversations.

        Returns:
            System prompt string defining worker's role and capabilities
        """
        pass

    def get_mcp_tools(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get MCP tools configuration for this worker.

        Override in subclass if worker uses MCP tools.

        Returns:
            List of MCP tool configurations, or None
        """
        return None

    async def start(self) -> None:
        """Start the worker agent."""
        logger.info(f"Starting worker agent: {self.name} ({self.agent_id})")

        # Connect to infrastructure
        await self.broker.connect()
        await self.registry.connect()

        # Register in registry
        agent_info = AgentInfo(
            agent_id=self.agent_id,
            agent_type=AgentType.WORKER,
            name=self.name,
            status=AgentStatus.STARTING,
            capabilities=self.get_capabilities(),
            stream=self.task_stream,
            metadata={"master_id": self.master_id},
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

        # Mark as ready
        await self.registry.update_status(self.agent_id, AgentStatus.READY)
        logger.info(f"Worker agent {self.name} is ready")

    async def stop(self) -> None:
        """Stop the worker agent."""
        logger.info(f"Stopping worker agent: {self.name}")
        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._consume_task:
            self._consume_task.cancel()

        # Wait for tasks to complete
        tasks = [t for t in [self._heartbeat_task, self._consume_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Update status and deregister
        await self.registry.update_status(self.agent_id, AgentStatus.STOPPED)
        await self.registry.deregister(self.agent_id)

        # Disconnect
        await self.broker.disconnect()
        await self.registry.disconnect()

        logger.info(f"Worker agent {self.name} stopped")

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
                count=1,  # Process one task at a time
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

        Processes via subclass implementation and sends result back.
        """
        logger.info(f"Received task: {message.task_type} from {message.sender}")

        await self.registry.update_status(self.agent_id, AgentStatus.BUSY)

        try:
            # Process task (subclass responsibility)
            result = await self.process_task(message)

            # Send result back to master
            await self._send_result(message, result, success=True)

        except Exception as e:
            logger.error(f"Task processing failed: {e}")
            await self._send_result(
                message,
                {"error": str(e)},
                success=False,
            )

        finally:
            await self.registry.update_status(self.agent_id, AgentStatus.READY)
            await self.registry.increment_task_count(self.agent_id)

    async def _send_result(
        self,
        original_message: AgentMessage,
        result: Dict[str, Any],
        success: bool,
    ) -> None:
        """
        Send result back to master.

        Args:
            original_message: Original task message
            result: Result data
            success: Whether task succeeded
        """
        # Get master info
        master_info = await self.registry.get_agent(self.master_id)
        if not master_info:
            logger.error(f"Master {self.master_id} not found in registry")
            return

        # Create result message
        result_message = AgentMessage(
            stream=master_info.stream,
            sender=self.agent_id,
            recipient=self.master_id,
            task_type=f"{original_message.task_type}_result",
            payload={
                "success": success,
                "result": result,
                "original_task": original_message.task_type,
                "original_payload": original_message.payload,
            },
            priority=original_message.priority,
            metadata={
                "original_message_id": original_message.message_id,
                "original_sender": original_message.metadata.get("original_sender", original_message.sender),
            },
        )

        await self.broker.publish(result_message)
        logger.info(f"Sent result to master {self.master_id}")

    async def ask_claude(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send a message to Claude and get a response.

        Args:
            user_message: Message to send to Claude
            system_prompt: Override default system prompt
            tools: Optional tool definitions for Claude
            max_tokens: Override default max_tokens

        Returns:
            Claude's response text
        """
        # Build messages list
        messages = self._conversation_history + [
            {"role": "user", "content": user_message}
        ]

        # Use provided system prompt or default
        system = system_prompt or self.get_system_prompt()

        # Prepare API call
        api_params = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system,
            "messages": messages,
        }

        if tools:
            api_params["tools"] = tools

        # Call Claude API
        logger.debug(f"Calling Claude API with {len(messages)} messages")
        response = await self.claude.messages.create(**api_params)

        # Extract response text
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        # Update conversation history
        self._conversation_history.append({"role": "user", "content": user_message})
        self._conversation_history.append({"role": "assistant", "content": response_text})

        logger.debug(f"Claude response: {len(response_text)} characters")
        return response_text

    async def ask_claude_with_tools(
        self,
        user_message: str,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Have a conversation with Claude that may involve tool use.

        Handles the agentic loop: message -> tool use -> tool result -> repeat

        Args:
            user_message: Initial message to Claude
            max_iterations: Maximum tool use iterations

        Returns:
            Dictionary with final response and tool calls made
        """
        messages = self._conversation_history + [
            {"role": "user", "content": user_message}
        ]

        tools = self.get_mcp_tools()
        tool_calls = []
        iterations = 0

        while iterations < max_iterations:
            # Call Claude
            response = await self.claude.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.get_system_prompt(),
                messages=messages,
                tools=tools if tools else None,
            )

            # Check if Claude wants to use a tool
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No more tool use, we're done
                response_text = ""
                for block in response.content:
                    if block.type == "text":
                        response_text += block.text

                # Update conversation history
                self._conversation_history = messages + [
                    {"role": "assistant", "content": response.content}
                ]

                return {
                    "response": response_text,
                    "tool_calls": tool_calls,
                    "iterations": iterations,
                }

            # Process tool calls
            messages.append({"role": "assistant", "content": response.content})

            for tool_block in tool_use_blocks:
                tool_name = tool_block.name
                tool_input = tool_block.input

                logger.info(f"Claude requesting tool: {tool_name}")
                tool_calls.append({"name": tool_name, "input": tool_input})

                # Execute tool (subclass responsibility via process_tool_call)
                try:
                    tool_result = await self.process_tool_call(tool_name, tool_input)
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    tool_result = {"error": str(e)}

                # Add tool result to messages
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": str(tool_result),
                    }]
                })

            iterations += 1

        # Max iterations reached
        logger.warning(f"Max tool use iterations ({max_iterations}) reached")
        self._conversation_history = messages

        return {
            "response": "Max iterations reached",
            "tool_calls": tool_calls,
            "iterations": iterations,
            "truncated": True,
        }

    async def process_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Process an MCP tool call from Claude.

        Override in subclass to handle tool execution.

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        raise NotImplementedError("Subclass must implement process_tool_call if using tools")

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self._conversation_history = []
        logger.debug("Cleared conversation history")

    def get_conversation_length(self) -> int:
        """Get number of messages in conversation history."""
        return len(self._conversation_history)
