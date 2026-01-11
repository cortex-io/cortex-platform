# Worker Certification System

## Overview

The Worker Certification System is Cortex's safety layer that distinguishes between **Union Workers** (certified, audited, production-grade) and **Non-Union Workers** (fast, flexible, dev/test). This prevents cowboy operations in production while maintaining development velocity.

## System Components

### 1. [WORKER_CERTIFICATION.md](./WORKER_CERTIFICATION.md)
**Complete certification system guide**

Explains:
- Union vs Non-Union worker concepts
- When to use each worker type
- Certification levels (0-4)
- Approval workflows (fast path, standard path, critical path)
- Safety rules and enforcement
- Certification process and requirements
- Audit requirements by level
- Emergency procedures
- Best practices

**Start here** to understand the certification system.

### 2. [union-requirements.json](./union-requirements.json)
**Union worker rules and requirements**

Defines:
- Hard requirements (always require union workers)
- Production indicators (environment detection)
- Audit requirements by certification level
- Approval gates and workflows
- Certification requirements for each level
- Safety boundaries (hard blocks)
- Risk assessment matrix
- Compliance mappings (SOC2, HIPAA, PCI-DSS, GDPR, SOX)

**Use this** when determining if a task requires union certification.

### 3. [non-union-guidelines.json](./non-union-guidelines.json)
**Non-union worker guidelines**

Defines:
- Allowed task patterns
- Environment indicators (dev/test detection)
- Auto-approval rules
- Resource limits
- Safety boundaries
- Fast-path workflows
- Testing requirements (lighter)
- Documentation requirements (minimal)
- Error handling approach
- Promotion criteria (when to upgrade to union)

**Use this** for development and testing operations.

### 4. [certification-checker.md](./certification-checker.md)
**Agent prompt for certification analysis**

Provides:
- Task analysis framework
- Environment detection logic
- Data sensitivity assessment
- Operation risk analysis
- Impact scope calculation
- Risk score calculation
- Decision matrix with examples
- Safety enforcement rules
- Routing logic (union vs non-union)
- Permit issuance process
- Integration with masters

**Use this** as a prompt for agents analyzing tasks.

### 5. [permit-system.md](./permit-system.md)
**Production change authorization system**

Explains:
- What permits are and why they're needed
- Permit lifecycle (7 stages)
- Permit types (standard, advanced, master, emergency)
- Approval workflows
- Who can approve what
- Audit trail requirements
- Permit revocation
- Permit templates for common operations
- Compliance integration

**Use this** when requesting production access.

### 6. [rollback-plans.md](./rollback-plans.md)
**Rollback procedures and safety net**

Provides:
- Required rollback documentation for all union operations
- Rollback plan templates with real examples
- Automatic rollback trigger definitions
- Rollback verification procedures
- Partial rollback strategies
- Rollback testing requirements
- Time-bound SLAs by certification level
- Rollback failure escalation procedures
- Post-rollback validation checklists
- Rollback metrics and reporting

**Use this** to create and execute rollback plans.

### 7. [rollback-plans.json](./rollback-plans.json)
**Rollback schemas and configurations**

Defines:
- Rollback plan schema and required fields
- Trigger definitions for automatic rollback
- Verification checklist templates
- Rollback SLAs by level and operation type
- Automation level requirements
- Partial rollback scenario patterns
- Example rollback plans (K8s, Terraform, Database, N8N)

**Use this** for rollback automation and validation.

### 8. [rollback-plans-quick-reference.md](./rollback-plans-quick-reference.md)
**Fast rollback reference guide**

Quick access to:
- Rollback checklist by level
- Common rollback commands (K8s, Terraform, DB, N8N)
- Automatic trigger thresholds
- Rollback time SLAs
- Verification scripts
- Partial rollback scenarios
- Escalation procedures
- Testing requirements

**Use this** for quick rollback execution and reference.

## Quick Start

### For Masters

When receiving a task:

```bash
# 1. Analyze task with certification checker
task_analysis=$(analyze_task_for_certification "$task_json")

# 2. Determine worker type
worker_type=$(echo "$task_analysis" | jq -r '.certification_decision.worker_type')

# 3. Route accordingly
if [ "$worker_type" = "non-union" ]; then
  # Fast path - instant approval
  spawn_non_union_worker "$task_json"
else
  # Union path - request permit
  cert_level=$(echo "$task_analysis" | jq -r '.certification_decision.certification_level_required')
  request_permit "$task_json" "$cert_level"
  wait_for_approvals
  spawn_union_worker "$task_json" "$cert_level"
fi
```

### For Workers

Check your certification before operations:

```javascript
// Before any operation
function checkPermit(operation) {
  if (operation.environment === 'production') {
    if (worker.certification_level < 2) {
      throw new Error('Production access requires Level 2+ certification');
    }

    const permit = getActivePermit(worker.id);
    if (!permit) {
      throw new Error('No active permit for production operations');
    }

    validatePermit(permit, operation);
  }
}
```

### For Developers

Default to non-union for all dev work:

```javascript
// Development operations are auto-approved
const task = {
  environment: 'development',
  operations: ['feature_implementation'],
  data_types: ['test_data']
};

// This will use non-union worker (fast path)
cortex.executeTask(task);
```

## Decision Tree

```
Task Received
    |
    v
Environment Check
    |
    +--> Development/Test? --> Non-Union Worker ✓ (instant)
    |
    +--> Production? --> Check Data Sensitivity
                            |
                            +--> No Sensitive Data? --> Check Operation Risk
                            |                               |
                            |                               +--> Low Risk? --> Level 2 Union (1 approval)
                            |                               |
                            |                               +--> High Risk? --> Level 3 Union (2 approvals)
                            |
                            +--> Sensitive Data (PII/PHI/Financial)? --> Level 3+ Union (2+ approvals)
```

## Safety Boundaries

### Hard Blocks (Cannot Override)

1. **Non-union workers cannot access production** - Period. No exceptions.
2. **Sensitive data requires Level 3+** - PII/PHI/Financial data needs advanced certification.
3. **Cannot skip required approvals** - Except emergency override with incident ticket.
4. **All Level 2+ operations must be logged** - Comprehensive audit trail required.

### Soft Blocks (Override with Justification)

1. **Extended token usage** - Can request with business justification.
2. **Expedited approval** - Can fast-track with executive sponsor.

## Certification Levels Summary

| Level | Type | Use Case | Approvers | Approval Time |
|-------|------|----------|-----------|---------------|
| 0 | Non-Union | Dev/test only | None (auto) | Instant |
| 1 | Basic | Read-only prod | 1 (auto/basic) | Minutes |
| 2 | Standard Union | Production deploys | 1 manager | Hours |
| 3 | Advanced Union | Critical systems, sensitive data | 2 directors | Days |
| 4 | Master Union | System-wide, multi-region | 3+ executives | Weeks |

## Risk Scoring

Tasks are scored 0-50 based on:
- Environment risk (0-10)
- Reversibility risk (0-10)
- Data sensitivity risk (0-10)
- Impact scope risk (0-10)
- Customer impact risk (0-10)

**Thresholds**:
- 0-5: Non-union eligible
- 6-20: Level 2 union required
- 21-35: Level 3 union required
- 36+: Level 4 union required

## Compliance Mappings

| Framework | Minimum Level | Key Controls |
|-----------|---------------|--------------|
| SOC 2 | Level 2 | Change management, audit trails |
| HIPAA | Level 3 | PHI protection, encryption, audit |
| PCI-DSS | Level 3 | Payment security, network segmentation |
| GDPR | Level 3 | Data protection, consent management |
| SOX | Level 4 | Financial controls, segregation of duties |

## Examples

### Example 1: Feature Development (Non-Union)
```json
{
  "task": "Implement user profile feature",
  "environment": "development",
  "risk_score": 2,
  "decision": "non-union",
  "approval": "instant",
  "duration": "30 minutes"
}
```

### Example 2: Production Deployment (Level 2 Union)
```json
{
  "task": "Deploy API v2.1 to production",
  "environment": "production",
  "risk_score": 18,
  "decision": "level_2_union",
  "approval": "1 manager, 24hrs max",
  "duration": "2 hours"
}
```

### Example 3: Database Migration (Level 3 Union)
```json
{
  "task": "Migrate customer data schema",
  "environment": "production",
  "data": "customer_pii",
  "risk_score": 32,
  "decision": "level_3_union",
  "approval": "2 directors, 48hrs max",
  "duration": "4 hours",
  "requires": ["security_review", "tested_rollback"]
}
```

### Example 4: Multi-Region Infrastructure (Level 4 Union)
```json
{
  "task": "Deploy new data center region",
  "environment": "production_multi_region",
  "risk_score": 45,
  "decision": "level_4_union",
  "approval": "3 executives + CAB, 7 days",
  "duration": "weeks",
  "requires": ["architecture_review", "disaster_recovery_tested"]
}
```

## Integration Points

### With Masters
- Masters call certification checker before spawning workers
- Masters request permits for union workers
- Masters monitor worker execution
- Masters close permits after completion

### With Dashboard
- Real-time permit status display
- Approval request interface
- Audit log viewer
- Metrics and compliance reporting

### With Governance
- Policy enforcement
- Compliance verification
- Incident tracking
- Certification management

## Metrics

Track system effectiveness:
- **Certification accuracy**: % correct level assignments
- **Approval time**: Time to approve by level
- **Success rate**: % successful operations by level
- **Safety violations**: Should be 0
- **False positives**: Over-certification rate (target <10%)
- **False negatives**: Under-certification rate (target <1%)

## Files Reference

```
worker-certification/
├── README.md                            # This file - system overview
├── WORKER_CERTIFICATION.md              # Complete guide (11KB)
├── union-requirements.json              # Union rules (16KB)
├── non-union-guidelines.json            # Non-union rules (15KB)
├── certification-checker.md             # Analysis agent prompt (14KB)
├── permit-system.md                     # Authorization system (20KB)
├── rollback-plans.md                    # Rollback procedures (30KB)
├── rollback-plans.json                  # Rollback schemas (31KB)
└── rollback-plans-quick-reference.md    # Quick rollback guide (9KB)
```

## Philosophy

**For Production**: Be conservative. Safety over speed. When in doubt, require certification.

**For Development**: Be liberal. Speed over process. When in doubt, allow non-union.

**Balance**: Right-size certification to risk. Don't over-certify (slows development), don't under-certify (creates incidents).

## Support

- **Questions**: Check WORKER_CERTIFICATION.md first
- **Rule Clarification**: See union-requirements.json or non-union-guidelines.json
- **Task Analysis**: Use certification-checker.md framework
- **Permit Issues**: Consult permit-system.md
- **Rollback Planning**: Use rollback-plans.md template and rollback-plans.json schema

## Conclusion

The Worker Certification System is your safety net. It prevents production incidents while enabling rapid development. Use it correctly:

1. **Default to non-union** for all dev/test work
2. **Require union certification** for production
3. **Right-size the certification level** to the risk
4. **Follow approval workflows** - no shortcuts
5. **Maintain audit trails** - comprehensive logging
6. **Learn from outcomes** - improve the system

When implemented correctly, you get both safety AND velocity.
