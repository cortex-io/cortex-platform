# Permit Workflow System

## Overview

The Permit Workflow System is Cortex's operational authorization framework that governs how workers request, obtain, and execute permits for production changes. It bridges the Worker Certification System with the Project Management state machine to ensure safe, auditable operations.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERMIT WORKFLOW SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │   Request    │─────>│   Routing    │─────>│   Approval   │ │
│  │   Engine     │      │   Engine     │      │   Engine     │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│         │                      │                      │         │
│         v                      v                      v         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │ Risk         │      │ Auto-Approve │      │ Multi-Stage  │ │
│  │ Assessment   │      │ Checker      │      │ Review       │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    PERMIT EXECUTION ENGINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │  Validation  │─────>│  Monitoring  │─────>│   Closure    │ │
│  │  Pre-Flight  │      │  Real-Time   │      │   & Audit    │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Permit Request Format

### Core Permit Request Schema

```json
{
  "$schema": "https://cortex.ai/schemas/permit-request/v1.0.0",
  "permit_request_id": "req-{uuid}",
  "version": "1.0.0",
  "created_at": "ISO-8601 timestamp",
  "requested_by": {
    "agent_type": "master|worker|pm|coordinator",
    "agent_id": "string",
    "project_id": "string (if PM context)",
    "task_id": "string"
  },

  "operation_details": {
    "operation_type": "deployment|migration|configuration|security|infrastructure|data_operation|emergency_fix",
    "operation_subtype": "string (specific operation)",
    "description": "Human-readable operation description",
    "justification": "Business or technical justification",

    "target": {
      "environment": "production|staging|development|test",
      "region": "string|array of strings",
      "services": ["service-1", "service-2"],
      "components": ["component-1", "component-2"],
      "infrastructure": ["resource-1", "resource-2"]
    },

    "timing": {
      "urgency": "emergency|high|normal|low",
      "requested_start": "ISO-8601 timestamp",
      "requested_end": "ISO-8601 timestamp",
      "estimated_duration_minutes": 0,
      "blackout_windows": ["ISO-8601 range"],
      "preferred_windows": ["ISO-8601 range"]
    },

    "impact_assessment": {
      "customer_facing": true|false,
      "service_interruption": "none|partial|full",
      "estimated_downtime_seconds": 0,
      "affected_users": "none|subset|all",
      "data_modification": true|false,
      "reversibility": "fully_reversible|automated_rollback|manual_rollback|irreversible"
    }
  },

  "risk_assessment": {
    "risk_score": 0,
    "risk_level": "very_low|low|medium|high|very_high|critical",
    "risk_factors": [
      {
        "category": "environment|data_sensitivity|operation_type|impact_scope|reversibility",
        "factor": "string",
        "score": 0,
        "weight": 0.0
      }
    ],
    "calculated_certification_level": 0,
    "mitigation_strategies": [
      {
        "risk": "string",
        "mitigation": "string",
        "status": "planned|implemented|tested"
      }
    ]
  },

  "certification_requirements": {
    "minimum_level": 0,
    "required_certifications": ["certification-type"],
    "approvers_required": 0,
    "approver_roles": ["role-1", "role-2"],
    "approval_mode": "parallel|sequential|change_advisory_board"
  },

  "technical_requirements": {
    "testing": {
      "unit_tests": "required|recommended|optional|not_applicable",
      "integration_tests": "required|recommended|optional|not_applicable",
      "performance_tests": "required|recommended|optional|not_applicable",
      "security_tests": "required|recommended|optional|not_applicable",
      "test_results_url": "string",
      "test_coverage": 0.0
    },

    "code_review": {
      "required": true|false,
      "reviewers_required": 0,
      "review_url": "string",
      "status": "pending|approved|changes_requested"
    },

    "rollback": {
      "strategy": "automated|manual|blue_green|canary|none",
      "procedure_documented": true|false,
      "procedure_url": "string",
      "tested": true|false,
      "test_date": "ISO-8601 timestamp",
      "estimated_rollback_time_minutes": 0
    },

    "monitoring": {
      "dashboard_url": "string",
      "key_metrics": ["metric-1", "metric-2"],
      "alert_rules": ["rule-1", "rule-2"],
      "on_call_team": "team-name"
    }
  },

  "compliance_requirements": {
    "frameworks": ["SOC2", "HIPAA", "PCI-DSS", "GDPR", "SOX"],
    "controls": ["control-id-1", "control-id-2"],
    "documentation_urls": ["url-1", "url-2"],
    "attestation_required": true|false,
    "external_audit": true|false
  },

  "dependencies": {
    "blocking_permits": ["permit-id-1"],
    "dependent_permits": ["permit-id-2"],
    "external_dependencies": [
      {
        "description": "string",
        "status": "satisfied|pending|blocked"
      }
    ]
  },

  "resources": {
    "token_allocation": 0,
    "estimated_cost_usd": 0.0,
    "team_members": ["user-id-1", "user-id-2"],
    "infrastructure_resources": ["resource-1"]
  },

  "metadata": {
    "priority": "p0|p1|p2|p3|p4",
    "tags": ["tag-1", "tag-2"],
    "related_incidents": ["incident-id"],
    "related_projects": ["project-id"],
    "communication_plan": {
      "stakeholders": ["stakeholder-1"],
      "notification_channels": ["slack", "email", "pagerduty"],
      "pre_notification_required": true|false,
      "post_notification_required": true|false
    }
  }
}
```

## Permit Types

### 1. Read-Only Permit (Level 1)

**Purpose**: Non-destructive observation and diagnostics

**Characteristics**:
- Read-only access to production systems
- No data modification
- Minimal approval overhead
- Audit logging required

**Auto-Approval Conditions**:
- Environment: Production (read-only)
- Risk score: < 10
- Worker certification: Level 1+
- No sensitive data access (PII/PHI/financial)
- Time window: Anytime

**Approval Routing**:
```
Auto-Approve IF:
  - risk_score < 10
  - worker.level >= 1
  - operation_type == "read_only"
  - data_sensitivity NOT IN ["pii", "phi", "financial", "credentials"]
ELSE:
  - Route to: [team_lead]
  - Approvers required: 1
  - SLA: 4 hours
```

**Example Use Cases**:
- Query production database for debugging
- Read application logs
- View system metrics
- Export monitoring data

### 2. Standard Production Permit (Level 2)

**Purpose**: Regular production deployments and configuration changes

**Characteristics**:
- Standard production modifications
- Tested rollback procedures
- Business-hours execution preferred
- Automated monitoring

**Approval Routing**:
```
Route to: [engineering_manager OR tech_lead OR senior_engineer]
Approvers required: 1
SLA: 24 hours
Approval mode: parallel

Requirements:
  - Test results: PASSED
  - Code review: APPROVED
  - Rollback plan: DOCUMENTED
  - Monitoring: CONFIGURED
```

**Example Use Cases**:
- Deploy application to production
- Update application configuration
- Scale infrastructure resources
- Enable feature flags

### 3. Advanced Production Permit (Level 3)

**Purpose**: High-risk operations on critical systems

**Characteristics**:
- Critical systems or sensitive data
- Complex rollback procedures
- Rehearsed execution
- Real-time oversight

**Approval Routing**:
```
Route to: [engineering_director, security_lead, architecture_lead]
Approvers required: 2
SLA: 48 hours
Approval mode: parallel (any 2)

Requirements:
  - Test results: COMPREHENSIVE
  - Code review: APPROVED
  - Security review: APPROVED
  - Rollback plan: TESTED
  - Impact analysis: COMPLETED
  - Monitoring: ENHANCED
  - Stakeholder notification: SENT
```

**Example Use Cases**:
- Database schema migration
- Multi-service coordinated deployment
- Security configuration changes
- Data migration with PII/PHI
- Infrastructure architecture changes

### 4. Master Production Permit (Level 4)

**Purpose**: System-wide changes with architectural impact

**Characteristics**:
- Multi-region deployments
- System architecture modifications
- Regulatory compliance impact
- Executive visibility required

**Approval Routing**:
```
Route to: [vp_engineering, cto, ciso, coo]
Approvers required: 3
SLA: 168 hours (7 days)
Approval mode: Change Advisory Board

Requirements:
  - Test results: EXHAUSTIVE
  - Code review: APPROVED
  - Security audit: COMPLETED
  - Architecture review: APPROVED
  - Rollback plan: REHEARSED
  - Risk assessment: COMPREHENSIVE
  - Business justification: DOCUMENTED
  - Customer communication: PLANNED
  - Incident response: READY
```

**Example Use Cases**:
- Multi-region infrastructure migration
- Core system architecture changes
- Compliance framework implementation
- Company-wide security policy changes

### 5. Emergency Permit (Temporary Level 3)

**Purpose**: Critical incident response requiring immediate action

**Characteristics**:
- Active incident ongoing
- Time-sensitive resolution
- Temporary elevated privileges
- Mandatory post-incident review

**Approval Routing**:
```
Route to: [incident_commander OR on_call_lead]
Approvers required: 1
SLA: 15 minutes
Approval mode: sequential

Emergency triggers:
  - Production outage (severity 1)
  - Security breach
  - Data loss event
  - Customer-impacting failure

Auto-revocation: 1 hour OR incident resolved

Requirements:
  - Incident ticket: REQUIRED
  - Real-time oversight: MANDATORY
  - Post-incident review: SCHEDULED
```

**Example Use Cases**:
- Production outage hotfix
- Security breach remediation
- Data recovery operations
- Emergency rollback

### 6. Destructive Permit (Level 3+)

**Purpose**: Irreversible operations requiring extreme caution

**Characteristics**:
- Data deletion or corruption risk
- No automated rollback
- Multiple approval stages
- Enhanced audit trail

**Approval Routing**:
```
Route to: [data_lead, security_lead, engineering_director]
Approvers required: 3 (all must approve)
SLA: 48 hours
Approval mode: sequential

Requirements:
  - Data backup: VERIFIED
  - Rollback plan: MANUAL (documented)
  - Impact analysis: COMPLETE
  - Legal review: IF data_retention_policy_affected
  - Business justification: STRONG
```

**Example Use Cases**:
- Production data deletion
- Database truncation
- Archive purging
- Account deletion (GDPR)

## Approval Routing Rules

### Routing Decision Tree

```javascript
function routePermitRequest(request) {
  // Step 1: Calculate risk score
  const riskScore = calculateRiskScore(request);

  // Step 2: Determine certification level
  const certLevel = determineCertificationLevel(riskScore, request);

  // Step 3: Check auto-approval eligibility
  if (isAutoApprovalEligible(request, riskScore, certLevel)) {
    return {
      routing: "auto_approve",
      approvers: [],
      sla_hours: 0,
      approval_mode: "automatic"
    };
  }

  // Step 4: Emergency permit fast-track
  if (request.operation_details.timing.urgency === "emergency") {
    return routeEmergencyPermit(request);
  }

  // Step 5: Route based on certification level
  switch(certLevel) {
    case 1:
      return routeLevel1Permit(request);
    case 2:
      return routeLevel2Permit(request);
    case 3:
      return routeLevel3Permit(request);
    case 4:
      return routeLevel4Permit(request);
    default:
      throw new Error(`Invalid certification level: ${certLevel}`);
  }
}

function calculateRiskScore(request) {
  let score = 0;

  // Environment (0-10)
  const envScores = {
    "production": 10,
    "staging": 5,
    "development": 1,
    "local": 0
  };
  score += envScores[request.operation_details.target.environment] || 0;

  // Reversibility (0-10)
  const revScores = {
    "irreversible": 10,
    "manual_rollback": 7,
    "automated_rollback": 3,
    "fully_reversible": 0
  };
  score += revScores[request.operation_details.impact_assessment.reversibility] || 0;

  // Data sensitivity (0-10)
  if (request.operation_details.impact_assessment.data_modification) {
    // Check compliance requirements for data sensitivity indicators
    const sensitiveFrameworks = ["HIPAA", "PCI-DSS", "GDPR"];
    const hasSensitiveData = request.compliance_requirements.frameworks.some(
      f => sensitiveFrameworks.includes(f)
    );
    score += hasSensitiveData ? 10 : 3;
  }

  // Impact scope (0-10)
  const impactScores = {
    "all": 10,
    "subset": 7,
    "none": 0
  };
  score += impactScores[request.operation_details.impact_assessment.affected_users] || 0;

  // Customer impact (0-10)
  if (request.operation_details.impact_assessment.customer_facing) {
    score += 8;
  }

  // Service interruption (0-10)
  const interruptScores = {
    "full": 10,
    "partial": 5,
    "none": 0
  };
  score += interruptScores[request.operation_details.impact_assessment.service_interruption] || 0;

  return score;
}

function determineCertificationLevel(riskScore, request) {
  // Hard requirements override risk score

  // Level 4: System-wide, multi-region, or architectural
  if (request.operation_details.target.region &&
      Array.isArray(request.operation_details.target.region) &&
      request.operation_details.target.region.length > 1) {
    return 4;
  }

  // Level 4: SOX compliance (financial)
  if (request.compliance_requirements.frameworks.includes("SOX")) {
    return 4;
  }

  // Level 3: Sensitive data
  const sensitiveFrameworks = ["HIPAA", "PCI-DSS", "GDPR"];
  if (request.compliance_requirements.frameworks.some(f => sensitiveFrameworks.includes(f))) {
    return 3;
  }

  // Level 3: Destructive operations
  const destructiveOps = ["database_migration", "data_deletion", "infrastructure_change"];
  if (destructiveOps.includes(request.operation_details.operation_type)) {
    return 3;
  }

  // Risk score based
  if (riskScore >= 36) return 4;
  if (riskScore >= 21) return 3;
  if (riskScore >= 6) return 2;
  return 1;
}

function isAutoApprovalEligible(request, riskScore, certLevel) {
  // Auto-approval conditions
  return (
    riskScore < 6 &&
    certLevel === 1 &&
    request.operation_details.target.environment !== "production" &&
    !request.operation_details.impact_assessment.customer_facing &&
    request.operation_details.impact_assessment.service_interruption === "none"
  );
}
```

### Approval Routing Tables

#### Level 1 Routing
```json
{
  "level": 1,
  "permit_type": "read_only",
  "approvers": {
    "roles": ["team_lead", "senior_engineer"],
    "required_count": 1,
    "selection_mode": "any"
  },
  "sla_hours": 4,
  "approval_mode": "parallel",
  "auto_approve_conditions": {
    "risk_score_max": 10,
    "environment": ["development", "test"],
    "read_only": true
  }
}
```

#### Level 2 Routing
```json
{
  "level": 2,
  "permit_type": "standard_production",
  "approvers": {
    "roles": ["engineering_manager", "tech_lead", "senior_engineer"],
    "required_count": 1,
    "selection_mode": "any"
  },
  "sla_hours": 24,
  "approval_mode": "parallel",
  "requirements": {
    "test_results": "required",
    "code_review": "required",
    "rollback_plan": "required",
    "monitoring_configured": "required"
  }
}
```

#### Level 3 Routing
```json
{
  "level": 3,
  "permit_type": "advanced_production",
  "approvers": {
    "roles": ["engineering_director", "security_lead", "architecture_lead"],
    "required_count": 2,
    "selection_mode": "any_2"
  },
  "sla_hours": 48,
  "approval_mode": "parallel",
  "requirements": {
    "test_results": "comprehensive",
    "code_review": "required",
    "security_review": "required",
    "rollback_plan": "tested",
    "impact_analysis": "required",
    "stakeholder_notification": "required"
  }
}
```

#### Level 4 Routing
```json
{
  "level": 4,
  "permit_type": "master_production",
  "approvers": {
    "roles": ["vp_engineering", "cto", "ciso", "coo"],
    "required_count": 3,
    "selection_mode": "minimum_3"
  },
  "sla_hours": 168,
  "approval_mode": "change_advisory_board",
  "requirements": {
    "test_results": "exhaustive",
    "code_review": "required",
    "security_audit": "required",
    "architecture_review": "required",
    "rollback_plan": "rehearsed",
    "risk_assessment": "comprehensive",
    "business_justification": "required",
    "incident_response_plan": "required"
  },
  "cab_meeting": {
    "frequency": "weekly",
    "advance_notice_days": 7,
    "presentation_required": true
  }
}
```

#### Emergency Routing
```json
{
  "permit_type": "emergency",
  "approvers": {
    "roles": ["incident_commander", "on_call_lead"],
    "required_count": 1,
    "selection_mode": "first_available"
  },
  "sla_minutes": 15,
  "approval_mode": "sequential",
  "triggers": [
    "production_outage_severity_1",
    "security_breach",
    "data_loss_event",
    "customer_impact_critical"
  ],
  "temporary_certification": {
    "grant_level": 3,
    "duration_hours": 1,
    "auto_revoke": true
  },
  "requirements": {
    "incident_ticket": "required",
    "real_time_oversight": "mandatory",
    "post_incident_review": "scheduled_within_24h"
  }
}
```

## Permit Expiration and Renewal

### Expiration Policies

```json
{
  "expiration_policies": {
    "read_only": {
      "default_duration_hours": 168,
      "max_duration_hours": 720,
      "renewal_allowed": true,
      "renewal_approval_required": false
    },
    "standard_production": {
      "default_duration_hours": 24,
      "max_duration_hours": 168,
      "renewal_allowed": true,
      "renewal_approval_required": true
    },
    "advanced_production": {
      "default_duration_hours": 8,
      "max_duration_hours": 48,
      "renewal_allowed": true,
      "renewal_approval_required": true,
      "renewal_justification_required": true
    },
    "master_production": {
      "default_duration_hours": 4,
      "max_duration_hours": 24,
      "renewal_allowed": false,
      "new_permit_required": true
    },
    "emergency": {
      "default_duration_hours": 1,
      "max_duration_hours": 4,
      "renewal_allowed": true,
      "renewal_approval_required": true,
      "renewal_incident_commander_only": true
    },
    "destructive": {
      "default_duration_hours": 2,
      "max_duration_hours": 8,
      "renewal_allowed": false,
      "single_use": true
    }
  },

  "expiration_warnings": {
    "first_warning_before_minutes": 30,
    "second_warning_before_minutes": 15,
    "final_warning_before_minutes": 5,
    "notification_channels": ["agent", "approvers", "monitoring"]
  },

  "auto_expiration_actions": {
    "on_expiration": {
      "revoke_permit": true,
      "halt_operations": true,
      "trigger_audit": true,
      "notify_stakeholders": true
    },
    "grace_period_minutes": 5,
    "allow_completion_if_in_progress": true
  }
}
```

### Renewal Process

```javascript
function renewPermit(permitId, renewalRequest) {
  const permit = getPermit(permitId);
  const policy = getExpirationPolicy(permit.permit_type);

  // Check if renewal allowed
  if (!policy.renewal_allowed) {
    return {
      status: "denied",
      reason: "Permit type does not allow renewal",
      action: "Submit new permit request"
    };
  }

  // Check if within renewal window
  const timeRemaining = permit.expires_at - Date.now();
  if (timeRemaining > (2 * 60 * 60 * 1000)) { // 2 hours
    return {
      status: "denied",
      reason: "Too early for renewal (> 2 hours remaining)",
      action: "Wait until within 2 hours of expiration"
    };
  }

  // Check if approval required
  if (policy.renewal_approval_required) {
    return requestRenewalApproval(permit, renewalRequest);
  }

  // Auto-renew
  return {
    status: "approved",
    new_expiration: calculateNewExpiration(permit, policy),
    renewal_id: generateRenewalId(),
    renewed_at: new Date().toISOString()
  };
}

function calculateNewExpiration(permit, policy) {
  const currentExpiration = new Date(permit.expires_at);
  const extensionHours = Math.min(
    renewalRequest.extension_hours || policy.default_duration_hours,
    policy.max_duration_hours
  );

  return new Date(currentExpiration.getTime() + (extensionHours * 60 * 60 * 1000));
}
```

## Permit Revocation Procedures

### Revocation Triggers

```json
{
  "revocation_triggers": {
    "automatic": {
      "time_expiration": {
        "action": "immediate_revoke",
        "notification": "all_stakeholders",
        "halt_operations": true
      },
      "safety_violation": {
        "action": "immediate_revoke_and_rollback",
        "notification": "emergency",
        "create_incident": true
      },
      "scope_expansion": {
        "action": "immediate_revoke",
        "notification": "approvers",
        "escalation": "security_team"
      },
      "constraint_breach": {
        "action": "immediate_revoke",
        "notification": "monitoring_team",
        "trigger_rollback": true
      }
    },

    "manual": {
      "approver_request": {
        "authorized_by": ["original_approvers", "security_lead", "incident_commander"],
        "action": "revoke_after_confirmation",
        "notification": "permit_holder",
        "reason_required": true
      },
      "security_incident": {
        "authorized_by": ["security_lead", "ciso", "incident_commander"],
        "action": "immediate_revoke",
        "notification": "all_stakeholders",
        "create_incident": true
      },
      "emergency_halt": {
        "authorized_by": ["incident_commander", "cto", "coo"],
        "action": "immediate_revoke_all_related",
        "notification": "emergency",
        "halt_all_operations": true
      }
    }
  }
}
```

### Revocation Process

```javascript
function revokePermit(permitId, revocationRequest) {
  const permit = getPermit(permitId);

  // Validate authorization
  if (!isAuthorizedToRevoke(revocationRequest.revoked_by, permit)) {
    throw new Error("Unauthorized revocation attempt");
  }

  // Immediate actions
  const revocation = {
    permit_id: permitId,
    revoked_at: new Date().toISOString(),
    revoked_by: revocationRequest.revoked_by,
    revocation_reason: revocationRequest.reason,
    revocation_trigger: revocationRequest.trigger,

    actions_taken: []
  };

  // 1. Update permit status
  permit.status = "revoked";
  permit.revoked_at = revocation.revoked_at;
  permit.revocation_reason = revocation.revocation_reason;
  savePermit(permit);
  revocation.actions_taken.push("permit_status_updated");

  // 2. Halt active operations
  if (permit.active_execution_id) {
    haltExecution(permit.active_execution_id);
    revocation.actions_taken.push("execution_halted");
  }

  // 3. Trigger rollback if necessary
  const criticalTriggers = ["safety_violation", "scope_expansion", "constraint_breach"];
  if (criticalTriggers.includes(revocationRequest.trigger)) {
    triggerEmergencyRollback(permit.active_execution_id);
    revocation.actions_taken.push("emergency_rollback_triggered");
  }

  // 4. Notify stakeholders
  notifyStakeholders(permit, "revoked", revocation);
  revocation.actions_taken.push("stakeholders_notified");

  // 5. Create incident if serious
  if (revocationRequest.create_incident) {
    const incident = createIncident({
      type: "permit_violation",
      severity: "critical",
      permit_id: permitId,
      revocation_reason: revocationRequest.reason,
      trigger: revocationRequest.trigger
    });
    revocation.incident_id = incident.incident_id;
    revocation.actions_taken.push("incident_created");
  }

  // 6. Audit logging
  logPermitRevocation(permit, revocation);
  revocation.actions_taken.push("audit_logged");

  // 7. Update metrics
  updateRevocationMetrics(permit, revocation);

  return revocation;
}
```

### Post-Revocation Procedures

```json
{
  "post_revocation": {
    "immediate": {
      "verify_operations_halted": {
        "timeout_seconds": 30,
        "verification_method": "monitoring_check",
        "escalate_if_not_halted": true
      },
      "verify_rollback_if_triggered": {
        "timeout_minutes": 15,
        "verification_method": "service_health_check",
        "manual_intervention_if_failed": true
      },
      "notify_on_call": {
        "if_severity": ["high", "critical"],
        "channels": ["pagerduty", "slack"],
        "include_context": true
      }
    },

    "within_24_hours": {
      "root_cause_analysis": {
        "required_for": ["safety_violation", "scope_expansion", "security_incident"],
        "assigned_to": "security_team",
        "template": "rca_template_v1"
      },
      "lessons_learned": {
        "document_in": "knowledge_base",
        "share_with": ["all_masters", "coordinator"],
        "update_policies_if_needed": true
      }
    },

    "within_1_week": {
      "permit_system_review": {
        "evaluate_if_preventable": true,
        "update_approval_rules_if_needed": true,
        "enhance_monitoring_if_needed": true
      }
    }
  }
}
```

## Emergency Bypass Protocols

### When Emergency Bypass is Authorized

```json
{
  "emergency_bypass": {
    "authorized_scenarios": {
      "severity_1_outage": {
        "description": "Complete production outage affecting all customers",
        "authorized_by": ["incident_commander", "cto", "coo"],
        "max_duration_minutes": 60,
        "requirements": {
          "incident_ticket": "required",
          "real_time_oversight": "mandatory",
          "continuous_communication": "required"
        }
      },

      "security_breach_active": {
        "description": "Active security breach requiring immediate remediation",
        "authorized_by": ["incident_commander", "ciso"],
        "max_duration_minutes": 30,
        "requirements": {
          "security_incident_ticket": "required",
          "security_team_oversight": "mandatory",
          "forensics_preservation": "required"
        }
      },

      "data_loss_imminent": {
        "description": "Immediate action required to prevent data loss",
        "authorized_by": ["incident_commander", "data_lead", "cto"],
        "max_duration_minutes": 45,
        "requirements": {
          "incident_ticket": "required",
          "data_team_oversight": "mandatory",
          "backup_verification": "required"
        }
      },

      "regulatory_deadline": {
        "description": "Regulatory compliance deadline requires immediate action",
        "authorized_by": ["cto", "ciso", "legal"],
        "max_duration_hours": 4,
        "requirements": {
          "legal_approval": "required",
          "compliance_documentation": "required",
          "audit_trail": "comprehensive"
        }
      }
    },

    "bypass_limitations": {
      "cannot_bypass": [
        "Data protection controls (PII/PHI encryption)",
        "Audit logging requirements",
        "Multi-person authorization for destructive operations",
        "Compliance framework controls (SOX, HIPAA)"
      ],
      "must_maintain": [
        "Audit trail",
        "Real-time oversight",
        "Communication with stakeholders",
        "Rollback capability"
      ]
    }
  }
}
```

### Emergency Bypass Procedure

```javascript
function requestEmergencyBypass(bypassRequest) {
  // Step 1: Validate emergency conditions
  if (!validateEmergencyConditions(bypassRequest)) {
    return {
      status: "denied",
      reason: "Emergency conditions not met"
    };
  }

  // Step 2: Verify authorization
  const authorized = verifyBypassAuthorization(
    bypassRequest.authorized_by,
    bypassRequest.scenario
  );

  if (!authorized) {
    return {
      status: "denied",
      reason: "Insufficient authorization for emergency bypass"
    };
  }

  // Step 3: Create emergency permit
  const emergencyPermit = {
    permit_id: generatePermitId("emergency"),
    permit_type: "emergency_bypass",
    status: "active",
    issued_at: new Date().toISOString(),

    granted_to: {
      worker_id: bypassRequest.worker_id,
      temporary_level: 3,
      original_level: bypassRequest.worker_certification_level
    },

    emergency_details: {
      scenario: bypassRequest.scenario,
      incident_id: bypassRequest.incident_ticket,
      authorized_by: bypassRequest.authorized_by,
      justification: bypassRequest.justification
    },

    time_constraints: {
      expires_at: calculateEmergencyExpiration(bypassRequest.scenario),
      max_duration_minutes: getScenarioDuration(bypassRequest.scenario),
      auto_revoke: true
    },

    enhanced_monitoring: {
      real_time_oversight: true,
      continuous_logging: true,
      alert_on_any_action: true,
      screen_recording_if_available: true
    },

    post_emergency_requirements: {
      post_incident_review: {
        required: true,
        due_within_hours: 24,
        attendees: ["incident_commander", "security_team", "engineering_lead"]
      },
      detailed_report: {
        required: true,
        template: "emergency_bypass_report_v1",
        must_include: ["actions_taken", "justification", "alternatives_considered", "lessons_learned"]
      }
    }
  };

  // Step 4: Activate enhanced monitoring
  activateEnhancedMonitoring(emergencyPermit);

  // Step 5: Notify all stakeholders
  notifyEmergencyBypass(emergencyPermit);

  // Step 6: Log emergency bypass
  logEmergencyBypass(emergencyPermit);

  return {
    status: "approved",
    permit: emergencyPermit,
    message: "Emergency bypass granted. Enhanced monitoring active. Post-incident review required."
  };
}
```

## Audit Requirements per Permit Type

### Audit Trail Schema

```json
{
  "$schema": "https://cortex.ai/schemas/permit-audit/v1.0.0",
  "audit_trail_id": "audit-{uuid}",
  "permit_id": "permit-{uuid}",
  "permit_type": "string",
  "certification_level": 0,

  "lifecycle": {
    "request": {
      "requested_at": "ISO-8601",
      "requested_by": {
        "agent_type": "string",
        "agent_id": "string"
      },
      "request_hash": "sha256",
      "request_signature": "digital_signature"
    },

    "approval": {
      "approvals": [
        {
          "approver_id": "string",
          "approver_role": "string",
          "approved_at": "ISO-8601",
          "approval_method": "web_ui|api|cli",
          "ip_address": "string",
          "decision": "approved|rejected|changes_requested",
          "conditions": ["string"],
          "reasoning": "string",
          "approval_signature": "digital_signature"
        }
      ],
      "final_approval_at": "ISO-8601"
    },

    "issuance": {
      "issued_at": "ISO-8601",
      "issued_by": "permit_system",
      "permit_hash": "sha256",
      "permit_signature": "digital_signature"
    },

    "execution": {
      "execution_id": "string",
      "started_at": "ISO-8601",
      "executed_by": {
        "worker_id": "string",
        "worker_type": "string",
        "certification_level": 0
      },
      "execution_host": "string",
      "execution_context": {
        "environment": "string",
        "region": "string",
        "services": ["string"]
      },

      "operations_log": [
        {
          "timestamp": "ISO-8601",
          "operation": "string",
          "parameters": {},
          "result": "success|failure|partial",
          "duration_ms": 0,
          "resources_affected": ["string"],
          "data_accessed": ["string"],
          "data_modified": ["string"]
        }
      ],

      "completed_at": "ISO-8601",
      "outcome": "success|failure|partial|cancelled"
    },

    "monitoring": {
      "constraint_checks": [
        {
          "timestamp": "ISO-8601",
          "constraint": "string",
          "status": "passed|failed|warning",
          "value": 0,
          "threshold": 0
        }
      ],
      "alerts_triggered": [
        {
          "timestamp": "ISO-8601",
          "alert_type": "string",
          "severity": "string",
          "message": "string"
        }
      ],
      "safety_violations": []
    },

    "closure": {
      "closed_at": "ISO-8601",
      "closed_by": "string",
      "final_status": "string",
      "validation_results": {},
      "rollback_available": true|false,
      "post_execution_notes": "string"
    }
  },

  "compliance": {
    "frameworks": ["string"],
    "controls_applied": ["string"],
    "attestations": [
      {
        "framework": "string",
        "control": "string",
        "status": "compliant|non_compliant|not_applicable",
        "evidence": "string"
      }
    ]
  },

  "data_classification": {
    "contains_pii": true|false,
    "contains_phi": true|false,
    "contains_financial": true|false,
    "contains_credentials": true|false,
    "data_retention_years": 0
  }
}
```

### Audit Requirements by Level

```json
{
  "level_1_read_only": {
    "audit_level": "basic",
    "required_logs": [
      "operation_timestamp",
      "worker_id",
      "operation_type",
      "resources_accessed",
      "duration",
      "outcome"
    ],
    "retention_days": 90,
    "real_time_monitoring": false,
    "log_destinations": ["audit_log", "metrics"]
  },

  "level_2_standard": {
    "audit_level": "standard",
    "required_logs": [
      "operation_timestamp",
      "worker_id",
      "operation_type",
      "input_parameters",
      "output_results",
      "resources_accessed",
      "resources_modified",
      "approver_id",
      "approval_timestamp",
      "duration",
      "outcome",
      "error_conditions"
    ],
    "retention_days": 365,
    "real_time_monitoring": true,
    "alerting": true,
    "log_destinations": ["audit_log", "metrics", "dashboard", "compliance_log"]
  },

  "level_3_advanced": {
    "audit_level": "comprehensive",
    "required_logs": [
      "operation_timestamp",
      "worker_id",
      "certification_level",
      "operation_type",
      "input_parameters",
      "output_results",
      "data_accessed",
      "data_modified",
      "resources_accessed",
      "resources_modified",
      "approver_ids",
      "approval_timestamps",
      "security_context",
      "compliance_tags",
      "rollback_capability",
      "duration",
      "outcome",
      "error_conditions",
      "constraint_validations"
    ],
    "retention_days": 2555,
    "real_time_monitoring": true,
    "alerting": true,
    "security_monitoring": true,
    "compliance_reporting": true,
    "log_destinations": ["audit_log", "security_log", "compliance_log", "metrics", "dashboard"]
  },

  "level_4_master": {
    "audit_level": "exhaustive",
    "required_logs": [
      "operation_timestamp",
      "worker_id",
      "certification_level",
      "operation_type",
      "input_parameters",
      "output_results",
      "data_accessed",
      "data_modified",
      "systems_affected",
      "resources_accessed",
      "resources_modified",
      "approver_ids",
      "approval_timestamps",
      "approval_reasoning",
      "security_context",
      "compliance_tags",
      "change_justification",
      "risk_assessment",
      "impact_analysis",
      "rollback_capability",
      "rollback_tested",
      "duration",
      "outcome",
      "error_conditions",
      "constraint_validations",
      "stakeholder_notifications"
    ],
    "retention_days": 2555,
    "real_time_monitoring": true,
    "alerting": true,
    "security_monitoring": true,
    "compliance_reporting": true,
    "executive_visibility": true,
    "external_audit_ready": true,
    "log_destinations": ["audit_log", "security_log", "compliance_log", "executive_dashboard", "metrics", "dashboard", "external_audit_system"]
  },

  "emergency": {
    "audit_level": "enhanced",
    "required_logs": [
      "All level_3_advanced logs",
      "emergency_justification",
      "incident_id",
      "authorized_by",
      "real_time_oversight_log",
      "continuous_action_log",
      "post_incident_review_id"
    ],
    "retention_days": 2555,
    "real_time_monitoring": true,
    "real_time_oversight": "mandatory",
    "screen_recording": "if_available",
    "continuous_logging": true,
    "alert_on_any_action": true,
    "log_destinations": ["audit_log", "security_log", "incident_log", "compliance_log", "dashboard"]
  }
}
```

## Rollback Requirements for Approved Permits

### Rollback Strategy Matrix

```json
{
  "rollback_strategies": {
    "automated": {
      "description": "Fully automated rollback triggered by monitoring",
      "required_for": ["deployment", "configuration_update", "feature_flag"],
      "implementation": {
        "rollback_script": "required",
        "rollback_tested": true,
        "max_rollback_time_minutes": 15,
        "trigger_conditions": [
          "error_rate > threshold",
          "latency > threshold",
          "health_check_failure",
          "manual_trigger"
        ]
      },
      "validation": {
        "pre_deployment": "test_rollback_in_staging",
        "monitoring": "continuous",
        "success_criteria": "service_health_restored"
      }
    },

    "blue_green": {
      "description": "Zero-downtime deployment with instant rollback",
      "required_for": ["critical_service_deployment", "database_cutover"],
      "implementation": {
        "maintain_old_version": true,
        "traffic_switching": "instant",
        "max_rollback_time_minutes": 5,
        "cleanup_after_hours": 24
      },
      "validation": {
        "both_versions_tested": true,
        "traffic_routing_tested": true,
        "rollback_rehearsed": true
      }
    },

    "canary": {
      "description": "Gradual rollout with progressive rollback",
      "required_for": ["high_risk_deployment", "performance_sensitive_change"],
      "implementation": {
        "rollout_stages": [1, 10, 25, 50, 100],
        "stage_duration_minutes": 30,
        "rollback_at_any_stage": true,
        "max_rollback_time_minutes": 20
      },
      "validation": {
        "metrics_per_stage": true,
        "automatic_rollback_configured": true,
        "manual_override_available": true
      }
    },

    "manual": {
      "description": "Documented manual rollback procedure",
      "required_for": ["database_migration", "infrastructure_change", "data_migration"],
      "implementation": {
        "procedure_documented": true,
        "procedure_url": "required",
        "estimated_rollback_time_minutes": "required",
        "team_trained": true,
        "on_call_available": true
      },
      "validation": {
        "procedure_reviewed": true,
        "dry_run_completed": "recommended",
        "dependencies_documented": true
      }
    },

    "backup_restore": {
      "description": "Restore from backup if rollback not possible",
      "required_for": ["data_migration", "destructive_operation"],
      "implementation": {
        "backup_created": "before_operation",
        "backup_verified": true,
        "restore_procedure": "documented",
        "estimated_restore_time_minutes": "required",
        "data_loss_acceptable": "specified"
      },
      "validation": {
        "backup_tested": true,
        "restore_tested": "within_30_days",
        "rpo_documented": true,
        "rto_documented": true
      }
    }
  },

  "rollback_requirements_by_permit_type": {
    "read_only": {
      "rollback_strategy": "none",
      "reason": "No modifications made"
    },
    "standard_production": {
      "rollback_strategy": "automated",
      "fallback_strategy": "manual",
      "rollback_tested": true,
      "max_rollback_time_minutes": 30
    },
    "advanced_production": {
      "rollback_strategy": "blue_green|canary",
      "fallback_strategy": "manual",
      "rollback_tested": true,
      "rollback_rehearsed": true,
      "max_rollback_time_minutes": 15
    },
    "master_production": {
      "rollback_strategy": "blue_green",
      "fallback_strategy": "manual",
      "rollback_tested": true,
      "rollback_rehearsed": true,
      "rollback_documented": "comprehensive",
      "max_rollback_time_minutes": 10
    },
    "emergency": {
      "rollback_strategy": "automated|manual",
      "rollback_available": "required",
      "max_rollback_time_minutes": 20
    },
    "destructive": {
      "rollback_strategy": "backup_restore",
      "backup_verified": true,
      "data_loss_acceptable": "documented",
      "restore_tested": true
    }
  }
}
```

### Rollback Validation

```javascript
function validateRollbackRequirements(permit) {
  const requirements = getRollbackRequirements(permit.permit_type);
  const validation = {
    permit_id: permit.permit_id,
    permit_type: permit.permit_type,
    rollback_validation: [],
    overall_status: "passed"
  };

  // Check rollback strategy
  if (requirements.rollback_strategy !== "none") {
    const hasStrategy = permit.technical_requirements.rollback.strategy !== "none";
    validation.rollback_validation.push({
      requirement: "rollback_strategy_defined",
      status: hasStrategy ? "passed" : "failed",
      value: permit.technical_requirements.rollback.strategy,
      expected: requirements.rollback_strategy
    });

    if (!hasStrategy) validation.overall_status = "failed";
  }

  // Check if procedure documented
  if (requirements.rollback_documented) {
    const hasDoc = permit.technical_requirements.rollback.procedure_documented;
    validation.rollback_validation.push({
      requirement: "rollback_procedure_documented",
      status: hasDoc ? "passed" : "failed",
      evidence: permit.technical_requirements.rollback.procedure_url
    });

    if (!hasDoc) validation.overall_status = "failed";
  }

  // Check if tested
  if (requirements.rollback_tested) {
    const isTested = permit.technical_requirements.rollback.tested;
    validation.rollback_validation.push({
      requirement: "rollback_tested",
      status: isTested ? "passed" : "failed",
      test_date: permit.technical_requirements.rollback.test_date
    });

    if (!isTested) validation.overall_status = "failed";
  }

  // Check rollback time
  if (requirements.max_rollback_time_minutes) {
    const estimatedTime = permit.technical_requirements.rollback.estimated_rollback_time_minutes;
    const withinLimit = estimatedTime <= requirements.max_rollback_time_minutes;

    validation.rollback_validation.push({
      requirement: "rollback_time_within_limit",
      status: withinLimit ? "passed" : "warning",
      estimated: estimatedTime,
      max_allowed: requirements.max_rollback_time_minutes
    });

    if (!withinLimit) validation.overall_status = "warning";
  }

  return validation;
}
```

## Integration with PM State Machine

### PM State Machine Integration Points

```json
{
  "pm_integration": {
    "task_planning": {
      "when": "PM planning phase",
      "action": "Identify tasks requiring permits",
      "integration": {
        "scan_task_definitions": true,
        "flag_production_operations": true,
        "estimate_permit_approval_time": true,
        "include_in_timeline": true
      }
    },

    "task_handoff": {
      "when": "PM creates division handoff",
      "action": "Check if permit required",
      "integration": {
        "evaluate_task_risk": true,
        "determine_permit_type": true,
        "create_permit_request_if_needed": true,
        "block_handoff_until_permit_approved": true
      }
    },

    "permit_request_from_pm": {
      "when": "PM requests permit for upcoming task",
      "process": [
        "PM analyzes task",
        "PM creates permit request",
        "Permit system routes to approvers",
        "Approvers review and approve",
        "Permit issued",
        "PM proceeds with task handoff"
      ],
      "timeline_impact": {
        "level_1": "0-4 hours",
        "level_2": "4-24 hours",
        "level_3": "24-48 hours",
        "level_4": "7 days"
      }
    },

    "task_execution": {
      "when": "Division worker executes task",
      "action": "Validate permit before execution",
      "integration": {
        "check_permit_active": true,
        "validate_worker_certification": true,
        "verify_time_window": true,
        "enforce_constraints": true,
        "log_all_operations": true
      }
    },

    "task_completion": {
      "when": "Division completes task",
      "action": "Close permit and audit",
      "integration": {
        "validate_deliverables": true,
        "check_constraints_met": true,
        "close_permit": true,
        "generate_audit_report": true,
        "update_pm_state": true
      }
    },

    "task_failure": {
      "when": "Task fails or blocked",
      "action": "Handle permit accordingly",
      "integration": {
        "trigger_rollback_if_configured": true,
        "revoke_permit_if_needed": true,
        "create_incident_if_serious": true,
        "notify_pm_and_approvers": true
      }
    }
  }
}
```

### PM Workflow with Permits

```javascript
// PM planning phase - identify permit requirements
function planProjectWithPermits(project) {
  const tasks = project.tasks;
  const permitRequirements = [];

  for (const task of tasks) {
    const requiresPermit = evaluatePermitRequirement(task);

    if (requiresPermit) {
      const permitReq = {
        task_id: task.id,
        permit_type: requiresPermit.type,
        approval_time_hours: requiresPermit.sla_hours,
        prerequisite_for_task: true
      };

      permitRequirements.push(permitReq);

      // Adjust task timeline to account for permit approval
      task.actual_start_time = addHours(
        task.planned_start_time,
        requiresPermit.sla_hours
      );
    }
  }

  project.permit_requirements = permitRequirements;
  project.timeline_adjusted_for_permits = true;

  return project;
}

// PM task handoff - request permit
async function handoffTaskWithPermit(pm, task, division) {
  // Check if permit required
  const permitReq = evaluatePermitRequirement(task);

  if (!permitReq) {
    // No permit required, proceed with handoff
    return issueHandoff(pm, task, division);
  }

  // Permit required - check if already approved
  const existingPermit = findPermit(task.id);

  if (existingPermit && existingPermit.status === "active") {
    // Permit already approved, proceed with handoff
    return issueHandoffWithPermit(pm, task, division, existingPermit);
  }

  // Need to request permit
  pm.log(`Task ${task.id} requires ${permitReq.type} permit. Requesting approval...`);

  const permitRequest = createPermitRequest({
    task: task,
    pm_id: pm.id,
    project_id: pm.project.id,
    permit_type: permitReq.type
  });

  const permit = await requestPermit(permitRequest);

  if (permit.routing === "auto_approve") {
    // Auto-approved, proceed immediately
    pm.log(`Permit auto-approved for task ${task.id}`);
    return issueHandoffWithPermit(pm, task, division, permit);
  }

  // Waiting for approval
  pm.log(`Permit request sent for task ${task.id}. Waiting for approval (SLA: ${permitReq.sla_hours}h)`);
  pm.updateProjectState({
    status: "waiting_for_permit_approval",
    blocked_task_id: task.id,
    permit_request_id: permit.permit_request_id
  });

  // Set up monitoring for permit approval
  monitorPermitApproval(pm, permit, task, division);
}

// Worker execution - validate permit
function executeTaskWithPermit(worker, task, permit) {
  // Pre-flight validation
  const validation = validatePermitForExecution(permit, worker, task);

  if (!validation.valid) {
    throw new Error(`Permit validation failed: ${validation.reason}`);
  }

  // Execute with permit context
  const execution = {
    execution_id: generateExecutionId(),
    permit_id: permit.permit_id,
    task_id: task.id,
    worker_id: worker.id,
    started_at: new Date().toISOString()
  };

  // Activate monitoring
  activatePermitMonitoring(permit, execution);

  try {
    // Perform task
    const result = worker.execute(task);

    // Validate results against permit constraints
    validateResultsAgainstConstraints(result, permit);

    // Log success
    logPermitExecution(permit, execution, "success", result);

    return result;

  } catch (error) {
    // Log failure
    logPermitExecution(permit, execution, "failure", error);

    // Trigger rollback if configured
    if (permit.safety_constraints.auto_rollback_on_error) {
      triggerRollback(execution, permit);
    }

    throw error;
  } finally {
    // Deactivate monitoring
    deactivatePermitMonitoring(permit, execution);
  }
}
```

## Common Operation Examples

### Example 1: API Deployment to Production

```json
{
  "permit_request_id": "req-api-deploy-001",
  "requested_by": {
    "agent_type": "pm",
    "agent_id": "pm-proj-123",
    "project_id": "proj-api-v2",
    "task_id": "task-deploy-prod"
  },

  "operation_details": {
    "operation_type": "deployment",
    "operation_subtype": "api_service_deployment",
    "description": "Deploy API v2.1.0 to production",
    "justification": "New features for Q1 release + critical bug fixes",

    "target": {
      "environment": "production",
      "region": "us-east-1",
      "services": ["api-service"],
      "components": ["api-v2", "cache-layer"]
    },

    "timing": {
      "urgency": "normal",
      "requested_start": "2025-12-15T02:00:00Z",
      "requested_end": "2025-12-15T04:00:00Z",
      "estimated_duration_minutes": 45,
      "preferred_windows": ["2025-12-15T02:00:00Z/2025-12-15T04:00:00Z"]
    },

    "impact_assessment": {
      "customer_facing": true,
      "service_interruption": "none",
      "estimated_downtime_seconds": 0,
      "affected_users": "all",
      "data_modification": false,
      "reversibility": "automated_rollback"
    }
  },

  "risk_assessment": {
    "risk_score": 18,
    "risk_level": "medium",
    "risk_factors": [
      {"category": "environment", "factor": "production", "score": 10},
      {"category": "customer_impact", "factor": "customer_facing", "score": 8},
      {"category": "reversibility", "factor": "automated_rollback", "score": 3}
    ],
    "calculated_certification_level": 2,
    "mitigation_strategies": [
      {"risk": "Deployment failure", "mitigation": "Blue-green deployment with instant rollback", "status": "implemented"},
      {"risk": "Performance degradation", "mitigation": "Canary release to 10% first", "status": "implemented"}
    ]
  },

  "certification_requirements": {
    "minimum_level": 2,
    "required_certifications": ["production_deployment"],
    "approvers_required": 1,
    "approver_roles": ["engineering_manager", "tech_lead"]
  },

  "technical_requirements": {
    "testing": {
      "unit_tests": "required",
      "integration_tests": "required",
      "performance_tests": "required",
      "test_results_url": "https://ci.cortex.ai/builds/12345",
      "test_coverage": 0.91
    },
    "code_review": {
      "required": true,
      "reviewers_required": 2,
      "review_url": "https://github.com/cortex/api/pull/456",
      "status": "approved"
    },
    "rollback": {
      "strategy": "blue_green",
      "procedure_documented": true,
      "procedure_url": "https://docs.cortex.ai/runbooks/api-rollback",
      "tested": true,
      "test_date": "2025-12-10T14:00:00Z",
      "estimated_rollback_time_minutes": 5
    },
    "monitoring": {
      "dashboard_url": "https://grafana.cortex.ai/api-production",
      "key_metrics": ["request_rate", "error_rate", "latency_p99"],
      "alert_rules": ["error_rate_>_1%", "latency_p99_>_500ms"],
      "on_call_team": "api-team"
    }
  }
}
```

**Approval Flow**: Auto-routed to engineering manager → Approved in 6 hours → Permit issued → Deployment executed → Success

---

### Example 2: Database Migration with PII

```json
{
  "permit_request_id": "req-db-migrate-001",
  "requested_by": {
    "agent_type": "master",
    "agent_id": "development-master",
    "task_id": "task-user-schema-migration"
  },

  "operation_details": {
    "operation_type": "migration",
    "operation_subtype": "database_schema_migration",
    "description": "Add email_verified column to users table",
    "justification": "Support email verification workflow for compliance",

    "target": {
      "environment": "production",
      "region": "us-east-1",
      "services": ["postgresql-primary"],
      "components": ["users_table"]
    },

    "timing": {
      "urgency": "normal",
      "requested_start": "2025-12-20T03:00:00Z",
      "requested_end": "2025-12-20T05:00:00Z",
      "estimated_duration_minutes": 90
    },

    "impact_assessment": {
      "customer_facing": false,
      "service_interruption": "none",
      "estimated_downtime_seconds": 0,
      "affected_users": "none",
      "data_modification": true,
      "reversibility": "manual_rollback"
    }
  },

  "risk_assessment": {
    "risk_score": 33,
    "risk_level": "high",
    "risk_factors": [
      {"category": "environment", "factor": "production", "score": 10},
      {"category": "operation_type", "factor": "database_migration", "score": 10},
      {"category": "data_sensitivity", "factor": "pii", "score": 10},
      {"category": "reversibility", "factor": "manual_rollback", "score": 7}
    ],
    "calculated_certification_level": 3,
    "mitigation_strategies": [
      {"risk": "Migration failure", "mitigation": "Tested migration on staging replica", "status": "implemented"},
      {"risk": "Data corruption", "mitigation": "Full database backup verified", "status": "implemented"},
      {"risk": "Long-running migration", "mitigation": "Online migration with pt-online-schema-change", "status": "planned"}
    ]
  },

  "certification_requirements": {
    "minimum_level": 3,
    "required_certifications": ["database_operations", "pii_handling"],
    "approvers_required": 2,
    "approver_roles": ["engineering_director", "security_lead"]
  },

  "technical_requirements": {
    "testing": {
      "migration_tested_on_replica": true,
      "rollback_tested": true,
      "data_integrity_validated": true
    },
    "rollback": {
      "strategy": "backup_restore",
      "backup_created": true,
      "backup_verified": true,
      "estimated_rollback_time_minutes": 120
    }
  },

  "compliance_requirements": {
    "frameworks": ["GDPR", "SOC2"],
    "controls": ["data_protection", "change_management"],
    "attestation_required": true
  }
}
```

**Approval Flow**: Routed to engineering director + security lead → Both approve in 32 hours → Permit issued → Migration rehearsed → Executed successfully

---

### Example 3: Emergency Hotfix

```json
{
  "permit_request_id": "req-emergency-001",
  "requested_by": {
    "agent_type": "worker",
    "agent_id": "worker-incident-001",
    "incident_id": "inc-prod-outage-789"
  },

  "operation_details": {
    "operation_type": "emergency_fix",
    "operation_subtype": "hotfix_deployment",
    "description": "Deploy hotfix for production API outage",
    "justification": "Production API returning 500 errors - 100% customer impact",

    "target": {
      "environment": "production",
      "region": "us-east-1",
      "services": ["api-service"]
    },

    "timing": {
      "urgency": "emergency",
      "requested_start": "immediate",
      "estimated_duration_minutes": 15
    },

    "impact_assessment": {
      "customer_facing": true,
      "service_interruption": "full",
      "affected_users": "all",
      "reversibility": "automated_rollback"
    }
  },

  "emergency_context": {
    "incident_id": "inc-prod-outage-789",
    "incident_severity": 1,
    "incident_started_at": "2025-12-09T14:30:00Z",
    "customer_impact": "All API requests failing",
    "incident_commander": "user-jane-doe"
  },

  "risk_assessment": {
    "risk_score": 45,
    "risk_level": "critical",
    "calculated_certification_level": 3
  }
}
```

**Approval Flow**: Emergency routing → Incident commander approves in 5 minutes → Emergency permit issued (1-hour expiration) → Hotfix deployed → Service restored → Post-incident review scheduled

---

## Summary

The Permit Workflow System ensures:

1. **Authorization**: All production changes require explicit approval
2. **Risk Management**: Operations routed based on risk assessment
3. **Auditability**: Comprehensive audit trails for compliance
4. **Safety**: Rollback procedures and constraints enforced
5. **Flexibility**: Emergency procedures for critical incidents
6. **Integration**: Seamless integration with PM state machine and worker certification

This system balances operational safety with development velocity, ensuring Cortex operates reliably in production environments while maintaining agility for rapid development.
