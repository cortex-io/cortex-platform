#!/usr/bin/env python3
"""
Documentation Curator

Watches cortex-docs repository and performs automated curation tasks:
- Triage new documents in _inbox/
- Enrich documents with backlinks and metadata
- Health check for broken links and stale docs
- Generate curation reports
"""

import hashlib
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import re
from datetime import datetime, timedelta

import redis
from anthropic import Anthropic
from git import Repo
from github import Github

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, ScoredPoint
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("docs-curator")


DOCS_QDRANT_COLLECTION = "cortex-docs"
DOCS_VECTOR_DIM = 1536


class CuratorConfig:
    """Configuration from environment"""
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO", "cortex-io/cortex-docs")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.vault_path = os.getenv("VAULT_PATH", "vault")
        self.curation_mode = os.getenv("CURATION_MODE", "suggest")  # suggest | auto-minor | auto-full
        self.trust_level = int(os.getenv("TRUST_LEVEL", "1"))  # 0-4
        self.redis_host = os.getenv("REDIS_HOST", "redis-queue")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.qdrant_host = os.getenv("QDRANT_HOST", "qdrant.cortex-ai-infra.svc.cluster.local")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.duplicate_threshold = float(os.getenv("DUPLICATE_THRESHOLD", "0.92"))


def _redis_connect(config: CuratorConfig) -> Optional[redis.Redis]:
    """Connect to Redis; return None if unavailable."""
    try:
        r = redis.Redis(host=config.redis_host, port=config.redis_port, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return None


def _qdrant_connect(config: CuratorConfig) -> Optional["QdrantClient"]:
    """Connect to Qdrant; return None if unavailable."""
    if not QDRANT_AVAILABLE:
        return None
    try:
        qc = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
        collections = {c.name for c in qc.get_collections().collections}
        if DOCS_QDRANT_COLLECTION not in collections:
            qc.create_collection(
                collection_name=DOCS_QDRANT_COLLECTION,
                vectors_config=VectorParams(size=DOCS_VECTOR_DIM, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {DOCS_QDRANT_COLLECTION}")
        return qc
    except Exception as e:
        logger.warning(f"Qdrant unavailable: {e}")
        return None


def _embed_text(text: str, api_key: str) -> Optional[List[float]]:
    """Generate embedding via OpenAI API."""
    if not api_key:
        return None
    try:
        import urllib.request, json as _json
        data = _json.dumps({"input": text[:8000], "model": "text-embedding-3-small"}).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=data,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read())["data"][0]["embedding"]
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None


class DocumentTriager:
    """Triages new documents in inbox"""

    def __init__(self, config: CuratorConfig, claude: Anthropic,
                 redis_client=None, qdrant_client=None):
        self.config = config
        self.claude = claude
        self._redis = redis_client
        self._qdrant = qdrant_client

    def _doc_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def is_already_processed(self, doc_path: Path, content: str) -> bool:
        """Return True if this doc (by path+content hash) was already triaged."""
        if not self._redis:
            return False
        key = f"curator:processed:{doc_path.name}:{self._doc_hash(content)}"
        return bool(self._redis.exists(key))

    def mark_processed(self, doc_path: Path, content: str):
        """Record that this doc has been triaged (TTL 30 days)."""
        if not self._redis:
            return
        key = f"curator:processed:{doc_path.name}:{self._doc_hash(content)}"
        self._redis.setex(key, 60 * 60 * 24 * 30, "1")

    def find_semantic_duplicates(self, content: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search Qdrant for existing docs semantically similar to this one."""
        if not self._qdrant or not self.config.openai_api_key:
            return []
        vector = _embed_text(content[:3000], self.config.openai_api_key)
        if not vector:
            return []
        try:
            results = self._qdrant.search(
                collection_name=DOCS_QDRANT_COLLECTION,
                query_vector=vector,
                limit=limit,
                with_payload=True,
            )
            return [
                {"score": r.score, "path": r.payload.get("path", ""), "title": r.payload.get("title", "")}
                for r in results
                if r.score >= self.config.duplicate_threshold
            ]
        except Exception as e:
            logger.warning(f"Qdrant duplicate search failed: {e}")
            return []

    def index_document(self, doc_path: Path, content: str):
        """Embed and index a document in Qdrant after successful triage."""
        if not self._qdrant or not self.config.openai_api_key:
            return
        vector = _embed_text(content[:3000], self.config.openai_api_key)
        if not vector:
            return
        try:
            point_id = int(hashlib.md5(str(doc_path).encode()).hexdigest(), 16) % (2**63)
            self._qdrant.upsert(
                collection_name=DOCS_QDRANT_COLLECTION,
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"path": str(doc_path), "title": doc_path.stem},
                )],
            )
        except Exception as e:
            logger.warning(f"Failed to index doc in Qdrant: {e}")

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

        # Check for semantic duplicates in Qdrant
        duplicates = self.find_semantic_duplicates(content)

        return {
            "doc_path": str(doc_path),
            "frontmatter": frontmatter,
            "analysis": analysis,
            "semantic_duplicates": duplicates,
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
        self._redis = _redis_connect(self.config)
        self._qdrant = _qdrant_connect(self.config)
        self.triager = DocumentTriager(self.config, self.claude,
                                       redis_client=self._redis,
                                       qdrant_client=self._qdrant)
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

            content = doc_path.read_text()

            # Skip docs already processed (Redis deduplication)
            if self.triager.is_already_processed(doc_path, content):
                logger.info(f"Skipping already-processed: {doc_path.name}")
                continue

            logger.info(f"Triaging: {doc_path.name}")
            result = self.triager.triage_document(doc_path, content)
            triage_results.append(result)

            # Mark processed in Redis and index in Qdrant
            self.triager.mark_processed(doc_path, content)
            self.triager.index_document(doc_path, content)

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
