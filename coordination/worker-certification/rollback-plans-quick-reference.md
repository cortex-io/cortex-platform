# Rollback Plans Quick Reference

## TL;DR

Every production change needs a tested rollback plan. Period.

## Required by Certification Level

| Level | Rollback Requirements | SLA | Automation |
|-------|----------------------|-----|------------|
| **Level 2** | Documented procedure, tested in staging | 30 min | Semi-automated preferred |
| **Level 3** | Comprehensive plan, tested rollback, rehearsal | 15 min | Automated mandatory |
| **Level 4** | Enterprise plan, multi-region coordination | 10 min/region | Automated with gates |

## Quick Checklist

Before deploying ANY production change:

- [ ] Rollback procedure documented
- [ ] Rollback tested in staging
- [ ] Rollback time measured (within SLA)
- [ ] Automatic triggers defined
- [ ] Verification checklist created
- [ ] Point of no return identified
- [ ] Alternative recovery path documented
- [ ] Rollback rehearsal completed (Level 3+)

## Rollback Plan Template (Minimal)

```markdown
# Rollback: [Operation Name]

## Quick Facts
- Operation ID: op-xxxxx
- SLA: XX minutes
- Automation: fully_automated | semi_automated | manual

## Pre-Rollback
Current state capture:
- Version: vX.X.X
- Backup location: /path/to/backup
- Critical metrics baseline: error_rate=X%, latency=XXms

## Rollback Procedure
1. Stop traffic to new version (1 min)
2. [Main rollback action] (X min)
3. Restore traffic (1 min)
4. Verify (2 min)

Total: XX minutes

## Automatic Triggers
- Error rate > 1% for 2 minutes
- Latency P99 > 500ms for 5 minutes
- Health checks fail 3 times

## Verification
- [ ] Version correct
- [ ] Health checks passing
- [ ] Error rate < 0.1%
- [ ] Smoke tests passing

## Point of No Return
[Describe when rollback becomes impossible/different]
```

## Common Rollback Commands

### Kubernetes
```bash
# Rollback deployment
kubectl rollout undo deployment/service-name -n production

# Check status
kubectl rollout status deployment/service-name -n production
```

### Terraform
```bash
# Restore previous state
cp terraform.tfstate.backup terraform.tfstate

# Plan and apply
terraform plan -out=rollback.plan
terraform apply rollback.plan
```

### Database
```bash
# Enable read-only
psql -c "ALTER DATABASE SET default_transaction_read_only = on;"

# Restore backup
pg_restore --clean -d production_db backup.sql

# Disable read-only
psql -c "ALTER DATABASE SET default_transaction_read_only = off;"
```

### N8N Workflow
```bash
# Deactivate workflow
curl -X POST http://n8n:5678/api/v1/workflows/ID/deactivate

# Restore previous version
curl -X PUT http://n8n:5678/api/v1/workflows/ID -d @backup.json

# Activate workflow
curl -X POST http://n8n:5678/api/v1/workflows/ID/activate
```

## Automatic Rollback Triggers

### Critical (Auto-execute immediately)
- Error rate > 1% for 2 minutes
- Database connection errors > 10/minute
- Authentication failure rate > 5%
- 3 consecutive health check failures
- Data inconsistency detected

### High (Auto-execute with warning)
- P99 latency > 500ms for 5 minutes
- CPU usage > 90% for 3 minutes
- Memory usage > 85% for 5 minutes
- Throughput < 50% of baseline

### Medium (Alert, wait for manual decision)
- P50 latency > 200ms for 5 minutes
- Conversion rate < 80% of baseline
- Support tickets increase 300%

## Rollback Time SLAs

| Operation Type | Target | SLA | Typical |
|---------------|--------|-----|---------|
| Application deployment | 5 min | 10 min | 3-7 min |
| Configuration change | 3 min | 5 min | 2-4 min |
| Database migration | 10 min | 20 min | 8-15 min |
| Infrastructure change | 15 min | 30 min | 12-25 min |
| Multi-service deploy | 15 min | 25 min | 12-20 min |

## Verification Commands

```bash
#!/bin/bash
# Quick verification script

# 1. Check version
echo "Checking version..."
kubectl get deployment service-name -o jsonpath='{.spec.template.spec.containers[0].image}'

# 2. Check health
echo "Checking health..."
curl -s service/health | jq -r '.status'

# 3. Check metrics
echo "Checking metrics..."
ERROR_RATE=$(curl -s metrics/error_rate | jq -r '.value')
LATENCY=$(curl -s metrics/latency_p99 | jq -r '.value')

echo "Error rate: $ERROR_RATE (should be < 0.001)"
echo "Latency P99: $LATENCY (should be < 200ms)"

# 4. Run smoke tests
echo "Running smoke tests..."
./tests/smoke-test.sh --suite=critical
```

## Partial Rollback Scenarios

### Application Only (40% faster)
When: Database is fine, app has bugs
```bash
kubectl rollout undo deployment/app-service
# Skip database restore
```

### Database Only (30% faster)
When: App is fine, data has issues
```bash
# Only restore database
pg_restore backup.sql
# Keep app running
```

### Single Service (60% faster)
When: One service in multi-service deploy has issues
```bash
kubectl rollout undo deployment/problematic-service
# Leave other services alone
```

### Configuration Only (70% faster)
When: Code is fine, config causes issues
```bash
kubectl apply -f config-backup.yaml
kubectl rollout restart deployment/service
```

## Rollback Failure Escalation

### 0-5 minutes: First Attempt Failed
1. Review logs
2. Retry with verbose logging
3. Notify incident commander

### 5-15 minutes: Retry Failed
1. Escalate to senior SRE
2. Try manual rollback
3. Consider partial rollback
4. Notify engineering director

### 15-30 minutes: Manual Struggling
1. Escalate to CTO/VP Engineering
2. Consider forward-fix
3. Activate disaster recovery
4. Prepare customer communication

### 30+ minutes: Critical Incident
1. Full incident response team
2. Complete service rebuild
3. Execute customer communication plan
4. Prepare post-incident review

## Testing Requirements

### Level 2 (Minimum)
- [ ] Test in staging
- [ ] Measure rollback time
- [ ] Document any issues

### Level 3 (Standard)
- [ ] Test in staging
- [ ] Test in production-like environment
- [ ] Test automated triggers
- [ ] Conduct rollback rehearsal
- [ ] Measure rollback time
- [ ] Train team on rollback

### Level 4 (Comprehensive)
- [ ] Test in staging
- [ ] Test in production-like environment
- [ ] Test multi-region coordination
- [ ] Test automated triggers
- [ ] Conduct rehearsal with stakeholders
- [ ] Measure rollback time per region
- [ ] Create communication plan
- [ ] Document lessons learned

## Common Mistakes

### Don't Do This
- Deploy without tested rollback plan
- Assume rollback will work (test it!)
- Skip verification steps
- Forget to measure rollback time
- Ignore SLA requirements
- Use manual rollback for high-frequency deploys
- Skip rollback rehearsal for Level 3+

### Do This Instead
- Test rollback in staging first
- Automate everything possible
- Verify thoroughly after rollback
- Track rollback metrics
- Meet SLA requirements
- Automate high-frequency deploys
- Rehearse complex rollbacks

## One-Liner Rollback Examples

```bash
# K8s deployment
kubectl rollout undo deployment/service -n prod && kubectl rollout status deployment/service -n prod

# Docker service
docker service update --rollback service-name && docker service ps service-name

# Git-based deployment
git reset --hard HEAD~1 && git push --force origin main && ./deploy.sh

# Feature flag toggle
curl -X POST flags-api/toggle/feature-name/disable

# Symlink swap
ln -sfn /releases/previous /current && systemctl restart service
```

## Metrics to Track

After every rollback, record:
- Rollback trigger (automatic vs manual)
- Rollback duration (compare to SLA)
- Attempts required (should be 1)
- Verification result (pass/fail)
- Downtime duration
- Customer impact
- Lessons learned

## Key Files

- **Full guide**: `/coordination/worker-certification/rollback-plans.md`
- **Schema**: `/coordination/worker-certification/rollback-plans.json`
- **Examples**: See rollback-plans.md sections for K8s, Terraform, DB, N8N

## Remember

1. Every production change needs a rollback plan
2. Test the rollback before production
3. Automate rollback for Level 3+
4. Meet SLA requirements for your level
5. Verify thoroughly after rollback
6. Learn from every rollback execution

**"The best rollback is the one you never need to execute, but must always be ready to use."**

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
