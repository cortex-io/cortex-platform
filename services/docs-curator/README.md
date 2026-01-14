# Documentation Curator

Automated curation service for the Cortex documentation vault.

## Features

- **Triage**: Analyze new documents in `_inbox/` and suggest categorization
- **Health Check**: Scan for broken links, stale docs, orphaned pages
- **Enrich**: Add backlinks, update index, validate templates (planned)
- **Consolidate**: Identify and merge similar documents (planned)

## Trust Levels

| Level | Name | Permissions |
|-------|------|-------------|
| 0 | Observer | Read-only, generate reports |
| 1 | Suggester | Create PRs, no direct commits |
| 2 | Minor Editor | Direct commits to `_inbox/`, `_index.md`, tags |
| 3 | Full Editor | Direct commits anywhere except `meta/` |
| 4 | Self-Governing | Can modify curation rules in `meta/` |

**Current Default**: Level 1 (Suggester)

## Usage

### Triage Inbox Documents

```bash
docs-curator triage /path/to/cortex-docs
```

### Run Health Check

```bash
docs-curator health-check /path/to/cortex-docs
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Required |
| `GITHUB_REPO` | Repository (org/name) | `ry-ops/cortex-docs` |
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `VAULT_PATH` | Path to vault within repo | `vault` |
| `CURATION_MODE` | Mode: suggest \| auto-minor \| auto-full | `suggest` |
| `TRUST_LEVEL` | Trust level (0-4) | `1` |

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docs-curator
  namespace: cortex-system
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: curator
        image: 10.43.170.72:5000/docs-curator:latest
        env:
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: github-token
              key: token
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: langflow-global-vars
              key: ANTHROPIC_API_KEY
```

## Cron Schedule

Run triage weekly:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: docs-triage
  namespace: cortex-system
spec:
  schedule: "0 6 * * 1"  # Monday 6am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: curator
            image: 10.43.170.72:5000/docs-curator:latest
            args: ["triage", "/workspace/cortex-docs"]
```

## Development

```bash
# Install dependencies
cd services/docs-curator
pip install -e ".[dev]"

# Run locally
python -m docs_curator.curator triage ~/Projects/cortex-docs
```

## Architecture

```
Curator Service
    ↓
Clone cortex-docs repo
    ↓
Scan _inbox/
    ↓
For each document:
  ├─ Extract frontmatter
  ├─ Analyze with Claude
  └─ Generate recommendations
    ↓
Create Triage Report
    ↓
If trust_level >= 1:
  Create PR with suggestions
Else:
  Log report
```

## Future Enhancements

- Automatic backlink generation
- Semantic similarity detection for consolidation
- Obsidian plugin integration
- Chat interface for curation requests
- Auto-generation of component docs from cluster
