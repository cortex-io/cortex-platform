# Cortex MCP Server Registry

A comprehensive catalog of all available Model Context Protocol (MCP) servers maintained by ry-ops for cortex integration.

## Registry Overview

This registry tracks all MCP servers that can be integrated with cortex for AI-powered infrastructure and operations management. Each server provides specialized tools for interacting with different platforms and services.

**Registry Maintainer:** ry-ops
**GitHub Organization:** https://github.com/ry-ops
**Last Updated:** 2025-12-09
**Total Servers:** 7

---

## MCP Servers

### 1. n8n MCP Server

**Repository:** https://github.com/ry-ops/n8n-mcp-server
**Status:** Active
**Language:** Python
**Tools:** 16+

#### Description
A Model Context Protocol server that provides Claude Desktop with access to your self-hosted n8n instance. Enables controlling workflows, monitoring executions, and managing automation directly through AI agents.

#### Key Capabilities
- **Workflow Management**: List, create, update, and delete workflows
- **Workflow Execution**: Execute workflows manually with optional input data
- **Workflow Control**: Activate and deactivate workflows
- **Execution Monitoring**: View execution history and details
- **Full API Access**: Comprehensive integration with n8n's REST API

#### Configuration
- `N8N_URL`: URL of your n8n instance
- `N8N_API_KEY`: API key for authentication

#### Use Cases
- Automated workflow orchestration
- CI/CD pipeline management
- Integration automation
- Workflow monitoring and debugging

---

### 2. Cortex Resource Manager

**Repository:** https://github.com/ry-ops/cortex-resource-manager
**Status:** Active
**Language:** Python
**Tools:** 16+

#### Description
A specialized MCP server for Kubernetes resource management, providing dynamic worker provisioning and cluster resource orchestration capabilities for cortex.

#### Key Capabilities
- **Burst Worker Provisioning**: Create temporary workers with configurable TTL
- **Node Management**: Gracefully drain and manage worker nodes
- **VM Integration**: Integrates with Talos MCP or Proxmox MCP for VM creation
- **Auto-Clustering**: Automatically joins new VMs to Kubernetes cluster
- **Resource Labeling**: Labels burst workers for tracking and management

#### Configuration
- Requires Python 3.8+
- Kubernetes cluster access (kubeconfig or service account)
- Integration with Talos or Proxmox MCP servers

#### Use Cases
- Dynamic worker scaling
- Burst compute capacity
- Graceful node maintenance
- Resource lifecycle management

---

### 3. Talos MCP Server

**Repository:** https://github.com/ry-ops/talos-mcp-server
**Status:** Active
**Language:** Python
**Tools:** 12+

#### Description
A Model Context Protocol server that provides seamless integration with Talos Linux clusters through the native gRPC API. Enables Claude to interact with Talos infrastructure for comprehensive cluster management.

#### Key Capabilities
- **Cluster Management**: Get version info, health status, and resource information
- **Disk Management**: List and inspect disks on Talos nodes
- **Monitoring**: Access logs, services, and real-time dashboard data
- **File System**: Browse and read files on Talos nodes
- **etcd Integration**: Manage and inspect etcd cluster members
- **Kubernetes Config**: Retrieve kubeconfig for cluster access
- **Resource Inspection**: Query any Talos resource (similar to kubectl get)

#### Configuration
- Uses Talos configuration from `~/.talos/config`
- Requires valid Talos cluster credentials
- Communicates via gRPC API

#### Use Cases
- Talos cluster monitoring
- Node troubleshooting
- Configuration inspection
- Kubernetes bootstrap
- etcd cluster management

---

### 4. Proxmox MCP Server

**Repository:** https://github.com/ry-ops/proxmox-mcp-server
**Status:** Active
**Language:** Python
**Tools:** 15+

#### Description
A Model Context Protocol server for managing Proxmox virtualization environments. Provides comprehensive VM and container lifecycle management through AI-powered interactions.

#### Key Capabilities
- **VM Management**: Create, start, stop, and delete virtual machines
- **Container Management**: LXC container lifecycle operations
- **Resource Monitoring**: Track CPU, memory, disk, and network usage
- **Cluster Management**: Multi-node Proxmox cluster support
- **Backup Operations**: VM and container backup management
- **Network Configuration**: Virtual network and VLAN management

#### Configuration
- Proxmox API endpoint URL
- API token or username/password authentication
- TLS certificate validation options

#### Use Cases
- VM provisioning and management
- Container orchestration
- Infrastructure automation
- Resource capacity planning
- Disaster recovery operations

---

### 5. UniFi MCP Server

**Repository:** https://github.com/ry-ops/unifi-mcp-server
**Status:** Active
**Language:** Python
**Tools:** 18+
**Fork From:** zcking/mcp-server-unifi

#### Description
A comprehensive Model Context Protocol server for UniFi infrastructure monitoring and management. Features Agent-to-Agent (A2A) Protocol for intelligent, multi-step network operations with built-in safety checks.

#### Key Capabilities
- **Local Controller Integration**: Direct access via Integration API
- **Cloud Site Manager**: Infrastructure monitoring via UniFi Site Manager API
- **Smart Fallback**: Automatically discovers correct site IDs and API switching
- **A2A Protocol**: Multi-step workflows with guided operations
- **Network Management**: Client, device, and network monitoring
- **Security Operations**: Firewall rules, port forwarding, VPN management

#### Configuration
- UniFi controller URL (local or cloud)
- API credentials (local controller or Site Manager)
- Site ID for multi-site deployments

#### Use Cases
- Network monitoring and troubleshooting
- Client and device management
- Security policy enforcement
- Network performance optimization
- Multi-site infrastructure management

---

### 6. Cloudflare MCP Server

**Repository:** https://github.com/ry-ops/cloudflare-mcp-server
**Status:** Active
**Language:** Python
**Tools:** 13

#### Description
A Model Context Protocol server providing seamless integration with the Cloudflare API. Enables comprehensive management of Cloudflare resources including DNS, zones, and KV storage.

#### Key Capabilities
- **Zone Management**: List and manage zones (domains)
- **DNS Operations**: Create, read, update, delete DNS records
- **KV Storage**: Cloudflare Workers KV namespace management
- **SSL/TLS**: Certificate management and configuration
- **Firewall Rules**: WAF and security rule management
- **Analytics**: Zone and DNS analytics access
- **Filtering Support**: Advanced filtering for all list operations

#### Configuration
- `CLOUDFLARE_API_TOKEN`: API token with appropriate permissions
- `CLOUDFLARE_ACCOUNT_ID`: Account ID (optional, needed for KV operations)

#### Use Cases
- DNS automation and management
- Zone configuration
- CDN and cache management
- Security policy deployment
- Edge compute resource management

---

### 7. Microsoft Graph MCP Server

**Repository:** https://github.com/ry-ops/microsoft-graph-mcp-server
**Status:** Active
**Language:** Python
**Tools:** 10+

#### Description
A Model Context Protocol server that integrates Microsoft Graph API with Claude, enabling natural language management of Microsoft 365 users, licenses, and groups.

#### Key Capabilities
- **User Management**: Create, update, and search users
- **License Management**: Assign and manage Microsoft 365 licenses
- **Group Management**: Create and manage security and distribution groups
- **Organization Data**: Access organization and directory information
- **User Search**: Advanced user search and filtering
- **Tenant Operations**: Tenant-wide configuration and management

#### Configuration
- `MICROSOFT_TENANT_ID`: Azure AD tenant ID
- `MICROSOFT_CLIENT_ID`: App registration client ID
- `MICROSOFT_CLIENT_SECRET`: App registration client secret

#### Use Cases
- User provisioning and management
- License automation
- Group membership management
- Directory synchronization
- Compliance and reporting

---

## Integration Patterns

### Cortex Integration

All MCP servers can be integrated with cortex through the standard MCP protocol:

1. **Direct Integration**: Configure MCP servers in Claude Desktop config
2. **Worker Integration**: Use MCP tools from cortex workers
3. **Master Orchestration**: Coordinate multiple MCP servers through cortex masters
4. **A2A Protocol**: Enable Agent-to-Agent communication for complex workflows

### Configuration Template

```json
{
  "mcpServers": {
    "server-name": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/server",
        "run",
        "server-name"
      ],
      "env": {
        "API_KEY": "your-api-key",
        "API_URL": "your-api-url"
      }
    }
  }
}
```

---

## Server Status Legend

- **Active**: Currently maintained and production-ready
- **Beta**: Under active development, may have breaking changes
- **Deprecated**: No longer maintained, use alternative
- **Archived**: Historical reference only

---

## Additional Resources

### ry-ops GitHub Organization
- **URL**: https://github.com/ry-ops
- **Patreon**: https://patreon.com/ry_ops
- **Total Repositories**: 16+

### Related Projects
- **unifi-grafana-streamer**: Real-time UniFi event streaming to Grafana via MCP
- **starlink-enterprise-mcp-server**: MCP server for Starlink Enterprise management

### Documentation References
- Model Context Protocol Specification: https://modelcontextprotocol.io
- MCP Server Directory (LobeHub): https://lobehub.com/mcp
- Anthropic MCP Documentation: https://docs.anthropic.com/mcp

---

## Contributing to Registry

To add or update MCP server information:

1. Create issue in cortex repository with server details
2. Include: GitHub URL, purpose, tool count, key capabilities
3. Provide configuration requirements and use cases
4. Submit PR updating both REGISTRY.md and servers.json

---

## Version History

- **v1.0.0** (2025-12-09): Initial registry with 7 core MCP servers
  - n8n MCP Server
  - Cortex Resource Manager
  - Talos MCP Server
  - Proxmox MCP Server
  - UniFi MCP Server
  - Cloudflare MCP Server
  - Microsoft Graph MCP Server

---

## License

This registry is maintained as part of the cortex project. Individual MCP servers have their own licenses - see respective repositories for details.
