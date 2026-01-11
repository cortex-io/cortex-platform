# Cortex MCP Server

Intelligent MCP (Model Context Protocol) server that routes queries to UniFi, Proxmox, Wazuh, and Kubernetes subsystems using Mixture of Experts (MoE) routing.

## Features

- **MCP Protocol Compliance**: Implements MCP specification (stdio mode)
- **Intelligent Routing**: MoE-based keyword routing with confidence scoring
- **Multi-System Support**: UniFi, Proxmox, Wazuh, Kubernetes
- **Two Core Tools**:
  - `cortex_query`: Route queries to appropriate subsystem
  - `cortex_get_status`: Get real-time Cortex operational status

## Architecture

```
┌─────────────────────────────────────────┐
│         Cortex MCP Server               │
│         (stdio protocol)                │
└───────────────┬─────────────────────────┘
                │
        ┌───────┴────────┐
        │  MoE Router    │
        │ (keyword-based)│
        └───────┬────────┘
                │
    ┌───────────┼───────────┬──────────┐
    │           │           │          │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌──▼──┐
│ UniFi │  │Proxmox│  │ Wazuh │  │ K8s │
│  MCP  │  │  MCP  │  │  MCP  │  │ CLI │
└───────┘  └───────┘  └───────┘  └─────┘
```

## Installation

```bash
cd /tmp/cortex-mcp-server
npm install
```

## Usage

### Start the MCP Server

```bash
npm start
```

The server runs in stdio mode and communicates via JSON-RPC 2.0 over stdin/stdout.

### Run Tests

```bash
npm test
```

## MCP Tools

### cortex_query

Query any Cortex subsystem with automatic or manual routing.

**Input Schema:**
```json
{
  "query": "Show me all WiFi networks",
  "system": "auto"  // or: unifi, proxmox, wazuh, k8s
}
```

**Examples:**

```javascript
// Auto routing (MoE intelligent selection)
{
  "query": "What VMs are running on Proxmox?",
  "system": "auto"
}

// Manual system selection
{
  "query": "Show network statistics",
  "system": "unifi"
}
```

**Routing Confidence Levels:**
- **1.0+ (Force)**: High confidence keyword match, automatic routing
- **0.5-0.99 (Suggest)**: Moderate confidence, suggested system
- **<0.5 (None)**: Low confidence, requires manual system selection

### cortex_get_status

Get real-time status of all Cortex operations.

**Input Schema:**
```json
{}
```

**Output:**
```json
{
  "timestamp": "2025-12-24T19:00:00Z",
  "mcp_servers": {
    "unifi": "healthy",
    "proxmox": "healthy",
    "wazuh": "healthy",
    "k8s": "healthy"
  },
  "cortex_operations": {
    "active_workers": 0,
    "active_masters": 1,
    "running_tasks": 0
  },
  "overall_health": "healthy"
}
```

## MoE Routing

The MoE router uses keyword-based routing with confidence scoring:

### Routing Keywords

**UniFi:**
- unifi, network, wifi, wireless, ssid, access point, ap, client, device connected, bandwidth, switch, port, vlan

**Proxmox:**
- proxmox, vm, virtual machine, container, lxc, pve, hypervisor, node resource, vcpu, memory, disk, snapshot

**Wazuh:**
- wazuh, security, alert, vulnerability, threat, compliance, cve, intrusion, siem, log, agent, malware

**Kubernetes:**
- k8s, kubernetes, pod, deployment, service, namespace, kubectl, container, cluster, helm, ingress, configmap

### Routing Algorithm

1. **Keyword Matching**: Scan query for system-specific keywords
2. **Confidence Scoring**: Calculate confidence based on keyword matches
3. **Route Selection**: Choose highest confidence system
4. **Action Determination**:
   - Confidence ≥1.0: Force route to system
   - Confidence 0.5-0.99: Suggest system
   - Confidence <0.5: Require manual selection

## Environment Variables

```bash
# MCP Server URLs (default: Kubernetes service URLs)
UNIFI_MCP_URL=http://unifi-mcp-server.cortex-system.svc.cluster.local:3000
PROXMOX_MCP_URL=http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000
WAZUH_MCP_URL=http://wazuh-mcp-server.cortex-system.svc.cluster.local:8080
```

## File Structure

```
cortex-mcp-server/
├── src/
│   ├── index.js              # MCP protocol server (stdio)
│   ├── moe-router.js         # Intelligent routing logic
│   ├── tools/
│   │   ├── query.js          # cortex_query tool
│   │   └── status.js         # cortex_get_status tool
│   ├── clients/
│   │   ├── unifi.js          # UniFi MCP HTTP client
│   │   ├── proxmox.js        # Proxmox MCP HTTP client
│   │   ├── wazuh.js          # Wazuh MCP HTTP client
│   │   └── k8s.js            # Kubernetes kubectl wrapper
│   └── tests/
│       └── moe-router.test.js # Router unit tests
├── package.json
└── README.md
```

## Development

### Adding New Systems

1. Add route to `src/moe-router.js`:
```javascript
newsystem: {
  keywords: ['keyword1', 'keyword2'],
  system: 'newsystem',
  priority: 100
}
```

2. Create client in `src/clients/newsystem.js`
3. Update query tool in `src/tools/query.js`
4. Add health check to `src/tools/status.js`

### Testing

Run all tests:
```bash
npm test
```

Test specific file:
```bash
node --test src/tests/moe-router.test.js
```

## MCP Protocol Reference

- **Specification**: https://modelcontextprotocol.io/specification
- **Version**: 2024-11-05
- **Transport**: stdio (HTTP planned)

## License

MIT
