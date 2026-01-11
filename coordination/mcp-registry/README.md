# MCP Server Registry

The unified registry for all Model Context Protocol (MCP) servers available to cortex for AI-powered infrastructure and operations management.

## Overview

This directory contains:
- **REGISTRY.md**: Human-readable catalog of all MCP servers with detailed documentation
- **servers.json**: Machine-readable registry for programmatic access and automation

## Quick Start

### For Humans

Read [REGISTRY.md](./REGISTRY.md) for:
- Complete server descriptions
- Configuration requirements
- Use cases and capabilities
- Integration patterns
- Setup instructions

### For Machines (Coordinator Agent)

Use [servers.json](./servers.json) for:
- Server discovery and enumeration
- Capability querying
- Configuration templating
- Automated integration

## Registry Contents

### Current Servers (7)

1. **n8n MCP Server** - Workflow automation (16 tools)
2. **Cortex Resource Manager** - Kubernetes resource management (16 tools)
3. **Talos MCP Server** - Talos Linux cluster management (12 tools)
4. **Proxmox MCP Server** - Virtualization management (15 tools)
5. **UniFi MCP Server** - Network infrastructure management (18 tools)
6. **Cloudflare MCP Server** - DNS and CDN management (13 tools)
7. **Microsoft Graph MCP Server** - Microsoft 365 management (10 tools)

**Total Tools:** 100+

## Usage Examples

### Query Available Servers

```bash
# List all server IDs
jq -r '.servers[].id' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json

# Get server by ID
jq '.servers[] | select(.id == "n8n-mcp-server")' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json

# Count total tools
jq '[.servers[].tool_count] | add' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json

# List servers by capability
jq '.servers[] | select(.capabilities[] | contains("monitoring"))' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json
```

### Filter by Tag

```bash
# Find all Kubernetes-related servers
jq '.servers[] | select(.tags[] | contains("kubernetes"))' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json

# Find all infrastructure servers
jq '.servers[] | select(.tags[] | contains("infrastructure"))' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json
```

### Get Configuration Requirements

```bash
# Get required env vars for a server
jq '.servers[] | select(.id == "cloudflare-mcp-server") | .configuration.env_vars[] | select(.required == true)' /Users/ryandahlberg/Projects/cortex/coordination/mcp-registry/servers.json
```

## Integration with Cortex

### Coordinator Agent Usage

The coordinator agent can use this registry to:

1. **Discover Available Tools**: Query which MCP servers provide needed capabilities
2. **Plan Integrations**: Determine which servers to use for specific tasks
3. **Validate Configuration**: Ensure required credentials are available
4. **Generate Handoffs**: Create appropriate handoffs to masters based on available tools

### Development Master Usage

The development master can use this registry to:

1. **Reference Capabilities**: Understand what infrastructure tools are available
2. **Plan Implementations**: Design features that leverage MCP server capabilities
3. **Document Integration**: Ensure new code properly integrates with MCP servers

### Security Master Usage

The security master can use this registry to:

1. **Audit Credentials**: Track which API tokens and secrets are required
2. **Review Permissions**: Understand what access each server needs
3. **Security Assessment**: Evaluate risk posture of integrated services

## Registry Schema

### servers.json Structure

```json
{
  "registry": {
    "name": "string",
    "version": "semver",
    "maintainer": "string",
    "github_org": "url",
    "last_updated": "iso8601",
    "total_servers": "number"
  },
  "servers": [
    {
      "id": "kebab-case-id",
      "name": "Display Name",
      "repository": "github-url",
      "status": "active|beta|deprecated|archived",
      "language": "python|typescript|go",
      "tool_count": "number",
      "description": "Brief description",
      "capabilities": ["array", "of", "capabilities"],
      "configuration": {
        "env_vars": [
          {
            "name": "ENV_VAR_NAME",
            "description": "What it does",
            "required": "boolean"
          }
        ]
      },
      "use_cases": ["array", "of", "use_cases"],
      "tags": ["array", "of", "tags"]
    }
  ]
}
```

## Maintenance

### Updating the Registry

When new MCP servers are added or existing ones are updated:

1. Update `REGISTRY.md` with comprehensive documentation
2. Update `servers.json` with structured data
3. Increment registry version if schema changes
4. Update `last_updated` timestamp
5. Commit changes with descriptive message

### Version History

- **v1.0.0** (2025-12-09): Initial registry with 7 core MCP servers

## Resources

### External Links

- **ry-ops GitHub**: https://github.com/ry-ops
- **ry-ops Patreon**: https://patreon.com/ry_ops
- **MCP Specification**: https://modelcontextprotocol.io
- **MCP Server Directory**: https://lobehub.com/mcp

### Related Cortex Files

- Configuration: `/Users/ryandahlberg/Projects/cortex/coordination/config/`
- Masters: `/Users/ryandahlberg/Projects/cortex/coordination/masters/`
- Knowledge Base: `/Users/ryandahlberg/Projects/cortex/coordination/knowledge-base/`

## Contributing

To suggest additions or updates to the registry:

1. Create an issue in the cortex repository
2. Include: Server name, GitHub URL, purpose, tool count, capabilities
3. Provide configuration requirements and use cases
4. Submit PR with updates to both REGISTRY.md and servers.json

## License

This registry is maintained as part of the cortex automation system. Individual MCP servers have their own licenses - refer to respective repositories for details.

---

**Maintained by:** Development Master
**Last Updated:** 2025-12-09
**Registry Version:** 1.0.0
