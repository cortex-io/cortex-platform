# Kubernetes API Integration for Cortex Resource-Manager

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Status**: Production-Ready

---

## Overview

The cortex resource-manager provides comprehensive integration with Kubernetes clusters running on Talos Linux. This document outlines connection patterns, service discovery, health monitoring, namespace management, RBAC configuration, and event handling strategies for production deployments.

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Cortex Resource-Manager                      │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │   K8s API    │  │   Service    │  │  Health Monitoring   │ │
│  │   Client     │  │  Discovery   │  │  (Probes & Metrics)  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │
│         │                 │                     │              │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │                 │                     │
          v                 v                     v
┌─────────────────────────────────────────────────────────────────┐
│                    Talos Kubernetes Cluster                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Control Plane (3+ nodes)                   │  │
│  │  ┌────────────┐  ┌──────────┐  ┌──────────────────────┐ │  │
│  │  │ API Server │  │   etcd   │  │ Controller Manager   │ │  │
│  │  └────────────┘  └──────────┘  └──────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Worker Nodes (3+ nodes)                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │  │
│  │  │  MCP Server  │  │  MCP Server  │  │  Application  │  │  │
│  │  │   (Pod 1)    │  │   (Pod 2)    │  │  Workloads    │  │  │
│  │  └──────────────┘  └──────────────┘  └───────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        Cluster Services                                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │ kube-state  │  │   CoreDNS   │  │  Metrics Server │  │  │
│  │  │  -metrics   │  │             │  │                 │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Connection to Talos Cluster via kubeconfig

### 1.1 Kubeconfig Acquisition

The resource-manager connects to Talos Kubernetes clusters using kubeconfig files obtained through the talos-mcp-server integration.

#### Obtaining Kubeconfig from Talos

**Via talos-mcp-server**:
```bash
# Using talos-mcp-server tool
talos_kubeconfig --nodes <control-plane-ip>

# Output: kubeconfig written to ~/.kube/config or returned as string
```

**Via talosctl directly**:
```bash
# Generate kubeconfig
talosctl kubeconfig --nodes <control-plane-ip> \
  --force \
  --merge=false \
  > /Users/ryandahlberg/Projects/cortex/coordination/resource-manager/kubeconfig-prod.yaml

# Merge into existing config
talosctl kubeconfig --nodes <control-plane-ip> --merge
```

### 1.2 Kubeconfig Storage and Management

**Directory Structure**:
```
/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/
├── kubeconfig/
│   ├── prod-cluster.yaml          # Production cluster
│   ├── staging-cluster.yaml       # Staging cluster
│   ├── dev-cluster.yaml           # Development cluster
│   └── edge-cluster-01.yaml       # Edge cluster 1
├── k8s-integration.json           # Connection config schema
└── k8s-integration.md             # This document
```

**Kubeconfig Security**:
- Store kubeconfigs with restricted permissions: `chmod 600`
- Use separate service accounts per cluster/environment
- Rotate credentials regularly (quarterly minimum)
- Never commit kubeconfigs to version control
- Use vault or secrets manager in production

### 1.3 Client Configuration

**Python Client (kubernetes library)**:
```python
from kubernetes import client, config
import os

class K8sResourceManager:
    def __init__(self, cluster_name: str):
        self.cluster_name = cluster_name
        self.kubeconfig_path = self._get_kubeconfig_path(cluster_name)
        self.api_client = self._initialize_client()

    def _get_kubeconfig_path(self, cluster_name: str) -> str:
        base_path = "/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/kubeconfig"
        kubeconfig_map = {
            "prod": f"{base_path}/prod-cluster.yaml",
            "staging": f"{base_path}/staging-cluster.yaml",
            "dev": f"{base_path}/dev-cluster.yaml"
        }
        return kubeconfig_map.get(cluster_name, f"{base_path}/{cluster_name}-cluster.yaml")

    def _initialize_client(self):
        """Initialize Kubernetes API client with kubeconfig"""
        config.load_kube_config(config_file=self.kubeconfig_path)
        return client.ApiClient()

    def get_core_v1_api(self):
        return client.CoreV1Api(self.api_client)

    def get_apps_v1_api(self):
        return client.AppsV1Api(self.api_client)

    def get_batch_v1_api(self):
        return client.BatchV1Api(self.api_client)

# Usage
rm = K8sResourceManager("prod")
v1 = rm.get_core_v1_api()
nodes = v1.list_node()
```

**Node.js Client (@kubernetes/client-node)**:
```javascript
const k8s = require('@kubernetes/client-node');

class K8sResourceManager {
  constructor(clusterName) {
    this.clusterName = clusterName;
    this.kc = new k8s.KubeConfig();
    this.kubeconfigPath = this.getKubeconfigPath(clusterName);
    this.kc.loadFromFile(this.kubeconfigPath);
  }

  getKubeconfigPath(clusterName) {
    const basePath = '/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/kubeconfig';
    const configMap = {
      'prod': `${basePath}/prod-cluster.yaml`,
      'staging': `${basePath}/staging-cluster.yaml`,
      'dev': `${basePath}/dev-cluster.yaml`
    };
    return configMap[clusterName] || `${basePath}/${clusterName}-cluster.yaml`;
  }

  getCoreV1Api() {
    return this.kc.makeApiClient(k8s.CoreV1Api);
  }

  getAppsV1Api() {
    return this.kc.makeApiClient(k8s.AppsV1Api);
  }

  async listNodes() {
    const k8sApi = this.getCoreV1Api();
    const res = await k8sApi.listNode();
    return res.body.items;
  }
}

// Usage
const rm = new K8sResourceManager('prod');
const nodes = await rm.listNodes();
```

### 1.4 Connection Testing and Validation

**Health Check Script**:
```bash
#!/bin/bash
# /Users/ryandahlberg/Projects/cortex/coordination/resource-manager/scripts/test-k8s-connection.sh

KUBECONFIG_PATH=$1

if [ -z "$KUBECONFIG_PATH" ]; then
  echo "Usage: $0 <kubeconfig-path>"
  exit 1
fi

export KUBECONFIG="$KUBECONFIG_PATH"

echo "Testing Kubernetes API connection..."
echo "-----------------------------------"

# Test 1: Cluster info
echo "1. Cluster Info:"
kubectl cluster-info

# Test 2: API server version
echo -e "\n2. API Server Version:"
kubectl version --short

# Test 3: Node status
echo -e "\n3. Node Status:"
kubectl get nodes -o wide

# Test 4: Namespace list
echo -e "\n4. Namespaces:"
kubectl get namespaces

# Test 5: API resources
echo -e "\n5. API Resources Available:"
kubectl api-resources --verbs=list -o name | head -10

# Test 6: Context verification
echo -e "\n6. Current Context:"
kubectl config current-context

echo -e "\n-----------------------------------"
echo "Connection test complete!"
```

**Automated Validation**:
```python
def validate_cluster_connection(cluster_name: str) -> dict:
    """Validate Kubernetes cluster connectivity"""
    rm = K8sResourceManager(cluster_name)
    v1 = rm.get_core_v1_api()

    validation_results = {
        "cluster": cluster_name,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check 1: API server reachable
    try:
        version = v1.get_api_resources()
        validation_results["checks"]["api_server"] = {
            "status": "healthy",
            "response_time_ms": 0  # measure this
        }
    except Exception as e:
        validation_results["checks"]["api_server"] = {
            "status": "failed",
            "error": str(e)
        }

    # Check 2: Nodes are ready
    try:
        nodes = v1.list_node()
        ready_nodes = sum(1 for node in nodes.items
                         if any(c.type == "Ready" and c.status == "True"
                               for c in node.status.conditions))
        validation_results["checks"]["nodes"] = {
            "status": "healthy",
            "total_nodes": len(nodes.items),
            "ready_nodes": ready_nodes
        }
    except Exception as e:
        validation_results["checks"]["nodes"] = {
            "status": "failed",
            "error": str(e)
        }

    # Check 3: Core DNS operational
    try:
        pods = v1.list_namespaced_pod("kube-system", label_selector="k8s-app=kube-dns")
        running_dns_pods = sum(1 for pod in pods.items if pod.status.phase == "Running")
        validation_results["checks"]["coredns"] = {
            "status": "healthy",
            "running_pods": running_dns_pods
        }
    except Exception as e:
        validation_results["checks"]["coredns"] = {
            "status": "failed",
            "error": str(e)
        }

    return validation_results
```

---

## 2. Service Discovery for MCP Servers Running in K8s

### 2.1 Service Discovery Strategy

MCP servers running as Kubernetes pods require dynamic discovery mechanisms. The resource-manager uses label selectors and annotations to identify MCP server instances.

#### MCP Server Pod Labels

**Standard Labels**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: talos-mcp-server-7d9f8c
  namespace: cortex-mcp
  labels:
    app: mcp-server
    mcp.cortex.dev/type: talos           # MCP server type
    mcp.cortex.dev/version: "1.0.0"      # Server version
    mcp.cortex.dev/protocol: stdio       # Communication protocol
    cortex.dev/component: mcp-server     # Cortex component
  annotations:
    mcp.cortex.dev/capabilities: "kubernetes,talos,cluster-management"
    mcp.cortex.dev/endpoint: "http://talos-mcp-server:8080"
```

### 2.2 Discovery Implementation

**Python Service Discovery**:
```python
class MCPServerDiscovery:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()

    def discover_mcp_servers(self, namespace: str = "cortex-mcp") -> list:
        """Discover all MCP servers in cluster"""
        label_selector = "app=mcp-server"

        try:
            pods = self.v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )

            mcp_servers = []
            for pod in pods.items:
                if pod.status.phase == "Running":
                    server_info = self._extract_server_info(pod)
                    mcp_servers.append(server_info)

            return mcp_servers
        except Exception as e:
            print(f"Error discovering MCP servers: {e}")
            return []

    def _extract_server_info(self, pod) -> dict:
        """Extract MCP server information from pod"""
        labels = pod.metadata.labels or {}
        annotations = pod.metadata.annotations or {}

        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "type": labels.get("mcp.cortex.dev/type", "unknown"),
            "version": labels.get("mcp.cortex.dev/version", "unknown"),
            "protocol": labels.get("mcp.cortex.dev/protocol", "stdio"),
            "capabilities": annotations.get("mcp.cortex.dev/capabilities", "").split(","),
            "endpoint": annotations.get("mcp.cortex.dev/endpoint", ""),
            "pod_ip": pod.status.pod_ip,
            "node_name": pod.spec.node_name,
            "status": pod.status.phase,
            "ready": self._is_pod_ready(pod)
        }

    def _is_pod_ready(self, pod) -> bool:
        """Check if pod is ready"""
        if not pod.status.conditions:
            return False
        for condition in pod.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False

    def find_mcp_server_by_type(self, server_type: str, namespace: str = "cortex-mcp") -> dict:
        """Find specific MCP server by type"""
        servers = self.discover_mcp_servers(namespace)
        for server in servers:
            if server["type"] == server_type and server["ready"]:
                return server
        return None

    def get_service_endpoint(self, server_type: str, namespace: str = "cortex-mcp") -> str:
        """Get service endpoint for MCP server"""
        try:
            service_name = f"{server_type}-mcp-server"
            service = self.v1.read_namespaced_service(service_name, namespace)

            # Get cluster IP and port
            cluster_ip = service.spec.cluster_ip
            port = service.spec.ports[0].port if service.spec.ports else None

            if cluster_ip and port:
                return f"http://{cluster_ip}:{port}"

            return None
        except Exception as e:
            print(f"Error getting service endpoint: {e}")
            return None
```

### 2.3 Service Discovery via Kubernetes DNS

**DNS-Based Discovery**:
```python
def resolve_mcp_server_dns(server_type: str, namespace: str = "cortex-mcp") -> str:
    """
    Resolve MCP server using Kubernetes DNS

    DNS pattern: <service-name>.<namespace>.svc.cluster.local
    """
    service_name = f"{server_type}-mcp-server"
    dns_name = f"{service_name}.{namespace}.svc.cluster.local"

    # DNS lookup
    import socket
    try:
        ip = socket.gethostbyname(dns_name)
        return f"http://{dns_name}:8080"  # Assuming standard port
    except socket.gaierror:
        return None
```

### 2.4 MCP Server Registry

**Maintain Active Registry**:
```python
class MCPServerRegistry:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.discovery = MCPServerDiscovery(k8s_manager)
        self.registry = {}
        self.last_update = None

    def refresh_registry(self, namespace: str = "cortex-mcp"):
        """Refresh MCP server registry from cluster"""
        servers = self.discovery.discover_mcp_servers(namespace)

        self.registry = {
            server["type"]: {
                "server_info": server,
                "discovered_at": datetime.utcnow().isoformat(),
                "health_status": "healthy" if server["ready"] else "degraded"
            }
            for server in servers
        }

        self.last_update = datetime.utcnow()

        # Save to file
        self._save_registry()

    def _save_registry(self):
        """Save registry to disk"""
        registry_path = "/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/mcp-server-registry.json"
        with open(registry_path, 'w') as f:
            json.dump({
                "last_update": self.last_update.isoformat(),
                "servers": self.registry
            }, f, indent=2)

    def get_server(self, server_type: str) -> dict:
        """Get server from registry"""
        if server_type not in self.registry:
            self.refresh_registry()

        return self.registry.get(server_type)
```

---

## 3. Health Monitoring Patterns (Liveness, Readiness Probes)

### 3.1 Probe Types and Purposes

**Liveness Probe**:
- Purpose: Detect when a container is stuck or deadlocked
- Action: Restart container if probe fails
- Use case: MCP server process health

**Readiness Probe**:
- Purpose: Determine when a container is ready to accept traffic
- Action: Remove from service endpoints if probe fails
- Use case: MCP server initialization, dependency checks

**Startup Probe**:
- Purpose: Allow slow-starting containers more time to initialize
- Action: Other probes disabled until startup succeeds
- Use case: MCP servers with long initialization

### 3.2 MCP Server Health Probe Configuration

**Example Deployment with Probes**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: talos-mcp-server
  namespace: cortex-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-server
      mcp.cortex.dev/type: talos
  template:
    metadata:
      labels:
        app: mcp-server
        mcp.cortex.dev/type: talos
    spec:
      containers:
      - name: talos-mcp-server
        image: ghcr.io/ry-ops/talos-mcp-server:latest
        ports:
        - containerPort: 8080
          name: http

        # Liveness Probe - Is the process healthy?
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          successThreshold: 1

        # Readiness Probe - Can it accept traffic?
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
          successThreshold: 1

        # Startup Probe - Allow time for initialization
        startupProbe:
          httpGet:
            path: /startup
            port: 8080
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30  # Allow 150 seconds for startup
          successThreshold: 1

        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi

        env:
        - name: TALOS_CONFIG
          valueFrom:
            secretKeyRef:
              name: talos-config
              key: talosconfig
```

### 3.3 Health Check Monitoring

**Python Health Monitor**:
```python
class HealthMonitor:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()

    def check_pod_health(self, pod_name: str, namespace: str) -> dict:
        """Check pod health status including probes"""
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)

            health_status = {
                "pod_name": pod_name,
                "namespace": namespace,
                "phase": pod.status.phase,
                "conditions": [],
                "container_statuses": []
            }

            # Extract conditions
            if pod.status.conditions:
                for condition in pod.status.conditions:
                    health_status["conditions"].append({
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message
                    })

            # Extract container statuses
            if pod.status.container_statuses:
                for container_status in pod.status.container_statuses:
                    health_status["container_statuses"].append({
                        "name": container_status.name,
                        "ready": container_status.ready,
                        "restart_count": container_status.restart_count,
                        "state": self._get_container_state(container_status.state)
                    })

            return health_status
        except Exception as e:
            return {"error": str(e)}

    def _get_container_state(self, state) -> dict:
        """Extract container state information"""
        if state.running:
            return {"status": "running", "started_at": state.running.started_at}
        elif state.waiting:
            return {"status": "waiting", "reason": state.waiting.reason}
        elif state.terminated:
            return {
                "status": "terminated",
                "exit_code": state.terminated.exit_code,
                "reason": state.terminated.reason
            }
        return {"status": "unknown"}

    def monitor_mcp_servers(self, namespace: str = "cortex-mcp") -> dict:
        """Monitor all MCP servers health"""
        label_selector = "app=mcp-server"

        try:
            pods = self.v1.list_namespaced_pod(namespace, label_selector=label_selector)

            monitoring_report = {
                "timestamp": datetime.utcnow().isoformat(),
                "namespace": namespace,
                "total_pods": len(pods.items),
                "healthy_pods": 0,
                "unhealthy_pods": 0,
                "pod_details": []
            }

            for pod in pods.items:
                health = self.check_pod_health(pod.metadata.name, namespace)
                is_healthy = health.get("phase") == "Running" and all(
                    cs.get("ready") for cs in health.get("container_statuses", [])
                )

                if is_healthy:
                    monitoring_report["healthy_pods"] += 1
                else:
                    monitoring_report["unhealthy_pods"] += 1

                monitoring_report["pod_details"].append(health)

            return monitoring_report
        except Exception as e:
            return {"error": str(e)}
```

### 3.4 Automated Health Checks

**Periodic Health Check Script**:
```bash
#!/bin/bash
# /Users/ryandahlberg/Projects/cortex/coordination/resource-manager/scripts/health-check.sh

NAMESPACE="cortex-mcp"
LABEL_SELECTOR="app=mcp-server"

echo "MCP Server Health Check - $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=================================================="

# Get all MCP server pods
kubectl get pods -n $NAMESPACE -l $LABEL_SELECTOR -o json | \
  jq -r '.items[] |
    "Pod: \(.metadata.name)\n" +
    "  Status: \(.status.phase)\n" +
    "  Ready: \([.status.conditions[] | select(.type=="Ready")] | .[0].status)\n" +
    "  Restarts: \(.status.containerStatuses[0].restartCount)\n" +
    "  Age: \(.metadata.creationTimestamp)\n"'

# Check probe status
echo -e "\nProbe Status:"
kubectl get pods -n $NAMESPACE -l $LABEL_SELECTOR -o json | \
  jq -r '.items[] |
    "\(.metadata.name):" +
    "\n  Liveness: \(.status.containerStatuses[0].state | keys[0])" +
    "\n  Readiness: \(.status.containerStatuses[0].ready)"'

# Check recent events
echo -e "\nRecent Events:"
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10
```

---

## 4. Namespace Management Strategy

### 4.1 Namespace Organization

**Recommended Namespace Structure**:
```
cortex-system          # Core Cortex infrastructure
cortex-mcp             # MCP servers
cortex-monitoring      # Monitoring and observability
cortex-workers         # Worker pods and jobs
cortex-config          # ConfigMaps and Secrets
cortex-data            # Data processing workloads
default                # Avoid using for Cortex
kube-system            # Kubernetes system components
```

### 4.2 Namespace Creation and Management

**Namespace Definition with Resource Quotas**:
```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: cortex-mcp
  labels:
    cortex.dev/component: mcp-servers
    environment: production
  annotations:
    cortex.dev/description: "MCP server deployments"
    cortex.dev/owner: "resource-manager"

---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: cortex-mcp-quota
  namespace: cortex-mcp
spec:
  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    persistentvolumeclaims: "10"
    pods: "50"

---
apiVersion: v1
kind: LimitRange
metadata:
  name: cortex-mcp-limits
  namespace: cortex-mcp
spec:
  limits:
  - max:
      cpu: "2"
      memory: 4Gi
    min:
      cpu: 50m
      memory: 64Mi
    default:
      cpu: 200m
      memory: 256Mi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    type: Container
```

### 4.3 Namespace Management Operations

**Python Namespace Manager**:
```python
class NamespaceManager:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()

    def create_namespace(self, namespace_name: str, labels: dict = None, annotations: dict = None):
        """Create namespace with labels and annotations"""
        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels=labels or {},
                annotations=annotations or {}
            )
        )

        try:
            self.v1.create_namespace(namespace)
            print(f"Namespace '{namespace_name}' created successfully")

            # Apply resource quota
            self._create_resource_quota(namespace_name)

            # Apply limit range
            self._create_limit_range(namespace_name)

        except Exception as e:
            print(f"Error creating namespace: {e}")

    def _create_resource_quota(self, namespace: str):
        """Create resource quota for namespace"""
        quota = client.V1ResourceQuota(
            metadata=client.V1ObjectMeta(name=f"{namespace}-quota"),
            spec=client.V1ResourceQuotaSpec(
                hard={
                    "requests.cpu": "10",
                    "requests.memory": "20Gi",
                    "limits.cpu": "20",
                    "limits.memory": "40Gi",
                    "pods": "50"
                }
            )
        )

        try:
            self.v1.create_namespaced_resource_quota(namespace, quota)
        except Exception as e:
            print(f"Error creating resource quota: {e}")

    def _create_limit_range(self, namespace: str):
        """Create limit range for namespace"""
        limit_range = client.V1LimitRange(
            metadata=client.V1ObjectMeta(name=f"{namespace}-limits"),
            spec=client.V1LimitRangeSpec(
                limits=[
                    client.V1LimitRangeItem(
                        max={"cpu": "2", "memory": "4Gi"},
                        min={"cpu": "50m", "memory": "64Mi"},
                        default={"cpu": "200m", "memory": "256Mi"},
                        default_request={"cpu": "100m", "memory": "128Mi"},
                        type="Container"
                    )
                ]
            )
        )

        try:
            self.v1.create_namespaced_limit_range(namespace, limit_range)
        except Exception as e:
            print(f"Error creating limit range: {e}")

    def list_cortex_namespaces(self) -> list:
        """List all Cortex-managed namespaces"""
        try:
            namespaces = self.v1.list_namespace(label_selector="cortex.dev/component")
            return [ns.metadata.name for ns in namespaces.items]
        except Exception as e:
            print(f"Error listing namespaces: {e}")
            return []

    def get_namespace_resource_usage(self, namespace: str) -> dict:
        """Get resource usage for namespace"""
        try:
            # Get all pods in namespace
            pods = self.v1.list_namespaced_pod(namespace)

            total_cpu_requests = 0
            total_memory_requests = 0
            total_cpu_limits = 0
            total_memory_limits = 0

            for pod in pods.items:
                for container in pod.spec.containers:
                    if container.resources.requests:
                        cpu_req = container.resources.requests.get("cpu", "0")
                        mem_req = container.resources.requests.get("memory", "0")
                        total_cpu_requests += self._parse_cpu(cpu_req)
                        total_memory_requests += self._parse_memory(mem_req)

                    if container.resources.limits:
                        cpu_lim = container.resources.limits.get("cpu", "0")
                        mem_lim = container.resources.limits.get("memory", "0")
                        total_cpu_limits += self._parse_cpu(cpu_lim)
                        total_memory_limits += self._parse_memory(mem_lim)

            return {
                "namespace": namespace,
                "pod_count": len(pods.items),
                "cpu_requests_cores": total_cpu_requests,
                "memory_requests_gb": total_memory_requests / (1024**3),
                "cpu_limits_cores": total_cpu_limits,
                "memory_limits_gb": total_memory_limits / (1024**3)
            }
        except Exception as e:
            return {"error": str(e)}

    def _parse_cpu(self, cpu_string: str) -> float:
        """Parse CPU string to cores (e.g., '500m' -> 0.5)"""
        if cpu_string.endswith('m'):
            return float(cpu_string[:-1]) / 1000
        return float(cpu_string)

    def _parse_memory(self, memory_string: str) -> int:
        """Parse memory string to bytes"""
        units = {'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4}
        for unit, multiplier in units.items():
            if memory_string.endswith(unit):
                return int(memory_string[:-2]) * multiplier
        return int(memory_string)
```

---

## 5. RBAC Configuration for Resource-Manager

### 5.1 Service Account Creation

**Resource-Manager Service Account**:
```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cortex-resource-manager
  namespace: cortex-system
  labels:
    cortex.dev/component: resource-manager

---
apiVersion: v1
kind: Secret
metadata:
  name: cortex-resource-manager-token
  namespace: cortex-system
  annotations:
    kubernetes.io/service-account.name: cortex-resource-manager
type: kubernetes.io/service-account-token
```

### 5.2 ClusterRole Definition

**Resource-Manager ClusterRole**:
```yaml
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cortex-resource-manager-role
rules:
# Nodes - Read access for cluster topology
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]

# Namespaces - Full management
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Pods - Full management for MCP servers and workers
- apiGroups: [""]
  resources: ["pods", "pods/log", "pods/status"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Services - Full management
- apiGroups: [""]
  resources: ["services", "endpoints"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# ConfigMaps - Full management
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Secrets - Read access only (creation via Vault)
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "watch"]

# ResourceQuotas and LimitRanges
- apiGroups: [""]
  resources: ["resourcequotas", "limitranges"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]

# PersistentVolumes and PersistentVolumeClaims
- apiGroups: [""]
  resources: ["persistentvolumes", "persistentvolumeclaims"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Deployments, ReplicaSets, StatefulSets
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Jobs and CronJobs
- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Events - Read for monitoring
- apiGroups: [""]
  resources: ["events"]
  verbs: ["get", "list", "watch"]

# Metrics - Read for monitoring
- apiGroups: ["metrics.k8s.io"]
  resources: ["nodes", "pods"]
  verbs: ["get", "list"]

# Custom Resource Definitions (if needed)
- apiGroups: ["apiextensions.k8s.io"]
  resources: ["customresourcedefinitions"]
  verbs: ["get", "list", "watch"]
```

### 5.3 ClusterRoleBinding

**Bind ClusterRole to ServiceAccount**:
```yaml
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cortex-resource-manager-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cortex-resource-manager-role
subjects:
- kind: ServiceAccount
  name: cortex-resource-manager
  namespace: cortex-system
```

### 5.4 Namespace-Specific Roles

**MCP Namespace Role (for namespace-scoped operations)**:
```yaml
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: cortex-mcp-manager
  namespace: cortex-mcp
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "pods/exec"]
  verbs: ["get", "list", "watch", "create", "delete"]

- apiGroups: [""]
  resources: ["services"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]

- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: cortex-mcp-manager-binding
  namespace: cortex-mcp
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: cortex-mcp-manager
subjects:
- kind: ServiceAccount
  name: cortex-resource-manager
  namespace: cortex-system
```

### 5.5 Using Service Account in Code

**Python Example with ServiceAccount**:
```python
from kubernetes import client, config

def get_k8s_client_from_service_account():
    """Initialize Kubernetes client using in-cluster service account"""
    try:
        # Load in-cluster config (when running inside K8s)
        config.load_incluster_config()
    except:
        # Fallback to kubeconfig (when running outside K8s)
        config.load_kube_config()

    return client.CoreV1Api()

# Usage
v1 = get_k8s_client_from_service_account()
pods = v1.list_namespaced_pod("cortex-mcp")
```

---

## 6. Secret Management Patterns

### 6.1 Secret Types and Usage

**Talos Configuration Secret**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: talos-config
  namespace: cortex-mcp
type: Opaque
stringData:
  talosconfig: |
    context: prod-cluster
    contexts:
      prod-cluster:
        endpoints:
          - 192.168.1.10
          - 192.168.1.11
        ca: LS0t...
        crt: LS0t...
        key: LS0t...
```

**MCP Server Credentials**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: proxmox-mcp-credentials
  namespace: cortex-mcp
type: Opaque
stringData:
  PROXMOX_URL: "https://proxmox.example.com:8006"
  PROXMOX_TOKEN_ID: "cortex@pve!mcp-token"
  PROXMOX_TOKEN_SECRET: "********-****-****-****-************"
```

### 6.2 Secret Creation and Management

**Python Secret Manager**:
```python
import base64

class SecretManager:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()

    def create_secret(self, name: str, namespace: str, data: dict, secret_type: str = "Opaque"):
        """Create Kubernetes secret"""
        # Encode data to base64
        encoded_data = {
            key: base64.b64encode(value.encode()).decode()
            for key, value in data.items()
        }

        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            type=secret_type,
            data=encoded_data
        )

        try:
            self.v1.create_namespaced_secret(namespace, secret)
            print(f"Secret '{name}' created in namespace '{namespace}'")
        except Exception as e:
            print(f"Error creating secret: {e}")

    def get_secret(self, name: str, namespace: str) -> dict:
        """Retrieve and decode secret"""
        try:
            secret = self.v1.read_namespaced_secret(name, namespace)

            # Decode base64 data
            decoded_data = {
                key: base64.b64decode(value).decode()
                for key, value in (secret.data or {}).items()
            }

            return decoded_data
        except Exception as e:
            print(f"Error retrieving secret: {e}")
            return {}

    def update_secret(self, name: str, namespace: str, data: dict):
        """Update existing secret"""
        # Encode data
        encoded_data = {
            key: base64.b64encode(value.encode()).decode()
            for key, value in data.items()
        }

        try:
            secret = self.v1.read_namespaced_secret(name, namespace)
            secret.data = encoded_data

            self.v1.replace_namespaced_secret(name, namespace, secret)
            print(f"Secret '{name}' updated")
        except Exception as e:
            print(f"Error updating secret: {e}")

    def delete_secret(self, name: str, namespace: str):
        """Delete secret"""
        try:
            self.v1.delete_namespaced_secret(name, namespace)
            print(f"Secret '{name}' deleted")
        except Exception as e:
            print(f"Error deleting secret: {e}")
```

### 6.3 Mounting Secrets in Pods

**Volume Mount**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mcp-server-with-secrets
spec:
  containers:
  - name: mcp-server
    image: ghcr.io/ry-ops/proxmox-mcp-server:latest
    volumeMounts:
    - name: credentials
      mountPath: /etc/mcp/secrets
      readOnly: true
    env:
    - name: PROXMOX_URL
      valueFrom:
        secretKeyRef:
          name: proxmox-mcp-credentials
          key: PROXMOX_URL
  volumes:
  - name: credentials
    secret:
      secretName: proxmox-mcp-credentials
```

### 6.4 Secret Rotation Strategy

**Automated Secret Rotation**:
```python
def rotate_mcp_credentials(mcp_type: str, namespace: str = "cortex-mcp"):
    """Rotate MCP server credentials"""
    secret_manager = SecretManager(k8s_manager)

    # Generate new credentials (implementation depends on MCP type)
    new_credentials = generate_new_credentials(mcp_type)

    # Update secret
    secret_name = f"{mcp_type}-mcp-credentials"
    secret_manager.update_secret(secret_name, namespace, new_credentials)

    # Trigger rolling restart of MCP server pods
    restart_mcp_server_pods(mcp_type, namespace)

    # Log rotation event
    log_secret_rotation(mcp_type, namespace)
```

---

## 7. ConfigMap Integration

### 7.1 ConfigMap Usage Patterns

**MCP Server Configuration**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: talos-mcp-config
  namespace: cortex-mcp
  labels:
    app: mcp-server
    mcp.cortex.dev/type: talos
data:
  # Server configuration
  server-config.yaml: |
    server:
      port: 8080
      log_level: info
      timeout: 30s

    talos:
      default_endpoint: https://192.168.1.10:50000
      verify_tls: true
      retry_attempts: 3

    kubernetes:
      enabled: true
      kubeconfig_path: /etc/kubernetes/kubeconfig

  # Feature flags
  features.json: |
    {
      "enable_cluster_management": true,
      "enable_node_operations": true,
      "enable_health_monitoring": true,
      "experimental_features": false
    }

  # Logging configuration
  logging.conf: |
    [loggers]
    keys=root,talos,kubernetes

    [handlers]
    keys=consoleHandler,fileHandler

    [formatters]
    keys=detailed

    [logger_root]
    level=INFO
    handlers=consoleHandler
```

### 7.2 ConfigMap Management

**Python ConfigMap Manager**:
```python
class ConfigMapManager:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()

    def create_configmap(self, name: str, namespace: str, data: dict, labels: dict = None):
        """Create ConfigMap"""
        configmap = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels=labels or {}
            ),
            data=data
        )

        try:
            self.v1.create_namespaced_config_map(namespace, configmap)
            print(f"ConfigMap '{name}' created")
        except Exception as e:
            print(f"Error creating ConfigMap: {e}")

    def get_configmap(self, name: str, namespace: str) -> dict:
        """Get ConfigMap data"""
        try:
            configmap = self.v1.read_namespaced_config_map(name, namespace)
            return configmap.data or {}
        except Exception as e:
            print(f"Error getting ConfigMap: {e}")
            return {}

    def update_configmap(self, name: str, namespace: str, data: dict):
        """Update ConfigMap"""
        try:
            configmap = self.v1.read_namespaced_config_map(name, namespace)
            configmap.data = data

            self.v1.replace_namespaced_config_map(name, namespace, configmap)
            print(f"ConfigMap '{name}' updated")
        except Exception as e:
            print(f"Error updating ConfigMap: {e}")

    def watch_configmap_changes(self, namespace: str, callback):
        """Watch for ConfigMap changes"""
        from kubernetes import watch

        w = watch.Watch()
        for event in w.stream(self.v1.list_namespaced_config_map, namespace=namespace):
            event_type = event['type']
            configmap = event['object']
            callback(event_type, configmap.metadata.name, configmap.data)
```

### 7.3 Mounting ConfigMaps in Pods

**As Volume**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mcp-server-with-config
spec:
  containers:
  - name: mcp-server
    image: ghcr.io/ry-ops/talos-mcp-server:latest
    volumeMounts:
    - name: config
      mountPath: /etc/mcp/config
      readOnly: true
  volumes:
  - name: config
    configMap:
      name: talos-mcp-config
```

**As Environment Variables**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mcp-server-env-config
spec:
  containers:
  - name: mcp-server
    image: ghcr.io/ry-ops/talos-mcp-server:latest
    envFrom:
    - configMapRef:
        name: talos-mcp-config
```

---

## 8. Event Watching and Reaction Patterns

### 8.1 Event Types and Significance

**Critical Events to Monitor**:
- Pod lifecycle events (Created, Started, Failed, Killed)
- Node events (NodeReady, NodeNotReady, NodePressure)
- Deployment events (ScalingReplicaSet, FailedCreate)
- Resource events (FailedScheduling, ResourceExhausted)
- Health probe events (Unhealthy, ProbeFailure)

### 8.2 Event Watcher Implementation

**Python Event Watcher**:
```python
from kubernetes import watch

class EventWatcher:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()
        self.apps_v1 = k8s_manager.get_apps_v1_api()

    def watch_namespace_events(self, namespace: str, event_handler):
        """Watch events in a namespace"""
        w = watch.Watch()

        try:
            for event in w.stream(
                self.v1.list_namespaced_event,
                namespace=namespace,
                timeout_seconds=0  # Watch indefinitely
            ):
                event_type = event['type']  # ADDED, MODIFIED, DELETED
                event_obj = event['object']

                event_data = {
                    "type": event_type,
                    "event_reason": event_obj.reason,
                    "event_message": event_obj.message,
                    "involved_object": {
                        "kind": event_obj.involved_object.kind,
                        "name": event_obj.involved_object.name,
                        "namespace": event_obj.involved_object.namespace
                    },
                    "first_timestamp": event_obj.first_timestamp,
                    "last_timestamp": event_obj.last_timestamp,
                    "count": event_obj.count
                }

                # Call handler
                event_handler(event_data)
        except Exception as e:
            print(f"Error watching events: {e}")

    def watch_pod_changes(self, namespace: str, label_selector: str, pod_handler):
        """Watch pod changes"""
        w = watch.Watch()

        try:
            for event in w.stream(
                self.v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector,
                timeout_seconds=0
            ):
                event_type = event['type']  # ADDED, MODIFIED, DELETED
                pod = event['object']

                pod_data = {
                    "event_type": event_type,
                    "pod_name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": pod.status.phase,
                    "conditions": [
                        {"type": c.type, "status": c.status}
                        for c in (pod.status.conditions or [])
                    ],
                    "container_statuses": [
                        {
                            "name": cs.name,
                            "ready": cs.ready,
                            "restart_count": cs.restart_count
                        }
                        for cs in (pod.status.container_statuses or [])
                    ]
                }

                # Call handler
                pod_handler(pod_data)
        except Exception as e:
            print(f"Error watching pods: {e}")
```

### 8.3 Event Reaction Patterns

**Automated Response System**:
```python
class EventReactor:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()
        self.apps_v1 = k8s_manager.get_apps_v1_api()

    def handle_event(self, event_data: dict):
        """Handle event and trigger appropriate reaction"""
        reason = event_data.get("event_reason")
        involved_object = event_data.get("involved_object", {})

        # Pod scheduling failure
        if reason == "FailedScheduling":
            self._handle_scheduling_failure(involved_object)

        # Pod crash loop
        elif reason == "BackOff":
            self._handle_crash_loop(involved_object)

        # Node not ready
        elif reason == "NodeNotReady":
            self._handle_node_failure(involved_object)

        # Resource exhaustion
        elif reason == "ResourceExhausted":
            self._handle_resource_exhaustion(involved_object)

        # Probe failure
        elif "Unhealthy" in reason:
            self._handle_probe_failure(involved_object)

    def _handle_scheduling_failure(self, obj: dict):
        """React to pod scheduling failure"""
        print(f"Scheduling failure detected for {obj['kind']}: {obj['name']}")

        # Check node resources
        nodes = self.v1.list_node()
        for node in nodes.items:
            allocatable = node.status.allocatable
            print(f"Node {node.metadata.name} allocatable: {allocatable}")

        # Consider scaling cluster or adjusting resource requests
        # Trigger alert to resource-manager

    def _handle_crash_loop(self, obj: dict):
        """React to crash loop backoff"""
        print(f"Crash loop detected for pod: {obj['name']}")

        # Get pod logs
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=obj['name'],
                namespace=obj['namespace'],
                tail_lines=50
            )
            print(f"Recent logs:\n{logs}")

            # Analyze logs for common errors
            # Consider restarting with different config
        except Exception as e:
            print(f"Error getting logs: {e}")

    def _handle_node_failure(self, obj: dict):
        """React to node not ready"""
        node_name = obj['name']
        print(f"Node failure detected: {node_name}")

        # Cordon node to prevent new pods
        try:
            body = {
                "spec": {
                    "unschedulable": True
                }
            }
            self.v1.patch_node(node_name, body)
            print(f"Node {node_name} cordoned")
        except Exception as e:
            print(f"Error cordoning node: {e}")

        # Trigger infrastructure-contractor for node replacement

    def _handle_resource_exhaustion(self, obj: dict):
        """React to resource exhaustion"""
        namespace = obj['namespace']
        print(f"Resource exhaustion in namespace: {namespace}")

        # Get namespace resource quota usage
        # Consider increasing quota or scaling down workloads
        # Alert resource-manager

    def _handle_probe_failure(self, obj: dict):
        """React to health probe failure"""
        print(f"Probe failure for pod: {obj['name']}")

        # Check if pod is stuck in initialization
        # Consider restarting pod or adjusting probe parameters
```

### 8.4 Event Logging and Alerting

**Event Logger**:
```python
import json
from datetime import datetime

class EventLogger:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir

    def log_event(self, event_data: dict):
        """Log event to file"""
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "event": event_data
        }

        # Append to daily log file
        log_file = f"{self.log_dir}/events-{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def get_recent_events(self, hours: int = 24) -> list:
        """Get recent events from logs"""
        # Implementation to read and filter events
        pass
```

---

## 9. Metric Scraping from kube-state-metrics

### 9.1 kube-state-metrics Deployment

**Deployment Manifest**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kube-state-metrics
  namespace: cortex-monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kube-state-metrics
  template:
    metadata:
      labels:
        app: kube-state-metrics
    spec:
      serviceAccountName: kube-state-metrics
      containers:
      - name: kube-state-metrics
        image: registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.10.0
        ports:
        - containerPort: 8080
          name: http-metrics
        - containerPort: 8081
          name: telemetry
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /
            port: 8081
          initialDelaySeconds: 5
          timeoutSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: kube-state-metrics
  namespace: cortex-monitoring
spec:
  selector:
    app: kube-state-metrics
  ports:
  - name: http-metrics
    port: 8080
    targetPort: http-metrics
  - name: telemetry
    port: 8081
    targetPort: telemetry
```

### 9.2 Metric Collection

**Python Metrics Scraper**:
```python
import requests
from prometheus_client.parser import text_string_to_metric_families

class MetricsScraper:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.v1 = k8s_manager.get_core_v1_api()

    def scrape_kube_state_metrics(self, namespace: str = "cortex-monitoring") -> dict:
        """Scrape metrics from kube-state-metrics"""
        # Get kube-state-metrics service endpoint
        service = self.v1.read_namespaced_service("kube-state-metrics", namespace)
        cluster_ip = service.spec.cluster_ip
        port = service.spec.ports[0].port

        # Scrape metrics
        metrics_url = f"http://{cluster_ip}:{port}/metrics"

        try:
            response = requests.get(metrics_url, timeout=10)
            response.raise_for_status()

            # Parse Prometheus metrics
            metrics = self._parse_prometheus_metrics(response.text)
            return metrics
        except Exception as e:
            print(f"Error scraping metrics: {e}")
            return {}

    def _parse_prometheus_metrics(self, metrics_text: str) -> dict:
        """Parse Prometheus text format metrics"""
        parsed_metrics = {}

        for family in text_string_to_metric_families(metrics_text):
            metric_name = family.name
            metric_type = family.type

            parsed_metrics[metric_name] = {
                "type": metric_type,
                "help": family.documentation,
                "samples": []
            }

            for sample in family.samples:
                parsed_metrics[metric_name]["samples"].append({
                    "labels": sample.labels,
                    "value": sample.value
                })

        return parsed_metrics

    def get_cluster_resource_metrics(self) -> dict:
        """Get cluster-wide resource metrics"""
        metrics = self.scrape_kube_state_metrics()

        # Extract key metrics
        cluster_metrics = {
            "nodes": {
                "total": self._get_metric_value(metrics, "kube_node_info"),
                "ready": self._get_metric_value(metrics, "kube_node_status_condition", {"condition": "Ready", "status": "true"})
            },
            "pods": {
                "total": self._get_metric_value(metrics, "kube_pod_info"),
                "running": self._get_metric_value(metrics, "kube_pod_status_phase", {"phase": "Running"}),
                "pending": self._get_metric_value(metrics, "kube_pod_status_phase", {"phase": "Pending"}),
                "failed": self._get_metric_value(metrics, "kube_pod_status_phase", {"phase": "Failed"})
            },
            "deployments": {
                "total": self._get_metric_value(metrics, "kube_deployment_created"),
                "available": self._get_metric_value(metrics, "kube_deployment_status_replicas_available")
            }
        }

        return cluster_metrics

    def _get_metric_value(self, metrics: dict, metric_name: str, label_filter: dict = None) -> int:
        """Extract metric value with optional label filtering"""
        if metric_name not in metrics:
            return 0

        metric = metrics[metric_name]
        total = 0

        for sample in metric["samples"]:
            if label_filter:
                # Check if all filter labels match
                match = all(
                    sample["labels"].get(k) == v
                    for k, v in label_filter.items()
                )
                if match:
                    total += sample["value"]
            else:
                total += sample["value"]

        return int(total)
```

### 9.3 Metrics Analysis and Reporting

**Cluster Health Report**:
```python
def generate_cluster_health_report(cluster_name: str) -> dict:
    """Generate comprehensive cluster health report"""
    rm = K8sResourceManager(cluster_name)
    scraper = MetricsScraper(rm)

    # Collect metrics
    metrics = scraper.get_cluster_resource_metrics()

    # Analyze health
    health_status = "healthy"
    issues = []

    # Check node health
    if metrics["nodes"]["ready"] < metrics["nodes"]["total"]:
        health_status = "degraded"
        issues.append("Some nodes are not ready")

    # Check pod health
    if metrics["pods"]["failed"] > 0:
        health_status = "degraded"
        issues.append(f"{metrics['pods']['failed']} pods in Failed state")

    if metrics["pods"]["pending"] > metrics["pods"]["total"] * 0.1:  # > 10% pending
        health_status = "warning"
        issues.append(f"High number of pending pods: {metrics['pods']['pending']}")

    # Generate report
    report = {
        "cluster": cluster_name,
        "timestamp": datetime.utcnow().isoformat(),
        "health_status": health_status,
        "metrics": metrics,
        "issues": issues,
        "recommendations": []
    }

    # Add recommendations
    if metrics["nodes"]["ready"] < 3:
        report["recommendations"].append("Scale cluster to at least 3 nodes for HA")

    if metrics["pods"]["running"] / metrics["nodes"]["ready"] > 100:
        report["recommendations"].append("Consider adding more nodes (high pod density)")

    return report
```

---

## 10. Integration with talos-mcp-server

### 10.1 Talos MCP Server Integration Architecture

**Integration Flow**:
```
┌────────────────────────────────────────────────────────────┐
│              Cortex Resource-Manager                       │
│                                                            │
│  1. Discovers talos-mcp-server pods in cortex-mcp namespace│
│  2. Establishes connection to MCP server service           │
│  3. Uses MCP tools for Talos cluster operations            │
│  4. Monitors cluster health via K8s API + Talos API        │
└────────────────┬───────────────────────────────────────────┘
                 │
                 v
┌────────────────────────────────────────────────────────────┐
│          talos-mcp-server (Running in K8s)                 │
│                                                            │
│  Tools:                                                    │
│  - talos_health                                            │
│  - talos_bootstrap                                         │
│  - talos_apply_config                                      │
│  - talos_kubeconfig                                        │
│  - talos_get_services                                      │
└────────────────┬───────────────────────────────────────────┘
                 │
                 v
┌────────────────────────────────────────────────────────────┐
│            Talos Kubernetes Cluster                        │
│  - Control Plane Nodes (3+)                                │
│  - Worker Nodes (3+)                                       │
│  - etcd Cluster                                            │
└────────────────────────────────────────────────────────────┘
```

### 10.2 Talos MCP Server Discovery and Connection

**Discovery Implementation**:
```python
class TalosMCPIntegration:
    def __init__(self, k8s_manager: K8sResourceManager):
        self.k8s = k8s_manager
        self.discovery = MCPServerDiscovery(k8s_manager)

    def get_talos_mcp_endpoint(self, namespace: str = "cortex-mcp") -> str:
        """Get talos-mcp-server endpoint"""
        server_info = self.discovery.find_mcp_server_by_type("talos", namespace)

        if not server_info:
            raise Exception("talos-mcp-server not found in cluster")

        if not server_info["ready"]:
            raise Exception("talos-mcp-server is not ready")

        return server_info["endpoint"]

    def check_talos_cluster_health(self, control_plane_ips: list) -> dict:
        """Check Talos cluster health via MCP server"""
        # This would use the MCP protocol to call talos_health tool
        # Implementation depends on MCP client library

        # Example conceptual code:
        mcp_endpoint = self.get_talos_mcp_endpoint()

        # Call talos_health via MCP protocol
        health_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": {}
        }

        for node_ip in control_plane_ips:
            # MCP call: talos_health --nodes {node_ip}
            node_health = self._call_mcp_tool("talos_health", {"nodes": node_ip})
            health_results["nodes"][node_ip] = node_health

        return health_results

    def _call_mcp_tool(self, tool_name: str, params: dict):
        """Call MCP tool (conceptual - actual implementation depends on MCP protocol)"""
        # This would use the MCP protocol specification
        # to make a tool call to the talos-mcp-server
        pass
```

### 10.3 Combined K8s + Talos Monitoring

**Unified Monitoring**:
```python
class UnifiedClusterMonitor:
    def __init__(self, cluster_name: str):
        self.k8s_manager = K8sResourceManager(cluster_name)
        self.health_monitor = HealthMonitor(self.k8s_manager)
        self.metrics_scraper = MetricsScraper(self.k8s_manager)
        self.talos_integration = TalosMCPIntegration(self.k8s_manager)

    def get_comprehensive_cluster_status(self) -> dict:
        """Get complete cluster status from both K8s and Talos perspectives"""

        # K8s metrics
        k8s_metrics = self.metrics_scraper.get_cluster_resource_metrics()

        # Pod health
        mcp_pod_health = self.health_monitor.monitor_mcp_servers("cortex-mcp")

        # Talos cluster health (via talos-mcp-server)
        control_plane_ips = self._get_control_plane_ips()
        talos_health = self.talos_integration.check_talos_cluster_health(control_plane_ips)

        # Combine all data
        comprehensive_status = {
            "cluster_name": self.k8s_manager.cluster_name,
            "timestamp": datetime.utcnow().isoformat(),
            "kubernetes_metrics": k8s_metrics,
            "mcp_servers_health": mcp_pod_health,
            "talos_cluster_health": talos_health,
            "overall_status": self._determine_overall_status(
                k8s_metrics,
                mcp_pod_health,
                talos_health
            )
        }

        return comprehensive_status

    def _get_control_plane_ips(self) -> list:
        """Get control plane node IPs"""
        v1 = self.k8s_manager.get_core_v1_api()
        nodes = v1.list_node(label_selector="node-role.kubernetes.io/control-plane")

        ips = []
        for node in nodes.items:
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    ips.append(address.address)

        return ips

    def _determine_overall_status(self, k8s_metrics, mcp_health, talos_health) -> str:
        """Determine overall cluster health status"""
        # Logic to combine all health signals
        if k8s_metrics["nodes"]["ready"] < k8s_metrics["nodes"]["total"]:
            return "degraded"

        if mcp_health["unhealthy_pods"] > 0:
            return "degraded"

        # Check Talos node health
        for node_ip, health in talos_health["nodes"].items():
            if not health.get("healthy"):
                return "degraded"

        return "healthy"
```

### 10.4 Operational Workflows

**Cluster Bootstrap via Resource-Manager**:
```python
def bootstrap_new_cluster_workflow(cluster_config: dict):
    """
    Complete workflow to bootstrap new Talos cluster using resource-manager

    Steps:
    1. Request VMs from infrastructure-contractor
    2. Use talos-mcp-server to generate configs
    3. Apply configs to nodes
    4. Bootstrap cluster
    5. Deploy MCP servers to cluster
    6. Register cluster in resource-manager
    """

    # Step 1: Provision VMs (coordinate with infrastructure-contractor)
    vm_ips = provision_cluster_vms(cluster_config)

    # Step 2: Generate Talos configs via talos-mcp-server
    talos_configs = generate_talos_configs(
        cluster_name=cluster_config["name"],
        control_plane_ips=vm_ips["control_plane"],
        worker_ips=vm_ips["workers"]
    )

    # Step 3: Apply configs
    apply_talos_configs(vm_ips, talos_configs)

    # Step 4: Bootstrap
    bootstrap_cluster(vm_ips["control_plane"][0])

    # Step 5: Wait for cluster ready
    wait_for_cluster_ready(vm_ips["control_plane"][0])

    # Step 6: Get kubeconfig
    kubeconfig = get_cluster_kubeconfig(vm_ips["control_plane"][0])

    # Step 7: Deploy MCP servers to new cluster
    deploy_mcp_servers_to_cluster(kubeconfig)

    # Step 8: Register in resource-manager
    register_cluster(cluster_config["name"], kubeconfig, vm_ips)

    return {
        "cluster_name": cluster_config["name"],
        "status": "operational",
        "endpoints": vm_ips,
        "kubeconfig_path": save_kubeconfig(cluster_config["name"], kubeconfig)
    }
```

---

## 11. Best Practices and Security

### 11.1 Connection Security

- Use TLS for all K8s API connections
- Rotate service account tokens quarterly
- Implement network policies to restrict MCP server access
- Use RBAC with least privilege principle
- Store kubeconfigs encrypted at rest

### 11.2 Monitoring and Alerting

- Monitor API server latency (p95 < 200ms)
- Alert on pod restart loops (> 5 restarts in 10 minutes)
- Track MCP server health continuously
- Monitor etcd cluster health
- Set up alerts for resource quota exhaustion

### 11.3 Operational Excellence

- Maintain kubeconfig backups in secure vault
- Document all RBAC role assignments
- Regular audit of namespace resource usage
- Automated testing of failover scenarios
- Keep resource-manager integration code version controlled

---

## 12. Troubleshooting

### Common Issues

**Issue: Cannot connect to cluster**
- Verify kubeconfig is valid
- Check API server is reachable
- Validate service account permissions
- Ensure network connectivity

**Issue: MCP servers not discovered**
- Check pod labels are correct
- Verify namespace is correct
- Ensure pods are in Running state
- Check service DNS resolution

**Issue: Metrics scraping fails**
- Verify kube-state-metrics is deployed
- Check service endpoint is accessible
- Validate RBAC permissions for metrics
- Review firewall rules

---

## 13. References

- Kubernetes API Documentation: https://kubernetes.io/docs/reference/
- Talos Linux Documentation: https://www.talos.dev/
- kube-state-metrics: https://github.com/kubernetes/kube-state-metrics
- Python Kubernetes Client: https://github.com/kubernetes-client/python
- Node.js Kubernetes Client: https://github.com/kubernetes-client/javascript

---

**Document Version**: 1.0.0
**Maintained By**: Cortex Resource-Manager Team
**Last Review**: 2025-12-09
