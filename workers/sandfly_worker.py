"""
Sandfly Worker - Security worker for Sandfly Linux intrusion detection.

This worker uses Claude API to analyze Sandfly findings and perform
threat analysis on Linux systems.
"""

import logging
import os
from typing import Any, Dict, List

import httpx

from agents.base_worker import BaseWorker
from agents.messaging import AgentMessage


logger = logging.getLogger(__name__)


class SandflyWorker(BaseWorker):
    """
    Sandfly security worker.

    Capabilities:
    - Query Sandfly API for host findings
    - Analyze threats using Claude
    - Generate remediation recommendations
    - Track intrusion patterns

    Uses Claude to interpret Sandfly findings and provide contextual
    threat analysis that goes beyond simple detection.
    """

    def __init__(self, **kwargs):
        # Get agent ID from environment or generate
        agent_id = os.getenv("AGENT_ID", "sandfly-worker-001")
        master_id = os.getenv("MASTER_ID", "security-master")

        super().__init__(
            agent_id=agent_id,
            name=f"Sandfly Worker ({agent_id})",
            master_id=master_id,
            **kwargs
        )

        # Sandfly API configuration
        self.sandfly_api_url = os.getenv(
            "SANDFLY_API_URL",
            "http://sandfly-api.cortex-security.svc.cluster.local"
        )
        self.sandfly_api_key = os.getenv("SANDFLY_API_KEY", "")

        # HTTP client for Sandfly API
        self._http_client: httpx.AsyncClient = None

    def get_capabilities(self) -> List[str]:
        """Sandfly worker capabilities."""
        return [
            "sandfly_api",
            "threat_analysis",
            "intrusion_detection",
            "linux_security",
        ]

    def get_system_prompt(self) -> str:
        """System prompt for Claude conversations."""
        return """You are a security analyst specializing in Linux intrusion detection using Sandfly.

Your capabilities:
- Analyze Sandfly scan findings
- Identify threat patterns and indicators of compromise (IOCs)
- Assess threat severity and risk
- Generate remediation recommendations
- Correlate findings across multiple hosts

When analyzing findings:
1. Categorize by threat type (malware, rootkit, suspicious process, etc.)
2. Assess severity (critical, high, medium, low)
3. Identify IOCs and attack patterns
4. Provide specific remediation steps
5. Recommend additional investigation if needed

Be concise but thorough. Focus on actionable intelligence.
"""

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """MCP tools for Sandfly operations."""
        return [
            {
                "name": "sandfly_get_findings",
                "description": "Get security findings from Sandfly for a specific host",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "host_id": {
                            "type": "string",
                            "description": "Sandfly host ID or hostname"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low", "all"],
                            "description": "Filter by severity level"
                        }
                    },
                    "required": ["host_id"]
                }
            },
            {
                "name": "sandfly_get_host_info",
                "description": "Get information about a monitored host",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "host_id": {
                            "type": "string",
                            "description": "Sandfly host ID or hostname"
                        }
                    },
                    "required": ["host_id"]
                }
            },
            {
                "name": "sandfly_list_hosts",
                "description": "List all monitored hosts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["online", "offline", "all"],
                            "description": "Filter by host status"
                        }
                    }
                }
            }
        ]

    async def process_task(self, message: AgentMessage) -> Dict[str, Any]:
        """
        Process task using Claude and Sandfly API.

        Task types:
        - scan_host: Analyze findings for a specific host
        - analyze_threat: Deep dive on specific threat
        - list_findings: Get all findings across hosts
        """
        task_type = message.task_type
        payload = message.payload

        logger.info(f"Processing task: {task_type}")

        # Ensure HTTP client is initialized
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                base_url=self.sandfly_api_url,
                headers={"Authorization": f"Bearer {self.sandfly_api_key}"},
                timeout=30.0,
            )

        if task_type == "scan_host":
            return await self._scan_host(payload)
        elif task_type == "analyze_threat":
            return await self._analyze_threat(payload)
        elif task_type == "list_findings":
            return await self._list_findings(payload)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    async def _scan_host(self, payload: Dict) -> Dict[str, Any]:
        """Scan a host and analyze findings with Claude."""
        host_id = payload.get("host_id")
        if not host_id:
            return {"error": "host_id required"}

        logger.info(f"Scanning host: {host_id}")

        # Clear previous conversation for fresh analysis
        self.clear_conversation()

        # Ask Claude to analyze the host using MCP tools
        user_message = f"""Analyze security findings for host: {host_id}

Please:
1. Get the host information
2. Retrieve all security findings
3. Categorize findings by threat type
4. Assess overall risk level
5. Provide prioritized remediation steps

Focus on critical and high-severity findings first."""

        result = await self.ask_claude_with_tools(user_message, max_iterations=5)

        return {
            "host_id": host_id,
            "analysis": result["response"],
            "tool_calls": result["tool_calls"],
            "iterations": result["iterations"],
        }

    async def _analyze_threat(self, payload: Dict) -> Dict[str, Any]:
        """Deep analysis of a specific threat."""
        threat_data = payload.get("threat_data")
        if not threat_data:
            return {"error": "threat_data required"}

        logger.info(f"Analyzing threat: {threat_data.get('type', 'unknown')}")

        user_message = f"""Perform deep threat analysis on this finding:

{threat_data}

Please:
1. Identify the threat type and TTPs (MITRE ATT&CK if applicable)
2. Assess severity and potential impact
3. List indicators of compromise (IOCs)
4. Suggest forensic investigation steps
5. Recommend immediate remediation actions

Be specific and actionable."""

        response = await self.ask_claude(user_message)

        return {
            "threat_type": threat_data.get("type"),
            "analysis": response,
            "severity": threat_data.get("severity"),
        }

    async def _list_findings(self, payload: Dict) -> Dict[str, Any]:
        """List findings across all hosts with Claude analysis."""
        severity_filter = payload.get("severity", "all")

        logger.info(f"Listing findings (severity: {severity_filter})")

        user_message = f"""Get an overview of security findings across all monitored hosts.

Filter: severity={severity_filter}

Please:
1. List all monitored hosts
2. Get findings for each host
3. Summarize by threat type and severity
4. Identify patterns or trends
5. Highlight top priority items

Provide a concise executive summary."""

        result = await self.ask_claude_with_tools(user_message, max_iterations=10)

        return {
            "summary": result["response"],
            "tool_calls": result["tool_calls"],
        }

    async def process_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute Sandfly MCP tool calls."""
        logger.info(f"Executing tool: {tool_name}")

        try:
            if tool_name == "sandfly_get_findings":
                return await self._tool_get_findings(tool_input)
            elif tool_name == "sandfly_get_host_info":
                return await self._tool_get_host_info(tool_input)
            elif tool_name == "sandfly_list_hosts":
                return await self._tool_list_hosts(tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    async def _tool_get_findings(self, input_data: Dict) -> Dict:
        """Get findings from Sandfly API."""
        host_id = input_data["host_id"]
        severity = input_data.get("severity", "all")

        # Call Sandfly API
        try:
            response = await self._http_client.get(
                f"/api/v1/hosts/{host_id}/findings",
                params={"severity": severity} if severity != "all" else {}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Mock data for development
            logger.warning(f"Sandfly API error, using mock data: {e}")
            return {
                "host_id": host_id,
                "findings": [
                    {
                        "id": "finding-001",
                        "type": "suspicious_process",
                        "severity": "high",
                        "description": "Unusual process /tmp/.hidden running as root",
                        "timestamp": "2026-01-12T20:00:00Z"
                    },
                    {
                        "id": "finding-002",
                        "type": "file_modification",
                        "severity": "medium",
                        "description": "/etc/passwd modified outside package manager",
                        "timestamp": "2026-01-12T19:30:00Z"
                    }
                ]
            }

    async def _tool_get_host_info(self, input_data: Dict) -> Dict:
        """Get host information from Sandfly API."""
        host_id = input_data["host_id"]

        try:
            response = await self._http_client.get(f"/api/v1/hosts/{host_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Mock data
            logger.warning(f"Sandfly API error, using mock data: {e}")
            return {
                "host_id": host_id,
                "hostname": "web-server-01",
                "os": "Ubuntu 22.04",
                "status": "online",
                "last_scan": "2026-01-12T20:30:00Z",
                "ip_address": "10.0.1.50"
            }

    async def _tool_list_hosts(self, input_data: Dict) -> Dict:
        """List hosts from Sandfly API."""
        status_filter = input_data.get("status", "all")

        try:
            response = await self._http_client.get(
                "/api/v1/hosts",
                params={"status": status_filter} if status_filter != "all" else {}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Mock data
            logger.warning(f"Sandfly API error, using mock data: {e}")
            return {
                "hosts": [
                    {"host_id": "host-001", "hostname": "web-server-01", "status": "online"},
                    {"host_id": "host-002", "hostname": "db-server-01", "status": "online"},
                    {"host_id": "host-003", "hostname": "app-server-01", "status": "offline"},
                ]
            }

    async def stop(self) -> None:
        """Stop worker and cleanup."""
        if self._http_client:
            await self._http_client.aclose()
        await super().stop()


async def main():
    """Run Sandfly worker."""
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
    worker = SandflyWorker(
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
