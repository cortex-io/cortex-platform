# Cortex Agent Framework - Quick Start

Get up and running with the Cortex Agent Framework in 5 minutes.

## Prerequisites

- Python 3.11+
- Redis 7.0+
- Anthropic API key

## Installation

### 1. Install Dependencies

```bash
cd ~/Projects/cortex-platform
pip install -r agents/requirements.txt
```

### 2. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7

# Or using local Redis
redis-server
```

### 3. Set Environment Variables

```bash
export REDIS_URL="redis://localhost:6379"
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

## Run Tests

Verify everything works:

```bash
pytest tests/agents/ -v
```

Expected output:
```
tests/agents/test_messaging.py::TestAgentMessage::test_message_creation PASSED
tests/agents/test_messaging.py::TestAgentMessage::test_message_to_dict PASSED
tests/agents/test_registry.py::TestAgentRegistry::test_register_agent PASSED
...
==================== 15 passed in 2.34s ====================
```

## Run Demo

Experience the full agent lifecycle:

```bash
python examples/agent_demo.py
```

This demo:
1. Starts coordinator master
2. Spawns security master
3. Spawns Sandfly worker
4. Sends a task through the chain
5. Worker uses Claude API to process the task

## Create Your First Worker

### 1. Create the Worker File

`workers/my_worker.py`:

```python
from agents.base_worker import BaseWorker

class MyWorker(BaseWorker):
    def get_capabilities(self):
        return ["my_capability"]

    def get_system_prompt(self):
        return "You are a helpful assistant."

    async def process_task(self, message):
        # Use Claude to process the task
        response = await self.ask_claude(
            f"Help me with: {message.payload}"
        )
        return {"result": response}

if __name__ == "__main__":
    import asyncio
    import os

    worker = MyWorker(
        agent_id=os.getenv("AGENT_ID", "my-worker-001"),
        name="My Worker",
        master_id=os.getenv("MASTER_ID", "coordinator-master"),
    )
    asyncio.run(worker.start())
```

### 2. Register It

`workers/__init__.py`:

```python
from workers.my_worker import MyWorker

__all__ = ["MyWorker", ...]
```

### 3. Run It

```bash
export AGENT_ID="my-worker-001"
export MASTER_ID="coordinator-master"
python -m workers.my_worker
```

## Create Your First Master

### 1. Create the Master File

`masters/my_master.py`:

```python
from agents.base_master import BaseMaster

class MyMaster(BaseMaster):
    def get_capabilities(self):
        return ["task_routing"]

    async def route_task(self, message):
        # Find a worker with the capability
        worker_id = await self.find_available_worker("my_capability")
        return worker_id

    async def process_result(self, message):
        # Handle results from workers
        print(f"Result: {message.payload}")

if __name__ == "__main__":
    import asyncio

    master = MyMaster(
        agent_id="my-master",
        name="My Master"
    )
    asyncio.run(master.start())
```

### 2. Run It

```bash
python -m masters.my_master
```

## Send a Task

```python
from agents.messaging import MessageBroker, AgentMessage

async def send_task():
    broker = MessageBroker(redis_url="redis://localhost:6379")
    await broker.connect()

    message = AgentMessage(
        stream="agent:tasks:my-master",
        sender="client",
        recipient="my-master",
        task_type="process_data",
        payload={"data": "important data"},
    )

    await broker.publish(message)
    await broker.disconnect()

import asyncio
asyncio.run(send_task())
```

## Monitor Agents

```python
from agents.registry import AgentRegistry

async def list_agents():
    registry = AgentRegistry(redis_url="redis://localhost:6379")
    await registry.connect()

    agents = await registry.list_agents()
    for agent in agents:
        print(f"{agent.name}: {agent.status.value}")

    await registry.disconnect()

import asyncio
asyncio.run(list_agents())
```

## Next Steps

1. **Read the full documentation**: `agents/README.md`
2. **Study the examples**: `workers/sandfly_worker.py`, `masters/security_master.py`
3. **Write tests**: `tests/agents/test_my_worker.py`
4. **Deploy to Kubernetes**: See `AGENT_FRAMEWORK.md` for deployment guide

## Troubleshooting

### Redis Connection Error

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

Solution: Make sure Redis is running on localhost:6379

### Import Error

```
ModuleNotFoundError: No module named 'agents'
```

Solution: Run Python from the cortex-platform directory or add to PYTHONPATH:
```bash
export PYTHONPATH="$PYTHONPATH:~/Projects/cortex-platform"
```

### Anthropic API Error

```
anthropic.AuthenticationError: Invalid API key
```

Solution: Check your ANTHROPIC_API_KEY environment variable

## Resources

- **Full Documentation**: `/Users/ryandahlberg/Projects/cortex-platform/agents/README.md`
- **Framework Overview**: `/Users/ryandahlberg/Projects/cortex-platform/AGENT_FRAMEWORK.md`
- **Example Demo**: `/Users/ryandahlberg/Projects/cortex-platform/examples/agent_demo.py`
- **Tests**: `/Users/ryandahlberg/Projects/cortex-platform/tests/agents/`

## Support

For questions or issues, check:
- Framework README for detailed API documentation
- Test files for usage examples
- Demo script for complete working example

---

**Happy agent building!** 🤖
