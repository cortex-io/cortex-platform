# Proxmox MCP Server - Quick Reference Card

## 🚀 One-Command Deploy

```bash
cd /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex
./deploy-proxmox.sh
```

## 📋 Individual Commands

```bash
# Build image only
./deploy-proxmox.sh build-only

# Deploy only (use existing image)
./deploy-proxmox.sh deploy-only

# Test only (no deploy)
./deploy-proxmox.sh test-only

# Full pipeline (default)
./deploy-proxmox.sh full
```

## 🔧 Manual Pipeline

```bash
# 1. Build
./scripts/build-proxmox-mcp.sh

# 2. Deploy
./scripts/deploy-proxmox-mcp.sh

# 3. Verify
./scripts/verify-proxmox-mcp.sh

# 4. Integration Test
./scripts/test-proxmox-integration.sh
```

## 🔄 Rollback

```bash
# Auto rollback
./scripts/rollback-proxmox-mcp.sh

# Specific revision
./scripts/rollback-proxmox-mcp.sh revision 5

# Emergency shutdown
./scripts/rollback-proxmox-mcp.sh emergency
```

## 🔍 Debugging

```bash
# View logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server --tail=50

# Follow logs
kubectl logs -n cortex-system deployment/proxmox-mcp-server -f

# Check pod status
kubectl get pods -n cortex-system -l app=proxmox-mcp-server

# Exec into pod
kubectl exec -it -n cortex-system deployment/proxmox-mcp-server -- /bin/bash

# Check deployment
kubectl describe deployment proxmox-mcp-server -n cortex-system
```

## 🧪 Testing

```bash
# Port forward for local testing
kubectl port-forward -n cortex-system deployment/proxmox-mcp-server 3000:3000

# Test health
curl http://localhost:3000/health

# Test tool execution
curl -X POST http://localhost:3000/execute \
  -H "Content-Type: application/json" \
  -d '{"tool":"proxmox_list_vms","arguments":{}}'
```

## 📊 Monitoring

```bash
# Resource usage
kubectl top pod -n cortex-system -l app=proxmox-mcp-server

# Watch pods
watch kubectl get pods -n cortex-system -l app=proxmox-mcp-server

# Get events
kubectl get events -n cortex-system --sort-by='.lastTimestamp' | grep proxmox
```

## 🛠️ Troubleshooting

### Pod CrashLoopBackOff
```bash
kubectl logs -n cortex-system deployment/proxmox-mcp-server --previous
kubectl describe pod -n cortex-system -l app=proxmox-mcp-server
```

### Build Failed
```bash
kubectl logs -n cortex-system job/kaniko-proxmox-mcp-build -f
kubectl get jobs -n cortex-system | grep kaniko
```

### Proxmox API Not Connecting
```bash
kubectl exec -n cortex-system deployment/proxmox-mcp-server -- ping -c 3 10.88.145.100
kubectl exec -n cortex-system deployment/proxmox-mcp-server -- env | grep PROXMOX
```

## ⚙️ Configuration

### Proxmox API
- **Host**: 10.88.145.100:8006
- **Token ID**: root@pam!automation
- **Config**: cortex-system/proxmox-mcp-config
- **Secrets**: cortex-system/proxmox-mcp-secrets

### Service Endpoints
- **MCP**: proxmox-mcp-server.cortex-system.svc.cluster.local:3000
- **Health**: proxmox-mcp-server.cortex-system.svc.cluster.local:8080
- **Alt Name**: proxmox-mcp.cortex-system.svc.cluster.local:3000

### Image Registry
- **Registry**: docker-registry.cortex-system.svc.cluster.local:5000
- **Image**: cortex-mcp-server:latest
- **Tags**: latest, YYYYMMDD-HHMMSS

## 📚 Documentation

- **Complete Pipeline**: PROXMOX-DEPLOYMENT-PIPELINE.md
- **Quick Start**: DEPLOYMENT-QUICK-START.md
- **Summary**: DEPLOYMENT-READY-SUMMARY.md
- **This Card**: QUICK-REFERENCE-CARD.md

## ⏱️ Timeline

| Task | Time |
|------|------|
| Build | 2-5 min |
| Deploy | 1-2 min |
| Verify | 1-2 min |
| Test | 2-3 min |
| **Total** | **11-17 min** |

## ✅ Success Criteria

- [ ] Pod Running and Ready
- [ ] No syntax errors
- [ ] MCP initialized
- [ ] Proxmox API connected
- [ ] Real data returned
- [ ] 15/15 verification tests pass
- [ ] 8/8 integration tests pass

## 🚨 Emergency Contacts

### Quick Actions
```bash
# Scale down immediately
kubectl scale deployment/proxmox-mcp-server -n cortex-system --replicas=0

# Quick rollback
./scripts/rollback-proxmox-mcp.sh

# Delete deployment
kubectl delete deployment proxmox-mcp-server -n cortex-system
```

### Support
- CI/CD Master: Check logs in coordination/masters/cicd/
- DevOps Team: k8s cluster issues
- Security Team: API credential issues

---

**Version**: 1.0.0
**Last Updated**: 2025-12-25
**Status**: Production Ready
