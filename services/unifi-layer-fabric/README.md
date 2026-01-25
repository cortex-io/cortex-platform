# UniFi Layer Fabric

**Serverless AI for UniFi network management.**

Every capability is a layer. Every layer scales to zero.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER QUERY                                     │
│                "Block the client causing WiFi issues"                    │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CORTEX ACTIVATOR (Always On)                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Keyword Match: "block" + "client" → UniFi domain               │ │
│  │ 2. Complexity: Needs reasoning (not simple lookup)                 │ │
│  │ 3. Wake: reasoning-slm, execution-unifi-api                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ REASONING-SLM   │ │ QDRANT          │ │ EXECUTION-API   │
│ (Phi-3 3.8B)    │ │ (Always On)     │ │ (UniFi API)     │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • Parse intent  │ │ • Past ops      │ │ • Site Manager  │
│ • Select tool   │ │ • Configs       │ │ • Network API   │
│ • Gen params    │ │ • Patterns      │ │ • Client mgmt   │
│                 │ │                 │ │                 │
│ KEDA: 0→1       │ │ PVC-backed      │ │ KEDA: 0→1       │
│ ~2.5GB warm     │ │ ~512MB          │ │ ~200MB warm     │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TELEMETRY LAYER                                  │
│  Query → Tool → Outcome → Qdrant (learning) + Prometheus (metrics)      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Layers

| Layer | Purpose | Memory | Cold Start | Scale |
|-------|---------|--------|------------|-------|
| `cortex-activator` | Route queries, wake layers | 128MB | Always on | 2 replicas |
| `cortex-qdrant` | Vector memory, RAG | 512MB | Always on | 1 replica |
| `reasoning-classifier` | Intent classification | 400MB | ~5s | 0→1 |
| `reasoning-slm` | Tool calling, reasoning | 2.5GB | ~12s | 0→1 |
| `execution-unifi-api` | UniFi API operations | 200MB | ~3s | 0→1 |
| `execution-unifi-ssh` | UDM Pro SSH (failover) | 100MB | ~3s | 0→1 |
| `cortex-telemetry` | Metrics, audit, learning | 128MB | ~2s | 0→1 |

**Total when idle:** ~640MB  
**Total when active:** ~4GB  
**Memory savings:** 85%+ vs always-on

## Quick Start

### Prerequisites

- Kubernetes cluster (k3s recommended)
- KEDA installed with HTTP Add-on
- ArgoCD for GitOps deployment
- Longhorn or similar CSI for PVCs

### Deploy with ArgoCD

```bash
# Add the ApplicationSet
kubectl apply -f argocd/applicationset.yaml
```

### Deploy with Helm (manual)

```bash
# Create namespace
kubectl create namespace cortex-unifi

# Create secrets
kubectl create secret generic unifi-credentials \
  --namespace cortex-unifi \
  --from-literal=api-key="YOUR_SITE_MANAGER_KEY" \
  --from-literal=controller-host="https://192.168.1.1" \
  --from-literal=controller-username="admin" \
  --from-literal=controller-password="YOUR_PASSWORD" \
  --from-literal=ssh-host="192.168.1.1" \
  --from-literal=ssh-username="root" \
  --from-literal=ssh-password="YOUR_SSH_PASSWORD"

# Install layers (order matters for dependencies)
helm install cortex-qdrant ./charts/cortex-qdrant -n cortex-unifi
helm install cortex-activator ./charts/cortex-activator -n cortex-unifi
helm install reasoning-classifier ./charts/reasoning-classifier -n cortex-unifi
helm install reasoning-slm ./charts/reasoning-slm -n cortex-unifi
helm install execution-unifi-api ./charts/execution-unifi-api -n cortex-unifi
helm install execution-unifi-ssh ./charts/execution-unifi-ssh -n cortex-unifi
helm install cortex-telemetry ./charts/cortex-telemetry -n cortex-unifi
```

## Configuration

### UniFi Credentials

Store in Kubernetes secret `unifi-credentials`:

| Key | Description |
|-----|-------------|
| `api-key` | Site Manager API key (from ui.com) |
| `controller-host` | Local controller URL |
| `controller-username` | Controller admin username |
| `controller-password` | Controller admin password |
| `ssh-host` | UDM Pro IP address |
| `ssh-username` | SSH username (usually `root`) |
| `ssh-password` | SSH password |

### Layer Tuning

Each layer has its own `values.yaml`. Key settings:

```yaml
# reasoning-slm/values.yaml
model:
  name: "microsoft/Phi-3-mini-4k-instruct-gguf"
  file: "Phi-3-mini-4k-instruct-q4_k_m.gguf"
  contextLength: 4096

resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"

keda:
  cooldownPeriod: 300  # 5 min idle before scale to 0
```

## API

### Query Endpoint

```bash
POST http://cortex-activator.cortex-unifi:8080/query
Content-Type: application/json

{
  "query": "Block the client with MAC aa:bb:cc:dd:ee:ff",
  "context": {
    "site": "default"
  }
}
```

### Response

```json
{
  "success": true,
  "result": {
    "action": "block_client",
    "params": {
      "mac": "aa:bb:cc:dd:ee:ff"
    },
    "outcome": {
      "blocked": true,
      "client_name": "Guest iPhone"
    }
  },
  "layers_activated": ["reasoning-slm", "execution-unifi-api"],
  "latency_ms": 2340,
  "cold_starts": ["reasoning-slm"]
}
```

## Learning Loop

Every successful operation is captured and stored:

1. **Query embedding** → Qdrant `operations` collection
2. **Tool selection** → Training data JSONL
3. **Outcome** → Qdrant for future RAG context

Over time, the system:
- Routes faster (embedding similarity vs LLM classification)
- Makes better tool selections (learns from successes)
- Provides relevant context (similar past operations)

## Monitoring

Prometheus metrics exposed on each layer:

```
# Activator
cortex_activator_queries_total{domain="unifi"}
cortex_activator_layer_wakes_total{layer="reasoning-slm"}
cortex_activator_cold_start_seconds{layer="reasoning-slm"}

# Reasoning
cortex_reasoning_inference_seconds{model="phi3"}
cortex_reasoning_tool_selections_total{tool="block_client"}

# Execution
cortex_execution_api_calls_total{endpoint="block_client"}
cortex_execution_api_errors_total{endpoint="block_client"}
cortex_execution_ssh_fallbacks_total
```

Grafana dashboard: `docs/grafana-dashboard.json`

## License

MIT
