# Proxmox MCP Server - Complete Deployment Pipeline

## Current Status

**Deployment**: Active in cortex-system namespace
**Current Issue**: Syntax error in server.py line 643
**Image Source**: Git clone from https://github.com/ry-ops/proxmox-mcp-server.git
**Registry**: In-cluster registry at docker-registry.cortex-system.svc.cluster.local:5000

## Error Analysis

```
File "/app/proxmox_mcp_server/server.py", line 643
    asyncio.run(main()) "description": "Timeout in seconds (optional)"},
                                                                      ^
SyntaxError: unmatched '}'
```

**Root Cause**: Malformed Python code - likely a merge conflict or incomplete edit in server.py

## Deployment Architecture

### Current Deployment Method
- **Type**: Git-based deployment (alpine/git init container)
- **Image**: python:3.11-slim
- **Init Container**: Clones repo at startup
- **Runtime**: pip install dependencies + wrapper script

### Proposed Deployment Method (After Fix)
- **Type**: Pre-built Docker image
- **Registry**: In-cluster Kaniko-built images
- **Advantages**:
  - Faster startup (no git clone)
  - Version controlled
  - Rollback capability
  - Consistent builds

## Environment Configuration

### Proxmox API Connection
```bash
PROXMOX_HOST=10.88.145.100
PROXMOX_TOKEN_ID=root@pam!automation
PROXMOX_TOKEN_SECRET=9c7c90e1-5d8c-4e32-afe9-8c27f0651f9e
```

### Service Endpoints
```bash
# Internal cluster service
proxmox-mcp-server.cortex-system.svc.cluster.local:3000

# Alternative service name
proxmox-mcp.cortex-system.svc.cluster.local:3000
```

### Ports
- **3000**: MCP HTTP wrapper (main service)
- **8080**: Health checks and metrics (future)

## Pre-Deployment Checklist

### 1. Code Fix Verification
- [ ] Syntax error fixed in server.py line 643
- [ ] Code passes Python linting (flake8/pylint)
- [ ] All imports resolved
- [ ] No additional syntax errors

### 2. Local Testing
- [ ] Server starts without errors
- [ ] MCP initialization succeeds
- [ ] Health endpoint responds (if implemented)
- [ ] Test Proxmox API connection
- [ ] Verify tool execution returns real data (not stubs)

### 3. Build Prerequisites
- [ ] Kaniko builder service account exists
- [ ] Docker config for in-cluster registry
- [ ] Sufficient resources for build (512Mi-2Gi RAM)

### 4. Deployment Prerequisites
- [ ] cortex-system namespace exists
- [ ] ConfigMap mcp-http-wrapper exists
- [ ] Service account has proper RBAC
- [ ] PVC available (if needed)

## Deployment Pipeline Stages

### Stage 1: Build Image (Kaniko)

**Script**: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/scripts/build-proxmox-mcp.sh`

**Process**:
1. Create Kaniko build job from source
2. Kaniko clones cortex repo
3. Builds multi-stage Dockerfile
4. Pushes to in-cluster registry with tags:
   - `cortex-mcp-server:latest`
   - `cortex-mcp-server:YYYYMMDD-HHMMSS`

**Expected Duration**: 2-5 minutes

**Success Criteria**:
- Build job completes successfully
- Image pushed to registry
- Both tags available

### Stage 2: Update Deployment

**Script**: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/scripts/deploy-proxmox-mcp.sh`

**Process**:
1. Update deployment YAML with new image
2. Apply updated deployment
3. Trigger rolling update
4. Monitor rollout status

**Expected Duration**: 1-2 minutes

**Success Criteria**:
- New pods created
- Old pods terminated gracefully
- No crash loops
- Readiness probes passing

### Stage 3: Verification

**Script**: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/scripts/verify-proxmox-mcp.sh`

**Tests**:
1. Pod status check
2. Container logs inspection
3. MCP initialization verification
4. Health endpoint test
5. Proxmox API connectivity test
6. Tool execution test (real data)

**Expected Duration**: 1-2 minutes

**Success Criteria**:
- All pods running
- No error logs
- MCP initialized successfully
- Health checks passing
- Proxmox API returns real data

### Stage 4: Integration Testing

**Script**: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/scripts/test-proxmox-integration.sh`

**Tests**:
1. List VMs tool
2. Get VM status
3. List nodes
4. Storage query
5. Performance metrics

**Expected Duration**: 2-3 minutes

**Success Criteria**:
- All tools return real data
- No stub responses
- API errors handled gracefully
- Response times acceptable (<5s)

## Build Commands

### Quick Build (Kaniko in-cluster)
```bash
# From project root
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex

# Trigger build job
./scripts/build-proxmox-mcp.sh

# Monitor build
kubectl logs -n cortex-system job/kaniko-cortex-mcp-build -f
```

### Manual Docker Build (for testing)
```bash
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex

# Build locally
docker build -t cortex-mcp-server:dev .

# Test locally
docker run -it --rm \
  -e PROXMOX_HOST=10.88.145.100 \
  -e PROXMOX_TOKEN_ID=root@pam!automation \
  -e PROXMOX_TOKEN_SECRET=9c7c90e1-5d8c-4e32-afe9-8c27f0651f9e \
  -p 3000:3000 \
  cortex-mcp-server:dev
```

## Deployment Commands

### Full Deployment Pipeline
```bash
# 1. Build new image
./scripts/build-proxmox-mcp.sh

# 2. Wait for build completion
kubectl wait --for=condition=complete --timeout=600s job/kaniko-cortex-mcp-build -n cortex-system

# 3. Deploy updated image
./scripts/deploy-proxmox-mcp.sh

# 4. Monitor rollout
kubectl rollout status deployment/proxmox-mcp-server -n cortex-system

# 5. Verify deployment
./scripts/verify-proxmox-mcp.sh
```

### Quick Deploy (if image already built)
```bash
# Update deployment to pull latest image
kubectl rollout restart deployment/proxmox-mcp-server -n cortex-system

# Watch progress
kubectl rollout status deployment/proxmox-mcp-server -n cortex-system -w
```

## Verification Commands

### Check Pod Status
```bash
kubectl get pods -n cortex-system -l app=proxmox-mcp-server
```

### Check Logs
```bash
# Latest logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server --tail=50

# Follow logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server -f

# Check for errors
kubectl logs -n cortex-system deployment/proxmox-mcp-server | grep -i error
```

### Test MCP Server
```bash
# Port-forward to access locally
kubectl port-forward -n cortex-system deployment/proxmox-mcp-server 3000:3000

# In another terminal, test endpoints
curl http://localhost:3000/health
curl http://localhost:3000/tools
curl -X POST http://localhost:3000/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "proxmox_list_vms", "arguments": {}}'
```

### Verify Proxmox API Connection
```bash
# Exec into pod
kubectl exec -it -n cortex-system deployment/proxmox-mcp-server -- /bin/bash

# Test Proxmox API directly
python3 << 'EOF'
from proxmoxer import ProxmoxAPI
proxmox = ProxmoxAPI(
    '10.88.145.100',
    token_name='root@pam!automation',
    token_value='9c7c90e1-5d8c-4e32-afe9-8c27f0651f9e',
    verify_ssl=False
)
print(proxmox.nodes.get())
EOF
```

## Rollback Procedures

### Quick Rollback (to previous revision)
```bash
# Rollback deployment
kubectl rollout undo deployment/proxmox-mcp-server -n cortex-system

# Monitor rollback
kubectl rollout status deployment/proxmox-mcp-server -n cortex-system
```

### Rollback to Specific Revision
```bash
# List deployment history
kubectl rollout history deployment/proxmox-mcp-server -n cortex-system

# Rollback to specific revision
kubectl rollout undo deployment/proxmox-mcp-server -n cortex-system --to-revision=6

# Verify rollback
kubectl get pods -n cortex-system -l app=proxmox-mcp-server
```

### Emergency Rollback (to working Git version)
```bash
# Scale down current deployment
kubectl scale deployment/proxmox-mcp-server -n cortex-system --replicas=0

# Update deployment to use git-clone method with last known working commit
kubectl patch deployment proxmox-mcp-server -n cortex-system -p '{
  "spec": {
    "template": {
      "spec": {
        "initContainers": [{
          "name": "git-clone",
          "args": ["clone", "--single-branch", "--branch", "main",
                   "https://github.com/ry-ops/proxmox-mcp-server.git", "/repo"]
        }]
      }
    }
  }
}'

# Scale back up
kubectl scale deployment/proxmox-mcp-server -n cortex-system --replicas=1
```

## Image Management

### List Available Images
```bash
# Via kubectl (if registry has UI)
kubectl run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl http://docker-registry.cortex-system.svc.cluster.local:5000/v2/cortex-mcp-server/tags/list
```

### Tag Management
```bash
# Tag convention:
# - latest: Current production version
# - YYYYMMDD-HHMMSS: Timestamped versions for rollback
# - dev: Development/testing builds
# - vX.Y.Z: Semantic versioning releases
```

### Clean Old Images
```bash
# Delete old build jobs (keeps last 5)
kubectl get jobs -n cortex-system | grep kaniko-cortex-mcp-build | tail -n +6 | awk '{print $1}' | xargs kubectl delete job -n cortex-system
```

## Monitoring and Observability

### Key Metrics to Monitor
1. **Pod Status**: Running, Ready, Restarts
2. **CPU/Memory**: Resource utilization
3. **Log Errors**: Syntax errors, API failures
4. **API Response Time**: Proxmox API calls
5. **MCP Tool Executions**: Success/failure rate

### Grafana Dashboards
- Kubernetes Pod metrics
- Proxmox API performance
- MCP tool execution metrics

### Prometheus Alerts
- Pod crash loops
- High error rate
- API connection failures
- Resource exhaustion

## Troubleshooting Guide

### Issue: Pod in CrashLoopBackOff
**Diagnosis**: Check logs for Python errors
```bash
kubectl logs -n cortex-system deployment/proxmox-mcp-server --previous
```

**Resolution**:
1. Verify syntax errors fixed
2. Check dependencies installed
3. Validate environment variables

### Issue: MCP Initialization Fails
**Diagnosis**: Check wrapper.py and MCP command
```bash
kubectl logs -n cortex-system deployment/proxmox-mcp-server | grep MCP-INIT
```

**Resolution**:
1. Verify mcp-http-wrapper ConfigMap
2. Check MCP_COMMAND environment variable
3. Test MCP server locally

### Issue: Proxmox API Connection Failed
**Diagnosis**: Test API credentials
```bash
kubectl exec -n cortex-system deployment/proxmox-mcp-server -- \
  curl -k https://10.88.145.100:8006/api2/json/access/ticket
```

**Resolution**:
1. Verify PROXMOX_HOST reachable
2. Check token credentials
3. Validate network policies

### Issue: Tools Return Stub Data
**Diagnosis**: Check server implementation
```bash
kubectl logs -n cortex-system deployment/proxmox-mcp-server | grep -i stub
```

**Resolution**:
1. Verify server.py has real API calls
2. Check Proxmox API permissions
3. Validate tool implementations

## Post-Deployment Validation

### Success Criteria Checklist
- [ ] Pods running without restarts
- [ ] No error logs in past 5 minutes
- [ ] MCP initialized successfully
- [ ] Health endpoint responding
- [ ] Proxmox API connection verified
- [ ] Tools return real data (not stubs)
- [ ] Response times < 5 seconds
- [ ] Memory usage < 256Mi
- [ ] CPU usage < 100m baseline

### Integration Tests
```bash
# Run full integration test suite
./scripts/test-proxmox-integration.sh

# Expected results:
# - list_vms: Returns actual VM list
# - get_vm_status: Returns real VM state
# - list_nodes: Returns Proxmox nodes
# - get_storage: Returns storage info
# - get_cluster_resources: Returns cluster data
```

## Documentation Updates Required

After successful deployment:
1. Update MCP server registry in coordination/mcp-registry/
2. Document new endpoints in API documentation
3. Update Cortex Chat integration guides
4. Record deployment in changelog
5. Update monitoring dashboards

## Next Steps

1. **Fix Code**: Resolve syntax error in server.py line 643
2. **Test Locally**: Verify fix works before building
3. **Build Image**: Use Kaniko or Docker to build new image
4. **Deploy**: Follow deployment pipeline
5. **Verify**: Run all verification tests
6. **Monitor**: Watch for 24 hours post-deployment
7. **Document**: Update knowledge base with lessons learned

## Files Created by This Pipeline

- `scripts/build-proxmox-mcp.sh` - Build automation
- `scripts/deploy-proxmox-mcp.sh` - Deployment automation
- `scripts/verify-proxmox-mcp.sh` - Verification tests
- `scripts/test-proxmox-integration.sh` - Integration tests
- `scripts/rollback-proxmox-mcp.sh` - Rollback automation
- `k8s/proxmox-mcp-deployment-updated.yaml` - Updated deployment manifest

---

**Last Updated**: 2025-12-25
**Pipeline Version**: 1.0.0
**Status**: Ready for code fix and deployment
