#!/usr/bin/env python3
"""
Layer Activator - Serverless MCP Stack Management

The Layer Activator is the central proxy that:
1. Receives all incoming requests
2. Determines the target Layer Stack
3. Activates stacks on-demand (scale 0→1)
4. Routes requests to active stacks
5. Tracks activity for scale-down decisions
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
import redis.asyncio as redis
import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("layer-activator")


# ============================================================================
# Models
# ============================================================================

class StackComponent(BaseModel):
    """A component (deployment) within a stack."""
    deployment: str
    namespace: Optional[str] = None  # If different from stack namespace


class StackRoute(BaseModel):
    """Routing pattern for a stack."""
    pattern: str  # Regex or glob pattern


class StackConfig(BaseModel):
    """Configuration for a Layer Stack."""
    id: str
    name: str
    namespace: str
    min_replicas: int = 0
    max_replicas: int = 5
    cooldown_seconds: int = 300
    components: List[StackComponent]
    routes: List[StackRoute]
    health_endpoint: Optional[str] = "/health"
    service_port: int = 8080


class StackStatus(BaseModel):
    """Current status of a stack."""
    stack_id: str
    status: str  # scaled_down, activating, active, scaling_down
    current_replicas: int
    last_activity: Optional[datetime]
    components: List[Dict]


class ActivateRequest(BaseModel):
    """Request to activate a stack."""
    stack_id: str


class RouteRequest(BaseModel):
    """Request to route to a stack."""
    task_type: str
    payload: Dict


# ============================================================================
# Layer Activator Service
# ============================================================================

class LayerActivator:
    """
    Central service for managing Layer Stack activation and routing.
    """

    def __init__(
        self,
        config_path: str = "/config/stacks.yaml",
        redis_url: str = "redis://localhost:6379",
    ):
        self.config_path = config_path
        self.redis_url = redis_url

        # Stack registry
        self.stacks: Dict[str, StackConfig] = {}

        # Activity tracking
        self.activity: Dict[str, datetime] = {}

        # Kubernetes client
        self.k8s_apps: Optional[client.AppsV1Api] = None
        self.k8s_core: Optional[client.CoreV1Api] = None

        # Redis client
        self.redis: Optional[redis.Redis] = None

        # HTTP client for health checks
        self.http_client: Optional[httpx.AsyncClient] = None

        # Background tasks
        self._scale_down_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Initialize the activator."""
        logger.info("Starting Layer Activator...")

        # Load Kubernetes config
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except config.ConfigException:
            config.load_kube_config()
            logger.info("Loaded local Kubernetes config")

        self.k8s_apps = client.AppsV1Api()
        self.k8s_core = client.CoreV1Api()

        # Connect to Redis
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        await self.redis.ping()
        logger.info(f"Connected to Redis at {self.redis_url}")

        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=10.0)

        # Load stack configuration
        await self.load_config()

        # Start background tasks
        self._running = True
        self._scale_down_task = asyncio.create_task(self._scale_down_loop())

        logger.info(f"Layer Activator started with {len(self.stacks)} stacks")

    async def stop(self):
        """Shutdown the activator."""
        logger.info("Stopping Layer Activator...")
        self._running = False

        if self._scale_down_task:
            self._scale_down_task.cancel()
            try:
                await self._scale_down_task
            except asyncio.CancelledError:
                pass

        if self.http_client:
            await self.http_client.aclose()

        if self.redis:
            await self.redis.close()

        logger.info("Layer Activator stopped")

    async def load_config(self):
        """Load stack configuration from file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self._load_default_config()
            return

        with open(self.config_path) as f:
            config_data = yaml.safe_load(f)

        for stack_data in config_data.get("stacks", []):
            stack = StackConfig(
                id=stack_data["id"],
                name=stack_data.get("name", stack_data["id"]),
                namespace=stack_data["namespace"],
                min_replicas=stack_data.get("min_replicas", 0),
                max_replicas=stack_data.get("max_replicas", 5),
                cooldown_seconds=stack_data.get("cooldown", 300),
                components=[
                    StackComponent(**c) for c in stack_data.get("components", [])
                ],
                routes=[
                    StackRoute(**r) for r in stack_data.get("routes", [])
                ],
                health_endpoint=stack_data.get("health_endpoint", "/health"),
                service_port=stack_data.get("service_port", 8080),
            )
            self.stacks[stack.id] = stack
            logger.info(f"Loaded stack config: {stack.id} ({stack.namespace})")

    def _load_default_config(self):
        """Load default stack configuration."""
        default_stacks = [
            StackConfig(
                id="security-stack",
                name="Security Operations",
                namespace="cortex-security",
                min_replicas=0,
                cooldown_seconds=300,
                components=[
                    StackComponent(deployment="sandfly-mcp-server", namespace="cortex-system"),
                    StackComponent(deployment="github-security-mcp-server", namespace="cortex-system"),
                ],
                routes=[
                    StackRoute(pattern="scan_.*"),
                    StackRoute(pattern="security.*"),
                    StackRoute(pattern="threat.*"),
                ],
            ),
            StackConfig(
                id="infra-stack",
                name="Infrastructure Operations",
                namespace="cortex-system",
                min_replicas=0,
                cooldown_seconds=300,
                components=[
                    StackComponent(deployment="proxmox-mcp-server"),
                    StackComponent(deployment="unifi-mcp-server"),
                    StackComponent(deployment="cloudflare-mcp-server"),
                    StackComponent(deployment="kubernetes-mcp-server"),
                ],
                routes=[
                    StackRoute(pattern="infra.*"),
                    StackRoute(pattern="vm.*"),
                    StackRoute(pattern="network.*"),
                    StackRoute(pattern="dns.*"),
                    StackRoute(pattern="cluster.*"),
                ],
            ),
            StackConfig(
                id="knowledge-stack",
                name="Knowledge Operations",
                namespace="cortex-knowledge",
                min_replicas=0,
                cooldown_seconds=600,
                components=[
                    StackComponent(deployment="mcp-server"),
                    StackComponent(deployment="knowledge-graph-api"),
                ],
                routes=[
                    StackRoute(pattern="knowledge.*"),
                    StackRoute(pattern="search.*"),
                    StackRoute(pattern="query.*"),
                ],
            ),
            StackConfig(
                id="school-stack",
                name="Cortex Online School",
                namespace="cortex-school",
                min_replicas=1,  # Always on
                cooldown_seconds=0,
                components=[
                    StackComponent(deployment="youtube-ingestion"),
                    StackComponent(deployment="implementation-workers"),
                ],
                routes=[
                    StackRoute(pattern="learn.*"),
                    StackRoute(pattern="youtube.*"),
                ],
            ),
        ]

        for stack in default_stacks:
            self.stacks[stack.id] = stack
            logger.info(f"Loaded default stack: {stack.id}")

    # ========================================================================
    # Stack Management
    # ========================================================================

    async def get_stack_status(self, stack_id: str) -> StackStatus:
        """Get current status of a stack."""
        if stack_id not in self.stacks:
            raise ValueError(f"Unknown stack: {stack_id}")

        stack = self.stacks[stack_id]
        components = []
        total_replicas = 0

        for component in stack.components:
            ns = component.namespace or stack.namespace
            try:
                deployment = self.k8s_apps.read_namespaced_deployment(
                    name=component.deployment,
                    namespace=ns,
                )
                ready = deployment.status.ready_replicas or 0
                desired = deployment.spec.replicas or 0
                total_replicas += ready

                components.append({
                    "name": component.deployment,
                    "namespace": ns,
                    "ready": ready,
                    "desired": desired,
                    "available": ready >= desired and desired > 0,
                })
            except ApiException as e:
                if e.status == 404:
                    components.append({
                        "name": component.deployment,
                        "namespace": ns,
                        "error": "not found",
                    })
                else:
                    raise

        # Determine status
        if total_replicas == 0:
            status = "scaled_down"
        elif all(c.get("available", False) for c in components if "error" not in c):
            status = "active"
        else:
            status = "activating"

        return StackStatus(
            stack_id=stack_id,
            status=status,
            current_replicas=total_replicas,
            last_activity=self.activity.get(stack_id),
            components=components,
        )

    async def is_stack_active(self, stack_id: str) -> bool:
        """Check if a stack is currently active."""
        status = await self.get_stack_status(stack_id)
        return status.status == "active"

    async def activate_stack(self, stack_id: str) -> bool:
        """Activate a stack by scaling its components."""
        if stack_id not in self.stacks:
            raise ValueError(f"Unknown stack: {stack_id}")

        stack = self.stacks[stack_id]
        logger.info(f"Activating stack: {stack_id}")

        start_time = time.time()

        # Scale up each component
        for component in stack.components:
            ns = component.namespace or stack.namespace
            try:
                # Get current deployment
                deployment = self.k8s_apps.read_namespaced_deployment(
                    name=component.deployment,
                    namespace=ns,
                )

                # Scale to 1 if at 0
                if deployment.spec.replicas == 0:
                    deployment.spec.replicas = 1
                    self.k8s_apps.patch_namespaced_deployment(
                        name=component.deployment,
                        namespace=ns,
                        body=deployment,
                    )
                    logger.info(f"Scaled up {component.deployment} in {ns}")

            except ApiException as e:
                logger.error(f"Failed to scale {component.deployment}: {e}")
                return False

        # Record activation in Redis
        await self.redis.hset(
            "layer-activator:activations",
            stack_id,
            datetime.now().isoformat(),
        )

        # Track activity
        self.activity[stack_id] = datetime.now()

        elapsed = time.time() - start_time
        logger.info(f"Stack {stack_id} activation initiated in {elapsed:.2f}s")

        return True

    async def wait_for_ready(
        self,
        stack_id: str,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> bool:
        """Wait for a stack to become ready."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.get_stack_status(stack_id)

            if status.status == "active":
                elapsed = time.time() - start_time
                logger.info(f"Stack {stack_id} ready in {elapsed:.2f}s")

                # Record cold start latency
                await self.redis.lpush(
                    f"layer-activator:cold-starts:{stack_id}",
                    elapsed,
                )
                await self.redis.ltrim(
                    f"layer-activator:cold-starts:{stack_id}",
                    0,
                    99,  # Keep last 100
                )

                return True

            await asyncio.sleep(poll_interval)

        logger.warning(f"Stack {stack_id} did not become ready within {timeout}s")
        return False

    async def scale_down_stack(self, stack_id: str) -> bool:
        """Scale down a stack to zero."""
        if stack_id not in self.stacks:
            raise ValueError(f"Unknown stack: {stack_id}")

        stack = self.stacks[stack_id]

        # Don't scale down if min_replicas > 0
        if stack.min_replicas > 0:
            logger.info(f"Stack {stack_id} has min_replicas={stack.min_replicas}, not scaling down")
            return False

        logger.info(f"Scaling down stack: {stack_id}")

        for component in stack.components:
            ns = component.namespace or stack.namespace
            try:
                deployment = self.k8s_apps.read_namespaced_deployment(
                    name=component.deployment,
                    namespace=ns,
                )

                if deployment.spec.replicas > 0:
                    deployment.spec.replicas = 0
                    self.k8s_apps.patch_namespaced_deployment(
                        name=component.deployment,
                        namespace=ns,
                        body=deployment,
                    )
                    logger.info(f"Scaled down {component.deployment} in {ns}")

            except ApiException as e:
                logger.error(f"Failed to scale down {component.deployment}: {e}")
                return False

        # Record scale-down
        await self.redis.hset(
            "layer-activator:scale-downs",
            stack_id,
            datetime.now().isoformat(),
        )

        return True

    # ========================================================================
    # Routing
    # ========================================================================

    def determine_stack(self, task_type: str) -> Optional[str]:
        """Determine which stack should handle a task type."""
        import re

        for stack_id, stack in self.stacks.items():
            for route in stack.routes:
                # Convert glob to regex
                pattern = route.pattern.replace("*", ".*")
                if re.match(pattern, task_type):
                    return stack_id

        return None

    async def route_request(
        self,
        task_type: str,
        payload: Dict,
        timeout: float = 90.0,
    ) -> Dict:
        """Route a request to the appropriate stack."""
        # Determine target stack
        stack_id = self.determine_stack(task_type)
        if not stack_id:
            raise ValueError(f"No stack found for task type: {task_type}")

        stack = self.stacks[stack_id]
        logger.info(f"Routing {task_type} to {stack_id}")

        # Check if stack is active
        status = await self.get_stack_status(stack_id)

        if status.status == "scaled_down":
            # Activate and wait
            logger.info(f"Stack {stack_id} is scaled down, activating...")
            await self.activate_stack(stack_id)

            if not await self.wait_for_ready(stack_id, timeout=60.0):
                raise RuntimeError(f"Stack {stack_id} failed to become ready")

        elif status.status == "activating":
            # Wait for it to become ready
            logger.info(f"Stack {stack_id} is activating, waiting...")
            if not await self.wait_for_ready(stack_id, timeout=60.0):
                raise RuntimeError(f"Stack {stack_id} failed to become ready")

        # Track activity
        self.activity[stack_id] = datetime.now()

        # Forward request to stack's primary service
        # For now, use the first component's service
        primary = stack.components[0]
        ns = primary.namespace or stack.namespace
        service_url = f"http://{primary.deployment}.{ns}.svc.cluster.local:{stack.service_port}"

        try:
            response = await self.http_client.post(
                service_url,
                json={"task_type": task_type, **payload},
                timeout=timeout,
            )
            response.raise_for_status()
            return {
                "stack_id": stack_id,
                "response": response.json(),
            }
        except httpx.HTTPError as e:
            logger.error(f"Request to {stack_id} failed: {e}")
            raise RuntimeError(f"Request to stack {stack_id} failed: {e}")

    # ========================================================================
    # Background Tasks
    # ========================================================================

    async def _scale_down_loop(self):
        """Background task to scale down idle stacks."""
        logger.info("Starting scale-down monitor")

        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = datetime.now()

                for stack_id, stack in self.stacks.items():
                    # Skip stacks with min_replicas > 0
                    if stack.min_replicas > 0:
                        continue

                    last_activity = self.activity.get(stack_id)
                    if last_activity is None:
                        continue

                    idle_time = (now - last_activity).total_seconds()

                    if idle_time > stack.cooldown_seconds:
                        status = await self.get_stack_status(stack_id)
                        if status.status == "active":
                            logger.info(
                                f"Stack {stack_id} idle for {idle_time:.0f}s "
                                f"(cooldown: {stack.cooldown_seconds}s), scaling down"
                            )
                            await self.scale_down_stack(stack_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scale-down loop error: {e}")

        logger.info("Scale-down monitor stopped")

    # ========================================================================
    # Metrics
    # ========================================================================

    async def get_metrics(self) -> Dict:
        """Get activator metrics."""
        metrics = {
            "total_stacks": len(self.stacks),
            "active_stacks": 0,
            "scaled_down_stacks": 0,
            "activating_stacks": 0,
        }

        for stack_id in self.stacks:
            try:
                status = await self.get_stack_status(stack_id)
                if status.status == "active":
                    metrics["active_stacks"] += 1
                elif status.status == "scaled_down":
                    metrics["scaled_down_stacks"] += 1
                elif status.status == "activating":
                    metrics["activating_stacks"] += 1
            except Exception:
                pass

        # Get cold start latencies from Redis
        cold_starts = {}
        for stack_id in self.stacks:
            latencies = await self.redis.lrange(
                f"layer-activator:cold-starts:{stack_id}",
                0,
                -1,
            )
            if latencies:
                latencies = [float(l) for l in latencies]
                cold_starts[stack_id] = {
                    "avg": sum(latencies) / len(latencies),
                    "min": min(latencies),
                    "max": max(latencies),
                    "count": len(latencies),
                }

        metrics["cold_start_latencies"] = cold_starts

        return metrics


# ============================================================================
# FastAPI Application
# ============================================================================

activator: Optional[LayerActivator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global activator

    # Startup
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    config_path = os.getenv("STACK_CONFIG", "/config/stacks.yaml")

    activator = LayerActivator(
        config_path=config_path,
        redis_url=redis_url,
    )
    await activator.start()

    yield

    # Shutdown
    await activator.stop()


app = FastAPI(
    title="Layer Activator",
    description="Serverless MCP Stack Management",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    if activator and activator.redis:
        try:
            await activator.redis.ping()
            return {"status": "ready"}
        except Exception:
            pass
    raise HTTPException(status_code=503, detail="Not ready")


@app.get("/stacks")
async def list_stacks():
    """List all configured stacks."""
    stacks = []
    for stack_id, stack in activator.stacks.items():
        status = await activator.get_stack_status(stack_id)
        stacks.append({
            "id": stack.id,
            "name": stack.name,
            "namespace": stack.namespace,
            "status": status.status,
            "replicas": status.current_replicas,
            "last_activity": status.last_activity.isoformat() if status.last_activity else None,
        })
    return {"stacks": stacks}


@app.get("/stacks/{stack_id}")
async def get_stack(stack_id: str):
    """Get detailed status of a stack."""
    if stack_id not in activator.stacks:
        raise HTTPException(status_code=404, detail=f"Stack not found: {stack_id}")

    status = await activator.get_stack_status(stack_id)
    stack = activator.stacks[stack_id]

    return {
        "id": stack.id,
        "name": stack.name,
        "namespace": stack.namespace,
        "min_replicas": stack.min_replicas,
        "max_replicas": stack.max_replicas,
        "cooldown_seconds": stack.cooldown_seconds,
        "status": status.status,
        "current_replicas": status.current_replicas,
        "last_activity": status.last_activity.isoformat() if status.last_activity else None,
        "components": status.components,
        "routes": [r.pattern for r in stack.routes],
    }


@app.post("/activate")
async def activate_stack(request: ActivateRequest):
    """Manually activate a stack."""
    if request.stack_id not in activator.stacks:
        raise HTTPException(status_code=404, detail=f"Stack not found: {request.stack_id}")

    start_time = time.time()
    success = await activator.activate_stack(request.stack_id)

    if not success:
        raise HTTPException(status_code=500, detail="Activation failed")

    # Wait for ready
    ready = await activator.wait_for_ready(request.stack_id, timeout=60.0)
    elapsed = time.time() - start_time

    return {
        "stack_id": request.stack_id,
        "status": "active" if ready else "activating",
        "activation_time_seconds": elapsed,
    }


@app.post("/route")
async def route_request(request: RouteRequest):
    """Route a request to the appropriate stack."""
    try:
        result = await activator.route_request(
            task_type=request.task_type,
            payload=request.payload,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/scale-down/{stack_id}")
async def scale_down(stack_id: str):
    """Manually scale down a stack."""
    if stack_id not in activator.stacks:
        raise HTTPException(status_code=404, detail=f"Stack not found: {stack_id}")

    success = await activator.scale_down_stack(stack_id)

    if not success:
        raise HTTPException(status_code=400, detail="Scale down not allowed or failed")

    return {"stack_id": stack_id, "status": "scaled_down"}


@app.get("/metrics")
async def metrics():
    """Get activator metrics."""
    return await activator.get_metrics()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
