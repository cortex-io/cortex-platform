# Kubernetes MCP Server

Model Context Protocol (MCP) server for Kubernetes cluster management integration with Cortex.

## Overview

This MCP server exposes Kubernetes API capabilities through the Model Context Protocol, allowing AI agents to:

- Query cluster information and status
- List and inspect resources (pods, deployments, services, nodes)
- View pod logs for debugging
- Monitor pod health and identify problems
- Access namespace information

## Configuration

Configure via environment variables:

```bash
K8S_IN_CLUSTER=true              # Use in-cluster config (default: true)
KUBECONFIG=/path/to/kubeconfig   # Path to kubeconfig (if not in-cluster)
```

## Available Tools

### Cluster Management

- **k8s_get_cluster_info** - Get Kubernetes cluster version and platform information

- **k8s_list_namespaces** - List all namespaces in the cluster

### Pod Management

- **k8s_list_pods** - List pods across namespaces
  - Optional namespace filter
  - Optional label selector
  - Shows pod status

- **k8s_get_pod** - Get detailed pod information
  - Pod status and phase
  - Container states
  - Node placement
  - IP addressing

- **k8s_get_pod_logs** - Retrieve pod logs
  - Configurable tail lines
  - Multi-container support
  - Real-time log access

- **k8s_get_pod_problems** - Identify problematic pods
  - Finds non-running pods
  - Detects container issues
  - Returns empty if all healthy

### Deployment Management

- **k8s_list_deployments** - List deployments
  - Shows replica counts
  - Ready vs desired state
  - Namespace filtering

- **k8s_get_deployment** - Get deployment details
  - Replica status
  - Update strategy
  - Condition information

### Service Management

- **k8s_list_services** - List Kubernetes services
  - Service types
  - ClusterIP information
  - Namespace filtering

### Node Management

- **k8s_list_nodes** - List cluster nodes
  - Node ready status
  - Kubelet version
  - Node count

- **k8s_get_node** - Get node details
  - System information
  - Resource capacity
  - Node conditions

## Installation

```bash
cd /Users/ryandahlberg/Projects/cortex-platform/services/mcp-servers/kubernetes
pip install -e .
```

## Usage

### Standalone Mode

```bash
kubernetes-mcp
```

### As MCP Server

Configure in your MCP client:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "kubernetes-mcp",
      "env": {
        "K8S_IN_CLUSTER": "true"
      }
    }
  }
}
```

## Kubernetes Access

### In-Cluster Mode (Default)

When running inside a Kubernetes cluster, the server automatically uses the in-cluster service account:

- Reads credentials from `/var/run/secrets/kubernetes.io/serviceaccount/`
- Uses the pod's service account token
- Respects RBAC permissions

### Out-of-Cluster Mode

For local development or external access:

```bash
export K8S_IN_CLUSTER=false
export KUBECONFIG=~/.kube/config
kubernetes-mcp
```

## RBAC Configuration

The server requires appropriate RBAC permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: kubernetes-mcp
  namespace: cortex-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kubernetes-mcp-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "namespaces", "nodes", "pods/log"]
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: kubernetes-mcp-reader-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: kubernetes-mcp-reader
subjects:
  - kind: ServiceAccount
    name: kubernetes-mcp
    namespace: cortex-system
```

## Architecture

```
┌─────────────────────┐
│   Cortex Agents     │
│                     │
│  (MCP Clients)      │
└──────────┬──────────┘
           │
           │ MCP Protocol
           │
┌──────────▼──────────┐
│  K8s MCP Server     │
│                     │
│  - Tool handlers    │
│  - Error handling   │
│  - K8s client       │
└──────────┬──────────┘
           │
           │ Kubernetes API
           │
┌──────────▼──────────┐
│  Kubernetes API     │
│                     │
│  k3s Cluster        │
│  7 nodes            │
└─────────────────────┘
```

## Deployment

This server is deployed as a Kubernetes pod in the cortex-system namespace:

```bash
# Check deployment status
kubectl get pods -n cortex-system -l app=kubernetes-mcp

# View logs
kubectl logs -n cortex-system -l app=kubernetes-mcp

# Check service
kubectl get svc -n cortex-system kubernetes-mcp
```

## Development

### Local Testing

```bash
# Set environment variables
export K8S_IN_CLUSTER=false
export KUBECONFIG=~/.kube/config

# Run server
python -m mcp_kubernetes.server
```

### Adding New Tools

1. Add tool definition in `list_tools()`
2. Implement handler in `call_tool()`
3. Add error handling with `@handle_errors`
4. Update RBAC permissions if needed
5. Update this README

## Security Considerations

- **Read-Only Access**: This server provides read-only access to the cluster
- **RBAC Enforcement**: All operations respect Kubernetes RBAC policies
- **No Mutations**: No create/update/delete operations are exposed
- **Service Account**: Uses dedicated service account with minimal permissions
- **Audit Logging**: All API calls are logged via Kubernetes audit logs

## Troubleshooting

### Permission Denied Errors

Check RBAC permissions:
```bash
kubectl auth can-i list pods --as=system:serviceaccount:cortex-system:kubernetes-mcp
```

### Connection Errors

Verify service account token:
```bash
kubectl get serviceaccount kubernetes-mcp -n cortex-system
kubectl describe secret $(kubectl get serviceaccount kubernetes-mcp -n cortex-system -o jsonpath='{.secrets[0].name}')
```

### Log Access Issues

Some operations require additional RBAC permissions:
```bash
kubectl auth can-i get pods/log --as=system:serviceaccount:cortex-system:kubernetes-mcp
```

## Related Documentation

- [Kubernetes Python Client](https://github.com/kubernetes-client/python)
- [MCP Specification](https://github.com/anthropics/mcp)
- [Cortex Platform Documentation](../../README.md)
- [K3s Documentation](https://docs.k3s.io/)
