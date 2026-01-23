#!/usr/bin/env python3
"""
Cortex Fabric Gateway
Unified WebSocket gateway for all Cortex clients (chat, Claude Desktop, Claude Code)
Provides bidirectional event streaming, MCP routing, and session management.
"""
import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set
from contextlib import asynccontextmanager
from enum import Enum

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.cortex-system.svc.cluster.local')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
MEMORY_SERVICE_URL = os.getenv('MEMORY_SERVICE_URL', 'http://memory-service.cortex-system.svc.cluster.local:8080')
MCP_GATEWAY_URL = os.getenv('MCP_GATEWAY_URL', 'http://cortex-mcp-server.cortex-system.svc.cluster.local:3000')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '30'))
SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', '24'))

# MCP Server URLs (can be overridden via config)
MCP_SERVERS = {
    'proxmox': os.getenv('PROXMOX_MCP_URL', 'http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000'),
    'unifi': os.getenv('UNIFI_MCP_URL', 'http://unifi-mcp-server.cortex-system.svc.cluster.local:3000'),
    'kubernetes': os.getenv('KUBERNETES_MCP_URL', 'http://kubernetes-mcp-server.cortex-system.svc.cluster.local:3001'),
    'github': os.getenv('GITHUB_MCP_URL', 'http://github-mcp-server.cortex-system.svc.cluster.local:3002'),
    'github-security': os.getenv('GITHUB_SECURITY_MCP_URL', 'http://github-security-mcp-server.cortex-system.svc.cluster.local:3003'),
    'outline': os.getenv('OUTLINE_MCP_URL', 'http://outline-mcp-server.cortex-system.svc.cluster.local:3004'),
    'n8n': os.getenv('N8N_MCP_URL', 'http://n8n-mcp-server.cortex-system.svc.cluster.local:3005'),
    'cloudflare': os.getenv('CLOUDFLARE_MCP_URL', 'http://cloudflare-mcp-server.cortex-system.svc.cluster.local:3006'),
    'sandfly': os.getenv('SANDFLY_MCP_URL', 'http://sandfly-mcp-server.cortex-system.svc.cluster.local:3000'),
    'checkmk': os.getenv('CHECKMK_MCP_URL', 'http://checkmk-mcp-server.cortex-system.svc.cluster.local:3002'),
    'langflow': os.getenv('LANGFLOW_MCP_URL', 'http://langflow-chat-mcp-server.cortex-system.svc.cluster.local:3000'),
    'youtube-ingestion': os.getenv('YOUTUBE_INGESTION_MCP_URL', 'http://youtube-ingestion-mcp.cortex.svc.cluster.local:3000'),
    'youtube-channel': os.getenv('YOUTUBE_CHANNEL_MCP_URL', 'http://youtube-channel-mcp.cortex.svc.cluster.local:3000'),
    'cortex-school': os.getenv('CORTEX_SCHOOL_MCP_URL', 'http://cortex-school-mcp.cortex-school.svc.cluster.local:3000'),
}

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)


class ClientType(str, Enum):
    CHAT = "chat"
    DESKTOP = "desktop"
    CODE = "code"
    BRIDGE = "bridge"
    UNKNOWN = "unknown"


class MessageType(str, Enum):
    # Client → Fabric
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    MCP_CALL = "mcp_call"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    STATE_QUERY = "state_query"

    # Fabric → Client
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    MCP_RESULT = "mcp_result"
    MCP_ERROR = "mcp_error"
    EVENT_BROADCAST = "event_broadcast"
    STATE_UPDATE = "state_update"
    ERROR = "error"
    PONG = "pong"


class FabricMessage(BaseModel):
    type: MessageType
    request_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConnectedClient:
    """Represents a connected WebSocket client."""

    def __init__(self, websocket: WebSocket, client_type: ClientType):
        self.id = str(uuid.uuid4())
        self.websocket = websocket
        self.client_type = client_type
        self.session_id: Optional[str] = None
        self.subscriptions: Set[str] = set()
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}

    async def send(self, message: Dict[str, Any]):
        """Send a message to the client."""
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to client {self.id}: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.id,
            "client_type": self.client_type.value,
            "session_id": self.session_id,
            "subscriptions": list(self.subscriptions),
            "connected_at": self.connected_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }


class FabricGateway:
    """Core Fabric Gateway managing all client connections and event routing."""

    def __init__(self):
        self.clients: Dict[str, ConnectedClient] = {}
        self.sessions: Dict[str, Set[str]] = {}  # session_id -> set of client_ids
        self.redis: Optional[redis.Redis] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.pubsub_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Initialize gateway connections."""
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self._running = True

        # Start Redis pubsub listener
        self.pubsub_task = asyncio.create_task(self._redis_listener())

        # Start heartbeat checker
        asyncio.create_task(self._heartbeat_checker())

        logger.info("Fabric Gateway started")

    async def stop(self):
        """Cleanup gateway connections."""
        self._running = False

        if self.pubsub_task:
            self.pubsub_task.cancel()

        if self.http_client:
            await self.http_client.aclose()

        if self.redis:
            await self.redis.close()

        logger.info("Fabric Gateway stopped")

    async def _redis_listener(self):
        """Listen for Redis pubsub events and broadcast to subscribed clients."""
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("fabric:*")

        try:
            while self._running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'pmessage':
                    channel = message['channel']
                    data = json.loads(message['data'])
                    await self._broadcast_to_channel(channel.replace('fabric:', ''), data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            await pubsub.punsubscribe("fabric:*")

    async def _heartbeat_checker(self):
        """Check for stale client connections."""
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)

            stale_threshold = datetime.utcnow() - timedelta(seconds=HEARTBEAT_INTERVAL * 3)
            stale_clients = [
                client_id for client_id, client in self.clients.items()
                if client.last_heartbeat < stale_threshold
            ]

            for client_id in stale_clients:
                logger.warning(f"Removing stale client: {client_id}")
                await self.disconnect_client(client_id)

    async def connect_client(self, websocket: WebSocket, client_type: ClientType) -> ConnectedClient:
        """Register a new client connection."""
        await websocket.accept()

        client = ConnectedClient(websocket, client_type)
        self.clients[client.id] = client

        # Auto-subscribe to common channels
        client.subscriptions.add("events")
        client.subscriptions.add("state")

        logger.info(f"Client connected: {client.id} ({client_type.value})")

        # Notify client of successful connection
        await client.send({
            "type": MessageType.CONNECTED.value,
            "client_id": client.id,
            "subscriptions": list(client.subscriptions),
            "mcp_servers": list(MCP_SERVERS.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Broadcast connection event
        await self.publish_event("client_connected", {
            "client_id": client.id,
            "client_type": client_type.value,
        })

        return client

    async def disconnect_client(self, client_id: str):
        """Remove a client connection."""
        client = self.clients.pop(client_id, None)
        if not client:
            return

        # Remove from session tracking
        if client.session_id and client.session_id in self.sessions:
            self.sessions[client.session_id].discard(client_id)
            if not self.sessions[client.session_id]:
                del self.sessions[client.session_id]

        logger.info(f"Client disconnected: {client_id}")

        # Broadcast disconnection event
        await self.publish_event("client_disconnected", {
            "client_id": client_id,
            "client_type": client.client_type.value,
        })

    async def handle_message(self, client: ConnectedClient, raw_message: str):
        """Process an incoming client message."""
        try:
            message = json.loads(raw_message)
            msg_type = message.get('type')
            request_id = message.get('request_id')
            data = message.get('data', {})

            handlers = {
                MessageType.HEARTBEAT.value: self._handle_heartbeat,
                MessageType.SUBSCRIBE.value: self._handle_subscribe,
                MessageType.UNSUBSCRIBE.value: self._handle_unsubscribe,
                MessageType.MCP_CALL.value: self._handle_mcp_call,
                MessageType.EVENT.value: self._handle_event,
                MessageType.SESSION_START.value: self._handle_session_start,
                MessageType.SESSION_END.value: self._handle_session_end,
                MessageType.STATE_QUERY.value: self._handle_state_query,
            }

            handler = handlers.get(msg_type)
            if handler:
                await handler(client, data, request_id)
            else:
                await client.send({
                    "type": MessageType.ERROR.value,
                    "request_id": request_id,
                    "error": f"Unknown message type: {msg_type}",
                })

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from client {client.id}: {e}")
            await client.send({
                "type": MessageType.ERROR.value,
                "error": "Invalid JSON",
            })
        except Exception as e:
            logger.error(f"Error handling message from {client.id}: {e}")
            await client.send({
                "type": MessageType.ERROR.value,
                "error": str(e),
            })

    async def _handle_heartbeat(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Handle heartbeat message."""
        client.last_heartbeat = datetime.utcnow()
        await client.send({
            "type": MessageType.PONG.value,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _handle_subscribe(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Handle channel subscription."""
        channels = data.get('channels', [])
        for channel in channels:
            client.subscriptions.add(channel)

        await client.send({
            "type": MessageType.SUBSCRIBED.value,
            "request_id": request_id,
            "subscriptions": list(client.subscriptions),
        })

    async def _handle_unsubscribe(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Handle channel unsubscription."""
        channels = data.get('channels', [])
        for channel in channels:
            client.subscriptions.discard(channel)

        await client.send({
            "type": MessageType.SUBSCRIBED.value,
            "request_id": request_id,
            "subscriptions": list(client.subscriptions),
        })

    async def _handle_mcp_call(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Route MCP tool call to appropriate server."""
        server = data.get('server')
        tool = data.get('tool')
        args = data.get('args', {})

        if not server or not tool:
            await client.send({
                "type": MessageType.MCP_ERROR.value,
                "request_id": request_id,
                "error": "Missing 'server' or 'tool' in request",
            })
            return

        server_url = MCP_SERVERS.get(server)
        if not server_url:
            await client.send({
                "type": MessageType.MCP_ERROR.value,
                "request_id": request_id,
                "error": f"Unknown MCP server: {server}",
                "available_servers": list(MCP_SERVERS.keys()),
            })
            return

        try:
            # Call the MCP server
            response = await self.http_client.post(
                f"{server_url}/call_tool",
                json={"name": tool, "arguments": args},
                timeout=120.0,
            )

            result = response.json() if response.status_code == 200 else {"error": response.text}

            await client.send({
                "type": MessageType.MCP_RESULT.value,
                "request_id": request_id,
                "server": server,
                "tool": tool,
                "result": result,
            })

            # Log telemetry
            await self._log_telemetry(client, server, tool, response.status_code)

        except httpx.TimeoutException:
            await client.send({
                "type": MessageType.MCP_ERROR.value,
                "request_id": request_id,
                "error": f"Timeout calling {server}/{tool}",
            })
        except Exception as e:
            await client.send({
                "type": MessageType.MCP_ERROR.value,
                "request_id": request_id,
                "error": str(e),
            })

    async def _handle_event(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Handle event publication from client."""
        event_name = data.get('name')
        event_data = data.get('data', {})

        if not event_name:
            await client.send({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": "Missing 'name' in event",
            })
            return

        # Add client context to event
        event_data['_source'] = {
            "client_id": client.id,
            "client_type": client.client_type.value,
            "session_id": client.session_id,
        }

        await self.publish_event(event_name, event_data)

        # Also send to Memory Service timeline
        await self._record_timeline_event(event_name, event_data, client)

    async def _handle_session_start(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Start or resume a session for this client."""
        session_id = data.get('session_id')
        working_directory = data.get('working_directory')

        try:
            if session_id:
                # Try to resume existing session
                response = await self.http_client.get(
                    f"{MEMORY_SERVICE_URL}/memory/sessions/{session_id}"
                )
                if response.status_code == 200:
                    session = response.json()
                    client.session_id = session_id
                else:
                    # Session not found, create new
                    session_id = None

            if not session_id:
                # Create new session
                response = await self.http_client.post(
                    f"{MEMORY_SERVICE_URL}/memory/sessions",
                    json={
                        "working_directory": working_directory or "/",
                        "metadata": {
                            "client_type": client.client_type.value,
                            "client_id": client.id,
                        }
                    }
                )
                if response.status_code in [200, 201]:
                    session = response.json()
                    session_id = session.get('session_id')
                    client.session_id = session_id
                else:
                    raise Exception(f"Failed to create session: {response.text}")

            # Track session-client mapping
            if session_id not in self.sessions:
                self.sessions[session_id] = set()
            self.sessions[session_id].add(client.id)

            await client.send({
                "type": "session_started",
                "request_id": request_id,
                "session_id": session_id,
                "session": session if 'session' in locals() else None,
            })

            # Broadcast session event
            await self.publish_event("session_started", {
                "session_id": session_id,
                "client_id": client.id,
                "client_type": client.client_type.value,
            })

        except Exception as e:
            logger.error(f"Session start error: {e}")
            await client.send({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": str(e),
            })

    async def _handle_session_end(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """End a session."""
        if not client.session_id:
            await client.send({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": "No active session",
            })
            return

        summary = data.get('summary', '')

        try:
            response = await self.http_client.post(
                f"{MEMORY_SERVICE_URL}/memory/sessions/{client.session_id}/end",
                json={"summary": summary}
            )

            # Remove from session tracking
            if client.session_id in self.sessions:
                self.sessions[client.session_id].discard(client.id)

            old_session_id = client.session_id
            client.session_id = None

            await client.send({
                "type": "session_ended",
                "request_id": request_id,
                "session_id": old_session_id,
            })

            await self.publish_event("session_ended", {
                "session_id": old_session_id,
                "client_id": client.id,
            })

        except Exception as e:
            logger.error(f"Session end error: {e}")
            await client.send({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": str(e),
            })

    async def _handle_state_query(self, client: ConnectedClient, data: Dict, request_id: Optional[str]):
        """Query shared state."""
        state_key = data.get('key', 'infrastructure')

        try:
            if state_key == 'infrastructure':
                response = await self.http_client.get(
                    f"{MEMORY_SERVICE_URL}/memory/infrastructure/current"
                )
            elif state_key == 'sessions':
                response = await self.http_client.get(
                    f"{MEMORY_SERVICE_URL}/memory/sessions"
                )
            elif state_key == 'timeline':
                response = await self.http_client.get(
                    f"{MEMORY_SERVICE_URL}/memory/timeline",
                    params=data.get('params', {})
                )
            elif state_key == 'clients':
                # Return connected clients (local state)
                await client.send({
                    "type": MessageType.STATE_UPDATE.value,
                    "request_id": request_id,
                    "key": state_key,
                    "data": {
                        "clients": [c.to_dict() for c in self.clients.values()],
                        "sessions": {k: list(v) for k, v in self.sessions.items()},
                    },
                })
                return
            else:
                await client.send({
                    "type": MessageType.ERROR.value,
                    "request_id": request_id,
                    "error": f"Unknown state key: {state_key}",
                })
                return

            await client.send({
                "type": MessageType.STATE_UPDATE.value,
                "request_id": request_id,
                "key": state_key,
                "data": response.json() if response.status_code == 200 else {"error": response.text},
            })

        except Exception as e:
            logger.error(f"State query error: {e}")
            await client.send({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": str(e),
            })

    async def publish_event(self, event_name: str, data: Dict[str, Any]):
        """Publish event to all subscribed clients and Redis."""
        event = {
            "type": MessageType.EVENT_BROADCAST.value,
            "event": event_name,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Publish to Redis for cross-instance distribution
        await self.redis.publish(f"fabric:events", json.dumps(event))

        # Also broadcast locally
        await self._broadcast_to_channel("events", event)

    async def _broadcast_to_channel(self, channel: str, data: Dict[str, Any]):
        """Broadcast message to all clients subscribed to a channel."""
        for client in self.clients.values():
            if channel in client.subscriptions:
                try:
                    await client.send(data)
                except Exception as e:
                    logger.error(f"Broadcast error to {client.id}: {e}")

    async def _log_telemetry(self, client: ConnectedClient, server: str, tool: str, status: int):
        """Log MCP call telemetry."""
        try:
            await self.redis.hincrby(
                f"fabric:telemetry:{datetime.utcnow().strftime('%Y-%m-%d')}",
                f"{server}:{tool}",
                1
            )
        except Exception as e:
            logger.warning(f"Telemetry logging failed: {e}")

    async def _record_timeline_event(self, event_name: str, data: Dict, client: ConnectedClient):
        """Record event to Memory Service timeline."""
        try:
            await self.http_client.post(
                f"{MEMORY_SERVICE_URL}/memory/timeline/event",
                json={
                    "event_type": event_name.upper(),
                    "source": f"fabric:{client.client_type.value}",
                    "description": data.get('description', event_name),
                    "details": data,
                    "severity": data.get('severity', 'low'),
                }
            )
        except Exception as e:
            logger.warning(f"Timeline recording failed: {e}")


# Global gateway instance
gateway = FabricGateway()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    await gateway.start()
    yield
    await gateway.stop()


app = FastAPI(
    title="Cortex Fabric Gateway",
    description="Unified WebSocket gateway for Cortex clients",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket endpoint
@app.websocket("/ws/fabric")
async def websocket_fabric(
    websocket: WebSocket,
    client_type: str = Query(default="unknown"),
):
    """Main WebSocket endpoint for fabric connections."""
    try:
        ct = ClientType(client_type) if client_type in [e.value for e in ClientType] else ClientType.UNKNOWN
    except ValueError:
        ct = ClientType.UNKNOWN

    client = await gateway.connect_client(websocket, ct)

    try:
        while True:
            message = await websocket.receive_text()
            await gateway.handle_message(client, message)
    except WebSocketDisconnect:
        await gateway.disconnect_client(client.id)
    except Exception as e:
        logger.error(f"WebSocket error for {client.id}: {e}")
        await gateway.disconnect_client(client.id)


# REST API endpoints
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "fabric-gateway",
        "clients": len(gateway.clients),
        "sessions": len(gateway.sessions),
    }


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    try:
        await gateway.redis.ping()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/clients")
async def list_clients():
    """List all connected clients."""
    return {
        "clients": [c.to_dict() for c in gateway.clients.values()],
        "total": len(gateway.clients),
    }


@app.get("/api/sessions")
async def list_sessions():
    """List active sessions with their clients."""
    return {
        "sessions": {k: list(v) for k, v in gateway.sessions.items()},
        "total": len(gateway.sessions),
    }


@app.get("/api/mcp/servers")
async def list_mcp_servers():
    """List available MCP servers."""
    return {
        "servers": list(MCP_SERVERS.keys()),
        "urls": MCP_SERVERS,
    }


@app.post("/api/events/publish")
async def publish_event(event_name: str, data: Dict[str, Any]):
    """Publish an event to all subscribed clients (for server-side event sources)."""
    await gateway.publish_event(event_name, data)
    return {"status": "published", "event": event_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
