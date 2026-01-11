# Cortex Self-Healing System

## Overview

The Cortex self-healing system provides automatic detection, diagnosis, and remediation of service failures. When an MCP server or infrastructure component fails, Cortex automatically spawns a diagnostic worker to investigate the issue, attempts common fixes, and either recovers the service or provides detailed diagnostic information to the user.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Query                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Cortex API (server.js)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  processUserQuery() → executeTool() → callMCPTool()  │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│                       ▼ (on error)                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Error Detection & Interception             │   │
│  │  - MCP server connection failures                    │   │
│  │  - Tool execution errors                             │   │
│  │  - Timeout errors                                    │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         spawnHealingWorker()                         │   │
│  │  - Extract service name from URL                     │   │
│  │  - Stream healing_start event                        │   │
│  │  - Execute self-heal-worker.sh                       │   │
│  │  - Stream progress events                            │   │
│  └────────────────────┬─────────────────────────────────┘   │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Self-Healing Worker (Bash Script)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Phase 1: Diagnosis                                  │   │
│  │  - Check pod status (running/crashloop/imagepull)    │   │
│  │  - Check service endpoints                           │   │
│  │  - Analyze recent logs for errors                    │   │
│  │  - Verify deployment configuration                   │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Phase 2: Remediation                                │   │
│  │  - Restart pods (rollout restart)                    │   │
│  │  - Scale deployment if needed                        │   │
│  │  - Verify connectivity post-fix                      │   │
│  │  - Wait for rollout completion                       │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Phase 3: Report                                     │   │
│  │  - Return JSON result                                │   │
│  │  - Include diagnosis, fix applied, timestamp         │   │
│  │  - Provide recommendations if fix failed             │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Result Processing (server.js)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  If healing succeeded:                               │   │
│  │  - Stream healing_complete event                     │   │
│  │  - Retry original operation                          │   │
│  │  - Return success to user                            │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  If healing failed:                                  │   │
│  │  - Stream healing_failed event                       │   │
│  │  - Return detailed diagnosis                         │   │
│  │  - Provide manual intervention steps                 │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  User Interface (SSE)                       │
│  - Shows healing progress in real-time                      │
│  - Displays "Investigating issue with [service]..."         │
│  - Shows progress: "Checking pod status..."                 │
│  - Shows result: "Service restored" or "Manual fix needed"  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Error Detection (server.js)

All MCP server calls and tool executions are wrapped with error handlers that detect:

- **Network errors**: Connection refused, timeout, DNS failures
- **MCP server errors**: Service unavailable, crash loops
- **Tool execution errors**: Command failures, timeouts
- **Claude API errors**: Rate limits, API failures, server errors
- **Unhandled exceptions**: Uncaught exceptions, unhandled promise rejections
- **Timeout errors**: MCP tool call timeouts triggering automatic healing

**Key Functions:**
- `callMCPTool()` - Wraps MCP tool calls with error handling and timeout healing
- `queryMCPServer()` - Wraps MCP queries with error handling
- `executeTool()` - Wraps tool execution with error handling
- `callClaude()` - Enhanced with retry logic, exponential backoff, and timeout handling
- Global error handlers for `uncaughtException` and `unhandledRejection` events

### 2. Self-Healing Worker (self-heal-worker.sh)

A bash script that performs diagnostic checks and attempts automated remediation.

**Location:** `/Users/ryandahlberg/Projects/cortex/scripts/self-heal-worker.sh`

**Input Parameters:**
1. `SERVICE_NAME` - Name of the failed service (e.g., "sandfly-mcp-server")
2. `ERROR_MESSAGE` - The error that triggered healing
3. `SERVER_URL` - Full URL of the failed service

**Diagnostic Checks:**
- Pod status (running, crashloop, imagepull errors)
- Service endpoint availability
- Recent pod logs for error patterns
- Deployment configuration validation
- Resource limits and OOMKilled detection
- Network policies affecting service
- Failed pod cleanup
- Resource usage metrics (CPU, memory)

**Remediation Strategies:**
- Restart crashlooping pods (`kubectl rollout restart`)
- Scale deployment if no pods exist
- Wait for rollout completion
- Verify connectivity post-fix
- Return detailed diagnosis if unable to fix

**Output:** JSON object with healing result
```json
{
  "success": true|false,
  "diagnosis": "Detailed diagnostic information",
  "fix_applied": "Description of fix applied",
  "timestamp": "ISO 8601 timestamp",
  "recommendation": "Manual intervention steps (if failed)"
}
```

### 3. Progress Streaming (SSE)

Real-time progress updates are streamed to the user interface using Server-Sent Events.

**Event Types:**

#### `processing_start`
Sent when query processing begins.
```json
{
  "type": "processing_start",
  "query": "User query"
}
```

#### `healing_start`
Sent when a service failure is detected and healing begins.
```json
{
  "type": "healing_start",
  "service": "sandfly-mcp-server",
  "issue": "connect ECONNREFUSED"
}
```

#### `healing_progress`
Sent during healing workflow to show progress.
```json
{
  "type": "healing_progress",
  "service": "sandfly-mcp-server",
  "message": "Checking pod status..."
}
```

#### `healing_complete`
Sent when healing succeeds.
```json
{
  "type": "healing_complete",
  "service": "sandfly-mcp-server",
  "success": true,
  "message": "Restarted deployment sandfly-mcp-server"
}
```

#### `healing_failed`
Sent when healing fails.
```json
{
  "type": "healing_failed",
  "service": "sandfly-mcp-server",
  "message": "Unable to fix automatically: ImagePullBackOff detected",
  "recommendation": "Check image name/tags and registry access"
}
```

#### `processing_complete`
Sent when query processing completes.
```json
{
  "type": "processing_complete",
  "id": "task-id",
  "status": "completed",
  "result": { /* Claude response */ }
}
```

#### `processing_delay`
Sent when Claude API encounters retryable errors.
```json
{
  "type": "processing_delay",
  "message": "Rate limited, retrying in 2 seconds..."
}
```

## Healing Workflows

### Workflow 1: MCP Server Connection Failure

**Trigger:** MCP server returns connection refused or timeout

1. **Detect**: `callMCPTool()` catches connection error
2. **Stream**: Send `healing_start` event to user
3. **Investigate**: Spawn healing worker
   - Check if pods are running
   - Check pod status (crashloop, imagepull errors)
   - Check service endpoints
   - Analyze logs for errors
4. **Fix**:
   - If crashloop: Restart deployment
   - If no pods: Scale up and restart
   - If imagepull: Report (cannot auto-fix)
5. **Verify**: Test connectivity to service
6. **Stream**: Send `healing_complete` or `healing_failed`
7. **Retry**: If succeeded, retry original MCP call
8. **Report**: Return result or detailed error to user

**Timeline:** ~30-60 seconds

### Workflow 2: Pod CrashLoopBackOff

**Trigger:** Diagnostic check finds crashlooping pods

1. **Diagnosis**:
   - Check recent logs for crash reason
   - Identify error patterns (OOM, config errors, etc.)
2. **Remediation**:
   - Execute `kubectl rollout restart deployment -n cortex-system <service>`
   - Wait for rollout completion (60s timeout)
   - Verify pods are in Ready state
3. **Verification**:
   - Test service connectivity
   - Check health endpoint if available
4. **Result**:
   - If success: Return fix applied
   - If failure: Return diagnosis with recommendation

### Workflow 3: ImagePullBackOff

**Trigger:** Diagnostic check finds imagepull errors

1. **Diagnosis**:
   - Identify image pull error type (not found, auth failure, etc.)
   - Check deployment for image name/tag
2. **Remediation**:
   - **Cannot auto-fix** (requires manual intervention)
3. **Report**:
   - Detailed diagnosis of image pull issue
   - Recommendations:
     - Verify image name and tag
     - Check registry credentials
     - Verify network access to registry

### Workflow 4: Service Endpoints Missing

**Trigger:** Service exists but has no endpoints

1. **Diagnosis**:
   - Check if deployment exists
   - Check if pods exist and are ready
   - Check selector labels match
2. **Remediation**:
   - If no pods: Scale deployment
   - If pods not ready: Wait and recheck
   - If selector mismatch: Report (manual fix)
3. **Verification**:
   - Wait for endpoints to appear
   - Verify service connectivity

## Adding New Healing Strategies

To add a new healing strategy, modify `/Users/ryandahlberg/Projects/cortex/scripts/self-heal-worker.sh`:

### 1. Add Diagnostic Function

```bash
check_new_issue() {
    progress "Checking for new issue..."

    # Your diagnostic logic here
    local issue_detected=$(kubectl get ... | jq ...)

    if [[ -n "$issue_detected" ]]; then
        DIAGNOSIS+="New issue detected: $issue_detected. "
        return 1
    fi

    return 0
}
```

### 2. Add Remediation Function

```bash
fix_new_issue() {
    progress "Fixing new issue..."

    if kubectl ... ; then
        FIX_APPLIED="Fixed new issue by doing X"
        log "Successfully fixed new issue"
        return 0
    else
        log "Failed to fix new issue"
        return 1
    fi
}
```

### 3. Update Main Workflow

```bash
main() {
    # ... existing diagnostic checks ...

    # Add your new check
    check_new_issue
    local new_issue_status=$?

    # ... existing remediation ...

    # Add remediation logic
    if [[ $new_issue_status -eq 1 ]]; then
        if fix_new_issue; then
            SUCCESS=true
        fi
    fi

    # ... generate report ...
}
```

### 4. Document the Strategy

Add documentation for the new strategy in this file.

## Common Healing Patterns

### Pattern 1: Restart Service

```bash
kubectl rollout restart deployment -n cortex-system <service-name>
kubectl rollout status deployment -n cortex-system <service-name> --timeout=60s
```

**Use when:**
- Pod is crashlooping
- Service is unresponsive
- Configuration has changed

### Pattern 2: Scale Service

```bash
kubectl scale deployment -n cortex-system <service-name> --replicas=1
```

**Use when:**
- No pods exist
- Deployment scaled to 0
- Need to reset replica count

### Pattern 3: Check Logs

```bash
kubectl logs -n cortex-system <pod-name> --tail=50
```

**Use when:**
- Diagnosing crash reasons
- Looking for error patterns
- Understanding failure mode

### Pattern 4: Test Connectivity

```bash
kubectl run test-connectivity-$RANDOM \
    --rm -i --restart=Never \
    --image=curlimages/curl:latest \
    -n cortex-system \
    --timeout=30s \
    -- curl -s -m 10 "http://<service>:3000/health"
```

**Use when:**
- Verifying service is reachable
- Testing post-fix connectivity
- Checking service health endpoints

## Configuration

### Environment Variables

Set in `/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api/deployment.yaml`:

```yaml
env:
  - name: SELF_HEAL_WORKER_PATH
    value: "/app/scripts/self-heal-worker.sh"
```

### Namespace

Self-healing assumes services are in `cortex-system` namespace. To change:

```bash
# In self-heal-worker.sh
NAMESPACE="your-namespace"
```

### Timeouts

Configurable timeouts:

- **Healing worker execution**: 120s (2 minutes)
- **Rollout status wait**: 60s
- **Connectivity test**: 30s
- **MCP tool call**: 60s

## Testing

### Manual Test: Simulate Service Failure

1. **Stop a service:**
   ```bash
   kubectl scale deployment -n cortex-system sandfly-mcp-server --replicas=0
   ```

2. **Make a query that uses the service:**
   - Open Cortex chat UI
   - Ask: "What security alerts do we have?"

3. **Observe healing:**
   - User should see "Investigating issue with sandfly-mcp-server..."
   - Progress updates shown
   - Service restarted automatically
   - Query retried and succeeds

4. **Verify logs:**
   ```bash
   kubectl logs -n cortex-system -l app=cortex-api --tail=100 | grep HEAL
   ```

### Manual Test: Simulate CrashLoop

1. **Cause a pod to crashloop:**
   ```bash
   # Edit deployment to use invalid image
   kubectl set image deployment/sandfly-mcp-server \
       -n cortex-system \
       sandfly-mcp-server=invalid-image:latest
   ```

2. **Make a query**

3. **Observe:**
   - Healing detects crashloop
   - Attempts restart
   - Reports failure with diagnosis
   - Recommends manual intervention

### Automated Tests

Create test script at `/Users/ryandahlberg/Projects/cortex/tests/test-self-healing.sh`:

```bash
#!/bin/bash
# Test self-healing system

set -euo pipefail

echo "Test 1: Service scaled to 0"
kubectl scale deployment -n cortex-system sandfly-mcp-server --replicas=0
sleep 5

# Trigger healing via API
curl -X POST http://cortex-api.cortex-system.svc.cluster.local:8000/api/tasks \
    -H "Content-Type: application/json" \
    -d '{"query": "list sandfly hosts", "streaming": true}'

# Wait for healing
sleep 30

# Verify service is back
replicas=$(kubectl get deployment -n cortex-system sandfly-mcp-server -o jsonpath='{.status.readyReplicas}')
if [[ "$replicas" -ge 1 ]]; then
    echo "✓ Test 1 passed: Service restored"
else
    echo "✗ Test 1 failed: Service not restored"
fi
```

## Monitoring & Logging

### Healing Events

All healing attempts are logged with structured format:

```
[2025-12-26T10:30:00Z] [HEAL-WORKER] Starting self-healing for service: sandfly-mcp-server
[2025-12-26T10:30:05Z] [HEAL-WORKER] Found 0 pod(s)
[2025-12-26T10:30:10Z] [HEAL-WORKER] Restarting deployment...
[2025-12-26T10:30:45Z] [HEAL-WORKER] Rollout completed successfully
[2025-12-26T10:30:50Z] [HEAL-WORKER] Service connectivity verified
[2025-12-26T10:30:50Z] [HEAL-WORKER] Healing successful
```

### Metrics to Track

Consider adding these metrics:

- Healing success rate
- Average healing time
- Most common failure types
- Services requiring most healing
- Manual interventions required

### Log Locations

- **API logs**: `kubectl logs -n cortex-system -l app=cortex-api`
- **Worker logs**: `/tmp/heal-worker-<service>-<timestamp>.log` (inside API pod)
- **Kubernetes events**: `kubectl get events -n cortex-system`

## Future Enhancements

### 1. Learning System

Track healing outcomes to improve strategies:

```json
{
  "service": "sandfly-mcp-server",
  "error_type": "connection_refused",
  "fix_applied": "restart_deployment",
  "success": true,
  "time_to_heal": 35,
  "timestamp": "2025-12-26T10:30:00Z"
}
```

### 2. Advanced Diagnostics

- Check resource usage (CPU, memory)
- Analyze network policies
- Verify RBAC permissions
- Check PersistentVolumeClaims
- Inspect ConfigMaps and Secrets

### 3. Proactive Healing

Monitor services and heal before failures:

- High memory usage → preemptive restart
- Slow response times → scale up
- Error rate increase → investigate

### 4. Multi-Service Coordination

Handle dependencies between services:

- If sandfly-mcp-server fails, check sandfly-api
- If proxmox-mcp-server fails, check proxmox connectivity
- Coordinate healing across service chains

### 5. User Notifications

Notify users of healing events:

- Slack/email notifications
- Dashboard alerts
- Historical healing reports

## Best Practices

1. **Always capture context**: Log error details, service state, and diagnostic results
2. **Stream progress**: Keep users informed during healing
3. **Verify fixes**: Always test connectivity after applying fixes
4. **Provide recommendations**: If auto-fix fails, give clear manual steps
5. **Learn from outcomes**: Track what works and what doesn't
6. **Timeout appropriately**: Don't let healing block forever
7. **Graceful degradation**: If healing fails, provide best possible error info
8. **Log everything**: Healing events are valuable for improving the system

## Troubleshooting

### Healing worker not executing

**Check:**
- Script exists at `SELF_HEAL_WORKER_PATH`
- Script is executable (`chmod +x`)
- API pod has kubectl access
- ServiceAccount has required RBAC permissions

**Fix:**
```bash
# Verify script in container
kubectl exec -n cortex-system deploy/cortex-api -- ls -la /app/scripts/

# Check RBAC
kubectl describe serviceaccount -n cortex-system cortex-api
```

### Healing succeeds but retry fails

**Possible causes:**
- Service needs more time to fully start
- Health check passing but service not ready
- Network policy blocking traffic

**Fix:**
- Add longer wait after healing
- Verify service readiness probe
- Check network policies

### Progress not streaming to UI

**Check:**
- SSE headers set correctly
- Frontend consuming SSE stream
- No reverse proxy buffering SSE
- Response not being buffered in middleware

**Fix:**
```javascript
// Ensure SSE headers
res.writeHead(200, {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
  'Connection': 'keep-alive',
  'X-Accel-Buffering': 'no'  // Disable nginx buffering
});
```

## Security Considerations

1. **RBAC**: Healing worker requires elevated permissions (restart pods, scale deployments)
2. **ServiceAccount**: Use dedicated ServiceAccount with least-privilege
3. **Audit**: Log all healing actions for security review
4. **Rate limiting**: Prevent healing loops (max retries per time window)
5. **Validation**: Validate service names to prevent injection

## Summary

The Cortex self-healing system provides automatic detection and remediation of service failures, significantly improving system reliability and user experience. When a service fails, users see progress updates instead of raw errors, and in most cases, the service is automatically restored without manual intervention.

**Key Benefits:**
- Improved uptime and reliability
- Better user experience (progress instead of errors)
- Reduced operational burden
- Detailed diagnostics when auto-fix fails
- Learning system for continuous improvement

**Key Files:**
- `/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api/server.js` - Main healing logic
- `/Users/ryandahlberg/Projects/cortex/scripts/self-heal-worker.sh` - Diagnostic and remediation worker
- `/Users/ryandahlberg/Projects/cortex/docs/self-healing-system.md` - This documentation
