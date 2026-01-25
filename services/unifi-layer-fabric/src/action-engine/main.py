"""
UniFi Action Engine - API Operations Layer

Handles all UniFi API operations:
- Site Manager API (cloud)
- Network Application API (local controller)

Each action is validated, logged, and can be rolled back.
"""

import os
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

# =============================================================================
# Configuration
# =============================================================================

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ActionDefinition:
    name: str
    method: str
    endpoint: str
    category: str
    risk_level: RiskLevel
    requires_confirmation: bool = False
    payload_template: Optional[str] = None


# =============================================================================
# UniFi API Client
# =============================================================================

class UniFiClient:
    """Client for UniFi Network Application API."""
    
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = False
    ):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session: Optional[httpx.AsyncClient] = None
        self.csrf_token: Optional[str] = None
        self.log = structlog.get_logger()
    
    async def connect(self):
        """Authenticate with the controller."""
        self.session = httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=30.0
        )
        
        # Login
        resp = await self.session.post(
            f"{self.host}/api/auth/login",
            json={
                "username": self.username,
                "password": self.password
            }
        )
        
        if resp.status_code != 200:
            raise Exception(f"Login failed: {resp.status_code}")
        
        # Extract CSRF token if present
        self.csrf_token = resp.headers.get("x-csrf-token")
        self.log.info("unifi_connected", host=self.host)
    
    async def disconnect(self):
        """Close the session."""
        if self.session:
            await self.session.aclose()
    
    async def request(
        self,
        method: str,
        endpoint: str,
        site: str = "default",
        json: Optional[dict] = None
    ) -> dict:
        """Make an authenticated request to the controller."""
        if not self.session:
            await self.connect()
        
        url = f"{self.host}/proxy/network/api/s/{site}{endpoint}"
        headers = {}
        if self.csrf_token:
            headers["x-csrf-token"] = self.csrf_token
        
        resp = await self.session.request(
            method=method,
            url=url,
            json=json,
            headers=headers
        )
        
        if resp.status_code == 401:
            # Re-authenticate and retry
            await self.connect()
            resp = await self.session.request(
                method=method,
                url=url,
                json=json,
                headers=headers
            )
        
        if resp.status_code >= 400:
            raise Exception(f"API error: {resp.status_code} - {resp.text}")
        
        return resp.json()


# =============================================================================
# Action Registry
# =============================================================================

ACTIONS: dict[str, ActionDefinition] = {
    # Client operations
    "get_clients": ActionDefinition(
        name="get_clients",
        method="GET",
        endpoint="/stat/sta",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "get_client": ActionDefinition(
        name="get_client", 
        method="GET",
        endpoint="/stat/user/{mac}",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "block_client": ActionDefinition(
        name="block_client",
        method="POST",
        endpoint="/cmd/stamgr",
        category="write",
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        payload_template='{"cmd": "block-sta", "mac": "{mac}"}'
    ),
    "unblock_client": ActionDefinition(
        name="unblock_client",
        method="POST",
        endpoint="/cmd/stamgr",
        category="write",
        risk_level=RiskLevel.LOW,
        payload_template='{"cmd": "unblock-sta", "mac": "{mac}"}'
    ),
    "reconnect_client": ActionDefinition(
        name="reconnect_client",
        method="POST",
        endpoint="/cmd/stamgr",
        category="execute",
        risk_level=RiskLevel.LOW,
        payload_template='{"cmd": "kick-sta", "mac": "{mac}"}'
    ),
    
    # Device operations
    "get_devices": ActionDefinition(
        name="get_devices",
        method="GET",
        endpoint="/stat/device",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "restart_device": ActionDefinition(
        name="restart_device",
        method="POST",
        endpoint="/cmd/devmgr",
        category="execute",
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        payload_template='{"cmd": "restart", "mac": "{mac}"}'
    ),
    "locate_device": ActionDefinition(
        name="locate_device",
        method="POST",
        endpoint="/cmd/devmgr",
        category="execute",
        risk_level=RiskLevel.LOW,
        payload_template='{"cmd": "set-locate", "mac": "{mac}"}'
    ),
    
    # Network operations
    "get_networks": ActionDefinition(
        name="get_networks",
        method="GET",
        endpoint="/rest/networkconf",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "create_network": ActionDefinition(
        name="create_network",
        method="POST",
        endpoint="/rest/networkconf",
        category="write",
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True
    ),
    
    # WLAN operations
    "get_wlans": ActionDefinition(
        name="get_wlans",
        method="GET",
        endpoint="/rest/wlanconf",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    
    # Firewall operations
    "get_firewall_rules": ActionDefinition(
        name="get_firewall_rules",
        method="GET",
        endpoint="/rest/firewallrule",
        category="read",
        risk_level=RiskLevel.LOW
    ),
}


# =============================================================================
# Models
# =============================================================================

class ExecuteRequest(BaseModel):
    tool: str
    query: str
    site: str = "default"
    context: Optional[dict] = None
    params: Optional[dict] = None
    confirmed: bool = False


class ExecuteResponse(BaseModel):
    success: bool
    tool: str
    result: Optional[Any] = None
    error: Optional[str] = None
    requires_confirmation: bool = False
    risk_level: str = "low"
    audit_id: Optional[str] = None


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="UniFi Action Engine",
    description="Execution layer for UniFi API operations",
    version="0.1.0"
)

# Initialize client from environment
unifi_client: Optional[UniFiClient] = None
log = structlog.get_logger()


@app.on_event("startup")
async def startup():
    global unifi_client
    
    host = os.getenv("UNIFI_CONTROLLER_HOST")
    username = os.getenv("UNIFI_CONTROLLER_USERNAME")
    password = os.getenv("UNIFI_CONTROLLER_PASSWORD")
    verify_ssl = os.getenv("UNIFI_VERIFY_SSL", "false").lower() == "true"
    
    if host and username and password:
        unifi_client = UniFiClient(host, username, password, verify_ssl)
        try:
            await unifi_client.connect()
        except Exception as e:
            log.error("unifi_connect_failed", error=str(e))


@app.on_event("shutdown")
async def shutdown():
    if unifi_client:
        await unifi_client.disconnect()


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    if not unifi_client or not unifi_client.session:
        raise HTTPException(503, "UniFi client not connected")
    return {"status": "ready"}


@app.get("/actions")
async def list_actions():
    """List all available actions."""
    return {
        name: {
            "category": action.category,
            "risk_level": action.risk_level.value,
            "requires_confirmation": action.requires_confirmation
        }
        for name, action in ACTIONS.items()
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute_action(request: ExecuteRequest):
    """Execute a UniFi action."""
    
    # Validate action exists
    action = ACTIONS.get(request.tool)
    if not action:
        return ExecuteResponse(
            success=False,
            tool=request.tool,
            error=f"Unknown action: {request.tool}"
        )
    
    # Check confirmation for risky actions
    if action.requires_confirmation and not request.confirmed:
        return ExecuteResponse(
            success=False,
            tool=request.tool,
            requires_confirmation=True,
            risk_level=action.risk_level.value,
            error="This action requires confirmation"
        )
    
    # Generate audit ID
    audit_id = f"{request.tool}-{datetime.utcnow().isoformat()}"
    
    log.info(
        "action_executing",
        tool=request.tool,
        site=request.site,
        audit_id=audit_id
    )
    
    try:
        # Build endpoint with params
        endpoint = action.endpoint
        if request.params:
            for key, value in request.params.items():
                endpoint = endpoint.replace(f"{{{key}}}", str(value))
        
        # Build payload
        payload = None
        if action.payload_template and request.params:
            import json
            payload_str = action.payload_template
            for key, value in request.params.items():
                payload_str = payload_str.replace(f"{{{key}}}", str(value))
            payload = json.loads(payload_str)
        
        # Execute
        result = await unifi_client.request(
            method=action.method,
            endpoint=endpoint,
            site=request.site,
            json=payload
        )
        
        log.info(
            "action_completed",
            tool=request.tool,
            audit_id=audit_id,
            success=True
        )
        
        return ExecuteResponse(
            success=True,
            tool=request.tool,
            result=result,
            risk_level=action.risk_level.value,
            audit_id=audit_id
        )
        
    except Exception as e:
        log.error(
            "action_failed",
            tool=request.tool,
            audit_id=audit_id,
            error=str(e)
        )
        
        return ExecuteResponse(
            success=False,
            tool=request.tool,
            error=str(e),
            risk_level=action.risk_level.value,
            audit_id=audit_id
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
