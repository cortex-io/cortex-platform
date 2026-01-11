# n8n MCP Server

Model Context Protocol (MCP) server for n8n workflow automation integration with Cortex.

## Overview

This MCP server exposes n8n's workflow automation capabilities through the Model Context Protocol, allowing AI agents to:

- List and inspect workflows
- Execute workflows programmatically
- Monitor workflow executions
- Check execution status and results

## Configuration

Configure via environment variables:

```bash
N8N_HOST=n8n.ry-ops.dev          # n8n server hostname
N8N_PORT=5678                     # n8n server port
N8N_API_KEY=your-api-key         # n8n API key (required)
N8N_VERIFY_SSL=false             # SSL verification (default: false)
N8N_TIMEOUT=30                   # Request timeout in seconds
```

## Available Tools

### Workflow Management

- **n8n_list_workflows** - List all workflows with their status
  - Optional filter by active status
  - Returns workflow names, IDs, and tags

- **n8n_get_workflow** - Get detailed workflow information
  - Shows workflow nodes and configuration
  - Displays creation and update timestamps

- **n8n_execute_workflow** - Trigger workflow execution
  - Activates workflows
  - Supports passing input data

### Execution Monitoring

- **n8n_list_executions** - List recent workflow executions
  - Filter by workflow ID or status
  - Shows success/error/running counts
  - Configurable result limit

- **n8n_get_execution** - Get detailed execution information
  - Shows execution status and timing
  - Includes execution data and results

## Installation

```bash
cd /Users/ryandahlberg/Projects/cortex-platform/services/mcp-servers/n8n
pip install -e .
```

## Usage

### Standalone Mode

```bash
n8n-mcp
```

### As MCP Server

Configure in your MCP client:

```json
{
  "mcpServers": {
    "n8n": {
      "command": "n8n-mcp",
      "env": {
        "N8N_HOST": "n8n.ry-ops.dev",
        "N8N_PORT": "5678",
        "N8N_API_KEY": "your-api-key"
      }
    }
  }
}
```

## API Access

### n8n API Setup

1. Access n8n at http://n8n.ry-ops.dev:5678
2. Go to Settings > API
3. Generate an API key
4. Use the API key in the N8N_API_KEY environment variable

### API Documentation

n8n API documentation: https://docs.n8n.io/api/

Key endpoints used:
- `GET /api/v1/workflows` - List workflows
- `GET /api/v1/workflows/{id}` - Get workflow details
- `POST /api/v1/workflows/{id}/activate` - Activate workflow
- `GET /api/v1/executions` - List executions
- `GET /api/v1/executions/{id}` - Get execution details

## Architecture

```
┌─────────────────────┐
│   Cortex Agents     │
│                     │
│  (MCP Clients)      │
└──────────┬──────────┘
           │
           │ MCP Protocol
           │
┌──────────▼──────────┐
│   n8n MCP Server    │
│                     │
│  - Tool handlers    │
│  - Error handling   │
│  - Response format  │
└──────────┬──────────┘
           │
           │ HTTP/REST
           │
┌──────────▼──────────┐
│    n8n Instance     │
│                     │
│  n8n.ry-ops.dev     │
│  Port 5678          │
└─────────────────────┘
```

## Deployment

This server is deployed as a Kubernetes pod in the cortex-system namespace:

```bash
# Check deployment status
kubectl get pods -n cortex-system -l app=n8n-mcp

# View logs
kubectl logs -n cortex-system -l app=n8n-mcp

# Check service
kubectl get svc -n cortex-system n8n-mcp
```

## Development

### Local Testing

```bash
# Set environment variables
export N8N_HOST=n8n.ry-ops.dev
export N8N_PORT=5678
export N8N_API_KEY=your-api-key

# Run server
python -m mcp_n8n.server
```

### Adding New Tools

1. Add tool definition in `list_tools()`
2. Implement handler in `call_tool()`
3. Add error handling with `@handle_errors`
4. Update this README

## Notes

- The server uses HTTP (not HTTPS) for internal cluster communication
- SSL verification is disabled by default for self-signed certificates
- API key authentication is required for all requests
- Webhook-based workflows need to be triggered via their webhook URL
- Manual workflows should be executed through the n8n UI

## Related Documentation

- [n8n Documentation](https://docs.n8n.io/)
- [MCP Specification](https://github.com/anthropics/mcp)
- [Cortex Platform Documentation](../../README.md)
