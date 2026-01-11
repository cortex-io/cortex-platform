  # Cortex IT Change Management System

**ITIL/ITSM-Compliant Change Management for Cortex Autonomous Orchestration**

## Overview

The Cortex Change Management System implements ITIL 4 best practices to manage all changes across the Cortex platform. This system ensures that changes are:

- ✅ **Controlled**: All changes follow a standardized process
- ✅ **Risk-Assessed**: AI-powered risk analysis routes changes appropriately
- ✅ **Auditable**: Complete audit trail for compliance (SOC2, HIPAA, ISO27001)
- ✅ **Automated**: Low-risk changes are pre-approved and auto-implemented
- ✅ **Transparent**: Users and stakeholders are kept informed
- ✅ **Recoverable**: Automated rollback on failure

## Quick Start

### 1. Run the Example

See the system in action with today's actual YouTube bug fix:

```bash
cd coordination/change-management
./examples/youtube-bugfix-example.sh
```

This demonstrates a complete change lifecycle from detection through closure.

### 2. Create Your First Change

```bash
# Create a normal deployment change
CHANGE_ID=$(./change-manager.sh create normal deployment \
  "Deploy new feature X" \
  "Detailed description of the change")

# Assess the change (automatic risk scoring)
./change-manager.sh assess $CHANGE_ID

# Approve the change (if you have approval rights)
./change-manager.sh approve $CHANGE_ID your-name "Approved for deployment"

# Implement the change
./change-manager.sh implement $CHANGE_ID

# Close the change
./change-manager.sh close $CHANGE_ID successful "Change deployed successfully"
```

### 3. Integrate with Your Component

```bash
# Example: Development Master creating a change for deployment
./integrations/cortex-integration.sh development-master deploy \
  "New error recovery feature"

# Example: Security Master patching a CVE
./integrations/cortex-integration.sh security-master patch_cve \
  '{"cve_id":"CVE-2024-12345","severity":"critical","description":"Critical security patch"}'

# Example: CI/CD Master deploying to production
./integrations/cortex-integration.sh cicd-master deploy \
  '{"environment":"production","service":"cortex-chat","description":"Deploy v2.1.0"}'
```

## Architecture

### Components

```
coordination/change-management/
├── change-manager.sh           # Core change management engine
├── config/
│   └── change-config.sh        # Configuration and policies
├── integrations/
│   └── cortex-integration.sh   # Integration with Cortex components
├── examples/
│   └── youtube-bugfix-example.sh
├── changes/                    # Change request storage
│   ├── pending/
│   ├── approved/
│   ├── rejected/
│   ├── implemented/
│   └── closed/
├── policies/                   # Change policies and models
└── audit/                      # Audit logs
```

### Change Flow

```
┌─────────────────┐
│ Change Request  │ ← Create RFC
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Risk Assessment │ ← AI-powered scoring
└────────┬────────┘
         │
    ┌────┴────┐
    │ Route   │
    └────┬────┘
         │
    ┌────┴─────────────┬──────────────┐
    │                  │              │
    ▼                  ▼              ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│   Auto   │    │   Tech   │    │   CAB    │
│ Approve  │    │   Lead   │    │  Review  │
└────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │
     └───────────────┴───────────────┘
                     │
                     ▼
            ┌─────────────────┐
            │  Implementation │
            └────────┬────────┘
                     │
            ┌────────┴────────┐
            │                 │
            ▼                 ▼
       ┌─────────┐       ┌─────────┐
       │ Success │       │ Failure │
       └────┬────┘       └────┬────┘
            │                 │
            ▼                 ▼
       ┌─────────┐       ┌─────────┐
       │  Close  │       │Rollback │
       └─────────┘       └─────────┘
```

## Change Types

### Standard Changes (Pre-Approved)

Routine operations with established procedures:

- Worker restarts (max 3/hour per worker)
- Auto-scaling (1-10 replicas)
- Security patches (severity < Critical)
- Configuration updates (within tolerance)

**Approval:** Pre-approved, automated execution
**Example:**
```bash
./integrations/cortex-integration.sh kubernetes restart_pod "worker-001"
```

### Normal Changes (Requires Assessment)

Regular changes that need evaluation:

- New feature deployments
- Service updates
- Policy modifications
- Infrastructure changes

**Approval:** Risk-based (auto/tech-lead/CAB)
**Example:**
```bash
./integrations/cortex-integration.sh cortex-chat deploy_feature \
  "Add conversation export functionality"
```

### Emergency Changes (Expedited)

Urgent fixes for production issues:

- Critical bug fixes
- Security incident response
- Service restoration
- Data corruption recovery

**Approval:** Implement first, retrospective CAB review within 24h
**Example:**
```bash
./integrations/cortex-integration.sh youtube-ingestion emergency_fix \
  "Fix [object Object] serialization bug"
```

## Risk Assessment

### Automatic Risk Scoring

The system automatically calculates risk scores (0-100) based on:

- **Impact** (0-40 points): Service criticality and blast radius
- **Complexity** (0-30 points): Number of affected services
- **Category Risk** (0-20 points): Type of change
- **Historical Success** (0-10 points): Past performance

### Risk Thresholds

| Risk Score | Level    | Approval Required | Testing        |
|------------|----------|-------------------|----------------|
| 0-29       | Low      | Auto-approved     | Unit tests     |
| 30-59      | Medium   | Technical Lead    | Integration    |
| 60-79      | High     | CAB               | Full staging   |
| 80-100     | Critical | CAB + CISO + CTO  | Complete suite |

## ITIL Roles

### Change Requester
- **Who:** Developers, agents, automated systems
- **Responsibility:** Create complete change requests with implementation and rollback plans

### Change Assessor
- **Who:** AI risk engine + Technical Leads
- **Responsibility:** Evaluate technical feasibility and risk

### Change Approver
- **Who:** Technical Leads, CAB members
- **Responsibility:** Approve/reject changes based on assessment

### Change Manager (Automated)
- **Who:** Cortex Change Management Service
- **Responsibility:** Route changes, track progress, enforce policies

### CAB (Change Advisory Board)
- **Who:** Tech Lead, Security, Operations, Product
- **Meeting:** Weekly (Thursdays 2 PM)
- **Responsibility:** Review high-risk changes, set policies

### Emergency CAB
- **Who:** On-call Tech Lead + Security
- **Availability:** 24/7
- **Responsibility:** Emergency approvals, retrospective reviews

## Integration with Cortex Components

### Master Agents

#### Development Master
```bash
# Deploy changes
./integrations/cortex-integration.sh development-master deploy \
  "Deploy error recovery system"

# Emergency bug fixes
./integrations/cortex-integration.sh development-master fix_bug \
  "Critical production bug in YouTube workflow"
```

#### Security Master
```bash
# Patch CVEs
./integrations/cortex-integration.sh security-master patch_cve \
  '{"cve_id":"CVE-2024-XXXXX","severity":"high","description":"..."}'

# Security scans
./integrations/cortex-integration.sh security-master scan_repository \
  "cortex-chat-backend"
```

#### CI/CD Master
```bash
# Builds
./integrations/cortex-integration.sh cicd-master build \
  "cortex-chat-backend:v2.1.0"

# Deployments
./integrations/cortex-integration.sh cicd-master deploy \
  '{"environment":"production","service":"cortex-chat"}'

# Rollbacks
./integrations/cortex-integration.sh cicd-master rollback \
  "Rollback cortex-chat to v2.0.9"
```

#### Inventory Master
```bash
# Catalog repositories
./integrations/cortex-integration.sh inventory-master catalog_repository \
  "new-microservice-repo"

# Update dependencies
./integrations/cortex-integration.sh inventory-master update_dependencies \
  "Update to Node.js 22 LTS"
```

#### Coordinator Master
```bash
# Review changes
./integrations/cortex-integration.sh coordinator-master review CHG-XXX

# Approve/Reject
./integrations/cortex-integration.sh coordinator-master approve CHG-XXX \
  "Approved after team review"

./integrations/cortex-integration.sh coordinator-master reject CHG-XXX \
  "Insufficient testing coverage"
```

### Workers

```bash
# Execute approved change
./integrations/cortex-integration.sh worker worker-001 execute CHG-XXX

# Report success
./integrations/cortex-integration.sh worker worker-001 report_success CHG-XXX

# Report failure (triggers rollback)
./integrations/cortex-integration.sh worker worker-001 report_failure CHG-XXX \
  "Deployment failed health checks"
```

### Services

#### YouTube Ingestion
```bash
# Service updates
./integrations/cortex-integration.sh youtube-ingestion update_service \
  "Improve transcript extraction"

# Emergency fixes
./integrations/cortex-integration.sh youtube-ingestion emergency_fix \
  "Fix object serialization bug"
```

#### Cortex Chat
```bash
# Feature deployments
./integrations/cortex-integration.sh cortex-chat deploy_feature \
  "Add file upload support"

# Hotfixes
./integrations/cortex-integration.sh cortex-chat hotfix \
  "Fix message overflow bug"
```

### Infrastructure

#### Kubernetes
```bash
# Auto-scaling
./integrations/cortex-integration.sh kubernetes scale \
  '{"deployment":"cortex-chat","replicas":8}'

# Pod restarts
./integrations/cortex-integration.sh kubernetes restart_pod \
  "cortex-chat-backend-abc123"

# Config updates
./integrations/cortex-integration.sh kubernetes update_config \
  "Update environment variables for cortex-chat"
```

## Configuration

Edit `config/change-config.sh` to customize:

```bash
# Risk thresholds
export RISK_THRESHOLD_LOW=30
export RISK_THRESHOLD_MEDIUM=60
export RISK_THRESHOLD_HIGH=80

# Auto-approval
export AUTO_APPROVE_LOW_RISK=true
export AUTO_APPROVE_THRESHOLD=25

# CAB settings
export CAB_MEETING_SCHEDULE="0 14 * * 4"  # Thursdays 2 PM
export CAB_MEMBERS="tech-lead,security-lead,ops-lead,product-lead"

# Rollback
export AUTO_ROLLBACK_ENABLED=true
export ROLLBACK_TIMEOUT=300

# Compliance
export SOC2_COMPLIANCE=true
export HIPAA_COMPLIANCE=false
export SEGREGATION_OF_DUTIES=true

# Notifications
export SLACK_NOTIFICATIONS=false
export EMAIL_NOTIFICATIONS=false
export PAGERDUTY_ENABLED=false
```

## Compliance & Audit

### Audit Trail

Every change maintains a complete audit trail:

```json
{
  "change_id": "RFC-20251230180000-abc123",
  "audit_trail": [
    {
      "timestamp": "2025-12-30T18:00:01Z",
      "action": "created",
      "actor": "cortex-orchestrator",
      "details": "Change request submitted"
    },
    {
      "timestamp": "2025-12-30T18:00:15Z",
      "action": "risk_assessed",
      "actor": "ai-risk-engine",
      "details": "Risk score: 45 (Medium)"
    },
    {
      "timestamp": "2025-12-30T18:05:32Z",
      "action": "approved",
      "actor": "tech-lead@cortex.ai",
      "details": "Approved with conditions"
    },
    {
      "timestamp": "2025-12-30T18:15:00Z",
      "action": "implemented",
      "actor": "cortex-deployer",
      "details": "Deployment completed"
    }
  ]
}
```

### Compliance Reports

```bash
# View changes by compliance status
./change-manager.sh list approved | while read change_file; do
  jq '.compliance' "$change_file"
done

# Generate metrics report
./change-manager.sh metrics today

# Audit log for specific date
cat audit/2025-12-30.log
```

### SOC2 Requirements

✅ Complete audit trail for all changes
✅ Segregation of duties (requester ≠ approver)
✅ Change approval documentation
✅ Rollback procedures tested quarterly
✅ Access control for change management system

### HIPAA Requirements

✅ Risk assessment for PHI-affecting changes
✅ Access control documentation
✅ Incident response integration
✅ Encryption validation
✅ Business Associate Agreement (BAA) compliance

## Metrics & KPIs

### Process Efficiency

- **Change Success Rate**: Target > 95%
- **Mean Time to Approve (MTTA)**: Target < 4 hours
- **Mean Time to Implement (MTTI)**: Target < 30 minutes
- **Rollback Rate**: Target < 5%

### Risk Management

- **Risk Prediction Accuracy**: Target > 90%
- **False Positive Rate**: Target < 10%
- **Emergency Change Rate**: Target < 5%

### Business Impact

- **Change-Induced Incidents**: Target < 2%
- **Unauthorized Changes**: Target = 0%
- **Audit Compliance**: Target = 100%

### View Metrics

```bash
# Today's metrics
./change-manager.sh metrics today

# This week
./change-manager.sh metrics week

# Custom period
./change-manager.sh metrics "2025-12-01 to 2025-12-31"
```

## Troubleshooting

### Common Issues

**Q: Change stuck in pending_approval**
```bash
# Check approval timeout
cat changes/*/RFC-XXXXX.json | jq '.approval_required'

# Manually approve if authorized
./change-manager.sh approve RFC-XXXXX your-name "Approved"
```

**Q: Auto-approval not working**
```bash
# Check risk score
./change-manager.sh show RFC-XXXXX | jq '.risk_score'

# Verify configuration
grep AUTO_APPROVE config/change-config.sh
```

**Q: Rollback not triggering**
```bash
# Check rollback configuration
grep ROLLBACK config/change-config.sh

# Manually trigger rollback
./integrations/cortex-integration.sh cicd-master rollback "Manual rollback"
```

## Best Practices

### 1. Always Include Implementation Plans

```json
{
  "implementation_plan": {
    "steps": [
      "Build new container image",
      "Deploy to staging",
      "Run integration tests",
      "Deploy to production",
      "Monitor for 30 minutes"
    ],
    "estimated_duration": "45m",
    "maintenance_window": false
  }
}
```

### 2. Always Include Rollback Plans

```json
{
  "rollback_plan": {
    "automated": true,
    "steps": [
      "Revert to previous image tag",
      "Verify services healthy",
      "Clear cache if needed"
    ],
    "max_duration": "5m"
  }
}
```

### 3. Document Affected Services and CIs

```json
{
  "affected_services": [
    "cortex-chat-backend",
    "youtube-ingestion"
  ],
  "affected_cis": [
    "K8S-CORTEX-CHAT",
    "REDIS-CORTEX-SYSTEM"
  ]
}
```

### 4. Use Standard Change Models

Create templates for common changes:

```bash
# Worker restart (standard)
./integrations/cortex-integration.sh kubernetes restart_pod worker-001

# This automatically:
# - Creates standard change
# - Auto-approves (pre-approved model)
# - Implements immediately
# - Validates health
# - Closes change
```

### 5. Test in Staging First

```bash
# Deploy to staging
CHANGE_ID=$(./integrations/cortex-integration.sh cicd-master deploy \
  '{"environment":"staging","service":"my-service"}')

# Wait for validation
sleep 300

# If successful, deploy to production
./integrations/cortex-integration.sh cicd-master deploy \
  '{"environment":"production","service":"my-service","tested_in_staging":"'$CHANGE_ID'"}'
```

## Roadmap

### Phase 1: Foundation ✅ (Current)
- [x] Basic change tracking
- [x] Risk assessment
- [x] Approval workflows
- [x] Cortex component integration
- [x] Audit logging

### Phase 2: Automation (Next 2 weeks)
- [ ] ML-based risk prediction
- [ ] Automated dependency analysis
- [ ] Self-service change portal
- [ ] Slack/email notifications
- [ ] CMDB integration

### Phase 3: Intelligence (Weeks 3-4)
- [ ] Predictive failure analysis
- [ ] Automated rollback decisions
- [ ] Change success prediction
- [ ] Performance impact forecasting
- [ ] Compliance automation

### Phase 4: Maturity (Weeks 5-8)
- [ ] Full DevOps integration
- [ ] Advanced analytics dashboard
- [ ] Continuous improvement loops
- [ ] Self-healing capabilities
- [ ] Enterprise reporting

## Support

### Documentation
- Framework Overview: `../../docs/CHANGE_MANAGEMENT_FRAMEWORK.md`
- Configuration Reference: `config/change-config.sh`
- Integration Guide: `integrations/cortex-integration.sh`

### Examples
- Real-world bug fix: `examples/youtube-bugfix-example.sh`
- Component integrations: See "Integration with Cortex Components" above

### Getting Help

1. Check this README
2. Review examples directory
3. Inspect audit logs: `audit/*.log`
4. Check configuration: `config/change-config.sh`
5. Open an issue in the Cortex repository

## References

**ITIL Framework:**
- [ITIL Change Management - ServiceNow Community](https://www.servicenow.com/community/developer-articles/itil-change-management-a-comprehensive-guide/ta-p/2330207)
- [ITIL ServiceNow Guide for IT Administrators](https://www.reco.ai/hub/itil-servicenow-guide-it-administrators)

**Best Practices:**
- [ServiceNow Change Management Best Practices](https://blog.vsoftconsulting.com/blog/servicenow-change-management-best-practices-strategies-for-it-teams)
- [Modern Change Management Adoption Playbook](https://www.servicenow.com/community/itsm-articles/modern-change-management-adoption-playbook-amp-maturity-journey/ta-p/3279260)

---

**Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Production Ready
**Maintainer:** Cortex Platform Team
