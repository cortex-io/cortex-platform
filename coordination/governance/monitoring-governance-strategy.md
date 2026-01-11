# Cortex Monitoring Governance Strategy

## Executive Summary

This document defines the monitoring governance strategy for Cortex, synthesizing industry best practices from Datadog and Splunk guides with Cortex's existing infrastructure. The goal is to establish a comprehensive observability framework that ensures optimal Kubernetes performance, proactive troubleshooting, and full-stack visibility.

---

## Current State Analysis

### Existing Infrastructure
- **Monitoring Stack**: kube-prometheus-stack (Prometheus, Grafana, Alertmanager)
- **Deployment Status**: Manifests ready, pending cluster accessibility
- **Integration**: N8N webhook configured for alert routing
- **Custom Alerts**: 4 Cortex-specific rules defined

### Governance Health (as of last check)
- Health Score: 93.9%
- Compliance Rate: 87.5%
- Security Incidents: 0
- System Availability: 99.95%

---

## Recommended Metrics Framework

### Category 1: Cluster State Metrics

| Priority | Metric | Source | Purpose | Alert Threshold |
|----------|--------|--------|---------|-----------------|
| P0 | Node Status | kube-state-metrics | Node health/availability | Ready=false for >2m |
| P0 | Desired vs Current Pods | kube-state-metrics | Deployment health | Mismatch >10% for >5m |
| P1 | Available/Unavailable Pods | kube-state-metrics | Service availability | Unavailable >5% |
| P1 | Pod Phase Distribution | kube-state-metrics | Workload status | Pending >10 for >5m |

**Recommended Additions to Cortex**:
```yaml
# Add to prometheus-values.yaml additionalPrometheusRulesMap
- alert: CortexNodeNotReady
  expr: kube_node_status_condition{condition="Ready",status="true"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Node {{ $labels.node }} not ready"

- alert: CortexDeploymentReplicaMismatch
  expr: |
    kube_deployment_status_replicas_available
    / kube_deployment_spec_replicas < 0.9
  for: 5m
  labels:
    severity: warning
```

### Category 2: Resource Metrics

| Priority | Metric | Current Status | Gap |
|----------|--------|----------------|-----|
| P0 | Memory Limits vs Utilization | Partial | Need per-pod limits tracking |
| P0 | CPU Limits vs Utilization | Partial | Need throttling detection |
| P0 | Disk Utilization | Not tracked | Add volume monitoring |
| P1 | Memory Requests vs Allocatable | Not tracked | Capacity planning |
| P1 | CPU Requests vs Allocatable | Not tracked | Capacity planning |

**Recommended Additions**:
```yaml
# Resource capacity alerts
- alert: CortexNodeMemoryPressure
  expr: |
    sum(container_memory_usage_bytes{namespace="cortex"}) by (node)
    / sum(kube_node_status_allocatable{resource="memory"}) by (node) > 0.85
  for: 10m
  labels:
    severity: warning

- alert: CortexPVCNearCapacity
  expr: |
    kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes > 0.8
  for: 5m
  labels:
    severity: warning
```

### Category 3: Control Plane Metrics

| Priority | Metric | Source | Current Status |
|----------|--------|--------|----------------|
| P0 | etcd Leader Status | etcd | Not tracked |
| P0 | etcd Leader Changes | etcd | Not tracked |
| P1 | API Server Request Latency | apiserver | Default rules enabled |
| P1 | Controller Manager Latency | kube-controller-manager | Default rules enabled |
| P1 | Scheduler Attempts/Latency | kube-scheduler | Default rules enabled |

**Note**: Talos-specific - control plane access may be limited.

### Category 4: Cortex-Specific Metrics (Custom)

#### Agent Hierarchy Metrics

| Component | Metric | Purpose |
|-----------|--------|---------|
| Meta-Agent | `cortex_meta_agent_up` | Core availability |
| Master Agents | `cortex_master_task_queue_length` | Workload distribution |
| Workers | `cortex_worker_task_failures_total` | Task reliability |
| Contractors | `contractor_requests_total` | External integration |
| MCP Servers | `mcp_request_duration_seconds` | Tool latency |

#### Token Management Metrics

| Metric | Alert Condition | Severity |
|--------|-----------------|----------|
| `cortex_tokens_remaining` | <10% budget | critical |
| `cortex_tokens_consumed_total` | >1000/sec | warning |
| `cortex_worker_tokens_allocated` | Efficiency <50% | info |

---

## Troubleshooting Framework

Based on Splunk's 6-step methodology, adapted for Cortex:

### Step 1: Identify Problem Scope

**Cortex Layer Model**:
```
┌─────────────────────────────────────────┐
│           Application Layer              │
│  (N8N Workflows, Custom Apps, API)      │
├─────────────────────────────────────────┤
│          Cortex Agent Layer              │
│  (Meta-Agent → Masters → Workers)       │
├─────────────────────────────────────────┤
│          MCP Server Layer                │
│  (Tool Providers, Integrations)         │
├─────────────────────────────────────────┤
│         Kubernetes Layer                 │
│  (Pods, Services, Ingress)              │
├─────────────────────────────────────────┤
│          Infrastructure Layer            │
│  (Talos Nodes, Storage, Network)        │
└─────────────────────────────────────────┘
```

**Diagnostic Flow**:
1. Check infrastructure (nodes, network, storage)
2. Verify Kubernetes objects (pods, services)
3. Inspect MCP server health
4. Review agent cascade (meta → master → worker)
5. Analyze application logs

### Step 2: Proactive Resource Allocation

**Capacity Planning Dashboards**:
- Node resource utilization trends
- Pod resource request vs actual usage
- Storage growth projections
- Token consumption patterns

**Recommended Grafana Panels**:
```json
{
  "panels": [
    {
      "title": "Memory Utilization Trend",
      "type": "timeseries",
      "targets": [{
        "expr": "sum(container_memory_usage_bytes{namespace='cortex'}) by (pod)",
        "legendFormat": "{{pod}}"
      }]
    },
    {
      "title": "CPU Throttling",
      "type": "stat",
      "targets": [{
        "expr": "rate(container_cpu_cfs_throttled_seconds_total{namespace='cortex'}[5m])"
      }]
    }
  ]
}
```

### Step 3: Anomaly Detection

**Key Signals**:
- Sudden spike in pod restarts
- Unexpected latency increases
- Token consumption anomalies
- Error rate deviations

**Recording Rules for Baselines**:
```yaml
groups:
  - name: cortex_baselines
    rules:
      - record: cortex:task_completion_rate:5m
        expr: rate(cortex_task_completions_total[5m])
      - record: cortex:error_rate:5m
        expr: rate(cortex_requests_total{status="error"}[5m])
      - record: cortex:avg_task_duration:5m
        expr: avg(cortex_task_duration_seconds) by (task_type)
```

### Step 4: AI-Driven Insights

**Integration Points**:
- Grafana ML-powered anomaly detection
- Prometheus alerting with prediction rules
- N8N workflow for automated response

**Predictive Alerts**:
```yaml
- alert: CortexPredictedTokenExhaustion
  expr: |
    predict_linear(cortex_tokens_remaining[1h], 3600) < 0
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "Token budget predicted to exhaust within 1 hour"
```

### Step 5: Configuration & Dependency Validation

**Dependency Health Checks**:
- Database connectivity
- External API availability
- MCP server responsiveness
- N8N webhook endpoint

**Configuration Drift Detection**:
```yaml
- alert: CortexConfigDrift
  expr: cortex_config_hash != cortex_config_expected_hash
  for: 1m
  labels:
    severity: info
```

### Step 6: OpenTelemetry Integration

**Recommended OTel Setup**:
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

---

## Alert Routing & Escalation

### Current Configuration
- Alertmanager → N8N webhook
- Routes: critical/warning → n8n-webhook
- Watchdog alerts → null (silenced)

### Recommended Escalation Matrix

| Severity | Response Time | Notification | Escalation |
|----------|---------------|--------------|------------|
| critical | 5 min | Immediate (all channels) | Auto-escalate after 15m |
| warning | 30 min | Team channel | Review in daily standup |
| info | 4 hours | Dashboard only | Weekly review |

### Alert Grouping Strategy
```yaml
route:
  group_by: ['alertname', 'cluster', 'service', 'component']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
```

---

## Dashboards Strategy

### Tier 1: Executive Overview
- System health score
- Availability metrics
- Cost/token utilization
- Compliance status

### Tier 2: Operational
- Cluster state summary
- Resource utilization
- Alert summary
- Task throughput

### Tier 3: Debugging
- Pod-level metrics
- Log aggregation
- Trace correlation
- Network flows

### Tier 4: Component-Specific
- Meta-agent dashboard
- Master agent dashboards (per type)
- Worker pool dashboard
- MCP server dashboard

---

## Implementation Roadmap

### Phase 1: Foundation (Immediate)
- [ ] Deploy kube-prometheus-stack to Talos cluster
- [ ] Verify default rules operational
- [ ] Test Alertmanager → N8N integration
- [ ] Import baseline Grafana dashboards

### Phase 2: Custom Metrics (Week 1-2)
- [ ] Instrument Cortex agents with Prometheus metrics
- [ ] Add custom alert rules from this document
- [ ] Create recording rules for baselines
- [ ] Build Tier 1 & 2 dashboards

### Phase 3: Advanced Observability (Week 3-4)
- [ ] Implement OpenTelemetry collector
- [ ] Enable distributed tracing
- [ ] Set up log aggregation
- [ ] Configure anomaly detection

### Phase 4: Automation (Week 5-6)
- [ ] Build N8N alert handling workflows
- [ ] Implement auto-remediation playbooks
- [ ] Create runbook automation
- [ ] Establish on-call rotation

---

## Governance Controls

### Monitoring SLOs

| Service | Availability | Latency (p99) | Error Rate |
|---------|--------------|---------------|------------|
| Meta-Agent | 99.9% | 5s | <1% |
| Master Agents | 99.5% | 10s | <2% |
| Workers | 99% | 30s | <5% |
| MCP Servers | 99.5% | 2s | <1% |

### Audit Requirements
- All alerts logged to audit trail
- Configuration changes tracked
- Access to dashboards authenticated
- Retention: 30 days metrics, 90 days logs

### Compliance Mapping

| Framework | Monitoring Requirement | Implementation |
|-----------|------------------------|----------------|
| SOC 2 | Audit logging | Alertmanager → audit trail |
| GDPR | Data retention | Prometheus retention config |
| Internal | Change tracking | GitOps + config drift alerts |

---

## Key Metrics Summary (Top 15 for Cortex)

### Cluster State (3)
1. Node status (Ready condition)
2. Desired vs current pods
3. Available vs unavailable pods

### Resource (5)
4. Memory limits vs utilization
5. Memory requests vs allocatable
6. CPU limits vs utilization
7. CPU requests vs allocatable
8. Disk/PVC utilization

### Control Plane (3)
9. etcd leader status
10. API server latency
11. Scheduler attempts/latency

### Cortex-Specific (4)
12. Agent availability (meta/master/worker)
13. Task completion rate
14. Token consumption rate
15. MCP server latency

---

## Next Steps

1. **Review this document** with stakeholders
2. **Prioritize metrics** based on current pain points
3. **Validate alert thresholds** against baseline data
4. **Schedule implementation** according to roadmap
5. **Establish monitoring governance committee** for ongoing oversight

---

## References

- Datadog: "15 Metrics Every DevOps Team Should Track"
- Splunk: "6 Key Steps for Kubernetes Troubleshooting"
- Cortex Phase 2 Deployment: `/deploy/monitoring/PHASE2-DEPLOYMENT.md`
- Current Alert Rules: `/deploy/monitoring/prometheus/alerting-rules.yaml`
- Governance Test Suite: `/testing/governance/README.md`

---

*Document Version: 1.0*
*Created: 2025-12-11*
*Status: Draft for Review*
