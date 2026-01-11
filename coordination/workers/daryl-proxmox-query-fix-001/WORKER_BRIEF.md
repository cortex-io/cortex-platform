# Daryl Worker Brief: Proxmox MCP Query Router Fix

**Worker ID**: daryl-proxmox-query-fix-001
**Worker Type**: Fix Worker (Daryl)
**Task ID**: task-proxmox-query-routing-001
**Priority**: HIGH
**Governance Bypass**: ENABLED

## Mission

Fix the Proxmox MCP `proxmox_query` wrapper so it intelligently routes queries to the correct tools instead of always calling `list_nodes`.

## Context

You are Daryl, a specialized fix worker in the Cortex automation system. Your parent master is the Coordinator, and you've been spawned to handle this MCP query routing fix.

## Problem Statement

The Proxmox MCP has a `/query` endpoint in the HTTP wrapper that always calls the first tool (`list_nodes`) regardless of the query content. This causes issues like:

**Evidence from logs**:
```
[HTTP] Query: list all running VMs
[MCP-REQUEST] {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_nodes", "arguments": {"query": "list all running VMs"}}}
```

When a user asks "what VMs are running?", it should call `list_vms`, not `list_nodes`.

## Available Tools in Proxmox MCP

```
list_nodes, get_node_status, list_vms, get_vm_config, get_vm_status,
start_vm, stop_vm, shutdown_vm, reboot_vm, list_containers,
get_container_status, start_container, stop_container, list_storage,
get_storage_status, list_tasks, get_task_status, create_vm_snapshot,
list_vm_snapshots, delete_vm_snapshot, get_cluster_status
```

## Current Deployment

- **Namespace**: `cortex-system`
- **Deployment**: `proxmox-mcp-server`
- **ConfigMap**: `mcp-http-wrapper` (contains the wrapper with /query endpoint)
- **Repository**: https://github.com/ry-ops/proxmox-mcp-server.git

## Solution Approach

Implement intelligent query routing in the HTTP wrapper's `/query` endpoint based on keywords:

### Query Routing Rules

1. **VM Operations**:
   - Keywords: "vm", "vms", "virtual machine", "qemu", "kvm"
   - Route to: `list_vms`
   - Examples: "what VMs are running?", "list all VMs", "show virtual machines"

2. **Container Operations**:
   - Keywords: "container", "containers", "lxc"
   - Route to: `list_containers`
   - Examples: "show containers", "list LXC containers"

3. **Storage Operations**:
   - Keywords: "storage", "disk", "volume"
   - Route to: `list_storage`
   - Examples: "show storage", "list disks"

4. **Snapshot Operations**:
   - Keywords: "snapshot", "snapshots"
   - Route to: `list_vm_snapshots` (requires node and vmid)
   - Examples: "show snapshots"

5. **Task Operations**:
   - Keywords: "task", "tasks", "job", "jobs"
   - Route to: `list_tasks`
   - Examples: "show tasks", "list running jobs"

6. **Cluster/Node Operations**:
   - Keywords: "node", "nodes", "cluster"
   - Route to: `list_nodes` or `get_cluster_status`
   - Examples: "show nodes", "cluster status"

7. **Default**: If no keywords match, use `get_cluster_status` for overview

## Implementation Steps

1. **Backup Current Configuration**
   - Get current mcp-http-wrapper ConfigMap
   - Save to worker directory for rollback if needed

2. **Implement Query Router Function**
   - Add a `route_query(query: str)` function to the HTTP wrapper
   - Implement keyword matching logic (case-insensitive)
   - Return the appropriate tool name and arguments

3. **Update the /query Endpoint**
   - Replace the current logic that uses `tools[0]`
   - Call the new `route_query()` function
   - Use the routed tool name instead of defaulting to first tool

4. **Handle Tool Arguments**
   - Most listing tools don't require specific arguments
   - For tools that need node/vmid, provide sensible defaults or return error
   - Pass empty dict for tools that don't need arguments

5. **Update ConfigMap**
   - Apply the updated mcp-http-wrapper ConfigMap
   - Verify ConfigMap is updated

6. **Restart Deployment**
   - Restart proxmox-mcp-server deployment to load new wrapper
   - Wait for pod to be ready

7. **Test Query Routing**
   - Test: "what VMs are running?" → should call `list_vms`
   - Test: "show containers" → should call `list_containers`
   - Test: "list storage" → should call `list_storage`
   - Test: "show nodes" → should call `list_nodes`
   - Test: "cluster status" → should call `get_cluster_status`

## Target Files

### Primary Target
- **ConfigMap**: `mcp-http-wrapper` in namespace `cortex-system`
  - Key: `mcp-http-wrapper.py`
  - Section to modify: `/query` POST endpoint handler (around line 150-180)

### Current Problematic Code
```python
# LEGACY ENDPOINT: Use first tool (for backward compat)
...
# Try to find the best tool for this query
tool_name = None
if tools:
    # Use first tool by default  <-- THIS IS THE PROBLEM
    tool_name = tools[0].get('name')
```

### New Code (Pseudo-code)
```python
def route_query(query: str, available_tools: list) -> tuple[str, dict]:
    """Route query to appropriate tool based on keywords"""
    query_lower = query.lower()

    # VM operations
    if any(kw in query_lower for kw in ['vm', 'virtual machine', 'qemu', 'kvm']):
        return 'list_vms', {}

    # Container operations
    elif any(kw in query_lower for kw in ['container', 'lxc']):
        return 'list_containers', {'node': 'pve'}  # Need to handle node

    # Storage operations
    elif any(kw in query_lower for kw in ['storage', 'disk', 'volume']):
        return 'list_storage', {}

    # Task operations
    elif any(kw in query_lower for kw in ['task', 'job']):
        return 'list_tasks', {}

    # Snapshot operations
    elif 'snapshot' in query_lower:
        return 'list_vm_snapshots', {}  # May need vmid

    # Node/cluster operations
    elif any(kw in query_lower for kw in ['node', 'cluster']):
        if 'status' in query_lower or 'cluster' in query_lower:
            return 'get_cluster_status', {}
        else:
            return 'list_nodes', {}

    # Default: cluster status for overview
    else:
        return 'get_cluster_status', {}

# In /query endpoint:
tool_name, arguments = route_query(query, tools)
result = mcp_client.call_tool(tool_name, arguments)
```

## Success Criteria

- Query "what VMs are running?" calls `list_vms` (not `list_nodes`)
- Query "show containers" calls `list_containers`
- Query "list storage" calls `list_storage`
- Query "show tasks" calls `list_tasks`
- Query "cluster status" calls `get_cluster_status`
- Logs show correct tool being called for each query type
- All existing functionality remains working

## Testing Plan

1. **Get Pod Logs Before Change**
   - `kubectl logs -n cortex-system deployment/proxmox-mcp-server --tail=50`
   - Verify current behavior (always calls list_nodes)

2. **Apply Fix**
   - Update ConfigMap
   - Restart deployment

3. **Test Each Query Type**
   - Use curl or kubectl exec to test /query endpoint
   - Verify logs show correct tool being called

4. **Verify No Regressions**
   - Test /call-tool endpoint still works
   - Test /list-tools endpoint still works
   - Test /health endpoint still works

## Output Requirements

Create these files in your worker directory:
- `implementation-log.md` - Full implementation log with code changes
- `updated-mcp-http-wrapper.py` - New version of the wrapper
- `test-results.md` - Test results showing query routing working
- `before-after-logs.md` - Logs showing the difference before/after fix
- `completion-report.json` - Structured completion report

## Resources

- **Token Budget**: 30,000 tokens
- **Time Limit**: 60 minutes
- **Working Directory**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-proxmox-query-fix-001`

## Important Notes

- Use GOVERNANCE_BYPASS=true for all operations
- You have full kubectl access to the cortex-system namespace
- The HTTP wrapper is written in Python 3
- Test thoroughly before marking complete
- Consider backward compatibility with existing clients

## Example Test Commands

```bash
# Get the pod name
POD=$(kubectl get pods -n cortex-system -l app=proxmox-mcp-server -o jsonpath='{.items[0].metadata.name}')

# Test VM query (should call list_vms)
kubectl exec -n cortex-system $POD -- curl -X POST http://localhost:3000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what VMs are running?"}'

# Check logs to verify correct tool was called
kubectl logs -n cortex-system $POD --tail=10
```

## When Complete

1. Update worker-spec.json status to "completed"
2. Create completion-report.json with test results
3. Document any issues or improvements discovered
4. Exit the worker session

Good luck, Daryl!
