"""
GitHub Security Worker - Security worker for GitHub code and repository security.

This worker uses Claude API to analyze GitHub Security alerts, dependabot findings,
and code scanning results.
"""

import logging
import os
from typing import Any, Dict, List

import httpx

from agents.base_worker import BaseWorker
from agents.messaging import AgentMessage


logger = logging.getLogger(__name__)


class GitHubSecurityWorker(BaseWorker):
    """
    GitHub Security worker.

    Capabilities:
    - Query GitHub Security APIs
    - Analyze Dependabot alerts
    - Review code scanning results
    - Assess vulnerability impact
    - Generate remediation PRs

    Uses Claude to provide contextual analysis of GitHub security
    findings and suggest fixes.
    """

    def __init__(self, **kwargs):
        # Get agent ID from environment or generate
        agent_id = os.getenv("AGENT_ID", "github-security-worker-001")
        master_id = os.getenv("MASTER_ID", "security-master")

        super().__init__(
            agent_id=agent_id,
            name=f"GitHub Security Worker ({agent_id})",
            master_id=master_id,
            **kwargs
        )

        # GitHub API configuration
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.github_api_url = "https://api.github.com"

        # HTTP client for GitHub API
        self._http_client: httpx.AsyncClient = None

    def get_capabilities(self) -> List[str]:
        """GitHub Security worker capabilities."""
        return [
            "github_security",
            "dependabot_analysis",
            "code_scanning",
            "vulnerability_assessment",
        ]

    def get_system_prompt(self) -> str:
        """System prompt for Claude conversations."""
        return """You are a security analyst specializing in GitHub code and dependency security.

Your capabilities:
- Analyze GitHub Security alerts (Dependabot, Code Scanning, Secret Scanning)
- Assess vulnerability severity and exploitability
- Review vulnerable dependencies and suggest upgrades
- Analyze code patterns that lead to vulnerabilities
- Generate remediation recommendations

When analyzing security findings:
1. Categorize by type (dependency, code, secret, supply chain)
2. Assess actual risk vs. theoretical risk
3. Consider exploit availability and reachability
4. Prioritize based on business impact
5. Suggest specific fixes or mitigations

Be practical - not all vulnerabilities need immediate action.
Focus on what actually matters for security posture.
"""

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """MCP tools for GitHub Security operations."""
        return [
            {
                "name": "github_list_dependabot_alerts",
                "description": "List Dependabot security alerts for a repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner (org or user)"
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name"
                        },
                        "state": {
                            "type": "string",
                            "enum": ["open", "closed", "all"],
                            "description": "Alert state filter"
                        }
                    },
                    "required": ["owner", "repo"]
                }
            },
            {
                "name": "github_list_code_scanning_alerts",
                "description": "List code scanning alerts for a repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "state": {
                            "type": "string",
                            "enum": ["open", "closed", "all"]
                        }
                    },
                    "required": ["owner", "repo"]
                }
            },
            {
                "name": "github_get_alert_details",
                "description": "Get detailed information about a specific alert",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "alert_number": {"type": "integer"}
                    },
                    "required": ["owner", "repo", "alert_number"]
                }
            }
        ]

    async def process_task(self, message: AgentMessage) -> Dict[str, Any]:
        """
        Process task using Claude and GitHub Security APIs.

        Task types:
        - scan_repository: Analyze all security alerts for a repo
        - check_vulnerabilities: Check specific vulnerability
        - list_alerts: Get alerts across repos
        """
        task_type = message.task_type
        payload = message.payload

        logger.info(f"Processing task: {task_type}")

        # Ensure HTTP client is initialized
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                base_url=self.github_api_url,
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=30.0,
            )

        if task_type == "scan_repository":
            return await self._scan_repository(payload)
        elif task_type == "check_vulnerabilities":
            return await self._check_vulnerabilities(payload)
        elif task_type == "list_alerts":
            return await self._list_alerts(payload)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    async def _scan_repository(self, payload: Dict) -> Dict[str, Any]:
        """Scan repository for security issues."""
        owner = payload.get("owner")
        repo = payload.get("repo")

        if not owner or not repo:
            return {"error": "owner and repo required"}

        logger.info(f"Scanning repository: {owner}/{repo}")

        # Clear previous conversation
        self.clear_conversation()

        user_message = f"""Analyze security posture for repository: {owner}/{repo}

Please:
1. Get all Dependabot alerts
2. Get all code scanning alerts
3. Categorize by severity and type
4. Assess overall security risk
5. Prioritize remediation actions

Provide executive summary with actionable next steps."""

        result = await self.ask_claude_with_tools(user_message, max_iterations=5)

        return {
            "owner": owner,
            "repo": repo,
            "analysis": result["response"],
            "tool_calls": result["tool_calls"],
        }

    async def _check_vulnerabilities(self, payload: Dict) -> Dict[str, Any]:
        """Check and analyze specific vulnerabilities."""
        owner = payload.get("owner")
        repo = payload.get("repo")
        alert_number = payload.get("alert_number")

        if not all([owner, repo, alert_number]):
            return {"error": "owner, repo, and alert_number required"}

        logger.info(f"Checking vulnerability: {owner}/{repo}#{alert_number}")

        user_message = f"""Analyze vulnerability alert #{alert_number} in {owner}/{repo}

Please:
1. Get alert details
2. Assess exploitability and impact
3. Check if exploit code exists
4. Determine if vulnerability is reachable in the codebase
5. Suggest specific remediation steps

Be precise about actual risk level."""

        result = await self.ask_claude_with_tools(user_message, max_iterations=3)

        return {
            "owner": owner,
            "repo": repo,
            "alert_number": alert_number,
            "analysis": result["response"],
        }

    async def _list_alerts(self, payload: Dict) -> Dict[str, Any]:
        """List alerts across repositories."""
        repos = payload.get("repos", [])

        if not repos:
            return {"error": "repos list required"}

        logger.info(f"Listing alerts for {len(repos)} repositories")

        repos_str = ", ".join([f"{r['owner']}/{r['repo']}" for r in repos])
        user_message = f"""Get security alert overview for: {repos_str}

Please:
1. Check Dependabot alerts for each repo
2. Summarize by repository
3. Identify patterns or common vulnerabilities
4. Highlight top priority items across all repos

Focus on critical and high-severity issues."""

        result = await self.ask_claude_with_tools(user_message, max_iterations=10)

        return {
            "repositories": repos,
            "summary": result["response"],
        }

    async def process_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute GitHub Security MCP tool calls."""
        logger.info(f"Executing tool: {tool_name}")

        try:
            if tool_name == "github_list_dependabot_alerts":
                return await self._tool_list_dependabot_alerts(tool_input)
            elif tool_name == "github_list_code_scanning_alerts":
                return await self._tool_list_code_scanning_alerts(tool_input)
            elif tool_name == "github_get_alert_details":
                return await self._tool_get_alert_details(tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    async def _tool_list_dependabot_alerts(self, input_data: Dict) -> Dict:
        """List Dependabot alerts via GitHub API."""
        owner = input_data["owner"]
        repo = input_data["repo"]
        state = input_data.get("state", "open")

        try:
            response = await self._http_client.get(
                f"/repos/{owner}/{repo}/dependabot/alerts",
                params={"state": state}
            )
            response.raise_for_status()
            return {"alerts": response.json()}
        except httpx.HTTPError as e:
            # Mock data for development
            logger.warning(f"GitHub API error, using mock data: {e}")
            return {
                "alerts": [
                    {
                        "number": 1,
                        "state": "open",
                        "dependency": {"package": {"name": "lodash"}},
                        "security_advisory": {
                            "severity": "high",
                            "summary": "Prototype Pollution in lodash",
                            "cve_id": "CVE-2020-8203"
                        }
                    },
                    {
                        "number": 2,
                        "state": "open",
                        "dependency": {"package": {"name": "axios"}},
                        "security_advisory": {
                            "severity": "medium",
                            "summary": "Server-Side Request Forgery in axios",
                            "cve_id": "CVE-2021-3749"
                        }
                    }
                ]
            }

    async def _tool_list_code_scanning_alerts(self, input_data: Dict) -> Dict:
        """List code scanning alerts via GitHub API."""
        owner = input_data["owner"]
        repo = input_data["repo"]
        state = input_data.get("state", "open")

        try:
            response = await self._http_client.get(
                f"/repos/{owner}/{repo}/code-scanning/alerts",
                params={"state": state}
            )
            response.raise_for_status()
            return {"alerts": response.json()}
        except httpx.HTTPError as e:
            # Mock data
            logger.warning(f"GitHub API error, using mock data: {e}")
            return {
                "alerts": [
                    {
                        "number": 1,
                        "state": "open",
                        "rule": {
                            "id": "js/sql-injection",
                            "severity": "error",
                            "description": "SQL injection vulnerability"
                        },
                        "most_recent_instance": {
                            "location": {
                                "path": "src/database.js",
                                "start_line": 42
                            }
                        }
                    }
                ]
            }

    async def _tool_get_alert_details(self, input_data: Dict) -> Dict:
        """Get detailed alert information via GitHub API."""
        owner = input_data["owner"]
        repo = input_data["repo"]
        alert_number = input_data["alert_number"]

        try:
            response = await self._http_client.get(
                f"/repos/{owner}/{repo}/dependabot/alerts/{alert_number}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Mock data
            logger.warning(f"GitHub API error, using mock data: {e}")
            return {
                "number": alert_number,
                "state": "open",
                "dependency": {
                    "package": {"ecosystem": "npm", "name": "lodash"},
                    "manifest_path": "package.json"
                },
                "security_advisory": {
                    "severity": "high",
                    "summary": "Prototype Pollution in lodash",
                    "description": "Vulnerable versions allow attackers to modify object prototypes",
                    "cve_id": "CVE-2020-8203",
                    "cvss": {"score": 7.4}
                },
                "security_vulnerability": {
                    "vulnerable_version_range": "< 4.17.19",
                    "first_patched_version": {"identifier": "4.17.19"}
                }
            }

    async def stop(self) -> None:
        """Stop worker and cleanup."""
        if self._http_client:
            await self._http_client.aclose()
        await super().stop()


async def main():
    """Run GitHub Security worker."""
    import signal

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Get config from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    # Create and start worker
    worker = GitHubSecurityWorker(
        redis_url=redis_url,
        anthropic_api_key=anthropic_api_key,
    )

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        import asyncio
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start worker
    await worker.start()

    # Keep running
    try:
        while worker._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await worker.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
