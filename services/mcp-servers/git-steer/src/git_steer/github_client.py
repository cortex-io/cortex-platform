"""
GitHub client — wraps PyGithub for repo/PR ops and httpx for Dependabot API.
"""

import os
from typing import Optional

import httpx
import structlog
from github import Github, GithubException
from github.Repository import Repository

log = structlog.get_logger()


class GitHubClient:
    def __init__(self, token: Optional[str] = None, org: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.org = org or os.getenv("GITHUB_ORG", "cortex-io")
        self._gh = Github(self.token) if self.token else None
        self._http = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            base_url="https://api.github.com",
            timeout=30,
        )

    async def close(self):
        await self._http.aclose()

    def _repo(self, repo_name: str) -> Repository:
        """Return a PyGithub Repository object. repo_name may be 'owner/repo' or just 'repo'."""
        if "/" not in repo_name:
            repo_name = f"{self.org}/{repo_name}"
        return self._gh.get_repo(repo_name)

    # -------------------------------------------------------------------------
    # PR operations
    # -------------------------------------------------------------------------

    def list_prs(self, repo_name: str, state: str = "open") -> list[dict]:
        repo = self._repo(repo_name)
        return [
            {
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "author": pr.user.login,
                "base": pr.base.ref,
                "head": pr.head.ref,
                "url": pr.html_url,
                "created_at": pr.created_at.isoformat(),
                "draft": pr.draft,
            }
            for pr in repo.get_pulls(state=state)
        ]

    def get_pr(self, repo_name: str, pr_number: int) -> dict:
        repo = self._repo(repo_name)
        pr = repo.get_pull(pr_number)
        return {
            "number": pr.number,
            "title": pr.title,
            "state": pr.state,
            "author": pr.user.login,
            "base": pr.base.ref,
            "head": pr.head.ref,
            "url": pr.html_url,
            "body": pr.body or "",
            "mergeable": pr.mergeable,
            "mergeable_state": pr.mergeable_state,
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "draft": pr.draft,
        }

    def get_pr_files(self, repo_name: str, pr_number: int) -> list[dict]:
        repo = self._repo(repo_name)
        pr = repo.get_pull(pr_number)
        return [
            {
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
            }
            for f in pr.get_files()
        ]

    def get_pr_reviews(self, repo_name: str, pr_number: int) -> list[dict]:
        repo = self._repo(repo_name)
        pr = repo.get_pull(pr_number)
        return [
            {
                "id": r.id,
                "author": r.user.login,
                "state": r.state,
                "body": r.body or "",
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in pr.get_reviews()
        ]

    def create_pr(
        self,
        repo_name: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False,
    ) -> dict:
        repo = self._repo(repo_name)
        pr = repo.create_pull(title=title, body=body, head=head, base=base, draft=draft)
        return {
            "number": pr.number,
            "url": pr.html_url,
            "state": pr.state,
        }

    def comment_pr(self, repo_name: str, pr_number: int, body: str) -> dict:
        repo = self._repo(repo_name)
        pr = repo.get_pull(pr_number)
        comment = pr.create_issue_comment(body)
        return {"comment_id": comment.id, "url": comment.html_url}

    def merge_pr(
        self,
        repo_name: str,
        pr_number: int,
        merge_method: str = "squash",
        commit_message: str = "",
    ) -> dict:
        repo = self._repo(repo_name)
        pr = repo.get_pull(pr_number)
        result = pr.merge(merge_method=merge_method, commit_message=commit_message or pr.title)
        return {"merged": result.merged, "sha": result.sha, "message": result.message}

    # -------------------------------------------------------------------------
    # Repository operations
    # -------------------------------------------------------------------------

    def list_repos(self, repo_type: str = "all") -> list[dict]:
        org = self._gh.get_organization(self.org)
        return [
            {
                "name": r.name,
                "full_name": r.full_name,
                "private": r.private,
                "language": r.language,
                "default_branch": r.default_branch,
                "url": r.html_url,
            }
            for r in org.get_repos(type=repo_type)
        ]

    def list_branches(self, repo_name: str) -> list[str]:
        repo = self._repo(repo_name)
        return [b.name for b in repo.get_branches()]

    # -------------------------------------------------------------------------
    # Dependabot / vulnerability operations (httpx — REST-only endpoint)
    # -------------------------------------------------------------------------

    async def _dependabot_get(self, endpoint: str, params: Optional[dict] = None) -> list | dict:
        r = await self._http.get(endpoint, params=params)
        r.raise_for_status()
        return r.json()

    async def _dependabot_patch(self, endpoint: str, data: dict) -> dict:
        r = await self._http.patch(endpoint, json=data)
        r.raise_for_status()
        return r.json()

    async def list_vulnerabilities(
        self,
        state: str = "open",
        severity: Optional[str] = None,
        ecosystem: Optional[str] = None,
    ) -> list[dict]:
        params: dict = {"state": state, "per_page": 100}
        if severity:
            params["severity"] = severity
        if ecosystem:
            params["ecosystem"] = ecosystem
        alerts = await self._dependabot_get(
            f"/orgs/{self.org}/dependabot/alerts", params=params
        )
        return _format_vuln_list(alerts)

    async def list_repo_vulnerabilities(
        self,
        repo_name: str,
        state: str = "open",
        severity: Optional[str] = None,
    ) -> list[dict]:
        if "/" not in repo_name:
            repo_name = f"{self.org}/{repo_name}"
        params: dict = {"state": state, "per_page": 100}
        if severity:
            params["severity"] = severity
        alerts = await self._dependabot_get(
            f"/repos/{repo_name}/dependabot/alerts", params=params
        )
        return _format_vuln_list(alerts)

    async def get_vulnerability(self, repo_name: str, alert_number: int) -> dict:
        if "/" not in repo_name:
            repo_name = f"{self.org}/{repo_name}"
        alert = await self._dependabot_get(
            f"/repos/{repo_name}/dependabot/alerts/{alert_number}"
        )
        return _format_vuln_detail(alert)

    async def dismiss_vulnerability(
        self,
        repo_name: str,
        alert_number: int,
        reason: str,
        comment: str = "",
    ) -> dict:
        if "/" not in repo_name:
            repo_name = f"{self.org}/{repo_name}"
        result = await self._dependabot_patch(
            f"/repos/{repo_name}/dependabot/alerts/{alert_number}",
            {"state": "dismissed", "dismissed_reason": reason, "dismissed_comment": comment},
        )
        return {
            "alert_number": alert_number,
            "state": result.get("state"),
            "dismissed_at": result.get("dismissed_at"),
            "dismissed_by": result.get("dismissed_by", {}).get("login"),
        }

    async def get_vulnerability_stats(self) -> dict:
        alerts = await self._dependabot_get(
            f"/orgs/{self.org}/dependabot/alerts",
            params={"state": "open", "per_page": 100},
        )
        by_severity: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_ecosystem: dict[str, int] = {}
        by_repo: dict[str, int] = {}
        for a in alerts:
            sev = a.get("security_advisory", {}).get("severity", "unknown").lower()
            if sev in by_severity:
                by_severity[sev] += 1
            eco = a.get("security_vulnerability", {}).get("package", {}).get("ecosystem", "unknown")
            by_ecosystem[eco] = by_ecosystem.get(eco, 0) + 1
            repo = a.get("repository", {}).get("name", "unknown")
            by_repo[repo] = by_repo.get(repo, 0) + 1
        return {
            "total": len(alerts),
            "by_severity": by_severity,
            "by_ecosystem": by_ecosystem,
            "top_repos": sorted(by_repo.items(), key=lambda x: x[1], reverse=True)[:10],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_vuln_list(alerts: list) -> list[dict]:
    out = []
    for a in alerts:
        adv = a.get("security_advisory", {})
        vuln = a.get("security_vulnerability", {})
        out.append({
            "number": a.get("number"),
            "state": a.get("state"),
            "severity": adv.get("severity", "unknown"),
            "cve_id": adv.get("cve_id"),
            "ghsa_id": adv.get("ghsa_id"),
            "summary": adv.get("summary", ""),
            "package": vuln.get("package", {}).get("name"),
            "ecosystem": vuln.get("package", {}).get("ecosystem"),
            "vulnerable_range": vuln.get("vulnerable_version_range"),
            "patched_version": vuln.get("first_patched_version", {}).get("identifier"),
            "repo": a.get("repository", {}).get("name"),
            "manifest_path": a.get("dependency", {}).get("manifest_path"),
            "created_at": a.get("created_at"),
        })
    return out


def _format_vuln_detail(a: dict) -> dict:
    adv = a.get("security_advisory", {})
    vuln = a.get("security_vulnerability", {})
    dep = a.get("dependency", {})
    fix_pr = a.get("fix", {}).get("pull_request", {})
    return {
        "number": a.get("number"),
        "state": a.get("state"),
        "severity": adv.get("severity"),
        "cvss_score": adv.get("cvss", {}).get("score"),
        "cve_id": adv.get("cve_id"),
        "ghsa_id": adv.get("ghsa_id"),
        "summary": adv.get("summary", ""),
        "description": adv.get("description", ""),
        "references": adv.get("references", []),
        "package": dep.get("package", {}).get("name"),
        "ecosystem": dep.get("package", {}).get("ecosystem"),
        "manifest_path": dep.get("manifest_path"),
        "vulnerable_range": vuln.get("vulnerable_version_range"),
        "patched_version": vuln.get("first_patched_version", {}).get("identifier"),
        "fix_pr_url": fix_pr.get("html_url"),
        "fix_pr_number": fix_pr.get("number"),
        "fix_pr_state": fix_pr.get("state"),
        "created_at": a.get("created_at"),
        "updated_at": a.get("updated_at"),
    }
