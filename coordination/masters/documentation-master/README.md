# Documentation Master

**A living, evolving documentation knowledge system for Cortex Holdings**

## Overview

The Documentation Master is a revolutionary Cortex master that treats documentation as a first-class, continuously evolving knowledge system. Instead of static reference material, documentation becomes an intelligent asset that learns, adapts, and improves based on actual usage patterns through MoE (Mixture of Experts) integration.

## Key Features

- **Intelligent Crawling**: Respects robots.txt, implements rate limiting, and schedules crawls based on priority
- **Smart Indexing**: Extracts headers, code blocks, keywords, and creates searchable metadata
- **MoE Learning**: Integrates with Cortex's MoE system to track documentation usage and optimize coverage
- **Query Service**: Provides documentation-as-a-service to other masters and MCP servers
- **Resource Management**: Comprehensive guardrails for storage, tokens, and API limits
- **Knowledge Evolution**: Automatically detects knowledge gaps and updates documentation priorities

## Architecture

```
documentation-master/
├── master.sh                      # Main orchestration script
├── lib/
│   ├── crawler.sh                 # Documentation crawling engine
│   ├── indexer.sh                 # Content indexing and search
│   ├── query-handler.sh           # Query API server
│   └── learner.sh                 # MoE learning integration
├── config/
│   ├── sources.json               # Documentation source registry
│   ├── crawl-policy.json          # Crawl scheduling and policies
│   ├── resource-limits.json       # Storage, token, and rate limits
│   └── learning-policy.json       # MoE learning configuration
├── knowledge-base/
│   ├── sandfly/                   # Sandfly-specific indexed content
│   ├── proxmox/                   # Future: Proxmox docs
│   ├── k3s/                       # Future: K3s docs
│   └── cross-domain/              # Cross-domain patterns
├── cache/
│   ├── indexed-content/           # Cached documentation with indexes
│   ├── embeddings/                # Future: Vector embeddings
│   └── metadata/                  # Version tracking, last-updated
└── workers/
    ├── crawler-worker.sh          # Spawnable crawl workers
    ├── indexer-worker.sh          # Spawnable index workers
    └── learner-worker.sh          # Spawnable learning workers
```

## Quick Start

### 1. Local Testing

```bash
# Start the Documentation Master
./master.sh start

# Check status
./master.sh status

# Manually trigger a crawl
./master.sh crawl schedule sandfly

# Query documentation
./master.sh query sandfly "alerts API"

# Stop the master
./master.sh stop
```

### 2. Kubernetes Deployment

```bash
# Create namespace (if not exists)
kubectl create namespace cortex

# Deploy persistent volumes
kubectl apply -f /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-governance/documentation-master-pvc.yaml

# Deploy configuration
kubectl apply -f /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-governance/documentation-master-configmap.yaml

# Deploy service
kubectl apply -f /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-governance/documentation-master-service.yaml

# Deploy master
kubectl apply -f /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-governance/documentation-master-deployment.yaml

# Deploy scheduled crawler
kubectl apply -f /Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-governance/documentation-master-cronjob.yaml

# Check deployment
kubectl get pods -n cortex -l app=documentation-master
kubectl logs -n cortex -l app=documentation-master --tail=100
```

## Configuration

### Sources Configuration

Edit `config/sources.json` to add new documentation sources:

```json
{
  "sandfly": {
    "enabled": true,
    "priority": "high",
    "sources": [
      {
        "url": "https://docs.sandflysecurity.com",
        "type": "documentation",
        "crawl_depth": 5,
        "update_frequency": "daily"
      }
    ]
  }
}
```

### Resource Limits

Configure in `config/resource-limits.json`:

- **Storage**: Max cache size, per-domain limits, pruning thresholds
- **Rate Limiting**: Requests per minute, concurrent crawls, timeouts
- **Token Budget**: Max tokens per crawl/query, daily budgets

### Crawl Policy

Control crawl behavior in `config/crawl-policy.json`:

- **Scheduled Updates**: High/medium/low priority frequencies
- **Triggered Updates**: Knowledge gaps, API changes, task failures
- **Scope Boundaries**: Allowed domains, blocked patterns, max depth

### Learning Policy

Configure MoE integration in `config/learning-policy.json`:

- **MoE Integration**: Router/learner endpoints, confidence thresholds
- **Priority Scoring**: Usage frequency, success rate, recency weights
- **Pruning Policy**: Min value scores, evaluation windows
- **Pattern Detection**: Common queries, knowledge gaps, outdated content

## Usage Examples

### Querying Documentation (CLI)

```bash
# Query Sandfly documentation for alerts
./lib/query-handler.sh query sandfly "alerts API" summary 5000

# Get detailed response
./lib/query-handler.sh query sandfly "forensics" detailed 10000
```

### Querying Documentation (HTTP API)

```bash
# POST to query endpoint
curl -X POST http://documentation-master.cortex.svc.cluster.local:8080/query \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "sandfly",
    "topic": "alerts API",
    "format": "summary",
    "maxTokens": 5000
  }'
```

Response:
```json
{
  "domain": "sandfly",
  "topic": "alerts API",
  "results": [
    {
      "url": "https://docs.sandflysecurity.com/api/alerts",
      "preview": "The Alerts API allows you to retrieve and manage security alerts...",
      "content": "Full content here...",
      "relevance": 15
    }
  ],
  "confidence": 0.85,
  "result_count": 3,
  "format": "summary",
  "timestamp": "2025-12-27T10:00:00Z",
  "documentation_used": [
    "https://docs.sandflysecurity.com/api/alerts",
    "https://docs.sandflysecurity.com/concepts/alerts"
  ]
}
```

### Manual Crawling

```bash
# Crawl specific URL
./lib/crawler.sh url "https://docs.sandflysecurity.com" sandfly 3

# Schedule crawl for all sources
./lib/crawler.sh schedule sandfly
```

### Indexing

```bash
# Index all content for a domain
./lib/indexer.sh index sandfly

# Search indexed content
./lib/indexer.sh search sandfly "alerts" 10

# Update master index
./lib/indexer.sh update-master sandfly
```

### MoE Learning Integration

```bash
# Register with MoE system
./lib/learner.sh register

# Track an outcome
./lib/learner.sh track "outcome-001" "task-123" "sandfly" "alerts" true 0.87

# Analyze patterns
./lib/learner.sh analyze sandfly

# Start monitoring loop
./lib/learner.sh monitor
```

## Integration with Other Systems

### From MCP Servers

MCP servers can query the Documentation Master for context:

```typescript
// Query Documentation Master
const response = await fetch('http://documentation-master:8080/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    domain: 'sandfly',
    topic: 'get_alerts',
    format: 'summary',
    maxTokens: 5000
  })
});

const docContext = await response.json();

// Enrich MCP tool responses with documentation
return {
  apiResult: sandflyApiResponse,
  documentation: docContext,
  confidence: docContext.confidence
};
```

### From Other Masters

```bash
# Coordinator Master querying for Sandfly documentation
curl -X POST http://documentation-master.cortex.svc.cluster.local:8080/query \
  -H "Content-Type: application/json" \
  -d '{"domain":"sandfly","topic":"threat detection","format":"summary"}'
```

## MoE Learning Flow

1. **Query Received**: Documentation Master receives query from MCP/master
2. **Documentation Retrieved**: Searches index and returns relevant content
3. **Outcome Tracked**: Success/failure and confidence recorded
4. **Patterns Analyzed**: Aggregates outcomes to identify trends
5. **Priorities Updated**: High-value documentation gets higher priority
6. **Crawl Scheduled**: Knowledge gaps trigger targeted re-crawls
7. **Index Refreshed**: Updated content improves future queries

## Monitoring

### Health Checks

```bash
# Local
curl http://localhost:8080/health

# Kubernetes
kubectl exec -it -n cortex deployment/documentation-master -- curl localhost:8080/health
```

### Logs

```bash
# View logs
tail -f cache/master.log

# Kubernetes logs
kubectl logs -n cortex -l app=documentation-master -f
```

### Metrics (Future)

- Total documents indexed
- Queries per second
- Cache hit rate
- Average confidence scores
- Knowledge gap detections

## Roadmap

### Phase 1 (Current - COMPLETE)
- ✅ Core infrastructure (master, crawler, indexer, query-handler)
- ✅ Configuration system (sources, limits, policies)
- ✅ Worker system (parallel processing)
- ✅ MoE learning integration
- ✅ Kubernetes deployment manifests

### Phase 2 (Next)
- [ ] Sandfly MCP Server integration
- [ ] End-to-end testing with real Sandfly docs
- [ ] Performance optimization
- [ ] Vector embeddings for semantic search
- [ ] Enhanced knowledge graph

### Phase 3 (Future)
- [ ] Proxmox documentation integration
- [ ] K3s/Kubernetes documentation integration
- [ ] Multi-language support
- [ ] Video/multimedia content indexing
- [ ] Community forum integration

## Troubleshooting

### Common Issues

**Issue**: Crawler fails with rate limiting errors
**Solution**: Adjust `requests_per_minute` in `config/resource-limits.json`

**Issue**: Index search returns no results
**Solution**: Run `./lib/indexer.sh index <domain>` to rebuild index

**Issue**: MoE integration not working
**Solution**: Check `MOE_ENABLED=true` and MoE endpoint connectivity

**Issue**: Out of disk space
**Solution**: Run pruning or increase PVC size in K8s manifest

## Contributing

This is a foundational pattern for all Cortex external integrations. Improvements here benefit all future integrations:

1. Test thoroughly with Sandfly integration
2. Document learnings and patterns
3. Optimize based on real usage
4. Prepare to replicate for next integration

## License

Part of Cortex Holdings coordination layer.

---

**Documentation Master represents a paradigm shift**: treating external knowledge as a living, evolving asset that grows smarter over time through the MoE learning system.
