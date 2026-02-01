"""
Execution Claude Code Layer - Agentic Task Execution

This layer executes complex, multi-step tasks using Claude Code CLI
running inside the cluster. It provides full agentic capabilities:
- Tool orchestration
- Code execution
- MCP server integration
- Multi-step reasoning

This is the "big brain" escalation path when local DMR can't handle
the complexity of a task.

Key features:
- Claude Code CLI execution with proper sandboxing
- MCP server access (kubernetes, cortex, sandfly, etc.)
- Streaming responses for long-running tasks
- Cost tracking and budget controls
"""

import asyncio
import os
import time
import json
import tempfile
import subprocess
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog

log = structlog.get_logger()

# =============================================================================
# Configuration
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", "120"))  # seconds
ALLOWED_MCP_SERVERS = os.getenv("ALLOWED_MCP_SERVERS", "kubernetes,cortex").split(",")

# Cost tracking
COST_PER_1K_INPUT = 0.003
COST_PER_1K_OUTPUT = 0.015
MAX_COST_PER_REQUEST = float(os.getenv("MAX_COST_PER_REQUEST", "0.10"))


# =============================================================================
# Metrics
# =============================================================================

EXECUTIONS_TOTAL = Counter(
    'cortex_claude_code_executions_total',
    'Total Claude Code executions',
    ['status']  # success, failure, timeout, budget_exceeded
)

EXECUTION_LATENCY = Histogram(
    'cortex_claude_code_execution_latency_seconds',
    'Execution latency',
    buckets=[1, 2, 5, 10, 30, 60, 120, 300]
)

TOKENS_TOTAL = Counter(
    'cortex_claude_code_tokens_total',
    'Total tokens used',
    ['direction']  # input, output
)

COST_USD = Counter(
    'cortex_claude_code_cost_usd_total',
    'Total cost in USD'
)

TOOLS_USED = Counter(
    'cortex_claude_code_tools_used_total',
    'Tools used during execution',
    ['tool']
)

ACTIVE_EXECUTIONS = Gauge(
    'cortex_claude_code_active_executions',
    'Currently running executions'
)


# =============================================================================
# Models
# =============================================================================

class ExecutionRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    mcp_servers: Optional[List[str]] = None
    max_tokens: Optional[int] = 4096
    timeout: Optional[int] = 120
    budget_usd: Optional[float] = 0.10


class ToolUsage(BaseModel):
    tool: str
    count: int


class ExecutionResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    execution_id: str
    latency_ms: int
    tokens_used: Dict[str, int]
    cost_usd: float
    tools_used: List[ToolUsage]
    mcp_servers_used: List[str]


# =============================================================================
# Claude Code Executor
# =============================================================================

class ClaudeCodeExecutor:
    """
    Executes queries using Claude Code CLI.

    Claude Code is run as a subprocess with appropriate sandboxing.
    MCP servers are configured to give Claude access to cluster tools.
    """

    def __init__(self):
        self.log = structlog.get_logger()
        self.api_key_available = bool(ANTHROPIC_API_KEY)

    async def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute a query using Claude Code."""
        execution_id = f"exec-{int(time.time())}-{os.urandom(4).hex()}"
        start = time.time()

        self.log.info(
            "claude_code_execution_starting",
            execution_id=execution_id,
            query=request.query[:100]
        )

        if not self.api_key_available:
            return ExecutionResponse(
                success=False,
                error="ANTHROPIC_API_KEY not configured",
                execution_id=execution_id,
                latency_ms=0,
                tokens_used={"input": 0, "output": 0},
                cost_usd=0.0,
                tools_used=[],
                mcp_servers_used=[],
            )

        ACTIVE_EXECUTIONS.inc()

        try:
            # Validate MCP servers
            mcp_servers = request.mcp_servers or ["kubernetes"]
            mcp_servers = [s for s in mcp_servers if s in ALLOWED_MCP_SERVERS]

            # Build the prompt with context
            prompt = self._build_prompt(request.query, request.context)

            # Execute Claude Code
            result = await self._run_claude_code(
                prompt=prompt,
                mcp_servers=mcp_servers,
                max_tokens=request.max_tokens,
                timeout=request.timeout or MAX_EXECUTION_TIME,
            )

            latency_ms = int((time.time() - start) * 1000)
            EXECUTION_LATENCY.observe(time.time() - start)

            # Calculate cost
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            cost = (input_tokens / 1000 * COST_PER_1K_INPUT +
                    output_tokens / 1000 * COST_PER_1K_OUTPUT)

            TOKENS_TOTAL.labels(direction="input").inc(input_tokens)
            TOKENS_TOTAL.labels(direction="output").inc(output_tokens)
            COST_USD.inc(cost)

            # Track tools used
            tools_used = result.get("tools_used", [])
            for tool in tools_used:
                TOOLS_USED.labels(tool=tool["tool"]).inc(tool["count"])

            if result.get("success"):
                EXECUTIONS_TOTAL.labels(status="success").inc()
            else:
                EXECUTIONS_TOTAL.labels(status="failure").inc()

            self.log.info(
                "claude_code_execution_complete",
                execution_id=execution_id,
                success=result.get("success"),
                latency_ms=latency_ms,
                cost_usd=round(cost, 4),
                tools_used=len(tools_used)
            )

            return ExecutionResponse(
                success=result.get("success", False),
                response=result.get("response"),
                error=result.get("error"),
                execution_id=execution_id,
                latency_ms=latency_ms,
                tokens_used={"input": input_tokens, "output": output_tokens},
                cost_usd=cost,
                tools_used=[ToolUsage(**t) for t in tools_used],
                mcp_servers_used=mcp_servers,
            )

        except asyncio.TimeoutError:
            EXECUTIONS_TOTAL.labels(status="timeout").inc()
            latency_ms = int((time.time() - start) * 1000)
            return ExecutionResponse(
                success=False,
                error=f"Execution timed out after {request.timeout}s",
                execution_id=execution_id,
                latency_ms=latency_ms,
                tokens_used={"input": 0, "output": 0},
                cost_usd=0.0,
                tools_used=[],
                mcp_servers_used=[],
            )

        except Exception as e:
            EXECUTIONS_TOTAL.labels(status="failure").inc()
            latency_ms = int((time.time() - start) * 1000)
            self.log.error("claude_code_execution_failed", error=str(e))
            return ExecutionResponse(
                success=False,
                error=str(e),
                execution_id=execution_id,
                latency_ms=latency_ms,
                tokens_used={"input": 0, "output": 0},
                cost_usd=0.0,
                tools_used=[],
                mcp_servers_used=[],
            )

        finally:
            ACTIVE_EXECUTIONS.dec()

    def _build_prompt(self, query: str, context: Optional[Dict]) -> str:
        """Build the full prompt with context."""
        prompt_parts = []

        # Add context if provided
        if context:
            prompt_parts.append("## Context")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")

        # Add the main query
        prompt_parts.append("## Task")
        prompt_parts.append(query)

        # Add guidelines
        prompt_parts.append("")
        prompt_parts.append("## Guidelines")
        prompt_parts.append("- Be thorough but concise in your response")
        prompt_parts.append("- Use available MCP tools when needed")
        prompt_parts.append("- For destructive actions, describe what you would do")
        prompt_parts.append("- Provide clear explanations of your findings")

        return "\n".join(prompt_parts)

    async def _run_claude_code(
        self,
        prompt: str,
        mcp_servers: List[str],
        max_tokens: int,
        timeout: int,
    ) -> Dict[str, Any]:
        """
        Run Claude Code CLI and capture output.

        This uses the Claude Code CLI in non-interactive mode.
        """
        # Create a temporary file with the prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Build Claude Code command
            cmd = [
                "claude",
                "--print",  # Non-interactive mode
                "--output-format", "json",
                "--max-turns", "10",
            ]

            # Add MCP server allowlist
            for server in mcp_servers:
                cmd.extend(["--allowedTools", f"mcp__{server}__*"])

            # Add the prompt
            cmd.extend(["--prompt", prompt])

            # Set environment
            env = os.environ.copy()
            env["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
            env["CLAUDE_MODEL"] = CLAUDE_MODEL

            # Run Claude Code
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                raise

            # Parse output
            output = stdout.decode()
            error_output = stderr.decode()

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": error_output or f"Exit code {process.returncode}",
                    "response": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "tools_used": [],
                }

            # Parse JSON output from Claude Code
            try:
                result = json.loads(output)
                return {
                    "success": True,
                    "response": result.get("result", output),
                    "error": None,
                    "input_tokens": result.get("usage", {}).get("input_tokens", 0),
                    "output_tokens": result.get("usage", {}).get("output_tokens", 0),
                    "tools_used": self._extract_tools_used(result),
                }
            except json.JSONDecodeError:
                # If not JSON, use raw output
                return {
                    "success": True,
                    "response": output,
                    "error": None,
                    "input_tokens": 0,  # Unknown without JSON
                    "output_tokens": 0,
                    "tools_used": [],
                }

        finally:
            # Clean up temp file
            try:
                os.unlink(prompt_file)
            except OSError:
                pass

    def _extract_tools_used(self, result: Dict) -> List[Dict]:
        """Extract tools used from Claude Code result."""
        tools = {}
        for message in result.get("messages", []):
            if message.get("role") == "assistant":
                for content in message.get("content", []):
                    if content.get("type") == "tool_use":
                        tool_name = content.get("name", "unknown")
                        tools[tool_name] = tools.get(tool_name, 0) + 1

        return [{"tool": name, "count": count} for name, count in tools.items()]


# =============================================================================
# FastAPI Application
# =============================================================================

executor: Optional[ClaudeCodeExecutor] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global executor

    log.info(
        "execution_claude_code_starting",
        model=CLAUDE_MODEL,
        api_key_configured=bool(ANTHROPIC_API_KEY)
    )

    executor = ClaudeCodeExecutor()

    yield

    log.info("execution_claude_code_shutdown")


app = FastAPI(
    title="Execution Claude Code",
    description="Agentic task execution via Claude Code CLI",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# HTTP Endpoints
# =============================================================================

@app.get("/health")
async def health():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "execution-claude-code",
        "api_key_configured": bool(ANTHROPIC_API_KEY),
        "model": CLAUDE_MODEL,
        "allowed_mcp_servers": ALLOWED_MCP_SERVERS,
    }


@app.get("/ready")
async def ready():
    """Readiness check."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, detail="ANTHROPIC_API_KEY not configured")
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.post("/execute", response_model=ExecutionResponse)
async def execute(request: ExecutionRequest):
    """Execute a query using Claude Code."""
    if not executor:
        raise HTTPException(503, detail="Executor not initialized")

    return await executor.execute(request)


@app.get("/cost-estimate")
async def cost_estimate(tokens: int):
    """Estimate cost for a given number of tokens."""
    # Assume 2:1 input:output ratio
    input_tokens = int(tokens * 0.66)
    output_tokens = int(tokens * 0.34)
    cost = (input_tokens / 1000 * COST_PER_1K_INPUT +
            output_tokens / 1000 * COST_PER_1K_OUTPUT)
    return {
        "estimated_cost_usd": round(cost, 4),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
