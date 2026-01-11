# Sandfly MCP Integration & Deep Conversation Testing Mission

**Mission ID**: SANDFLY-INTEGRATION-2025-12-25
**Coordinator**: Larry (Coordinator Master)
**Status**: IN PROGRESS
**Priority**: CRITICAL
**Started**: 2025-12-25T16:30:00Z

## Mission Objectives

1. Deploy Sandfly MCP server to Kubernetes cluster
2. Integrate 45+ Sandfly security tools into chat backend
3. Fix conversational context dropping issues
4. Test deep multi-turn conversations (20+ messages) across all vendor APIs
5. Validate end-to-end security monitoring capabilities via natural language

## Background

### Sandfly Security Platform
- **Location**: 10.88.140.176
- **Capabilities**: Agentless Linux intrusion detection, forensics, and incident response
- **MCP Server**: 45+ tools for security monitoring and analysis
- **Source**: /Users/ryandahlberg/Desktop/sandfly/

### Chat Backend
- **Location**: /tmp/cortex-chat/backend/
- **Current Issue**: Context drops after few messages
- **Architecture**: Express + TypeScript + Anthropic SDK
- **MCP Integration Pattern**: Tool routing to microservices

## Task Breakdown

### Phase 1: Sandfly MCP Deployment (Priority 1)
**Handoff**: task-sandfly-integration-001.json
**Assigned To**: Development Master
**Status**: PENDING

Deploy Sandfly MCP server as Kubernetes service:
- Use existing Dockerfile and deployment.yaml
- Deploy to cortex-system namespace
- Configure Sandfly credentials (10.88.140.176)
- Expose as sandfly-mcp.cortex-system.svc.cluster.local:3000
- Verify health and tool availability

**Success Criteria**:
- Pod running in cortex-system
- Health endpoint accessible
- 45+ tools available via MCP protocol

---

### Phase 2: Tool Integration (Priority 1)
**Handoff**: task-sandfly-integration-002.json
**Assigned To**: Development Master
**Status**: PENDING
**Depends On**: Phase 1

Integrate all Sandfly tools into chat backend:
- Extract 45+ tool definitions from server.py
- Convert Python tools to TypeScript format
- Add to /tmp/cortex-chat/backend/src/tools/index.ts
- Update tool-executor.ts routing
- Test tool execution

**Tool Categories** (45 total):
- Authentication & System (3 tools)
- Hosts Management (11 tools)
- Credentials (3 tools)
- Scanning (2 tools)
- Results & Alerts (4 tools)
- Detection Rules/Sandflies (4 tools)
- Schedules (7 tools)
- Jump Hosts (3 tools)
- Notifications (3 tools)
- Reports (2 tools)
- Audit (1 tool)

**Success Criteria**:
- All tools in /api/tools endpoint
- Tool routing works correctly
- Test execution succeeds

---

### Phase 3: Context Persistence Fix (Priority 2)
**Handoff**: task-context-persistence-003.json
**Assigned To**: Development Master
**Status**: PENDING

Fix conversation context dropping:
- Deploy Redis for session storage
- Implement session-based conversation persistence
- Add conversation summarization (15+ messages)
- Test deep conversations (20+ messages)

**Technical Approach**:
1. Deploy Redis to cortex-system
2. Add ioredis client to backend
3. Create ConversationStore service
4. Implement session ID management
5. Add conversation summarization
6. Test with extended conversations

**Success Criteria**:
- Conversations persist across requests
- Context maintained for 20+ messages
- Summarization works at 15+ messages
- Tool execution history preserved

---

### Phase 4: Deep Conversation Testing (Priority 3)
**Handoff**: task-deep-conversation-testing-004.json
**Assigned To**: Development Master
**Status**: PENDING
**Depends On**: Phases 1, 2, 3

Comprehensive testing of all vendor APIs:
- Test Sandfly (20+ message conversation)
- Test Proxmox (20+ message conversation)
- Test UniFi (20+ message conversation)
- Test Wazuh (20+ message conversation)

**Test Scenarios**: See handoff document for detailed conversation flows

**Success Criteria**:
- Complete 20+ message conversations for each vendor
- No context loss
- All API endpoints accessible via natural language
- Test report documenting results

---

## Architecture Overview

### Current State
```
┌─────────────────────┐
│  Chat Frontend      │
│  (React/Next.js)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Chat Backend       │
│  (Express/TS)       │
│  - /api/chat        │
│  - /api/tools       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│         MCP Server Routing              │
│  - wazuh-mcp (existing)                 │
│  - unifi-mcp (existing)                 │
│  - proxmox-mcp (existing)               │
│  - cortex-orchestrator (existing)       │
└─────────────────────────────────────────┘
```

### Target State (After Integration)
```
┌─────────────────────┐
│  Chat Frontend      │
│  (React/Next.js)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────┐
│  Chat Backend       │────▶│    Redis     │
│  (Express/TS)       │     │  (Sessions)  │
│  + Session Mgmt     │     └──────────────┘
│  + Summarization    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│         MCP Server Routing              │
│  - wazuh-mcp                            │
│  - unifi-mcp                            │
│  - proxmox-mcp                          │
│  - cortex-orchestrator                  │
│  - sandfly-mcp (NEW!)                   │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│         Vendor APIs                     │
│  - Wazuh Server                         │
│  - UniFi Controller                     │
│  - Proxmox Cluster                      │
│  - Sandfly (10.88.140.176)              │
└─────────────────────────────────────────┘
```

## Example Deep Conversation Flow (Sandfly)

```
User: "List all hosts monitored by Sandfly"
Assistant: → sandfly_list_hosts
Assistant: "I found 12 hosts being monitored..."

User: "Show me details for k3s-worker-01"
Assistant: → sandfly_get_host(host_id="...")
Assistant: "k3s-worker-01 is a Ubuntu 22.04 server..."

User: "What processes are running on that host?"
Assistant: → sandfly_get_host_processes(host_id="...")
Assistant: "There are 127 processes running. Here are the key ones..."

User: "Are there any security alerts for this host?"
Assistant: → sandfly_get_results(host_id="...", status="alert")
Assistant: "Yes, I found 2 security alerts..."

User: "Show me the details of the critical alert"
Assistant: → sandfly_get_result(result_id="...")
Assistant: "This is a critical alert for suspicious process..."

[Continues for 15+ more messages, testing context retention]
```

## Coordination Status

### Handoffs Created
- ✅ task-sandfly-integration-001.json (Sandfly MCP Deployment)
- ✅ task-sandfly-integration-002.json (Tool Integration)
- ✅ task-context-persistence-003.json (Context Persistence)
- ✅ task-deep-conversation-testing-004.json (Deep Testing)

### Next Steps
1. Development Master picks up handoffs
2. Spawn Daryl agents for each phase
3. Monitor progress via coordination files
4. Aggregate results and report completion

## Technical References

### Key Files
- **Sandfly MCP Source**: /Users/ryandahlberg/Desktop/sandfly/src/mcp_sandfly/server.py
- **Sandfly Deployment**: /Users/ryandahlberg/Desktop/sandfly/deployment.yaml
- **Chat Backend**: /tmp/cortex-chat/backend/src/
- **Tool Definitions**: /tmp/cortex-chat/backend/src/tools/index.ts
- **Tool Executor**: /tmp/cortex-chat/backend/src/services/tool-executor.ts
- **Claude Service**: /tmp/cortex-chat/backend/src/services/claude.ts

### Environment Variables Required
```bash
SANDFLY_HOST=10.88.140.176
SANDFLY_USERNAME=admin
SANDFLY_PASSWORD=<configured>
SANDFLY_VERIFY_SSL=false
```

### Service Endpoints
- **Sandfly MCP**: http://sandfly-mcp.cortex-system.svc.cluster.local:3000
- **Chat Backend**: http://localhost:3001 (dev) or K8s service (prod)
- **Redis**: redis.cortex-system.svc.cluster.local:6379

## Success Metrics

### Integration Success
- [ ] Sandfly MCP deployed and healthy
- [ ] 45+ tools integrated into chat backend
- [ ] All tools accessible via /api/tools
- [ ] Test tool execution succeeds

### Context Persistence Success
- [ ] Redis deployed and accessible
- [ ] Conversations persist across requests
- [ ] Context maintained for 20+ messages
- [ ] Summarization works correctly

### Deep Testing Success
- [ ] Sandfly: 20+ message conversation completed
- [ ] Proxmox: 20+ message conversation completed
- [ ] UniFi: 20+ message conversation completed
- [ ] Wazuh: 20+ message conversation completed
- [ ] Test report generated

## Risk Assessment

### Risks
1. **Sandfly MCP connectivity**: May need VPN or network routing
2. **Redis performance**: High conversation volume may stress Redis
3. **Context window limits**: Very long conversations may hit token limits
4. **Tool execution timeouts**: Some forensic operations may be slow

### Mitigations
1. Verify network connectivity before deployment
2. Configure Redis with appropriate memory limits
3. Implement aggressive summarization at 15+ messages
4. Increase timeout for long-running tools (60s+)

## Timeline

- **Phase 1**: 2-4 hours (Sandfly deployment)
- **Phase 2**: 3-5 hours (Tool integration)
- **Phase 3**: 4-6 hours (Context persistence)
- **Phase 4**: 4-8 hours (Deep testing)

**Total Estimated Time**: 13-23 hours

## Contact & Escalation

- **Coordinator**: Larry (Coordinator Master)
- **Development Master**: Handles all technical implementation
- **Escalation**: Cortex Meta-Agent for critical blockers

---

**Last Updated**: 2025-12-25T16:30:00Z
**Mission Status**: HANDOFFS CREATED - AWAITING PICKUP