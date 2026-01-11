# Example Project: Setup Application Monitoring Stack

## Project Overview

**Project ID**: proj-2025-monitoring-001
**PM ID**: pm-proj-2025-monitoring-001
**Priority**: Medium
**Project Type**: Single-Division Infrastructure Project

**Objective**: Deploy comprehensive monitoring stack (Prometheus, Grafana, Alertmanager) for existing production applications.

**Business Value**: Improve operational visibility, reduce incident response time, enable proactive issue detection.

**Estimated Duration**: 4 hours
**Token Budget**: 25,000 tokens

---

## Divisions Involved

1. **Monitoring** (Primary and Only)
   - Role: Deploy monitoring infrastructure, configure data sources, create dashboards
   - Tasks: 8
   - Token Allocation: 22,000

2. **Documentation** (Supporting, minimal)
   - Role: Create runbook for monitoring operations
   - Tasks: 1
   - Token Allocation: 3,000

---

## Success Criteria

1. **Deliverable** (35%): Monitoring stack deployed and operational
   - Validation: Prometheus UI accessible, scraping metrics
   - Validation: Grafana UI accessible, connected to Prometheus
   - Validation: Alertmanager operational

2. **Quality** (30%): Key application metrics visible in dashboards
   - Validation: At least 3 dashboards created (infra, apps, business)
   - Validation: Metrics from all production services visible

3. **Alerting** (20%): Critical alerts configured and tested
   - Validation: At least 5 alert rules configured
   - Validation: Test alert fires and delivers via configured channel

4. **Documentation** (15%): Runbook complete with common operations
   - Validation: Runbook covers alert response, dashboard usage, troubleshooting

**Minimum Passing Score**: 80%

---

## Project Phases

### Phase 1: Initiation & Planning (30 minutes)

**Activities**:
- Review current infrastructure and applications to monitor
- Identify key metrics to track
- Define alert thresholds
- Plan dashboard layout
- Create task breakdown

**Deliverables**:
- Monitoring requirements document
- List of services to monitor
- Alert rule definitions
- Dashboard specifications

**Exit Criteria**:
- Monitoring division acknowledges project
- Requirements documented
- Plan approved

---

### Phase 2: Infrastructure Deployment (1.5 hours)

**Activities**:
- Deploy Prometheus server
- Deploy Grafana server
- Deploy Alertmanager
- Configure service discovery
- Set up persistent storage

**Tasks**:

**Monitoring**:
1. `task-mon-001`: Deploy Prometheus server (30 min, 4k tokens)
   - Deploy via Docker/K8s
   - Configure retention policy
   - Set up persistent volume

2. `task-mon-002`: Configure Prometheus service discovery (30 min, 3k tokens)
   - Depends on: task-mon-001
   - Configure scrape configs for all services
   - Validate metrics collection

3. `task-mon-003`: Deploy Grafana (20 min, 3k tokens)
   - Depends on: task-mon-001
   - Configure data source (Prometheus)
   - Set up authentication

4. `task-mon-004`: Deploy Alertmanager (20 min, 2k tokens)
   - Configure notification channels (Slack, email, etc.)
   - Set up alert routing rules

**Deliverables**:
- Prometheus operational and scraping metrics
- Grafana operational and connected to Prometheus
- Alertmanager operational with notification channels configured
- All services accessible via browser

**Exit Criteria**:
- All three services healthy and accessible
- Prometheus shows targets being scraped
- Grafana can query Prometheus successfully
- Alertmanager connectivity test passes

---

### Phase 3: Dashboard Creation (1.5 hours)

**Activities**:
- Create infrastructure dashboards
- Create application performance dashboards
- Create business metrics dashboards
- Test and refine visualizations

**Tasks**:

**Monitoring**:
1. `task-mon-005`: Create infrastructure dashboard (30 min, 4k tokens)
   - Depends on: task-mon-002, task-mon-003
   - CPU, Memory, Disk, Network metrics
   - Node health and status

2. `task-mon-006`: Create application performance dashboard (30 min, 4k tokens)
   - Depends on: task-mon-002, task-mon-003
   - Request rates, error rates, latencies (RED metrics)
   - Service dependencies and health

3. `task-mon-007`: Create business metrics dashboard (30 min, 3k tokens)
   - Depends on: task-mon-002, task-mon-003
   - Key business KPIs
   - User activity metrics

**Deliverables**:
- Three operational dashboards in Grafana
- All key metrics visualized
- Dashboard templates exported for version control

**Exit Criteria**:
- All dashboards render correctly
- Metrics show realistic data (not empty)
- Dashboards are organized and labeled clearly

---

### Phase 4: Alert Configuration & Testing (1 hour)

**Activities**:
- Configure alert rules in Prometheus
- Test alert firing
- Validate notification delivery
- Document alert response procedures

**Tasks**:

**Monitoring**:
1. `task-mon-008`: Configure alert rules (40 min, 4k tokens)
   - Depends on: task-mon-001, task-mon-004
   - Critical alerts: service down, high error rate, resource exhaustion
   - Warning alerts: elevated latency, approaching limits
   - Connect to Alertmanager

2. `task-mon-009`: Test alert delivery (20 min, 2k tokens)
   - Depends on: task-mon-008
   - Trigger test alerts
   - Verify delivery to notification channels
   - Validate alert format and content

**Documentation**:
1. `task-doc-001`: Create monitoring runbook (30 min, 3k tokens)
   - Can start earlier, finalize now
   - Alert response procedures
   - Dashboard usage guide
   - Common troubleshooting steps

**Deliverables**:
- Alert rules configured in Prometheus
- Test alerts successfully delivered
- Monitoring runbook complete

**Exit Criteria**:
- At least 5 alert rules active
- Test alert received in notification channel
- Runbook covers all common scenarios

---

### Phase 5: Validation & Closure (30 minutes)

**Activities**:
- Final validation of all success criteria
- Create project completion report
- Document lessons learned
- Archive artifacts

**PM Tasks**:
1. Validate all success criteria met
2. Create completion report
3. Update knowledge base with monitoring patterns
4. Hand off to coordinator

**Deliverables**:
- Validation checklist (all items passed)
- Project completion report
- Lessons learned document

**Exit Criteria**:
- All success criteria score ≥80%
- Documentation complete
- Artifacts archived

---

## Dependency Map

```
┌─────────────┐
│ Phase 1     │ Initiation & Planning
└──────┬──────┘
       │
┌──────▼──────┐
│ Phase 2     │ Infrastructure Deployment
│             │
│ mon-001 ────┼──> mon-002
│     │       │
│     ├───────┼──> mon-003
│     │       │
│     └───────┼──> mon-004
└──────┬──────┘
       │
┌──────▼──────┐
│ Phase 3     │ Dashboard Creation
│             │
│ mon-005     │ (all parallel, depend on mon-002 & mon-003)
│ mon-006     │
│ mon-007     │
└──────┬──────┘
       │
┌──────▼──────┐
│ Phase 4     │ Alert Configuration
│             │
│ mon-008 ────┼──> mon-009
│             │
│ doc-001     │ (parallel)
└──────┬──────┘
       │
┌──────▼──────┐
│ Phase 5     │ Validation & Closure
└─────────────┘
```

**Critical Path**: mon-001 → mon-002 → mon-005/006/007 → mon-008 → mon-009
**Duration**: ~3.5 hours
**Parallelism Opportunities**: Dashboard creation (Phase 3), documentation (Phase 4)

---

## Risk Register

### Risk 1: Service Discovery Configuration Issues

**Severity**: Medium
**Probability**: Medium
**Impact**: Delays Phase 2, metrics not collected

**Triggers**:
- Prometheus can't discover services
- Scrape configs fail validation
- Firewall blocking metric endpoints

**Mitigation**:
- Use proven service discovery patterns from knowledge base
- Validate connectivity to each service before scraping
- Have fallback to static configurations

**Contingency**:
- If auto-discovery fails: Use static scrape configs
- Allocate +30 minutes for debugging
- Escalate if blocked >1 hour

---

### Risk 2: Insufficient Metrics from Applications

**Severity**: Low
**Probability**: High
**Impact**: Dashboards incomplete, limited visibility

**Triggers**:
- Applications don't expose metrics endpoints
- Metrics format incompatible with Prometheus
- Missing key business metrics

**Mitigation**:
- Survey applications before project start
- Document which metrics are available
- Set realistic dashboard expectations

**Contingency**:
- If metrics missing: Document gaps, create follow-up tasks
- Use available metrics, note limitations
- Project success not blocked by this

---

### Risk 3: Alert Notification Delivery Failure

**Severity**: Medium
**Probability**: Low
**Impact**: Alerts configured but not delivered, defeats purpose

**Triggers**:
- Alertmanager can't reach notification service (Slack, email)
- Authentication issues
- Network connectivity problems

**Mitigation**:
- Test notification channel connectivity early
- Validate credentials before configuring
- Have backup notification channel

**Contingency**:
- If primary channel fails: Switch to backup (e.g., email if Slack fails)
- Allocate +20 minutes for troubleshooting
- Ensure at least one channel works

---

## Timeline & Resource Plan

### Timeline Summary

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Initiation | 0.5h | 0.5h |
| Phase 2: Infrastructure | 1.5h | 2h |
| Phase 3: Dashboards | 1.5h | 3.5h |
| Phase 4: Alerting | 1h | 4.5h |
| Phase 5: Closure | 0.5h | 5h |
| **Buffer (20%)** | **-1h** | **4h** |

**Target Completion**: 4 hours

---

### Token Allocation by Phase

| Phase | Monitoring | Documentation | PM | Total |
|-------|-----------|---------------|-----|-------|
| Phase 1 | 1,000 | 0 | 500 | 1,500 |
| Phase 2 | 12,000 | 0 | 500 | 12,500 |
| Phase 3 | 11,000 | 0 | 500 | 11,500 |
| Phase 4 | 6,000 | 3,000 | 500 | 9,500 |
| Phase 5 | 0 | 0 | 1,000 | 1,000 |
| **Total** | **30,000** | **3,000** | **3,000** | **36,000** |

**Actual Budget**: 25,000 tokens
**Buffer**: -11,000 tokens (estimates are conservative, expect to come in under)

---

## Handoff Sequence

### Phase 1: Initiation

```bash
# PM notifies monitoring division
pm-to-monitoring-notice.json
```

---

### Phase 2: Infrastructure (T+0.5h)

```bash
# Deploy Prometheus
pm-to-mon-001.json
mon-to-pm-001-complete.json

# Configure service discovery
pm-to-mon-002.json

# Deploy Grafana and Alertmanager (parallel)
pm-to-mon-003.json
pm-to-mon-004.json

# Wait for all Phase 2 tasks
mon-to-pm-002-complete.json
mon-to-pm-003-complete.json
mon-to-pm-004-complete.json
```

---

### Phase 3: Dashboards (T+2h)

```bash
# Create all dashboards (can be parallel)
pm-to-mon-005.json  # Infrastructure dashboard
pm-to-mon-006.json  # Application dashboard
pm-to-mon-007.json  # Business metrics dashboard

# Wait for completion
mon-to-pm-005-complete.json
mon-to-pm-006-complete.json
mon-to-pm-007-complete.json
```

---

### Phase 4: Alerting (T+3.5h)

```bash
# Configure alerts
pm-to-mon-008.json
mon-to-pm-008-complete.json

# Test alert delivery
pm-to-mon-009.json

# Documentation (parallel with testing)
pm-to-doc-001.json

# Wait for completion
mon-to-pm-009-complete.json
doc-to-pm-001-complete.json
```

---

### Phase 5: Closure (T+4.5h)

```bash
# PM performs internal validation
# No handoffs needed

# Final handoff to coordinator
pm-to-coordinator-project-complete.json
```

---

## Success Metrics

**Schedule Performance**:
- Target: ≤4 hours
- Measured: Actual completion time
- Success: ≤4 hours

**Budget Performance**:
- Target: ≤25,000 tokens
- Measured: Actual tokens used
- Success: ≤25,000 tokens

**Quality Score**:
- Target: ≥80% success criteria met
- Measured: Weighted success criteria score
- Success: ≥80%

**Operational Readiness**:
- Target: Monitoring stack production-ready
- Measured: All components operational, alerts firing correctly
- Success: Pass operational readiness checklist

---

## Operational Readiness Checklist

Before project closure, validate:

**Prometheus**:
- [ ] Service is running and healthy
- [ ] All configured targets are being scraped (green status)
- [ ] Retention policy configured appropriately
- [ ] Persistent storage working (metrics survive restart)
- [ ] Web UI accessible and responsive

**Grafana**:
- [ ] Service is running and healthy
- [ ] Data source connected to Prometheus (green status)
- [ ] At least 3 dashboards created and functional
- [ ] Dashboards show realistic data (not empty)
- [ ] Authentication configured
- [ ] Web UI accessible and responsive

**Alertmanager**:
- [ ] Service is running and healthy
- [ ] At least one notification channel configured
- [ ] Test alert successfully delivered
- [ ] Alert routing rules validated
- [ ] Web UI accessible

**Documentation**:
- [ ] Runbook created and reviewed
- [ ] Alert response procedures documented
- [ ] Dashboard usage guide included
- [ ] Common troubleshooting steps documented

**Score**: 17/17 = 100% (Pass), <14/17 = <80% (Fail)

---

## Lessons Learned (Template)

*To be completed at project closure*

**What Went Well**:
-

**What Could Be Improved**:
-

**Technical Insights**:
-

**Monitoring Patterns to Reuse**:
-

**Knowledge Base Updates**:
-

**Recommendations for Future Monitoring Projects**:
-

---

## Artifacts

**Deliverables**:
- Prometheus server operational
- Grafana server operational with dashboards
- Alertmanager operational with configured channels
- Monitoring runbook

**Configuration Files** (to be version controlled):
- `prometheus/prometheus.yml` - Prometheus configuration
- `prometheus/alerts.yml` - Alert rule definitions
- `grafana/dashboards/*.json` - Dashboard definitions
- `alertmanager/alertmanager.yml` - Alertmanager configuration

**Documentation**:
- Monitoring runbook
- Dashboard usage guide
- Alert response procedures

**Reports**:
- Project completion report
- Operational readiness validation
- Lessons learned

---

## Notes

**Why Single-Division Project Still Needs PM**:

Even though this project involves primarily one division (Monitoring), a PM is valuable because:

1. **Coordination Complexity**: 9 sequential/parallel tasks requiring careful orchestration
2. **Multi-Phase Execution**: 5 phases with clear dependencies and handoffs
3. **Resource Management**: Token budget tracking and allocation
4. **Risk Management**: Multiple technical risks requiring monitoring and mitigation
5. **Quality Gates**: Success criteria validation at each phase
6. **Documentation**: Project tracking and lessons learned for future projects

**When NOT to Use PM for Single-Division Projects**:
- Simple projects with <3 tasks
- Single-phase execution (no dependencies)
- Estimated duration <2 hours
- Low complexity, routine operations

**This Project Requires PM Because**:
- 9 tasks across 5 phases
- 4-hour duration with critical dependencies
- Multiple technical risks
- Production system impact (monitoring is critical)
- Reusable patterns for future monitoring projects

---

**Project Status**: Template (not executed)
**Last Updated**: 2025-12-09
**PM Template Version**: 1.0.0
