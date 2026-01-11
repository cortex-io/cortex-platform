# mcp-sandfly

<p align="center">
  <img src="assets/logo.png" alt="mcp-sandfly logo" width="200"/>
</p>

[![PyPI version](https://badge.fury.io/py/mcp-sandfly.svg)](https://badge.fury.io/py/mcp-sandfly)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

MCP (Model Context Protocol) server for [Sandfly Security](https://sandflysecurity.com/) - enabling AI-powered agentless Linux intrusion detection and incident response.

## 🎯 Overview

Sandfly is an agentless intrusion detection and incident response platform for Linux. This MCP server exposes Sandfly's REST API to AI assistants like Claude, enabling natural language interaction with your Linux security infrastructure.

**Key Capabilities:**
- 🔍 Query host security status and alerts
- 🚀 Trigger on-demand security scans
- 📊 Retrieve forensic data (processes, users, network listeners)
- ⚙️ Manage scanning schedules and detection rules
- 🔔 Configure alerting and notifications
- 🔐 Manage SSH credentials and jump hosts

## 🚀 Quick Start

### Installation

```bash
# Using uv (recommended)
uv pip install mcp-sandfly

# Using pip
pip install mcp-sandfly
```

### Configuration

Set environment variables for your Sandfly server:

```bash
export SANDFLY_HOST="sandfly.example.com"
export SANDFLY_USERNAME="admin"
export SANDFLY_PASSWORD="your-password"
export SANDFLY_VERIFY_SSL="true"  # Set to "false" for self-signed certs
```

### Claude Desktop Integration

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sandfly": {
      "command": "mcp-sandfly",
      "env": {
        "SANDFLY_HOST": "sandfly.example.com",
        "SANDFLY_USERNAME": "admin",
        "SANDFLY_PASSWORD": "your-password"
      }
    }
  }
}
```

### Docker Deployment

```bash
docker run -d \
  --name mcp-sandfly \
  -e SANDFLY_HOST=sandfly.example.com \
  -e SANDFLY_USERNAME=admin \
  -e SANDFLY_PASSWORD=your-password \
  ghcr.io/ry-ops/mcp-sandfly:latest
```

## 📋 Available Tools

### Host Management

| Tool | Description |
|------|-------------|
| `sandfly_list_hosts` | List all monitored hosts |
| `sandfly_get_host` | Get detailed host information |
| `sandfly_add_hosts` | Add new hosts for monitoring |
| `sandfly_delete_host` | Remove a host from monitoring |

### Host Forensics

| Tool | Description |
|------|-------------|
| `sandfly_get_host_processes` | Get running processes |
| `sandfly_get_host_users` | Get user accounts |
| `sandfly_get_host_listeners` | Get network listeners |
| `sandfly_get_host_services` | Get systemd services |
| `sandfly_get_host_scheduled_tasks` | Get cron/at/timer jobs |
| `sandfly_get_host_kernel_modules` | Get loaded kernel modules |

### Scanning

| Tool | Description |
|------|-------------|
| `sandfly_start_scan` | Trigger an on-demand scan |
| `sandfly_get_scan_errors` | Get scan error log |

### Results & Alerts

| Tool | Description |
|------|-------------|
| `sandfly_get_results` | Search scan results with filters |
| `sandfly_get_result` | Get specific result details |
| `sandfly_get_host_result_summary` | Get result summary by host |
| `sandfly_delete_result` | Delete a result |

### Detection Rules (Sandflies)

| Tool | Description |
|------|-------------|
| `sandfly_list_sandflies` | List all detection rules |
| `sandfly_get_sandfly` | Get rule details |
| `sandfly_activate_sandfly` | Enable a detection rule |
| `sandfly_deactivate_sandfly` | Disable a detection rule |

### Scheduling

| Tool | Description |
|------|-------------|
| `sandfly_list_schedules` | List scan schedules |
| `sandfly_add_schedule` | Create a new schedule |
| `sandfly_run_schedule` | Manually trigger a schedule |
| `sandfly_pause_schedule` | Pause a schedule |
| `sandfly_delete_schedule` | Delete a schedule |

### Credentials & Jump Hosts

| Tool | Description |
|------|-------------|
| `sandfly_list_credentials` | List SSH credentials |
| `sandfly_add_credential` | Add SSH credentials |
| `sandfly_list_jump_hosts` | List bastion/jump hosts |
| `sandfly_add_jump_host` | Add a jump host |

### Notifications

| Tool | Description |
|------|-------------|
| `sandfly_list_notifications` | List notification configs |
| `sandfly_add_notification` | Add webhook/email/syslog alert |
| `sandfly_test_notification` | Send test notification |

### Reports & Audit

| Tool | Description |
|------|-------------|
| `sandfly_get_host_snapshot` | Host snapshot report |
| `sandfly_get_scan_performance` | Scan performance metrics |
| `sandfly_get_audit_log` | System audit log |

## 💬 Example Conversations

### Check for Security Alerts

> **You:** Are there any critical security alerts on my k3s nodes?

> **Claude:** I'll check for critical alerts on your k3s cluster nodes.
> 
> *[Uses sandfly_get_results with severity filter]*
> 
> Found 2 critical alerts:
> - **k3s-worker-01**: Suspicious process detected - cryptominer signature in `/tmp/.hidden`
> - **k3s-worker-03**: SSH authorized_keys modification - new key added for root

### Investigate a Host

> **You:** What processes are running on k3s-worker-01 and are any suspicious?

> **Claude:** *[Uses sandfly_get_host_processes]*
> 
> Here's what's running on k3s-worker-01. I've flagged potentially suspicious items:
> 
> ⚠️ **Suspicious:**
> - PID 4521: `/tmp/.hidden/xmrig` - Known cryptominer binary
> - PID 4520: `/bin/sh -c while true; do...` - Persistence mechanism
> 
> ✅ **Normal k3s processes:**
> - containerd, kubelet, kube-proxy...

### Scan on Demand

> **You:** Run a full security scan on all nodes tagged "production"

> **Claude:** *[Uses sandfly_start_scan with host tags]*
> 
> Initiated full scan on 8 production hosts. The scan typically takes 2-5 minutes per host. I'll check results when complete.

## 🔧 Development

```bash
# Clone and setup
git clone https://github.com/ry-ops/mcp-sandfly.git
cd mcp-sandfly
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
mypy src/
```

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude / AI    │────▶│  MCP Server     │────▶│  Sandfly API    │
│  Assistant      │◀────│  (mcp-sandfly)  │◀────│  Server         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                        │
                               │                        ▼
                               │                ┌───────────────┐
                               │                │ Sandfly Nodes │
                               │                │ (Scanners)    │
                               │                └───────┬───────┘
                               │                        │
                               │                        ▼
                               │                ┌───────────────┐
                               └───────────────▶│ Linux Hosts   │
                                                │ (Agentless)   │
                                                └───────────────┘
```

## 🔐 Security Considerations

- **Credentials**: Store Sandfly credentials securely (environment variables, secrets manager)
- **Network**: MCP server should run in a trusted network with access to Sandfly
- **RBAC**: Use a Sandfly user with appropriate permissions for your use case
- **SSL**: Always verify SSL in production (`SANDFLY_VERIFY_SSL=true`)

## 📚 Resources

- [Sandfly Documentation](https://docs.sandflysecurity.com/)
- [Sandfly API Reference](https://api.sandflysecurity.com/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Author's Blog](https://ry-ops.dev)

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with ❤️ by [ry-ops](https://github.com/ry-ops)
