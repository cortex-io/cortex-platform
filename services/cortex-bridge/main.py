#!/usr/bin/env python3
"""
Cortex Bridge - Local agent connecting Claude Desktop/Code to Cortex Fabric

This lightweight service runs on your Mac and:
1. Provides MCP server interface for Claude Desktop
2. Maintains persistent WebSocket connection to Fabric Gateway
3. Watches local cortex-platform for file changes
4. Manages session lifecycle automatically
5. Handles reconnection and offline resilience

Usage:
    python main.py                    # Start bridge (default: fabric.ry-ops.dev)
    python main.py --local            # Use local port-forward instead
    python main.py --fabric-url ws://custom-url
"""
import os
import sys
import json
import asyncio
import logging
import signal
import argparse
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import uuid

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    print("Missing websockets library. Install with: pip install websockets")
    sys.exit(1)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    print("Warning: watchdog not installed. File watching disabled.")
    print("Install with: pip install watchdog")

# Configuration
DEFAULT_FABRIC_URL = os.getenv('FABRIC_URL', 'wss://fabric.ry-ops.dev/ws/fabric')
LOCAL_FABRIC_URL = 'ws://localhost:8080/ws/fabric'
CORTEX_PLATFORM_PATH = os.getenv('CORTEX_PLATFORM_PATH', os.path.expanduser('~/Projects/cortex-platform'))
CLIENT_TYPE = os.getenv('CLIENT_TYPE', 'bridge')
RECONNECT_DELAY = int(os.getenv('RECONNECT_DELAY', '5'))
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '25'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
MCP_STDIO_MODE = os.getenv('MCP_STDIO_MODE', 'false').lower() == 'true'

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cortex-bridge')


class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events and queues them for the bridge."""

    def __init__(self, bridge: 'CortexBridge'):
        self.bridge = bridge
        self._debounce_tasks: Dict[str, asyncio.Task] = {}

    def _get_relative_path(self, path: str) -> str:
        try:
            return str(Path(path).relative_to(CORTEX_PLATFORM_PATH))
        except ValueError:
            return path

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        ignore_patterns = [
            '.git', '__pycache__', '.pyc', '.DS_Store',
            'node_modules', '.env', '.venv', 'venv',
            'coordination/knowledge-base/embeddings',
            'library/', '.idea', '.vscode'
        ]
        return any(pattern in path for pattern in ignore_patterns)

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return

        # Queue the event with debouncing
        asyncio.run_coroutine_threadsafe(
            self._debounced_notify(event),
            self.bridge.loop
        )

    async def _debounced_notify(self, event: FileSystemEvent):
        """Debounce file events to avoid flooding."""
        path = event.src_path

        # Cancel existing debounce for this path
        if path in self._debounce_tasks:
            self._debounce_tasks[path].cancel()

        async def delayed_notify():
            await asyncio.sleep(0.5)  # 500ms debounce
            await self.bridge.notify_file_change(
                event_type=event.event_type,
                path=self._get_relative_path(path)
            )
            self._debounce_tasks.pop(path, None)

        self._debounce_tasks[path] = asyncio.create_task(delayed_notify())


class CortexBridge:
    """
    Main bridge class connecting local environment to Cortex Fabric.
    """

    def __init__(self, fabric_url: str):
        self.fabric_url = fabric_url
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.client_id: Optional[str] = None
        self.connected = False
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # Request tracking
        self._pending_requests: Dict[str, asyncio.Future] = {}

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}

        # File watcher
        self._observer: Optional[Observer] = None

        # MCP stdio mode
        self._mcp_input_task: Optional[asyncio.Task] = None

        # Reconnection state
        self._reconnect_attempt = 0
        self._max_reconnect_attempts = 10

    async def start(self):
        """Start the bridge."""
        self.running = True
        self.loop = asyncio.get_event_loop()

        # Start file watcher
        if HAS_WATCHDOG and os.path.exists(CORTEX_PLATFORM_PATH):
            self._start_file_watcher()

        # Connect to fabric
        await self._connect_loop()

    async def stop(self):
        """Stop the bridge gracefully."""
        self.running = False

        # Stop file watcher
        if self._observer:
            self._observer.stop()
            self._observer.join()

        # End session if active
        if self.session_id and self.connected:
            try:
                await self.end_session("Bridge stopped")
            except Exception:
                pass

        # Close websocket
        if self.websocket:
            await self.websocket.close()

        logger.info("Bridge stopped")

    def _start_file_watcher(self):
        """Start watching cortex-platform for changes."""
        handler = FileChangeHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, CORTEX_PLATFORM_PATH, recursive=True)
        self._observer.start()
        logger.info(f"Watching for file changes in {CORTEX_PLATFORM_PATH}")

    async def _connect_loop(self):
        """Main connection loop with automatic reconnection."""
        while self.running:
            try:
                await self._connect()
                self._reconnect_attempt = 0
                await self._message_loop()
            except websockets.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}")
            except Exception as e:
                logger.error(f"Connection error: {e}")

            if not self.running:
                break

            # Reconnection logic
            self._reconnect_attempt += 1
            if self._reconnect_attempt > self._max_reconnect_attempts:
                logger.error("Max reconnection attempts reached")
                break

            delay = min(RECONNECT_DELAY * (2 ** (self._reconnect_attempt - 1)), 60)
            logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempt})")
            await asyncio.sleep(delay)

    async def _connect(self):
        """Establish connection to Fabric Gateway."""
        logger.info(f"Connecting to {self.fabric_url}")

        self.websocket = await websockets.connect(
            f"{self.fabric_url}?client_type={CLIENT_TYPE}",
            ping_interval=HEARTBEAT_INTERVAL,
            ping_timeout=10,
        )

        # Wait for connected message
        response = await self.websocket.recv()
        data = json.loads(response)

        if data.get('type') == 'connected':
            self.client_id = data.get('client_id')
            self.connected = True
            logger.info(f"Connected to Fabric Gateway (client_id: {self.client_id})")
            logger.info(f"Available MCP servers: {data.get('mcp_servers', [])}")

            # Auto-start session
            await self.start_session()
        else:
            raise Exception(f"Unexpected response: {data}")

    async def _message_loop(self):
        """Main message receiving loop."""
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            async for message in self.websocket:
                await self._handle_message(message)
        finally:
            heartbeat_task.cancel()
            self.connected = False

    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.connected:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await self._send({
                    'type': 'heartbeat',
                    'timestamp': datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                break

    async def _handle_message(self, raw_message: str):
        """Handle incoming message from Fabric Gateway."""
        try:
            message = json.loads(raw_message)
            msg_type = message.get('type')
            request_id = message.get('request_id')

            # Handle request responses
            if request_id and request_id in self._pending_requests:
                self._pending_requests[request_id].set_result(message)
                return

            # Handle event broadcasts
            if msg_type == 'event_broadcast':
                event_name = message.get('event')
                event_data = message.get('data', {})
                await self._dispatch_event(event_name, event_data)
                return

            # Handle state updates
            if msg_type == 'state_update':
                await self._dispatch_event('state_update', message)
                return

            # Handle session messages
            if msg_type == 'session_started':
                self.session_id = message.get('session_id')
                logger.info(f"Session started: {self.session_id}")
                return

            if msg_type == 'session_ended':
                logger.info(f"Session ended: {message.get('session_id')}")
                self.session_id = None
                return

            # Handle pong
            if msg_type == 'pong':
                return

            # Log unknown messages
            logger.debug(f"Received: {message}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")

    async def _dispatch_event(self, event_name: str, data: Dict[str, Any]):
        """Dispatch event to registered handlers."""
        handlers = self._event_handlers.get(event_name, [])
        handlers += self._event_handlers.get('*', [])  # Wildcard handlers

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_name, data)
                else:
                    handler(event_name, data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def _send(self, message: Dict[str, Any]) -> None:
        """Send message to Fabric Gateway."""
        if not self.websocket or not self.connected:
            raise Exception("Not connected to Fabric Gateway")
        await self.websocket.send(json.dumps(message))

    async def _request(self, message: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
        """Send request and wait for response."""
        request_id = str(uuid.uuid4())
        message['request_id'] = request_id

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            await self._send(message)
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending_requests.pop(request_id, None)

    # Public API methods

    def on_event(self, event_name: str, handler: Callable):
        """Register event handler."""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    async def start_session(self, working_directory: Optional[str] = None):
        """Start or resume a session."""
        response = await self._request({
            'type': 'session_start',
            'data': {
                'working_directory': working_directory or CORTEX_PLATFORM_PATH,
                'session_id': self.session_id,  # Will resume if valid
            }
        })

        if response.get('type') == 'session_started':
            self.session_id = response.get('session_id')
            return self.session_id
        else:
            raise Exception(f"Failed to start session: {response}")

    async def end_session(self, summary: str = ''):
        """End current session."""
        if not self.session_id:
            return

        await self._request({
            'type': 'session_end',
            'data': {'summary': summary}
        })

    async def call_mcp_tool(self, server: str, tool: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call an MCP tool through the Fabric Gateway."""
        response = await self._request({
            'type': 'mcp_call',
            'data': {
                'server': server,
                'tool': tool,
                'args': args or {},
            }
        }, timeout=120.0)

        if response.get('type') == 'mcp_result':
            return response.get('result', {})
        elif response.get('type') == 'mcp_error':
            raise Exception(response.get('error', 'Unknown MCP error'))
        else:
            raise Exception(f"Unexpected response: {response}")

    async def publish_event(self, event_name: str, data: Dict[str, Any]):
        """Publish an event to all fabric clients."""
        await self._send({
            'type': 'event',
            'data': {
                'name': event_name,
                'data': data,
            }
        })

    async def query_state(self, key: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query shared state."""
        response = await self._request({
            'type': 'state_query',
            'data': {
                'key': key,
                'params': params or {},
            }
        })

        if response.get('type') == 'state_update':
            return response.get('data', {})
        else:
            raise Exception(f"State query failed: {response}")

    async def notify_file_change(self, event_type: str, path: str):
        """Notify fabric of local file change."""
        await self.publish_event('file_changed', {
            'event_type': event_type,
            'path': path,
            'working_directory': CORTEX_PLATFORM_PATH,
        })
        logger.debug(f"File change: {event_type} {path}")

    async def subscribe(self, channels: List[str]):
        """Subscribe to additional channels."""
        await self._send({
            'type': 'subscribe',
            'data': {'channels': channels}
        })

    async def list_mcp_servers(self) -> List[str]:
        """Get list of available MCP servers."""
        state = await self.query_state('clients')
        return state.get('mcp_servers', [])

    async def get_infrastructure_state(self) -> Dict[str, Any]:
        """Get current infrastructure state."""
        return await self.query_state('infrastructure')

    async def get_timeline(self, limit: int = 50) -> Dict[str, Any]:
        """Get recent timeline events."""
        return await self.query_state('timeline', {'limit': limit})


class MCPStdioServer:
    """
    MCP server implementation that reads/writes via stdio.
    This allows Claude Desktop to communicate with the bridge.
    """

    def __init__(self, bridge: CortexBridge):
        self.bridge = bridge
        self.running = False

    async def start(self):
        """Start the stdio MCP server."""
        self.running = True
        logger.info("MCP stdio server started")

        while self.running:
            try:
                # Read from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break

                request = json.loads(line.strip())
                response = await self._handle_request(request)

                # Write to stdout
                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON input: {e}")
            except Exception as e:
                logger.error(f"MCP request error: {e}")
                print(json.dumps({"error": str(e)}), flush=True)

    async def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request."""
        method = request.get('method')
        params = request.get('params', {})
        request_id = request.get('id')

        if method == 'initialize':
            return {
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                    },
                    "serverInfo": {
                        "name": "cortex-bridge",
                        "version": "1.0.0",
                    }
                }
            }

        elif method == 'tools/list':
            # List all available MCP tools from all servers
            tools = []

            # Add meta-tools for the bridge itself
            tools.extend([
                {
                    "name": "fabric_status",
                    "description": "Get Cortex Fabric connection status and connected clients",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "fabric_infrastructure",
                    "description": "Get current k3s infrastructure state",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "fabric_timeline",
                    "description": "Get recent timeline events",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 50}
                        }
                    }
                },
                {
                    "name": "mcp_call",
                    "description": "Call any MCP tool through the Cortex Fabric",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "server": {"type": "string", "description": "MCP server name (proxmox, kubernetes, github, etc.)"},
                            "tool": {"type": "string", "description": "Tool name to call"},
                            "args": {"type": "object", "description": "Tool arguments"}
                        },
                        "required": ["server", "tool"]
                    }
                },
            ])

            return {"id": request_id, "result": {"tools": tools}}

        elif method == 'tools/call':
            tool_name = params.get('name')
            tool_args = params.get('arguments', {})

            try:
                if tool_name == 'fabric_status':
                    result = await self.bridge.query_state('clients')
                elif tool_name == 'fabric_infrastructure':
                    result = await self.bridge.get_infrastructure_state()
                elif tool_name == 'fabric_timeline':
                    result = await self.bridge.get_timeline(tool_args.get('limit', 50))
                elif tool_name == 'mcp_call':
                    server = tool_args.get('server')
                    tool = tool_args.get('tool')
                    args = tool_args.get('args', {})
                    result = await self.bridge.call_mcp_tool(server, tool, args)
                else:
                    return {
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                    }

                return {
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                    }
                }
            except Exception as e:
                return {
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                        "isError": True,
                    }
                }

        else:
            return {
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Cortex Bridge - Local Fabric Connection')
    parser.add_argument('--local', action='store_true', help='Use local port-forward (localhost:8080)')
    parser.add_argument('--fabric-url', type=str, help='Custom Fabric Gateway URL')
    parser.add_argument('--mcp-stdio', action='store_true', help='Run as MCP stdio server for Claude Desktop')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine fabric URL
    if args.fabric_url:
        fabric_url = args.fabric_url
    elif args.local:
        fabric_url = LOCAL_FABRIC_URL
    else:
        fabric_url = DEFAULT_FABRIC_URL

    # Create bridge
    bridge = CortexBridge(fabric_url)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(bridge.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Log events
    def log_event(event_name: str, data: Dict[str, Any]):
        logger.info(f"Event: {event_name} - {json.dumps(data)[:200]}")

    bridge.on_event('*', log_event)

    # Start bridge
    logger.info(f"Starting Cortex Bridge (connecting to {fabric_url})")

    if args.mcp_stdio:
        # Run in MCP stdio mode for Claude Desktop
        mcp_server = MCPStdioServer(bridge)
        await asyncio.gather(
            bridge.start(),
            mcp_server.start(),
        )
    else:
        # Run in standalone mode
        await bridge.start()


if __name__ == '__main__':
    asyncio.run(main())
