# Permit System

## Overview

The Permit System is Cortex's authorization framework for production changes and high-risk operations. It implements approval workflows, audit trails, and safety gates to ensure that union-certified workers only perform authorized operations.

## Philosophy

**Principle**: Explicit authorization for every production change, with full auditability.

**Goals**:
- Prevent unauthorized production changes
- Enforce approval workflows
- Maintain comprehensive audit trails
- Enable emergency operations safely
- Support compliance requirements

## What is a Permit?

A **permit** is a time-limited authorization document that grants a specific worker permission to perform specific operations within defined constraints.

**Think of it like**:
- Construction permit: Authorization to modify infrastructure
- Work order: Approved scope and timeline
- Access badge: Time-limited credentials
- Flight plan: Pre-approved route and procedures

## Permit Lifecycle

```
1. Request → 2. Review → 3. Approval → 4. Issuance → 5. Execution → 6. Validation → 7. Closure
```

### 1. Permit Request

Initiated when certification checker determines union worker is needed:

```json
{
  "permit_request_id": "req-abc123",
  "requested_at": "2025-12-09T14:00:00Z",
  "requested_by": "development-master",
  "task_id": "task-12345",

  "operation_details": {
    "description": "Deploy API v2.1 to production",
    "operations": ["deploy", "database_migration", "configuration_update"],
    "environment": "production",
    "services_affected": ["api-service", "database", "cache"],
    "estimated_duration_minutes": 30,
    "scheduled_window": {
      "start": "2025-12-09T20:00:00Z",
      "end": "2025-12-09T21:00:00Z"
    }
  },

  "risk_assessment": {
    "risk_score": 28,
    "risk_level": "medium-high",
    "risk_factors": [
      "production_environment",
      "database_migration",
      "customer_facing_api"
    ],
    "mitigation_strategies": [
      "Blue-green deployment",
      "Automated rollback ready",
      "Feature flags enabled"
    ]
  },

  "certification_requirements": {
    "level_required": 3,
    "approvers_required": 2,
    "approver_roles": ["engineering_director", "security_lead"],
    "testing_required": {
      "unit_tests": "passed",
      "integration_tests": "passed",
      "performance_tests": "passed",
      "security_scan": "passed"
    }
  },

  "compliance_requirements": {
    "frameworks": ["SOC2", "GDPR"],
    "controls": ["change_management", "audit_logging"],
    "documentation_required": true
  }
}
```

### 2. Permit Review

Approvers review the request:

**What Approvers Check**:
- Does the change make business sense?
- Is the risk assessment accurate?
- Are rollback procedures documented?
- Is the change window appropriate?
- Are all requirements met?
- Is the scope reasonable?

**Approver Actions**:
- Approve: Grant authorization
- Reject: Deny with reason
- Request Changes: Ask for modifications
- Escalate: Route to higher authority

### 3. Permit Approval

Collect required approvals:

```json
{
  "approvals": [
    {
      "approver_id": "user-jane-doe",
      "approver_role": "engineering_director",
      "approved_at": "2025-12-09T15:30:00Z",
      "decision": "approved",
      "comments": "Looks good. Ensure monitoring is active during deployment.",
      "conditions": ["monitor_error_rates", "have_oncall_ready"]
    },
    {
      "approver_id": "user-john-smith",
      "approver_role": "security_lead",
      "approved_at": "2025-12-09T16:00:00Z",
      "decision": "approved",
      "comments": "Security scan passed. Approved for deployment.",
      "conditions": []
    }
  ],
  "approvals_complete": true,
  "approval_completion_time": "2025-12-09T16:00:00Z"
}
```

### 4. Permit Issuance

Once all approvals are obtained, issue the permit:

```json
{
  "permit_id": "permit-xyz789",
  "permit_type": "production_change",
  "status": "active",
  "issued_at": "2025-12-09T16:00:00Z",
  "expires_at": "2025-12-09T22:00:00Z",

  "authorized_worker": {
    "worker_id": "worker-deploy-001",
    "certification_level": 3,
    "master_id": "development-master"
  },

  "authorized_operations": {
    "operations": ["deploy", "database_migration", "configuration_update"],
    "environment": "production",
    "services": ["api-service", "database", "cache"],
    "methods_allowed": ["PUT", "POST", "PATCH"],
    "methods_forbidden": ["DELETE"]
  },

  "time_constraints": {
    "earliest_start": "2025-12-09T19:45:00Z",
    "latest_start": "2025-12-09T20:15:00Z",
    "must_complete_by": "2025-12-09T21:00:00Z",
    "max_duration_minutes": 45
  },

  "safety_constraints": {
    "rollback_required": true,
    "rollback_tested": true,
    "monitoring_required": true,
    "approval_for_scope_expansion": true,
    "auto_rollback_on_error": true,
    "max_error_rate": 0.01,
    "max_latency_p99_ms": 500
  },

  "audit_requirements": {
    "log_all_operations": true,
    "log_level": "verbose",
    "real_time_monitoring": true,
    "stakeholder_notification": ["engineering_director", "security_lead", "oncall"],
    "success_notification_required": true,
    "failure_notification_required": true
  },

  "approvals": [
    {
      "approver": "user-jane-doe",
      "role": "engineering_director",
      "approved_at": "2025-12-09T15:30:00Z"
    },
    {
      "approver": "user-john-smith",
      "role": "security_lead",
      "approved_at": "2025-12-09T16:00:00Z"
    }
  ],

  "conditions": [
    "Monitor error rates continuously",
    "Have on-call engineer ready",
    "Validate rollback procedure before starting",
    "Notify stakeholders 15 minutes before execution"
  ]
}
```

### 5. Permit Execution

Worker executes with permit:

**Pre-execution checks**:
```javascript
function validatePermit(permit, operation) {
  // Check permit is active
  if (permit.status !== 'active') {
    throw new Error('Permit not active');
  }

  // Check time window
  const now = new Date();
  if (now < permit.time_constraints.earliest_start ||
      now > permit.time_constraints.latest_start) {
    throw new Error('Outside permitted time window');
  }

  // Check operation is authorized
  if (!permit.authorized_operations.operations.includes(operation.type)) {
    throw new Error('Operation not authorized in permit');
  }

  // Check environment matches
  if (operation.environment !== permit.authorized_operations.environment) {
    throw new Error('Environment mismatch');
  }

  // Check worker certification
  if (operation.worker.certification_level < permit.authorized_worker.certification_level) {
    throw new Error('Insufficient worker certification');
  }

  return true;
}
```

**During execution**:
```javascript
function executeWithPermit(permit, operation) {
  // Start execution tracking
  const execution_id = startExecution(permit, operation);

  // Log start
  logPermitExecution({
    permit_id: permit.permit_id,
    execution_id: execution_id,
    started_at: new Date(),
    operation: operation.type,
    worker_id: operation.worker.id
  });

  try {
    // Perform operation with real-time monitoring
    const result = performOperation(operation);

    // Validate results against safety constraints
    validateResults(result, permit.safety_constraints);

    // Log success
    logPermitSuccess({
      permit_id: permit.permit_id,
      execution_id: execution_id,
      completed_at: new Date(),
      result: result
    });

    // Notify stakeholders
    notifyStakeholders(permit, 'success', result);

    return result;

  } catch (error) {
    // Log failure
    logPermitFailure({
      permit_id: permit.permit_id,
      execution_id: execution_id,
      failed_at: new Date(),
      error: error
    });

    // Auto-rollback if configured
    if (permit.safety_constraints.auto_rollback_on_error) {
      await rollback(execution_id);
    }

    // Notify stakeholders
    notifyStakeholders(permit, 'failure', error);

    throw error;
  }
}
```

### 6. Permit Validation

Continuous validation during execution:

```javascript
function monitorPermitExecution(permit, execution_id) {
  const interval = setInterval(() => {
    // Check time constraints
    if (new Date() > permit.time_constraints.must_complete_by) {
      cancelExecution(execution_id);
      revokePermit(permit.permit_id, 'time_exceeded');
    }

    // Check safety constraints
    const metrics = getCurrentMetrics(execution_id);

    if (metrics.error_rate > permit.safety_constraints.max_error_rate) {
      triggerAutoRollback(execution_id, 'error_rate_exceeded');
      revokePermit(permit.permit_id, 'safety_violation');
    }

    if (metrics.latency_p99 > permit.safety_constraints.max_latency_p99_ms) {
      triggerAutoRollback(execution_id, 'latency_exceeded');
      revokePermit(permit.permit_id, 'performance_degradation');
    }

    // Check scope
    if (metrics.services_affected.length > permit.authorized_operations.services.length) {
      cancelExecution(execution_id);
      revokePermit(permit.permit_id, 'scope_expansion');
    }

  }, 10000); // Check every 10 seconds

  return interval;
}
```

### 7. Permit Closure

Close permit after execution:

```json
{
  "permit_id": "permit-xyz789",
  "status": "closed",
  "closed_at": "2025-12-09T20:35:00Z",
  "closed_by": "worker-deploy-001",

  "execution_summary": {
    "execution_id": "exec-123456",
    "started_at": "2025-12-09T20:00:00Z",
    "completed_at": "2025-12-09T20:35:00Z",
    "duration_minutes": 35,
    "outcome": "success",

    "operations_performed": [
      "deploy_api_v2.1",
      "run_database_migration_v2.1",
      "update_configuration"
    ],

    "changes_made": {
      "deployments": 1,
      "migrations": 1,
      "configurations": 3,
      "services_restarted": 2
    },

    "validation": {
      "tests_passed": true,
      "health_checks_passed": true,
      "error_rate": 0.0001,
      "latency_p99_ms": 245,
      "all_constraints_met": true
    }
  },

  "audit_trail": {
    "operations_logged": 47,
    "approvals_verified": true,
    "constraints_enforced": true,
    "stakeholders_notified": true,
    "compliance_requirements_met": true
  },

  "post_execution": {
    "rollback_available": true,
    "rollback_tested_at": "2025-12-09T20:40:00Z",
    "documentation_updated": true,
    "lessons_learned": "Deployment went smoothly. Consider automating configuration updates."
  }
}
```

## Permit Types

### Standard Production Permit (Level 2)

**Use Case**: Regular production deployments and changes

**Requirements**:
- 1 approver (engineering manager)
- Test results required
- Rollback plan documented
- 24-hour approval window

**Example**: Deploy feature to production

### Advanced Production Permit (Level 3)

**Use Case**: Critical systems, sensitive data, complex changes

**Requirements**:
- 2 approvers (director + security/architecture)
- Comprehensive testing required
- Rollback tested
- Impact analysis completed
- 48-hour approval window

**Example**: Database migration in production

### Master Production Permit (Level 4)

**Use Case**: System-wide changes, multi-region, architectural

**Requirements**:
- 3+ approvers (VP/CTO/CISO)
- Change Advisory Board review
- Full documentation suite
- Rehearsed rollback procedures
- Risk assessment
- 7-day approval window

**Example**: Multi-region infrastructure change

### Emergency Permit (Temporary Level 3)

**Use Case**: Critical incidents requiring immediate action

**Requirements**:
- 1 approver (incident commander)
- Active incident ticket
- Real-time oversight required
- Automatic revocation after 1 hour
- Post-incident review mandatory

**Example**: Production outage requiring hotfix

### Read-Only Permit (Level 1)

**Use Case**: Production observability and diagnostics

**Requirements**:
- Basic approval or auto-approved
- Read-only access only
- No data modification
- Audit logging

**Example**: Query production database for debugging

## Approval Workflows

### Single Approver Workflow

```
Request → Review (approver) → Approve → Issue Permit
Timeline: Minutes to hours
```

### Multi-Approver Workflow (Parallel)

```
Request → Review (all approvers in parallel) → All Approve → Issue Permit
Timeline: Hours to days
```

### Multi-Approver Workflow (Serial)

```
Request → Review (approver 1) → Approve →
          Review (approver 2) → Approve →
          Review (approver 3) → Approve → Issue Permit
Timeline: Days to week
```

### Change Advisory Board Workflow

```
Request → Pre-review → CAB Meeting → Board Vote →
          Approval → Conditions Applied → Issue Permit
Timeline: Weeks
```

## Who Can Approve?

### Approval Authority Matrix

| Permit Level | Approver Roles | Count Required |
|-------------|----------------|----------------|
| Level 1 | Engineering team member | 1 (can be auto) |
| Level 2 | Engineering manager, Tech lead, Senior engineer | 1 |
| Level 3 | Engineering director, Security lead, Architecture lead | 2 |
| Level 4 | VP Engineering, CTO, CISO, COO | 3+ |
| Emergency | Incident commander, On-call lead | 1 |

### Approver Responsibilities

**When Approving, Consider**:
1. Business justification - Why is this change needed?
2. Technical correctness - Is the approach sound?
3. Risk vs benefit - Is the risk justified?
4. Timing - Is now the right time?
5. Alternatives - Were other options considered?
6. Rollback - Can we undo this if needed?
7. Testing - Has it been adequately tested?
8. Documentation - Is it well documented?
9. Team readiness - Is the team prepared?
10. Customer impact - How will customers be affected?

**Approvers Must**:
- Review within SLA timeframe
- Provide clear decision (approve/reject/modify)
- Document reasoning
- Specify any conditions
- Be available during execution window

**Approvers Cannot**:
- Approve their own changes
- Delegate approval authority (except emergencies)
- Approve without reviewing
- Backdoor the approval process

## Audit Trail Requirements

Every permit must maintain:

### Required Audit Logs

```json
{
  "audit_trail": {
    "permit_id": "permit-xyz789",

    "creation": {
      "requested_by": "development-master",
      "requested_at": "2025-12-09T14:00:00Z",
      "request_source": "task-12345",
      "requester_auth": "verified"
    },

    "approvals": [
      {
        "approver": "user-jane-doe",
        "approved_at": "2025-12-09T15:30:00Z",
        "approval_method": "web_ui",
        "ip_address": "192.168.1.100",
        "decision": "approved",
        "reasoning": "Change is low-risk and well-tested"
      }
    ],

    "issuance": {
      "issued_at": "2025-12-09T16:00:00Z",
      "issued_by": "permit-system",
      "permit_hash": "sha256:abc123...",
      "digital_signature": "sig:xyz789..."
    },

    "execution": {
      "started_at": "2025-12-09T20:00:00Z",
      "executed_by": "worker-deploy-001",
      "execution_host": "deploy-runner-03",
      "operations_performed": [...],
      "resources_accessed": [...],
      "data_modified": [...]
    },

    "monitoring": {
      "constraint_checks": [
        {"timestamp": "2025-12-09T20:05:00Z", "status": "passed"},
        {"timestamp": "2025-12-09T20:15:00Z", "status": "passed"},
        {"timestamp": "2025-12-09T20:25:00Z", "status": "passed"}
      ],
      "alerts_triggered": [],
      "safety_violations": []
    },

    "closure": {
      "closed_at": "2025-12-09T20:35:00Z",
      "outcome": "success",
      "validation": "passed",
      "rollback_available": true
    },

    "compliance": {
      "frameworks": ["SOC2", "GDPR"],
      "controls_applied": ["change_management", "audit_logging"],
      "attestation": "compliant"
    }
  }
}
```

### Retention Requirements

- **Production permits**: 1 year minimum
- **Critical systems permits**: 7 years (compliance)
- **Failed operations**: 2 years
- **Emergency permits**: 3 years

### Audit Access

- **Real-time**: Approvers, stakeholders, security team
- **Historical**: Compliance team, auditors, executives
- **External audit**: Auditable export format

## Permit Revocation

Permits can be revoked for:

1. **Time Expiration**: Past permitted time window
2. **Safety Violation**: Constraint breach detected
3. **Scope Expansion**: Operation exceeds authorized scope
4. **Approver Request**: Approver withdraws approval
5. **Incident**: Related incident requires halt
6. **Emergency**: Emergency situation requires immediate stop

**Revocation Process**:
```javascript
function revokePermit(permit_id, reason) {
  // Immediate halt
  const permit = getPermit(permit_id);
  permit.status = 'revoked';
  permit.revoked_at = new Date();
  permit.revoked_reason = reason;

  // Stop ongoing executions
  if (permit.active_execution_id) {
    haltExecution(permit.active_execution_id);
  }

  // Trigger rollback if needed
  if (reason === 'safety_violation' || reason === 'scope_expansion') {
    triggerEmergencyRollback(permit.active_execution_id);
  }

  // Notify all stakeholders
  notifyStakeholders(permit, 'revoked', reason);

  // Log revocation
  logPermitRevocation(permit);

  // Create incident if serious
  if (['safety_violation', 'scope_expansion'].includes(reason)) {
    createIncident({
      type: 'permit_violation',
      permit_id: permit_id,
      reason: reason
    });
  }
}
```

## Permit Templates

Pre-approved templates for common operations:

```json
{
  "templates": {
    "standard_api_deployment": {
      "permit_type": "production_change",
      "level_required": 2,
      "approvers_required": 1,
      "operations": ["deploy", "health_check"],
      "time_window_hours": 2,
      "auto_rollback": true,
      "pre_populated": {
        "testing_checklist": true,
        "rollback_procedure": true,
        "monitoring_dashboard": true
      }
    },

    "database_migration": {
      "permit_type": "production_change",
      "level_required": 3,
      "approvers_required": 2,
      "operations": ["database_migration"],
      "time_window_hours": 4,
      "auto_rollback": false,
      "requires_rehearsal": true,
      "pre_populated": {
        "migration_script": true,
        "rollback_script": true,
        "data_backup_verification": true
      }
    },

    "configuration_change": {
      "permit_type": "production_change",
      "level_required": 2,
      "approvers_required": 1,
      "operations": ["configuration_update"],
      "time_window_hours": 1,
      "auto_rollback": true
    },

    "emergency_hotfix": {
      "permit_type": "emergency",
      "level_required": 3,
      "approvers_required": 1,
      "operations": ["deploy", "configuration_update"],
      "time_window_hours": 1,
      "auto_revocation": true,
      "requires": {
        "incident_ticket": true,
        "real_time_oversight": true
      }
    }
  }
}
```

## Permit Dashboard

Real-time permit visibility:

**Active Permits View**:
- Currently executing permits
- Time remaining
- Progress indicators
- Safety constraint status
- Real-time metrics

**Pending Approvals View**:
- Permits awaiting approval
- Time since requested
- Required approvers
- Urgency indicators

**Historical View**:
- Completed permits
- Success/failure rates
- Average approval time
- Common patterns

## Compliance Integration

### SOC 2 Requirements
- Change management process documented
- All changes approved
- Audit trail maintained
- Access controls enforced

### HIPAA Requirements
- PHI access logged
- Minimum necessary principle
- Access authorization
- Audit reports available

### PCI DSS Requirements
- Segregation of duties
- Change tracking
- Access logging
- Quarterly reviews

## Best Practices

### For Requesters
1. Request permits early (don't wait until last minute)
2. Provide comprehensive details
3. Document rollback procedures
4. Schedule during low-traffic windows
5. Have team ready during execution

### For Approvers
1. Review thoroughly, don't rubber-stamp
2. Ask questions if unclear
3. Verify testing completion
4. Ensure team readiness
5. Be available during execution window

### For Operators
1. Execute only within time window
2. Monitor continuously
3. Report issues immediately
4. Follow rollback procedures if needed
5. Complete post-execution documentation

## Metrics

Track permit system health:

- Approval time (by level)
- Permit success rate
- Revocation rate
- Time-to-approval SLA compliance
- Audit trail completeness
- Safety violation rate
- Emergency permit frequency

## Conclusion

The Permit System ensures that:
- Production changes are authorized
- Approval workflows are enforced
- Audit trails are comprehensive
- Safety constraints are monitored
- Compliance requirements are met
- Emergency operations are safe

**Remember**: Every production change requires a permit. No exceptions.
