# Monitoring Exporters

This document covers the Prometheus exporters that feed data into Grafana for infrastructure monitoring.

## Exporter Overview

| Exporter | Namespace | Purpose | Port |
|----------|-----------|---------|------|
| unifi-exporter | monitoring-exporters | UniFi network metrics | 9130 |
| sandfly-exporter | monitoring | Sandfly security metrics | 9131 |
| proxmox-exporter | monitoring-exporters | Proxmox VM metrics | 9221 |
| proxmox-exporter | monitoring | Proxmox VM metrics (duplicate) | 9221 |
| github-exporter | monitoring-exporters | GitHub repo metrics | 9171 |
| redis-exporter | monitoring-exporters | Redis metrics | 9121 |
| cloudflare-exporter | monitoring-exporters | Cloudflare metrics | 9199 |
| claude-api-exporter | monitoring | Claude API usage metrics | 9131 |
| otel-collector | monitoring | OpenTelemetry collector | 4317/4318 |
| unpoller | monitoring | Additional UniFi metrics | 9130 |

## Managing Exporters

### Check Exporter Status

```bash
# Monitoring namespace
kubectl get deploy -n monitoring | grep -v kube-prometheus

# Monitoring-exporters namespace
kubectl get deploy -n monitoring-exporters
```

### Scale Up Exporters

```bash
# Scale up specific exporter
kubectl scale deploy -n monitoring-exporters unifi-exporter --replicas=1
kubectl scale deploy -n monitoring sandfly-exporter --replicas=1

# Scale up all exporters in monitoring-exporters
kubectl scale deploy -n monitoring-exporters --all --replicas=1
```

### Scale Down Exporters (to free resources)

```bash
kubectl scale deploy -n monitoring-exporters cloudflare-exporter --replicas=0
kubectl scale deploy -n monitoring otel-collector --replicas=0
```

## Exporter Configuration

### UniFi Exporter (unifi-poller)

**Location:** `monitoring-exporters/unifi-exporter`

**Environment Variables:**
- `UP_UNIFI_DEFAULT_URL`: UniFi controller URL (e.g., `https://10.88.140.1:8443`)
- `UP_UNIFI_DEFAULT_USER`: Controller username (from secret)
- `UP_UNIFI_DEFAULT_PASS`: Controller password (from secret)
- `UP_UNIFI_DEFAULT_VERIFY_SSL`: Set to `false` for self-signed certs

**Secret:**
```bash
kubectl get secret -n monitoring-exporters unifi-exporter-credentials -o yaml
```

### Sandfly Exporter

**Location:** `monitoring/sandfly-exporter`

**Configuration:** Custom Python exporter that queries Sandfly API

### Proxmox Exporter

**Location:** `monitoring-exporters/proxmox-exporter`

**Environment Variables:**
- `PROXMOX_HOST`: Proxmox server hostname
- `PROXMOX_USER`: API user
- `PROXMOX_TOKEN_NAME`: API token name
- `PROXMOX_TOKEN_VALUE`: API token (from secret)

## ServiceMonitors

Each exporter has a corresponding ServiceMonitor that tells Prometheus how to scrape it:

```bash
# List all ServiceMonitors
kubectl get servicemonitor -A

# Check specific ServiceMonitor
kubectl describe servicemonitor -n monitoring-exporters unifi-exporter
```

## Troubleshooting

### Exporter Not Showing Data in Grafana

1. **Check exporter is running:**
   ```bash
   kubectl get pods -n monitoring-exporters -l app=unifi-exporter
   ```

2. **Check exporter logs:**
   ```bash
   kubectl logs -n monitoring-exporters deploy/unifi-exporter
   ```

3. **Verify metrics endpoint:**
   ```bash
   kubectl port-forward -n monitoring-exporters svc/unifi-exporter 9130:9130 &
   curl http://localhost:9130/metrics | head -20
   ```

4. **Check ServiceMonitor exists:**
   ```bash
   kubectl get servicemonitor -n monitoring-exporters unifi-exporter
   ```

5. **Verify Prometheus is scraping:**
   - Open Prometheus UI (grafana.ry-ops.dev → Explore → Prometheus)
   - Query: `up{job="unifi-exporter"}`

### Exporter Pending Due to Insufficient Memory

1. **Check node resources:**
   ```bash
   kubectl describe nodes | grep -A5 "Allocated resources:"
   ```

2. **Scale down idle stacks via Layer Activator:**
   ```bash
   kubectl run -it --rm curl-cmd --image=curlimages/curl --restart=Never -- \
     curl -s -X POST http://layer-activator.cortex-system.svc.cluster.local:8080/scale-down/dev-stack
   ```

3. **Reduce exporter memory requests:**
   ```bash
   kubectl patch deploy -n monitoring otel-collector --type='json' \
     -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"}]'
   ```

### Exporter Failing with Authentication Error

1. **Check secrets exist:**
   ```bash
   kubectl get secrets -n monitoring-exporters
   ```

2. **Verify secret values:**
   ```bash
   kubectl get secret -n monitoring-exporters unifi-exporter-credentials -o jsonpath='{.data.UNIFI_USERNAME}' | base64 -d
   ```

3. **Update credentials:**
   ```bash
   kubectl create secret generic unifi-exporter-credentials \
     -n monitoring-exporters \
     --from-literal=UNIFI_USERNAME=<user> \
     --from-literal=UNIFI_PASSWORD=<pass> \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

### Exporter PVC Issues

Some exporters (like cortex-agent-exporter) require PVCs:

1. **Check PVC status:**
   ```bash
   kubectl get pvc -n monitoring
   ```

2. **Fix access mode issues:**
   ```bash
   # Delete broken PVC
   kubectl delete pvc -n monitoring cortex-data-pvc

   # Recreate with correct access mode
   cat <<EOF | kubectl apply -f -
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: cortex-data-pvc
     namespace: monitoring
   spec:
     accessModes:
       - ReadWriteOnce  # NOT ReadWriteMany for local-path
     storageClassName: local-path
     resources:
       requests:
         storage: 1Gi
   EOF
   ```

## Adding New Exporters

1. Create deployment with appropriate image
2. Create service exposing metrics port
3. Create ServiceMonitor:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-exporter
  namespace: monitoring-exporters
  labels:
    release: kube-prometheus-stack
spec:
  endpoints:
    - interval: 30s
      port: metrics
  selector:
    matchLabels:
      app: my-exporter
```

## Related Documentation

- [K3s Cluster Configuration](./k3s-cluster-configuration.md)
- [Layer Activator Guide](./layer-activator-guide.md)
