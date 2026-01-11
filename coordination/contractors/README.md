# Cortex Contractors

Contractors are specialized agents with deep domain expertise in specific tools, platforms, or technologies. Unlike masters (which orchestrate) and workers (which execute), contractors bring expert knowledge about HOW to use external systems effectively.

## Purpose

Contractors serve as domain experts that:
- Understand best practices for specific platforms
- Know common patterns and anti-patterns
- Have access to specialized MCP servers
- Can design and implement complex integrations
- Maintain knowledge bases of successful approaches

## Available Contractors

### infrastructure-contractor

**Specialization**: Infrastructure provisioning and management expert

**Knowledge Domains**:
- VM provisioning and lifecycle management
- Network segmentation and VLAN design
- Firewall rules and security policies
- DNS configuration and management
- Cloudflare CDN and edge services
- Multi-MCP orchestration patterns
- Backup strategies and disaster recovery

**MCP Servers**:
- proxmox-mcp-server (virtualization)
- unifi-mcp-server (networking)
- cloudflare-mcp-server (DNS/edge)

**Files**:
- `/Users/ryandahlberg/Projects/cortex/coordination/contractors/infrastructure-contractor.md` - Agent definition and expertise
- `/Users/ryandahlberg/Projects/cortex/coordination/contractors/infrastructure-contractor-knowledge.json` - Knowledge base with VM templates, network patterns, firewall rules

**Use Cases**:
- Provision complete infrastructure stacks (VM → Network → DNS)
- Configure isolated network environments
- Implement security zones and firewall policies
- Set up Cloudflare tunnels and SSL
- Design high-availability architectures
- Implement backup and disaster recovery strategies

### talos-contractor

**Specialization**: Talos Linux and Kubernetes cluster management expert

**Knowledge Domains**:
- Talos Linux cluster provisioning and management
- Kubernetes cluster operations
- Node lifecycle management
- etcd cluster management
- System upgrades and maintenance
- Cluster security and hardening

**MCP Server**: talos-mcp-server

**Files**:
- `/Users/ryandahlberg/Projects/cortex/coordination/contractors/talos-contractor.md` - Agent definition and expertise
- `/Users/ryandahlberg/Projects/cortex/coordination/contractors/talos-contractor-knowledge.json` - Knowledge base with cluster patterns and configurations

**Use Cases**:
- Provision and bootstrap Talos clusters
- Manage Kubernetes node lifecycle
- Implement cluster upgrades and maintenance
- Troubleshoot cluster issues
- Configure etcd for high availability

## Contractor vs Master vs Worker

| Aspect | Master | Worker | Contractor |
|--------|--------|--------|------------|
| **Role** | Orchestration | Execution | Expert consultation |
| **Scope** | Domain (dev, security, etc) | Task-specific | Tool/platform-specific |
| **Knowledge** | Coordination patterns | Implementation skills | Deep domain expertise |
| **Lifecycle** | Long-running | Short-lived (task duration) | On-demand |
| **Examples** | Development Master, Security Master | feature-implementer, bug-fixer | infrastructure-contractor, talos-contractor |

## How Contractors Work

### 1. Request Pattern

```json
{
  "request_type": "contractor_consultation",
  "contractor": "infrastructure-contractor",
  "task": "Design isolated network environment",
  "requirements": {
    "vlan": "145",
    "services": ["k3s cluster", "monitoring", "storage"],
    "security": "firewall rules for external access"
  }
}
```

### 2. Contractor Response

The contractor provides:
- Infrastructure architecture design
- Recommended configurations and security policies
- Network topology and VLAN design
- Code snippets and examples
- Implementation using MCP server tools

### 3. Integration with Masters

Contractors are typically requested by:
- **Development Master**: For implementing integrations
- **CI/CD Master**: For deployment automation workflows
- **Security Master**: For security-aware integrations
- **Inventory Master**: For documentation automation

### 4. Knowledge Base Updates

Contractors maintain knowledge bases that:
- Record successful patterns
- Document failures and solutions
- Store reusable code snippets
- Track performance optimizations

## Adding New Contractors

To create a new contractor:

1. **Create contractor markdown file**: `{name}-contractor.md`
   - Agent identity and purpose
   - Domain knowledge areas
   - Tool/platform expertise
   - Example prompts and responses
   - Integration patterns

2. **Create knowledge base**: `{name}-contractor-knowledge.json`
   - Pattern library
   - Best practices
   - Code snippets
   - Common mistakes
   - Learning outcomes

3. **Register with coordinator**: Update contractor registry
   ```json
   {
     "contractor_id": "terraform-contractor",
     "specialization": "Infrastructure as Code",
     "mcp_server": "terraform-mcp-server",
     "expertise": ["AWS", "GCP", "Azure", "Kubernetes"]
   }
   ```

4. **Update handoff patterns**: Define how masters request contractor help

## Example Contractors (Future)

- **kubernetes-contractor**: K8s deployment and operations expert (beyond Talos)
- **database-contractor**: Database design and optimization expert
- **api-contractor**: API design and implementation expert
- **security-contractor**: Security architecture and implementation expert
- **microsoft-contractor**: Microsoft 365 and Azure AD expert (uses microsoft-graph-mcp)
- **cortex-resource-contractor**: Kubernetes resource management and burst worker provisioning expert

## Best Practices

### For Contractors

1. **Maintain Deep Knowledge**: Stay updated on platform best practices
2. **Document Patterns**: Record successful and failed approaches
3. **Provide Context**: Explain WHY not just WHAT
4. **Include Examples**: Working code snippets and configurations
5. **Consider Trade-offs**: Discuss pros/cons of different approaches

### For Masters Using Contractors

1. **Clear Requirements**: Provide detailed context and constraints
2. **Accept Recommendations**: Contractors are domain experts
3. **Record Outcomes**: Feed back results to contractor knowledge base
4. **Escalate Edge Cases**: Help contractors improve their knowledge
5. **Validate Implementations**: Test contractor-designed solutions

## Metrics and Evaluation

Track contractor effectiveness:
- **Success Rate**: Implemented designs that work
- **Pattern Reuse**: How often patterns are reused
- **Knowledge Growth**: Knowledge base expansion
- **Master Satisfaction**: Masters' assessment of contractor help
- **Time Savings**: Faster implementation with contractor expertise

## Directory Structure

```
coordination/contractors/
├── README.md                                    # This file
├── infrastructure-contractor.md                 # Infrastructure expert agent
├── infrastructure-contractor-knowledge.json     # Infrastructure knowledge base
├── talos-contractor.md                          # Talos/K8s expert agent
├── talos-contractor-knowledge.json              # Talos knowledge base
└── [future contractors...]
```

## Contributing

When adding contractor knowledge:
1. Document the pattern or approach
2. Include working code examples
3. Explain use cases and trade-offs
4. Add to appropriate section in knowledge base
5. Update version and timestamp

---

**Version**: 1.0.0
**Created**: 2025-12-09
**Maintained by**: Cortex Development Master
