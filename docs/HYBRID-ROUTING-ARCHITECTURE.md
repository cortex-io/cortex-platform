# Hybrid Routing Architecture - Cascade Design

**Status**: 🎯 **Architecture Defined, Ready for Implementation**
**Last Updated**: 2025-11-27
**Scale**: 100+ dynamic agents
**Approach**: Keyword → Semantic → RAG → PyTorch cascade

---

## Executive Summary

**Decision**: Use **ALL** routing methods as layers, not competitors.

**Key Insight**: Treat routing as a **cascade** - exit early when confidence is high, fall through to more expensive methods only when needed.

```
Query → Keyword (fast-path, <1ms)
         ↓ (low confidence)
      Semantic (embedding similarity, 10-50ms)
         ↓ (low confidence)
      RAG retrieval (agent docs, history, state, 50-150ms)
         ↓
      PyTorch routing head (learned patterns, 100-300ms)
         ↓
      Confidence check → route or clarify
```

---

## Architecture Layers

### Layer 1: Keyword Fast-Path (<1ms)

**Purpose**: Deterministic routing for known patterns

**When to Use**:
- Explicit agent names ("use unifi-mcp")
- Exact command patterns ("git status", "npm test")
- High-confidence regex matches
- Critical latency paths

**Implementation**:
```bash
# File: coordination/masters/coordinator/lib/routing-cascade.sh

keyword_fast_path() {
  local query="$1"
  local query_lower=$(echo "$query" | tr '[:upper:]' '[:lower:]')

  # Exact agent name match
  if echo "$query_lower" | grep -qE "use (unifi|netdata|github)-mcp"; then
    AGENT=$(echo "$query_lower" | grep -oE "(unifi|netdata|github)-mcp")
    return 0  # High confidence
  fi

  # Explicit command patterns
  if echo "$query_lower" | grep -qE "^(git|npm|docker) "; then
    AGENT="development-master"
    return 0
  fi

  # Security keywords (high priority)
  if echo "$query_lower" | grep -qE "cve-[0-9]{4}-[0-9]+|vulnerability|security audit"; then
    AGENT="security-master"
    return 0
  fi

  return 1  # Low confidence, fall through
}
```

**Latency**: <1ms
**Accuracy**: ~95% for matched patterns
**Exit Early**: If matched, route immediately

---

### Layer 2: Semantic Fallback (10-50ms)

**Purpose**: Intent disambiguation for novel queries

**When to Use**:
- User says "why is my network slow" (need to disambiguate: UniFi vs Netdata vs general)
- Ambiguous queries
- No keyword match

**Implementation**:
```python
# File: llm-mesh/lib/routing/semantic_router.py

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Dict, List, Tuple

class SemanticRouter:
    """
    Semantic routing using embedding similarity

    With 100+ agents, use hierarchical clustering:
    1. Coarse match to domain cluster
    2. Fine-grained match within cluster
    """

    def __init__(self, agent_index_path: str):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

        # Load pre-computed agent embeddings
        self.agent_embeddings = self.load_agent_index(agent_index_path)

        # Domain clusters (for 100+ agents)
        self.clusters = {
            'infrastructure': ['unifi-mcp', 'netdata-mcp', 'proxmox-mcp'],
            'development': ['github-mcp', 'gitlab-mcp', 'jira-mcp'],
            'monitoring': ['grafana-mcp', 'prometheus-mcp', 'elastic-mcp'],
            'security': ['security-master', 'cve-scanner', 'audit-agent']
        }

        # Pre-compute cluster centroids
        self.cluster_centroids = self.compute_cluster_centroids()

    def route(
        self,
        query: str,
        confidence_threshold: float = 0.7
    ) -> Tuple[str, float, Dict]:
        """
        Hierarchical semantic routing

        Returns:
            agent_name: Selected agent
            confidence: 0.0-1.0
            metadata: Routing details
        """
        # Embed query
        query_emb = self.model.encode(query)

        # Step 1: Coarse match to cluster
        cluster_scores = {}
        for cluster_name, centroid in self.cluster_centroids.items():
            similarity = np.dot(query_emb, centroid) / (
                np.linalg.norm(query_emb) * np.linalg.norm(centroid)
            )
            cluster_scores[cluster_name] = similarity

        best_cluster = max(cluster_scores, key=cluster_scores.get)
        cluster_conf = cluster_scores[best_cluster]

        # Step 2: Fine-grained match within cluster
        cluster_agents = self.clusters[best_cluster]
        agent_scores = {}

        for agent_name in cluster_agents:
            agent_emb = self.agent_embeddings[agent_name]
            similarity = np.dot(query_emb, agent_emb) / (
                np.linalg.norm(query_emb) * np.linalg.norm(agent_emb)
            )
            agent_scores[agent_name] = similarity

        best_agent = max(agent_scores, key=agent_scores.get)
        agent_conf = agent_scores[best_agent]

        # Combined confidence (cluster + agent)
        final_conf = (cluster_conf + agent_conf) / 2

        metadata = {
            'method': 'semantic',
            'cluster': best_cluster,
            'cluster_confidence': cluster_conf,
            'agent_confidence': agent_conf,
            'all_agent_scores': agent_scores
        }

        if final_conf >= confidence_threshold:
            return best_agent, final_conf, metadata
        else:
            return None, final_conf, metadata  # Fall through to RAG

    def compute_cluster_centroids(self) -> Dict[str, np.ndarray]:
        """Pre-compute cluster centroids for fast coarse matching"""
        centroids = {}
        for cluster_name, agents in self.clusters.items():
            embeddings = [self.agent_embeddings[a] for a in agents]
            centroids[cluster_name] = np.mean(embeddings, axis=0)
        return centroids
```

**Latency**: 10-50ms (faster with cached embeddings)
**Accuracy**: ~85-90% for novel queries
**Exit Early**: If confidence >= 0.7, route

---

### Layer 3: RAG Context Enrichment (50-150ms)

**Purpose**: Ground routing in real context

**When to Use**:
- Semantic routing returned low confidence
- Need context from agent docs, history, system state

**What RAG Retrieves**:
1. **Agent capability docs** (static but rich)
2. **Historical routing decisions** (learning from past)
3. **Recent usage patterns** ("UniFi MCP last used 2 hours ago for similar query")
4. **System state** (active incidents, recent errors)

**Implementation**:
```python
# File: llm-mesh/lib/routing/rag_enhanced_router.py

from typing import Dict, List, Optional
from .semantic_router import SemanticRouter
from ..rag.vectorstore import CodebaseVectorStore
from ..rag.retriever import ContextRetriever

class RAGEnhancedRouter:
    """
    RAG-enhanced routing with grounded context

    Retrieves:
    - Agent docs & examples
    - Historical routing decisions
    - System state & recent activity
    """

    def __init__(
        self,
        vectorstore_path: str,
        routing_history_path: str
    ):
        # Semantic router for initial candidates
        self.semantic_router = SemanticRouter(vectorstore_path)

        # RAG components
        self.vectorstore = CodebaseVectorStore(vectorstore_path)
        self.retriever = ContextRetriever(self.vectorstore)

        # Routing history for learning
        self.routing_history = self.load_history(routing_history_path)

    def route_with_context(
        self,
        query: str,
        n_context_results: int = 5
    ) -> Dict:
        """
        Route with RAG-retrieved context

        Returns enriched routing decision with context
        """
        # Step 1: Get initial semantic candidates
        agent, conf, metadata = self.semantic_router.route(
            query,
            confidence_threshold=0.5  # Lower threshold, will rerank with context
        )

        # Step 2: Retrieve relevant context
        context = self.retrieve_routing_context(
            query=query,
            candidate_agents=metadata.get('all_agent_scores', {}),
            n_results=n_context_results
        )

        # Step 3: Rerank candidates with context
        reranked_agent, reranked_conf = self.rerank_with_context(
            query=query,
            candidates=metadata.get('all_agent_scores', {}),
            context=context
        )

        return {
            'agent': reranked_agent,
            'confidence': reranked_conf,
            'method': 'rag_enhanced',
            'context_used': context,
            'semantic_candidate': agent,
            'semantic_confidence': conf
        }

    def retrieve_routing_context(
        self,
        query: str,
        candidate_agents: Dict[str, float],
        n_results: int
    ) -> Dict:
        """
        Retrieve grounded context for routing decision

        Returns:
            agent_docs: Relevant capability documentation
            history: Similar past routing decisions
            system_state: Current system context
        """
        # 1. Agent capability docs
        agent_docs = {}
        for agent_name in candidate_agents.keys():
            docs = self.vectorstore.search(
                query=f"{agent_name} capabilities: {query}",
                n_results=2,
                filter_metadata={'type': 'agent_doc'}
            )
            agent_docs[agent_name] = docs

        # 2. Historical routing decisions
        history = self.search_routing_history(query, n_results=3)

        # 3. System state (recent activity)
        system_state = self.get_system_state(candidate_agents.keys())

        return {
            'agent_docs': agent_docs,
            'history': history,
            'system_state': system_state
        }

    def search_routing_history(self, query: str, n_results: int) -> List[Dict]:
        """
        Find similar past routing decisions

        Example: "UniFi MCP successfully resolved VLAN tagging issues,
                  commonly invoked for firewall rules, last used 2 hours ago"
        """
        # Search routing history vector store
        results = self.vectorstore.search(
            query=query,
            n_results=n_results,
            filter_metadata={'type': 'routing_decision'}
        )

        return [
            {
                'query': r['metadata']['original_query'],
                'agent': r['metadata']['selected_agent'],
                'outcome': r['metadata']['outcome'],
                'timestamp': r['metadata']['timestamp'],
                'similarity': r['score']
            }
            for r in results
        ]

    def get_system_state(self, candidate_agents: List[str]) -> Dict:
        """
        Get current system state for context

        - Active incidents
        - Recent errors
        - Agent availability
        - Load balancing info
        """
        return {
            'active_incidents': self.query_active_incidents(),
            'recent_errors': self.query_recent_errors(),
            'agent_availability': {
                agent: self.check_agent_health(agent)
                for agent in candidate_agents
            },
            'load_info': self.get_load_balancing_info(candidate_agents)
        }
```

**Latency**: 50-150ms (vector search + history lookup)
**Accuracy**: ~90-95% with rich context
**Exit Early**: If reranked confidence >= 0.8, route

---

### Layer 4: PyTorch Routing Head (100-300ms)

**Purpose**: Learned patterns from telemetry data

**When to Use**:
- RAG-enhanced routing still below confidence threshold
- Complex ambiguous queries
- Need cross-attention between query and agent context

**Implementation**:
```python
# File: llm-mesh/lib/routing/pytorch_routing_head.py

import torch
import torch.nn as nn
from typing import Dict, Tuple

class PyTorchRoutingHead(nn.Module):
    """
    Trainable routing classifier

    Architecture:
    - Takes: query embedding + RAG context embeddings + agent embeddings
    - Outputs: agent probabilities + confidence score

    Trained on actual routing telemetry (successful/failed routes)
    """

    def __init__(
        self,
        embedding_dim: int = 384,  # all-MiniLM-L6-v2 dimension
        context_dim: int = 384 * 5,  # 5 context results
        agent_dim: int = 384,
        num_agents: int = 100,
        hidden_dim: int = 512
    ):
        super().__init__()

        # Query encoder
        self.query_encoder = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim)
        )

        # Context encoder (RAG results)
        self.context_encoder = nn.Sequential(
            nn.Linear(context_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim)
        )

        # Agent encoder
        self.agent_encoder = nn.Sequential(
            nn.Linear(agent_dim * num_agents, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim * 2, hidden_dim)
        )

        # Cross-attention (query + context)
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=8,
            dropout=0.1
        )

        # Routing classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, num_agents)
        )

        # Confidence predictor
        self.confidence = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()
        )

    def forward(
        self,
        query_emb: torch.Tensor,        # [batch, embedding_dim]
        context_emb: torch.Tensor,      # [batch, context_dim]
        agent_embs: torch.Tensor        # [batch, agent_dim * num_agents]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with query, RAG context, and agent embeddings

        Returns:
            logits: [batch, num_agents] - Agent selection logits
            confidence: [batch, 1] - Confidence scores
        """
        # Encode inputs
        query_enc = self.query_encoder(query_emb)
        context_enc = self.context_encoder(context_emb)
        agent_enc = self.agent_encoder(agent_embs)

        # Cross-attention between query and context
        query_enc_attn = query_enc.unsqueeze(0)  # [1, batch, hidden]
        context_enc_attn = context_enc.unsqueeze(0)

        attn_output, _ = self.cross_attention(
            query_enc_attn,
            context_enc_attn,
            context_enc_attn
        )
        attn_output = attn_output.squeeze(0)  # [batch, hidden]

        # Combine all representations
        combined = torch.cat([query_enc, attn_output, agent_enc], dim=-1)

        # Classify and predict confidence
        logits = self.classifier(combined)
        conf = self.confidence(combined)

        return logits, conf


class PyTorchRouter:
    """
    PyTorch-based router with RAG context

    Uses trained routing head to make final decisions
    """

    def __init__(
        self,
        model_path: str,
        agent_index: Dict[str, torch.Tensor]
    ):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = PyTorchRoutingHead().to(self.device)

        # Load trained weights
        checkpoint = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

        # Agent index (pre-computed embeddings)
        self.agent_index = agent_index
        self.agent_names = list(agent_index.keys())

    @torch.no_grad()
    def route(
        self,
        query_embedding: torch.Tensor,
        rag_context_embeddings: torch.Tensor,
        confidence_threshold: float = 0.9
    ) -> Dict:
        """
        Final routing decision using PyTorch model

        Args:
            query_embedding: [embedding_dim]
            rag_context_embeddings: [context_dim] - concatenated RAG results

        Returns:
            agent: Selected agent
            confidence: Confidence score
            all_probabilities: Probabilities for all agents
        """
        # Prepare agent embeddings
        agent_embs = torch.cat([
            self.agent_index[name] for name in self.agent_names
        ])

        # Add batch dimension
        query_emb = query_embedding.unsqueeze(0).to(self.device)
        context_emb = rag_context_embeddings.unsqueeze(0).to(self.device)
        agent_emb = agent_embs.unsqueeze(0).to(self.device)

        # Forward pass
        logits, conf = self.model(query_emb, context_emb, agent_emb)

        # Get probabilities
        probs = torch.softmax(logits, dim=-1)[0]
        confidence = conf[0].item()

        # Select agent
        agent_idx = probs.argmax().item()
        selected_agent = self.agent_names[agent_idx]

        # All probabilities
        all_probs = {
            name: probs[i].item()
            for i, name in enumerate(self.agent_names)
        }

        return {
            'agent': selected_agent,
            'confidence': confidence,
            'method': 'pytorch',
            'all_probabilities': all_probs,
            'needs_clarification': confidence < confidence_threshold
        }
```

**Latency**: 100-300ms (inference on CPU, faster on GPU)
**Accuracy**: ~95-98% (with trained model)
**Exit Condition**: If confidence >= 0.9, route; else ask for clarification

---

## Full Cascade Implementation

### Master Router Orchestration

```bash
# File: coordination/masters/coordinator/lib/routing-cascade.sh

route_query_cascade() {
  local query="$1"
  local routing_start=$(date +%s%3N)

  echo "🔍 Starting routing cascade for: $query" >&2

  # Layer 1: Keyword fast-path
  if keyword_fast_path "$query"; then
    local latency=$(($(date +%s%3N) - routing_start))
    echo "✅ Keyword match: $AGENT (${latency}ms, confidence: 0.95)" >&2
    log_routing_decision "$query" "$AGENT" "keyword" 0.95 "$latency"
    echo "$AGENT"
    return 0
  fi

  # Layer 2: Semantic fallback
  SEMANTIC_RESULT=$(python llm-mesh/lib/routing/run_semantic.py \
    --query "$query" \
    --confidence-threshold 0.7)

  SEMANTIC_AGENT=$(echo "$SEMANTIC_RESULT" | jq -r '.agent')
  SEMANTIC_CONF=$(echo "$SEMANTIC_RESULT" | jq -r '.confidence')

  if [ "$SEMANTIC_AGENT" != "null" ] && (( $(echo "$SEMANTIC_CONF >= 0.7" | bc -l) )); then
    local latency=$(($(date +%s%3N) - routing_start))
    echo "✅ Semantic match: $SEMANTIC_AGENT (${latency}ms, confidence: $SEMANTIC_CONF)" >&2
    log_routing_decision "$query" "$SEMANTIC_AGENT" "semantic" "$SEMANTIC_CONF" "$latency"
    echo "$SEMANTIC_AGENT"
    return 0
  fi

  # Layer 3: RAG-enhanced routing
  RAG_RESULT=$(python llm-mesh/lib/routing/run_rag_enhanced.py \
    --query "$query" \
    --confidence-threshold 0.8)

  RAG_AGENT=$(echo "$RAG_RESULT" | jq -r '.agent')
  RAG_CONF=$(echo "$RAG_RESULT" | jq -r '.confidence')

  if [ "$RAG_AGENT" != "null" ] && (( $(echo "$RAG_CONF >= 0.8" | bc -l) )); then
    local latency=$(($(date +%s%3N) - routing_start))
    echo "✅ RAG-enhanced match: $RAG_AGENT (${latency}ms, confidence: $RAG_CONF)" >&2
    log_routing_decision "$query" "$RAG_AGENT" "rag_enhanced" "$RAG_CONF" "$latency"
    echo "$RAG_AGENT"
    return 0
  fi

  # Layer 4: PyTorch routing head (final decision)
  PYTORCH_RESULT=$(python llm-mesh/lib/routing/run_pytorch.py \
    --query "$query" \
    --rag-context "$RAG_RESULT")

  PYTORCH_AGENT=$(echo "$PYTORCH_RESULT" | jq -r '.agent')
  PYTORCH_CONF=$(echo "$PYTORCH_RESULT" | jq -r '.confidence')
  NEEDS_CLARIFICATION=$(echo "$PYTORCH_RESULT" | jq -r '.needs_clarification')

  local latency=$(($(date +%s%3N) - routing_start))

  if [ "$NEEDS_CLARIFICATION" = "true" ]; then
    echo "⚠️  Low confidence ($PYTORCH_CONF), requesting clarification" >&2
    log_routing_decision "$query" "clarification_needed" "pytorch" "$PYTORCH_CONF" "$latency"
    echo "CLARIFY"
    return 1
  else
    echo "✅ PyTorch match: $PYTORCH_AGENT (${latency}ms, confidence: $PYTORCH_CONF)" >&2
    log_routing_decision "$query" "$PYTORCH_AGENT" "pytorch" "$PYTORCH_CONF" "$latency"
    echo "$PYTORCH_AGENT"
    return 0
  fi
}

log_routing_decision() {
  local query="$1"
  local agent="$2"
  local method="$3"
  local confidence="$4"
  local latency="$5"

  local log_entry=$(cat <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "query": "$query",
  "selected_agent": "$agent",
  "routing_method": "$method",
  "confidence": $confidence,
  "latency_ms": $latency
}
EOF
)

  echo "$log_entry" >> coordination/logs/routing-decisions.jsonl
}
```

---

## Observability & Telemetry

### Route to Elastic for Analysis

**Key Metrics to Track**:
1. **Routing method distribution**
   - % keyword vs semantic vs RAG vs PyTorch
   - Identify patterns

2. **Confidence scores by method**
   - Are we tuning thresholds correctly?

3. **Latency per layer**
   - Where are bottlenecks?

4. **Misrouting rate**
   - Track failed routes, retrain PyTorch

5. **Cascade efficiency**
   - How often do we exit early vs fall through?

**Elastic Integration**:
```javascript
// File: api-server/server/index.js

app.post('/api/routing/telemetry', async (req, res) => {
  const {
    query,
    selected_agent,
    routing_method,
    confidence,
    latency_ms,
    all_scores
  } = req.body;

  // Send to Elastic APM
  apm.captureEvent({
    name: 'routing_decision',
    type: 'custom',
    data: {
      query,
      agent: selected_agent,
      method: routing_method,
      confidence,
      latency_ms,
      scores: all_scores
    }
  });

  res.json({ received: true });
});
```

**Queries for Optimization**:
```
# Find low-confidence routes that succeeded (false negatives)
GET /routing-decisions/_search
{
  "query": {
    "bool": {
      "must": [
        { "range": { "confidence": { "lt": 0.8 } } },
        { "term": { "outcome": "success" } }
      ]
    }
  }
}

# Find misrouted queries (for retraining)
GET /routing-decisions/_search
{
  "query": {
    "term": { "outcome": "failed" }
  }
}
```

---

## Cold Start Strategy for New Agents

**Problem**: New agents spin up dynamically, no training data

**Solution**: Graceful degradation

```python
# File: llm-mesh/lib/routing/cold_start_handler.py

class ColdStartHandler:
    """
    Handle routing for new agents with no training data

    Strategy:
    1. Zero-shot semantic routing (use agent description)
    2. Collect telemetry (10-50 queries)
    3. Incremental training update
    4. Full integration once validated
    """

    def handle_new_agent(
        self,
        agent_name: str,
        agent_description: str,
        capabilities: List[str]
    ):
        """
        Initialize routing for new agent

        1. Embed description
        2. Add to semantic index
        3. Mark as "cold_start"
        4. Route with zero-shot until telemetry collected
        """
        # Embed agent description
        agent_emb = self.model.encode(agent_description)

        # Add to semantic index
        self.agent_index[agent_name] = {
            'embedding': agent_emb,
            'capabilities': capabilities,
            'status': 'cold_start',
            'queries_seen': 0,
            'success_rate': None
        }

        # Log for monitoring
        self.log_new_agent(agent_name, agent_description)

    def check_graduation(self, agent_name: str) -> bool:
        """
        Check if agent ready to graduate from cold start

        Criteria:
        - 50+ queries routed
        - 80%+ success rate
        - Confidence scores stabilized
        """
        agent_data = self.agent_index[agent_name]

        if agent_data['status'] != 'cold_start':
            return False

        if agent_data['queries_seen'] < 50:
            return False

        if agent_data['success_rate'] < 0.8:
            return False

        # Graduate to full routing
        agent_data['status'] = 'active'
        self.update_pytorch_model_incremental(agent_name)

        return True
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1)

**Day 1-2: Keyword + Semantic Cascade**
1. Implement keyword fast-path
2. Implement semantic routing with hierarchical clustering
3. Test cascade (keyword → semantic)
4. Set confidence thresholds

**Day 3-4: RAG Integration**
1. Index agent docs (capabilities, examples)
2. Index routing history
3. Implement RAG context retrieval
4. Test RAG-enhanced routing

**Day 5: Telemetry**
1. Add routing decision logging
2. Elastic integration
3. Dashboard for monitoring

---

### Phase 2: PyTorch Training (Week 2-3)

**Week 2: Data Collection**
1. Run cascade in production (keyword + semantic + RAG)
2. Collect routing decisions (1000+ examples)
3. Label with outcomes (success/failed)
4. Create training dataset

**Week 3: Model Training**
1. Train PyTorch routing head
2. Validate on held-out set
3. A/B test at 10% traffic
4. Monitor accuracy vs semantic+RAG

---

### Phase 3: Optimization (Week 4)

**Day 1-2: Agent Studio Integration**
1. Connect Agent Studio to routing cascade
2. Register 100+ agents
3. Enable lifecycle tracking

**Day 3-4: Cold Start Handler**
1. Implement zero-shot for new agents
2. Incremental training pipeline
3. Graduation criteria

**Day 5: Performance Tuning**
1. Optimize latency (caching, batching)
2. Tune confidence thresholds
3. Load testing

---

## Expected Performance

| Layer | Latency | Accuracy | When Used |
|-------|---------|----------|-----------|
| Keyword | <1ms | 95% | 30-40% of queries |
| Semantic | 10-50ms | 85-90% | 30-40% of queries |
| RAG | 50-150ms | 90-95% | 15-25% of queries |
| PyTorch | 100-300ms | 95-98% | 5-10% of queries |

**Overall System**:
- **Average latency**: 20-50ms (most queries exit early)
- **Accuracy**: 95%+ (with cascade)
- **Clarification rate**: <5% (only hardest queries)

---

## Success Metrics

Track these to validate hybrid routing:

1. **Cascade efficiency**: What % exit at each layer?
2. **Latency distribution**: P50, P95, P99
3. **Accuracy by layer**: Are lower layers worse?
4. **Misrouting rate**: <2% target
5. **Cold start success**: New agents validated in <50 queries

---

## Next Steps

1. **This Week**: Implement keyword + semantic cascade
2. **Week 2**: Add RAG layer
3. **Week 3**: Collect data, train PyTorch
4. **Week 4**: Full integration, Agent Studio, cold start

**Owner**: Development Master + Security Master (telemetry)
**Timeline**: 4 weeks to full deployment
