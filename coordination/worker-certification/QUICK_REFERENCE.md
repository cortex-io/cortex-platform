# Worker Certification Quick Reference

## One-Minute Decision Guide

### Is this production?
- **NO** → Use Non-Union Worker (instant approval)
- **YES** → Continue to next question

### Does it access PII/PHI/Financial data?
- **YES** → Level 3+ Union Worker required (2+ approvals)
- **NO** → Continue to next question

### Is it a high-risk operation?
(Database migration, infrastructure change, security config, data deletion)
- **YES** → Level 3+ Union Worker required (2+ approvals)
- **NO** → Continue to next question

### Is it customer-facing or system-wide?
- **YES** → Level 2 Union Worker required (1 approval)
- **NO** → Non-Union Worker (instant approval)

---

## Certification Levels at a Glance

| Level | Name | Environment | Approvals | Time | Use Case |
|-------|------|-------------|-----------|------|----------|
| 0 | Non-Union | Dev/Test | None | Instant | Development, testing, documentation |
| 1 | Basic | Prod (read) | Auto/1 | Minutes | Monitoring, observability |
| 2 | Standard Union | Production | 1 | Hours | Standard deployments, config changes |
| 3 | Advanced Union | Prod Critical | 2 | Days | Sensitive data, critical systems, migrations |
| 4 | Master Union | Multi-region | 3+ | Weeks | Architecture changes, system-wide |

---

## Risk Score Calculator

```
Environment:     Prod=10, Staging=5, Dev=1, Local=0
Reversibility:   Irreversible=10, Complex=7, Auto=3, Full=0
Data:            PII/PHI/Fin=10, Internal=7, Test=3, Public=0
Impact:          Multi-region=10, System=8, Multi-service=6, Single=3
Customer Impact: All=10, Segment=7, Internal=3, None=0

Total Score → Certification Required:
  0-5:   Level 0 (Non-Union)
  6-20:  Level 2 (Union Standard)
  21-35: Level 3 (Union Advanced)
  36+:   Level 4 (Union Master)
```

---

## Hard Blocks (Cannot Override)

```
❌ Non-union workers in production
❌ Sensitive data without Level 3+
❌ Skip required approvals (except emergency)
❌ No audit trail for Level 2+ ops
❌ Cross-environment promotion without re-certification
```

---

## Environment Detection

### Production Indicators
```bash
# Environment variables
NODE_ENV=production, ENV=prod, ENVIRONMENT=production

# Hostnames
*.prod.*, *.production.*, api.*, www.*

# Branches
main, master, production, release/*

# Task flags
critical=true, production=true, customer_facing=true
```

### Non-Production Indicators
```bash
# Environment variables
NODE_ENV=development, ENV=dev, ENV=test, ENV=local

# Hostnames
localhost, *.local, *.dev, *.test, *-dev-*, *-test-*

# Branches
feature/*, bugfix/*, dev, develop, test

# Paths
/tmp/, ~/dev/, ~/projects/, */test/, */spec/
```

---

## Sensitive Data Patterns

**Level 3+ Required:**
- PII: email, phone, address, SSN, name, DOB
- PHI: medical records, health data, diagnoses
- Financial: credit card, bank account, payment info
- Credentials: passwords, API keys, tokens, certificates

---

## High-Risk Operations

**Level 3+ Required:**
- Database: `ALTER TABLE`, `DROP`, `TRUNCATE`, migrations
- Infrastructure: terraform, kubernetes, network changes
- Security: firewall, IAM, RBAC, encryption config
- Data deletion: `DELETE`, `DROP`, `TRUNCATE`, purge operations

---

## Approval Authority

| Level | Who Can Approve | How Many |
|-------|----------------|----------|
| 0 | Auto-approved | 0 |
| 1 | Engineering team member | 1 |
| 2 | Engineering manager, Tech lead, Senior engineer | 1 |
| 3 | Engineering director, Security lead, Architecture lead | 2 |
| 4 | VP Engineering, CTO, CISO, COO | 3+ |
| Emergency | Incident commander, On-call lead | 1 |

---

## Typical Token Allocations

| Level | Default Tokens | Extended (with justification) |
|-------|---------------|------------------------------|
| 0 (Non-Union) | 10,000 | 25,000 |
| 2 (Union) | 20,000 | 40,000 |
| 3 (Union) | 25,000 | 50,000 |
| 4 (Union) | 30,000 | 75,000 |

---

## Audit Log Requirements

### Level 0 (Non-Union)
```
Minimal: operation, timestamp, success/failure, errors
Retention: 30 days
```

### Level 2 (Union)
```
Required: operation, timestamp, worker_id, input, output,
          execution_time, errors, approver, approval_time
Retention: 90 days
```

### Level 3 (Union)
```
Comprehensive: All Level 2 fields plus:
               data_accessed, data_modified, security_context,
               compliance_tags, rollback_capability
Retention: 365 days
```

### Level 4 (Union)
```
Full Audit: All Level 3 fields plus:
            systems_affected, risk_assessment, impact_analysis,
            change_justification, rollback_tested
Retention: 7 years (2555 days)
```

---

## Fast Reference Commands

### Check Task Certification Requirement
```bash
# Analyze task
./certification-checker.sh task.json

# Extract decision
jq -r '.certification_decision.worker_type' analysis.json
```

### Request Permit
```bash
# Create permit request
cat > permit-request.json <<EOF
{
  "task_id": "$TASK_ID",
  "certification_level": 3,
  "approver_roles": ["engineering_director", "security_lead"]
}
EOF

# Submit request
./request-permit.sh permit-request.json
```

### Check Permit Status
```bash
# Get permit
jq '.status' permit-xyz789.json

# Check approvals
jq '.approvals | length' permit-xyz789.json
```

---

## Common Scenarios

### Scenario: Deploy feature to production
```
Environment: production ✓
Data: customer data ✓
Operation: deployment
Risk Score: 18
→ Level 2 Union Worker
→ 1 approval required
→ ~4 hours to approval
```

### Scenario: Database migration in production
```
Environment: production ✓
Data: customer + financial ✓✓
Operation: schema migration ✓✓
Risk Score: 45
→ Level 4 Union Worker
→ 3+ approvals + CAB
→ ~7 days to approval
```

### Scenario: Update documentation
```
Environment: any
Data: none
Operation: markdown edit
Risk Score: 0
→ Non-Union Worker
→ No approval needed
→ Instant execution
```

### Scenario: Bug fix in development
```
Environment: development
Data: test data
Operation: code change
Risk Score: 2
→ Non-Union Worker
→ No approval needed
→ Instant execution
```

---

## Emergency Override

**When to Use**: Production outage, security breach, data loss

**Requirements**:
- Active incident ticket
- Incident commander approval
- Real-time oversight (screen share)
- Auto-revocation after 1 hour
- Mandatory post-incident review

**Grant Temporary Level 3 Certification**

```bash
# Declare emergency
./emergency-override.sh \
  --incident-id INC-12345 \
  --commander user-jane-doe \
  --reason "Production outage affecting all customers" \
  --duration 60
```

---

## Permit Lifecycle (7 Steps)

```
1. Request  →  Master submits permit request
2. Review   →  Approvers evaluate request
3. Approval →  Required approvals obtained
4. Issuance →  Permit issued with constraints
5. Execute  →  Worker performs operations
6. Validate →  Continuous monitoring of constraints
7. Close    →  Permit closed with audit summary
```

---

## Safety Checks Before Execution

```python
def can_execute(worker, operation):
    # Check certification level
    if operation.environment == "production":
        if worker.certification_level < 2:
            return False, "Production requires Level 2+"

    # Check sensitive data
    if operation.has_pii or operation.has_phi or operation.has_financial:
        if worker.certification_level < 3:
            return False, "Sensitive data requires Level 3+"

    # Check active permit
    if worker.certification_level >= 2:
        permit = get_active_permit(worker.id)
        if not permit:
            return False, "No active permit"
        if not validate_permit(permit, operation):
            return False, "Operation not authorized by permit"

    return True, "Authorized"
```

---

## Compliance Quick Map

| Framework | Min Level | Key Requirement |
|-----------|-----------|-----------------|
| SOC 2 | 2 | Change management |
| HIPAA | 3 | PHI protection |
| PCI-DSS | 3 | Payment security |
| GDPR | 3 | Data protection |
| SOX | 4 | Financial controls |

---

## Best Practices

**DO**:
- ✓ Default to non-union for dev/test
- ✓ Request permits early (not last minute)
- ✓ Document rollback procedures
- ✓ Test in staging before production
- ✓ Monitor during execution
- ✓ Close permits after completion

**DON'T**:
- ✗ Try to bypass safety boundaries
- ✗ Skip required approvals
- ✗ Ignore audit logging
- ✗ Expand scope without re-approval
- ✗ Use emergency override for non-emergencies
- ✗ Approve your own changes

---

## Contact & Escalation

| Issue | Action |
|-------|--------|
| Task certification unclear | Review certification-checker.md |
| Need emergency override | Contact incident commander |
| Permit approval delayed | Escalate to approver's manager |
| Safety violation detected | Alert security team immediately |
| Compliance questions | Contact compliance team |

---

## Files to Reference

- **Full Guide**: WORKER_CERTIFICATION.md
- **Union Rules**: union-requirements.json
- **Non-Union Rules**: non-union-guidelines.json
- **Analysis Logic**: certification-checker.md
- **Permit System**: permit-system.md
- **System Overview**: README.md

---

## Remember

**Production = Always Union (Level 2+)**
**Sensitive Data = Advanced Union (Level 3+)**
**Development = Non-Union (Level 0)**

**When in doubt, ask. Better to delay than to cause an incident.**
