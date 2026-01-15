# Cortex Online School Services

**"The infrastructure that teaches itself."**

This directory contains the 5 microservices that power Cortex Online School - the autonomous learning and implementation pipeline.

## Services

### 1. Coordinator (`coordinator/`)
Main orchestration service that manages the entire pipeline.

**Responsibilities**:
- Monitors Redis improvement queues
- Routes improvements through MoE → RAG → Auto-approval
- Tracks improvement status through all stages
- Provides API for pipeline status

**Environment Variables**:
- `REDIS_HOST` - Redis server hostname
- `AUTO_APPROVE_THRESHOLD` - Relevance threshold (default: 0.90)
- `HIGH_RISK_THRESHOLD` - High-risk category threshold (default: 0.95)
- `MOE_ROUTER_URL` - MoE router service URL
- `RAG_VALIDATOR_URL` - RAG validator service URL

### 2. MoE Router (`moe-router/`)
Routes improvements to specialized expert agents using LLM-D coordination.

**Expert Agents**:
- Architecture (Claude Opus 4.5)
- Integration (Claude Sonnet 4.5)
- Security (Claude Opus 4.5)
- Database (Claude Sonnet 4.5)
- Networking (Claude Sonnet 4.5)
- Monitoring (Claude Haiku 4)

**Environment Variables**:
- `ANTHROPIC_API_KEY` - Anthropic API key (required)
- `LLMD_ENDPOINT` - LLM-D service endpoint
- `EXPERT_*_MODEL` - Model for each expert type

### 3. RAG Validator (`rag-validator/`)
Validates improvements against existing infrastructure using vector search.

**Validation Checks**:
- Searches for duplicate improvements
- Checks cortex-docs for conflicts
- Checks cortex-gitops for existing implementations
- Validates dependencies

**Environment Variables**:
- `QDRANT_HOST` - Qdrant vector database hostname
- `OPENAI_API_KEY` - OpenAI API key (for embeddings)
- `EMBEDDING_MODEL` - Embedding model (default: text-embedding-3-large)
- `SIMILARITY_THRESHOLD` - Similarity threshold (default: 0.85)

### 4. Implementation Worker (`implementation-worker/`)
Generates Kubernetes manifests and commits to Git.

**Responsibilities**:
- Picks approved improvements from Redis
- Generates appropriate manifests
- Commits to cortex-gitops repository
- Pushes to GitHub
- Tracks deployment status

**Environment Variables**:
- `REDIS_HOST` - Redis server hostname
- `GITHUB_REPO` - GitHub repository (e.g., ry-ops/cortex-gitops)
- `GITHUB_TOKEN` - GitHub personal access token (required)
- `COMMIT_AUTHOR_NAME` - Git commit author name
- `COMMIT_AUTHOR_EMAIL` - Git commit author email

### 5. Health Monitor (`health-monitor/`)
Monitors deployments and triggers automatic rollbacks on failures.

**Monitoring Period**: 5 minutes after deployment

**Health Checks**:
- Pod status and readiness
- Prometheus metrics
- Log analysis
- Dependency connectivity

**Rollback Process**:
1. Detect failure
2. `git revert <commit>`
3. Push rollback commit
4. Force ArgoCD sync
5. Verify system healthy

**Environment Variables**:
- `REDIS_HOST` - Redis server hostname
- `PROMETHEUS_URL` - Prometheus server URL
- `HEALTH_CHECK_DURATION` - Monitoring duration in seconds (default: 300)
- `ROLLBACK_ENABLED` - Enable automatic rollback (default: true)
- `GITHUB_REPO` - GitHub repository
- `GITHUB_TOKEN` - GitHub token (required for rollback)

## Building Images

### Prerequisites
- Docker installed
- Access to local registry at `10.43.170.72:5000`

### Build All Services
```bash
cd ~/Projects/cortex-platform/services
./cortex-school-build.sh
```

This will:
1. Build Docker images for all 5 services
2. Tag images for local registry
3. Push images to `10.43.170.72:5000`

### Build Individual Service
```bash
cd coordinator/  # or any service directory
docker build -t cortex-coordinator:latest .
docker tag cortex-coordinator:latest 10.43.170.72:5000/cortex-coordinator:latest
docker push 10.43.170.72:5000/cortex-coordinator:latest
```

## Deployment

Services are deployed via GitOps using ArgoCD.

**Manifests**: `~/Projects/cortex-gitops/apps/cortex-school/`
**ArgoCD Application**: `cortex-school`

After building images, restart pods:
```bash
kubectl delete pods -n cortex-school --all
```

ArgoCD will recreate them and pull the new images.

## Architecture

```
YouTube Learning (✅ Working)
    ↓
Redis Improvement Queue
    ↓
MoE Router → Specialized Experts
    ↓
RAG Validator → Check Conflicts
    ↓
Auto-Approve (≥90% relevance)
    ↓
Implementation Workers → Generate Manifests
    ↓
Git Commit → cortex-gitops
    ↓
ArgoCD Auto-Sync (within 3 min)
    ↓
K8s Deployment
    ↓
Health Monitor → Verify or Rollback
```

## Redis Pipeline

Improvements flow through 7 stages:

1. `improvements:raw` - From YouTube service
2. `improvements:categorized` - After MoE evaluation
3. `improvements:validated` - After RAG validation
4. `improvements:approved` - Auto-approved (≥90% relevance)
5. `improvements:pending_review` - Requires human review
6. `improvements:deployed` - Deployed by ArgoCD
7. `improvements:verified` - Health checks passed
8. `improvements:failed` - Failed health checks (rolled back)

## Auto-Approval Criteria

### Approved Automatically
✅ Relevance ≥ 0.90 AND category in: architecture, capability, monitoring
✅ Relevance ≥ 0.95 AND category in: security, database

### Requires Human Review
❌ Category: integration (tools, external services)
❌ Relevance < 0.90 (below threshold)
❌ RAG conflicts found

## Secrets Required

Create these secrets in the `cortex-school` namespace:

```bash
# Anthropic API key (for MoE router)
kubectl create secret generic anthropic-api-key \
  -n cortex-school \
  --from-literal=key=YOUR_KEY

# OpenAI API key (for RAG embeddings)
kubectl create secret generic openai-api-key \
  -n cortex-school \
  --from-literal=key=YOUR_KEY

# GitHub token (for Git commits)
kubectl create secret generic github-token \
  -n cortex-school \
  --from-literal=token=YOUR_TOKEN
```

## Monitoring

### Check Pipeline Status
```bash
# Coordinator API
kubectl port-forward -n cortex-school svc/school-coordinator 8080:8080
curl http://localhost:8080/status

# Check queue sizes
kubectl exec -n cortex deploy/school-coordinator -- sh -c "
echo 'ZCARD improvements:raw' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:approved' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:verified' | redis-cli -h redis.cortex.svc.cluster.local
"
```

### View Logs
```bash
# Coordinator
kubectl logs -n cortex-school -l app=school-coordinator --tail=50 -f

# MoE Router
kubectl logs -n cortex-school -l app=moe-router --tail=50 -f

# RAG Validator
kubectl logs -n cortex-school -l app=rag-validator --tail=50 -f

# Implementation Workers
kubectl logs -n cortex-school -l app=implementation-workers --tail=50 -f

# Health Monitor
kubectl logs -n cortex-school -l app=health-monitor --tail=50 -f
```

### Check Pod Status
```bash
kubectl get pods -n cortex-school
kubectl describe pod <pod-name> -n cortex-school
```

## Documentation

**Complete Architecture**: `~/Projects/cortex-docs/vault/architecture/cortex-online-school.md` (1,350 lines)

**Kubernetes Manifests**: `~/Projects/cortex-gitops/apps/cortex-school/`

## Development

### Local Testing
Each service can be run locally for testing:

```bash
cd coordinator/
pip install -r requirements.txt
export REDIS_HOST=localhost
export REDIS_PORT=6379
python app.py
```

### Adding New Features
1. Modify service code
2. Build and push new image
3. Restart pods in cluster
4. Monitor logs for issues

## Troubleshooting

### Pods stuck in ErrImagePull
Images need to be built and pushed to registry:
```bash
./cortex-school-build.sh
kubectl delete pods -n cortex-school --all
```

### Services can't connect to Redis
Check Redis service is running:
```bash
kubectl get svc -n cortex redis
kubectl get pods -n cortex -l app=redis
```

### GitHub commits failing
Check GitHub token secret:
```bash
kubectl get secret github-token -n cortex-school
# Recreate if needed
kubectl delete secret github-token -n cortex-school
kubectl create secret generic github-token -n cortex-school --from-literal=token=YOUR_TOKEN
```

### RAG validation not working
Check Qdrant and OpenAI API key:
```bash
kubectl get pods -n cortex-school -l app=qdrant
kubectl get secret openai-api-key -n cortex-school
```

---

**Status**: ✅ Code complete, ready to build images
**Next**: Run `./cortex-school-build.sh` on a machine with Docker access
