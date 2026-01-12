# GitHub Security MCP Server

Vulnerability detection and automated remediation for Cortex infrastructure via Model Context Protocol.

## Overview

This MCP server exposes GitHub Dependabot vulnerability alerts for all repositories in the `ry-ops` organization. It enables vulnerability detection, analysis, and remediation through a chat interface.

## Features

- **Organization-wide vulnerability scanning** - Query all Dependabot alerts across all repos
- **Repository-specific queries** - Focus on specific projects (e.g., DriveIQ, cortex-platform)
- **Detailed vulnerability information** - CVE details, CVSS scores, affected packages
- **Remediation support** - Check for Dependabot fix PRs, view affected files
- **Alert management** - Dismiss false positives and track vulnerability lifecycle
- **Statistics and reporting** - Vulnerability stats by severity, ecosystem, and repository

## Tools

### Scanning Tools

#### `list_vulnerabilities`
List all Dependabot vulnerability alerts across the organization.

**Parameters:**
- `state` (optional): Filter by state - `open`, `dismissed`, `fixed`, `auto_dismissed` (default: `open`)
- `severity` (optional): Filter by severity - `low`, `medium`, `high`, `critical`
- `ecosystem` (optional): Filter by ecosystem - `npm`, `pip`, `rubygems`, etc.

**Example:**
```
list_vulnerabilities(state="open", severity="high")
```

#### `list_repo_vulnerabilities`
List vulnerabilities for a specific repository.

**Parameters:**
- `repo_name` (required): Repository name (e.g., `DriveIQ`, `cortex-platform`)
- `state` (optional): Filter by state (default: `open`)
- `severity` (optional): Filter by severity

**Example:**
```
list_repo_vulnerabilities(repo_name="DriveIQ", severity="critical")
```

### Analysis Tools

#### `get_vulnerability_details`
Get detailed information for a specific vulnerability alert.

**Parameters:**
- `repo_name` (required): Repository name
- `alert_number` (required): Alert number from list commands

**Returns:**
- CVE/GHSA IDs
- CVSS scores
- Detailed description
- Affected package and versions
- Patched version
- References and links

#### `get_vulnerable_files`
List files affected by a vulnerability (manifest files like `requirements.txt`, `package.json`).

**Parameters:**
- `repo_name` (required): Repository name
- `alert_number` (required): Alert number

### Remediation Tools

#### `get_remediation_pr`
Check if Dependabot has created a fix PR for this vulnerability.

**Parameters:**
- `repo_name` (required): Repository name
- `alert_number` (required): Alert number

**Returns:** PR number and URL if exists, otherwise guidance on manual fixes.

#### `dismiss_vulnerability`
Dismiss a vulnerability alert (false positive, accepted risk, etc.).

**Parameters:**
- `repo_name` (required): Repository name
- `alert_number` (required): Alert number
- `dismiss_reason` (required): One of:
  - `fix_started` - Fix is in progress
  - `inaccurate` - False positive
  - `no_bandwidth` - Won't fix right now
  - `not_used` - Vulnerable code not used
  - `tolerable_risk` - Accepted risk
- `dismiss_comment` (optional): Explanation

### Repository Tools

#### `list_org_repositories`
List all repositories in the organization.

**Parameters:**
- `type` (optional): Filter by type - `all`, `public`, `private` (default: `all`)

#### `get_vulnerability_stats`
Get vulnerability statistics across the organization.

**Returns:**
- Total open vulnerabilities
- Breakdown by severity
- Breakdown by ecosystem
- Top affected repositories

## Configuration

### Environment Variables

- `GITHUB_TOKEN` (required): GitHub Personal Access Token with `security_events` and `repo` scopes
- `GITHUB_ORG` (optional): GitHub organization name (default: `ry-ops`)
- `GITHUB_API_URL` (optional): GitHub API base URL (default: `https://api.github.com`)
- `GITHUB_TIMEOUT` (optional): Request timeout in seconds (default: `30`)

### GitHub Token Setup

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Create a new token with scopes:
   - `security_events` - Read security events (required for Dependabot alerts)
   - `repo` - Full repository access (required for private repos)
3. Set as `GITHUB_TOKEN` environment variable

## API Reference

This server uses the GitHub REST API v3:

- **Dependabot Alerts**: `https://docs.github.com/en/rest/dependabot/alerts`
- **Authentication**: Bearer token via `Authorization` header
- **Rate Limits**: 5,000 requests/hour for authenticated requests

## Usage Examples

### Example 1: Scan all vulnerabilities
```
User: "Show me all critical vulnerabilities across our organization"
System calls: list_vulnerabilities(severity="critical")
```

### Example 2: Check specific repository
```
User: "Show me vulnerabilities in DriveIQ backend"
System calls: list_repo_vulnerabilities(repo_name="DriveIQ", state="open")
```

### Example 3: Get detailed information
```
User: "Tell me more about alert #42 in DriveIQ"
System calls: get_vulnerability_details(repo_name="DriveIQ", alert_number=42)
```

### Example 4: Check for fix PR
```
User: "Is there a fix PR for DriveIQ alert #42?"
System calls: get_remediation_pr(repo_name="DriveIQ", alert_number=42)
```

### Example 5: Dismiss false positive
```
User: "Dismiss alert #42 in DriveIQ as false positive"
System calls: dismiss_vulnerability(
    repo_name="DriveIQ",
    alert_number=42,
    dismiss_reason="inaccurate",
    dismiss_comment="This vulnerability doesn't apply to our use case"
)
```

### Example 6: Organization statistics
```
User: "Show me vulnerability statistics for our organization"
System calls: get_vulnerability_stats()
```

## Deployment

This server runs as a Kubernetes deployment in the `cortex-system` namespace:

- **Service**: `github-security-mcp-server.cortex-system.svc.cluster.local:3003`
- **Port**: 3003
- **Protocol**: HTTP (MCP over HTTP via wrapper)
- **Resources**: 100m-400m CPU, 128Mi-256Mi memory

## Integration with Cortex

This MCP server integrates with the Cortex MoE (Mixture of Experts) router. Queries containing vulnerability-related keywords are automatically routed to this server:

- `vulnerability`, `vulnerabilities`, `cve`, `dependabot`, `security alert`
- `dependency`, `dependencies`, `upgrade`, `patch`, `security fix`
- `snyk`, `npm audit`, `pip-audit`, `remediate`, `remediation`

## Security Considerations

- **Token Security**: GitHub token provides read/write access to Dependabot alerts
- **Rate Limiting**: Monitor GitHub API rate limits (5,000 requests/hour)
- **Network Policy**: Server runs in `cortex-system` namespace with appropriate network policies
- **Secrets Management**: Token stored as Kubernetes environment variable (consider using Secrets)

## Future Enhancements

- **Automatic PR creation** - Generate fix PRs directly from chat
- **Batch operations** - Fix multiple vulnerabilities at once
- **Scheduled scanning** - Periodic vulnerability reports
- **Webhook integration** - Real-time alerts for new vulnerabilities
- **SBOM generation** - Software Bill of Materials for each repository
- **Custom remediation templates** - Predefined fix patterns for common vulnerabilities

## Support

For issues or questions:
- Check GitHub API status: https://www.githubstatus.com/
- Review Dependabot documentation: https://docs.github.com/en/code-security/dependabot
- Check server logs: `kubectl logs -n cortex-system deployment/github-security-mcp-server`

## Version

**v1.0.0** - Initial release with core vulnerability scanning and remediation features
