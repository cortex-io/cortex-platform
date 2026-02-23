"""
git-steer FastMCP server.

Exposes all git/GitHub operations as MCP tools.  Write operations (commit,
push, revert, create_pr, merge_pr, dismiss_vulnerability) acquire a per-branch
lock via GitSteerStore before executing, then log the operation to the op log.

Read-only operations (status, log, diff, list_*, get_*) run without locking.

Transport: HTTP/SSE on GIT_STEER_HOST:GIT_STEER_PORT (default 0.0.0.0:3000).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import structlog
from mcp.server.fastmcp import FastMCP

from git_steer import git_ops
from git_steer.github_client import GitHubClient
from git_steer.store import GitSteerStore

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, LOG_LEVEL, logging.INFO)
    ),
)
log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Global singletons (initialised in lifespan)
# ---------------------------------------------------------------------------

store: GitSteerStore = GitSteerStore()
gh: GitHubClient = GitHubClient()

HOST = os.getenv("GIT_STEER_HOST", "0.0.0.0")
PORT = int(os.getenv("GIT_STEER_PORT", "3000"))

mcp = FastMCP("git-steer", host=HOST, port=PORT)


# ---------------------------------------------------------------------------
# Lifespan: connect/disconnect Redis and GitHub HTTP client
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app):
    await store.connect()
    log.info("git_steer_started", host=HOST, port=PORT)
    yield
    await store.close()
    await gh.close()
    log.info("git_steer_stopped")


mcp.settings.lifespan = _lifespan  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Helper: caller identity from tool context (best-effort)
# ---------------------------------------------------------------------------

def _caller(ctx_caller: Optional[str] = None) -> str:
    return ctx_caller or os.getenv("GIT_STEER_CALLER", "unknown")


# ===========================================================================
# GIT TOOLS
# ===========================================================================

@mcp.tool()
async def git_status(
    repo_name: str,
    branch: str = "main",
) -> dict:
    """Return the working-tree status of a repo (dirty, staged, unstaged, untracked)."""
    return git_ops.git_status(repo_name, branch)


@mcp.tool()
async def git_log(
    repo_name: str,
    branch: str = "main",
    limit: int = 20,
) -> list:
    """Return recent commits on a branch (sha, author, date, message)."""
    return git_ops.git_log(repo_name, branch, limit)


@mcp.tool()
async def git_diff(
    repo_name: str,
    branch: str = "main",
    ref: Optional[str] = None,
) -> str:
    """Return the diff for a repo. If ref is provided, diffs against that ref; otherwise diffs HEAD."""
    return git_ops.git_diff(repo_name, branch, ref)


@mcp.tool()
async def git_list_branches(repo_name: str) -> list:
    """List all local branches in the cached clone of a repo."""
    return git_ops.list_branches(repo_name)


@mcp.tool()
async def git_create_branch(
    repo_name: str,
    branch: str,
    from_branch: str = "main",
) -> dict:
    """Create a new branch (idempotent — checks out existing branch if it already exists)."""
    return git_ops.git_create_branch(repo_name, branch, from_branch)


@mcp.tool()
async def git_commit(
    repo_name: str,
    branch: str,
    message: str,
    files: Optional[list] = None,
    author_name: str = "Cortex",
    author_email: str = "cortex@cortex.ai",
    caller: str = "unknown",
) -> dict:
    """
    Stage files (or all tracked changes) and create a commit on branch.
    Acquires the branch lock before writing. Returns new commit SHA.
    """
    async with store.branch_lock(repo_name, branch, _caller(caller)):
        result = git_ops.git_commit(repo_name, branch, message, files, author_name, author_email)
        await store.log_op("commit", repo_name, branch, _caller(caller), result)
        return result


@mcp.tool()
async def git_push(
    repo_name: str,
    branch: str,
    force: bool = False,
    caller: str = "unknown",
) -> dict:
    """
    Push the current branch to origin.
    Acquires the branch lock before pushing.
    """
    async with store.branch_lock(repo_name, branch, _caller(caller)):
        result = git_ops.git_push(repo_name, branch, force)
        await store.log_op("push", repo_name, branch, _caller(caller), result)
        return result


@mcp.tool()
async def git_commit_and_push(
    repo_name: str,
    branch: str,
    message: str,
    files: Optional[list] = None,
    author_name: str = "Cortex",
    author_email: str = "cortex@cortex.ai",
    caller: str = "unknown",
) -> dict:
    """
    Convenience: commit then push in a single lock acquisition.
    Returns the push result with the commit SHA included.
    """
    async with store.branch_lock(repo_name, branch, _caller(caller)):
        commit_result = git_ops.git_commit(repo_name, branch, message, files, author_name, author_email)
        if commit_result.get("status") == "nothing_to_commit":
            return commit_result
        push_result = git_ops.git_push(repo_name, branch, force=False)
        result = {**commit_result, **push_result}
        await store.log_op("commit_and_push", repo_name, branch, _caller(caller), result)
        return result


@mcp.tool()
async def git_revert(
    repo_name: str,
    branch: str,
    commit_sha: str,
    author_name: str = "Cortex",
    author_email: str = "cortex@cortex.ai",
    push: bool = True,
    caller: str = "unknown",
) -> dict:
    """
    Create a revert commit for commit_sha on branch.
    If push=True (default) also pushes to origin in the same lock acquisition.
    """
    async with store.branch_lock(repo_name, branch, _caller(caller)):
        result = git_ops.git_revert(repo_name, branch, commit_sha, author_name, author_email)
        if push:
            push_result = git_ops.git_push(repo_name, branch)
            result = {**result, **push_result}
        await store.log_op("revert", repo_name, branch, _caller(caller), result)
        return result


@mcp.tool()
async def git_op_log(
    repo: Optional[str] = None,
    caller: Optional[str] = None,
    limit: int = 50,
) -> list:
    """Query the operation log. Filter by repo and/or caller. Returns most-recent first."""
    return await store.get_ops(repo=repo, caller=caller, limit=limit)


@mcp.tool()
async def git_lock_status(
    repo_name: str,
    branch: str,
) -> dict:
    """Return who holds the branch lock (or null if unlocked)."""
    holder = await store.get_lock_status(repo_name, branch)
    return {"repo": repo_name, "branch": branch, "locked_by": holder}


# ===========================================================================
# GITHUB TOOLS — PRs
# ===========================================================================

@mcp.tool()
async def github_list_prs(
    repo_name: str,
    state: str = "open",
) -> list:
    """List pull requests for a repo. state: open | closed | all."""
    return gh.list_prs(repo_name, state)


@mcp.tool()
async def github_get_pr(
    repo_name: str,
    pr_number: int,
) -> dict:
    """Get details for a specific pull request."""
    return gh.get_pr(repo_name, pr_number)


@mcp.tool()
async def github_get_pr_files(
    repo_name: str,
    pr_number: int,
) -> list:
    """List files changed in a pull request."""
    return gh.get_pr_files(repo_name, pr_number)


@mcp.tool()
async def github_get_pr_reviews(
    repo_name: str,
    pr_number: int,
) -> list:
    """List reviews on a pull request."""
    return gh.get_pr_reviews(repo_name, pr_number)


@mcp.tool()
async def github_create_pr(
    repo_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
    draft: bool = False,
    caller: str = "unknown",
) -> dict:
    """
    Open a pull request. head is the source branch, base is the target (default: main).
    Logs the operation to the op log.
    """
    result = gh.create_pr(repo_name, title, head, base, body, draft)
    await store.log_op("create_pr", repo_name, head, _caller(caller), result)
    return result


@mcp.tool()
async def github_comment_pr(
    repo_name: str,
    pr_number: int,
    body: str,
    caller: str = "unknown",
) -> dict:
    """Post a comment on a pull request."""
    result = gh.comment_pr(repo_name, pr_number, body)
    await store.log_op("comment_pr", repo_name, str(pr_number), _caller(caller), result)
    return result


@mcp.tool()
async def github_merge_pr(
    repo_name: str,
    pr_number: int,
    merge_method: str = "squash",
    commit_message: str = "",
    caller: str = "unknown",
) -> dict:
    """
    Merge a pull request. merge_method: merge | squash | rebase.
    Acquires the branch lock on the PR's base branch before merging.
    """
    pr = gh.get_pr(repo_name, pr_number)
    base_branch = pr["base"]
    async with store.branch_lock(repo_name, base_branch, _caller(caller)):
        result = gh.merge_pr(repo_name, pr_number, merge_method, commit_message)
        await store.log_op("merge_pr", repo_name, base_branch, _caller(caller), result)
        return result


# ===========================================================================
# GITHUB TOOLS — Repos
# ===========================================================================

@mcp.tool()
async def github_list_repos(repo_type: str = "all") -> list:
    """List repos in the default GitHub org. repo_type: all | public | private | forks | sources | member."""
    return gh.list_repos(repo_type)


@mcp.tool()
async def github_list_branches(repo_name: str) -> list:
    """List branches for a repo via the GitHub API (not the local cache)."""
    return gh.list_branches(repo_name)


# ===========================================================================
# GITHUB TOOLS — Dependabot / Vulnerabilities
# ===========================================================================

@mcp.tool()
async def github_list_vulnerabilities(
    state: str = "open",
    severity: Optional[str] = None,
    ecosystem: Optional[str] = None,
) -> list:
    """
    List Dependabot vulnerability alerts across the org.
    severity: critical | high | medium | low
    ecosystem: npm | pip | maven | rubygems | nuget | go | cargo | ...
    """
    return await gh.list_vulnerabilities(state, severity, ecosystem)


@mcp.tool()
async def github_list_repo_vulnerabilities(
    repo_name: str,
    state: str = "open",
    severity: Optional[str] = None,
) -> list:
    """List Dependabot alerts for a specific repo."""
    return await gh.list_repo_vulnerabilities(repo_name, state, severity)


@mcp.tool()
async def github_get_vulnerability(
    repo_name: str,
    alert_number: int,
) -> dict:
    """Get full details for a Dependabot alert including CVSS score, description, and fix PR."""
    return await gh.get_vulnerability(repo_name, alert_number)


@mcp.tool()
async def github_dismiss_vulnerability(
    repo_name: str,
    alert_number: int,
    reason: str,
    comment: str = "",
    caller: str = "unknown",
) -> dict:
    """
    Dismiss a Dependabot alert.
    reason: fix_started | inaccurate | no_bandwidth | not_used | tolerable_risk
    """
    result = await gh.dismiss_vulnerability(repo_name, alert_number, reason, comment)
    await store.log_op("dismiss_vulnerability", repo_name, str(alert_number), _caller(caller), result)
    return result


@mcp.tool()
async def github_vulnerability_stats() -> dict:
    """Return open vulnerability counts by severity, ecosystem, and top affected repos."""
    return await gh.get_vulnerability_stats()


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    log.info("git_steer_starting", host=HOST, port=PORT)
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
