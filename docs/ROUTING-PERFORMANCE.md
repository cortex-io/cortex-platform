# Routing Performance Tracking

Comprehensive performance tracking and optimization for the 5-layer hybrid routing cascade.

## Overview

The Cortex routing system uses a 5-layer cascade to intelligently route tasks to the optimal master agent. This document describes the performance tracking infrastructure that measures, learns from, and optimizes routing decisions.

## Architecture

### 5-Layer Routing Cascade

```
┌─────────────────────────────────────────────────────────────┐
│ Task: "Fix authentication bug in user login"               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Keyword Matching                                  │
│ ├─ Latency: <5ms                                           │
│ ├─ Accuracy: 80%                                           │
│ └─ Threshold: 0.85                                         │
│                                                             │
│ Result: confidence=0.82 → PASS TO NEXT LAYER              │
└────────────────┬────────────────────────────────────────────┘
                 │ confidence < threshold
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Semantic Similarity                               │
│ ├─ Latency: 10-50ms                                        │
│ ├─ Accuracy: 88%                                           │
│ └─ Threshold: 0.70                                         │
│                                                             │
│ Result: confidence=0.91 → ROUTE                            │
└────────────────┬────────────────────────────────────────────┘
                 │ confidence ≥ threshold
                 ▼
         development-master
```

### Layer Specifications

| Layer | Method | Latency | Accuracy | Threshold | Description |
|-------|--------|---------|----------|-----------|-------------|
| 1 | Keyword | <5ms | 80% | 0.85 | Fast pattern matching on keywords |
| 2 | Semantic | 10-50ms | 88% | 0.70 | Embedding similarity with clustering |
| 3 | RAG | 50-150ms | 92% | 0.85 | Vector search with codebase context |
| 4 | PyTorch | 100-300ms | 96% | 0.90 | Neural routing head (trained model) |
| 5 | Clarification | N/A | 100% | 1.00 | User clarification fallback |

## Performance Tracking Schema

### Routing Decision Event

Each routing decision is logged to `coordination/routing/performance.jsonl`:

```json
{
  "event_id": "route-20251127-143052-a3f8b2c1",
  "timestamp": "2025-11-27T14:30:52Z",
  "task_id": "task-001",
  "task_description": "Fix authentication bug in user login system",
  "task_metadata": {
    "priority": "high",
    "source": "user"
  },
  "routing_layers": [
    {
      "layer_id": 1,
      "layer_name": "keyword",
      "attempted": true,
      "success": false,
      "confidence": 0.82,
      "threshold": 0.85,
      "selected_master": "development-master",
      "latency_ms": 3.2,
      "metadata": {
        "matched_keywords": ["fix", "bug", "authentication"]
      }
    },
    {
      "layer_id": 2,
      "layer_name": "semantic",
      "attempted": true,
      "success": true,
      "confidence": 0.91,
      "threshold": 0.70,
      "selected_master": "development-master",
      "latency_ms": 42.1,
      "metadata": {
        "similarity_score": 0.91,
        "cluster": "development"
      }
    }
  ],
  "final_decision": {
    "selected_master": "development-master",
    "routing_layer": "semantic",
    "confidence": 0.91,
    "all_probabilities": {
      "development-master": 0.91,
      "security-master": 0.05,
      "cicd-master": 0.04
    }
  },
  "total_latency_ms": 45.3,
  "outcome": {
    "task_completed": true,
    "task_status": "completed",
    "was_correct_master": true,
    "user_corrected_to": null,
    "completion_time_minutes": 45,
    "quality_score": 0.95
  },
  "learning_feedback": {
    "correct_routing": true,
    "should_have_routed_to": null,
    "layer_should_have_caught": null,
    "threshold_too_high": false,
    "threshold_too_low": false
  }
}
```

## Usage

### 1. Track Routing Decisions (Python)

```python
from llm_mesh.lib.routing.performance_tracker import RoutingPerformanceTracker

# Initialize tracker
tracker = RoutingPerformanceTracker()

# Start routing
event_id = tracker.start_routing(
    task_description="Deploy API to production",
    task_id="task-123",
    task_metadata={"priority": "high"}
)

# Layer 1: Keyword
tracker.mark_layer_start("keyword")
tracker.record_layer_attempt(
    layer_name="keyword",
    confidence=0.88,
    selected_master="cicd-master",
    success=True,
    metadata={"matched_keywords": ["deploy", "production"]}
)

# Finalize
tracker.finalize_routing(
    selected_master="cicd-master",
    routing_layer="keyword",
    confidence=0.88,
    all_probabilities={
        "cicd-master": 0.88,
        "development-master": 0.10,
        "security-master": 0.02
    }
)

# Later: record outcome
tracker.record_outcome(
    task_completed=True,
    task_status="completed",
    was_correct_master=True,
    completion_time_minutes=30,
    quality_score=0.98
)
```

### 2. View Performance Dashboard

```bash
# One-time view
./scripts/routing-dashboard.sh

# Live mode with auto-refresh
./scripts/routing-dashboard.sh --live

# Custom time window
./scripts/routing-dashboard.sh -w 24  # Last 24 hours
```

Dashboard output:

```
╔════════════════════════════════════════════════════════════════════╗
║           ROUTING PERFORMANCE DASHBOARD                           ║
╚════════════════════════════════════════════════════════════════════╝

Time Window: 1h  |  Updated: 2025-11-27 14:35:22

━━━ Routing Cascade Overview ━━━
Total routes: 145

Layer 1 - Keyword      [============----------------] 42 (29.0%)
Layer 2 - Semantic     [====================--------] 68 (46.9%)
Layer 3 - RAG          [========--------------------] 25 (17.2%)
Layer 4 - PyTorch      [===-------------------------]  8 (5.5%)
Layer 5 - Clarification[=---------------------------]  2 (1.4%)

━━━ Layer Performance ━━━
Layer            Attempts   Success%   Avg Conf   Avg Latency      Accuracy
───────────────────────────────────────────────────────────────────────────
keyword              145       29.0%      0.784         3.2ms         91.2%
semantic             103       66.0%      0.812        38.5ms         94.1%
rag                   35       71.4%      0.891       128.3ms         96.0%
pytorch               10       80.0%      0.923       245.7ms         98.8%
clarification          2      100.0%      1.000         0.0ms        100.0%
```

### 3. Analyze Performance

```bash
# Analyze all layers (last 24 hours)
./scripts/analyze-routing-performance.sh

# Specific layer
./scripts/analyze-routing-performance.sh -l semantic

# Custom time window
./scripts/analyze-routing-performance.sh -w 72

# JSON output for integration
./scripts/analyze-routing-performance.sh -f json
```

### 4. Auto-Tune Thresholds

```bash
# Dry run (preview changes)
./scripts/tune-routing-thresholds.sh -d

# Apply tuning (based on last 7 days)
./scripts/tune-routing-thresholds.sh

# Aggressive tuning
./scripts/tune-routing-thresholds.sh -a

# Custom parameters
./scripts/tune-routing-thresholds.sh -w 168 -s 0.05 -m 100
```

Tuning algorithm:

1. **Collect samples**: Gather all routing decisions with outcomes
2. **Calculate optimal threshold**: For each possible threshold, calculate accuracy
3. **Recommend adjustment**: Adjust by step size toward optimal
4. **Validate**: Only adjust if sufficient samples and significant improvement

## Integration with MoE Router

### Integration Points

The performance tracker integrates with the existing MoE router at these points:

#### 1. **Route Decision Point**

In `/Users/ryandahlberg/Projects/cortex/llm-mesh/lib/integration/moe_ml_router.py`:

```python
from llm_mesh.lib.routing.performance_tracker import RoutingPerformanceTracker

class MLEnhancedRouter:
    def __init__(self, ...):
        # ... existing init ...
        self.perf_tracker = RoutingPerformanceTracker()

    def route_task(self, task_description: str, task_metadata: Optional[Dict] = None):
        # Start tracking
        event_id = self.perf_tracker.start_routing(
            task_description=task_description,
            task_metadata=task_metadata
        )

        # Try each layer in cascade
        result = self._try_cascade(task_description, task_metadata)

        # Finalize tracking
        self.perf_tracker.finalize_routing(
            selected_master=result['selected_master'],
            routing_layer=result['routing_method'],
            confidence=result['confidence'],
            all_probabilities=result.get('all_probabilities', {})
        )

        return result
```

#### 2. **Layer Attempt Tracking**

For each routing layer:

```python
def _try_keyword_layer(self, task_description: str):
    self.perf_tracker.mark_layer_start("keyword")

    # Perform keyword matching
    master, confidence, metadata = self._keyword_match(task_description)

    # Get threshold
    threshold = self._get_threshold("keyword")
    success = confidence >= threshold

    # Record attempt
    self.perf_tracker.record_layer_attempt(
        layer_name="keyword",
        confidence=confidence,
        selected_master=master,
        success=success,
        metadata=metadata
    )

    return success, master, confidence
```

#### 3. **Outcome Feedback**

After task completion (in task completion handlers):

```python
def on_task_complete(task_id: str, outcome: Dict):
    # Find associated routing event
    routing_event = find_routing_event_for_task(task_id)

    if routing_event:
        tracker = RoutingPerformanceTracker()
        tracker.current_routing = routing_event

        tracker.record_outcome(
            task_completed=outcome['success'],
            task_status=outcome['status'],
            was_correct_master=outcome.get('correct_routing', True),
            user_corrected_to=outcome.get('corrected_master'),
            completion_time_minutes=outcome.get('duration_minutes'),
            quality_score=outcome.get('quality_score')
        )
```

### Cascade Implementation

Update routing cascade to use performance tracking:

```python
def route_with_cascade(self, task_description: str) -> Dict:
    """Route using 5-layer cascade with performance tracking"""
    event_id = self.perf_tracker.start_routing(task_description)

    # Layer 1: Keyword
    success, master, conf = self._try_keyword_layer(task_description)
    if success:
        return self._finalize_route(master, "keyword", conf)

    # Layer 2: Semantic
    success, master, conf = self._try_semantic_layer(task_description)
    if success:
        return self._finalize_route(master, "semantic", conf)

    # Layer 3: RAG
    success, master, conf = self._try_rag_layer(task_description)
    if success:
        return self._finalize_route(master, "rag", conf)

    # Layer 4: PyTorch
    success, master, conf = self._try_pytorch_layer(task_description)
    if success:
        return self._finalize_route(master, "pytorch", conf)

    # Layer 5: Clarification
    return self._request_clarification(task_description)
```

## Learning from Failures

### Identifying Incorrect Routes

The system tracks several failure patterns:

1. **User Correction**: User manually reassigns task to different master
2. **Task Failure**: Task fails due to wrong master assignment
3. **Quality Issues**: Task completes but with low quality score

### Learning Feedback Generation

```python
def _generate_learning_feedback(self):
    """Generate feedback for model training"""
    outcome = self.current_routing["outcome"]

    if outcome["was_correct_master"] == False:
        # Find which layer should have caught it
        correct_master = outcome["user_corrected_to"]

        for layer in self.current_routing["routing_layers"]:
            if layer["selected_master"] == correct_master:
                if layer["confidence"] < layer["threshold"]:
                    # Threshold too high!
                    return {
                        "layer_should_have_caught": layer["layer_name"],
                        "threshold_too_high": True,
                        "recommended_threshold": layer["confidence"] - 0.05
                    }
```

### Threshold Auto-Tuning

The tuner analyzes two types of errors:

1. **Missed Opportunities** (False Negatives)
   - Layer had correct answer but confidence below threshold
   - **Fix**: Lower threshold

2. **False Positives**
   - Layer had high confidence but wrong answer
   - **Fix**: Raise threshold

Algorithm:

```python
def find_optimal_threshold(layer_name, samples):
    best_threshold = 0
    best_accuracy = 0

    for threshold in range(0.5, 0.95, 0.05):
        tp = 0  # Correct, above threshold
        fp = 0  # Incorrect, above threshold
        tn = 0  # Correct, below threshold (passed to next layer)
        fn = 0  # Incorrect, below threshold

        for sample in samples:
            if sample.confidence >= threshold:
                if sample.correct:
                    tp += 1
                else:
                    fp += 1
            else:
                if sample.correct:
                    tn += 1
                else:
                    fn += 1

        accuracy = (tp + tn) / (tp + fp + tn + fn)

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = threshold

    return best_threshold, best_accuracy
```

## Metrics

### Key Performance Indicators

1. **Layer Success Rate**: Percentage of attempts that meet threshold
2. **Layer Accuracy**: Percentage of final decisions that were correct
3. **Cascade Efficiency**: How early in cascade routes are resolved
4. **Average Latency**: Time to route per layer
5. **Threshold Effectiveness**: Gap between threshold and optimal

### Performance Targets

| Metric | Target | Alert If |
|--------|--------|----------|
| Overall Accuracy | >95% | <90% |
| Layer 1 Capture Rate | >30% | <20% |
| Layer 2 Capture Rate | >40% | <30% |
| Avg Total Latency | <100ms | >200ms |
| User Corrections | <5% | >10% |

## Best Practices

### 1. Regular Monitoring

```bash
# Daily dashboard check
./scripts/routing-dashboard.sh -w 24

# Weekly analysis
./scripts/analyze-routing-performance.sh -w 168

# Monthly tuning
./scripts/tune-routing-thresholds.sh -w 720
```

### 2. Outcome Feedback

Always provide outcome feedback for learning:

```python
# After task completion
tracker.record_outcome(
    task_completed=task.success,
    was_correct_master=True,  # Important!
    quality_score=calculate_quality(task)
)
```

### 3. Threshold Tuning

- Run dry-run first: `tune-routing-thresholds.sh -d`
- Start conservative: Use default step size (0.05)
- Validate impact: Check dashboard after tuning
- Require minimum samples: Default 100 per layer

### 4. Integration Testing

After threshold changes:

```bash
# Check routing distribution
./scripts/routing-dashboard.sh -w 1

# Verify latency hasn't increased
./scripts/analyze-routing-performance.sh -l semantic

# Monitor accuracy for 24h
watch -n 300 './scripts/routing-dashboard.sh -w 24'
```

## Troubleshooting

### Low Layer 1 Success Rate

**Symptom**: Keyword layer catches <20% of routes

**Solutions**:
1. Lower keyword threshold
2. Add more keyword patterns
3. Check if tasks are too complex for keywords

### High Clarification Rate

**Symptom**: >5% routes fall through to clarification

**Solutions**:
1. Lower Layer 4 (PyTorch) threshold
2. Retrain PyTorch model with recent data
3. Review RAG vector store coverage

### Accuracy Degradation

**Symptom**: Accuracy drops below 90%

**Solutions**:
1. Check for data drift in task types
2. Review recent threshold changes
3. Retrain models with recent outcome data
4. Analyze learning feedback for patterns

### High Latency

**Symptom**: Average latency >200ms

**Solutions**:
1. Optimize early layers to catch more routes
2. Check embedding model performance
3. Review vector store query time
4. Consider caching for common patterns

## Files

```
coordination/routing/
├── config.json                    # Layer configuration & thresholds
├── performance.jsonl              # Routing decision log
└── backups/                       # Config backups from tuning

coordination/schemas/
└── routing-decision.json          # Event schema definition

llm-mesh/lib/routing/
├── performance_tracker.py         # Python tracking library
├── neural_router.py               # PyTorch routing head
├── run_semantic.py                # Semantic similarity layer
├── run_rag_enhanced.py            # RAG layer
└── run_pytorch.py                 # PyTorch layer

scripts/
├── analyze-routing-performance.sh # Performance analyzer
├── routing-dashboard.sh           # Real-time dashboard
└── tune-routing-thresholds.sh     # Auto-tuner
```

## Next Steps

1. **Model Training**: Retrain PyTorch head with logged data
2. **Feature Engineering**: Add context features to improve accuracy
3. **A/B Testing**: Test threshold changes with controlled experiments
4. **Alerting**: Add alerts for performance degradation
5. **Visualization**: Create Grafana dashboards for monitoring

## References

- Schema: `/Users/ryandahlberg/Projects/cortex/coordination/schemas/routing-decision.json`
- Config: `/Users/ryandahlberg/Projects/cortex/coordination/routing/config.json`
- Tracker: `/Users/ryandahlberg/Projects/cortex/llm-mesh/lib/routing/performance_tracker.py`
- MoE Router: `/Users/ryandahlberg/Projects/cortex/llm-mesh/lib/integration/moe_ml_router.py`
