# Self-Healing System Deployment Guide

## Overview

This guide covers deploying the Cortex self-healing system to your K3s cluster.

## Prerequisites

- K3s cluster running
- kubectl access to the cluster
- Docker registry accessible from cluster (10.43.170.72:5000)
- Cortex API already deployed (or being deployed)

## Deployment Steps

### Step 1: Build and Push Docker Image

The self-healing worker is embedded in the cortex-api image.

```bash
cd /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api

# Build image with self-healing worker
docker build -t 10.43.170.72:5000/cortex-api:latest .

# Push to registry
docker push 10.43.170.72:5000/cortex-api:latest
```

**What's included:**
- Updated `server.js` with self-healing logic
- `self-heal-worker.sh` script in `/app/scripts/`
- bash, jq, kubectl, and required tools

### Step 2: Update RBAC Permissions

The self-healing system requires additional RBAC permissions to manage pods and deployments.

**Already included in deployment.yaml:**
- Pod restart permissions (`patch`, `update` on deployments)
- Scaling permissions (`deployments/scale`)
- Pod creation/deletion (for connectivity tests)
- Log reading (`pods/log`)
- Event reading (for diagnostics)

**Verify RBAC:**
```bash
kubectl describe clusterrole cortex-api-reader
```

Should show:
- `deployments`: get, list, watch, patch, update
- `deployments/scale`: get, update, patch
- `pods`: get, list, watch, create, delete
- `pods/log`: get, list
- `endpoints`: get, list, watch
- `events`: get, list, watch

### Step 3: Deploy to Cluster

```bash
cd /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api

# Apply deployment
kubectl apply -f deployment.yaml

# Wait for rollout
kubectl rollout status deployment/cortex-orchestrator -n cortex
```

### Step 4: Verify Deployment

```bash
# Check pod is running
kubectl get pods -n cortex -l app=cortex-orchestrator

# Check self-healing worker exists
kubectl exec -n cortex deploy/cortex-orchestrator -- ls -la /app/scripts/

# Should show:
# -rwxr-xr-x    1 root     root         12345 Dec 26 10:00 self-heal-worker.sh

# Check kubectl access
kubectl exec -n cortex deploy/cortex-orchestrator -- kubectl get pods -n cortex

# Check environment variables
kubectl exec -n cortex deploy/cortex-orchestrator -- env | grep HEAL

# Should show:
# SELF_HEAL_WORKER_PATH=/app/scripts/self-heal-worker.sh
# HEALING_ENABLED=true
```

### Step 5: Test Self-Healing

Run the test suite:

```bash
cd /Users/ryandahlberg/Projects/cortex

# Copy test script to a location accessible from cluster
kubectl create configmap self-healing-tests \
    --from-file=test-self-healing.sh=/Users/ryandahlberg/Projects/cortex/tests/test-self-healing.sh \
    -n cortex

# Run tests from a debug pod
kubectl run test-runner --rm -it \
    --image=bitnami/kubectl:latest \
    --restart=Never \
    -n cortex \
    -- bash -c "
    apk add --no-cache bash curl jq
    kubectl get configmap self-healing-tests -n cortex -o jsonpath='{.data.test-self-healing\.sh}' > /tmp/test.sh
    chmod +x /tmp/test.sh
    /tmp/test.sh
"
```

Or test manually:

```bash
# Test 1: Scale service to 0
kubectl scale deployment -n cortex-system sandfly-mcp-server --replicas=0

# Make a query via Cortex UI or API
curl -X POST http://cortex-orchestrator.cortex.svc.cluster.local:8000/api/tasks \
    -H "Content-Type: application/json" \
    -d '{"query": "list sandfly hosts", "streaming": true}'

# Watch healing in action
kubectl logs -n cortex -l app=cortex-orchestrator -f | grep HEAL

# Verify service restored
kubectl get deployment -n cortex-system sandfly-mcp-server
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SELF_HEAL_WORKER_PATH` | `/app/scripts/self-heal-worker.sh` | Path to healing worker script |
| `HEALING_ENABLED` | `true` | Enable/disable self-healing |

### Timeouts

Edit `self-heal-worker.sh` to adjust timeouts:

```bash
# Rollout timeout
kubectl rollout status deployment ... --timeout=60s  # Change 60s

# Connectivity test timeout
kubectl run ... --timeout=30s  # Change 30s
```

### Target Namespace

By default, healing targets `cortex-system` namespace. To change:

```bash
# In self-heal-worker.sh
NAMESPACE="your-namespace"
```

## Monitoring

### Check Healing Logs

```bash
# Real-time logs
kubectl logs -n cortex -l app=cortex-orchestrator -f | grep HEAL

# Recent healing events
kubectl logs -n cortex -l app=cortex-orchestrator --tail=100 | grep "HEAL-WORKER"

# Specific healing attempt
kubectl exec -n cortex deploy/cortex-orchestrator -- \
    cat /tmp/heal-worker-sandfly-mcp-server-*.log
```

### Metrics to Monitor

```bash
# Count healing attempts
kubectl logs -n cortex -l app=cortex-orchestrator | grep "Starting self-healing" | wc -l

# Count successful healings
kubectl logs -n cortex -l app=cortex-orchestrator | grep "Healing successful" | wc -l

# Count failed healings
kubectl logs -n cortex -l app=cortex-orchestrator | grep "Healing failed" | wc -l

# Average healing time
kubectl logs -n cortex -l app=cortex-orchestrator | grep "Starting self-healing\|Remediation Complete" | # parse timestamps
```

## Troubleshooting

### Issue: Healing worker not found

**Symptoms:**
```
Error: Cannot find healing worker at /app/scripts/self-heal-worker.sh
```

**Solution:**
```bash
# Verify script in image
docker run --rm 10.43.170.72:5000/cortex-api:latest ls -la /app/scripts/

# Rebuild and push image
cd /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api
docker build -t 10.43.170.72:5000/cortex-api:latest .
docker push 10.43.170.72:5000/cortex-api:latest

# Force pod restart
kubectl rollout restart deployment/cortex-orchestrator -n cortex
```

### Issue: Permission denied errors

**Symptoms:**
```
Error from server (Forbidden): deployments.apps "sandfly-mcp-server" is forbidden
```

**Solution:**
```bash
# Check RBAC
kubectl describe clusterrolebinding cortex-api-reader-binding

# Verify ServiceAccount
kubectl get serviceaccount -n cortex cortex-api

# Reapply RBAC
kubectl apply -f deployment.yaml

# Check pod's ServiceAccount
kubectl get pod -n cortex -l app=cortex-orchestrator -o jsonpath='{.items[0].spec.serviceAccountName}'
```

### Issue: kubectl not found in pod

**Symptoms:**
```
bash: kubectl: command not found
```

**Solution:**
```bash
# Verify kubectl in image
docker run --rm 10.43.170.72:5000/cortex-api:latest kubectl version --client

# Rebuild with kubectl
cd /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-chat/cortex-api
docker build -t 10.43.170.72:5000/cortex-api:latest .
docker push 10.43.170.72:5000/cortex-api:latest
kubectl rollout restart deployment/cortex-orchestrator -n cortex
```

### Issue: Healing succeeds but retry fails

**Symptoms:**
```
Healing successful: Restarted deployment
Retry failed: connect ECONNREFUSED
```

**Possible causes:**
- Service needs more time to fully start
- Readiness probe not configured
- Network policy blocking traffic

**Solution:**
```bash
# Add wait time in self-heal-worker.sh after restart
if restart_pods; then
    FIX_APPLIED="Restarted deployment $DEPLOYMENT"
    sleep 15  # Add longer wait

    # Verify readiness
    if kubectl wait --for=condition=ready pod \
        -l "app=$DEPLOYMENT" \
        -n "$NAMESPACE" \
        --timeout=60s; then
        SUCCESS=true
    fi
fi

# Check readiness probe
kubectl get deployment -n cortex-system sandfly-mcp-server -o yaml | grep -A 5 readinessProbe

# Check network policies
kubectl get networkpolicies -n cortex-system
```

### Issue: Progress not streaming to UI

**Symptoms:**
- User sees immediate error instead of healing progress

**Check:**
```bash
# Verify SSE support
curl -N -H "Accept: text/event-stream" \
    -X POST http://cortex-orchestrator.cortex.svc.cluster.local:8000/api/tasks \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "streaming": true}'

# Should see SSE events:
# data: {"type":"processing_start",...}
```

**Solution:**
- Ensure frontend is consuming SSE stream properly
- Check for reverse proxy buffering
- Verify streaming parameter is true

## Rollback

If self-healing causes issues, rollback:

```bash
# Disable healing via environment variable
kubectl set env deployment/cortex-orchestrator \
    -n cortex \
    HEALING_ENABLED=false

# Or rollback to previous version
kubectl rollout undo deployment/cortex-orchestrator -n cortex

# Or use previous image
kubectl set image deployment/cortex-orchestrator \
    -n cortex \
    cortex-api=10.43.170.72:5000/cortex-api:previous-version
```

## Production Checklist

Before deploying to production:

- [ ] Test all healing scenarios (scaled to 0, crashloop, pod deletion)
- [ ] Verify RBAC permissions are least-privilege
- [ ] Configure appropriate resource limits
- [ ] Set up monitoring and alerting for healing events
- [ ] Document manual intervention procedures
- [ ] Test rollback procedure
- [ ] Configure log retention for healing logs
- [ ] Set up metrics collection for healing success rate
- [ ] Test healing with multiple simultaneous failures
- [ ] Verify healing doesn't cause cascading failures

## Next Steps

1. Monitor healing events in production
2. Tune timeouts based on actual service startup times
3. Add more healing strategies for specific failure modes
4. Implement proactive healing (before failures occur)
5. Build learning system to improve healing strategies
6. Create dashboard for healing metrics
7. Set up alerts for repeated healing attempts

## Support

For issues or questions:
1. Check logs: `kubectl logs -n cortex -l app=cortex-orchestrator`
2. Review documentation: `/Users/ryandahlberg/Projects/cortex/docs/self-healing-system.md`
3. Run tests: `/Users/ryandahlberg/Projects/cortex/tests/test-self-healing.sh`
4. Verify RBAC and configuration
