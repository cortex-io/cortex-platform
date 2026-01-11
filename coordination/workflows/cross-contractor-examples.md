# Cross-Contractor Workflow Examples

This document provides complete, production-ready workflow examples demonstrating how multiple contractors coordinate to accomplish complex infrastructure and operational tasks.

## Table of Contents

1. [Deploy Monitoring Stack](#1-deploy-monitoring-stack)
2. [Build New K8s Cluster](#2-build-new-k8s-cluster)
3. [Disaster Recovery Failover](#3-disaster-recovery-failover)
4. [Application Deployment Pipeline](#4-application-deployment-pipeline)
5. [Security Incident Response](#5-security-incident-response)

---

## 1. Deploy Monitoring Stack

**Objective**: Deploy a complete monitoring solution with Prometheus, Grafana, and automated alerting.

**Contractors Involved**: infrastructure-contractor, talos-contractor, n8n-contractor

### Step-by-Step Sequence

#### Phase 1: Infrastructure Preparation (infrastructure-contractor)

```json
{
  "task_id": "mon-001-infra",
  "contractor": "infrastructure-contractor",
  "action": "provision_monitoring_vms",
  "parameters": {
    "vm_specs": [
      {
        "name": "monitoring-node-01",
        "cpu": 4,
        "memory": 8192,
        "disk": 100,
        "network": "vlan20-monitoring"
      },
      {
        "name": "monitoring-node-02",
        "cpu": 4,
        "memory": 8192,
        "disk": 100,
        "network": "vlan20-monitoring"
      }
    ],
    "storage": {
      "type": "ceph",
      "pool": "monitoring-data",
      "size": 500
    }
  },
  "expected_outputs": {
    "vm_ips": ["10.20.1.10", "10.20.1.11"],
    "storage_endpoint": "ceph://monitoring-data",
    "network_config": "vlan20 configured"
  }
}
```

**Output Handoff**:
```json
{
  "handoff_id": "mon-001-infra-to-talos",
  "from_contractor": "infrastructure-contractor",
  "to_contractor": "talos-contractor",
  "status": "completed",
  "data": {
    "vm_nodes": [
      {
        "hostname": "monitoring-node-01",
        "ip": "10.20.1.10",
        "mac": "52:54:00:ab:cd:01"
      },
      {
        "hostname": "monitoring-node-02",
        "ip": "10.20.1.11",
        "mac": "52:54:00:ab:cd:02"
      }
    ],
    "storage_config": {
      "endpoint": "10.20.1.5:6789",
      "pool": "monitoring-data",
      "credentials_secret": "monitoring-ceph-secret"
    },
    "network_gateway": "10.20.1.1"
  }
}
```

#### Phase 2: K8s Deployment (talos-contractor)

```json
{
  "task_id": "mon-001-k8s",
  "contractor": "talos-contractor",
  "action": "deploy_monitoring_stack",
  "parameters": {
    "cluster": "production-cluster",
    "namespace": "monitoring",
    "components": [
      {
        "name": "prometheus",
        "chart": "prometheus-community/kube-prometheus-stack",
        "version": "55.5.0",
        "values": {
          "prometheus.retention": "30d",
          "prometheus.storageSpec.volumeClaimTemplate.spec.resources.requests.storage": "100Gi",
          "prometheus.storageSpec.volumeClaimTemplate.spec.storageClassName": "ceph-rbd",
          "alertmanager.enabled": true,
          "grafana.enabled": true,
          "grafana.persistence.enabled": true,
          "grafana.persistence.size": "10Gi"
        }
      }
    ],
    "storage_backend": "ceph-rbd",
    "ingress": {
      "prometheus": "prometheus.cortex.local",
      "grafana": "grafana.cortex.local",
      "alertmanager": "alertmanager.cortex.local"
    }
  },
  "expected_outputs": {
    "prometheus_endpoint": "http://prometheus.monitoring.svc:9090",
    "grafana_endpoint": "http://grafana.monitoring.svc:3000",
    "alertmanager_endpoint": "http://alertmanager.monitoring.svc:9093",
    "webhook_urls": ["http://alertmanager.monitoring.svc:9093/api/v2/alerts"]
  }
}
```

**Output Handoff**:
```json
{
  "handoff_id": "mon-001-k8s-to-n8n",
  "from_contractor": "talos-contractor",
  "to_contractor": "n8n-contractor",
  "status": "completed",
  "data": {
    "monitoring_endpoints": {
      "prometheus": "https://prometheus.cortex.local",
      "grafana": "https://grafana.cortex.local",
      "alertmanager": "https://alertmanager.cortex.local"
    },
    "webhook_config": {
      "alertmanager_url": "http://alertmanager.monitoring.svc:9093/api/v2/alerts",
      "prometheus_url": "http://prometheus.monitoring.svc:9090"
    },
    "credentials": {
      "grafana_admin_secret": "monitoring/grafana-admin-credentials",
      "prometheus_token_secret": "monitoring/prometheus-sa-token"
    },
    "default_dashboards": [
      "kubernetes-cluster-overview",
      "node-exporter-full",
      "prometheus-stats"
    ]
  }
}
```

#### Phase 3: Alert Workflow Setup (n8n-contractor)

```json
{
  "task_id": "mon-001-alerts",
  "contractor": "n8n-contractor",
  "action": "create_alert_workflows",
  "parameters": {
    "alertmanager_endpoint": "https://alertmanager.cortex.local",
    "workflows": [
      {
        "name": "critical-alert-handler",
        "trigger": "webhook",
        "webhook_path": "/webhook/critical-alerts",
        "actions": [
          {
            "type": "slack_notification",
            "channel": "#ops-critical",
            "template": "CRITICAL: {{alert.name}} on {{alert.instance}}"
          },
          {
            "type": "pagerduty_incident",
            "severity": "critical",
            "service": "infrastructure"
          },
          {
            "type": "create_ticket",
            "system": "jira",
            "project": "OPS"
          }
        ]
      },
      {
        "name": "warning-alert-handler",
        "trigger": "webhook",
        "webhook_path": "/webhook/warning-alerts",
        "actions": [
          {
            "type": "slack_notification",
            "channel": "#ops-warnings"
          },
          {
            "type": "aggregate_and_report",
            "interval": "1h"
          }
        ]
      },
      {
        "name": "health-check-monitor",
        "trigger": "schedule",
        "schedule": "*/5 * * * *",
        "actions": [
          {
            "type": "http_request",
            "url": "{{prometheus_endpoint}}/-/healthy"
          },
          {
            "type": "http_request",
            "url": "{{grafana_endpoint}}/api/health"
          },
          {
            "type": "on_failure",
            "notify": "#ops-critical"
          }
        ]
      }
    ],
    "alertmanager_config": {
      "receivers": [
        {
          "name": "n8n-critical",
          "webhook_configs": [
            {
              "url": "https://n8n.cortex.local/webhook/critical-alerts",
              "send_resolved": true
            }
          ]
        },
        {
          "name": "n8n-warning",
          "webhook_configs": [
            {
              "url": "https://n8n.cortex.local/webhook/warning-alerts",
              "send_resolved": true
            }
          ]
        }
      ],
      "route": {
        "group_by": ["alertname", "cluster"],
        "group_wait": "10s",
        "group_interval": "5m",
        "repeat_interval": "4h",
        "receiver": "n8n-warning",
        "routes": [
          {
            "match": {"severity": "critical"},
            "receiver": "n8n-critical"
          }
        ]
      }
    }
  }
}
```

### Data Flow Diagram

```
infrastructure-contractor
    |
    | VM IPs, Storage Config
    v
talos-contractor
    |
    | Monitoring Endpoints, Webhook URLs
    v
n8n-contractor
    |
    | Alert Workflows Active
    v
MONITORING STACK OPERATIONAL
```

### Error Handling

**Infrastructure Provisioning Failure**:
```json
{
  "error": "vm_creation_failed",
  "contractor": "infrastructure-contractor",
  "recovery_action": "retry_with_fallback_host",
  "fallback_parameters": {
    "proxmox_host": "pve-02.cortex.local",
    "storage_pool": "local-lvm"
  },
  "notify": ["talos-contractor", "n8n-contractor"],
  "workflow_status": "paused"
}
```

**K8s Deployment Failure**:
```json
{
  "error": "helm_install_failed",
  "contractor": "talos-contractor",
  "details": {
    "component": "prometheus",
    "reason": "insufficient_storage"
  },
  "recovery_action": "request_storage_increase",
  "handoff_back_to": "infrastructure-contractor",
  "request": {
    "action": "expand_storage_pool",
    "pool": "monitoring-data",
    "new_size": 750
  }
}
```

**Alert Workflow Failure**:
```json
{
  "error": "webhook_unreachable",
  "contractor": "n8n-contractor",
  "recovery_action": "verify_network_connectivity",
  "steps": [
    "Check alertmanager service status",
    "Verify network policies allow n8n → monitoring namespace",
    "Test webhook endpoint manually",
    "Escalate to infrastructure-contractor if network issue"
  ]
}
```

### Rollback Procedure

```bash
#!/bin/bash
# Rollback monitoring stack deployment

WORKFLOW_ID="mon-001"

# Step 1: n8n-contractor - Disable alert workflows
cat > /tmp/rollback-alerts.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-rollback-alerts",
  "contractor": "n8n-contractor",
  "action": "disable_workflows",
  "workflow_ids": ["critical-alert-handler", "warning-alert-handler", "health-check-monitor"]
}
EOF

# Step 2: talos-contractor - Uninstall monitoring stack
cat > /tmp/rollback-k8s.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-rollback-k8s",
  "contractor": "talos-contractor",
  "action": "uninstall_helm_release",
  "namespace": "monitoring",
  "release": "kube-prometheus-stack",
  "preserve_pvcs": true
}
EOF

# Step 3: infrastructure-contractor - Deprovision VMs
cat > /tmp/rollback-infra.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-rollback-infra",
  "contractor": "infrastructure-contractor",
  "action": "destroy_vms",
  "vm_names": ["monitoring-node-01", "monitoring-node-02"],
  "preserve_storage": true
}
EOF
```

### Success Criteria

- [ ] VMs provisioned with correct specs
- [ ] Storage pool created and accessible
- [ ] Prometheus collecting metrics from all nodes
- [ ] Grafana dashboards loading correctly
- [ ] Alertmanager routing alerts to n8n
- [ ] n8n workflows triggering on test alerts
- [ ] Health check monitors running every 5 minutes
- [ ] All endpoints accessible via ingress

---

## 2. Build New K8s Cluster

**Objective**: Deploy a complete production-ready Kubernetes cluster from scratch.

**Contractors Involved**: infrastructure-contractor, talos-contractor, n8n-contractor

### Step-by-Step Sequence

#### Phase 1: Infrastructure Provisioning (infrastructure-contractor)

```json
{
  "task_id": "k8s-002-infra",
  "contractor": "infrastructure-contractor",
  "action": "provision_cluster_infrastructure",
  "parameters": {
    "cluster_name": "prod-k8s-02",
    "control_plane_nodes": [
      {
        "name": "k8s-cp-01",
        "cpu": 4,
        "memory": 8192,
        "disk": 100,
        "ip": "10.10.1.10"
      },
      {
        "name": "k8s-cp-02",
        "cpu": 4,
        "memory": 8192,
        "disk": 100,
        "ip": "10.10.1.11"
      },
      {
        "name": "k8s-cp-03",
        "cpu": 4,
        "memory": 8192,
        "disk": 100,
        "ip": "10.10.1.12"
      }
    ],
    "worker_nodes": [
      {
        "name": "k8s-worker-01",
        "cpu": 8,
        "memory": 16384,
        "disk": 200,
        "ip": "10.10.1.20"
      },
      {
        "name": "k8s-worker-02",
        "cpu": 8,
        "memory": 16384,
        "disk": 200,
        "ip": "10.10.1.21"
      },
      {
        "name": "k8s-worker-03",
        "cpu": 8,
        "memory": 16384,
        "disk": 200,
        "ip": "10.10.1.22"
      }
    ],
    "network": {
      "vlan": "vlan10-kubernetes",
      "subnet": "10.10.1.0/24",
      "gateway": "10.10.1.1",
      "dns": ["10.10.1.2", "10.10.1.3"]
    },
    "storage": {
      "type": "ceph",
      "pools": ["k8s-rbd", "k8s-cephfs"],
      "total_size": 2000
    },
    "load_balancer": {
      "type": "haproxy",
      "vip": "10.10.1.100",
      "backend_ports": [6443, 443, 80]
    }
  }
}
```

**Output Handoff**:
```json
{
  "handoff_id": "k8s-002-infra-to-talos",
  "from_contractor": "infrastructure-contractor",
  "to_contractor": "talos-contractor",
  "status": "completed",
  "data": {
    "cluster_name": "prod-k8s-02",
    "control_plane": [
      {"hostname": "k8s-cp-01", "ip": "10.10.1.10", "mac": "52:54:00:aa:bb:01"},
      {"hostname": "k8s-cp-02", "ip": "10.10.1.11", "mac": "52:54:00:aa:bb:02"},
      {"hostname": "k8s-cp-03", "ip": "10.10.1.12", "mac": "52:54:00:aa:bb:03"}
    ],
    "workers": [
      {"hostname": "k8s-worker-01", "ip": "10.10.1.20", "mac": "52:54:00:aa:bb:11"},
      {"hostname": "k8s-worker-02", "ip": "10.10.1.21", "mac": "52:54:00:aa:bb:12"},
      {"hostname": "k8s-worker-03", "ip": "10.10.1.22", "mac": "52:54:00:aa:bb:13"}
    ],
    "network": {
      "pod_cidr": "10.244.0.0/16",
      "service_cidr": "10.96.0.0/12",
      "gateway": "10.10.1.1",
      "dns_servers": ["10.10.1.2", "10.10.1.3"]
    },
    "storage": {
      "ceph_monitors": ["10.10.1.5:6789", "10.10.1.6:6789", "10.10.1.7:6789"],
      "rbd_pool": "k8s-rbd",
      "cephfs_pool": "k8s-cephfs",
      "admin_keyring": "k8s-ceph-admin-secret"
    },
    "load_balancer": {
      "api_endpoint": "https://10.10.1.100:6443",
      "ingress_http": "10.10.1.100:80",
      "ingress_https": "10.10.1.100:443"
    }
  }
}
```

#### Phase 2: Talos Cluster Initialization (talos-contractor)

```json
{
  "task_id": "k8s-002-talos-init",
  "contractor": "talos-contractor",
  "action": "initialize_talos_cluster",
  "parameters": {
    "cluster_name": "prod-k8s-02",
    "talos_version": "v1.6.1",
    "kubernetes_version": "v1.29.1",
    "control_plane_endpoint": "https://10.10.1.100:6443",
    "control_plane_nodes": [
      {"ip": "10.10.1.10", "hostname": "k8s-cp-01"},
      {"ip": "10.10.1.11", "hostname": "k8s-cp-02"},
      {"ip": "10.10.1.12", "hostname": "k8s-cp-03"}
    ],
    "worker_nodes": [
      {"ip": "10.10.1.20", "hostname": "k8s-worker-01"},
      {"ip": "10.10.1.21", "hostname": "k8s-worker-02"},
      {"ip": "10.10.1.22", "hostname": "k8s-worker-03"}
    ],
    "network_config": {
      "cni": "cilium",
      "pod_cidr": "10.244.0.0/16",
      "service_cidr": "10.96.0.0/12"
    },
    "features": {
      "disk_encryption": true,
      "kube_prism": true,
      "cluster_discovery": true
    },
    "post_install": [
      "install_csi_drivers",
      "install_ingress_controller",
      "configure_storage_classes",
      "install_cert_manager"
    ]
  }
}
```

**Substeps**:

1. **Generate Talos Configs**:
```bash
talosctl gen config prod-k8s-02 https://10.10.1.100:6443 \
  --config-patch-control-plane @control-plane-patch.yaml \
  --config-patch-worker @worker-patch.yaml
```

2. **Bootstrap First Control Plane**:
```bash
talosctl apply-config --insecure \
  --nodes 10.10.1.10 \
  --file controlplane.yaml

talosctl bootstrap --nodes 10.10.1.10
```

3. **Join Additional Control Planes**:
```bash
talosctl apply-config --insecure \
  --nodes 10.10.1.11,10.10.1.12 \
  --file controlplane.yaml
```

4. **Join Worker Nodes**:
```bash
talosctl apply-config --insecure \
  --nodes 10.10.1.20,10.10.1.21,10.10.1.22 \
  --file worker.yaml
```

5. **Install Core Components**:
```bash
# Install Cilium CNI
helm install cilium cilium/cilium --namespace kube-system

# Install Ceph CSI drivers
helm install ceph-csi ceph-csi/ceph-csi-rbd --namespace kube-system

# Install Ingress NGINX
helm install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace

# Install cert-manager
helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace --set installCRDs=true
```

**Output Handoff**:
```json
{
  "handoff_id": "k8s-002-talos-to-n8n",
  "from_contractor": "talos-contractor",
  "to_contractor": "n8n-contractor",
  "status": "completed",
  "data": {
    "cluster_name": "prod-k8s-02",
    "cluster_endpoint": "https://10.10.1.100:6443",
    "kubeconfig": "base64_encoded_kubeconfig",
    "cluster_status": {
      "control_plane_nodes": 3,
      "worker_nodes": 3,
      "ready_nodes": 6,
      "kubernetes_version": "v1.29.1",
      "cni": "cilium"
    },
    "installed_components": [
      {
        "name": "cilium",
        "namespace": "kube-system",
        "version": "1.14.5"
      },
      {
        "name": "ceph-csi-rbd",
        "namespace": "kube-system",
        "version": "3.10.1"
      },
      {
        "name": "ingress-nginx",
        "namespace": "ingress-nginx",
        "version": "4.9.0"
      },
      {
        "name": "cert-manager",
        "namespace": "cert-manager",
        "version": "1.13.3"
      }
    ],
    "webhook_targets": {
      "cluster_events": "https://n8n.cortex.local/webhook/k8s-cluster-events",
      "deployment_ready": "https://n8n.cortex.local/webhook/k8s-deployment-ready"
    }
  }
}
```

#### Phase 3: Deployment Automation Setup (n8n-contractor)

```json
{
  "task_id": "k8s-002-automation",
  "contractor": "n8n-contractor",
  "action": "setup_deployment_webhooks",
  "parameters": {
    "cluster_name": "prod-k8s-02",
    "cluster_endpoint": "https://10.10.1.100:6443",
    "workflows": [
      {
        "name": "deployment-webhook-handler",
        "trigger": "webhook",
        "webhook_path": "/webhook/k8s-deploy",
        "actions": [
          {
            "type": "validate_deployment_request",
            "required_fields": ["namespace", "image", "replicas"]
          },
          {
            "type": "create_namespace_if_missing"
          },
          {
            "type": "apply_k8s_manifest",
            "template": "deployment-template.yaml"
          },
          {
            "type": "wait_for_rollout",
            "timeout": 300
          },
          {
            "type": "notify_slack",
            "channel": "#deployments",
            "message": "Deployed {{image}} to {{cluster_name}}/{{namespace}}"
          }
        ]
      },
      {
        "name": "cluster-health-monitor",
        "trigger": "schedule",
        "schedule": "*/10 * * * *",
        "actions": [
          {
            "type": "kubectl_exec",
            "command": "get nodes -o json"
          },
          {
            "type": "check_node_conditions",
            "alert_if": ["NotReady", "MemoryPressure", "DiskPressure"]
          },
          {
            "type": "kubectl_exec",
            "command": "get pods --all-namespaces -o json"
          },
          {
            "type": "check_pod_status",
            "alert_if": ["CrashLoopBackOff", "ImagePullBackOff", "Error"]
          },
          {
            "type": "notify_on_issues",
            "channel": "#ops-alerts"
          }
        ]
      },
      {
        "name": "backup-etcd-snapshot",
        "trigger": "schedule",
        "schedule": "0 2 * * *",
        "actions": [
          {
            "type": "talosctl_exec",
            "command": "etcd snapshot",
            "node": "10.10.1.10"
          },
          {
            "type": "upload_to_s3",
            "bucket": "cortex-backups",
            "path": "etcd-snapshots/prod-k8s-02/"
          },
          {
            "type": "verify_snapshot"
          },
          {
            "type": "rotate_old_snapshots",
            "retention_days": 30
          }
        ]
      }
    ],
    "github_integration": {
      "enabled": true,
      "repositories": ["cortex-apps/*"],
      "webhook_secret": "github-webhook-secret",
      "on_push_to_main": {
        "action": "trigger_deployment",
        "workflow": "deployment-webhook-handler"
      }
    }
  }
}
```

### Data Flow Diagram

```
infrastructure-contractor
    |
    | VMs, Network, Storage, LB
    v
talos-contractor
    |
    | Initialize Cluster, Join Nodes, Install Components
    v
n8n-contractor
    |
    | Setup Webhooks, Health Monitoring, Backups
    v
CLUSTER READY FOR DEPLOYMENTS
```

### Error Handling

**Node Join Failure**:
```json
{
  "error": "node_join_timeout",
  "contractor": "talos-contractor",
  "failed_node": "k8s-worker-02",
  "details": {
    "reason": "network_unreachable",
    "last_known_state": "configuring"
  },
  "recovery_steps": [
    {
      "step": 1,
      "action": "verify_network_connectivity",
      "contractor": "infrastructure-contractor",
      "verify": "ping 10.10.1.21 from gateway"
    },
    {
      "step": 2,
      "action": "check_talos_logs",
      "command": "talosctl logs --nodes 10.10.1.21"
    },
    {
      "step": 3,
      "action": "regenerate_node_config",
      "if": "config_mismatch"
    },
    {
      "step": 4,
      "action": "reapply_config",
      "command": "talosctl apply-config --nodes 10.10.1.21 --file worker.yaml"
    }
  ]
}
```

**CNI Installation Failure**:
```json
{
  "error": "cilium_install_failed",
  "contractor": "talos-contractor",
  "details": {
    "helm_error": "timeout waiting for pods to be ready",
    "namespace": "kube-system"
  },
  "recovery_steps": [
    {
      "step": 1,
      "action": "check_pod_logs",
      "command": "kubectl logs -n kube-system -l app.kubernetes.io/name=cilium"
    },
    {
      "step": 2,
      "action": "verify_network_policies",
      "check": "no restrictive network policies blocking CNI"
    },
    {
      "step": 3,
      "action": "reinstall_with_debug",
      "helm_values": {"debug.enabled": true}
    }
  ]
}
```

### Rollback Procedure

```bash
#!/bin/bash
# Rollback K8s cluster deployment

WORKFLOW_ID="k8s-002"
CLUSTER_NAME="prod-k8s-02"

# Step 1: n8n-contractor - Disable automation
cat > /tmp/rollback-automation.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-rollback-automation",
  "contractor": "n8n-contractor",
  "action": "disable_cluster_workflows",
  "cluster_name": "${CLUSTER_NAME}"
}
EOF

# Step 2: talos-contractor - Destroy cluster
cat > /tmp/rollback-cluster.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-rollback-cluster",
  "contractor": "talos-contractor",
  "action": "destroy_cluster",
  "cluster_name": "${CLUSTER_NAME}",
  "nodes": [
    "10.10.1.10", "10.10.1.11", "10.10.1.12",
    "10.10.1.20", "10.10.1.21", "10.10.1.22"
  ],
  "preserve_etcd_backup": true
}
EOF

# Step 3: infrastructure-contractor - Deprovision infrastructure
cat > /tmp/rollback-infrastructure.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-rollback-infrastructure",
  "contractor": "infrastructure-contractor",
  "action": "destroy_cluster_infrastructure",
  "cluster_name": "${CLUSTER_NAME}",
  "destroy_vms": true,
  "preserve_storage": true,
  "destroy_load_balancer": true
}
EOF
```

### Success Criteria

- [ ] All 6 nodes (3 CP + 3 workers) in Ready state
- [ ] CNI (Cilium) pods running on all nodes
- [ ] CoreDNS resolving correctly
- [ ] CSI drivers installed and storage classes available
- [ ] Ingress controller responding to HTTP/HTTPS
- [ ] cert-manager issuing certificates
- [ ] n8n deployment webhooks responding
- [ ] Health monitoring workflow running
- [ ] Etcd backup workflow scheduled
- [ ] kubectl access working from bastion

---

## 3. Disaster Recovery Failover

**Objective**: Execute automated failover from primary datacenter to DR site during an outage.

**Contractors Involved**: infrastructure-contractor, talos-contractor, n8n-contractor

### Step-by-Step Sequence

#### Phase 1: DR Site Verification (infrastructure-contractor)

```json
{
  "task_id": "dr-003-verify",
  "contractor": "infrastructure-contractor",
  "action": "verify_dr_site_readiness",
  "parameters": {
    "dr_site": "datacenter-02",
    "primary_site": "datacenter-01",
    "checks": [
      {
        "type": "network_connectivity",
        "targets": ["gateway", "dns", "storage"]
      },
      {
        "type": "storage_replication",
        "verify": "ceph_replication_lag < 60s"
      },
      {
        "type": "vm_resources",
        "required": {
          "cpu": 100,
          "memory": 204800,
          "storage": 5000
        }
      },
      {
        "type": "load_balancer_health",
        "vip": "10.20.1.100"
      }
    ]
  }
}
```

**Output**:
```json
{
  "verification_result": {
    "dr_site_ready": true,
    "checks_passed": 4,
    "checks_total": 4,
    "details": {
      "network_connectivity": "all targets reachable",
      "storage_replication_lag": "12s",
      "available_resources": {
        "cpu": 128,
        "memory": 262144,
        "storage": 6000
      },
      "load_balancer_status": "healthy"
    },
    "failover_approved": true,
    "estimated_rto": "15 minutes"
  }
}
```

#### Phase 2: Promote DR Cluster (talos-contractor)

```json
{
  "task_id": "dr-003-promote",
  "contractor": "talos-contractor",
  "action": "promote_dr_cluster",
  "parameters": {
    "primary_cluster": "prod-k8s-01",
    "dr_cluster": "dr-k8s-01",
    "dr_cluster_endpoint": "https://10.20.1.100:6443",
    "failover_mode": "automatic",
    "steps": [
      {
        "action": "verify_dr_cluster_health",
        "acceptable_status": ["Ready"]
      },
      {
        "action": "restore_latest_etcd_snapshot",
        "source": "s3://cortex-backups/etcd-snapshots/prod-k8s-01/latest"
      },
      {
        "action": "update_storage_endpoints",
        "new_endpoints": ["10.20.1.5:6789", "10.20.1.6:6789"]
      },
      {
        "action": "scale_up_workloads",
        "target_replicas": "match_primary"
      },
      {
        "action": "verify_pod_status",
        "required_ready": 0.95
      }
    ],
    "data_sync": {
      "method": "ceph_replication",
      "verify_consistency": true,
      "max_data_loss": "60s"
    }
  }
}
```

**Substeps**:

1. **Verify DR Cluster Health**:
```bash
talosctl --nodes 10.20.1.10 health --wait-timeout 5m
kubectl --kubeconfig dr-kubeconfig get nodes
```

2. **Restore Etcd Snapshot**:
```bash
# Download latest snapshot
aws s3 cp s3://cortex-backups/etcd-snapshots/prod-k8s-01/latest.snapshot /tmp/

# Restore to DR cluster
talosctl --nodes 10.20.1.10 etcd snapshot restore /tmp/latest.snapshot
```

3. **Update Persistent Storage**:
```bash
# Update Ceph endpoints in CSI config
kubectl --kubeconfig dr-kubeconfig patch configmap ceph-csi-config \
  -n kube-system \
  --patch '{"data":{"config.json":"[{\"clusterID\":\"dr-ceph\",\"monitors\":[\"10.20.1.5:6789\",\"10.20.1.6:6789\"]}]"}}'

# Restart CSI pods
kubectl --kubeconfig dr-kubeconfig rollout restart -n kube-system deployment ceph-csi-controller
```

4. **Scale Workloads**:
```bash
# Get deployment specs from primary (if accessible)
# Otherwise use etcd restored state
kubectl --kubeconfig dr-kubeconfig scale deployment --all --replicas=3 -n production
```

**Output Handoff**:
```json
{
  "handoff_id": "dr-003-promote-to-n8n",
  "from_contractor": "talos-contractor",
  "to_contractor": "n8n-contractor",
  "status": "completed",
  "data": {
    "dr_cluster_status": "promoted",
    "cluster_endpoint": "https://10.20.1.100:6443",
    "restored_from_snapshot": "2025-12-09T06:00:00Z",
    "data_loss_window": "8s",
    "workload_status": {
      "total_deployments": 42,
      "ready_deployments": 41,
      "pending_deployments": 1
    },
    "storage_endpoints": ["10.20.1.5:6789", "10.20.1.6:6789"],
    "requires_dns_update": true,
    "requires_notification": true
  }
}
```

#### Phase 3: Update DNS and Notify (n8n-contractor)

```json
{
  "task_id": "dr-003-cutover",
  "contractor": "n8n-contractor",
  "action": "execute_dr_cutover",
  "parameters": {
    "primary_site": "datacenter-01",
    "dr_site": "datacenter-02",
    "dns_updates": [
      {
        "record": "api.cortex.local",
        "old_value": "10.10.1.100",
        "new_value": "10.20.1.100",
        "ttl": 60
      },
      {
        "record": "*.apps.cortex.local",
        "old_value": "10.10.1.100",
        "new_value": "10.20.1.100",
        "ttl": 60
      },
      {
        "record": "grafana.cortex.local",
        "old_value": "10.10.1.100",
        "new_value": "10.20.1.100",
        "ttl": 60
      }
    ],
    "notifications": [
      {
        "channel": "slack",
        "recipients": ["#ops-critical", "#engineering"],
        "template": "DR_FAILOVER_COMPLETE",
        "data": {
          "event": "DR failover completed",
          "primary_site": "datacenter-01 (DOWN)",
          "active_site": "datacenter-02 (DR)",
          "rto_achieved": "14 minutes",
          "data_loss": "8 seconds",
          "status_page": "https://status.cortex.local"
        }
      },
      {
        "channel": "pagerduty",
        "action": "resolve_incident",
        "incident_id": "from_trigger"
      },
      {
        "channel": "email",
        "recipients": ["ops@cortex.local", "management@cortex.local"],
        "template": "DR_FAILOVER_SUMMARY"
      },
      {
        "channel": "status_page",
        "action": "update_status",
        "message": "Services running from DR site. Primary site under maintenance."
      }
    ],
    "health_checks": [
      {
        "type": "http",
        "url": "https://api.cortex.local/health",
        "expected_status": 200,
        "retry": 5,
        "interval": 10
      },
      {
        "type": "dns",
        "query": "api.cortex.local",
        "expected": "10.20.1.100"
      }
    ],
    "post_failover_monitoring": {
      "duration": "24h",
      "check_interval": "5m",
      "alert_on": ["high_latency", "error_rate_increase", "pod_restarts"]
    }
  }
}
```

### Data Flow Diagram

```
OUTAGE DETECTED
    |
    v
infrastructure-contractor (verify DR site)
    |
    | DR Site Ready: True
    v
talos-contractor (promote DR cluster)
    |
    | Cluster Promoted, Workloads Running
    v
n8n-contractor (update DNS, notify stakeholders)
    |
    | DNS Updated, Notifications Sent
    v
DR SITE ACTIVE - SERVICES RESTORED
```

### Error Handling

**DR Site Not Ready**:
```json
{
  "error": "dr_site_not_ready",
  "contractor": "infrastructure-contractor",
  "details": {
    "storage_replication_lag": "320s",
    "threshold": "60s"
  },
  "decision": {
    "failover_approved": false,
    "reason": "data_loss_exceeds_rpo",
    "alternative_actions": [
      {
        "action": "wait_for_replication_sync",
        "max_wait": "10m"
      },
      {
        "action": "manual_approval_override",
        "requires": "ops_manager_approval"
      },
      {
        "action": "partial_failover",
        "description": "failover critical services only"
      }
    ]
  }
}
```

**Etcd Restore Failure**:
```json
{
  "error": "etcd_restore_failed",
  "contractor": "talos-contractor",
  "details": {
    "snapshot_corrupted": false,
    "error_message": "insufficient disk space"
  },
  "recovery": {
    "action": "expand_etcd_disk",
    "handoff_to": "infrastructure-contractor",
    "request": {
      "node": "k8s-cp-01",
      "disk_expand": 50
    }
  },
  "alternative": {
    "action": "use_previous_snapshot",
    "snapshot": "s3://cortex-backups/etcd-snapshots/prod-k8s-01/2025-12-08.snapshot",
    "data_loss_window": "24h"
  }
}
```

**DNS Update Failure**:
```json
{
  "error": "dns_update_failed",
  "contractor": "n8n-contractor",
  "details": {
    "dns_provider": "cloudflare",
    "error": "api_timeout"
  },
  "recovery": {
    "action": "manual_dns_update_required",
    "notify": ["ops-team", "network-team"],
    "instructions": "Update DNS records manually via Cloudflare dashboard",
    "records": [
      "api.cortex.local -> 10.20.1.100",
      "*.apps.cortex.local -> 10.20.1.100"
    ]
  },
  "temporary_solution": {
    "action": "update_local_dns",
    "description": "Update internal DNS server as temporary measure"
  }
}
```

### Rollback Procedure

```bash
#!/bin/bash
# Rollback to primary site (when restored)

WORKFLOW_ID="dr-003"

# Step 1: Verify primary site is healthy
cat > /tmp/verify-primary.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-verify-primary",
  "contractor": "infrastructure-contractor",
  "action": "verify_site_health",
  "site": "datacenter-01",
  "required_checks": ["network", "storage", "compute", "load_balancer"]
}
EOF

# Step 2: Sync data from DR to primary
cat > /tmp/sync-to-primary.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-sync-primary",
  "contractor": "talos-contractor",
  "action": "sync_data_to_primary",
  "source_cluster": "dr-k8s-01",
  "target_cluster": "prod-k8s-01",
  "method": "etcd_snapshot_restore"
}
EOF

# Step 3: Update DNS back to primary
cat > /tmp/dns-to-primary.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-dns-primary",
  "contractor": "n8n-contractor",
  "action": "update_dns_to_primary",
  "records": [
    {"name": "api.cortex.local", "value": "10.10.1.100"},
    {"name": "*.apps.cortex.local", "value": "10.10.1.100"}
  ]
}
EOF

# Step 4: Demote DR cluster
cat > /tmp/demote-dr.json <<EOF
{
  "task_id": "${WORKFLOW_ID}-demote-dr",
  "contractor": "talos-contractor",
  "action": "demote_cluster_to_standby",
  "cluster": "dr-k8s-01"
}
EOF
```

### Success Criteria

- [ ] DR site infrastructure verified healthy
- [ ] Etcd snapshot restored successfully
- [ ] All pods running in DR cluster
- [ ] DNS records updated to DR site
- [ ] Health checks passing
- [ ] Stakeholders notified
- [ ] RTO < 15 minutes
- [ ] RPO < 60 seconds
- [ ] Post-failover monitoring active

---

## 4. Application Deployment Pipeline

**Objective**: Automated end-to-end application deployment from code commit to production.

**Contractors Involved**: n8n-contractor, talos-contractor, infrastructure-contractor

### Step-by-Step Sequence

#### Phase 1: CI/CD Orchestration (n8n-contractor)

```json
{
  "task_id": "deploy-004-cicd",
  "contractor": "n8n-contractor",
  "action": "orchestrate_deployment_pipeline",
  "trigger": {
    "type": "github_webhook",
    "event": "push",
    "branch": "main",
    "repository": "cortex-apps/web-api"
  },
  "parameters": {
    "pipeline_stages": [
      {
        "stage": "build",
        "actions": [
          {
            "type": "clone_repository",
            "repo": "cortex-apps/web-api",
            "branch": "main"
          },
          {
            "type": "run_tests",
            "command": "npm test",
            "coverage_threshold": 80
          },
          {
            "type": "build_docker_image",
            "dockerfile": "Dockerfile",
            "tags": ["latest", "${GIT_SHA}", "v${VERSION}"]
          },
          {
            "type": "scan_image",
            "scanner": "trivy",
            "fail_on": "HIGH,CRITICAL"
          },
          {
            "type": "push_to_registry",
            "registry": "harbor.cortex.local",
            "repository": "cortex-apps/web-api"
          }
        ]
      },
      {
        "stage": "deploy_staging",
        "actions": [
          {
            "type": "handoff_to_talos_contractor",
            "deployment_spec": {
              "cluster": "staging-k8s",
              "namespace": "staging",
              "image": "harbor.cortex.local/cortex-apps/web-api:${GIT_SHA}",
              "replicas": 2
            }
          },
          {
            "type": "wait_for_deployment",
            "timeout": 300
          },
          {
            "type": "run_smoke_tests",
            "endpoint": "https://api.staging.cortex.local/health"
          }
        ]
      },
      {
        "stage": "deploy_production",
        "requires_approval": true,
        "approval_timeout": 3600,
        "actions": [
          {
            "type": "handoff_to_talos_contractor",
            "deployment_spec": {
              "cluster": "prod-k8s-01",
              "namespace": "production",
              "image": "harbor.cortex.local/cortex-apps/web-api:${GIT_SHA}",
              "replicas": 5,
              "strategy": "rolling_update"
            }
          },
          {
            "type": "wait_for_rollout",
            "timeout": 600
          },
          {
            "type": "verify_health",
            "endpoint": "https://api.cortex.local/health",
            "expected_version": "${GIT_SHA}"
          },
          {
            "type": "handoff_to_infrastructure_contractor",
            "action": "update_load_balancer_config",
            "new_backend_version": "${GIT_SHA}"
          }
        ]
      }
    ],
    "on_failure": {
      "rollback": true,
      "notify": ["#deployments", "@on-call"]
    }
  }
}
```

**Output Handoff to Talos**:
```json
{
  "handoff_id": "deploy-004-to-talos-staging",
  "from_contractor": "n8n-contractor",
  "to_contractor": "talos-contractor",
  "task_type": "deploy_application",
  "data": {
    "cluster": "staging-k8s",
    "namespace": "staging",
    "deployment_manifest": {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "web-api",
        "namespace": "staging",
        "labels": {
          "app": "web-api",
          "version": "a1b2c3d"
        }
      },
      "spec": {
        "replicas": 2,
        "selector": {
          "matchLabels": {
            "app": "web-api"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "web-api",
              "version": "a1b2c3d"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "web-api",
                "image": "harbor.cortex.local/cortex-apps/web-api:a1b2c3d",
                "ports": [{"containerPort": 3000}],
                "env": [
                  {"name": "NODE_ENV", "value": "staging"},
                  {"name": "DB_HOST", "valueFrom": {"secretKeyRef": {"name": "db-config", "key": "host"}}}
                ],
                "resources": {
                  "requests": {"cpu": "100m", "memory": "128Mi"},
                  "limits": {"cpu": "500m", "memory": "512Mi"}
                },
                "livenessProbe": {
                  "httpGet": {"path": "/health", "port": 3000},
                  "initialDelaySeconds": 30
                },
                "readinessProbe": {
                  "httpGet": {"path": "/ready", "port": 3000},
                  "initialDelaySeconds": 10
                }
              }
            ]
          }
        }
      }
    },
    "callback_webhook": "https://n8n.cortex.local/webhook/deployment-status"
  }
}
```

#### Phase 2: K8s Deployment (talos-contractor)

```json
{
  "task_id": "deploy-004-k8s",
  "contractor": "talos-contractor",
  "action": "deploy_application",
  "parameters": {
    "cluster": "prod-k8s-01",
    "namespace": "production",
    "deployment_strategy": "rolling_update",
    "manifest": "received_from_n8n",
    "pre_deployment_checks": [
      {
        "type": "verify_namespace_exists",
        "create_if_missing": true
      },
      {
        "type": "verify_secrets_exist",
        "required_secrets": ["db-config", "api-keys"]
      },
      {
        "type": "verify_resource_quotas",
        "required_cpu": "500m",
        "required_memory": "2.5Gi"
      }
    ],
    "deployment_options": {
      "max_surge": 1,
      "max_unavailable": 0,
      "progress_deadline_seconds": 600
    },
    "post_deployment": [
      {
        "type": "wait_for_rollout",
        "timeout": 300
      },
      {
        "type": "verify_pod_health",
        "all_pods_ready": true
      },
      {
        "type": "run_post_deploy_job",
        "job": "database-migrations"
      }
    ]
  }
}
```

**Deployment Execution**:
```bash
# Apply deployment manifest
kubectl --kubeconfig prod-kubeconfig apply -f deployment.yaml

# Wait for rollout
kubectl --kubeconfig prod-kubeconfig rollout status deployment/web-api -n production --timeout=5m

# Verify pods
kubectl --kubeconfig prod-kubeconfig get pods -n production -l app=web-api

# Run migrations
kubectl --kubeconfig prod-kubeconfig create job --from=cronjob/db-migrate migrate-$(date +%s) -n production
```

**Output Handoff Back to n8n**:
```json
{
  "handoff_id": "deploy-004-talos-to-n8n",
  "from_contractor": "talos-contractor",
  "to_contractor": "n8n-contractor",
  "status": "completed",
  "data": {
    "deployment_status": "success",
    "cluster": "prod-k8s-01",
    "namespace": "production",
    "deployment": "web-api",
    "image": "harbor.cortex.local/cortex-apps/web-api:a1b2c3d",
    "replicas": {
      "desired": 5,
      "ready": 5,
      "available": 5
    },
    "rollout_duration": "142s",
    "pod_details": [
      {"name": "web-api-66d4f7b8c9-abc12", "status": "Running", "node": "k8s-worker-01"},
      {"name": "web-api-66d4f7b8c9-def34", "status": "Running", "node": "k8s-worker-02"},
      {"name": "web-api-66d4f7b8c9-ghi56", "status": "Running", "node": "k8s-worker-03"},
      {"name": "web-api-66d4f7b8c9-jkl78", "status": "Running", "node": "k8s-worker-01"},
      {"name": "web-api-66d4f7b8c9-mno90", "status": "Running", "node": "k8s-worker-02"}
    ],
    "requires_lb_update": true
  }
}
```

#### Phase 3: Load Balancer Configuration (infrastructure-contractor)

```json
{
  "task_id": "deploy-004-lb",
  "contractor": "infrastructure-contractor",
  "action": "update_load_balancer",
  "parameters": {
    "load_balancer": "prod-lb-01",
    "backend_pool": "web-api",
    "update_type": "add_backend_version",
    "backend_config": {
      "version": "a1b2c3d",
      "servers": [
        {"ip": "10.10.1.20", "port": 30080, "weight": 100},
        {"ip": "10.10.1.21", "port": 30080, "weight": 100},
        {"ip": "10.10.1.22", "port": 30080, "weight": 100}
      ],
      "health_check": {
        "path": "/health",
        "interval": 5,
        "timeout": 3,
        "rise": 2,
        "fall": 3
      }
    },
    "traffic_shift": {
      "strategy": "gradual",
      "phases": [
        {"duration": 300, "new_version_weight": 10},
        {"duration": 300, "new_version_weight": 50},
        {"duration": 300, "new_version_weight": 100}
      ]
    }
  }
}
```

**HAProxy Configuration Update**:
```bash
# Generate new backend config
cat >> /etc/haproxy/haproxy.cfg <<EOF
backend web-api-a1b2c3d
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200
    server worker-01 10.10.1.20:30080 check weight 100
    server worker-02 10.10.1.21:30080 check weight 100
    server worker-03 10.10.1.22:30080 check weight 100
EOF

# Reload HAProxy
haproxy -c -f /etc/haproxy/haproxy.cfg && systemctl reload haproxy
```

**Output Handoff Back to n8n**:
```json
{
  "handoff_id": "deploy-004-infra-to-n8n",
  "from_contractor": "infrastructure-contractor",
  "to_contractor": "n8n-contractor",
  "status": "completed",
  "data": {
    "load_balancer_updated": true,
    "backend_pool": "web-api-a1b2c3d",
    "active_servers": 3,
    "health_checks_passing": 3,
    "traffic_shift_complete": true,
    "old_version_removed": false,
    "metrics": {
      "requests_per_second": 245,
      "avg_response_time_ms": 42,
      "error_rate": 0.001
    }
  }
}
```

#### Phase 4: Post-Deployment Verification (n8n-contractor)

```json
{
  "task_id": "deploy-004-verify",
  "contractor": "n8n-contractor",
  "action": "post_deployment_verification",
  "parameters": {
    "checks": [
      {
        "type": "health_check",
        "url": "https://api.cortex.local/health",
        "expected": {"status": 200, "version": "a1b2c3d"}
      },
      {
        "type": "smoke_tests",
        "test_suite": "production-smoke-tests",
        "tests": [
          {"name": "authentication", "endpoint": "/auth/login"},
          {"name": "database_connection", "endpoint": "/db/ping"},
          {"name": "cache_access", "endpoint": "/cache/ping"}
        ]
      },
      {
        "type": "performance_test",
        "duration": 300,
        "expected_rps": 200,
        "max_p95_latency": 100
      },
      {
        "type": "error_rate_check",
        "duration": 300,
        "max_error_rate": 0.01
      }
    ],
    "monitoring_period": 1800,
    "rollback_on_failure": true,
    "notifications": [
      {
        "channel": "slack",
        "recipients": ["#deployments"],
        "message": "Deployment complete: web-api:a1b2c3d to production"
      },
      {
        "channel": "github",
        "action": "comment_on_commit",
        "commit": "a1b2c3d",
        "comment": "Deployed to production successfully"
      }
    ]
  }
}
```

### Data Flow Diagram

```
GitHub Push → main
    |
    v
n8n-contractor (build, test, scan)
    |
    | Docker image: web-api:a1b2c3d
    v
n8n-contractor → talos-contractor
    |
    | Deploy to staging
    v
talos-contractor (K8s deployment)
    |
    | Staging OK
    v
Manual Approval
    |
    v
n8n-contractor → talos-contractor
    |
    | Deploy to production
    v
talos-contractor (K8s deployment)
    |
    | Pods running
    v
talos-contractor → infrastructure-contractor
    |
    | Update load balancer
    v
infrastructure-contractor (LB config)
    |
    | Traffic shifted
    v
n8n-contractor (verification)
    |
    | All checks pass
    v
DEPLOYMENT COMPLETE
```

### Error Handling

**Build Failure**:
```json
{
  "error": "docker_build_failed",
  "contractor": "n8n-contractor",
  "stage": "build",
  "details": {
    "step": "npm install",
    "error_message": "ENOTFOUND registry.npmjs.org"
  },
  "recovery": {
    "action": "retry_with_fallback_registry",
    "fallback_registry": "npm.cortex.local",
    "retry_count": 3
  },
  "notify": ["#deployments"]
}
```

**Deployment Timeout**:
```json
{
  "error": "deployment_timeout",
  "contractor": "talos-contractor",
  "details": {
    "deployment": "web-api",
    "namespace": "production",
    "timeout_after": "600s",
    "current_status": {
      "desired": 5,
      "ready": 2,
      "available": 2
    }
  },
  "recovery": {
    "action": "rollback_deployment",
    "rollback_to": "previous_revision",
    "notify_n8n": true
  }
}
```

**Health Check Failure**:
```json
{
  "error": "health_check_failed",
  "contractor": "n8n-contractor",
  "details": {
    "url": "https://api.cortex.local/health",
    "status_code": 503,
    "error": "database connection timeout"
  },
  "recovery": {
    "action": "initiate_rollback",
    "trigger_contractors": ["talos-contractor", "infrastructure-contractor"],
    "rollback_sequence": [
      "shift_traffic_to_old_version",
      "scale_down_new_version",
      "investigate_database_issue"
    ]
  }
}
```

### Rollback Procedure

```bash
#!/bin/bash
# Automated rollback procedure

DEPLOYMENT="web-api"
NAMESPACE="production"
PREVIOUS_VERSION="x9y8z7w"

# Step 1: n8n triggers rollback
cat > /tmp/rollback-trigger.json <<EOF
{
  "task_id": "deploy-004-rollback",
  "contractor": "n8n-contractor",
  "action": "initiate_rollback",
  "deployment": "${DEPLOYMENT}",
  "namespace": "${NAMESPACE}",
  "rollback_to": "${PREVIOUS_VERSION}"
}
EOF

# Step 2: infrastructure-contractor shifts traffic back
cat > /tmp/rollback-lb.json <<EOF
{
  "task_id": "deploy-004-rollback-lb",
  "contractor": "infrastructure-contractor",
  "action": "shift_traffic_to_version",
  "backend_pool": "web-api",
  "target_version": "${PREVIOUS_VERSION}",
  "immediate": true
}
EOF

# Step 3: talos-contractor rolls back K8s deployment
cat > /tmp/rollback-k8s.json <<EOF
{
  "task_id": "deploy-004-rollback-k8s",
  "contractor": "talos-contractor",
  "action": "rollback_deployment",
  "deployment": "${DEPLOYMENT}",
  "namespace": "${NAMESPACE}",
  "revision": "previous"
}
EOF

# Step 4: n8n verifies rollback success
cat > /tmp/rollback-verify.json <<EOF
{
  "task_id": "deploy-004-rollback-verify",
  "contractor": "n8n-contractor",
  "action": "verify_rollback",
  "checks": [
    {"type": "health_check", "url": "https://api.cortex.local/health"},
    {"type": "version_check", "expected": "${PREVIOUS_VERSION}"},
    {"type": "error_rate", "max": 0.01}
  ],
  "notify": ["#deployments", "@oncall"]
}
EOF
```

### Success Criteria

- [ ] Code pushed to main branch
- [ ] Tests pass (coverage > 80%)
- [ ] Docker image built and scanned
- [ ] Deployed to staging successfully
- [ ] Smoke tests pass in staging
- [ ] Manual approval received
- [ ] Deployed to production successfully
- [ ] All 5 replicas ready
- [ ] Load balancer updated
- [ ] Traffic shifted to new version
- [ ] Health checks passing
- [ ] Performance metrics acceptable
- [ ] Notifications sent

---

## 5. Security Incident Response

**Objective**: Coordinate rapid response to security incident across all infrastructure layers.

**Contractors Involved**: All contractors (infrastructure, talos, n8n) + Security Master

**Incident Scenario**: Suspected compromise of a worker node in production K8s cluster.

### Step-by-Step Sequence

#### Phase 1: Detection and Initial Response (n8n-contractor)

```json
{
  "task_id": "sec-005-detect",
  "contractor": "n8n-contractor",
  "trigger": {
    "type": "security_alert",
    "source": "falco",
    "severity": "critical",
    "alert": "Unauthorized process execution on k8s-worker-02"
  },
  "immediate_actions": [
    {
      "action": "create_incident_record",
      "incident_id": "SEC-2025-12-09-001",
      "severity": "critical",
      "affected_systems": ["prod-k8s-01", "k8s-worker-02"]
    },
    {
      "action": "notify_security_team",
      "channels": ["pagerduty", "slack-security", "email"],
      "escalation_level": "critical"
    },
    {
      "action": "trigger_containment_workflow",
      "workflow": "security-incident-containment"
    },
    {
      "action": "enable_enhanced_logging",
      "targets": ["k8s-worker-02", "surrounding_nodes"]
    }
  ],
  "coordinate_with": ["infrastructure-contractor", "talos-contractor", "security-master"]
}
```

**Incident Record**:
```json
{
  "incident_id": "SEC-2025-12-09-001",
  "timestamp": "2025-12-09T14:32:15Z",
  "severity": "critical",
  "status": "active",
  "affected_systems": [
    {
      "type": "kubernetes_node",
      "identifier": "k8s-worker-02",
      "ip": "10.10.1.21",
      "cluster": "prod-k8s-01"
    }
  ],
  "initial_indicators": {
    "source": "falco",
    "rule_triggered": "Unauthorized Process Execution",
    "process": "/tmp/suspicious_binary",
    "user": "nobody",
    "timestamp": "2025-12-09T14:31:42Z"
  },
  "response_team": [
    "security-master",
    "infrastructure-contractor",
    "talos-contractor",
    "n8n-contractor"
  ]
}
```

#### Phase 2: Isolation (talos-contractor + infrastructure-contractor)

**Talos Contractor - K8s Level Isolation**:
```json
{
  "task_id": "sec-005-isolate-k8s",
  "contractor": "talos-contractor",
  "action": "isolate_compromised_node",
  "parameters": {
    "node": "k8s-worker-02",
    "cluster": "prod-k8s-01",
    "isolation_steps": [
      {
        "action": "cordon_node",
        "command": "kubectl cordon k8s-worker-02",
        "description": "Prevent new pods from being scheduled"
      },
      {
        "action": "apply_network_policy",
        "policy": {
          "apiVersion": "networking.k8s.io/v1",
          "kind": "NetworkPolicy",
          "metadata": {
            "name": "isolate-worker-02",
            "namespace": "kube-system"
          },
          "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [],
            "egress": [
              {
                "to": [{"podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}],
                "ports": [{"port": 53, "protocol": "UDP"}]
              }
            ]
          }
        }
      },
      {
        "action": "drain_node_safely",
        "command": "kubectl drain k8s-worker-02 --ignore-daemonsets --delete-emptydir-data",
        "preserve_forensics": true
      }
    ],
    "preserve_state": {
      "take_memory_dump": false,
      "snapshot_disk": true,
      "capture_logs": true
    }
  }
}
```

**Infrastructure Contractor - Network Level Isolation**:
```json
{
  "task_id": "sec-005-isolate-network",
  "contractor": "infrastructure-contractor",
  "action": "isolate_at_network_layer",
  "parameters": {
    "target_vm": "k8s-worker-02",
    "ip": "10.10.1.21",
    "isolation_method": "firewall_rules",
    "firewall_config": {
      "default_policy": "deny_all",
      "allowed_connections": [
        {
          "description": "SSH from bastion for forensics",
          "source": "10.10.1.250/32",
          "destination": "10.10.1.21",
          "port": 22,
          "protocol": "tcp"
        },
        {
          "description": "Monitoring/logging",
          "source": "10.10.1.21",
          "destination": "10.20.1.10",
          "port": 9090,
          "protocol": "tcp",
          "purpose": "prometheus"
        }
      ],
      "blocked_connections": [
        {
          "description": "Block all outbound internet",
          "source": "10.10.1.21",
          "destination": "0.0.0.0/0",
          "action": "deny"
        },
        {
          "description": "Block lateral movement",
          "source": "10.10.1.21",
          "destination": "10.10.1.0/24",
          "action": "deny",
          "except": ["10.10.1.250"]
        }
      ]
    },
    "capture_traffic": {
      "enabled": true,
      "duration": 3600,
      "pcap_location": "/var/forensics/incident-SEC-2025-12-09-001/"
    }
  }
}
```

#### Phase 3: Investigation (All Contractors)

**Talos Contractor - K8s Forensics**:
```json
{
  "task_id": "sec-005-investigate-k8s",
  "contractor": "talos-contractor",
  "action": "gather_forensic_data",
  "parameters": {
    "node": "k8s-worker-02",
    "data_collection": [
      {
        "type": "running_processes",
        "command": "talosctl --nodes 10.10.1.21 ps",
        "output": "/var/forensics/incident-SEC-2025-12-09-001/processes.txt"
      },
      {
        "type": "network_connections",
        "command": "talosctl --nodes 10.10.1.21 netstat",
        "output": "/var/forensics/incident-SEC-2025-12-09-001/netstat.txt"
      },
      {
        "type": "system_logs",
        "command": "talosctl --nodes 10.10.1.21 logs",
        "output": "/var/forensics/incident-SEC-2025-12-09-001/system-logs.txt"
      },
      {
        "type": "container_logs",
        "namespaces": ["all"],
        "command": "kubectl logs --all-containers --previous",
        "output": "/var/forensics/incident-SEC-2025-12-09-001/container-logs/"
      },
      {
        "type": "etcd_snapshot",
        "preserve_cluster_state": true,
        "output": "/var/forensics/incident-SEC-2025-12-09-001/etcd-snapshot.db"
      }
    ],
    "pod_analysis": {
      "get_pod_list": "kubectl get pods --all-namespaces -o json --field-selector spec.nodeName=k8s-worker-02",
      "analyze_images": true,
      "check_for_privilege_escalation": true
    }
  }
}
```

**Infrastructure Contractor - System Forensics**:
```json
{
  "task_id": "sec-005-investigate-infra",
  "contractor": "infrastructure-contractor",
  "action": "perform_system_forensics",
  "parameters": {
    "vm": "k8s-worker-02",
    "forensic_actions": [
      {
        "action": "create_disk_snapshot",
        "preserve_original": true,
        "snapshot_name": "k8s-worker-02-incident-snapshot",
        "location": "forensics-pool"
      },
      {
        "action": "collect_system_artifacts",
        "artifacts": [
          "/var/log/",
          "/tmp/",
          "/root/.bash_history",
          "/home/*/.bash_history",
          "/etc/cron*",
          "/etc/systemd/"
        ]
      },
      {
        "action": "check_persistence_mechanisms",
        "locations": [
          "cron jobs",
          "systemd units",
          "rc.local",
          "ssh authorized_keys"
        ]
      },
      {
        "action": "analyze_suspicious_files",
        "file": "/tmp/suspicious_binary",
        "analyses": [
          "file_hash",
          "virus_total_lookup",
          "strings_extraction",
          "static_analysis"
        ]
      }
    ],
    "network_forensics": {
      "analyze_pcap": "/var/forensics/incident-SEC-2025-12-09-001/traffic.pcap",
      "look_for": [
        "c2_communication",
        "data_exfiltration",
        "lateral_movement_attempts"
      ]
    }
  }
}
```

**n8n Contractor - Log Analysis and Correlation**:
```json
{
  "task_id": "sec-005-investigate-logs",
  "contractor": "n8n-contractor",
  "action": "correlate_security_events",
  "parameters": {
    "time_range": {
      "start": "2025-12-09T14:00:00Z",
      "end": "2025-12-09T15:00:00Z"
    },
    "data_sources": [
      {
        "source": "prometheus",
        "query": "node_metrics{node='k8s-worker-02'}",
        "look_for": "anomalies in CPU, network, disk I/O"
      },
      {
        "source": "loki",
        "query": "{node='k8s-worker-02'}",
        "look_for": "authentication failures, privilege escalation"
      },
      {
        "source": "falco",
        "query": "alerts for k8s-worker-02",
        "look_for": "suspicious syscalls, file access"
      },
      {
        "source": "audit_logs",
        "query": "kubectl audit logs for node k8s-worker-02",
        "look_for": "unauthorized API calls"
      }
    ],
    "correlation": {
      "build_timeline": true,
      "identify_initial_compromise": true,
      "map_attacker_actions": true,
      "determine_scope": true
    }
  }
}
```

#### Phase 4: Remediation (All Contractors)

**Remediation Plan**:
```json
{
  "incident_id": "SEC-2025-12-09-001",
  "remediation_plan": {
    "findings": {
      "attack_vector": "compromised container with privileged mode",
      "initial_access": "vulnerable web application",
      "persistence": "malicious binary in /tmp",
      "scope": "single node, no lateral movement detected"
    },
    "remediation_steps": [
      {
        "step": 1,
        "contractor": "talos-contractor",
        "action": "remove_compromised_node",
        "details": {
          "delete_node": "k8s-worker-02",
          "remove_from_cluster": true
        }
      },
      {
        "step": 2,
        "contractor": "infrastructure-contractor",
        "action": "destroy_compromised_vm",
        "details": {
          "vm": "k8s-worker-02",
          "preserve_forensic_copy": true,
          "secure_wipe": true
        }
      },
      {
        "step": 3,
        "contractor": "infrastructure-contractor",
        "action": "provision_replacement_node",
        "details": {
          "name": "k8s-worker-02-new",
          "specs": "match original",
          "hardened_image": true
        }
      },
      {
        "step": 4,
        "contractor": "talos-contractor",
        "action": "join_new_node_to_cluster",
        "details": {
          "apply_security_patches": true,
          "restrict_privileged_containers": true
        }
      },
      {
        "step": 5,
        "contractor": "talos-contractor",
        "action": "patch_vulnerable_application",
        "details": {
          "application": "web-app",
          "vulnerability": "CVE-2025-XXXXX",
          "patch_version": "v2.1.5"
        }
      },
      {
        "step": 6,
        "contractor": "talos-contractor",
        "action": "implement_pod_security_standards",
        "details": {
          "enforce": "restricted",
          "disable_privileged_mode": true,
          "namespace": "production"
        }
      },
      {
        "step": 7,
        "contractor": "n8n-contractor",
        "action": "enhance_monitoring",
        "details": {
          "add_falco_rules": ["detect suspicious binary execution"],
          "add_prometheus_alerts": ["unusual network activity"],
          "implement_runtime_scanning": true
        }
      }
    ]
  }
}
```

**Talos Contractor Remediation**:
```bash
# Remove compromised node
kubectl delete node k8s-worker-02

# Apply pod security standards
kubectl label namespace production pod-security.kubernetes.io/enforce=restricted

# Update deployment to disable privileged mode
kubectl patch deployment web-app -n production --patch '
spec:
  template:
    spec:
      containers:
      - name: web-app
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
          runAsNonRoot: true
          seccompProfile:
            type: RuntimeDefault
'

# Join new hardened node
talosctl apply-config --nodes 10.10.1.21 --file hardened-worker.yaml
```

**Infrastructure Contractor Remediation**:
```bash
# Destroy compromised VM (after forensics complete)
qm destroy 121 --purge

# Create new VM with hardened base image
qm create 121 \
  --name k8s-worker-02-new \
  --memory 16384 \
  --cores 8 \
  --net0 virtio,bridge=vmbr0,tag=10 \
  --scsi0 ceph-storage:100,format=raw,discard=on

# Deploy hardened Talos image
qm importdisk 121 talos-hardened-v1.6.1.img ceph-storage
qm set 121 --boot order=scsi0
```

**n8n Contractor - Enhanced Monitoring**:
```json
{
  "task_id": "sec-005-enhance-monitoring",
  "contractor": "n8n-contractor",
  "action": "implement_enhanced_security_monitoring",
  "parameters": {
    "new_falco_rules": [
      {
        "rule": "Suspicious Binary Execution from Temp",
        "condition": "spawned_process and proc.name in (suspicious_binaries) and fd.directory in (/tmp, /var/tmp)",
        "output": "Suspicious binary executed from temp directory",
        "priority": "critical"
      }
    ],
    "new_prometheus_alerts": [
      {
        "alert": "UnusualNetworkActivity",
        "expr": "rate(node_network_transmit_bytes_total[5m]) > 100000000",
        "for": "5m",
        "severity": "warning"
      }
    ],
    "runtime_scanning": {
      "tool": "trivy",
      "scan_frequency": "hourly",
      "scan_running_containers": true,
      "alert_on": ["HIGH", "CRITICAL"]
    },
    "automated_response": {
      "on_critical_alert": [
        "isolate_affected_pod",
        "capture_forensics",
        "notify_security_team"
      ]
    }
  }
}
```

#### Phase 5: Post-Incident Review (n8n-contractor)

```json
{
  "task_id": "sec-005-post-incident",
  "contractor": "n8n-contractor",
  "action": "conduct_post_incident_review",
  "parameters": {
    "generate_report": {
      "incident_id": "SEC-2025-12-09-001",
      "sections": [
        "timeline_of_events",
        "attack_vector_analysis",
        "scope_of_compromise",
        "response_effectiveness",
        "lessons_learned",
        "recommendations"
      ],
      "distribute_to": ["security-team", "management", "all-contractors"]
    },
    "update_runbooks": {
      "runbook": "security-incident-response",
      "updates": [
        "add faster node isolation procedure",
        "improve forensics collection automation",
        "enhance privilege escalation detection"
      ]
    },
    "implement_preventive_measures": [
      {
        "measure": "mandatory_pod_security_standards",
        "enforce_in": ["production", "staging"]
      },
      {
        "measure": "regular_vulnerability_scanning",
        "frequency": "daily"
      },
      {
        "measure": "security_training",
        "target": "development_team",
        "topic": "secure_container_practices"
      }
    ]
  }
}
```

### Data Flow Diagram

```
Security Alert (Falco)
    |
    v
n8n-contractor (detect, create incident)
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
talos-contractor  infrastructure-   security-master
(K8s isolation)   contractor         (coordinate)
                  (network isolation)
    |                  |                  |
    +------------------+------------------+
    |
    v
ALL CONTRACTORS (investigation)
    |
    | Forensic data collected
    v
n8n-contractor (correlate, analyze)
    |
    | Attack vector identified
    v
ALL CONTRACTORS (remediation)
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
talos-contractor  infrastructure-   n8n-contractor
(patch app,       contractor         (enhanced
 harden K8s)      (replace node)     monitoring)
    |                  |                  |
    +------------------+------------------+
    |
    v
n8n-contractor (post-incident review)
    |
    v
INCIDENT RESOLVED - PREVENTIVE MEASURES IMPLEMENTED
```

### Success Criteria

- [ ] Incident detected within 5 minutes
- [ ] Compromised node isolated within 10 minutes
- [ ] Forensic data captured before remediation
- [ ] No lateral movement to other nodes
- [ ] No data exfiltration detected
- [ ] Vulnerable application patched
- [ ] Replacement node deployed with hardening
- [ ] Enhanced monitoring implemented
- [ ] Post-incident report completed
- [ ] Preventive measures deployed cluster-wide
- [ ] Security team trained on new procedures

---

## Cross-Workflow Patterns

### Common Data Structures

**Contractor Handoff Format**:
```json
{
  "handoff_id": "unique-id",
  "from_contractor": "source-contractor",
  "to_contractor": "target-contractor",
  "task_id": "parent-task-id",
  "handoff_type": "type-of-handoff",
  "priority": "low|normal|high|critical",
  "deadline": "ISO8601 timestamp",
  "status": "pending|in_progress|completed|failed",
  "data": {
    "key": "value"
  },
  "callback_webhook": "https://n8n.cortex.local/webhook/callback",
  "created_at": "ISO8601 timestamp",
  "completed_at": "ISO8601 timestamp"
}
```

**Error Response Format**:
```json
{
  "error": "error_code",
  "contractor": "contractor-name",
  "task_id": "task-id",
  "timestamp": "ISO8601 timestamp",
  "details": {
    "message": "human readable error",
    "context": {}
  },
  "recovery": {
    "action": "recovery_action",
    "automated": true|false,
    "handoff_to": "contractor-name",
    "request": {}
  },
  "severity": "low|medium|high|critical"
}
```

### Coordination Best Practices

1. **Always Use Handoffs**: Never directly invoke another contractor's actions. Use the handoff mechanism.

2. **Preserve Forensic Data**: Before any destructive action, capture state and logs.

3. **Implement Timeouts**: Every cross-contractor call should have a timeout and fallback.

4. **Use Callbacks**: Async operations should use webhooks for status updates.

5. **Centralize Logging**: n8n-contractor should aggregate all workflow events.

6. **Rollback Support**: Every workflow should have a documented rollback procedure.

7. **Health Checks**: Verify target contractor availability before handoff.

8. **Idempotency**: All contractor actions should be idempotent to support retries.

---

## Workflow Metrics

Track these metrics for each workflow:

- **Total Duration**: End-to-end workflow time
- **Contractor Handoff Time**: Time spent passing between contractors
- **Error Rate**: Failed handoffs / total handoffs
- **Rollback Frequency**: How often rollbacks are triggered
- **Mean Time to Recovery**: Average time to recover from failures
- **Resource Utilization**: CPU/memory/network during workflow execution

Store metrics in: `/Users/ryandahlberg/Projects/cortex/coordination/workflows/metrics/`
