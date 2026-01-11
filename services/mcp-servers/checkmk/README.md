# CheckMK MCP Server

Infrastructure monitoring integration for Cortex through CheckMK REST API.

## Overview

The CheckMK MCP Server exposes CheckMK's monitoring capabilities through the Model Context Protocol (MCP), enabling Claude Code to query infrastructure health, service status, and current problems across all monitored systems.

## Features

- **Host Monitoring**: Query status of all monitored hosts
- **Service Monitoring**: Check service states and performance
- **Problem Detection**: Identify current issues across infrastructure
- **Real-time Status**: Get up-to-date monitoring information

## MCP Tools

### System Tools
- `checkmk_get_version` - Get CheckMK version and site information

### Host Tools
- `checkmk_list_hosts` - List all monitored hosts with status
- `checkmk_get_host` - Get details for a specific host
- `checkmk_get_host_problems` - Get problems for a specific host

### Service Tools
- `checkmk_get_host_services` - Get all services for a specific host

### Problem/Alert Tools
- `checkmk_get_all_problems` - Get all current problems (non-OK services and down hosts)

## Configuration

Environment variables:

- `CHECKMK_HOST` - CheckMK server hostname (default: checkmk.ry-ops.dev)
- `CHECKMK_SITE` - CheckMK site name (default: cmk)
- `CHECKMK_USERNAME` - Automation user username
- `CHECKMK_PASSWORD` - Automation user password/secret
- `CHECKMK_VERIFY_SSL` - Verify SSL certificates (default: false)
- `CHECKMK_TIMEOUT` - HTTP request timeout in seconds (default: 30)

## Deployment

Deployed via GitOps in cortex-system namespace:
- Service: `checkmk-mcp-server` on port 3000
- Health endpoint: `/health`
- MCP endpoint: `/` (POST with JSON-RPC 2.0)

## CheckMK Setup

1. Create automation user in CheckMK:
   - Setup > Users > Add user
   - Type: Automation user
   - Username: `cortex-automation`
   - Generate automation secret
   - Permissions: Read-only monitoring access

2. Test API access:
   ```bash
   curl -H "Authorization: Bearer cortex-automation {secret}" \
     http://checkmk.ry-ops.dev/cmk/check_mk/api/1.0/version
   ```

## Usage Examples

### List all hosts
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "checkmk_list_hosts",
    "arguments": {
      "summary": true
    }
  }
}
```

### Get current problems
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "checkmk_get_all_problems",
    "arguments": {}
  }
}
```

### Check specific host services
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "checkmk_get_host_services",
    "arguments": {
      "host_name": "k3s-node01",
      "summary": true
    }
  }
}
```

## Architecture

- **Python 3.11** base image
- **MCP HTTP wrapper** for JSON-RPC 2.0 endpoint
- **httpx** for async HTTP client
- **Pydantic** for configuration validation

## Integration

The CheckMK MCP server integrates with:
- **Cortex MCP Gateway** (cortex-mcp-server)
- **MoE Router** with CheckMK-specific keywords
- **ArgoCD** for GitOps deployment

## Keywords for MoE Routing

The MoE router will route queries containing these keywords to CheckMK:
- checkmk, monitoring, host, service, alert, problem, status, health, uptime, performance, metric

## API Reference

CheckMK REST API base URL:
```
http://checkmk.ry-ops.dev/{site}/check_mk/api/1.0
```

Key endpoints used:
- `/version` - Version information
- `/domain-types/host/collections/all` - All hosts with status
- `/objects/host/{host_name}` - Specific host details
- `/objects/host/{host_name}/collections/services` - Services for host

Authentication:
```
Authorization: Bearer {username} {password}
```

## Development

Run locally:
```bash
export CHECKMK_HOST=checkmk.ry-ops.dev
export CHECKMK_SITE=cmk
export CHECKMK_USERNAME=automation
export CHECKMK_PASSWORD=your-secret

python -m mcp_checkmk.server
```

## License

Part of the Cortex infrastructure platform.
