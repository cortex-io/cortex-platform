"""
Git operations using GitPython.

All write operations (commit, push, revert) go through the branch lock in the
caller (server.py) — this module is purely mechanical.

Repos are cloned to a persistent local cache under GIT_STEER_CACHE_DIR
(default: ~/.git-steer/repos). On k3s this will be an emptyDir or PVC.
Subsequent calls do a fetch+checkout rather than a full re-clone.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional

import structlog
from git import Repo, GitCommandError, InvalidGitRepositoryError

log = structlog.get_logger()

CACHE_DIR = Path(os.getenv("GIT_STEER_CACHE_DIR", Path.home() / ".git-steer" / "repos"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def _cache_path(repo_name: str) -> Path:
    """Local path for a cached repo clone. repo_name is 'owner/repo'."""
    safe = repo_name.replace("/", "__")
    return CACHE_DIR / safe


def _auth_url(repo_name: str) -> str:
    """HTTPS clone URL with embedded token."""
    if "/" not in repo_name:
        raise ValueError(f"repo_name must be 'owner/repo', got: {repo_name!r}")
    token = GITHUB_TOKEN
    if token:
        return f"https://x-access-token:{token}@github.com/{repo_name}.git"
    return f"https://github.com/{repo_name}.git"


def _get_repo(repo_name: str, branch: str = "main") -> Repo:
    """
    Return a GitPython Repo object for repo_name, cloning or fetching as needed.
    Always checks out the requested branch at HEAD after fetching.
    """
    path = _cache_path(repo_name)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            repo = Repo(path)
            # Update remote URL (token may have rotated)
            repo.remotes.origin.set_url(_auth_url(repo_name))
            repo.remotes.origin.fetch()
            # Checkout + reset to remote HEAD
            repo.git.checkout(branch)
            repo.git.reset("--hard", f"origin/{branch}")
            log.info("git_fetch_ok", repo=repo_name, branch=branch)
            return repo
        except (InvalidGitRepositoryError, GitCommandError) as e:
            log.warning("git_repo_corrupt_recloning", repo=repo_name, error=str(e))
            shutil.rmtree(path)

    log.info("git_clone", repo=repo_name, branch=branch)
    repo = Repo.clone_from(
        _auth_url(repo_name),
        path,
        branch=branch,
        depth=None,  # full clone so revert has history
    )
    return repo


def _configure_author(repo: Repo, name: str, email: str):
    with repo.config_writer() as cw:
        cw.set_value("user", "name", name)
        cw.set_value("user", "email", email)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def git_status(repo_name: str, branch: str = "main") -> dict:
    repo = _get_repo(repo_name, branch)
    return {
        "repo": repo_name,
        "branch": repo.active_branch.name,
        "head_commit": repo.head.commit.hexsha,
        "head_message": repo.head.commit.message.strip(),
        "is_dirty": repo.is_dirty(untracked_files=True),
        "staged": [item.a_path for item in repo.index.diff("HEAD")],
        "unstaged": [item.a_path for item in repo.index.diff(None)],
        "untracked": repo.untracked_files,
    }


def git_log(repo_name: str, branch: str = "main", limit: int = 20) -> list[dict]:
    repo = _get_repo(repo_name, branch)
    return [
        {
            "sha": c.hexsha,
            "short_sha": c.hexsha[:8],
            "author": f"{c.author.name} <{c.author.email}>",
            "date": c.authored_datetime.isoformat(),
            "message": c.message.strip(),
        }
        for c in repo.iter_commits(branch, max_count=limit)
    ]


def git_diff(repo_name: str, branch: str = "main", ref: Optional[str] = None) -> str:
    repo = _get_repo(repo_name, branch)
    if ref:
        return repo.git.diff(ref)
    return repo.git.diff("HEAD")


def git_create_branch(repo_name: str, branch: str, from_branch: str = "main") -> dict:
    repo = _get_repo(repo_name, from_branch)
    if branch in [b.name for b in repo.branches]:
        # Branch exists — just check it out
        repo.git.checkout(branch)
        return {"repo": repo_name, "branch": branch, "created": False}
    repo.git.checkout("-b", branch)
    log.info("git_branch_created", repo=repo_name, branch=branch)
    return {"repo": repo_name, "branch": branch, "created": True, "from": from_branch}


def git_commit(
    repo_name: str,
    branch: str,
    message: str,
    files: Optional[list[str]] = None,
    author_name: str = "Cortex",
    author_email: str = "cortex@cortex.ai",
) -> dict:
    """
    Stage files (or all changes) and create a commit.
    Returns the new commit SHA or raises on failure.
    """
    repo = _get_repo(repo_name, branch)
    _configure_author(repo, author_name, author_email)

    if files:
        repo.index.add(files)
    else:
        # Add everything tracked + modified; don't accidentally add secrets
        repo.git.add("-u")

    if not repo.index.diff("HEAD") and not repo.untracked_files:
        return {"repo": repo_name, "branch": branch, "status": "nothing_to_commit"}

    commit = repo.index.commit(message)
    log.info("git_committed", repo=repo_name, branch=branch, sha=commit.hexsha)
    return {
        "repo": repo_name,
        "branch": branch,
        "sha": commit.hexsha,
        "short_sha": commit.hexsha[:8],
        "message": message,
    }


def git_push(
    repo_name: str,
    branch: str,
    force: bool = False,
) -> dict:
    repo = _get_repo(repo_name, branch)
    repo.remotes.origin.set_url(_auth_url(repo_name))
    push_args = [repo.remotes.origin, branch]
    if force:
        push_infos = repo.remotes.origin.push(refspec=f"{branch}:{branch}", force=True)
    else:
        push_infos = repo.remotes.origin.push(refspec=f"{branch}:{branch}")

    for info in push_infos:
        if info.flags & info.ERROR:
            raise GitCommandError("push", info.summary)

    log.info("git_pushed", repo=repo_name, branch=branch)
    return {"repo": repo_name, "branch": branch, "pushed": True}


def git_revert(
    repo_name: str,
    branch: str,
    commit_sha: str,
    author_name: str = "Cortex",
    author_email: str = "cortex@cortex.ai",
) -> dict:
    """
    Create a revert commit for commit_sha and return the new commit hash.
    Does NOT push — caller must call git_push after.
    """
    repo = _get_repo(repo_name, branch)
    _configure_author(repo, author_name, author_email)
    repo.git.revert("--no-edit", commit_sha)
    new_sha = repo.head.commit.hexsha
    log.info("git_reverted", repo=repo_name, branch=branch, reverted=commit_sha, new_sha=new_sha)
    return {
        "repo": repo_name,
        "branch": branch,
        "reverted_commit": commit_sha,
        "revert_commit": new_sha,
        "short_sha": new_sha[:8],
    }


def list_branches(repo_name: str) -> list[str]:
    repo = _get_repo(repo_name)
    return [b.name for b in repo.branches]
