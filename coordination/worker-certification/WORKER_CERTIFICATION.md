# Worker Certification System

## Overview

The Cortex Worker Certification System distinguishes between **Union Workers** (certified, audited, production-grade) and **Non-Union Workers** (fast, flexible, dev/test) to ensure operational safety while maintaining development velocity.

## Union vs Non-Union Workers

### Union Workers (Certified)

**Definition**: Certified workers that have passed rigorous testing, auditing, and approval processes. Required for production operations, critical systems, and regulated environments.

**Characteristics**:
- Formally certified and audited
- Production-grade quality standards
- Full audit trail required
- Approval gates enforced
- Slower but safer operations
- Higher token allocation
- Must follow strict protocols
- Subject to governance oversight

**When to Use**:
- Production deployments
- Critical infrastructure changes
- Security-sensitive operations
- Financial or regulated systems
- Data with PII/PHI/financial info
- Changes affecting customers
- Compliance-required operations
- High-risk refactoring

**Certification Requirements**:
1. Pass comprehensive test suite (95%+ coverage)
2. Security audit completed
3. Code review by senior engineers
4. Performance benchmarks met
5. Documentation complete
6. Approval from authorized personnel
7. Rollback procedures validated
8. Incident response plan documented

### Non-Union Workers (Flexible)

**Definition**: Fast, flexible workers for development, testing, and low-risk operations. Optimized for velocity and experimentation without heavy oversight.

**Characteristics**:
- Minimal certification barriers
- Development/test focused
- Lighter audit requirements
- Faster approval (or auto-approved)
- Optimized for speed
- Lower token allocation
- Flexible protocols
- Self-service capable

**When to Use**:
- Development environments
- Testing and QA
- Non-critical features
- Internal tools
- Documentation updates
- Code exploration
- Proof of concepts
- Local experimentation

**Guidelines**:
1. No production access
2. Isolated environments only
3. No customer data access
4. Basic testing required
5. Self-documenting preferred
6. Fast-fail acceptable
7. Limited scope operations

## Certification Levels

### Level 0: Uncertified (Non-Union Default)
- Dev/test only
- No production access
- Auto-approved for safe operations
- Minimal oversight

### Level 1: Basic Certification
- Read-only production access
- Monitoring and observability
- Non-destructive operations
- Basic approval required

### Level 2: Standard Certification (Union)
- Production deployments
- Configuration changes
- Standard operations
- Manager approval required

### Level 3: Advanced Certification (Union)
- Critical infrastructure
- Security operations
- Database migrations
- Senior leadership approval

### Level 4: Master Certification (Union)
- System architecture changes
- Multi-region deployments
- Compliance operations
- Executive approval required

## Approval Workflows

### Fast Path (Non-Union)
```
Task → Auto-Analysis → Risk Check → Execute
         (< 5 seconds)
```

**Conditions**:
- Environment: dev/test/local
- Risk Level: low
- Data Sensitivity: none/public
- Impact Scope: single service/limited
- Reversibility: fully reversible

### Standard Path (Union - Level 2)
```
Task → Analysis → Permit Request → Manager Review → Approval → Execute
        (5-30 minutes)
```

**Conditions**:
- Environment: staging/production
- Risk Level: medium
- Data Sensitivity: internal
- Impact Scope: service-wide
- Reversibility: automated rollback available

### Critical Path (Union - Level 3/4)
```
Task → Deep Analysis → Security Review → Architecture Review →
Senior Leadership Approval → Permit Issuance → Scheduled Execution
(hours to days)
```

**Conditions**:
- Environment: production (critical)
- Risk Level: high
- Data Sensitivity: PII/PHI/financial
- Impact Scope: system-wide/customer-facing
- Reversibility: complex rollback procedures

## Safety Rules

### Hard Blocks (Never Override)

1. **No Uncertified Production Access**: Workers without Level 2+ certification cannot touch production
2. **No PII Without Level 3+**: Personal data requires advanced certification
3. **No Cross-Environment Promotion**: Cannot auto-promote dev workers to production
4. **No Approval Bypass**: Required approvals cannot be skipped
5. **No Audit Trail Gaps**: All production operations must be fully logged

### Soft Blocks (Override with Justification)

1. **Extended Token Usage**: Can request budget increase with business justification
2. **Expedited Approval**: Can fast-track with executive sponsor
3. **Testing Waivers**: Can reduce test coverage for hotfixes (with documentation)
4. **Parallel Operations**: Can run multiple operations with coordination plan

## Certification Process

### For New Workers (Union Path)

1. **Development Phase**
   - Build worker in non-union mode
   - Test in isolated dev environment
   - Document capabilities and limitations

2. **Testing Phase**
   - Comprehensive test suite (95%+ coverage)
   - Integration testing
   - Performance benchmarking
   - Failure mode analysis

3. **Security Review**
   - Code security audit
   - Dependency scanning
   - Vulnerability assessment
   - Access control validation

4. **Documentation Phase**
   - Complete operational runbook
   - Incident response procedures
   - Rollback documentation
   - Training materials

5. **Approval Phase**
   - Present to certification board
   - Demonstrate capabilities
   - Address concerns
   - Receive certification level

6. **Monitoring Phase**
   - Probationary period (30 days)
   - Enhanced monitoring
   - Performance review
   - Final certification or remediation

### For Existing Workers (Recertification)

- **Annual Recertification**: All Level 2+ workers
- **Quarterly Reviews**: Level 3+ workers
- **Post-Incident Review**: After any major incident
- **Capability Changes**: When worker is modified

## Audit Requirements

### Union Workers (Level 2+)

**Required Logs**:
- All operations with timestamps
- Input parameters and outputs
- Approvals and approvers
- Error conditions and recoveries
- Performance metrics
- Security events

**Retention**:
- Operational logs: 90 days minimum
- Audit logs: 1 year minimum
- Compliance logs: 7 years minimum

**Access**:
- Real-time monitoring dashboard
- Queryable audit database
- Automated alerting
- Compliance reporting

### Non-Union Workers

**Required Logs**:
- Basic operation summary
- Error conditions
- Resource usage

**Retention**:
- 30 days minimum
- Local storage acceptable

**Access**:
- Developer access only
- No compliance requirements

## Emergency Procedures

### Emergency Certification (Temporary Union Status)

**Trigger Conditions**:
- Production incident requiring immediate action
- Security breach requiring rapid response
- System outage affecting customers

**Process**:
1. Incident commander declares emergency
2. Temporary Level 3 certification granted (1 hour max)
3. Enhanced monitoring activated
4. Post-incident review mandatory
5. Certification revoked after emergency

**Requirements**:
- Incident ticket created
- Real-time oversight (screen share)
- Detailed post-action report
- Lessons learned documentation

## Metrics and Monitoring

### Union Worker Metrics
- Certification pass rate
- Time to certification
- Incident rate by certification level
- Approval time (by level)
- Compliance adherence score
- Audit finding severity

### Non-Union Worker Metrics
- Promotion rate to union status
- Fast-path usage
- Environment boundary violations
- Resource efficiency
- Development velocity impact

## Best Practices

### For Masters (Worker Managers)

1. **Default to Non-Union**: Start workers in non-union mode, promote as needed
2. **Right-Size Certification**: Don't over-certify (adds overhead)
3. **Plan Ahead**: Request union workers early (approval takes time)
4. **Document Everything**: Clear justification for union worker requests
5. **Monitor Closely**: Higher certification = higher scrutiny

### For Workers

1. **Know Your Limits**: Understand your certification level
2. **Request Appropriately**: Ask for permits before restricted operations
3. **Document Actions**: Comprehensive logging for union operations
4. **Fail Safely**: Always have rollback procedures ready
5. **Communicate Status**: Report progress and blockers

### For Operators

1. **Verify Certification**: Check worker credentials before approving
2. **Review Permits**: Understand what's being authorized
3. **Monitor Operations**: Watch union workers during execution
4. **Enforce Boundaries**: Block unauthorized operations immediately
5. **Audit Regularly**: Review logs and compliance

## Integration with Cortex

### Task Routing
```javascript
// Certification checker evaluates incoming tasks
if (task.environment === 'production' || task.critical) {
  requireUnionWorker(task, minLevel: 2);
} else if (task.risk_level === 'high') {
  requireUnionWorker(task, minLevel: 3);
} else {
  allowNonUnionWorker(task);
}
```

### Master Assignment
- Masters receive certification-aware task assignments
- Cannot spawn workers above their authorization level
- Must request permits for union worker operations

### Dashboard Integration
- Real-time certification status display
- Permit approval interface
- Audit log viewer
- Compliance reporting

## Compliance and Governance

### Regulatory Mapping
- **SOC 2**: Level 2+ certification for all production operations
- **HIPAA**: Level 3+ for PHI access
- **PCI-DSS**: Level 3+ for payment processing
- **GDPR**: Level 3+ for EU personal data

### Governance Oversight
- Certification board reviews quarterly
- Policy updates reviewed annually
- Incident patterns trigger policy changes
- Metrics reviewed in governance meetings

## FAQ

**Q: Can I use non-union workers in staging?**
A: Yes, if staging doesn't contain production data or affect customers.

**Q: How long does union certification take?**
A: Level 2: 1-2 weeks, Level 3: 3-4 weeks, Level 4: 4-8 weeks

**Q: Can I expedite certification?**
A: Yes, with executive sponsorship and business justification.

**Q: What happens if a non-union worker tries production access?**
A: Hard block - operation denied, incident logged, notification sent.

**Q: Can certification be revoked?**
A: Yes - due to incidents, policy violations, or failed recertification.

**Q: Do all workers need certification?**
A: No - only workers that need production access or handle sensitive data.

## Conclusion

The Union/Non-Union system balances safety and velocity:
- **Union workers** provide production safety and compliance
- **Non-union workers** enable rapid development and experimentation
- **Clear boundaries** prevent dangerous operations
- **Audit trails** ensure accountability
- **Approval workflows** enforce governance

Choose the right worker type for your task. When in doubt, start non-union and promote as needed.
