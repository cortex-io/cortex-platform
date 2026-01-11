# Cortex Orchestrator REST API

The Cortex Orchestrator now exposes all MCP tools as REST API endpoints for easy integration with other services.

## Base URL

```
http://cortex-orchestrator.cortex-system.svc.cluster.local:8080
```

## Health & Status Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "cortex-orchestrator"
}
```

### GET /ready
Readiness check endpoint.

**Response:**
```json
{
  "status": "ready",
  "service": "cortex-orchestrator"
}
```

### GET /status
Detailed status endpoint.

**Response:**
```json
{
  "status": "running",
  "service": "cortex-orchestrator",
  "monitoring": "active"
}
```

## MCP Tool REST API Endpoints

All tool endpoints are POST requests.

### POST /tools/get_orchestration_status

Get overall orchestration status including active agents, capacity, and health.

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/get_orchestration_status
```

**Response:**
```json
{
  "active_agents": 0,
  "capacity_limit": 28,
  "headroom": 28,
  "current_spawn_rate": 10.0,
  "stuck_pods": 0,
  "queued_tasks": 0,
  "health": "healthy",
  "recommendations": [],
  "timestamp": "2026-01-10T20:32:02.505641"
}
```

### POST /tools/calculate_current_limit

Get current dynamic pod limit based on cluster capacity.

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/calculate_current_limit
```

**Response:**
```json
{
  "current_count": 0,
  "calculated_limit": 28,
  "limiting_resource": "cpu",
  "headroom": 28,
  "stability_factor": 1.0,
  "can_scale_up": true,
  "recommendation": "Significant headroom available. Can handle burst workloads."
}
```

### POST /tools/calculate_spawn_rate

Get current spawn rate and backpressure signals.

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/calculate_spawn_rate
```

**Response:**
```json
{
  "current_rate": 10.0,
  "base_rate": 10,
  "backpressure": [
    {
      "name": "cpu_headroom",
      "value": 1.0,
      "reason": "CPU headroom at 50% (target: 30%)"
    },
    {
      "name": "pending_pressure",
      "value": 1.0,
      "reason": "0 pods pending (target: <50)"
    },
    {
      "name": "failure_rate",
      "value": 1.0,
      "reason": "No recent failures"
    },
    {
      "name": "api_latency",
      "value": 1.0,
      "reason": "API latency normal (0ms)"
    }
  ]
}
```

### POST /tools/get_stuck_pods

Get list of stuck/unhealthy pods that may need intervention.

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/get_stuck_pods
```

**Response:**
```json
{
  "count": 0,
  "pods": []
}
```

When pods are stuck:
```json
{
  "count": 2,
  "pods": [
    {
      "name": "agent-xyz-123",
      "score": 0.3,
      "stuck_duration": 300,
      "signals": {
        "k8s_ready": false,
        "recent_logs": true,
        "cpu_activity": false,
        "network_activity": false,
        "task_progress": false
      }
    }
  ]
}
```

### POST /tools/pause_spawning

Pause all agent spawning (emergency brake).

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/pause_spawning \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual pause for maintenance"}'
```

**Response:**
```json
{
  "paused": true,
  "reason": "Manual pause for maintenance"
}
```

### POST /tools/resume_spawning

Resume agent spawning after pause.

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/resume_spawning
```

**Response:**
```json
{
  "resumed": true,
  "current_rate": 10.0
}
```

### POST /tools/get_queue_depth

Get current spawn queue depth.

**Request:**
```bash
curl -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/get_queue_depth
```

**Response:**
```json
{
  "queue_depth": 0
}
```

## Testing from Within the Cluster

Use a curl pod to test:

```bash
kubectl run test-api --rm -i --restart=Never --image=curlimages/curl:latest -n cortex-system -- \
  curl -s -X POST http://cortex-orchestrator.cortex-system.svc.cluster.local:8080/tools/get_orchestration_status
```

## Integration Example

Example of using the REST API from another service:

```python
import httpx

ORCHESTRATOR_URL = "http://cortex-orchestrator.cortex-system.svc.cluster.local:8080"

async def check_orchestrator_health():
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{ORCHESTRATOR_URL}/tools/get_orchestration_status")
        status = response.json()

        if status["health"] != "healthy":
            print(f"Warning: Orchestrator health is {status['health']}")
            print(f"Active agents: {status['active_agents']}/{status['capacity_limit']}")
            print(f"Stuck pods: {status['stuck_pods']}")

        return status
```

## Error Handling

All endpoints return HTTP 500 with error details on failure:

```json
{
  "error": "Error message details"
}
```

## Metrics

Prometheus metrics are available on port 9090 at `/metrics`.

## Build Information

- **Source**: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex-orchestrator`
- **Image**: `10.43.170.72:5000/cortex-orchestrator:latest`
- **Namespace**: `cortex-system`
- **Service**: `cortex-orchestrator.cortex-system.svc.cluster.local`
- **Ports**:
  - 8080 (HTTP/REST API)
  - 9090 (Prometheus metrics)

## Deployment

Built using buildah in-cluster build job. See `/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-orchestrator/build-and-deploy.sh` for build script.

To rebuild and redeploy:
```bash
/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-orchestrator/build-and-deploy.sh
```
