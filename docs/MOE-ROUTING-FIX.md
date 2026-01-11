# MoE Routing Fix & Cortex MCP Server

## Problem

**Current State:**
- Chat sends queries to Cortex orchestrator
- Cortex has MCP tools (unifi_query, proxmox_query, wazuh_query) defined
- MCP servers are healthy and reachable
- BUT: Claude defaults to kubectl tool instead of MCP tools
- Result: Only k8s queries work, UniFi/Proxmox queries return kubectl output

**Root Cause:**
- No pre-routing logic before Claude
- Tool descriptions aren't strong enough
- Claude sees kubectl as "safer" default
- No MoE (Mixture of Experts) routing happening

## Solution 1: Add MoE Pre-Router

### Implementation
Add keyword-based routing BEFORE calling Claude:

```javascript
// In cortex-api-server-final
const { routeQuery, shouldForceRoute } = require('./moe-router');

async function processUserQuery(userQuery) {
  // MoE Pre-routing
  const routing = shouldForceRoute(userQuery);

  if (routing.forceTool) {
    // High confidence - force specific tool
    console.log(`[MoE] Forcing tool: ${routing.forceTool}`);

    // Execute tool directly
    const toolResult = await executeTool(routing.forceTool, {
      query: userQuery,
      command: userQuery
    });

    // Return result to user
    return {
      answer: formatToolResult(routing.forceTool, toolResult),
      routing: { forced: true, tool: routing.forceTool }
    };
  }

  // Normal Claude flow with optional hint
  const systemMessage = routing.systemHint
    ? `${DEFAULT_SYSTEM_MESSAGE}\n\n${routing.systemHint}`
    : DEFAULT_SYSTEM_MESSAGE;

  // Continue with Claude...
}
```

### Routing Rules
```javascript
const MoE_ROUTES = {
  unifi: {
    keywords: ['unifi', 'network', 'wifi', 'wireless', 'ssid'],
    tool: 'unifi_query',
    priority: 100  // Force route if matched
  },
  proxmox: {
    keywords: ['proxmox', 'vm', 'virtual machine'],
    tool: 'proxmox_query',
    priority: 100
  },
  wazuh: {
    keywords: ['wazuh', 'security', 'alert'],
    tool: 'wazuh_query',
    priority: 100
  },
  kubernetes: {
    keywords: ['k8s', 'pod', 'deployment'],
    tool: 'kubectl',
    priority: 50  // Lower priority - only if no other match
  }
};
```

### Benefits
- ✅ Instant routing based on keywords
- ✅ No ambiguity - "unifi network" → `unifi_query` 100%
- ✅ Saves Claude API tokens
- ✅ Faster responses
- ✅ Predictable behavior

---

## Solution 2: Create Cortex MCP Server

### Architecture
```
┌─────────────────────────────────────┐
│ Chat App                             │
└──────────────┬──────────────────────┘
               ↓
┌──────────────────────────────────────┐
│ Cortex MCP Server (NEW)              │
│  - Exposes Cortex via MCP protocol   │
│  - Routes to specialists:            │
│    • UniFi MCP                       │
│    • Proxmox MCP                     │
│    • Wazuh MCP                       │
│    • Worker Pool                     │
│    • Master Agents                   │
│    • kubectl                         │
└──────────────────────────────────────┘
```

### Cortex MCP Tools
```javascript
{
  name: 'cortex_route',
  description: 'Route query to appropriate Cortex subsystem (UniFi, Proxmox, Wazuh, k8s, workers)',
  input_schema: {
    type: 'object',
    properties: {
      query: { type: 'string' },
      system: { type: 'string', enum: ['auto', 'unifi', 'proxmox', 'wazuh', 'k8s', 'workers'] }
    }
  }
},
{
  name: 'cortex_spawn_worker',
  description: 'Spawn a Cortex worker for a specific task',
  input_schema: {
    type: 'object',
    properties: {
      task_type: { type: 'string' },
      priority: { type: 'number' }
    }
  }
},
{
  name: 'cortex_get_status',
  description: 'Get Cortex orchestrator status, active workers, task queue',
  input_schema: {
    type: 'object',
    properties: {}
  }
}
```

### Implementation Files
```
cortex-mcp-server/
├── src/
│   ├── index.js          # MCP server entry point
│   ├── moe-router.js     # Intelligent routing
│   ├── tools/
│   │   ├── route.js      # cortex_route tool
│   │   ├── worker.js     # cortex_spawn_worker tool
│   │   └── status.js     # cortex_get_status tool
│   └── clients/
│       ├── unifi.js      # UniFi MCP client
│       ├── proxmox.js    # Proxmox MCP client
│       ├── wazuh.js      # Wazuh MCP client
│       └── kubectl.js    # k8s client
├── package.json
└── Dockerfile
```

### Benefits
- ✅ **Unified interface** - One MCP server for everything Cortex
- ✅ **Full construction company** - Access workers, masters, coordinators
- ✅ **Composable** - Chat app just calls one MCP server
- ✅ **Scalable** - Add new systems by registering new routes
- ✅ **Standard protocol** - Uses MCP spec, works with any MCP client

---

## Implementation Plan

### Phase 1: Quick Fix (30 min)
1. Add MoE router to cortex-api-server ✓
2. Update Cortex ConfigMap
3. Restart Cortex orchestrator
4. Test: "how is my unifi network?" → should use `unifi_query`
5. Test: "what VMs are running?" → should use `proxmox_query`

### Phase 2: Cortex MCP Server (2-3 hours)
1. Create cortex-mcp-server package
2. Implement MCP protocol (stdio mode first)
3. Add routing tools (cortex_route, etc.)
4. Build Docker image
5. Deploy to k8s (cortex-system namespace)
6. Update chat app to use Cortex MCP instead of direct API
7. Test end-to-end

### Phase 3: Full Integration (1 hour)
1. Add Cortex MCP to preflight checks
2. Create Traefik ingress for Cortex MCP
3. Update docs
4. Test all query types

---

## Testing

### Test Queries
```bash
# Should route to unifi_query
curl -X POST http://cortex:8000/api/tasks \
  -d '{"id":"test-1","payload":{"query":"how is my unifi network?"}}'

# Should route to proxmox_query
curl -X POST http://cortex:8000/api/tasks \
  -d '{"id":"test-2","payload":{"query":"what VMs are running on proxmox?"}}'

# Should route to wazuh_query
curl -X POST http://cortex:8000/api/tasks \
  -d '{"id":"test-3","payload":{"query":"any security alerts from wazuh?"}}'

# Should route to kubectl
curl -X POST http://cortex:8000/api/tasks \
  -d '{"id":"test-4","payload":{"query":"what pods are running in cortex-system?"}}'
```

### Expected Results
```json
{
  "result": {
    "answer": "...",
    "routing": {
      "tool": "unifi_query",
      "confidence": 1.0,
      "forced": true
    }
  }
}
```

---

## Files to Create/Modify

### Quick Fix
- [x] `/tmp/cortex-moe-router.js` - Created
- [ ] Update `/cortex-api-server-final` ConfigMap
- [ ] Restart cortex-orchestrator deployment

### Cortex MCP Server
- [ ] `cortex-mcp-server/package.json`
- [ ] `cortex-mcp-server/src/index.js`
- [ ] `cortex-mcp-server/src/moe-router.js`
- [ ] `cortex-mcp-server/src/tools/route.js`
- [ ] `cortex-mcp-server/Dockerfile`
- [ ] `k8s/cortex-mcp-server.yaml`

### Documentation
- [x] `docs/MOE-ROUTING-FIX.md` - This file
- [ ] `docs/CORTEX-MCP-SERVER.md`
- [ ] Update `docs/PREFLIGHT-PLAYBOOK.md`
- [ ] Update `README-OPERATIONS.md`

---

## Next Steps

1. **Immediate**: Apply MoE router fix to current Cortex orchestrator
2. **Short-term**: Build Cortex MCP Server
3. **Long-term**: Migrate chat app to use Cortex MCP exclusively

This gives you the "full Cortex construction company" accessible via a single, clean MCP interface! 🏗️
