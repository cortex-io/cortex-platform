# Tailscale DNS Configuration

This document covers the Tailscale integration and DNS configuration for external access to Cortex services.

## Architecture Overview

External traffic flows through Tailscale to reach internal services:

```
User Device (Tailscale) → Tailscale Network → k3s-cluster-ingress → Traefik → Service
```

## Tailscale Ingress

The Tailscale ingress runs in the `tailscale` namespace and provides the entry point for all external traffic.

### Current Configuration

| Component | Value |
|-----------|-------|
| Namespace | tailscale |
| Deployment | tailscale-ingress |
| Tailscale IP | 100.81.79.19 |
| Machine Name | k3s-cluster-ingress |

### Check Tailscale Status

```bash
# From the ingress pod
kubectl exec -n tailscale deploy/tailscale-ingress -c tailscale -- tailscale status

# Get Tailscale IP
kubectl exec -n tailscale deploy/tailscale-ingress -c tailscale -- tailscale ip
```

## DNS Configuration (Cloudflare)

All `*.ry-ops.dev` domains should point to the Tailscale ingress IP.

### Required DNS Records

| Type | Name | Value | Notes |
|------|------|-------|-------|
| A | * | 100.81.79.19 | Wildcard - covers all subdomains |
| A | chat | 100.81.79.19 | Optional explicit record |

### Important: Do NOT Create Internal IP Records

Do not create DNS records pointing to internal cluster IPs (e.g., `10.88.145.200`). These override the wildcard and break external access.

**Bad Example (don't do this):**
```
A    sandfly-mcp    10.88.145.200    ❌ WRONG
```

**Good Example:**
```
A    *              100.81.79.19     ✅ CORRECT
```

## Troubleshooting

### Services Unreachable Externally

1. **Verify DNS resolution:**
   ```bash
   dig +short sandfly.ry-ops.dev @1.1.1.1
   # Should return: 100.81.79.19
   ```

2. **Check Tailscale connectivity:**
   ```bash
   ping 100.81.79.19
   ```

3. **Test with curl:**
   ```bash
   curl -sk https://sandfly.ry-ops.dev/health
   ```

### Stale Tailscale Nodes

If DNS points to an old/removed Tailscale node:

1. Check current Tailscale nodes:
   ```bash
   kubectl exec -n tailscale deploy/tailscale-ingress -c tailscale -- tailscale status
   ```

2. Remove stale nodes from Tailscale admin console

3. Update DNS to point to the active node's IP

### SSL Certificate Warnings

Self-signed certificate warnings are expected if not using Let's Encrypt. Services work but browsers will warn.

For proper TLS, ensure cert-manager is configured with the correct cluster-issuer.

## Service Routing

Traefik handles routing based on Host headers:

| Host | Backend Service | Namespace |
|------|-----------------|-----------|
| chat.ry-ops.dev | cortex-chat | cortex-chat |
| sandfly.ry-ops.dev | sandfly-web | cortex-system |
| grafana.ry-ops.dev | kube-prometheus-stack-grafana | monitoring |
| *-mcp.ry-ops.dev | Various MCP servers | cortex-system |

### Check Ingress Configuration

```bash
# List all ingresses
kubectl get ingress -A

# Check specific ingress
kubectl describe ingress -n cortex-system sandfly-ingress
```

## Related Documentation

- [K3s Cluster Configuration](./k3s-cluster-configuration.md)
- [Layer Activator Guide](./layer-activator-guide.md)
