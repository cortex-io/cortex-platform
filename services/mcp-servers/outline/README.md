# Outline MCP Server

Documentation wiki access for Cortex agents via Model Context Protocol.

## Overview

This MCP server exposes the Outline collaborative wiki at `docs.ry-ops.dev`, enabling agents to search, read, create, and update documentation. Outline serves as Cortex's living documentation intranet, containing strategic plans, network topology, operational runbooks, ADRs, and agent development guides.

## Features

- **Full-text search** - Search across all documentation with query strings
- **Document CRUD** - Create, read, update documentation programmatically
- **Collection management** - Browse and organize docs by collection
- **Agent-friendly** - Query docs via chat interface (e.g., "What's the network topology?")
- **Single source of truth** - Cortex knowledge accessible to all agents

## Tools

### Search Tools

#### `search_docs`
Search Outline documentation by query string.

**Parameters:**
- `query` (required): Search query string
- `limit` (optional): Maximum number of results (default: 10)

**Returns:**
- Document ID, title, URL, snippet, and last updated timestamp

**Example:**
```
search_docs(query="langflow deployment", limit=5)
```

#### `list_collections`
List all available collections in Outline.

**Returns:**
- Collection ID, name, description, URL, and document count

**Example:**
```
list_collections()
```

#### `list_documents_in_collection`
List all documents in a specific collection.

**Parameters:**
- `collection_id` (required): Collection ID

**Returns:**
- Document ID, title, URL, and last updated timestamp

**Example:**
```
list_documents_in_collection(collection_id="abc123")
```

### Document Tools

#### `get_document`
Get full content of a document by ID.

**Parameters:**
- `document_id` (required): Document ID

**Returns:**
- Full document: ID, title, markdown content, URL, timestamps, creator, collection ID

**Example:**
```
get_document(document_id="doc-123")
```

#### `create_document`
Create a new document in Outline.

**Parameters:**
- `title` (required): Document title
- `text` (required): Document content (markdown)
- `collection_id` (optional): Collection ID (creates in default if not specified)
- `publish` (optional): Whether to publish immediately (default: true)

**Returns:**
- Created document ID, URL, and title

**Example:**
```
create_document(
  title="K3s Cluster Architecture",
  text="# K3s Cluster\n\nOur cluster has 7 nodes...",
  collection_id="network-topology",
  publish=true
)
```

#### `update_document`
Update an existing document.

**Parameters:**
- `document_id` (required): Document ID to update
- `title` (optional): New title
- `text` (optional): New content (markdown)
- `publish` (optional): Whether to publish

**Returns:**
- Success status, document ID, URL, and updated timestamp

**Example:**
```
update_document(
  document_id="doc-123",
  text="# Updated Content\n\nNew information...",
  publish=true
)
```

## Planned Collections

The following collection structure will be created in Outline:

1. **Strategic Plans** - Roadmaps, objectives, long-term vision
2. **Network Topology** - Infrastructure diagrams, node maps, architecture
3. **Operational Runbooks** - SOPs, incident response, deployment guides
4. **ADRs (Architectural Decision Records)** - Design decisions and rationale
5. **Agent Development Guide** - MCP server development, agent coordination

## Configuration

The server expects the following environment variables:

- `OUTLINE_API_TOKEN` (required): Outline API token for authentication
- `OUTLINE_BASE_URL` (optional): Outline base URL (default: `http://outline.cortex-knowledge.svc.cluster.local:3000`)
- `OUTLINE_TIMEOUT` (optional): HTTP timeout in seconds (default: 30)

## Deployment

### Kubernetes (via cortex-gitops)

The server is deployed to the `cortex-system` namespace and integrated into the cortex-mcp-server MOE router:

```yaml
# apps/cortex-system/outline-mcp-server-deployment.yaml
```

### Local Development

```bash
cd ~/Projects/cortex-platform/services/mcp-servers/outline

# Install dependencies
pip install -e .

# Set environment variables
export OUTLINE_API_TOKEN="your-token-here"
export OUTLINE_BASE_URL="https://docs.ry-ops.dev"

# Run server
outline-mcp
```

## Usage Examples

### Agent Query Flow

1. Agent asks: "What's the deployment process for Langflow?"
2. cortex-mcp-server MOE routes to outline-mcp-server
3. outline-mcp-server calls `search_docs(query="langflow deployment")`
4. Returns relevant runbook from Operational Runbooks collection
5. Agent synthesizes answer from documentation

### Creating Documentation

Agents can create documentation as they work:

```
Agent: "I just deployed a new service. Let me document it."

create_document(
  title="Phoenix Observability Dashboard - Deployment Notes",
  text="# Phoenix Dashboard\n\nDeployed on 2026-01-12 to cortex-knowledge namespace...",
  collection_id="operational-runbooks"
)
```

## Integration

The outline-mcp-server is registered with the cortex-mcp-server MOE router, enabling automatic routing based on query intent:

- Queries about docs, documentation, runbooks → outline-mcp-server
- Queries about infrastructure, k8s, deployments → kubernetes-mcp-server
- Queries about security, vulnerabilities → github-security-mcp-server

## Architecture

```
┌─────────────────────────────────┐
│   Agent (via cortex-mcp-server) │
└────────────┬────────────────────┘
             │ MCP Protocol
             ▼
┌─────────────────────────────────┐
│     outline-mcp-server          │
│   (cortex-system namespace)     │
└────────────┬────────────────────┘
             │ HTTP API
             ▼
┌─────────────────────────────────┐
│          Outline Wiki           │
│  (cortex-knowledge namespace)   │
│   docs.ry-ops.dev               │
└─────────────────────────────────┘
```

## Benefits

- **Self-documenting system** - Agents can query and update docs as they work
- **Knowledge persistence** - Operational knowledge survives across sessions
- **Agent collaboration** - Multiple agents can contribute to shared knowledge base
- **Human-readable** - Docs are accessible to both agents and humans via web UI
- **Audit trail** - All doc changes tracked in Outline's version history

## Next Steps

1. Create initial collection structure in Outline web UI
2. Migrate existing documentation (e.g., CLAUDE.md, network diagrams) into Outline
3. Train agents to query docs before performing operations
4. Enable agents to create runbooks as they complete tasks
5. Integrate with alerting (e.g., "Check runbook for this alert")
