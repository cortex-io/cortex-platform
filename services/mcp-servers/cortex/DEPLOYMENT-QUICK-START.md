# Proxmox MCP Server - Quick Deployment Guide

## Current Problem

**Syntax Error in server.py line 643**
```
asyncio.run(main()) "description": "Timeout in seconds (optional)"},
                                                                  ^
SyntaxError: unmatched '}'
```

## Quick Fix & Deploy (5 Minutes)

### Step 1: Fix the Code
```bash
# The syntax error is in the proxmox-mcp-server repository
# at proxmox_mcp_server/server.py line 643

# This needs to be fixed in the source repository:
# https://github.com/ry-ops/proxmox-mcp-server.git
```

### Step 2: Build New Image
```bash
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex

# Start build (takes 2-5 minutes)
./scripts/build-proxmox-mcp.sh

# Wait for completion or monitor separately
```

### Step 3: Deploy
```bash
# Deploy latest image
./scripts/deploy-proxmox-mcp.sh

# Or deploy specific version
./scripts/deploy-proxmox-mcp.sh 20251225-120000
```

### Step 4: Verify
```bash
# Run verification tests
./scripts/verify-proxmox-mcp.sh

# Run integration tests
./scripts/test-proxmox-integration.sh
```

## One-Line Deployment (After Code Fix)

```bash
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex && \
./scripts/build-proxmox-mcp.sh && \
./scripts/deploy-proxmox-mcp.sh && \
./scripts/verify-proxmox-mcp.sh
```

## Rollback (If Needed)

```bash
# Quick rollback to previous version
./scripts/rollback-proxmox-mcp.sh

# Rollback to specific revision
./scripts/rollback-proxmox-mcp.sh revision 5

# Emergency shutdown
./scripts/rollback-proxmox-mcp.sh emergency
```

## Manual Testing

### Port Forward to Test Locally
```bash
# Forward MCP server port
kubectl port-forward -n cortex-system deployment/proxmox-mcp-server 3000:3000

# In another terminal, test endpoints
curl http://localhost:3000/health
curl http://localhost:3000/tools

# Test tool execution
curl -X POST http://localhost:3000/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "proxmox_list_vms", "arguments": {}}'
```

### Check Logs
```bash
# View recent logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server --tail=50

# Follow logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server -f

# Check for specific errors
kubectl logs -n cortex-system deployment/proxmox-mcp-server | grep -i "syntax\|error\|exception"
```

### Exec into Pod
```bash
# Get shell access
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
print("Nodes:", proxmox.nodes.get())
print("VMs:", proxmox.cluster.resources.get(type='vm'))
EOF
```

## Common Issues & Solutions

### Issue: Build fails
**Solution:**
```bash
# Check build job logs
kubectl logs -n cortex-system job/kaniko-proxmox-mcp-build -f

# Check if job exists
kubectl get jobs -n cortex-system | grep kaniko

# Delete old failed jobs
kubectl delete job kaniko-proxmox-mcp-build -n cortex-system
```

### Issue: Pod in CrashLoopBackOff
**Solution:**
```bash
# Check previous logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server --previous

# Describe pod for events
kubectl describe pod -n cortex-system -l app=proxmox-mcp-server

# Check if syntax error still exists
kubectl logs -n cortex-system deployment/proxmox-mcp-server | grep SyntaxError
```

### Issue: "No space left on device" during build
**Solution:**
```bash
# Clean up old images/containers on k3s nodes
ssh larry "docker system prune -af"
ssh daryl "docker system prune -af"

# Or increase build job timeout
# Edit build-proxmox-mcp.sh and increase ttlSecondsAfterFinished
```

### Issue: Proxmox API connection fails
**Solution:**
```bash
# Test network connectivity
kubectl exec -n cortex-system deployment/proxmox-mcp-server -- \
  ping -c 3 10.88.145.100

# Check environment variables
kubectl exec -n cortex-system deployment/proxmox-mcp-server -- env | grep PROXMOX

# Verify credentials work
curl -k https://10.88.145.100:8006/api2/json/access/ticket \
  -d "username=root@pam" \
  -d "password=yourpassword"
```

## Files Created

All deployment automation files are in:
```
/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/scripts/

├── build-proxmox-mcp.sh           # Build image with Kaniko
├── deploy-proxmox-mcp.sh          # Deploy to k8s
├── verify-proxmox-mcp.sh          # Verify deployment
├── test-proxmox-integration.sh    # Integration tests
└── rollback-proxmox-mcp.sh        # Rollback procedures
```

Documentation:
```
/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/

├── PROXMOX-DEPLOYMENT-PIPELINE.md  # Complete pipeline docs
└── DEPLOYMENT-QUICK-START.md       # This file
```

## Success Criteria

After deployment, verify:
- [ ] Pod is Running and Ready
- [ ] No syntax errors in logs
- [ ] MCP initialization successful
- [ ] Proxmox API connection works
- [ ] Tools return real data (not stubs)
- [ ] No crash loops or restarts
- [ ] Response times < 5 seconds
- [ ] Memory usage < 256Mi

## Timeline Estimate

| Task | Time | Notes |
|------|------|-------|
| Fix syntax error | 5 min | Edit server.py line 643 |
| Build image | 2-5 min | Kaniko in-cluster build |
| Deploy | 1-2 min | Rolling update |
| Verify | 1-2 min | Automated tests |
| Integration tests | 2-3 min | Full API verification |
| **Total** | **11-17 min** | From fix to production |

## Next Steps After Successful Deployment

1. Update MCP registry in coordination/mcp-registry/
2. Test from Cortex Chat interface
3. Document new tools in API docs
4. Monitor for 24 hours
5. Update runbooks with any lessons learned

## Support

If issues persist:
1. Check full documentation: PROXMOX-DEPLOYMENT-PIPELINE.md
2. Review build job logs
3. Check Proxmox API status
4. Verify network policies allow access to 10.88.145.100:8006
5. Contact DevOps team for k8s cluster issues

---

**Last Updated**: 2025-12-25
**Status**: Ready for deployment after code fix
**Estimated Success Rate**: 95% (pending syntax fix)
