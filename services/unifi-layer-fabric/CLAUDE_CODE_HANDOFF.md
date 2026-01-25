# Claude Code Handoff: UniFi Layer Fabric Deployment

## Context

You're continuing a design session where we built a **serverless AI layer fabric** for UniFi network management. The architecture treats every capability (routing, reasoning, execution, memory) as an independent Kubernetes layer that scales to zero via KEDA.

This replaces the traditional "one big LLM" approach with composable layers that wake on demand.

## What's Been Built

The `unifi-layer-fabric/` directory contains:

```
unifi-layer-fabric/
├── README.md                           # Architecture overview
├── docs/
│   └── QUICKSTART.md                   # Deployment guide
├── argocd/
│   ├── applicationset.yaml             # GitOps deployment
│   └── secrets.yaml                    # Credential templates
└── charts/
    ├── cortex-activator/               # Always-on query router
    ├── cortex-qdrant/                  # Always-on vector memory
    ├── reasoning-classifier/           # Qwen2-0.5B (fast classification)
    ├── reasoning-slm/                  # Phi-3-3.8B (tool calling)
    ├── execution-unifi-api/            # UniFi API operations
    ├── execution-unifi-ssh/            # SSH failover/diagnostics
    └── cortex-telemetry/               # Metrics, audit, learning
```

## What Needs To Be Done

### 1. Build Container Images

The Helm charts reference these images that need source code + Dockerfiles:

| Image | Purpose | Language |
|-------|---------|----------|
| `ghcr.io/ry-ops/cortex-activator` | Query routing, layer orchestration | Python/FastAPI or Go |
| `ghcr.io/ry-ops/unifi-action-engine` | UniFi API wrapper | Python |
| `ghcr.io/ry-ops/unifi-ssh-gateway` | SSH command execution | Python |
| `ghcr.io/ry-ops/cortex-telemetry` | Metrics collection, Qdrant writes | Python |

### 2. Push to GitHub

Create repo: `github.com/ry-ops/unifi-layer-fabric`

Structure:
```
unifi-layer-fabric/
├── src/
│   ├── activator/           # Cortex Activator source
│   ├── action-engine/       # UniFi Action Engine source
│   ├── ssh-gateway/         # SSH Gateway source
│   └── telemetry/           # Telemetry collector source
├── charts/                  # Helm charts (already built)
├── argocd/                  # ArgoCD manifests
├── .github/workflows/       # CI/CD for building images
└── environments/
    └── production/          # Production value overrides
```

### 3. Configure ArgoCD

```bash
# Add the ApplicationSet to ArgoCD
kubectl apply -f argocd/applicationset.yaml
```

### 4. Create Secrets

```bash
kubectl create namespace cortex-unifi

kubectl create secret generic unifi-credentials \
  --namespace cortex-unifi \
  --from-literal=api-key="SITE_MANAGER_API_KEY" \
  --from-literal=controller-host="https://UDM_PRO_IP" \
  --from-literal=controller-username="admin" \
  --from-literal=controller-password="CONTROLLER_PASSWORD" \
  --from-literal=ssh-host="UDM_PRO_IP" \
  --from-literal=ssh-username="root" \
  --from-literal=ssh-password="SSH_PASSWORD"
```

### 5. Monitor Deployment

```bash
# Watch ArgoCD sync
argocd app list | grep unifi

# Watch pods
kubectl get pods -n cortex-unifi -w

# Check KEDA ScaledObjects
kubectl get scaledobjects -n cortex-unifi
```

### 6. Test

```bash
# Port forward to activator
kubectl port-forward svc/cortex-activator -n cortex-unifi 8080:8080

# Test query
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "List all clients on the network"}'
```

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER QUERY                                     │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    CORTEX ACTIVATOR (Always On, ~128MB)                  │
│  1. Keyword match → direct to execution layer (90% of queries)          │
│  2. Ambiguous → wake classifier layer                                    │
│  3. Complex → wake SLM reasoning layer                                   │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ REASONING     │    │ QDRANT        │    │ EXECUTION     │
│ (Scale 0→1)   │    │ (Always On)   │    │ (Scale 0→1)   │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ • Classifier  │    │ • Operations  │    │ • UniFi API   │
│   (0.5B)      │    │ • Configs     │    │ • SSH Gateway │
│ • SLM (3.8B)  │    │ • Patterns    │    │               │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Memory Profile

| State | Memory | What's Running |
|-------|--------|----------------|
| **Idle** | ~640MB | Activator + Qdrant |
| **Simple Query** | ~1GB | + Execution layer |
| **Complex Query** | ~4GB | + SLM reasoning |
| **Full Active** | ~4.5GB | All layers warm |

## Key Files to Review

1. `charts/cortex-activator/values.yaml` - Routing rules, layer endpoints
2. `charts/reasoning-slm/values.yaml` - Model config, system prompt
3. `charts/execution-unifi-api/values.yaml` - Action definitions
4. `charts/execution-unifi-ssh/values.yaml` - Allowed SSH commands
5. `argocd/applicationset.yaml` - GitOps deployment config

## Environment Details

- **Cluster**: k3s on Proxmox (7 nodes)
- **RAM**: 64GB total, ~8-12GB available for Cortex
- **CPU**: 20 cores
- **GPU**: None (CPU inference only)
- **Storage**: Longhorn CSI
- **GitOps**: ArgoCD
- **UniFi**: 1 site, UDM Pro

## After Deployment: Blog Post

Once running, create a blog post for ry-ops.dev covering:

1. **The Journey** - From monolithic LLM to composable layers
2. **Why Serverless AI** - Cost savings, resource efficiency
3. **Architecture Deep Dive** - How layers communicate
4. **Real Performance** - Cold start times, memory usage
5. **Learning Loop** - How it improves over time
6. **What's Next** - Extending to other MCP servers

## Questions for Ryan

Before deploying, confirm:
1. UDM Pro IP address for controller-host and ssh-host
2. Site Manager API key (from ui.com account)
3. Controller admin credentials
4. SSH credentials for UDM Pro
5. GitHub repo name (suggested: `ry-ops/unifi-layer-fabric`)
6. Container registry (suggested: `ghcr.io/ry-ops/`)
