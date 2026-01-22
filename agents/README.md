# Cortex Agent Framework

A Python-first agent framework for building agentic AI systems with Claude.

## Overview

The Cortex Agent Framework provides a clean abstraction for building multi-agent systems where:
- **Masters** orchestrate work by spawning and routing tasks to workers
- **Workers** execute tasks via Claude API conversations with MCP tool integration
- **Redis Streams** provides reliable inter-agent messaging
- **Full async/await** support with asyncio throughout

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Coordinator Master                     │
│   (Top-level routing & orchestration)            │
└──────────────┬──────────────────────────────────┘
               │
               ├─────────────┬─────────────┐
               ▼             ▼             ▼
      ┌───────────────┐ ┌──────────┐ ┌──────────┐
      │Security Master│ │Infra...  │ │Other...  │
      │  (Division GM)│ │          │ │          │
      └───────┬───────┘ └──────────┘ └──────────┘
              │
              ├──────────────┬────────────┐
              ▼              ▼            ▼
      ┌────────────┐  ┌──────────┐  ┌──────────┐
      │  Sandfly   │  │ GitHub   │  │  Other   │
      │  Worker    │  │ Security │  │ Workers  │
      │            │  │ Worker   │  │          │
      └────────────┘  └──────────┘  └──────────┘
           │                │             │
           └────────────────┴─────────────┘
                          │
                          ▼
                  ┌──────────────┐
                  │  Claude API  │
                  │ (Anthropic)  │
                  └──────────────┘
```

### Key Concepts

1. **Masters Don't Talk to Claude** - Masters route tasks and manage workers. They don't make API calls to Claude.

2. **Workers Are the AI Agents** - Workers receive tasks and use Claude API to accomplish them, optionally using MCP tools.

3. **Redis Streams for Messaging** - All inter-agent communication happens via Redis Streams for reliability and observability.

4. **Registry Tracks Everything** - All agents register themselves with heartbeats for health monitoring.

5. **Lifecycle Management** - Masters can spawn workers as subprocesses (dev) or Kubernetes Jobs (prod).

## Core Components

### 1. Messaging Layer (`messaging.py`)

Redis Streams-based messaging for agent communication.

```python
from agents.messaging import MessageBroker, AgentMessage, MessagePriority

# Initialize broker
broker = MessageBroker(redis_url="redis://localhost:6379")
await broker.connect()

# Publish a message
message = AgentMessage(
    stream="agent:tasks:sandfly-worker",
    sender="security-master",
    recipient="sandfly-worker-001",
    task_type="scan_host",
    payload={"host_id": "web-01"},
    priority=MessagePriority.HIGH,
)
await broker.publish(message)

# Consume messages with consumer groups
async for msg in broker.consume(
    stream="agent:tasks:sandfly-worker",
    group="sandfly-group",
    consumer="worker-001",
):
    print(f"Received: {msg.task_type}")
    await broker.ack(msg.stream, "sandfly-group", msg.message_id)
```

### 2. Agent Registry (`registry.py`)

Track all active agents with health monitoring.

```python
from agents.registry import AgentRegistry, AgentInfo, AgentType, AgentStatus

registry = AgentRegistry(redis_url="redis://localhost:6379")
await registry.connect()

# Register an agent
agent_info = AgentInfo(
    agent_id="sandfly-worker-001",
    agent_type=AgentType.WORKER,
    name="Sandfly Security Worker",
    status=AgentStatus.READY,
    capabilities=["sandfly_api", "threat_analysis"],
    stream="agent:tasks:sandfly-worker-001",
)
await registry.register(agent_info)

# Send heartbeats
await registry.heartbeat("sandfly-worker-001")

# Find workers by capability
workers = await registry.find_workers_by_capability("sandfly_api")
```

### 3. Lifecycle Management (`lifecycle.py`)

Spawn and manage worker processes.

```python
from agents.lifecycle import AgentLifecycle, SpawnMode

# Subprocess mode (development)
lifecycle = AgentLifecycle(spawn_mode=SpawnMode.SUBPROCESS)

await lifecycle.spawn_worker(
    agent_id="sandfly-worker-001",
    worker_class="workers.sandfly_worker",
    env_vars={"SANDFLY_API_URL": "http://sandfly-api"},
)

# Kubernetes mode (production)
lifecycle_k8s = AgentLifecycle(
    spawn_mode=SpawnMode.KUBERNETES,
    namespace="cortex-system",
)

await lifecycle_k8s.spawn_worker(
    agent_id="sandfly-worker-001",
    worker_class="workers.sandfly_worker",
    image="cortex/sandfly-worker:latest",
    cpu_request="100m",
    memory_request="256Mi",
)
```

### 4. Base Master (`base_master.py`)

Abstract base class for master agents.

```python
from agents.base_master import BaseMaster

class MyMaster(BaseMaster):
    def get_capabilities(self):
        return ["task_routing", "orchestration"]

    async def route_task(self, message):
        # Determine which worker should handle this task
        if "security" in message.task_type:
            return await self.find_available_worker("security_operations")
        return None

    async def process_result(self, message):
        # Handle results from workers
        print(f"Result: {message.payload}")

# Run the master
master = MyMaster(agent_id="my-master", name="My Master")
await master.start()
```

### 5. Base Worker (`base_worker.py`)

Abstract base class for worker agents.

```python
from agents.base_worker import BaseWorker

class MyWorker(BaseWorker):
    def get_capabilities(self):
        return ["my_capability"]

    def get_system_prompt(self):
        return "You are a helpful assistant that..."

    async def process_task(self, message):
        # Use Claude to accomplish the task
        response = await self.ask_claude(
            f"Please help with: {message.payload}"
        )
        return {"result": response}

# Run the worker
worker = MyWorker(
    agent_id="my-worker-001",
    name="My Worker",
    master_id="my-master",
)
await worker.start()
```

## Example: Security Division

### Security Master

Routes security tasks to specialized workers:

```python
from masters.security_master import SecurityMaster

master = SecurityMaster(redis_url="redis://localhost:6379")
await master.start()

# Master spawns workers and routes tasks
# - Sandfly tasks → Sandfly workers
# - GitHub tasks → GitHub Security workers
# - Escalates critical findings to coordinator
```

### Sandfly Worker

Analyzes Linux security findings using Claude:

```python
from workers.sandfly_worker import SandflyWorker

worker = SandflyWorker(
    redis_url="redis://localhost:6379",
    anthropic_api_key="sk-ant-...",
)
await worker.start()

# Worker receives tasks like:
# {
#   "task_type": "scan_host",
#   "payload": {"host_id": "web-01"}
# }
#
# Then uses Claude + MCP tools to:
# 1. Query Sandfly API for findings
# 2. Analyze threats with Claude
# 3. Generate remediation recommendations
# 4. Return results to master
```

## Development Workflow

### 1. Install Dependencies

```bash
cd ~/Projects/cortex-platform/agents
pip install -r requirements.txt
```

### 2. Run Tests

```bash
pytest tests/agents/ -v --cov=agents
```

### 3. Create a New Worker

1. Create `workers/my_worker.py`:

```python
from agents.base_worker import BaseWorker

class MyWorker(BaseWorker):
    def get_capabilities(self):
        return ["my_capability"]

    def get_system_prompt(self):
        return "You are..."

    async def process_task(self, message):
        # Your task processing logic
        response = await self.ask_claude("...")
        return {"result": response}

if __name__ == "__main__":
    import asyncio
    worker = MyWorker(
        agent_id=os.getenv("AGENT_ID", "my-worker-001"),
        name="My Worker",
        master_id=os.getenv("MASTER_ID", "coordinator-master"),
    )
    asyncio.run(worker.start())
```

2. Register in `workers/__init__.py`
3. Update master routing logic
4. Write tests in `tests/agents/test_my_worker.py`

### 4. Create a New Master

1. Create `masters/my_master.py`:

```python
from agents.base_master import BaseMaster

class MyMaster(BaseMaster):
    def get_capabilities(self):
        return ["my_routing"]

    async def route_task(self, message):
        # Routing logic
        worker_id = await self.find_available_worker("my_capability")
        return worker_id

    async def process_result(self, message):
        # Result handling
        pass

if __name__ == "__main__":
    import asyncio
    master = MyMaster(agent_id="my-master", name="My Master")
    asyncio.run(master.start())
```

## Production Deployment

### 1. Build Container Images

```dockerfile
# Dockerfile for worker
FROM python:3.11-slim
WORKDIR /app
COPY agents/ /app/agents/
COPY workers/ /app/workers/
COPY requirements.txt /app/
RUN pip install -r requirements.txt
CMD ["python", "-m", "workers.my_worker"]
```

### 2. Deploy with GitOps

Add to `~/cortex-gitops/apps/cortex-system/`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-worker
  namespace: cortex-system
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-worker
  template:
    metadata:
      labels:
        app: my-worker
    spec:
      containers:
      - name: worker
        image: cortex/my-worker:latest
        env:
        - name: AGENT_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: REDIS_URL
          value: "redis://redis.cortex-system.svc.cluster.local:6379"
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: anthropic-api-key
              key: key
        resources:
          requests:
            cpu: "100m"
            memory: "256Mi"
```

### 3. Monitor Agents

Query the registry:

```python
registry = AgentRegistry(redis_url="redis://...")
await registry.connect()

# List all agents
agents = await registry.list_agents()
for agent in agents:
    print(f"{agent.name}: {agent.status}")

# Find unhealthy agents
unhealthy = await registry.list_agents(status=AgentStatus.UNHEALTHY)
```

## Best Practices

### 1. Error Handling

Always wrap task processing in try/except:

```python
async def process_task(self, message):
    try:
        result = await self.ask_claude(...)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Task failed: {e}")
        return {"success": False, "error": str(e)}
```

### 2. Conversation Management

Clear conversation history between unrelated tasks:

```python
async def process_task(self, message):
    # Clear previous context
    self.clear_conversation()

    # Fresh conversation for this task
    response = await self.ask_claude(...)
```

### 3. Heartbeats

Always implement heartbeat loops:

```python
async def _heartbeat_loop(self):
    while self._running:
        await self.registry.heartbeat(self.agent_id)
        await asyncio.sleep(30)
```

### 4. Graceful Shutdown

Handle SIGTERM/SIGINT properly:

```python
import signal

def signal_handler(sig, frame):
    asyncio.create_task(worker.stop())

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

### 5. Resource Limits

Set appropriate CPU/memory limits in production:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "256Mi"
  limits:
    cpu: "500m"
    memory: "1Gi"
```

## Troubleshooting

### Workers Not Receiving Tasks

1. Check stream name matches: `agent:tasks:{agent_id}`
2. Verify consumer group exists
3. Check Redis connectivity

```python
# Debug messaging
broker = MessageBroker(redis_url="...")
await broker.connect()
info = await broker.get_stream_info("agent:tasks:my-worker")
print(info)
```

### Stale Agents in Registry

Clean up manually:

```python
registry = AgentRegistry(redis_url="...")
await registry.connect()
stale_count = await registry.cleanup_stale_agents()
print(f"Cleaned up {stale_count} stale agents")
```

### Worker Spawn Failures

Check logs:

```bash
# Subprocess mode
tail -f /tmp/worker-*.log

# Kubernetes mode
kubectl logs -n cortex-system -l app=my-worker
```

## Testing

Run the full test suite:

```bash
# All tests
pytest tests/agents/ -v

# With coverage
pytest tests/agents/ --cov=agents --cov-report=html

# Specific test file
pytest tests/agents/test_messaging.py -v

# Async tests only
pytest tests/agents/ -k "async" -v
```

## Future Enhancements

1. **Circuit Breakers** - Prevent cascading failures
2. **Rate Limiting** - Protect Claude API quota
3. **Distributed Tracing** - OpenTelemetry integration
4. **Metrics** - Prometheus metrics for observability
5. **Dead Letter Queue** - Handle failed tasks
6. **Task Prioritization** - Priority-based scheduling
7. **Multi-turn Conversations** - Persistent conversation state
8. **Tool Result Caching** - Cache expensive MCP tool calls

## Contributing

1. Write tests for all new features
2. Follow existing code structure
3. Update this README
4. Use type hints throughout
5. Run `ruff` for linting

## License

MIT

## Contact

Built for Cortex - AI Infrastructure Orchestration
Project Repository: https://github.com/ry-ops/cortex-platform
