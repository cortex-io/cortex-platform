# Cortex MCP Server - Usage Examples

## JSON-RPC 2.0 Protocol Examples

All communication follows JSON-RPC 2.0 over stdin/stdout.

### 1. Initialize Connection

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "clientInfo": {
      "name": "claude-desktop",
      "version": "1.0.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": {
      "name": "cortex-mcp-server",
      "version": "1.0.0"
    },
    "capabilities": {
      "tools": {}
    }
  }
}
```

### 2. List Available Tools

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "cortex_query",
        "description": "Query any Cortex subsystem (UniFi, Proxmox, Wazuh, Kubernetes)...",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "Natural language query..."
            },
            "system": {
              "type": "string",
              "enum": ["auto", "unifi", "proxmox", "wazuh", "k8s"],
              "default": "auto"
            }
          },
          "required": ["query"]
        }
      },
      {
        "name": "cortex_get_status",
        "description": "Get real-time status of all Cortex operations...",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    ]
  }
}
```

### 3. Query UniFi Network (Auto Routing)

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "cortex_query",
    "arguments": {
      "query": "Show me all WiFi clients connected to the network",
      "system": "auto"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"success\":true,\"data\":{\"clients\":[...]},\"routing\":{\"target_system\":\"unifi\",\"routing_mode\":\"automatic\",\"routing_info\":{\"action\":\"force\",\"confidence\":1.0}}}"
      }
    ]
  }
}
```

### 4. Query Proxmox VMs (Manual System)

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "cortex_query",
    "arguments": {
      "query": "List all running virtual machines",
      "system": "proxmox"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"success\":true,\"data\":{\"vms\":[...]},\"routing\":{\"target_system\":\"proxmox\",\"routing_mode\":\"manual\"}}"
      }
    ]
  }
}
```

### 5. Check Wazuh Security Alerts

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "cortex_query",
    "arguments": {
      "query": "What security alerts have been triggered in the last 24 hours?",
      "system": "auto"
    }
  }
}
```

**Console Output (stderr):**
```
[Cortex Query] MoE Router: force routing to wazuh (confidence: 1.0)
[Cortex Query] Reason: Matched keywords: security, alert
```

### 6. Query Kubernetes Cluster

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "cortex_query",
    "arguments": {
      "query": "List all pods in the cortex-system namespace",
      "system": "auto"
    }
  }
}
```

### 7. Get Cortex Status

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "cortex_get_status",
    "arguments": {}
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"success\":true,\"status\":{\"timestamp\":\"2025-12-24T19:00:00Z\",\"mcp_servers\":{\"unifi\":\"healthy\",\"proxmox\":\"healthy\",\"wazuh\":\"healthy\",\"k8s\":\"healthy\"},\"cortex_operations\":{\"active_workers\":0,\"active_masters\":1,\"running_tasks\":0},\"overall_health\":\"healthy\"}}"
      }
    ]
  }
}
```

## Routing Examples

### High Confidence (Force Route)

**Query:** "Show me UniFi access points"
- **Matched Keywords:** unifi, access point
- **Confidence:** 2.0 (200/100)
- **Action:** Force route to UniFi
- **System:** unifi

**Query:** "What VMs are running on Proxmox?"
- **Matched Keywords:** vm, proxmox
- **Confidence:** 2.0
- **Action:** Force route to Proxmox
- **System:** proxmox

### Moderate Confidence (Suggest Route)

**Query:** "Show me network statistics"
- **Matched Keywords:** network
- **Confidence:** 1.0
- **Action:** Force route (single strong match)
- **System:** unifi

### Low Confidence (No Route)

**Query:** "What is the current time?"
- **Matched Keywords:** (none)
- **Confidence:** 0.0
- **Action:** None
- **Error:** "Could not determine target system from query"

### Multi-System Match

**Query:** "Show me network security alerts"
- **Matched Keywords:**
  - unifi: network
  - wazuh: security, alert
- **Top Match:** wazuh (confidence: 2.0)
- **System:** wazuh

## Error Handling

### Unknown Tool

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "unknown_tool",
    "arguments": {}
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "error": {
    "code": -32601,
    "message": "Unknown tool: unknown_tool",
    "data": {
      "available_tools": ["cortex_query", "cortex_get_status"]
    }
  }
}
```

### Tool Execution Failure

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "error": {
    "code": -32603,
    "message": "Tool execution failed: Connection refused",
    "data": {
      "tool": "cortex_query",
      "error": "..."
    }
  }
}
```

## Testing with curl (HTTP mode - future)

```bash
# When HTTP transport is implemented:
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "cortex_query",
      "arguments": {
        "query": "Show WiFi networks",
        "system": "auto"
      }
    }
  }'
```

## Integration with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "node",
      "args": ["/tmp/cortex-mcp-server/src/index.js"],
      "env": {
        "UNIFI_MCP_URL": "http://unifi-mcp-server.cortex-system.svc.cluster.local:3000",
        "PROXMOX_MCP_URL": "http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000",
        "WAZUH_MCP_URL": "http://wazuh-mcp-server.cortex-system.svc.cluster.local:8080"
      }
    }
  }
}
```

Then use in Claude:

```
User: "What WiFi networks are available?"
Claude: [Uses cortex_query tool with auto routing]

User: "Show me Proxmox VM status"
Claude: [Uses cortex_query tool, routes to Proxmox]

User: "What's the overall system status?"
Claude: [Uses cortex_get_status tool]
```
