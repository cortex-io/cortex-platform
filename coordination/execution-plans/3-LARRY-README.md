# 3-Larry Distributed Orchestration - Quick Start Guide

Welcome to the ultimate demonstration of distributed AI orchestration! This guide will help you execute the 3-Larry orchestration system across your K3s cluster "Larry & the Darryls".

## What Is This?

The 3-Larry orchestration is a distributed AI system where **3 independent Larry instances** (coordinator-master agents) each lead their own domain with dedicated workers:

- **LARRY-01:** Infrastructure & Database Operations (4 workers)
- **LARRY-02:** Security & Compliance (4 workers)
- **LARRY-03:** Development & Inventory (8 workers)

All 3 Larrys coordinate via **Redis pub/sub** using lock-based task assignment to prevent duplicate work, achieving true distributed orchestration.

## Architecture

```
K3s Cluster "Larry & the Darryls"
├── k3s-master01 → Larry-01 coordinator → Workers on k3s-worker01
├── k3s-master02 → Larry-02 coordinator → Workers on k3s-worker02
└── k3s-master03 → Larry-03 coordinator → Workers on k3s-worker03 + k3s-worker04

Redis Coordination Hub (redis-ha namespace)
├── Distributed locking (prevent duplicate work)
├── Progress tracking (real-time status)
├── Inter-Larry messaging (pub/sub)
└── Shared state (task results)
```

## Prerequisites

1. **K3s Cluster:** 3 master nodes + 4 worker nodes
2. **Redis Cluster:** Deployed in `redis-ha` namespace
3. **Tools Installed:**
   - `kubectl` (K8s CLI)
   - `redis-cli` (Redis CLI)
   - `jq` (JSON processor)
   - `python3` (for dashboard and reporting)

## File Structure

```
cortex/
├── coordination/execution-plans/
│   ├── 3-LARRY-ORCHESTRATION-PLAN.md    # Complete execution strategy
│   ├── COORDINATION-PROTOCOL.md          # Redis coordination details
│   └── 3-LARRY-README.md                 # This file
├── k8s/deployments/
│   ├── larry-01-phase.yaml               # Larry-01 K8s deployment
│   ├── larry-02-phase.yaml               # Larry-02 K8s deployment
│   └── larry-03-phase.yaml               # Larry-03 K8s deployment
└── scripts/
    ├── execute-3-larry-orchestration.sh  # Main execution script
    ├── larry-dashboard.py                # Real-time monitoring dashboard
    └── aggregate-larry-reports.py        # Final report aggregation
```

## Quick Start

### Step 1: Review the Plan

Read the comprehensive orchestration plan:

```bash
cat coordination/execution-plans/3-LARRY-ORCHESTRATION-PLAN.md
```

This document covers:
- Phase distribution strategy
- Worker responsibilities
- Timeline and success criteria
- Token budgets
- Risk mitigation

### Step 2: Launch the 3-Larry Orchestration

Execute the automated launcher:

```bash
./scripts/execute-3-larry-orchestration.sh
```

This script will:
1. Check prerequisites (cluster, Redis connectivity)
2. Initialize Redis coordination state
3. Deploy all 3 Larry instances simultaneously
4. Monitor progress with real-time updates
5. Trigger Phase 4 convergence when all complete
6. Generate final aggregated report

### Step 3: Monitor Real-Time (Optional)

In a separate terminal, launch the live dashboard:

```bash
./scripts/larry-dashboard.py
```

This provides:
- Larry-01, Larry-02, Larry-03 progress bars
- Active task status
- Security findings (Larry-02)
- Inventory metrics (Larry-03)
- Real-time event log

### Step 4: Review Results

After execution completes (~40 minutes), review the final report:

```bash
cat /coordination/reports/3-LARRY-EXECUTION-SUMMARY.md
```

Individual Larry reports:
```bash
cat /coordination/reports/larry-01-final.json  # Infrastructure results
cat /coordination/reports/larry-02-final.json  # Security findings
cat /coordination/reports/larry-03-final.json  # Development metrics
```

## Execution Timeline

```
T+0:00  → Launch all 3 Larrys simultaneously
T+0:01  → Larry-01, Larry-02, Larry-03 spawn workers
T+0:10  → Mid-phase progress check
T+0:25  → Larry-01 completes (Infrastructure)
T+0:30  → Larry-02 completes (Security)
T+0:30  → Larry-03 completes (Development)
T+0:31  → Barrier sync - all Larrys converge
T+0:35  → Phase 4: Cross-validation
T+0:40  → Final report generated ✅
```

## What Each Larry Does

### LARRY-01: Infrastructure & Database Operations
**Duration:** 25 minutes | **Workers:** 4 on k3s-worker01

**Tasks:**
1. Fix PgAdmin CrashLoopBackOff in `database` namespace
2. Consolidate multiple PostgreSQL instances into one
3. Optimize database performance (PgBouncer, indexing)
4. Deploy comprehensive monitoring (Grafana dashboards)

**Success Criteria:**
- PgAdmin operational (0 restarts in 30 min)
- Single consolidated PostgreSQL instance
- P95 latency < 100ms
- Grafana dashboards showing real-time metrics

### LARRY-02: Security & Compliance
**Duration:** 30 minutes | **Workers:** 4 on k3s-worker02

**Tasks:**
1. Security scan all namespaces (database, monitoring, n8n, ingress, ai-agents, etc.)
2. CVE vulnerability assessment (CVSS ≥ 7.0)
3. Dependency audits (npm, pip, go.mod)
4. Generate automated fix PRs for critical issues

**Success Criteria:**
- 100% namespace coverage
- CVE report with CVSS scoring
- Minimum 3 automated fix PRs created
- Compliance audit trail generated

### LARRY-03: Development & Inventory
**Duration:** 30 minutes | **Workers:** 8 on k3s-worker03 + k3s-worker04

**Tasks:**
1. Deep catalog discovery (all K8s deployments, Helm releases)
2. Asset classification and tagging (database, ai, monitoring)
3. Lineage mapping (app → chart → image)
4. Code quality analysis and improvements
5. Test coverage expansion (target: +10%)
6. Documentation generation (API docs, architecture diagrams)

**Success Criteria:**
- Complete asset inventory (150+ resources)
- Lineage graph visualized
- Test coverage +10% or more
- 5+ PRs created (features, tests, docs)

## Advanced Usage

### Monitor Specific Larry

```bash
# Watch Larry-01 workers
kubectl get pods -n larry-01 -w

# Check Larry-02 security findings
redis-cli -h redis-cluster.redis-ha.svc.cluster.local HGETALL phase:larry-02:findings

# Monitor Larry-03 inventory progress
redis-cli -h redis-cluster.redis-ha.svc.cluster.local GET phase:larry-03:inventory:assets_discovered
```

### Subscribe to Coordination Events

```bash
# Real-time coordination events
redis-cli -h redis-cluster.redis-ha.svc.cluster.local SUBSCRIBE larry:coordination

# Critical alerts
redis-cli -h redis-cluster.redis-ha.svc.cluster.local SUBSCRIBE larry:alerts
```

### Manual Report Aggregation

If you need to regenerate the final report:

```bash
python3 scripts/aggregate-larry-reports.py \
  --larry-01-report /coordination/reports/larry-01-final.json \
  --larry-02-report /coordination/reports/larry-02-final.json \
  --larry-03-report /coordination/reports/larry-03-final.json \
  --output /coordination/reports/3-LARRY-EXECUTION-SUMMARY.md
```

## Troubleshooting

### Larry Not Starting

Check coordinator pod logs:
```bash
kubectl logs -n larry-01 -l app=larry-coordinator
kubectl logs -n larry-02 -l app=larry-coordinator
kubectl logs -n larry-03 -l app=larry-coordinator
```

### Workers Failing

Check worker job status:
```bash
kubectl get jobs -n larry-01
kubectl describe job larry-01-cleanup-worker -n larry-01
```

View worker logs:
```bash
kubectl logs -n larry-01 job/larry-01-cleanup-worker
```

### Redis Connection Issues

Test Redis connectivity:
```bash
redis-cli -h redis-cluster.redis-ha.svc.cluster.local -p 6379 ping
```

Check Redis pod status:
```bash
kubectl get pods -n redis-ha
```

### Task Lock Conflicts

View all active task locks:
```bash
redis-cli -h redis-cluster.redis-ha.svc.cluster.local --scan --pattern "task:lock:*"
```

Clear stuck locks (if needed):
```bash
redis-cli -h redis-cluster.redis-ha.svc.cluster.local DEL task:lock:fix-pgadmin-crashloop
```

## Cleanup

After execution, you can clean up resources:

```bash
# Delete Larry deployments
kubectl delete namespace larry-01
kubectl delete namespace larry-02
kubectl delete namespace larry-03

# Clean up Redis state
redis-cli -h redis-cluster.redis-ha.svc.cluster.local --scan --pattern "phase:larry-*" | \
  xargs redis-cli -h redis-cluster.redis-ha.svc.cluster.local del

redis-cli -h redis-cluster.redis-ha.svc.cluster.local --scan --pattern "task:*" | \
  xargs redis-cli -h redis-cluster.redis-ha.svc.cluster.local del

redis-cli -h redis-cluster.redis-ha.svc.cluster.local --scan --pattern "worker:*" | \
  xargs redis-cli -h redis-cluster.redis-ha.svc.cluster.local del
```

## Understanding Redis Coordination

The 3 Larrys coordinate using Redis:

**Task Locking:**
```python
# Larry-01 attempts to acquire task lock
SET task:lock:fix-pgadmin-crashloop "larry-01" NX EX 3600

# If another Larry tries to claim the same task
# Redis returns nil (lock already exists)
# Task conflict avoided ✅
```

**Progress Broadcasting:**
```python
# Larry-02 updates progress
SET phase:larry-02:progress 50
PUBLISH larry:coordination '{"from":"larry-02","progress":50,"message":"2/4 workers done"}'

# All Larrys receive update via SUBSCRIBE
```

**Barrier Synchronization:**
```python
# Wait for all Larrys to complete
while True:
    status_01 = GET phase:larry-01:status
    status_02 = GET phase:larry-02:status
    status_03 = GET phase:larry-03:status

    if all == "completed":
        initiate_phase_4()
        break
```

See `coordination/execution-plans/COORDINATION-PROTOCOL.md` for full details.

## Success Metrics

After execution, validate these metrics:

| Metric | Target | How to Check |
|--------|--------|--------------|
| All Larrys complete | Yes | Dashboard shows 100% progress |
| No task duplication | Yes | Redis lock logs show no conflicts |
| Workers on correct nodes | Yes | `kubectl get pods -o wide` |
| Infrastructure SLA met | Yes | PgAdmin 0 restarts, p95 < 100ms |
| Security scan complete | Yes | All namespaces in Larry-02 report |
| Inventory accurate | Yes | Asset count matches cluster resources |
| Final report generated | Yes | File exists at `/coordination/reports/` |

## Token Budget

Total system budget: **478k tokens**

| Larry | Personal | Workers | Total |
|-------|----------|---------|-------|
| Larry-01 | 50k | 36k | 86k |
| Larry-02 | 30k | 36k | 66k |
| Larry-03 | 90k | 76k | 166k |
| Meta-Coordinator | 50k | - | 50k |
| Emergency Reserve | 25k | - | 25k |

Monitor usage via Redis:
```bash
redis-cli -h redis-cluster.redis-ha.svc.cluster.local GET tokens:larry-01:used
```

## Architecture Highlights

This orchestration demonstrates:

1. **ASI (Autonomous Super Intelligence):**
   - Each Larry learns independently
   - Cross-master insights inform strategy
   - Performance trends guide optimization

2. **MoE (Mixture of Experts):**
   - Coordinator routes to specialists
   - Each Larry has domain expertise
   - Workers specialize further within domains

3. **RAG (Retrieval-Augmented Generation):**
   - Historical execution data informs decisions
   - Knowledge bases provide context
   - Cross-referencing master learnings

4. **Master-Worker-Observer:**
   - 3 masters (Larry-01, Larry-02, Larry-03)
   - 16 workers (distributed across 4 nodes)
   - 1 observer (dashboard agent for monitoring)

## Next Steps

After successful execution:

1. **Review Security Findings:** Address critical CVEs from Larry-02
2. **Validate Infrastructure:** Test database consolidation from Larry-01
3. **Merge Development PRs:** Review code quality improvements from Larry-03
4. **Iterate:** Run again with lessons learned

## Support

For issues or questions:

1. Check logs: `kubectl logs -n <namespace> <pod-name>`
2. Review Redis state: `redis-cli -h ... GET phase:<larry-id>:status`
3. Consult documentation: `coordination/execution-plans/*.md`
4. GitHub issues: Create issue with logs and error messages

---

**Remember:** This is the ultimate test of distributed AI orchestration. 3 autonomous Larrys, 16 workers, 40 minutes, complete system transformation. Let's show what Cortex can do!

Ready to launch? Run:
```bash
./scripts/execute-3-larry-orchestration.sh
```

**May the Larrys be with you!** 🚀
