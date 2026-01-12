#!/usr/bin/env python3
"""
GitHub Security MCP Server
Exposes GitHub Dependabot vulnerability alerts through Model Context Protocol
Enables vulnerability detection and automated remediation via chat interface
"""

import os
import json
import logging
from typing import Any, Optional, Dict, List
from functools import wraps

import httpx
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-security-mcp")


class GitHubSecurityConfig(BaseModel):
    """Configuration from environment variables"""
    github_token: str
    organization: str = Field(default="ry-ops")
    base_url: str = Field(default="https://api.github.com")
    timeout: int = Field(default=30)

    @classmethod
    def from_env(cls) -> "GitHubSecurityConfig":
        """Load configuration from environment variables"""
        return cls(
            github_token=os.getenv("GITHUB_TOKEN", ""),
            organization=os.getenv("GITHUB_ORG", "ry-ops"),
            base_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
            timeout=int(os.getenv("GITHUB_TIMEOUT", "30"))
        )


class GitHubSecurityClient:
    """HTTP client for GitHub Security/Dependabot API"""

    def __init__(self, config: GitHubSecurityConfig):
        self.config = config
        self.base_url = config.base_url
        self.client = httpx.Client(
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
        )
        logger.info(f"GitHub Security client initialized for org: {config.organization}")

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        """Execute GET request"""
        url = f"{self.base_url}{endpoint}"
        logger.info(f"GET {url}")
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Execute POST request"""
        url = f"{self.base_url}{endpoint}"
        logger.info(f"POST {url}")
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def patch(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Execute PATCH request"""
        url = f"{self.base_url}{endpoint}"
        logger.info(f"PATCH {url}")
        try:
            response = self.client.patch(url, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def close(self):
        """Close HTTP client"""
        self.client.close()


# Initialize server and client
app = Server("github-security-mcp")
config = GitHubSecurityConfig.from_env()
client = GitHubSecurityClient(config)


def handle_errors(func):
    """Decorator to handle errors and return TextContent"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPError as e:
            error_msg = f"GitHub API error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    return wrapper


def format_vulnerability_summary(alerts: List[dict]) -> str:
    """Format vulnerability alerts into readable summary"""
    if not alerts:
        return "No vulnerabilities found."

    # Group by severity
    by_severity = {"critical": [], "high": [], "medium": [], "low": []}

    for alert in alerts:
        severity = alert.get("security_advisory", {}).get("severity", "unknown").lower()
        if severity in by_severity:
            by_severity[severity].append(alert)

    summary = f"Found {len(alerts)} vulnerabilities:\n\n"

    for severity in ["critical", "high", "medium", "low"]:
        count = len(by_severity[severity])
        if count > 0:
            summary += f"{severity.upper()}: {count}\n"

    summary += "\n"

    # Show details for each vulnerability
    for alert in alerts[:10]:  # Limit to 10 to avoid token overflow
        number = alert.get("number")
        severity = alert.get("security_advisory", {}).get("severity", "unknown").upper()
        cve_id = alert.get("security_advisory", {}).get("cve_id", "N/A")
        summary_text = alert.get("security_advisory", {}).get("summary", "")
        package_name = alert.get("security_vulnerability", {}).get("package", {}).get("name", "unknown")
        vulnerable_version = alert.get("security_vulnerability", {}).get("vulnerable_version_range", "unknown")
        patched_version = alert.get("security_vulnerability", {}).get("first_patched_version", {}).get("identifier", "N/A")

        summary += f"{severity} - {cve_id} (Alert #{number})\n"
        summary += f"└─ Package: {package_name} ({vulnerable_version})\n"
        summary += f"└─ {summary_text}\n"
        summary += f"└─ Fix: Upgrade to {patched_version}\n\n"

    if len(alerts) > 10:
        summary += f"... and {len(alerts) - 10} more vulnerabilities\n"

    return summary


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available GitHub Security MCP tools"""
    return [
        # Organization-wide vulnerability tools
        Tool(
            name="list_vulnerabilities",
            description="List all Dependabot vulnerability alerts across the organization",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["open", "dismissed", "fixed", "auto_dismissed"],
                        "description": "Filter by alert state (default: open)",
                        "default": "open"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Filter by severity level"
                    },
                    "ecosystem": {
                        "type": "string",
                        "description": "Filter by package ecosystem (e.g., npm, pip, rubygems)"
                    }
                },
                "required": []
            }
        ),

        # Repository-specific tools
        Tool(
            name="list_repo_vulnerabilities",
            description="List vulnerabilities for a specific repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name (e.g., 'cortex-platform', 'DriveIQ')"
                    },
                    "state": {
                        "type": "string",
                        "enum": ["open", "dismissed", "fixed", "auto_dismissed"],
                        "description": "Filter by alert state (default: open)",
                        "default": "open"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Filter by severity level"
                    }
                },
                "required": ["repo_name"]
            }
        ),

        # Detailed vulnerability information
        Tool(
            name="get_vulnerability_details",
            description="Get detailed information for a specific vulnerability alert",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "alert_number": {
                        "type": "integer",
                        "description": "Alert number from list_vulnerabilities"
                    }
                },
                "required": ["repo_name", "alert_number"]
            }
        ),

        # Remediation tools
        Tool(
            name="get_vulnerable_files",
            description="List files affected by a vulnerability (manifests like requirements.txt, package.json)",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "alert_number": {
                        "type": "integer",
                        "description": "Alert number"
                    }
                },
                "required": ["repo_name", "alert_number"]
            }
        ),

        Tool(
            name="get_remediation_pr",
            description="Check if Dependabot has created a fix PR for this vulnerability",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "alert_number": {
                        "type": "integer",
                        "description": "Alert number"
                    }
                },
                "required": ["repo_name", "alert_number"]
            }
        ),

        Tool(
            name="dismiss_vulnerability",
            description="Dismiss a vulnerability alert (false positive, won't fix, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "alert_number": {
                        "type": "integer",
                        "description": "Alert number"
                    },
                    "dismiss_reason": {
                        "type": "string",
                        "enum": ["fix_started", "inaccurate", "no_bandwidth", "not_used", "tolerable_risk"],
                        "description": "Reason for dismissing the alert"
                    },
                    "dismiss_comment": {
                        "type": "string",
                        "description": "Optional comment explaining dismissal"
                    }
                },
                "required": ["repo_name", "alert_number", "dismiss_reason"]
            }
        ),

        # Repository information
        Tool(
            name="list_org_repositories",
            description="List all repositories in the organization",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["all", "public", "private"],
                        "description": "Filter by repository type (default: all)",
                        "default": "all"
                    }
                },
                "required": []
            }
        ),

        # Summary/stats tools
        Tool(
            name="get_vulnerability_stats",
            description="Get vulnerability statistics across the organization",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


@app.call_tool()
@handle_errors
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution"""

    if name == "list_vulnerabilities":
        state = arguments.get("state", "open")
        severity = arguments.get("severity")
        ecosystem = arguments.get("ecosystem")

        # Build query parameters
        params = {"state": state, "per_page": 100}
        if severity:
            params["severity"] = severity
        if ecosystem:
            params["ecosystem"] = ecosystem

        # Get alerts from organization
        endpoint = f"/orgs/{config.organization}/dependabot/alerts"
        alerts = client.get(endpoint, params=params)

        # Format response
        summary = format_vulnerability_summary(alerts)
        return [TextContent(type="text", text=summary)]

    elif name == "list_repo_vulnerabilities":
        repo_name = arguments.get("repo_name")
        state = arguments.get("state", "open")
        severity = arguments.get("severity")

        # Build query parameters
        params = {"state": state, "per_page": 100}
        if severity:
            params["severity"] = severity

        # Get alerts from repository
        endpoint = f"/repos/{config.organization}/{repo_name}/dependabot/alerts"
        alerts = client.get(endpoint, params=params)

        # Format response
        summary = f"Vulnerabilities in {config.organization}/{repo_name}:\n\n"
        summary += format_vulnerability_summary(alerts)
        return [TextContent(type="text", text=summary)]

    elif name == "get_vulnerability_details":
        repo_name = arguments.get("repo_name")
        alert_number = arguments.get("alert_number")

        endpoint = f"/repos/{config.organization}/{repo_name}/dependabot/alerts/{alert_number}"
        alert = client.get(endpoint)

        # Format detailed response
        advisory = alert.get("security_advisory", {})
        vulnerability = alert.get("security_vulnerability", {})
        package = vulnerability.get("package", {})

        details = f"""Vulnerability Details (Alert #{alert_number}):

CVE ID: {advisory.get('cve_id', 'N/A')}
GHSA ID: {advisory.get('ghsa_id', 'N/A')}
Severity: {advisory.get('severity', 'unknown').upper()}
CVSS Score: {advisory.get('cvss', {}).get('score', 'N/A')}

Summary: {advisory.get('summary', '')}

Description:
{advisory.get('description', '')}

Affected Package:
- Name: {package.get('name', 'unknown')}
- Ecosystem: {package.get('ecosystem', 'unknown')}
- Vulnerable Range: {vulnerability.get('vulnerable_version_range', 'unknown')}
- First Patched Version: {vulnerability.get('first_patched_version', {}).get('identifier', 'N/A')}

State: {alert.get('state', 'unknown')}
Created: {alert.get('created_at', 'unknown')}
Updated: {alert.get('updated_at', 'unknown')}

References:
{chr(10).join('- ' + ref for ref in advisory.get('references', []))}

Affected Files:
"""
        # Add affected dependency manifest files
        dependency = alert.get("dependency", {})
        if dependency:
            details += f"- Package: {dependency.get('package', {}).get('name', 'unknown')}\n"
            manifest = dependency.get("manifest_path", "")
            if manifest:
                details += f"- Manifest: {manifest}\n"

        return [TextContent(type="text", text=details)]

    elif name == "get_vulnerable_files":
        repo_name = arguments.get("repo_name")
        alert_number = arguments.get("alert_number")

        endpoint = f"/repos/{config.organization}/{repo_name}/dependabot/alerts/{alert_number}"
        alert = client.get(endpoint)

        dependency = alert.get("dependency", {})
        manifest_path = dependency.get("manifest_path", "")
        package_name = dependency.get("package", {}).get("name", "unknown")

        response = f"""Vulnerable Files for Alert #{alert_number}:

Package: {package_name}
Manifest File: {manifest_path if manifest_path else 'Not specified'}

To view the file:
GET /repos/{config.organization}/{repo_name}/contents/{manifest_path}
"""
        return [TextContent(type="text", text=response)]

    elif name == "get_remediation_pr":
        repo_name = arguments.get("repo_name")
        alert_number = arguments.get("alert_number")

        endpoint = f"/repos/{config.organization}/{repo_name}/dependabot/alerts/{alert_number}"
        alert = client.get(endpoint)

        # Check if there's an associated PR
        pr_url = alert.get("fix", {}).get("pull_request", {}).get("html_url")
        pr_number = alert.get("fix", {}).get("pull_request", {}).get("number")
        pr_state = alert.get("fix", {}).get("pull_request", {}).get("state")

        if pr_url:
            response = f"""Dependabot Fix PR for Alert #{alert_number}:

PR #{pr_number}: {pr_state.upper()}
URL: {pr_url}

The fix is ready to review and merge.
"""
        else:
            response = f"""No Dependabot PR found for Alert #{alert_number}.

Dependabot has not yet created a PR for this vulnerability.
You may need to:
1. Check if auto-updates are enabled for this repo
2. Manually create a PR with the fix
3. Update the dependency in your manifest file
"""
        return [TextContent(type="text", text=response)]

    elif name == "dismiss_vulnerability":
        repo_name = arguments.get("repo_name")
        alert_number = arguments.get("alert_number")
        dismiss_reason = arguments.get("dismiss_reason")
        dismiss_comment = arguments.get("dismiss_comment", "")

        endpoint = f"/repos/{config.organization}/{repo_name}/dependabot/alerts/{alert_number}"
        data = {
            "state": "dismissed",
            "dismissed_reason": dismiss_reason,
            "dismissed_comment": dismiss_comment
        }

        result = client.patch(endpoint, data=data)

        response = f"""Alert #{alert_number} dismissed successfully.

Reason: {dismiss_reason}
Comment: {dismiss_comment if dismiss_comment else 'None'}

State: {result.get('state', 'unknown')}
Dismissed By: {result.get('dismissed_by', {}).get('login', 'unknown')}
Dismissed At: {result.get('dismissed_at', 'unknown')}
"""
        return [TextContent(type="text", text=response)]

    elif name == "list_org_repositories":
        repo_type = arguments.get("type", "all")

        endpoint = f"/orgs/{config.organization}/repos"
        params = {"per_page": 100}
        if repo_type != "all":
            params["type"] = repo_type

        repos = client.get(endpoint, params=params)

        response = f"Repositories in {config.organization} ({repo_type}):\n\n"
        for repo in repos:
            name = repo.get("name", "unknown")
            private = "Private" if repo.get("private") else "Public"
            language = repo.get("language", "N/A")
            response += f"- {name} ({private}, {language})\n"

        response += f"\nTotal: {len(repos)} repositories"
        return [TextContent(type="text", text=response)]

    elif name == "get_vulnerability_stats":
        # Get all open vulnerabilities
        endpoint = f"/orgs/{config.organization}/dependabot/alerts"
        params = {"state": "open", "per_page": 100}
        alerts = client.get(endpoint, params=params)

        # Calculate statistics
        total = len(alerts)
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_ecosystem = {}
        by_repo = {}

        for alert in alerts:
            severity = alert.get("security_advisory", {}).get("severity", "unknown").lower()
            if severity in by_severity:
                by_severity[severity] += 1

            ecosystem = alert.get("security_vulnerability", {}).get("package", {}).get("ecosystem", "unknown")
            by_ecosystem[ecosystem] = by_ecosystem.get(ecosystem, 0) + 1

            repo = alert.get("repository", {}).get("name", "unknown")
            by_repo[repo] = by_repo.get(repo, 0) + 1

        stats = f"""Vulnerability Statistics for {config.organization}:

TOTAL OPEN VULNERABILITIES: {total}

By Severity:
- Critical: {by_severity['critical']}
- High: {by_severity['high']}
- Medium: {by_severity['medium']}
- Low: {by_severity['low']}

By Ecosystem:
"""
        for ecosystem, count in sorted(by_ecosystem.items(), key=lambda x: x[1], reverse=True):
            stats += f"- {ecosystem}: {count}\n"

        stats += "\nTop Affected Repositories:\n"
        for repo, count in sorted(by_repo.items(), key=lambda x: x[1], reverse=True)[:10]:
            stats += f"- {repo}: {count} vulnerabilities\n"

        return [TextContent(type="text", text=stats)]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run MCP server"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
