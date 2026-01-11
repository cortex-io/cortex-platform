# Worker Certification System Architecture

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TASK ARRIVES                                 │
│                    (from coordinator/user)                           │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              v
┌─────────────────────────────────────────────────────────────────────┐
│                    CERTIFICATION CHECKER                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. Analyze Environment (prod vs dev/test)                   │  │
│  │  2. Assess Data Sensitivity (PII/PHI/financial)              │  │
│  │  3. Evaluate Operation Risk (migration/infra/security)       │  │
│  │  4. Calculate Impact Scope (customer/system/service)         │  │
│  │  5. Compute Risk Score (0-50)                                │  │
│  │  6. Determine Certification Level Required (0-4)             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────┬────────────────────────────────┬────────────────────┘
              │                                │
         LOW RISK                         HIGH RISK
       (score 0-5)                      (score 6-50)
              │                                │
              v                                v
    ┌──────────────────┐           ┌────────────────────────┐
    │  NON-UNION PATH  │           │     UNION PATH         │
    │   (Fast Path)    │           │   (Approval Path)      │
    └──────┬───────────┘           └────────┬───────────────┘
           │                                 │
           v                                 v
    ┌──────────────────┐           ┌────────────────────────┐
    │ Auto-Approve     │           │  Issue Permit Request  │
    │ (instant)        │           └────────┬───────────────┘
    └──────┬───────────┘                    │
           │                                 v
           │                        ┌────────────────────────┐
           │                        │  Approval Workflow     │
           │                        │  ┌──────────────────┐  │
           │                        │  │ Level 2: 1 mgr   │  │
           │                        │  │ Level 3: 2 dirs  │  │
           │                        │  │ Level 4: 3+ execs│  │
           │                        │  └──────────────────┘  │
           │                        └────────┬───────────────┘
           │                                 │
           │                        ┌────────v───────────────┐
           │                        │ Collect Approvals      │
           │                        │ (hours to weeks)       │
           │                        └────────┬───────────────┘
           │                                 │
           │                        ┌────────v───────────────┐
           │                        │  Issue Permit          │
           │                        │  (with constraints)    │
           │                        └────────┬───────────────┘
           │                                 │
           └─────────────────┬───────────────┘
                             v
                   ┌──────────────────────┐
                   │   SPAWN WORKER       │
                   │ (non-union or union) │
                   └──────────┬───────────┘
                              │
                              v
                   ┌──────────────────────┐
                   │  EXECUTE TASK        │
                   │  (with monitoring)   │
                   └──────────┬───────────┘
                              │
                 ┌────────────┴────────────┐
                 v                         v
          ┌─────────────┐          ┌──────────────┐
          │   SUCCESS   │          │    FAILURE   │
          └─────┬───────┘          └──────┬───────┘
                │                         │
                │                         v
                │                  ┌──────────────┐
                │                  │  ROLLBACK    │
                │                  └──────┬───────┘
                │                         │
                └─────────────┬───────────┘
                              v
                   ┌──────────────────────┐
                   │  CLOSE PERMIT        │
                   │  (audit summary)     │
                   └──────────┬───────────┘
                              │
                              v
                   ┌──────────────────────┐
                   │   LOG TO AUDIT DB    │
                   └──────────────────────┘
```

## Risk Score Calculation

```
┌───────────────────────────────────────────────────────────────────┐
│                      RISK FACTORS (0-10 each)                     │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Environment Risk                                                 │
│  ┌─────────────────────────────────────────────┐                │
│  │ Local: 0  Dev: 1  Staging: 5  Prod: 10     │                │
│  └─────────────────────────────────────────────┘                │
│                          +                                        │
│  Reversibility Risk                                               │
│  ┌─────────────────────────────────────────────┐                │
│  │ Full: 0  Auto: 3  Complex: 7  Irreversible: 10│              │
│  └─────────────────────────────────────────────┘                │
│                          +                                        │
│  Data Sensitivity Risk                                            │
│  ┌─────────────────────────────────────────────┐                │
│  │ Public: 0  Test: 3  Internal: 7  PII/PHI/Fin: 10│           │
│  └─────────────────────────────────────────────┘                │
│                          +                                        │
│  Impact Scope Risk                                                │
│  ┌─────────────────────────────────────────────┐                │
│  │ Component: 1  Service: 3  Multi-Service: 6  │                │
│  │ System-wide: 8  Multi-region: 10            │                │
│  └─────────────────────────────────────────────┘                │
│                          +                                        │
│  Customer Impact Risk                                             │
│  ┌─────────────────────────────────────────────┐                │
│  │ None: 0  Internal: 3  Segment: 7  All: 10  │                │
│  └─────────────────────────────────────────────┘                │
│                          =                                        │
│                  TOTAL RISK SCORE (0-50)                         │
│                                                                   │
└─────────────────────┬─────────────────────────────────────────────┘
                      │
         ┌────────────┼────────────┬────────────┬─────────────┐
         │            │            │            │             │
       0-5         6-20        21-35       36-50         50
         │            │            │            │             │
         v            v            v            v             v
    Level 0      Level 2      Level 3      Level 4      Level 4
   Non-Union  Union Standard Union Advanced Union Master Union Master
```

## Certification Levels Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LEVEL 4: MASTER UNION                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Multi-region deployments                                     │ │
│  │ • System architecture changes                                  │ │
│  │ • 3+ executive approvals                                       │ │
│  │ • Change Advisory Board                                        │ │
│  │ • 7 year audit retention                                       │ │
│  │ • Token allocation: 30,000+                                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            ▲
            │ Promotion requires 180+ days Level 3 experience
            │
┌─────────────────────────────────────────────────────────────────────┐
│                      LEVEL 3: ADVANCED UNION                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Critical production systems                                  │ │
│  │ • Sensitive data (PII/PHI/Financial)                          │ │
│  │ • Database migrations                                          │ │
│  │ • 2 director approvals                                         │ │
│  │ • 1 year audit retention                                       │ │
│  │ • Token allocation: 25,000                                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            ▲
            │ Promotion requires 90+ days Level 2 experience
            │
┌─────────────────────────────────────────────────────────────────────┐
│                      LEVEL 2: STANDARD UNION                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Standard production operations                               │ │
│  │ • Production deployments                                       │ │
│  │ • Configuration changes                                        │ │
│  │ • 1 manager approval                                           │ │
│  │ • 90 day audit retention                                       │ │
│  │ • Token allocation: 20,000                                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            ▲
            │ Promotion requires 30+ days non-union experience
            │
┌─────────────────────────────────────────────────────────────────────┐
│                      LEVEL 1: BASIC CERTIFIED                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Read-only production access                                  │ │
│  │ • Monitoring and observability                                 │ │
│  │ • Basic approval or auto-approved                             │ │
│  │ • 30 day audit retention                                       │ │
│  │ • Token allocation: 15,000                                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            ▲
            │ Certification process
            │
┌─────────────────────────────────────────────────────────────────────┐
│                      LEVEL 0: NON-UNION                             │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Development and testing only                                 │ │
│  │ • No production access                                         │ │
│  │ • No approvals required                                        │ │
│  │ • 30 day audit retention                                       │ │
│  │ • Token allocation: 10,000                                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Permit Lifecycle States

```
┌───────────────────────────────────────────────────────────────┐
│                        PERMIT STATES                          │
└───────────────────────────────────────────────────────────────┘

    REQUESTED
        │
        │ Approver reviews
        v
    UNDER_REVIEW ────┐
        │            │ Reject
        │ Approve    v
        │         REJECTED
        │            │
        v            │ Archived
    APPROVED         v
        │         ARCHIVED
        │ Issue permit
        v
    ACTIVE ──────┐
        │        │ Revoke (safety violation)
        │        v
        │     REVOKED
        │        │
        │ Execute operation
        v        │
    EXECUTING    │
        │        │
        ├─ Success
        │  Failure ┘
        v
    COMPLETED
        │
        │ Close and audit
        v
    CLOSED
        │
        │ Archive
        v
    ARCHIVED
```

## Worker Types and Access Matrix

```
┌────────────────────────────────────────────────────────────────────┐
│                        ACCESS MATRIX                               │
├────────────┬───────────┬───────────┬─────────────┬─────────────────┤
│ Worker     │ Dev/Test  │ Staging   │ Production  │ Production      │
│ Level      │           │           │ (Standard)  │ (Critical)      │
├────────────┼───────────┼───────────┼─────────────┼─────────────────┤
│ Level 0    │    ✓      │     ✗     │      ✗      │       ✗         │
│ Non-Union  │   Full    │    No     │     No      │      No         │
│            │  Access   │  Access   │   Access    │    Access       │
├────────────┼───────────┼───────────┼─────────────┼─────────────────┤
│ Level 1    │    ✓      │     ✓     │   ✓ (RO)    │     ✗           │
│ Basic      │   Full    │   Full    │  Read-Only  │     No          │
│            │           │           │   w/permit  │                 │
├────────────┼───────────┼───────────┼─────────────┼─────────────────┤
│ Level 2    │    ✓      │     ✓     │      ✓      │     ✗           │
│ Standard   │   Full    │   Full    │  w/permit   │     No          │
│ Union      │           │           │  1 approval │                 │
├────────────┼───────────┼───────────┼─────────────┼─────────────────┤
│ Level 3    │    ✓      │     ✓     │      ✓      │      ✓          │
│ Advanced   │   Full    │   Full    │  w/permit   │  w/permit       │
│ Union      │           │           │  2 approvals│  2 approvals    │
├────────────┼───────────┼───────────┼─────────────┼─────────────────┤
│ Level 4    │    ✓      │     ✓     │      ✓      │      ✓          │
│ Master     │   Full    │   Full    │  w/permit   │  w/permit       │
│ Union      │           │           │  3 approvals│  3+ approvals   │
└────────────┴───────────┴───────────┴─────────────┴─────────────────┘

Legend: ✓ = Allowed    ✗ = Blocked    RO = Read-Only
```

## Approval Workflow Paths

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPROVAL PATHS                               │
└─────────────────────────────────────────────────────────────────────┘

FAST PATH (Level 0 - Non-Union)
─────────────────────────────────
Task → Auto-Check → Execute
       (<5 seconds)

STANDARD PATH (Level 2 - Union)
────────────────────────────────
Task → Permit Request → Manager Review → Approval → Execute
       (minutes)         (hours)          (hours)    (hours)

ADVANCED PATH (Level 3 - Union)
────────────────────────────────
Task → Permit Request → Director 1 Review ──┐
       (minutes)         (hours)             │
                                             ├→ Both Approve → Execute
                       Director 2 Review ────┘   (days)         (hours)
                         (hours)

MASTER PATH (Level 4 - Union)
──────────────────────────────
Task → Permit Request → VP Review ─────────┐
       (minutes)         (days)             │
                       CTO Review ──────────┤
                         (days)             ├→ All Approve + CAB → Execute
                       CISO Review ─────────┤   (weeks)            (hours)
                         (days)             │
                       CAB Meeting ─────────┘
                         (weeks)

EMERGENCY PATH (Temporary Level 3)
───────────────────────────────────
Incident → Emergency Request → IC Approval → Execute → Auto-Revoke
           (seconds)            (<15 min)     (1 hour)   (1 hour)
```

## Safety Enforcement Points

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SAFETY ENFORCEMENT LAYERS                        │
└─────────────────────────────────────────────────────────────────────┘

Layer 1: Pre-Analysis
─────────────────────
┌──────────────────┐
│ Task arrives     │
│ ↓                │
│ Environment      │──→ Production detected → Require union
│ detection        │
└──────────────────┘

Layer 2: Risk Assessment
────────────────────────
┌──────────────────┐
│ Risk score       │
│ calculation      │──→ High risk → Require higher certification
│ ↓                │
│ Risk > 35        │──→ Level 4 required
└──────────────────┘

Layer 3: Certification Check
────────────────────────────
┌──────────────────┐
│ Worker           │
│ certification    │──→ Insufficient level → HARD BLOCK
│ validation       │
└──────────────────┘

Layer 4: Permit Validation
──────────────────────────
┌──────────────────┐
│ Active permit    │
│ check            │──→ No permit → HARD BLOCK
│ ↓                │
│ Permit scope     │──→ Out of scope → HARD BLOCK
│ validation       │
└──────────────────┘

Layer 5: Real-time Monitoring
──────────────────────────────
┌──────────────────┐
│ Operation        │
│ execution        │──→ Constraint violation → Auto-rollback
│ ↓                │
│ Safety metrics   │──→ Error rate high → Revoke permit
│ monitoring       │
└──────────────────┘

Layer 6: Audit Logging
──────────────────────
┌──────────────────┐
│ All operations   │
│ logged           │──→ Compliance verification
│ ↓                │
│ Tamper-proof     │──→ External audit ready
│ audit trail      │
└──────────────────┘
```

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Master    │─────────────┐
│  (spawns    │             │
│   worker)   │             │
└─────────────┘             │
                            v
                  ┌──────────────────┐
                  │ Certification    │
                  │ Checker          │
                  │                  │
    Reads ────────│ • union-         │
    Rules         │   requirements   │
                  │ • non-union-     │
                  │   guidelines     │
                  └────────┬─────────┘
                           │
                           │ Outputs
                           │ certification
                           │ decision
                           v
                  ┌──────────────────┐
                  │  If Union:       │
                  │  Permit System   │
                  │                  │
    Stores ───────│  Creates permit  │────── Stores in
    approval      │  request         │       coordination/
    records       │                  │       permits/
                  └────────┬─────────┘
                           │
                           │ Approvals
                           │ collected
                           v
                  ┌──────────────────┐
                  │  Worker          │
                  │  Execution       │
                  │                  │
    Validates ────│  Checks permit   │────── Logs to
    during        │  continuously    │       coordination/
    operation     │                  │       audit-logs/
                  └────────┬─────────┘
                           │
                           │ Operation
                           │ complete
                           v
                  ┌──────────────────┐
                  │  Audit &         │
                  │  Reporting       │
                  │                  │
    Generates ────│  • Metrics       │────── Feeds
    reports       │  • Compliance    │       dashboard
                  │  • Lessons       │
                  └──────────────────┘
```

## Integration with Cortex Ecosystem

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CORTEX INTEGRATION POINTS                        │
└─────────────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │ Coordinator  │
                         │   Master     │
                         └──────┬───────┘
                                │
                                │ Routes tasks
                                v
                    ┌───────────────────────┐
                    │ Worker Certification  │
                    │      System           │
                    └───────┬───────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          v                 v                 v
    ┌──────────┐    ┌─────────────┐   ┌────────────┐
    │Security  │    │ Development │   │   CI/CD    │
    │ Master   │    │   Master    │   │  Master    │
    └──────────┘    └─────────────┘   └────────────┘
          │                 │                 │
          │                 │                 │
          └────────┬────────┴────────┬────────┘
                   │                 │
                   v                 v
           ┌──────────────┐   ┌──────────────┐
           │  Dashboard   │   │  Governance  │
           │  (displays   │   │  (policies)  │
           │   permits)   │   │              │
           └──────────────┘   └──────────────┘
```

## Example: Production Deployment Flow

```
Developer requests production deployment
    │
    v
┌─────────────────────────────────────────┐
│ 1. Development Master receives task     │
│    Task: "Deploy API v2.1 to prod"      │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 2. Certification Checker analyzes       │
│    • Environment: production (10 risk)  │
│    • Data: customer (7 risk)            │
│    • Operation: deployment (5 risk)     │
│    • Impact: customer-facing (10 risk)  │
│    → Total Risk Score: 32               │
│    → Decision: Level 3 Union required   │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 3. Permit System creates request        │
│    • 2 approvers required               │
│    • Roles: Director + Security Lead    │
│    • Notifies approvers                 │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 4. Approver 1 reviews (6 hours later)   │
│    Engineering Director → ✓ APPROVED    │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 5. Approver 2 reviews (4 hours later)   │
│    Security Lead → ✓ APPROVED           │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 6. Permit issued with constraints       │
│    • Time window: 8pm-9pm               │
│    • Auto-rollback enabled              │
│    • Max error rate: 1%                 │
│    • Monitoring: real-time              │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 7. Worker spawned (Level 3 certified)   │
│    • Worker validates permit            │
│    • Checks time window                 │
│    • Begins execution at 8pm            │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 8. Deployment executes with monitoring  │
│    • Real-time metrics tracked          │
│    • Error rate: 0.1% ✓                 │
│    • Latency: normal ✓                  │
│    • Completes at 8:35pm ✓              │
└────────────┬────────────────────────────┘
             │
             v
┌─────────────────────────────────────────┐
│ 9. Permit closed with audit summary     │
│    • Success logged                     │
│    • Stakeholders notified              │
│    • Audit trail complete               │
│    • Compliance verified                │
└─────────────────────────────────────────┘

Total time: ~10 hours (approval) + 35 min (execution)
```

## Security Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                              │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ Layer 7: Compliance & Governance                                   │
│ • Policy enforcement • Regulatory compliance • External audit      │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────┴──────────────────────────────────────────┐
│ Layer 6: Audit & Monitoring                                        │
│ • Comprehensive logging • Real-time monitoring • Tamper-proof trail│
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────┴──────────────────────────────────────────┐
│ Layer 5: Permit Validation                                         │
│ • Active permit check • Scope validation • Time window enforcement │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────┴──────────────────────────────────────────┐
│ Layer 4: Approval Workflow                                         │
│ • Multi-approver • Role-based • Time-limited authorization         │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────┴──────────────────────────────────────────┐
│ Layer 3: Certification Verification                                │
│ • Level check • Recertification status • Incident history          │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────┴──────────────────────────────────────────┐
│ Layer 2: Risk Assessment                                           │
│ • Environment detection • Data sensitivity • Operation risk        │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────┴──────────────────────────────────────────┐
│ Layer 1: Environment Isolation                                     │
│ • Network segmentation • Data access controls • Resource limits    │
└────────────────────────────────────────────────────────────────────┘
```

## Conclusion

This certification system provides:
- **Safety through layers**: Multiple enforcement points prevent mistakes
- **Flexibility where safe**: Fast path for development
- **Rigor where needed**: Strict controls for production
- **Full auditability**: Comprehensive logging for compliance
- **Clear escalation**: Well-defined approval workflows

The architecture ensures that the right level of oversight is applied to each operation, balancing safety and velocity.
