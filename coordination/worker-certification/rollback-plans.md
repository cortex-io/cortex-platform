# Rollback Plans System

## Overview

The Rollback Plans System is Cortex's safety net for union operations, ensuring that every production change can be safely reversed if issues arise. This system mandates documented, tested, and automated rollback procedures for all Level 2+ operations.

## Philosophy

**Principle**: Every production change must be reversible, or have a documented recovery path.

**Core Tenets**:
- Plan the rollback before executing the change
- Test the rollback before production
- Automate rollback where possible
- Document manual rollback steps clearly
- Time-bound rollback procedures
- Verify rollback completeness

**Quote**: "Hope is not a strategy. Have a tested rollback plan."

## Why Rollback Plans Matter

### Without Rollback Plans
- 45% of production incidents become worse during recovery attempts
- Average recovery time: 4.5 hours
- High stress, poor decisions
- Customer impact extended
- Team exhaustion

### With Rollback Plans
- 95% of rollbacks complete successfully
- Average rollback time: 12 minutes
- Calm, systematic recovery
- Customer impact minimized
- Team confidence maintained

## Rollback Requirements by Certification Level

### Level 2 (Standard Union)
**Required**:
- Documented rollback procedure
- Rollback tested in staging
- Automated rollback preferred
- Rollback time SLA: 30 minutes
- Verification checklist

**Example**: API deployment rollback

### Level 3 (Advanced Union)
**Required**:
- Comprehensive rollback documentation
- Rollback tested in production-like environment
- Automated rollback mandatory
- Partial rollback capability
- Rollback time SLA: 15 minutes
- Data consistency verification
- Rollback rehearsal conducted

**Example**: Database migration rollback

### Level 4 (Master Union)
**Required**:
- Enterprise rollback plan
- Multi-region rollback coordination
- Automated rollback with manual gates
- Partial rollback capability
- Rollback time SLA: 10 minutes per region
- Complete data integrity verification
- Rollback rehearsal with stakeholders
- Communication plan included

**Example**: Multi-region infrastructure change rollback

## Rollback Plan Template

```markdown
# Rollback Plan: [Operation Name]

## Metadata
- **Operation ID**: op-12345
- **Permit ID**: permit-xyz789
- **Created**: 2025-12-09T10:00:00Z
- **Last Updated**: 2025-12-09T14:00:00Z
- **Owner**: development-master
- **Certification Level**: 3

## Operation Summary
**What we're changing**:
Deploy API v2.1 with new authentication system and database schema migration.

**Services affected**:
- api-service (production)
- auth-service (production)
- postgresql-primary (production)
- redis-cache (production)

**Risk level**: High (authentication changes + schema migration)

## Pre-Rollback State Capture
**Critical state to preserve**:
- [ ] Database schema version: v2.0.5
- [ ] Current API version: v2.0.8
- [ ] Active user sessions: ~12,000
- [ ] Database backup taken: backup-20251209-140000.sql
- [ ] Configuration snapshots: config-snapshot-20251209.json
- [ ] Container image tags: api:v2.0.8, auth:v1.5.2

**State capture commands**:
```bash
# Capture current versions
kubectl get deployment api-service -o yaml > api-deployment-backup.yaml
kubectl get deployment auth-service -o yaml > auth-deployment-backup.yaml

# Database backup verification
pg_dump production_db > backup-pre-v2.1.sql
sha256sum backup-pre-v2.1.sql

# Session count baseline
redis-cli INFO | grep connected_clients

# Metrics baseline
curl metrics-api/snapshot > metrics-baseline.json
```

## Rollback Decision Criteria

### Automatic Rollback Triggers
Execute rollback automatically if:
- Error rate > 1% for 2 consecutive minutes
- P99 latency > 500ms for 5 consecutive minutes
- Authentication failure rate > 5%
- Database connection errors > 10/minute
- Health check failures > 3 consecutive
- CPU usage > 90% for 3 minutes

### Manual Rollback Triggers
Consider rollback if:
- User-reported issues > 10/hour
- Data inconsistencies detected
- Unexpected behavior in critical flows
- Performance degradation > 20%
- Security concerns identified

### Point of No Return
**Before this point**: Safe to rollback
**After this point**: Must use forward-fix

**Point of No Return**: Database migration v2.1 migrations 008-011 completed (irreversible schema changes)

**Alternative if past point of no return**:
- Deploy compensating schema migration
- Apply data transformation scripts
- Forward-fix with v2.1.1 patch

## Rollback Procedure

### Phase 1: Preparation (2 minutes)
**Objective**: Prepare for rollback execution

1. **Verify rollback readiness**
   ```bash
   # Check backup availability
   ls -lh backup-pre-v2.1.sql

   # Verify rollback images exist
   docker pull api:v2.0.8
   docker pull auth:v1.5.2

   # Confirm rollback automation is ready
   ./scripts/rollback-verify.sh
   ```

2. **Notify stakeholders**
   ```bash
   # Auto-notification via rollback system
   notify-stakeholders --operation="API v2.1 Rollback" \
                      --severity="high" \
                      --channels="slack,pagerduty,email"
   ```

3. **Enable enhanced monitoring**
   ```bash
   # Increase monitoring frequency
   ./scripts/enable-rollback-monitoring.sh
   ```

### Phase 2: Stop Traffic to New Version (1 minute)
**Objective**: Prevent new requests from hitting v2.1

1. **Route traffic away**
   ```bash
   # Update load balancer to route to v2.0.8 pods only
   kubectl label pods -l version=v2.1 rollout=rolling --overwrite
   kubectl scale deployment api-service-v2.1 --replicas=0

   # Verify traffic shifted
   curl -s load-balancer/health | jq '.active_version'
   # Expected: "v2.0.8"
   ```

2. **Verify traffic stopped**
   ```bash
   # Check v2.1 pods receiving no traffic
   kubectl logs -l version=v2.1 --tail=10
   # Should show no new requests for 30 seconds
   ```

### Phase 3: Database Rollback (3 minutes)
**Objective**: Restore database to v2.0 schema

**CRITICAL**: Only execute if NOT past point of no return!

1. **Stop application writes**
   ```bash
   # Enable read-only mode
   kubectl exec -it postgresql-primary -- psql -c \
     "ALTER DATABASE production_db SET default_transaction_read_only = on;"
   ```

2. **Restore database backup**
   ```bash
   # Verify backup integrity
   sha256sum -c backup-pre-v2.1.sql.sha256

   # Restore backup
   pg_restore --clean --no-owner --no-acl \
              -d production_db backup-pre-v2.1.sql

   # Verify schema version
   psql -c "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;"
   # Expected: 20251201120000 (v2.0.5)
   ```

3. **Re-enable writes**
   ```bash
   kubectl exec -it postgresql-primary -- psql -c \
     "ALTER DATABASE production_db SET default_transaction_read_only = off;"
   ```

### Phase 4: Application Rollback (2 minutes)
**Objective**: Restore application to v2.0.8

1. **Deploy previous version**
   ```bash
   # Rollback API service
   kubectl set image deployment/api-service \
     api=api:v2.0.8 --record

   # Rollback auth service
   kubectl set image deployment/auth-service \
     auth=auth:v1.5.2 --record

   # Wait for rollout
   kubectl rollout status deployment/api-service --timeout=120s
   kubectl rollout status deployment/auth-service --timeout=120s
   ```

2. **Restore configuration**
   ```bash
   # Restore previous config
   kubectl apply -f config-snapshot-20251209.json

   # Restart pods to pick up config
   kubectl rollout restart deployment/api-service
   kubectl rollout restart deployment/auth-service
   ```

### Phase 5: Cache Invalidation (1 minute)
**Objective**: Clear stale cache data

1. **Flush Redis cache**
   ```bash
   # Clear authentication cache
   redis-cli FLUSHDB

   # Verify cache cleared
   redis-cli DBSIZE
   # Expected: 0
   ```

2. **Warm critical caches**
   ```bash
   # Pre-warm frequently accessed data
   ./scripts/cache-warmup.sh --critical-only
   ```

### Phase 6: Traffic Restoration (1 minute)
**Objective**: Resume normal traffic flow

1. **Scale up v2.0.8 pods**
   ```bash
   # Ensure full capacity
   kubectl scale deployment api-service --replicas=10
   kubectl scale deployment auth-service --replicas=5

   # Wait for ready
   kubectl wait --for=condition=ready pod -l app=api-service --timeout=60s
   ```

2. **Route traffic to v2.0.8**
   ```bash
   # Update load balancer
   kubectl label pods -l version=v2.0.8 rollout=stable --overwrite

   # Gradually increase traffic
   ./scripts/traffic-shift.sh --from=0 --to=100 --duration=30s
   ```

### Phase 7: Verification (2 minutes)
**Objective**: Confirm rollback success

1. **Health checks**
   ```bash
   # Check all services healthy
   kubectl get pods -l app=api-service
   kubectl get pods -l app=auth-service

   # Verify health endpoints
   curl api-service/health | jq '.status'
   # Expected: "healthy"
   ```

2. **Functional tests**
   ```bash
   # Run critical path tests
   ./tests/smoke-test.sh --suite=critical
   # Expected: All tests passing
   ```

3. **Metrics verification**
   ```bash
   # Compare to baseline
   curl metrics-api/snapshot > metrics-post-rollback.json
   ./scripts/compare-metrics.sh metrics-baseline.json metrics-post-rollback.json

   # Verify key metrics:
   # - Error rate < 0.1%
   # - P99 latency < 200ms
   # - Authentication success rate > 99.5%
   ```

### Phase 8: Cleanup (2 minutes)
**Objective**: Remove v2.1 artifacts and restore normal operations

1. **Remove v2.1 deployments**
   ```bash
   # Delete v2.1 resources
   kubectl delete deployment api-service-v2.1
   kubectl delete deployment auth-service-v2.1

   # Clean up config maps
   kubectl delete configmap api-config-v2.1
   ```

2. **Disable enhanced monitoring**
   ```bash
   ./scripts/disable-rollback-monitoring.sh
   ```

3. **Archive rollback logs**
   ```bash
   # Collect all logs
   kubectl logs -l app=api-service --since=30m > rollback-logs-api.txt
   kubectl logs -l app=auth-service --since=30m > rollback-logs-auth.txt

   # Store in audit trail
   aws s3 cp rollback-logs-*.txt s3://audit-logs/rollbacks/op-12345/
   ```

## Rollback Time Estimate
- **Phase 1 (Preparation)**: 2 minutes
- **Phase 2 (Stop Traffic)**: 1 minute
- **Phase 3 (Database)**: 3 minutes
- **Phase 4 (Application)**: 2 minutes
- **Phase 5 (Cache)**: 1 minute
- **Phase 6 (Traffic Restoration)**: 1 minute
- **Phase 7 (Verification)**: 2 minutes
- **Phase 8 (Cleanup)**: 2 minutes

**Total Time**: 14 minutes
**SLA**: 15 minutes (Level 3)
**Buffer**: 1 minute

## Partial Rollback Capability

### Scenario: Database OK, Application Issues
**Rollback**: Application only (Phases 4-8)
**Time**: 8 minutes
**Use when**: Schema changes are fine, but application has bugs

### Scenario: Application OK, Database Issues
**Rollback**: Database only (Phases 3, 5-8)
**Time**: 8 minutes
**Use when**: Application works, but database has data issues

### Scenario: Specific Service Issues
**Rollback**: Single service (auth-service only)
**Time**: 4 minutes
**Use when**: Only one service has problems

## Rollback Testing Requirements

### Pre-Production Testing
**Required before permit approval**:

1. **Staging Environment Test**
   ```bash
   # Deploy v2.1 to staging
   ./deploy.sh --env=staging --version=v2.1

   # Execute full rollback
   ./rollback.sh --env=staging --operation=api-v2.1

   # Verify rollback success
   ./verify-rollback.sh --env=staging
   ```

2. **Production-Like Environment Test**
   ```bash
   # Use blue-green environment
   ./deploy.sh --env=production-blue --version=v2.1

   # Simulate failure and rollback
   ./simulate-failure.sh --type=high_error_rate
   ./rollback.sh --env=production-blue --auto

   # Verify automated rollback
   ./verify-rollback.sh --env=production-blue --expect=automated
   ```

3. **Rollback Rehearsal**
   - Schedule: 24 hours before production deployment
   - Participants: Engineering team, SRE, stakeholders
   - Duration: 30 minutes
   - Document any issues found
   - Update rollback plan based on learnings

### Rollback Test Checklist
- [ ] Rollback tested in staging environment
- [ ] Rollback tested in production-like environment
- [ ] Automated triggers tested
- [ ] Manual rollback tested
- [ ] Partial rollback scenarios tested
- [ ] Rollback time measured (within SLA)
- [ ] Verification procedures tested
- [ ] Rollback rehearsal completed
- [ ] Stakeholders trained on rollback procedure
- [ ] Rollback documentation reviewed by SRE

## Automatic Rollback System

### Configuration
```json
{
  "auto_rollback": {
    "enabled": true,
    "operation_id": "op-12345",
    "permit_id": "permit-xyz789",

    "triggers": [
      {
        "metric": "error_rate",
        "threshold": 0.01,
        "duration_seconds": 120,
        "comparison": "greater_than"
      },
      {
        "metric": "latency_p99",
        "threshold": 500,
        "duration_seconds": 300,
        "comparison": "greater_than"
      },
      {
        "metric": "auth_failure_rate",
        "threshold": 0.05,
        "duration_seconds": 60,
        "comparison": "greater_than"
      },
      {
        "metric": "health_check_failures",
        "threshold": 3,
        "consecutive": true,
        "comparison": "greater_than"
      }
    ],

    "rollback_script": "./scripts/rollback-api-v2.1.sh",
    "notification_channels": ["slack", "pagerduty", "email"],
    "require_manual_confirmation": false,
    "rollback_timeout_seconds": 900,

    "safety_checks": {
      "verify_backup_exists": true,
      "verify_previous_version_healthy": true,
      "verify_rollback_tested": true
    }
  }
}
```

### Monitoring Script
```bash
#!/bin/bash
# auto-rollback-monitor.sh

OPERATION_ID="op-12345"
PERMIT_ID="permit-xyz789"
CONFIG="auto-rollback-config.json"

# Load configuration
ERROR_THRESHOLD=$(jq -r '.auto_rollback.triggers[] | select(.metric=="error_rate") | .threshold' $CONFIG)
LATENCY_THRESHOLD=$(jq -r '.auto_rollback.triggers[] | select(.metric=="latency_p99") | .threshold' $CONFIG)

# Monitoring loop
while true; do
  # Get current metrics
  ERROR_RATE=$(curl -s metrics-api/error_rate | jq -r '.value')
  LATENCY_P99=$(curl -s metrics-api/latency_p99 | jq -r '.value')

  # Check thresholds
  if (( $(echo "$ERROR_RATE > $ERROR_THRESHOLD" | bc -l) )); then
    echo "ERROR RATE EXCEEDED: $ERROR_RATE > $ERROR_THRESHOLD"
    echo "Triggering automatic rollback..."

    # Execute rollback
    ./scripts/rollback-api-v2.1.sh --auto --reason="error_rate_exceeded"

    # Notify stakeholders
    notify-stakeholders --type="auto_rollback_triggered" \
                       --metric="error_rate" \
                       --value="$ERROR_RATE"

    # Exit monitoring
    exit 0
  fi

  if (( $(echo "$LATENCY_P99 > $LATENCY_THRESHOLD" | bc -l) )); then
    echo "LATENCY EXCEEDED: $LATENCY_P99 > $LATENCY_THRESHOLD"
    echo "Triggering automatic rollback..."

    ./scripts/rollback-api-v2.1.sh --auto --reason="latency_exceeded"
    notify-stakeholders --type="auto_rollback_triggered" \
                       --metric="latency_p99" \
                       --value="$LATENCY_P99"
    exit 0
  fi

  # Log normal status
  echo "$(date): Metrics normal (error_rate=$ERROR_RATE, latency_p99=$LATENCY_P99)"

  # Sleep before next check
  sleep 30
done
```

## Rollback Verification Procedure

### Automated Verification
```bash
#!/bin/bash
# verify-rollback.sh

echo "=== Rollback Verification ==="

# 1. Version Check
echo "Checking deployed versions..."
API_VERSION=$(kubectl get deployment api-service -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)
AUTH_VERSION=$(kubectl get deployment auth-service -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)

if [[ "$API_VERSION" == "v2.0.8" ]] && [[ "$AUTH_VERSION" == "v1.5.2" ]]; then
  echo "✓ Versions correct"
else
  echo "✗ Version mismatch: API=$API_VERSION, AUTH=$AUTH_VERSION"
  exit 1
fi

# 2. Database Schema Check
echo "Checking database schema..."
SCHEMA_VERSION=$(psql -t -c "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;" | xargs)

if [[ "$SCHEMA_VERSION" == "20251201120000" ]]; then
  echo "✓ Schema version correct"
else
  echo "✗ Schema version incorrect: $SCHEMA_VERSION"
  exit 1
fi

# 3. Health Check
echo "Checking service health..."
API_HEALTH=$(curl -s api-service/health | jq -r '.status')
AUTH_HEALTH=$(curl -s auth-service/health | jq -r '.status')

if [[ "$API_HEALTH" == "healthy" ]] && [[ "$AUTH_HEALTH" == "healthy" ]]; then
  echo "✓ Services healthy"
else
  echo "✗ Services unhealthy: API=$API_HEALTH, AUTH=$AUTH_HEALTH"
  exit 1
fi

# 4. Metrics Check
echo "Checking metrics..."
ERROR_RATE=$(curl -s metrics-api/error_rate | jq -r '.value')
LATENCY_P99=$(curl -s metrics-api/latency_p99 | jq -r '.value')

if (( $(echo "$ERROR_RATE < 0.001" | bc -l) )) && (( $(echo "$LATENCY_P99 < 200" | bc -l) )); then
  echo "✓ Metrics acceptable (error_rate=$ERROR_RATE, latency_p99=$LATENCY_P99)"
else
  echo "✗ Metrics out of range (error_rate=$ERROR_RATE, latency_p99=$LATENCY_P99)"
  exit 1
fi

# 5. Functional Test
echo "Running functional tests..."
./tests/smoke-test.sh --suite=critical > /dev/null 2>&1

if [[ $? -eq 0 ]]; then
  echo "✓ Functional tests passed"
else
  echo "✗ Functional tests failed"
  exit 1
fi

# 6. Data Consistency Check
echo "Checking data consistency..."
RECORD_COUNT=$(psql -t -c "SELECT COUNT(*) FROM users;" | xargs)
EXPECTED_COUNT=$(cat pre-rollback-counts.txt | grep users | awk '{print $2}')

if [[ "$RECORD_COUNT" -eq "$EXPECTED_COUNT" ]]; then
  echo "✓ Data consistency verified"
else
  echo "⚠ Record count mismatch: found=$RECORD_COUNT, expected=$EXPECTED_COUNT"
  # Don't fail - just warn
fi

echo ""
echo "=== Rollback Verification Complete ==="
echo "All critical checks passed ✓"
exit 0
```

### Manual Verification Checklist
**After automated verification, manually verify**:

- [ ] User login works correctly
- [ ] Critical user flows function (checkout, signup, etc.)
- [ ] No error spikes in dashboards
- [ ] No customer complaints in support channels
- [ ] Database queries returning expected data
- [ ] Cache hit rates normal
- [ ] All pods running and ready
- [ ] Load balancer routing correctly
- [ ] SSL certificates valid
- [ ] External integrations working

## Rollback Time SLAs

### Level 2 Operations
- **Target**: 20 minutes
- **SLA**: 30 minutes
- **Breach consequences**: Warning, review rollback plan

### Level 3 Operations
- **Target**: 10 minutes
- **SLA**: 15 minutes
- **Breach consequences**: Incident review required

### Level 4 Operations
- **Target**: 5 minutes per region
- **SLA**: 10 minutes per region
- **Breach consequences**: Executive review required

### Measuring Rollback Time
**Start**: When rollback decision is made
**End**: When verification is complete and traffic is stable

**Excludes**: Decision-making time (covered separately in incident response)

**Tracking**:
```bash
# Record rollback start
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > rollback-start-time.txt

# Execute rollback
./rollback.sh

# Record rollback end
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > rollback-end-time.txt

# Calculate duration
start=$(cat rollback-start-time.txt)
end=$(cat rollback-end-time.txt)
duration=$(($(date -d "$end" +%s) - $(date -d "$start" +%s)))

echo "Rollback completed in $duration seconds"

# Compare to SLA
if [[ $duration -gt 900 ]]; then
  echo "⚠ SLA BREACH: Rollback took longer than 15 minutes"
  create-incident --type=sla_breach --rollback-time=$duration
fi
```

## Rollback Failure Escalation

### If Rollback Fails

**Level 1: First Attempt Failed (0-5 minutes)**
1. Review rollback logs for errors
2. Check prerequisites (backups, images, etc.)
3. Retry rollback with verbose logging
4. Notify incident commander

**Level 2: Retry Failed (5-15 minutes)**
1. Escalate to senior SRE
2. Attempt manual rollback steps
3. Check for blocking conditions
4. Consider partial rollback
5. Notify engineering director

**Level 3: Manual Rollback Struggling (15-30 minutes)**
1. Escalate to CTO/VP Engineering
2. Engage vendor support if needed
3. Consider forward-fix instead
4. Activate disaster recovery procedures
5. Prepare customer communication

**Level 4: Critical Incident (30+ minutes)**
1. Activate full incident response team
2. Consider complete service rebuild
3. Restore from disaster recovery backups
4. Execute customer communication plan
5. Prepare post-incident review

### Rollback Failure Documentation
```json
{
  "rollback_failure": {
    "operation_id": "op-12345",
    "permit_id": "permit-xyz789",
    "rollback_attempted_at": "2025-12-09T20:15:00Z",
    "rollback_failed_at": "2025-12-09T20:35:00Z",
    "failure_reason": "Database restore failed due to corrupted backup",

    "failure_details": {
      "phase": "Phase 3: Database Rollback",
      "step": "Restore database backup",
      "error_message": "pg_restore: error: could not read from input file: end of file",
      "logs": "rollback-failure-logs.txt"
    },

    "escalation_timeline": [
      {
        "level": 1,
        "timestamp": "2025-12-09T20:35:00Z",
        "action": "Retry with secondary backup",
        "outcome": "failed"
      },
      {
        "level": 2,
        "timestamp": "2025-12-09T20:42:00Z",
        "action": "Escalated to senior SRE",
        "outcome": "investigating"
      },
      {
        "level": 3,
        "timestamp": "2025-12-09T20:55:00Z",
        "action": "Decided on forward-fix approach",
        "outcome": "in_progress"
      }
    ],

    "resolution": {
      "approach": "forward-fix",
      "description": "Applied compensating migration and deployed v2.1.1 patch",
      "resolved_at": "2025-12-09T21:30:00Z",
      "total_incident_duration_minutes": 75
    },

    "lessons_learned": [
      "Backup verification process insufficient",
      "Need multiple backup retention points",
      "Should have tested backup restore in staging"
    ]
  }
}
```

## Post-Rollback Validation

### Immediate Post-Rollback (0-15 minutes)
1. **Service Availability**
   - All services responding to health checks
   - No errors in logs
   - Traffic routing correctly

2. **Performance Metrics**
   - Error rate < 0.1%
   - Latency within baselines
   - Throughput normal

3. **Data Integrity**
   - Record counts match expectations
   - No data corruption detected
   - Referential integrity intact

### Short-Term Validation (15 minutes - 1 hour)
1. **User Impact Assessment**
   - Monitor user complaints
   - Check support ticket volume
   - Review social media mentions

2. **Business Metrics**
   - Conversion rates normal
   - Transaction volume normal
   - Revenue impact assessment

3. **System Stability**
   - No resource exhaustion
   - No memory leaks
   - No cascading failures

### Long-Term Validation (1-24 hours)
1. **Trend Analysis**
   - Compare metrics to pre-incident baseline
   - Identify any lingering issues
   - Monitor for delayed effects

2. **Data Quality**
   - Run data quality checks
   - Verify batch jobs completed
   - Check data synchronization

3. **Customer Communication**
   - Send status update if needed
   - Monitor customer sentiment
   - Address any concerns

## Rollback Metrics and Reporting

### Key Metrics
```json
{
  "rollback_metrics": {
    "operation_id": "op-12345",
    "permit_id": "permit-xyz789",

    "rollback_execution": {
      "triggered_at": "2025-12-09T20:15:00Z",
      "trigger_type": "automatic",
      "trigger_reason": "error_rate_exceeded",
      "trigger_value": 0.025,
      "trigger_threshold": 0.01,

      "completed_at": "2025-12-09T20:29:00Z",
      "total_duration_seconds": 840,
      "sla_seconds": 900,
      "sla_met": true,
      "sla_buffer_seconds": 60
    },

    "phase_timings": {
      "preparation": 118,
      "stop_traffic": 45,
      "database_rollback": 182,
      "application_rollback": 125,
      "cache_invalidation": 67,
      "traffic_restoration": 58,
      "verification": 143,
      "cleanup": 102
    },

    "rollback_success": {
      "success": true,
      "attempts": 1,
      "verification_passed": true,
      "all_services_healthy": true
    },

    "impact_metrics": {
      "downtime_seconds": 180,
      "affected_requests": 2847,
      "failed_requests": 71,
      "customer_impact": "minimal",
      "revenue_impact_usd": 0
    },

    "quality_metrics": {
      "rollback_tested_before": true,
      "automated_rollback": true,
      "manual_intervention_required": false,
      "rollback_documentation_followed": true,
      "rollback_plan_accuracy": 0.95
    }
  }
}
```

### Rollback Dashboard
**Real-time during rollback**:
- Current phase and progress
- Time elapsed vs SLA
- Service health status
- Metrics comparison (current vs baseline)
- Errors encountered

**Historical view**:
- Rollback frequency by service
- Average rollback time
- SLA compliance rate
- Common rollback triggers
- Rollback success rate

### Rollback Reporting
**Generate after each rollback**:

```markdown
# Rollback Report: API v2.1 Deployment

## Executive Summary
- **Operation**: Deploy API v2.1
- **Rollback Triggered**: 2025-12-09T20:15:00Z
- **Rollback Completed**: 2025-12-09T20:29:00Z
- **Duration**: 14 minutes (SLA: 15 minutes)
- **Outcome**: Successful
- **Customer Impact**: Minimal (180s elevated errors)

## Trigger Analysis
- **Trigger Type**: Automatic
- **Reason**: Error rate exceeded threshold
- **Metric**: error_rate = 2.5% (threshold: 1%)
- **Detection**: Automated monitoring (30s delay)

## Rollback Execution
- **Method**: Automated rollback script
- **Attempts**: 1 (successful on first attempt)
- **Manual Intervention**: None required
- **SLA Compliance**: Yes (60s buffer)

## Impact Assessment
- **Downtime**: 3 minutes
- **Affected Requests**: 2,847
- **Failed Requests**: 71 (2.5%)
- **Customer Complaints**: 0
- **Revenue Impact**: $0

## Root Cause
Database connection pool exhaustion in v2.1 under production load. Issue not detected in staging due to lower traffic volume.

## Prevention Measures
1. Enhance load testing to match production traffic
2. Implement connection pool monitoring
3. Add connection pool size to deployment checklist
4. Update rollback plan with connection pool checks

## Lessons Learned
- Automated rollback worked perfectly
- Rollback time well within SLA
- Staging environment needs higher load simulation
- Monitoring detected issue quickly (30s)

## Follow-up Actions
- [ ] Fix connection pool configuration (v2.1.1)
- [ ] Enhanced load testing in staging
- [ ] Update deployment checklist
- [ ] Schedule v2.1.1 deployment
```

## Rollback Plan Examples

### Example 1: Kubernetes Deployment Rollback

```markdown
# Rollback Plan: Kubernetes Deployment

## Operation
Deploy microservice v3.2 to production cluster

## Rollback Procedure
```bash
#!/bin/bash
# rollback-k8s-deployment.sh

SERVICE_NAME="payment-service"
NAMESPACE="production"
PREVIOUS_VERSION="v3.1.8"

echo "Rolling back $SERVICE_NAME to $PREVIOUS_VERSION..."

# 1. Rollback deployment
kubectl rollout undo deployment/$SERVICE_NAME -n $NAMESPACE

# 2. Wait for rollout
kubectl rollout status deployment/$SERVICE_NAME -n $NAMESPACE --timeout=120s

# 3. Verify pods
kubectl get pods -n $NAMESPACE -l app=$SERVICE_NAME

# 4. Check health
for pod in $(kubectl get pods -n $NAMESPACE -l app=$SERVICE_NAME -o name); do
  kubectl exec -n $NAMESPACE $pod -- curl -s localhost:8080/health
done

# 5. Verify version
kubectl get deployment $SERVICE_NAME -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}'

echo "Rollback complete!"
```

**Time Estimate**: 3 minutes
**Automation**: Fully automated
**Manual Steps**: None required
```

### Example 2: Infrastructure (Terraform) Rollback

```markdown
# Rollback Plan: Infrastructure Change

## Operation
Update load balancer configuration via Terraform

## Rollback Procedure
```bash
#!/bin/bash
# rollback-terraform.sh

COMPONENT="load-balancer"
PREVIOUS_STATE="terraform.tfstate.backup"

echo "Rolling back Terraform infrastructure..."

# 1. Verify backup state exists
if [[ ! -f "$PREVIOUS_STATE" ]]; then
  echo "ERROR: No backup state found!"
  exit 1
fi

# 2. Restore previous state
cp $PREVIOUS_STATE terraform.tfstate

# 3. Apply previous configuration
terraform plan -out=rollback.plan
terraform apply rollback.plan

# 4. Verify infrastructure
terraform show | grep load_balancer

# 5. Test load balancer
curl -I https://api.example.com/health

echo "Rollback complete!"
```

**Time Estimate**: 5 minutes
**Automation**: Semi-automated (requires approval for terraform apply)
**Manual Steps**: Review plan output before apply
**Point of No Return**: After terraform apply completes (15 seconds)
```

### Example 3: N8N Workflow Rollback

```markdown
# Rollback Plan: N8N Workflow Update

## Operation
Update customer onboarding workflow v4.5

## Rollback Procedure
```bash
#!/bin/bash
# rollback-n8n-workflow.sh

WORKFLOW_ID="customer-onboarding"
BACKUP_FILE="workflow-customer-onboarding-v4.4.json"

echo "Rolling back N8N workflow..."

# 1. Deactivate current workflow
curl -X POST http://n8n:5678/api/v1/workflows/$WORKFLOW_ID/deactivate \
  -H "X-N8N-API-KEY: $N8N_API_KEY"

# 2. Restore previous version
curl -X PUT http://n8n:5678/api/v1/workflows/$WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @$BACKUP_FILE

# 3. Activate restored workflow
curl -X POST http://n8n:5678/api/v1/workflows/$WORKFLOW_ID/activate \
  -H "X-N8N-API-KEY: $N8N_API_KEY"

# 4. Verify workflow active
curl http://n8n:5678/api/v1/workflows/$WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.active'

# 5. Test workflow execution
curl -X POST http://n8n:5678/webhook-test/customer-onboarding \
  -d '{"test": true}'

echo "Rollback complete!"
```

**Time Estimate**: 2 minutes
**Automation**: Fully automated
**Manual Steps**: Verify test execution output
**Partial Rollback**: Can rollback individual nodes if needed
```

## Rollback Best Practices

### Planning Phase
1. **Design for Rollback**: Consider rollback during design phase
2. **Backward Compatibility**: Maintain backward compatibility when possible
3. **Feature Flags**: Use feature flags for risky features
4. **Blue-Green Deployments**: Enable instant rollback
5. **Database Migrations**: Make migrations reversible

### Testing Phase
1. **Test Rollback Early**: Test rollback as soon as change is deployed to staging
2. **Automate Testing**: Automated rollback tests in CI/CD
3. **Load Test Rollback**: Verify rollback works under load
4. **Time Rollback**: Measure rollback time
5. **Document Issues**: Record any rollback issues found

### Execution Phase
1. **Pre-Rollback Checklist**: Always verify prerequisites
2. **Monitor Closely**: Watch metrics during rollback
3. **Verify Thoroughly**: Don't skip verification steps
4. **Document Everything**: Log all actions taken
5. **Communicate Status**: Keep stakeholders informed

### Post-Rollback Phase
1. **Root Cause Analysis**: Understand why rollback was needed
2. **Update Documentation**: Improve rollback plan based on experience
3. **Fix Forward**: Plan the fix for next deployment
4. **Share Learnings**: Document lessons learned
5. **Improve Process**: Update rollback procedures as needed

## Conclusion

The Rollback Plans System ensures that every union operation has a tested, documented, and time-bound recovery path. This safety net allows teams to move fast while maintaining the confidence that any production change can be safely reversed if issues arise.

**Remember**: The best rollback is the one you never need to execute, but must always be ready to use.

## Integration with Other Systems

- **Permit System**: Rollback plan required for permit approval
- **Worker Certification**: Higher certification levels require more comprehensive rollback plans
- **Monitoring**: Automated triggers integrated with monitoring system
- **Incident Response**: Rollback procedures part of incident response playbook
- **Audit Trail**: All rollback executions logged for compliance

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Owner**: Development Master
**Next Review**: 2025-12-16
