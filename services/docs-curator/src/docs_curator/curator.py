#!/usr/bin/env python3
"""
Documentation Curator

Watches cortex-docs repository and performs automated curation tasks:
- Triage new documents in _inbox/
- Enrich documents with backlinks and metadata
- Health check for broken links and stale docs
- Generate curation reports
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import re
from datetime import datetime, timedelta

from anthropic import Anthropic
from git import Repo
from github import Github

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("docs-curator")


class CuratorConfig:
    """Configuration from environment"""
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO", "ry-ops/cortex-docs")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.vault_path = os.getenv("VAULT_PATH", "vault")
        self.curation_mode = os.getenv("CURATION_MODE", "suggest")  # suggest | auto-minor | auto-full
        self.trust_level = int(os.getenv("TRUST_LEVEL", "1"))  # 0-4


class DocumentTriager:
    """Triages new documents in inbox"""

    def __init__(self, config: CuratorConfig, claude: Anthropic):
        self.config = config
        self.claude = claude

    def triage_document(self, doc_path: Path, content: str) -> Dict[str, Any]:
        """Analyze document and suggest categorization"""

        # Extract frontmatter if present
        frontmatter = self._extract_frontmatter(content)

        # Use Claude to analyze the document
        prompt = f"""Analyze this documentation file and provide curation recommendations.

Document Path: {doc_path}

Content:
{content[:2000]}  # First 2000 chars

Provide recommendations in this format:
1. Document Type: (component|runbook|decision|knowledge|other)
2. Suggested Folder: (architecture|components|operations|knowledge|projects)
3. Suggested Tags: (comma-separated list)
4. Key Entities: (services, namespaces, concepts mentioned)
5. Related Documents: (potential connections to existing docs)
6. Summary: (one sentence description)

Be concise and specific."""

        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        analysis = response.content[0].text

        return {
            "doc_path": str(doc_path),
            "frontmatter": frontmatter,
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter from markdown"""
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                return None
        return None


class DocumentEnricher:
    """Enriches documents with metadata and links"""

    def __init__(self, config: CuratorConfig):
        self.config = config

    def enrich_document(self, doc_path: Path, vault_root: Path) -> Dict[str, Any]:
        """Add backlinks, update index, validate template"""

        enrichments = {
            "backlinks_added": [],
            "index_updated": False,
            "template_valid": False,
            "suggested_tags": []
        }

        # TODO: Implement backlink discovery
        # TODO: Update _index.md
        # TODO: Validate against templates

        return enrichments


class HealthChecker:
    """Checks documentation health"""

    def __init__(self, config: CuratorConfig):
        self.config = config

    def check_health(self, vault_root: Path) -> Dict[str, Any]:
        """Scan for broken links, orphans, stale docs"""

        issues = {
            "broken_links": [],
            "orphaned_docs": [],
            "stale_docs": [],
            "validation_errors": []
        }

        # Scan all markdown files
        for md_file in vault_root.rglob("*.md"):
            if md_file.name.startswith("_"):
                continue  # Skip special files

            content = md_file.read_text()

            # Check for broken internal links
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            for link in links:
                target = vault_root / f"{link}.md"
                if not target.exists():
                    issues["broken_links"].append({
                        "source": str(md_file.relative_to(vault_root)),
                        "target": link
                    })

            # Check staleness
            modified_time = datetime.fromtimestamp(md_file.stat().st_mtime)
            age_days = (datetime.now() - modified_time).days

            # Get doc type from frontmatter
            frontmatter = self._extract_frontmatter(content)
            doc_type = frontmatter.get("type") if frontmatter else "unknown"

            stale_threshold = self._get_stale_threshold(doc_type)
            if age_days > stale_threshold:
                issues["stale_docs"].append({
                    "path": str(md_file.relative_to(vault_root)),
                    "age_days": age_days,
                    "type": doc_type
                })

        return issues

    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter"""
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                return None
        return None

    def _get_stale_threshold(self, doc_type: str) -> int:
        """Get staleness threshold in days by document type"""
        thresholds = {
            "component": 90,
            "runbook": 60,
            "decision": 180,
            "knowledge": 120
        }
        return thresholds.get(doc_type, 90)


class GitHubIntegration:
    """Manages GitHub interactions"""

    def __init__(self, config: CuratorConfig):
        self.config = config
        self.gh = Github(config.github_token)
        self.repo = self.gh.get_repo(config.github_repo)

    def create_suggestion_pr(self, title: str, body: str, branch_name: str, changes: List[Dict[str, str]]):
        """Create a PR with suggested changes"""

        # Create branch
        base_branch = self.repo.get_branch("main")
        self.repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=base_branch.commit.sha
        )

        # Apply changes
        for change in changes:
            path = change["path"]
            content = change["content"]
            message = change.get("message", f"Update {path}")

            try:
                # Try to get existing file
                file = self.repo.get_contents(path, ref=branch_name)
                self.repo.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=file.sha,
                    branch=branch_name
                )
            except:
                # File doesn't exist, create it
                self.repo.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch_name
                )

        # Create PR
        pr = self.repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base="main"
        )

        logger.info(f"Created PR #{pr.number}: {pr.html_url}")
        return pr


class DocumentCurator:
    """Main curator orchestrator"""

    def __init__(self):
        self.config = CuratorConfig()
        self.claude = Anthropic(api_key=self.config.anthropic_api_key)
        self.triager = DocumentTriager(self.config, self.claude)
        self.enricher = DocumentEnricher(self.config)
        self.health_checker = HealthChecker(self.config)
        self.github = GitHubIntegration(self.config)

    def run_triage(self, repo_path: Path):
        """Triage all documents in inbox"""
        inbox_path = repo_path / self.config.vault_path / "_inbox"

        if not inbox_path.exists():
            logger.warning(f"Inbox not found: {inbox_path}")
            return

        triage_results = []

        for doc_path in inbox_path.glob("*.md"):
            if doc_path.name.startswith("."):
                continue

            logger.info(f"Triaging: {doc_path.name}")
            content = doc_path.read_text()
            result = self.triager.triage_document(doc_path, content)
            triage_results.append(result)

        if triage_results:
            self._create_triage_report(triage_results)

    def run_health_check(self, repo_path: Path):
        """Run health check on vault"""
        vault_path = repo_path / self.config.vault_path

        logger.info("Running health check...")
        issues = self.health_checker.check_health(vault_path)

        self._create_health_report(issues)

    def _create_triage_report(self, results: List[Dict[str, Any]]):
        """Create triage report and PR"""

        report = f"""# Documentation Triage Report

Generated: {datetime.utcnow().isoformat()}

## Documents Analyzed: {len(results)}

"""
        for result in results:
            report += f"""### {Path(result['doc_path']).name}

{result['analysis']}

---

"""

        if self.config.trust_level >= 1:  # Can create PRs
            branch_name = f"curator/triage-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

            self.github.create_suggestion_pr(
                title="[Curator] Documentation Triage Suggestions",
                body=report,
                branch_name=branch_name,
                changes=[
                    {
                        "path": f"vault/_inbox/TRIAGE-REPORT-{datetime.utcnow().strftime('%Y%m%d')}.md",
                        "content": report,
                        "message": "Add triage report"
                    }
                ]
            )
        else:
            # Just log the report
            logger.info(f"Triage Report:\n{report}")

    def _create_health_report(self, issues: Dict[str, Any]):
        """Create health check report"""

        report = f"""# Documentation Health Report

Generated: {datetime.utcnow().isoformat()}

## Summary

- Broken Links: {len(issues['broken_links'])}
- Orphaned Documents: {len(issues['orphaned_docs'])}
- Stale Documents: {len(issues['stale_docs'])}
- Validation Errors: {len(issues['validation_errors'])}

"""

        if issues["broken_links"]:
            report += "\n## Broken Links\n\n"
            for link in issues["broken_links"]:
                report += f"- `{link['source']}` → `{link['target']}`\n"

        if issues["stale_docs"]:
            report += "\n## Stale Documents\n\n"
            for doc in issues["stale_docs"]:
                report += f"- `{doc['path']}` ({doc['age_days']} days old, type: {doc['type']})\n"

        logger.info(f"Health Report:\n{report}")


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: docs-curator <command> <repo-path>")
        print("Commands: triage, health-check, enrich")
        sys.exit(1)

    command = sys.argv[1]
    repo_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()

    curator = DocumentCurator()

    if command == "triage":
        curator.run_triage(repo_path)
    elif command == "health-check":
        curator.run_health_check(repo_path)
    elif command == "enrich":
        logger.info("Enrich command not yet implemented")
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
