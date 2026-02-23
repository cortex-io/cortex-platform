"""
git-steer — Git operations MCP server for Cortex.

Provides all git/GitHub operations through a single FastMCP interface:
  - git_*   : local git operations (commit, push, branch, revert, status, diff, log)
  - github_* : GitHub API operations (PRs, issues, repos, vulnerabilities)

Runs as a persistent daemon both on k3s (autonomous pipeline) and locally
(human + Claude Code development workflow). Redis-backed operation log and
per-repo branch locks prevent races between concurrent callers.

Environment variables:
  GITHUB_TOKEN      — GitHub personal access token (required)
  GITHUB_ORG        — Default GitHub org (default: cortex-io)
  REDIS_URL         — Redis URL for op log + locking (optional, degrades gracefully)
  GIT_STEER_PORT    — HTTP port (default: 3000)
  GIT_STEER_HOST    — Bind host (default: 0.0.0.0)
  LOG_LEVEL         — Logging level (default: INFO)
"""

__version__ = "0.1.0"
