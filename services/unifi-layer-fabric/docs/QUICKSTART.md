# Quick Start Guide

Deploy the UniFi Layer Fabric to your k3s cluster in 5 minutes.

## Prerequisites

```bash
# 1. KEDA (if not installed)
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda -n keda --create-namespace

# 2. KEDA HTTP Add-on (for scale-to-zero)
helm install http-add-on kedacore/keda-add-ons-http -n keda
```

## Deploy

### Step 1: Create Namespace & Secrets

```bash
kubectl create namespace cortex-unifi

kubectl create secret generic unifi-credentials \
  --namespace cortex-unifi \
  --from-literal=api-key="YOUR_SITE_MANAGER_API_KEY" \
  --from-literal=controller-host="https://YOUR_UDM_IP" \
  --from-literal=controller-username="admin" \
  --from-literal=controller-password="YOUR_PASSWORD" \
  --from-literal=ssh-host="YOUR_UDM_IP" \
  --from-literal=ssh-username="root" \
  --from-literal=ssh-password="YOUR_SSH_PASSWORD"
```

### Step 2: Deploy with ArgoCD (Recommended)

```bash
kubectl apply -f argocd/applicationset.yaml
```

### Step 2 (Alternative): Deploy with Helm

```bash
# Always-on layers first
helm install cortex-qdrant ./charts/cortex-qdrant -n cortex-unifi
helm install cortex-activator ./charts/cortex-activator -n cortex-unifi

# Serverless layers
helm install reasoning-classifier ./charts/reasoning-classifier -n cortex-unifi
helm install reasoning-slm ./charts/reasoning-slm -n cortex-unifi
helm install execution-unifi-api ./charts/execution-unifi-api -n cortex-unifi
helm install execution-unifi-ssh ./charts/execution-unifi-ssh -n cortex-unifi
helm install cortex-telemetry ./charts/cortex-telemetry -n cortex-unifi
```

## Verify

```bash
# Check deployments (serverless layers should show 0/0 ready)
kubectl get deployments -n cortex-unifi

# Expected output:
# NAME                    READY   UP-TO-DATE   AVAILABLE
# cortex-activator        2/2     2            2
# cortex-qdrant           1/1     1            1
# reasoning-classifier    0/0     0            0        <-- Scaled to zero
# reasoning-slm           0/0     0            0        <-- Scaled to zero
# execution-unifi-api     0/0     0            0        <-- Scaled to zero
# execution-unifi-ssh     0/0     0            0        <-- Scaled to zero
# cortex-telemetry        0/0     0            0        <-- Scaled to zero

# Check KEDA ScaledObjects
kubectl get scaledobjects -n cortex-unifi
```

## Test

```bash
# Port-forward to activator
kubectl port-forward svc/cortex-activator -n cortex-unifi 8080:8080 &

# Send a test query
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "List all clients"}'

# Watch layers wake up
kubectl get pods -n cortex-unifi -w
```

## Memory Usage

| State | Memory | Notes |
|-------|--------|-------|
| **Idle** | ~640MB | Only Activator + Qdrant |
| **Light Query** | ~1.5GB | + API execution layer |
| **Complex Query** | ~4GB | + SLM reasoning layer |
| **Full Warm** | ~4.5GB | All layers active |

## Next Steps

1. **Configure your UDM IP** in the secrets
2. **Adjust cooldown periods** in values.yaml if needed
3. **Set up Prometheus** for KEDA metrics-based scaling
4. **Add Grafana dashboard** for monitoring (see docs/)
