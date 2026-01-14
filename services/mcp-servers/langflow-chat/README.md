# Langflow Chat MCP Server

Routes chat messages to appropriate Langflow workflows based on intent detection.

## Features

- Pattern-based intent detection
- Automatic routing to Langflow workflows
- Support for 10+ workflow types
- Session management
- Configurable workflow mappings

## Workflow Mapping

| Intent | Trigger Patterns | Workflow | Description |
|--------|-----------------|----------|-------------|
| daily_brief | hello, hi, hey, greetings | workflow-11 | Daily status brief |
| k8s_health | kubernetes, k8s, pods, cluster | workflow-1 | K8s monitoring |
| security_scan | security, vulnerability, cve | workflow-3 | Security scanning |
| cost_analysis | cost, spending, budget | workflow-6 | Cost tracking |
| log_analysis | log, error, anomaly | workflow-8 | Log analysis |
| deployment_check | deploy, release, rollout | workflow-7 | Deployment validation |
| service_health | health, status, dashboard | workflow-9 | Service health |
| infrastructure | proxmox, vm, server | workflow-2 | Infrastructure status |
| alert_analysis | alert, notification, warning | workflow-5 | Alert categorization |
| documentation | documentation, docs, readme | workflow-10 | Auto-docs |

## Tools

### `chat`
Route a chat message to the appropriate workflow.

**Input**:
```json
{
  "message": "hello",
  "session_id": "user-123"
}
```

**Output**:
```json
{
  "response": "Daily brief with weather and infrastructure status...",
  "intent": "daily_brief",
  "workflow": "Daily status brief with weather and infrastructure",
  "flow_id": "abc123"
}
```

### `get_workflows`
List all available workflows and their configuration status.

**Output**:
```json
{
  "daily_brief": {
    "description": "Daily status brief with weather and infrastructure",
    "patterns": ["\\b(hello|hi|hey)\\b"],
    "flow_id": "abc123",
    "configured": true
  },
  ...
}
```

### `set_workflow_id`
Configure a workflow's Langflow flow ID.

**Input**:
```json
{
  "workflow_name": "daily_brief",
  "flow_id": "abc123def456"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFLOW_URL` | Langflow API base URL | `http://langflow.cortex-system.svc.cluster.local:7860` |
| `LANGFLOW_API_KEY` | Langflow API key | None |
| `ANTHROPIC_API_KEY` | Claude API key (for workflows) | None |

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langflow-chat-mcp-server
  namespace: cortex-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: langflow-chat-mcp-server
  template:
    metadata:
      labels:
        app: langflow-chat-mcp-server
    spec:
      containers:
      - name: server
        image: 10.43.170.72:5000/langflow-chat-mcp-server:latest
        ports:
        - containerPort: 3000
        env:
        - name: LANGFLOW_URL
          value: "http://langflow.cortex-system.svc.cluster.local:7860"
        - name: LANGFLOW_API_KEY
          valueFrom:
            secretKeyRef:
              name: langflow-global-vars
              key: LANGFLOW_STORE_API_KEY
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: langflow-global-vars
              key: ANTHROPIC_API_KEY
```

## Usage Flow

```
User: "hello"
    ↓
Chat Backend
    ↓
Langflow Chat MCP Server
    ↓
Intent Detection → "daily_brief"
    ↓
Route to Langflow workflow-11
    ↓
Langflow executes workflow:
  - Fetch Duluth weather
  - Query K8s cluster
  - Query Proxmox
  - Query UniFi
  - Query Sandfly
  - Generate brief with Claude
    ↓
Return comprehensive daily status
    ↓
Chat Backend → User
```

## Configuration After Deployment

After deploying and importing workflows into Langflow, configure the flow IDs:

```bash
# Get flow IDs from Langflow UI or API
# Then call set_workflow_id for each:

curl -X POST http://langflow-chat-mcp-server:3000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "set_workflow_id",
      "arguments": {
        "workflow_name": "daily_brief",
        "flow_id": "YOUR_FLOW_ID_HERE"
      }
    },
    "id": 1
  }'
```

## Development

```bash
# Install dependencies
cd services/mcp-servers/langflow-chat
pip install -e ".[dev]"

# Run locally
python -m mcp_langflow_chat.server

# Run tests
pytest
```

## Architecture

This MCP server acts as a bridge between Cortex Chat and Langflow:

- **Intent Detection**: Uses regex patterns to determine user intent
- **Workflow Routing**: Maps intents to specific Langflow workflows
- **Session Management**: Maintains conversation context
- **Error Handling**: Graceful fallbacks if workflows aren't configured

## Integration with Chat Backend

Update chat backend to use this MCP server:

```yaml
# In cortex-chat-backend-simple-deployment.yaml
env:
- name: CORTEX_URL
  value: http://langflow-chat-mcp-server.cortex-system.svc.cluster.local:3000
```

The chat backend will call this MCP server, which routes to Langflow workflows.
