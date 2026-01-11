# Sentinel Forge Repository Analysis

**Analysis Date**: 2025-12-13
**Analyzed By**: Inventory Master (Cortex)
**Repository**: https://github.com/ry-ops/sentinel-forge
**Status**: Initial Development Complete - Pre-deployment

---

## Executive Summary

Sentinel Forge is a sophisticated Red vs Blue Team security testing environment that provides automated attack/defense exercises on Proxmox infrastructure. The system uniquely differentiates between authorized Red Team activities and real unauthorized threats, making it both a training platform and a threat detection system.

**Strategic Value**: HIGH - Critical security capability with direct integration opportunities with Cortex security infrastructure.

**Deployment Status**: Infrastructure-as-code complete, awaiting deployment prerequisites (Sandfly, n8n, Proxmox templates).

---

## Repository Overview

### Basic Information
- **Created**: 2025-12-09 (Recent)
- **Last Commit**: 2025-12-09
- **Visibility**: Private
- **License**: MIT
- **Primary Language**: Not detected (Infrastructure/Config heavy)
- **Files**: 11 core files
- **Lines of Code**: ~4,000+ (Terraform, n8n workflows, Sandfly rules, documentation)

### Repository Structure
```
sentinel-forge/
├── terraform/
│   ├── main.tf              # 15+ VM definitions, network config
│   └── variables.tf         # Exercise parameters, team configs
├── n8n-workflows/
│   ├── 01-exercise-orchestrator.json  # Main control workflow
│   └── 02-red-team-automation.json    # Attack automation
├── sandfly/
│   └── rules/
│       └── security-lab-rules.xml     # 100+ custom detection rules
├── README.md                # Quick start guide
├── DEPLOYMENT-GUIDE.md      # 11-phase deployment process
├── ARCHITECTURE.md          # Detailed technical architecture
├── PROJECT-STATUS.md        # Current status and roadmap
├── SUMMARY.md              # Executive overview
├── CONTRIBUTING.md         # Contribution guidelines
└── .github/
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

---

## Purpose & Capabilities

### Primary Functions

1. **Automated Red Team Operations**
   - Multi-phase attack chains (recon → exploit → post-exploit)
   - Automated scenarios via n8n workflows
   - Attack tools: Kali Linux, Metasploit, Nuclei, Nmap, Burp Suite
   - C2 infrastructure (Covenant, Sliver)
   - Phishing simulation (GoPhish)

2. **Blue Team Defense & Detection**
   - Real-time detection via Sandfly SIEM
   - Automated incident response workflows
   - SOC analyst workstation
   - Threat intelligence (MISP)
   - Network monitoring (Zeek, Suricata)
   - Forensics capabilities (Volatility, Autopsy)

3. **Purple Team Coordination**
   - Controlled exercise management
   - Real-time scoring system
   - Post-exercise analysis
   - Team deconfliction
   - Continuous improvement feedback

4. **Unauthorized Threat Detection (Unique Feature)**
   - Differentiates Red Team (10.0.10.0/24) from real threats
   - Any non-Red Team attack triggers CRITICAL alerts
   - Honeypot network (10.0.50.0/24) for deception
   - Automated IP blocking and incident response
   - Dual-purpose: Training + Real Security

---

## Technical Architecture

### Infrastructure Layer

**Proxmox Environment**:
- 15+ VM deployment via Terraform/OpenTofu
- 5 VLAN network segmentation:
  - VLAN 1: Management (10.0.0.0/24)
  - VLAN 10: Red Team (10.0.10.0/24)
  - VLAN 20: Blue Team (10.0.20.0/24)
  - VLAN 30: Targets (10.0.30.0/24)
  - VLAN 40: Purple Control (10.0.40.0/24)
  - VLAN 50: Honeypots (10.0.50.0/24)

**Virtual Machines**:
- Red Team: Kali (CT110), Parrot (CT111), C2 Server (CT112), Phishing (CT113)
- Blue Team: SOC (CT121), MISP (CT122), Network Monitor (CT123), Forensics (CT124)
- Targets: Web (CT130), Windows AD (CT131), Docker (CT132), Database (CT133)
- Honeypots: SSH (CT150), Web (CT151), Database (CT152), SMB (CT153)
- Control: Purple Dashboard (CT140)

### Orchestration Layer

**n8n Workflows**:
1. **Exercise Orchestrator** (01-exercise-orchestrator.json)
   - Webhook trigger: `/start-exercise`
   - VM verification via Proxmox API
   - Sandfly rule activation
   - Team coordination
   - 5-minute monitoring loop
   - Unauthorized threat detection
   - Alert routing (Slack, Email)
   - Real-time scoring

2. **Red Team Automation** (02-red-team-automation.json)
   - 15-minute scheduled attacks
   - 6-phase attack chains
   - Detection checking
   - Result logging
   - Team notifications

### Detection Layer

**Sandfly Custom Rules** (100+ rules):
- 100001-100009: Red Team activity (authorized, level 5-8)
- 100010-100014: Unauthorized attacks (CRITICAL, level 12-14)
- 100020-100027: Honeypot interactions (level 10)
- 100050-100051: Blue Team operations
- 100060-100065: Target compromise indicators
- 100100-100103: Exercise control markers

**Detection Logic**:
```
IF source_ip == 10.0.10.0/24:
  → Tag as "Red Team" (authorized)
  → Alert Blue Team for scoring
  → Level 5-8 alerts
ELSE:
  → Tag as "Black Hat" (unauthorized)
  → CRITICAL alert (level 12-14)
  → Auto-block IP
  → Immediate SOC notification
  → Trigger IR playbook
```

---

## Technology Stack

### Infrastructure & Orchestration
- **Hypervisor**: Proxmox VE 7.x/8.x
- **IaC**: Terraform/OpenTofu 1.6+
- **Workflow Engine**: n8n (self-hosted)
- **Networking**: Linux bridges, VLANs, iptables

### Security & Monitoring
- **SIEM**: Sandfly 4.x (existing deployment)
- **IDS/IPS**: Suricata
- **Network Analysis**: Zeek
- **Threat Intel**: MISP, ThreatFox, OpenCTI
- **Log Stack**: Elasticsearch, Kibana

### Offensive Tools
- **OS**: Kali Linux 2024.4, Parrot OS
- **Frameworks**: Metasploit, Empire, Covenant
- **Scanners**: Nmap, Masscan, Nuclei, Nikto, Burp Suite
- **Exploitation**: SQLMap, Impacket, CrackMapExec

### Defensive Tools
- **Forensics**: Volatility, Autopsy
- **IR**: TheHive (optional), Cortex SOAR (optional)
- **Honeypots**: Cowrie (SSH), Snare/Tanner (Web), Elasticpot (DB)

### Target Applications
- **Web**: DVWA, WebGoat, OWASP Juice Shop
- **Infrastructure**: Windows Server 2022 AD, Docker
- **Databases**: MySQL, PostgreSQL

---

## Strategic Value Assessment

### Critical Strengths

1. **Unique Threat Detection Capability**
   - Dual-purpose system: Training + Real Security
   - Automatic differentiation of authorized vs unauthorized attacks
   - Honeypot network for advanced threat detection
   - **Market Differentiator**: No comparable open-source solution

2. **Full Automation**
   - Complete exercise lifecycle automation
   - n8n workflow orchestration
   - Infrastructure-as-Code deployment
   - Minimal manual intervention required

3. **Existing Infrastructure Integration**
   - Leverages existing Sandfly SIEM (no new SIEM needed)
   - Proxmox integration (existing hypervisor)
   - Zero additional licensing costs
   - Integrates with Cortex (optional enhancement)

4. **Production-Ready Design**
   - Comprehensive documentation (5 guides)
   - 11-phase deployment process
   - Network segmentation and isolation
   - Backup and disaster recovery procedures
   - Security-first architecture

5. **Scalability**
   - Modular VM design (add/remove as needed)
   - Configurable exercise types via variables
   - Horizontal and vertical scaling options
   - Template-based VM provisioning

### Current Limitations

1. **Deployment Prerequisites**
   - Requires manual VM template creation
   - Sandfly rules need manual installation
   - n8n workflows require manual import
   - Not fully automated end-to-end (by design for security)

2. **Resource Requirements**
   - 15+ VMs (60-100GB RAM total)
   - ~1TB storage for all VMs
   - Dedicated Proxmox capacity needed

3. **Initial Setup Complexity**
   - 11-phase deployment process
   - Multiple technology stack components
   - Network configuration expertise needed
   - Estimated 1-2 days initial setup

4. **Missing Components**
   - Purple Team control dashboard (planned, not implemented)
   - Blue Team automated response workflow (planned)
   - Purple Team scoring workflow (planned)
   - Additional attack scenarios (container escape, AD attacks, etc.)

---

## Integration Opportunities with Cortex

### Priority 1: Security Master Integration

**Capability**: Automated security testing and validation

**Integration Points**:
1. **Scheduled Security Exercises**
   - Cortex Security Master triggers Sentinel Forge exercises
   - Weekly/monthly automated Red Team testing
   - Results fed back to Security Master for analysis

2. **Threat Detection Enhancement**
   - Sentinel Forge honeypots → Cortex Security Master alerts
   - Unauthorized attack detection → Immediate Cortex notification
   - Integration with Cortex incident response workflows

3. **Security Metrics Pipeline**
   - MTTD (Mean Time to Detect) tracking
   - MTTR (Mean Time to Respond) monitoring
   - Detection coverage reporting
   - Feed metrics to Cortex dashboard

**Implementation**:
```yaml
cortex_integration:
  security_master:
    - trigger_exercises: webhook → Sentinel Forge n8n
    - receive_alerts: Sandfly → Cortex Security Master
    - metrics_pipeline: Sentinel Forge → Cortex dashboard
    - incident_response: Unauthorized attack → Cortex IR workflow
```

### Priority 2: CI/CD Master Integration

**Capability**: Automated security testing in deployment pipeline

**Integration Points**:
1. **Pre-Deployment Security Testing**
   - Test new deployments in Sentinel Forge targets
   - Automated vulnerability scanning before production
   - Container security testing (Docker targets)

2. **Post-Deployment Validation**
   - Verify security controls after deployment
   - Test detection rules against new infrastructure
   - Validate incident response procedures

**Implementation**:
```yaml
cortex_integration:
  cicd_master:
    - pre_deploy_test: Deploy to Sentinel Forge targets first
    - security_scan: Automated Red Team against staging
    - post_deploy_verify: Confirm detection capabilities
```

### Priority 3: Development Master Integration

**Capability**: Security-enhanced development lifecycle

**Integration Points**:
1. **Secure Code Testing**
   - Deploy development builds to Sentinel Forge
   - Test against OWASP Top 10 attacks
   - Validate security controls implementation

2. **Security Training for Developers**
   - Demonstrate attack vectors
   - Show real-time detection
   - Security awareness through practice

**Implementation**:
```yaml
cortex_integration:
  development_master:
    - code_security_test: Dev builds → Sentinel Forge web targets
    - attack_demonstration: Educational Red Team exercises
    - security_feedback: Vulnerabilities → Dev Master for remediation
```

### Priority 4: Inventory Master Integration

**Capability**: Asset security posture tracking

**Integration Points**:
1. **Repository Security Scanning**
   - Deploy portfolio projects to Sentinel Forge
   - Automated security testing of all repositories
   - Track security posture over time

2. **Security Health Metrics**
   - Add security scores to repository inventory
   - Track MTTD/MTTR per project
   - Identify high-risk repositories

**Implementation**:
```yaml
cortex_integration:
  inventory_master:
    - security_posture: Track per-repo security metrics
    - automated_testing: Schedule tests for all portfolio projects
    - risk_assessment: Flag high-risk repositories
```

### Priority 5: AI-Powered Analysis (Future)

**Capability**: LLM-enhanced security analysis

**Integration Points**:
1. **Attack Pattern Recognition**
   - Claude analyzes exercise results
   - Identify trends across exercises
   - Suggest detection rule improvements

2. **Automated Playbook Generation**
   - Generate IR playbooks from exercise outcomes
   - Create detection rules based on attack patterns
   - Natural language reporting for executives

3. **Executive Reporting**
   - Claude generates natural language summaries
   - Translate technical findings to business impact
   - Automated monthly security posture reports

**Implementation**:
```yaml
cortex_integration:
  ai_analysis:
    - pattern_recognition: Claude analyzes exercise logs
    - playbook_generation: Auto-create IR procedures
    - executive_reporting: Natural language summaries
```

---

## Cortex Security Master Synergies

### Current Cortex Security Capabilities

From the Cortex ecosystem, we have:
- **Security Master**: Security monitoring and compliance
- **n8n-mcp-server**: Already integrated with Cortex
- **proxmox-mcp-server**: Already integrated with Cortex
- **Dependency-Track**: Container security scanning
- **Sandfly**: Already deployed SIEM

### Sentinel Forge Enhancements

Sentinel Forge adds:
1. **Active Security Testing** (vs. passive monitoring)
2. **Red Team Capabilities** (vs. detection-only)
3. **Purple Team Coordination** (vs. siloed teams)
4. **Unauthorized Threat Detection** (vs. assumed authorized)
5. **Honeypot Network** (vs. production-only monitoring)

### Combined Capabilities Matrix

| Capability | Cortex Security | Sentinel Forge | Combined |
|------------|----------------|----------------|----------|
| Vulnerability Scanning | Dependency-Track | Red Team Attacks | Comprehensive |
| Threat Detection | Sandfly Alerts | Sandfly + Honeypots | Enhanced |
| Incident Response | Manual | Automated n8n | Fully Automated |
| Security Testing | Manual | Automated Exercises | Continuous |
| Attack Simulation | None | Full Red Team | Complete |
| Deception Tech | None | Honeypots | Advanced |
| Metrics | Basic | MTTD/MTTR/Coverage | Production-Grade |

---

## Strategic Recommendations

### Recommendation 1: DEPLOY (High Priority)

**Rationale**:
- Unique security capability not available elsewhere in portfolio
- Direct integration with existing Cortex infrastructure
- Zero additional licensing costs
- High strategic value for security posture improvement

**Timeline**:
- Phase 1 (Core Deployment): 2-3 days
- Phase 2 (Honeypots): 1 day
- Phase 3 (Cortex Integration): 2 days
- Total: ~1 week for full deployment

**Resource Requirements**:
- Proxmox: 60-100GB RAM, 1TB storage
- Personnel: 1-2 days initial setup, 2-4 hours/month maintenance
- Cost: $0 (leverages existing infrastructure)

### Recommendation 2: INTEGRATE with Cortex Security Master

**Rationale**:
- Seamless integration with existing Cortex architecture
- Enhanced automated security capabilities
- Metrics pipeline to Cortex dashboard
- Unified security operations

**Integration Plan**:
1. Security Master → Sentinel Forge webhook triggers
2. Sentinel Forge → Security Master alert pipeline
3. Sandfly → Cortex dashboard metrics export
4. Unauthorized threats → Cortex IR workflows

**Timeline**: 2 days post-deployment

### Recommendation 3: EXPAND with AI Analysis (Future)

**Rationale**:
- Leverage Cortex AI capabilities for security analysis
- Automated pattern recognition and learning
- Executive-friendly reporting
- Continuous improvement automation

**Future Enhancement Plan**:
1. Claude analyzes exercise logs
2. Automated playbook generation
3. Natural language reporting
4. Trend analysis across exercises

**Timeline**: Phase 2 enhancement (Q1 2026)

### Recommendation 4: DOCUMENT as Cortex Security Lab

**Rationale**:
- Market differentiator for Cortex
- Demonstrates advanced security capabilities
- Training and certification opportunity
- Community contribution potential

**Documentation Plan**:
1. Add to Cortex documentation as "Security Lab Module"
2. Create integration guides
3. Video walkthroughs
4. Case studies and metrics

**Timeline**: Ongoing post-deployment

---

## Deployment Priority

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create Proxmox VM templates
- [ ] Configure VLANs
- [ ] Deploy Terraform infrastructure
- [ ] Install Sandfly custom rules
- [ ] Import n8n workflows
- [ ] Test basic Red Team attack
- [ ] Verify Blue Team detection

### Phase 2: Cortex Integration (Week 2)
- [ ] Configure Security Master webhooks
- [ ] Set up metrics pipeline to dashboard
- [ ] Integrate unauthorized threat alerts
- [ ] Test end-to-end Cortex → Sentinel Forge → Cortex
- [ ] Deploy honeypots
- [ ] Configure automated responses

### Phase 3: Operational Testing (Week 3)
- [ ] Run full-spectrum exercise
- [ ] Validate all attack scenarios
- [ ] Test unauthorized threat detection
- [ ] Verify automated blocking
- [ ] Performance tuning
- [ ] Documentation updates

### Phase 4: Production Readiness (Week 4)
- [ ] Scheduled exercise automation
- [ ] Metrics dashboard updates
- [ ] Executive reporting
- [ ] Team training
- [ ] Disaster recovery testing
- [ ] Go-live

---

## Risk Assessment

### Technical Risks

1. **Resource Contention** (Medium)
   - Mitigation: Dedicated Proxmox capacity allocation
   - Impact: Performance degradation if under-resourced

2. **Network Isolation Breach** (Low)
   - Mitigation: Multiple isolation layers (VLANs, firewall, monitoring)
   - Impact: Potential escape to production network

3. **False Positive Overload** (Medium)
   - Mitigation: Tuning Sandfly rules during testing phase
   - Impact: Alert fatigue, missed real threats

### Operational Risks

1. **Complexity** (Medium)
   - Mitigation: Comprehensive documentation, phased deployment
   - Impact: Extended deployment timeline

2. **Maintenance Overhead** (Low)
   - Mitigation: Automated updates, template management
   - Impact: 2-4 hours/month maintenance required

3. **Skill Requirements** (Medium)
   - Mitigation: Training, documentation, gradual rollout
   - Impact: Learning curve for team

### Security Risks

1. **Vulnerable Systems Escape** (Low)
   - Mitigation: Network isolation, monitoring, firewall rules
   - Impact: Intentionally vulnerable systems could be exploited

2. **Unauthorized Access** (Low)
   - Mitigation: SSH key-based auth, Sandfly monitoring, audit logging
   - Impact: Unauthorized use of Red Team tools

---

## Success Metrics

### Deployment Success Criteria

- [ ] All 15+ VMs deployed and operational
- [ ] Network segmentation verified
- [ ] Sandfly rules active and triggering
- [ ] n8n workflows executing successfully
- [ ] First exercise completed end-to-end
- [ ] Blue Team detection confirmed
- [ ] Unauthorized threat detection validated

### Operational Metrics (Ongoing)

**Blue Team Performance**:
- MTTD (Mean Time to Detect): Target < 5 minutes
- MTTR (Mean Time to Respond): Target < 15 minutes
- False Positive Rate: Target < 5%
- Coverage: % of MITRE ATT&CK techniques tested

**Red Team Performance**:
- Success Rate: Should decrease over time (Blue Team improving)
- Stealth Score: Undetected attack percentage
- Objectives Achieved: % of attack phases completed

**System Health**:
- VM Uptime: Target > 99%
- Sandfly Agent Status: Target 100% agents active
- n8n Workflow Success Rate: Target > 95%

---

## Financial Analysis

### Initial Investment
- **Hardware**: $0 (uses existing Proxmox)
- **Software**: $0 (all open-source)
- **Personnel**: ~16 hours @ $150/hr = $2,400
- **Total Initial**: $2,400

### Ongoing Costs
- **Maintenance**: 4 hours/month @ $150/hr = $600/month = $7,200/year
- **Infrastructure**: $0 (existing)
- **Software**: $0 (open-source)
- **Total Annual**: $7,200

### Cost Avoidance
- **External Pentesting**: $15,000-50,000/year (replaced by Red Team)
- **Security Training**: $5,000-10,000/year (hands-on learning)
- **Incident Response Drills**: $5,000/year (automated)
- **Total Avoidance**: $25,000-65,000/year

### ROI Calculation
- **Year 1 Net**: $25,000 - $9,600 = $15,400 savings
- **ROI**: 161% first year
- **Payback Period**: < 2 months

---

## Conclusion

Sentinel Forge represents a **strategic security capability** that perfectly complements the Cortex automation ecosystem. Its unique ability to differentiate authorized testing from real threats, combined with full automation and existing infrastructure integration, makes it a high-value, low-cost addition to the security portfolio.

**Recommendation**: DEPLOY with HIGH PRIORITY and integrate with Cortex Security Master.

**Next Steps**:
1. Approve deployment
2. Allocate Proxmox resources
3. Create VM templates
4. Execute Phase 1 deployment
5. Integrate with Cortex
6. Begin scheduled security exercises

---

**Analysis Prepared By**: Inventory Master (Cortex)
**Date**: 2025-12-13
**Document Version**: 1.0
**Classification**: Internal Use - Strategic Planning
