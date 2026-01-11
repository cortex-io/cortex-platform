# Cortex Workflows

This directory contains workflow documentation and examples for orchestrating complex operations across multiple contractors in the Cortex automation system.

## Overview

Cortex workflows enable coordination between specialized contractors to accomplish complex infrastructure and operational tasks. Each workflow involves multiple contractors working together through a structured handoff mechanism.

## Directory Structure

```
workflows/
├── README.md                           # This file
├── cross-contractor-examples.md        # Complete workflow examples
├── templates/                          # Workflow templates
│   ├── deployment-workflow.json
│   ├── maintenance-workflow.json
│   └── incident-response-workflow.json
├── metrics/                            # Workflow execution metrics
│   ├── workflow-stats.json
│   └── contractor-performance.json
└── active/                             # Currently executing workflows
    └── .gitkeep
```

## Workflow Concepts

### Contractors

Cortex uses three primary contractors:

1. **infrastructure-contractor**: Manages physical/virtual infrastructure (Proxmox VMs, storage, networking, load balancers)
2. **talos-contractor**: Manages Kubernetes clusters (Talos Linux, K8s operations, Helm deployments)
3. **n8n-contractor**: Orchestrates workflows, automation, monitoring, and integrations

### Handoff Mechanism

Contractors communicate through a structured handoff system:

```json
{
  "handoff_id": "unique-identifier",
  "from_contractor": "source",
  "to_contractor": "destination",
  "task_id": "parent-task",
  "data": {},
  "status": "pending|in_progress|completed|failed"
}
```

### Workflow Phases

Most workflows follow this pattern:

1. **Initialization**: n8n-contractor receives trigger (webhook, schedule, alert)
2. **Preparation**: First contractor provisions resources
3. **Configuration**: Second contractor configures services
4. **Integration**: Third contractor connects components
5. **Verification**: n8n-contractor validates and monitors
6. **Notification**: Stakeholders informed of results

## Available Workflows

See [cross-contractor-examples.md](cross-contractor-examples.md) for detailed implementations:

### 1. Deploy Monitoring Stack

**Purpose**: Deploy Prometheus, Grafana, and automated alerting

**Contractors**: infrastructure → talos → n8n

**Duration**: ~45 minutes

**Use Cases**:
- Setting up monitoring for new environments
- Expanding monitoring capabilities
- Implementing custom alerting workflows

### 2. Build New K8s Cluster

**Purpose**: Deploy production-ready Kubernetes cluster from scratch

**Contractors**: infrastructure → talos → n8n

**Duration**: ~60 minutes

**Use Cases**:
- Launching new environments (dev/staging/prod)
- Cluster capacity expansion
- Multi-datacenter deployments

### 3. Disaster Recovery Failover

**Purpose**: Automated failover from primary to DR site

**Contractors**: infrastructure → talos → n8n (coordinated)

**Duration**: ~15 minutes (RTO target)

**Use Cases**:
- Datacenter outages
- Major infrastructure failures
- Planned maintenance requiring failover

### 4. Application Deployment Pipeline

**Purpose**: End-to-end CI/CD from code commit to production

**Contractors**: n8n → talos → infrastructure (circular)

**Duration**: ~20 minutes (with approval)

**Use Cases**:
- Continuous deployment
- Blue-green deployments
- Canary releases

### 5. Security Incident Response

**Purpose**: Coordinated response to security incidents

**Contractors**: All (n8n, talos, infrastructure) + security-master

**Duration**: ~2 hours (varies by severity)

**Use Cases**:
- Node compromise
- Container breakout
- Malware detection
- Unauthorized access

## Creating New Workflows

### Workflow Design Principles

1. **Single Responsibility**: Each contractor handles its domain of expertise
2. **Clear Handoffs**: Explicit data transfer between contractors
3. **Error Handling**: Comprehensive error handling and recovery
4. **Rollback Support**: Every workflow should be reversible
5. **Observability**: Log all actions and state transitions
6. **Idempotency**: Actions should be safely repeatable

### Workflow Template

```json
{
  "workflow_id": "unique-workflow-id",
  "workflow_name": "Descriptive Name",
  "description": "What this workflow accomplishes",
  "version": "1.0.0",
  "contractors": ["contractor-1", "contractor-2", "contractor-3"],
  "estimated_duration": "30m",
  "phases": [
    {
      "phase_id": "phase-1",
      "phase_name": "Preparation",
      "contractor": "contractor-1",
      "actions": [
        {
          "action_id": "action-1-1",
          "action": "provision_resources",
          "parameters": {},
          "timeout": 600,
          "on_error": "rollback"
        }
      ],
      "handoff_to": "contractor-2",
      "handoff_data": ["resource_ids", "endpoints"]
    },
    {
      "phase_id": "phase-2",
      "phase_name": "Configuration",
      "contractor": "contractor-2",
      "actions": [],
      "handoff_to": "contractor-3"
    }
  ],
  "rollback_procedure": {
    "phases": ["phase-2-rollback", "phase-1-rollback"]
  },
  "success_criteria": [
    "All resources provisioned",
    "Health checks passing",
    "Notifications sent"
  ]
}
```

### Development Process

1. **Define Objective**: Clear statement of what the workflow accomplishes
2. **Identify Contractors**: Which contractors need to be involved
3. **Design Data Flow**: What data passes between contractors
4. **Plan Error Handling**: How to handle failures at each step
5. **Create Rollback**: How to undo the workflow if needed
6. **Document Workflow**: Add to cross-contractor-examples.md
7. **Test Workflow**: Execute in test environment
8. **Deploy to Production**: Add to production workflows

## Workflow Execution

### Manual Trigger

```bash
# Trigger via n8n webhook
curl -X POST https://n8n.cortex.local/webhook/workflow-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "deploy-monitoring-stack",
    "parameters": {
      "environment": "production",
      "cluster_name": "prod-k8s-01"
    }
  }'
```

### Scheduled Execution

Configure in n8n-contractor:

```json
{
  "workflow_id": "backup-etcd-snapshot",
  "trigger": "schedule",
  "schedule": "0 2 * * *",
  "timezone": "UTC",
  "enabled": true
}
```

### Event-Driven Trigger

Configure webhook in n8n-contractor:

```json
{
  "workflow_id": "security-incident-response",
  "trigger": "webhook",
  "webhook_path": "/webhook/security-alert",
  "source": "falco",
  "conditions": {
    "severity": "critical"
  }
}
```

## Monitoring Workflows

### View Active Workflows

```bash
# List currently executing workflows
ls -la /Users/ryandahlberg/Projects/cortex/coordination/workflows/active/

# Check workflow status
cat coordination/workflows/active/workflow-*.json | jq '.status'
```

### Workflow Metrics

```bash
# View workflow statistics
cat coordination/workflows/metrics/workflow-stats.json | jq
```

Example metrics:

```json
{
  "workflow_id": "deploy-monitoring-stack",
  "executions": {
    "total": 42,
    "successful": 40,
    "failed": 2,
    "success_rate": 0.952
  },
  "performance": {
    "avg_duration": "2845s",
    "min_duration": "2312s",
    "max_duration": "3621s",
    "p95_duration": "3200s"
  },
  "last_execution": {
    "timestamp": "2025-12-09T12:00:00Z",
    "status": "completed",
    "duration": "2734s"
  }
}
```

### Contractor Performance

```bash
# View contractor-specific metrics
cat coordination/workflows/metrics/contractor-performance.json | jq
```

Example:

```json
{
  "contractor": "infrastructure-contractor",
  "workflows_participated": 127,
  "avg_handoff_time": "45s",
  "error_rate": 0.015,
  "common_errors": [
    {"error": "vm_creation_timeout", "count": 12},
    {"error": "storage_quota_exceeded", "count": 8}
  ]
}
```

## Debugging Workflows

### Common Issues

#### Handoff Timeout

**Symptom**: Workflow stalls between contractors

**Diagnosis**:
```bash
# Check handoff file
cat coordination/masters/*/handoffs/*.json | jq '.status'

# Check contractor logs
tail -f coordination/masters/*/logs/contractor.log
```

**Resolution**:
- Verify target contractor is running
- Check network connectivity
- Verify handoff file permissions
- Retry handoff manually

#### Resource Exhaustion

**Symptom**: Workflow fails during provisioning

**Diagnosis**:
```bash
# Check available resources
pvesh get /cluster/resources

# Check storage pools
pvesh get /storage
```

**Resolution**:
- Free up resources
- Use alternative resource pool
- Modify workflow parameters to use less resources

#### Configuration Error

**Symptom**: Service fails to start after deployment

**Diagnosis**:
```bash
# Check pod logs (K8s)
kubectl logs -n namespace pod-name

# Check service status (VM)
systemctl status service-name

# Check configuration
kubectl get configmap -n namespace -o yaml
```

**Resolution**:
- Review configuration in handoff data
- Verify secrets are available
- Check for typos in configuration
- Validate against expected schema

### Debug Mode

Enable debug logging for contractors:

```bash
# Set debug flag in contractor state
echo '{"debug_mode": true}' > coordination/masters/infrastructure/context/debug-flag.json

# Tail debug logs
tail -f coordination/masters/infrastructure/logs/debug.log
```

## Workflow Best Practices

### Design

1. **Keep Phases Atomic**: Each phase should be a complete unit of work
2. **Use Timeouts**: Every action should have a timeout
3. **Validate Inputs**: Check all parameters before starting
4. **Preserve State**: Save state at each phase completion
5. **Enable Rollback**: Design for easy rollback from any phase

### Implementation

1. **Test Thoroughly**: Test in non-production environment first
2. **Use Dry-Run**: Implement dry-run mode for validation
3. **Log Everything**: Comprehensive logging for debugging
4. **Monitor Progress**: Real-time status updates
5. **Handle Errors Gracefully**: Never leave system in inconsistent state

### Operations

1. **Document Thoroughly**: Clear documentation for operators
2. **Version Workflows**: Track changes to workflows
3. **Measure Performance**: Track metrics for optimization
4. **Review Regularly**: Periodic review of workflows
5. **Learn from Failures**: Post-mortem analysis of failed workflows

## Integration with Other Systems

### GitHub Integration

Workflows can be triggered by GitHub events:

```json
{
  "workflow_id": "application-deployment",
  "trigger": {
    "type": "github_webhook",
    "events": ["push", "pull_request"],
    "branches": ["main"],
    "repository": "cortex-apps/*"
  }
}
```

### Monitoring Integration

Workflows can be triggered by monitoring alerts:

```json
{
  "workflow_id": "auto-scaling",
  "trigger": {
    "type": "prometheus_alert",
    "alert_name": "HighMemoryUsage",
    "threshold": 0.85
  }
}
```

### Ticketing Integration

Workflows can create and update tickets:

```json
{
  "action": "create_ticket",
  "system": "jira",
  "project": "OPS",
  "issue_type": "Task",
  "summary": "Workflow Execution: ${workflow_name}",
  "description": "Workflow ${workflow_id} completed with status: ${status}"
}
```

## Security Considerations

### Access Control

- Workflows should use service accounts with minimal permissions
- Sensitive data should be stored in secrets, not in workflow definitions
- Audit all workflow executions

### Data Protection

- Encrypt data in transit between contractors
- Mask sensitive data in logs
- Secure storage for workflow artifacts

### Compliance

- Maintain audit trail of all workflow executions
- Implement approval gates for sensitive workflows
- Regular security reviews of workflow definitions

## Troubleshooting Guide

### Workflow Won't Start

1. Check trigger configuration
2. Verify contractor availability
3. Check for conflicting workflows
4. Review workflow definition syntax

### Workflow Stalls Mid-Execution

1. Check contractor logs
2. Verify network connectivity
3. Check for resource exhaustion
4. Review handoff data

### Workflow Fails Consistently

1. Review error logs
2. Check parameter validation
3. Verify prerequisite conditions
4. Test in isolation

### Rollback Fails

1. Check current state
2. Verify rollback procedure
3. Manual intervention may be required
4. Document issue for workflow improvement

## Contributing

To add new workflows:

1. Design workflow following templates
2. Document in cross-contractor-examples.md
3. Create workflow definition JSON
4. Test in development environment
5. Submit for review
6. Deploy to production

## Support

For workflow-related issues:

- Check documentation in this directory
- Review contractor logs
- Contact DevOps team
- Create incident ticket for urgent issues

## References

- [Cross-Contractor Examples](cross-contractor-examples.md) - Detailed workflow implementations
- [Contractor Documentation](../contractors/) - Individual contractor capabilities
- [Master Documentation](../masters/) - Master orchestration patterns
- [Project Management](../project-management/) - Project-level workflow coordination

## Changelog

### 2025-12-09

- Initial creation of workflows directory
- Added 5 comprehensive cross-contractor workflow examples
- Documented workflow patterns and best practices
- Created metrics tracking structure
