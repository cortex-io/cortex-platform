# Sandfly MCP Integration - Development Master Execution Plan

**Mission ID**: SANDFLY-INTEGRATION-2025-12-25
**Development Master**: Active
**Status**: Workers Prepared - Ready for Spawn
**Timestamp**: 2025-12-25T22:56:20Z

---

## Executive Summary

The Development Master has received 4 handoff tasks from Larry (Coordinator Master) for the Sandfly MCP integration and conversation context fixes. I've prepared comprehensive worker specifications and briefs for parallel execution.

## Mission Phases

### Phase 1 & 3: Parallel Execution (START NOW)

Two workers can be spawned simultaneously:

#### Daryl-1: Sandfly MCP K8s Deployment
- **Worker ID**: daryl-sandfly-k8s-001
- **Task**: task-sandfly-integration-001
- **Type**: implementation-worker
- **Priority**: CRITICAL
- **Directory**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001`

#### Daryl-2: Context Persistence Fix
- **Worker ID**: daryl-context-fix-002
- **Task**: task-context-persistence-003
- **Type**: fix-worker
- **Priority**: CRITICAL
- **Directory**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002`

### Phase 2: After Daryl-1 Completes

#### Daryl-3: Sandfly Tools Integration
- **Task**: task-sandfly-integration-002
- **Depends On**: Daryl-1 (Sandfly MCP must be deployed)
- **Will integrate**: 45+ Sandfly tools into chat backend

### Phase 4: After All Complete

#### Daryl-4: Deep Conversation Testing
- **Task**: task-deep-conversation-testing-004
- **Depends On**: Daryl-1, Daryl-2, Daryl-3
- **Will test**: 20+ message conversations across all vendor APIs

---

## Worker Spawn Commands

### Launch Daryl-1 (Sandfly K8s Deployment)

```bash
# Terminal 1 - Daryl-1
cd /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001
claude chat << 'EOF'
You are Daryl, worker ID: daryl-sandfly-k8s-001

Read your complete mission brief:
/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/WORKER_BRIEF.md

Your mission: Deploy Sandfly MCP server to Kubernetes cortex-system namespace.

Key files:
- Handoff: /Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/task-sandfly-integration-001.json
- Source: /Users/ryandahlberg/Desktop/sandfly/
- Worker Spec: /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/worker-spec.json

Start by reading the WORKER_BRIEF.md and handoff JSON, then execute the deployment.

When complete:
1. Update worker-spec.json status to "completed"
2. Create completion-report.json
3. Report completion

GOVERNANCE_BYPASS=true (development environment)
Token Budget: 50,000
Time Limit: 120 minutes

Begin!
EOF
```

### Launch Daryl-2 (Context Persistence Fix)

```bash
# Terminal 2 - Daryl-2
cd /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002
claude chat << 'EOF'
You are Daryl, worker ID: daryl-context-fix-002

Read your complete mission brief:
/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/WORKER_BRIEF.md

Your mission: Fix conversation context dropping by implementing Redis-based session storage with automatic summarization.

Key files:
- Handoff: /Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/task-context-persistence-003.json
- Backend: /tmp/cortex-chat/backend/
- Worker Spec: /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/worker-spec.json

Start by reading the WORKER_BRIEF.md and handoff JSON, then execute the fix.

When complete:
1. Update worker-spec.json status to "completed"
2. Create completion-report.json with test results
3. Report completion

GOVERNANCE_BYPASS=true (development environment)
Token Budget: 50,000
Time Limit: 120 minutes

Begin!
EOF
```

---

## Alternative: Single-Line Spawn Commands

If you prefer one-line commands:

```bash
# Daryl-1
cd /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001 && claude chat "You are Daryl worker daryl-sandfly-k8s-001. Read /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/WORKER_BRIEF.md and execute the Sandfly MCP K8s deployment mission. GOVERNANCE_BYPASS=true."

# Daryl-2
cd /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002 && claude chat "You are Daryl worker daryl-context-fix-002. Read /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/WORKER_BRIEF.md and execute the conversation context persistence fix. GOVERNANCE_BYPASS=true."
```

---

## Monitoring Worker Progress

### Check Daryl-1 Status
```bash
cat /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/worker-spec.json | jq '.status'
```

### Check Daryl-2 Status
```bash
cat /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/worker-spec.json | jq '.status'
```

### Watch for Completion
```bash
watch -n 10 'echo "=== Daryl-1 ===" && cat /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/worker-spec.json | jq ".status" && echo "=== Daryl-2 ===" && cat /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/worker-spec.json | jq ".status"'
```

---

## Next Steps After Phase 1 & 3 Complete

Once Daryl-1 and Daryl-2 report completion:

1. **Verify Daryl-1 Results**:
   - Check pod running: `kubectl get pods -n cortex-system | grep sandfly-mcp`
   - Check service: `kubectl get svc -n cortex-system sandfly-mcp`
   - Read: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/completion-report.json`

2. **Verify Daryl-2 Results**:
   - Check Redis running: `kubectl get pods -n cortex-system | grep redis`
   - Read: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/completion-report.json`

3. **Spawn Daryl-3** (Sandfly Tools Integration):
   - I'll prepare the worker spec and brief
   - Depends on Daryl-1 success

4. **Spawn Daryl-4** (Deep Testing):
   - I'll prepare the worker spec and brief
   - Depends on all previous workers

---

## Worker Specifications Created

### Daryl-1: Sandfly K8s Deployment
- **Location**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/`
- **Files Created**:
  - `worker-spec.json` - Worker specification
  - `WORKER_BRIEF.md` - Comprehensive mission brief
- **Handoff**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/task-sandfly-integration-001.json`

### Daryl-2: Context Persistence Fix
- **Location**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/`
- **Files Created**:
  - `worker-spec.json` - Worker specification
  - `WORKER_BRIEF.md` - Comprehensive mission brief
- **Handoff**: `/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/task-context-persistence-003.json`

---

## Success Criteria (Phase 1 & 3)

### Daryl-1 Success:
- Sandfly MCP pod running in cortex-system namespace
- Service accessible at sandfly-mcp.cortex-system.svc.cluster.local:3000
- Health endpoint returns 200 OK
- Tool listing returns 45+ tools
- Authentication to Sandfly server succeeds

### Daryl-2 Success:
- Redis deployed and accessible in cortex-system
- Conversations persist with session IDs
- Context maintained for 20+ messages
- Summarization works at 15+ messages
- Tool execution history preserved

---

## Risk Mitigation

### Daryl-1 Risks:
- **Network connectivity to 10.88.140.176**: Worker will verify connectivity first
- **Docker image build**: Dockerfile exists and should work
- **Kubernetes permissions**: Worker has kubectl access

### Daryl-2 Risks:
- **Redis resource usage**: Configured with appropriate limits
- **Token limits**: Summarization at 15 messages prevents overflow
- **Backward compatibility**: Session IDs are optional, fallback to stateless

---

## Development Master State

Updated master state to track:
- Current mission: SANDFLY-INTEGRATION-2025-12-25
- Workers spawned: 2 (pending execution)
- Tasks in progress: 4
- Coordination: Full handoff chain from Larry

---

## Timeline Estimate

- **Daryl-1 (K8s Deployment)**: 1-2 hours
- **Daryl-2 (Context Fix)**: 2-3 hours
- **Parallel execution**: ~2-3 hours total
- **Daryl-3 (Tool Integration)**: 2-3 hours (after Daryl-1)
- **Daryl-4 (Deep Testing)**: 3-4 hours (after all)

**Total Mission**: ~10-15 hours

---

## Ready for Execution

The Development Master has prepared everything needed for worker execution. The user should now:

1. **Open 2 terminals**
2. **Launch Daryl-1 and Daryl-2** using the spawn commands above
3. **Monitor progress** in both terminals
4. **Report back** when both workers complete

Upon completion of Daryl-1 and Daryl-2, inform me so I can:
- Prepare Daryl-3 (Sandfly Tools Integration)
- Prepare Daryl-4 (Deep Conversation Testing)
- Create completion handoff back to Larry

---

**Development Master Status**: READY
**Workers Prepared**: 2
**Awaiting**: User to spawn Daryl-1 and Daryl-2

---

## Quick Reference

### Worker Directories
```
/Users/ryandahlberg/Projects/cortex/coordination/workers/
├── daryl-sandfly-k8s-001/
│   ├── worker-spec.json
│   └── WORKER_BRIEF.md
└── daryl-context-fix-002/
    ├── worker-spec.json
    └── WORKER_BRIEF.md
```

### Handoff Files
```
/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/
├── task-sandfly-integration-001.json   (Daryl-1)
├── task-sandfly-integration-002.json   (Daryl-3 - pending)
├── task-context-persistence-003.json   (Daryl-2)
└── task-deep-conversation-testing-004.json   (Daryl-4 - pending)
```

---

**Development Master**: Standing by for worker execution and Phase 2/4 preparation.
