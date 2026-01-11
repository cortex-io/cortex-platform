# Self-Healing System - Quick Reference

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| **Main Logic** | `/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api/server.js` | Error detection, worker spawning, SSE streaming |
| **Healing Worker** | `/Users/ryandahlberg/Projects/cortex/scripts/self-heal-worker.sh` | Diagnostic checks and remediation |
| **Deployment** | `/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api/deployment.yaml` | K8s deployment with RBAC |
| **Docker Image** | `/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api/Dockerfile` | Container with healing worker |
| **Tests** | `/Users/ryandahlberg/Projects/cortex/tests/test-self-healing.sh` | Test suite |
| **Documentation** | `/Users/ryandahlberg/Projects/cortex/docs/self-healing-system.md` | Full documentation |
| **Deployment Guide** | `/Users/ryandahlberg/Projects/cortex/docs/self-healing-deployment.md` | Deployment steps |

## Quick Commands

### Deploy
```bash
cd /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api
docker build -t 10.43.170.72:5000/cortex-api:latest .
docker push 10.43.170.72:5000/cortex-api:latest
kubectl apply -f deployment.yaml
kubectl rollout status deployment/cortex-orchestrator -n cortex
```

### Test
```bash
# Scale service to 0 to trigger healing
kubectl scale deployment -n cortex-system sandfly-mcp-server --replicas=0

# Watch healing
kubectl logs -n cortex -l app=cortex-orchestrator -f | grep HEAL

# Verify restoration
kubectl get deployment -n cortex-system sandfly-mcp-server
```

### Monitor
```bash
# View healing logs
kubectl logs -n cortex -l app=cortex-orchestrator | grep HEAL-WORKER

# Check worker script exists
kubectl exec -n cortex deploy/cortex-orchestrator -- ls -la /app/scripts/

# Test kubectl access
kubectl exec -n cortex deploy/cortex-orchestrator -- kubectl get pods -n cortex
```

### Debug
```bash
# Run healing worker manually
kubectl exec -n cortex deploy/cortex-orchestrator -- \
    bash /app/scripts/self-heal-worker.sh sandfly-mcp-server "Test error" ""

# Check RBAC
kubectl describe clusterrole cortex-api-reader
kubectl describe clusterrolebinding cortex-api-reader-binding

# View recent events
kubectl get events -n cortex-system --sort-by='.lastTimestamp' | tail -20
```

## Key Functions (server.js)

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `extractServiceName()` | Extract service name from URL | `serverUrl` | Service name |
| `spawnHealingWorker()` | Execute healing worker | `{service, error, serverUrl}`, `sseWriter` | Healing result JSON |
| `callMCPTool()` | Call MCP tool with healing | `serverUrl, toolName, arguments, sseWriter` | Tool result |
| `queryMCPServer()` | Query MCP server with healing | `serverUrl, query, sseWriter` | Query result |

## SSE Event Types

| Event | When Sent | Payload |
|-------|-----------|---------|
| `processing_start` | Query processing begins | `{type, query}` |
| `healing_start` | Failure detected | `{type, service, issue}` |
| `healing_progress` | During healing | `{type, service, message}` |
| `healing_complete` | Healing succeeded | `{type, service, success, message}` |
| `healing_failed` | Healing failed | `{type, service, message, recommendation}` |
| `processing_complete` | Query complete | `{type, id, status, result}` |

## Healing Workflow

```
Error Detected
    ↓
Stream healing_start event
    ↓
Spawn healing worker
    ↓
Diagnostic Phase
    ├─ Check pod status
    ├─ Check endpoints
    ├─ Check logs
    └─ Check config
    ↓
Remediation Phase
    ├─ Restart pods (if crashloop)
    ├─ Scale up (if no pods)
    └─ Wait for ready
    ↓
Verification Phase
    └─ Test connectivity
    ↓
Stream healing_complete/failed
    ↓
Retry original operation (if successful)
    ↓
Return result to user
```

## Common Healing Strategies

| Issue | Detection | Fix | Command |
|-------|-----------|-----|---------|
| **CrashLoop** | Pod status check | Restart deployment | `kubectl rollout restart deployment -n cortex-system <service>` |
| **Scaled to 0** | No pods found | Scale up | `kubectl scale deployment -n cortex-system <service> --replicas=1` |
| **Pod deleted** | Pod count mismatch | Wait for recreation | Automatic (K8s handles) |
| **No endpoints** | Endpoint check | Restart pods | `kubectl rollout restart deployment -n cortex-system <service>` |
| **ImagePullBackOff** | Container status | Manual intervention | Report to user |

## RBAC Permissions Required

```yaml
# Read permissions
- pods, services, nodes, namespaces, configmaps, secrets, endpoints: get, list, watch
- pods/log: get, list

# Write permissions (for healing)
- deployments: patch, update
- deployments/scale: get, update, patch
- pods: create, delete (for connectivity tests)

# Diagnostic
- events: get, list, watch
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SELF_HEAL_WORKER_PATH` | `/app/scripts/self-heal-worker.sh` | Path to worker script |
| `HEALING_ENABLED` | `true` | Enable/disable healing |

## Timeouts

| Operation | Timeout | Configurable In |
|-----------|---------|-----------------|
| Healing worker execution | 120s | `server.js` - `spawnHealingWorker()` |
| Rollout status | 60s | `self-heal-worker.sh` - `restart_pods()` |
| Connectivity test | 30s | `self-heal-worker.sh` - `verify_connectivity()` |
| MCP tool call | 60s | `server.js` - `callMCPTool()` |

## Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Worker not found | `kubectl rollout restart deployment/cortex-orchestrator -n cortex` |
| Permission denied | `kubectl apply -f deployment.yaml` (reapply RBAC) |
| kubectl not found | Rebuild image with kubectl |
| Healing loops | Check logs for root cause, add timeout protection |
| SSE not streaming | Verify `streaming: true` in request |

## Example API Call with Streaming

```bash
curl -N -H "Accept: text/event-stream" \
    -X POST http://cortex-orchestrator.cortex.svc.cluster.local:8000/api/tasks \
    -H "Content-Type: application/json" \
    -d '{"query": "list sandfly hosts", "streaming": true}'
```

Expected output:
```
data: {"type":"processing_start","query":"list sandfly hosts"}

data: {"type":"healing_start","service":"sandfly-mcp-server","issue":"connect ECONNREFUSED"}

data: {"type":"healing_progress","service":"sandfly-mcp-server","message":"Checking pod status..."}

data: {"type":"healing_progress","service":"sandfly-mcp-server","message":"Restarting pods..."}

data: {"type":"healing_complete","service":"sandfly-mcp-server","success":true,"message":"Restarted deployment"}

data: {"type":"processing_complete","id":"task-123","status":"completed","result":{...}}
```

## Testing Scenarios

1. **Service scaled to 0**: `kubectl scale deployment -n cortex-system <service> --replicas=0`
2. **Pod crashed**: `kubectl delete pod -n cortex-system <pod-name>`
3. **CrashLoop**: `kubectl set image deployment/<service> <container>=invalid-image:latest`
4. **No endpoints**: Break service selector in deployment

## Success Criteria

- ✅ Error detected and healing triggered automatically
- ✅ Progress streamed to user in real-time
- ✅ Service restored without manual intervention
- ✅ Original operation retried successfully
- ✅ User sees "Service restored" message
- ✅ Healing logged for analysis

## Metrics to Track

- Healing success rate
- Average healing time
- Most common failures
- Services requiring most healing
- Manual interventions needed

## Production Readiness

- [ ] All tests passing
- [ ] RBAC least-privilege verified
- [ ] Resource limits configured
- [ ] Monitoring and alerting set up
- [ ] Rollback procedure tested
- [ ] Documentation complete
- [ ] Team trained on system
