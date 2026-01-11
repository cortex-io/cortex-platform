# Auto-Learning System

**Version:** 1.0
**Last Updated:** 2025-11-27

## Overview

The Auto-Learning System is a **continuous learning pipeline** that automatically improves Cortex by learning from its own task executions. As Cortex completes tasks, the system:

1. ✅ **Auto-collects** high-quality task outcomes
2. 📊 **Auto-generates** training data from medallion gold layer
3. 🤖 **Auto-triggers** fine-tuning when 1000+ examples collected
4. 🚀 **Auto-deploys** fine-tuned models with A/B testing
5. 📈 **Auto-promotes** models that outperform baselines

**This makes Cortex self-improving with zero manual intervention.**

---

## Architecture

```
Task Execution
      ↓
Medallion Pipeline (Bronze → Silver → Gold)
      ↓
HQ Outcome Collector (quality filter)
      ↓
Training Data Pipeline (1000+ examples)
      ↓
Auto-Fine-Tuning (triggered automatically)
      ↓
Auto-Deployment (challenger with 10% traffic)
      ↓
A/B Testing (champion vs challenger)
      ↓
Auto-Promotion (if >5% improvement)
```

---

## Components

### 1. High-Quality Outcome Collector

**Location:** `llm-mesh/auto-learning/hq-outcome-collector.py`

**Purpose:** Automatically identifies and collects high-quality task outcomes for training

**Quality Criteria:**
- ✅ Task completed successfully
- ✅ Has meaningful output
- ✅ Quality score ≥ 4.0 (on 1-5 scale)
- ✅ Duration in reasonable range (10-600 seconds)
- ✅ No errors or retries

**Output:**
- `llm-mesh/auto-learning/hq-outcomes/training/` - 80% of HQ tasks
- `llm-mesh/auto-learning/hq-outcomes/validation/` - 20% of HQ tasks
- Train/val split is deterministic based on task_id hash

**Usage:**
```bash
# Manual collection from yesterday's silver data
python3 llm-mesh/auto-learning/hq-outcome-collector.py

# Automatic collection (runs hourly via daemon)
scripts/daemons/auto-learning-daemon.sh
```

**Example Output:**
```
Total tasks processed: 250
High-quality tasks: 42
  - Training: 34
  - Validation: 8

Rejection reasons:
  Quality score too low: 98
  Too fast (trivial): 45
  No output: 32
  Not successful: 33
```

---

### 2. Auto-Fine-Tuning System

**Location:** `llm-mesh/auto-learning/auto-fine-tune.py`

**Purpose:** Automatically triggers fine-tuning when enough data is collected

**Threshold:** 1000+ high-quality training examples

**Process:**
1. Checks training data readiness
2. Prepares data in Claude fine-tuning format
3. Creates fine-tuning configuration
4. Triggers training job (when API integration added)
5. Monitors training progress

**Usage:**
```bash
# Check status
python3 llm-mesh/auto-learning/auto-fine-tune.py status

# Output:
{
  "data_collection": {
    "training_examples": 1250,
    "min_required": 1000,
    "ready": true,
    "progress_percent": 100
  },
  "fine_tuning": {
    "has_triggered": false,
    "models_trained": 0
  },
  "cost_estimate": {
    "example_count": 1250,
    "estimated_tokens": 625000,
    "estimated_cost_usd": 0.63
  }
}

# Trigger fine-tuning
python3 llm-mesh/auto-learning/auto-fine-tune.py trigger
```

---

### 3. Auto-Deployment System

**Location:** `llm-mesh/auto-learning/auto-deploy.sh`

**Purpose:** Automatically deploys fine-tuned models with A/B testing

**Deployment Strategy:**
1. Deploy fine-tuned model as **challenger**
2. Start A/B test: **90% champion, 10% challenger**
3. Monitor performance (100+ tasks per variant)
4. Auto-promote if challenger improves:
   - Quality score: +0.2 or more
   - Completion rate: +5% or more

**Usage:**
```bash
# Deploy fine-tuned model
./llm-mesh/auto-learning/auto-deploy.sh deploy <model_id> <master_name>

# Example:
./llm-mesh/auto-learning/auto-deploy.sh deploy ft-20251127-001 security-master

# Check if ready to promote
./llm-mesh/auto-learning/auto-deploy.sh check security-master-ft-20251127-001 security-master
```

**Auto-Promotion Decision:**
```bash
# Automatically checks:
if quality_improvement > 0.2 AND completion_improvement > 5%; then
    promote_challenger_to_champion
fi
```

---

### 4. Auto-Learning Daemon

**Location:** `scripts/daemons/auto-learning-daemon.sh`

**Purpose:** Continuously orchestrates the entire auto-learning pipeline

**Tasks:**
1. **Hourly:** Collect HQ outcomes from medallion silver layer
2. **Daily:** Check fine-tuning readiness, trigger if 1000+ examples
3. **Daily 2 AM:** Run medallion pipeline (Bronze → Silver → Gold)
4. **Every 6 hours:** Log status and progress

**Start Daemon:**
```bash
./scripts/daemons/auto-learning-daemon.sh &

# Or add to daemon-control.sh
./scripts/daemon-control.sh start auto-learning-daemon
```

**Logs:**
```bash
tail -f coordination/logs/auto-learning-daemon.log
```

---

## Complete Workflow Example

### Day 1-30: Data Collection Phase

```bash
# Start auto-learning daemon
./scripts/daemons/auto-learning-daemon.sh &

# Daemon automatically:
# - Collects HQ outcomes hourly
# - Processes medallion pipeline daily
# - Checks progress daily
```

**Progress:**
```
Day 1:  50 HQ tasks collected (5% progress)
Day 7:  350 HQ tasks collected (35% progress)
Day 15: 750 HQ tasks collected (75% progress)
Day 20: 1000 HQ tasks collected (100% progress) ✅
```

### Day 20: Auto-Fine-Tuning Triggered

```bash
# Daemon detects 1000+ examples and automatically:
# 1. Prepares training data
# 2. Creates fine-tuning config
# 3. Triggers fine-tuning job (via API)
# 4. Monitors progress
```

**Fine-Tuning Output:**
```
📋 Fine-tuning configuration:
{
  "model_base": "claude-3-haiku-20240307",
  "training_examples": 1250,
  "validation_split": 0.2,
  "hyperparameters": {
    "n_epochs": 3,
    "batch_size": 32
  }
}

🎯 Fine-tuning triggered!
Model ID: ft-20251127-001
Estimated completion: 2-4 hours
Estimated cost: $0.63
```

### Day 20 (4 hours later): Auto-Deployment

```bash
# Fine-tuning complete, daemon automatically:
# 1. Deploys as challenger
# 2. Starts A/B test (90/10 split)
```

**Deployment Output:**
```
✅ Deployed ft-20251127-001 as challenger
A/B test started: security-master-ft-20251127-001
  Champion (v1.0.0): 90%
  Challenger (ft-20251127-001): 10%
```

### Days 21-25: A/B Testing Phase

```bash
# Daemon monitors A/B test results:
# - Challenger handles 10% of security tasks
# - Champion handles 90% of security tasks
# - Both collect performance metrics
```

**After 100+ tasks per variant:**
```json
{
  "variants": {
    "a": {
      "name": "v1.0.0",
      "tasks_completed": 450,
      "completion_rate": 92.5,
      "avg_quality": 4.1
    },
    "b": {
      "name": "ft-20251127-001",
      "tasks_completed": 55,
      "completion_rate": 98.2,
      "avg_quality": 4.4
    }
  }
}

Analysis:
  Quality improvement: +0.3 (>0.2 required) ✅
  Completion improvement: +5.7% (>5% required) ✅

Decision: AUTO-PROMOTE ✅
```

### Day 25: Auto-Promotion

```bash
# Daemon detects significant improvement and automatically:
# 1. Stops A/B test
# 2. Promotes challenger → champion
# 3. Logs promotion event
```

**Promotion Output:**
```
🎉 Fine-tuned model outperforms baseline!
Auto-promoting challenger to champion...

Promoted ft-20251127-001 to champion for security-master
Previous champion: v1.0.0

✅ Auto-promotion complete!
```

---

## Monitoring & Metrics

### Check Auto-Learning Status

```bash
# Overall status
python3 llm-mesh/auto-learning/auto-fine-tune.py status | jq '
{
  progress: .data_collection.progress_percent,
  examples: .data_collection.training_examples,
  ready: .data_collection.ready,
  cost: .cost_estimate.estimated_cost_usd
}'

# Output:
{
  "progress": 100,
  "examples": 1250,
  "ready": true,
  "cost": 0.63
}
```

### Check A/B Test Performance

```bash
source scripts/lib/ab-testing.sh
get_ab_summary "security-master-ft-20251127-001"
```

### View Auto-Learning Events

```bash
# All auto-learning events
cat coordination/logs/auto-learning-events.jsonl | jq '.'

# Recent promotions
cat coordination/logs/auto-learning-events.jsonl | \
    jq 'select(.event == "auto_promotion")'
```

---

## Configuration

### Adjust Quality Thresholds

Edit `llm-mesh/auto-learning/hq-outcome-collector.py`:

```python
# Minimum quality score (1-5)
MIN_QUALITY_SCORE = 4.0  # Raise to 4.5 for stricter filtering

# Duration range
MIN_DURATION_SECONDS = 10  # Filter out trivial tasks
MAX_DURATION_SECONDS = 600  # Filter out timeouts
```

### Adjust Fine-Tuning Threshold

Edit `llm-mesh/auto-learning/auto-fine-tune.py`:

```python
# Minimum training examples before fine-tuning
MIN_TRAINING_EXAMPLES = 1000  # Increase to 2000 for more data
```

### Adjust Promotion Criteria

Edit `llm-mesh/auto-learning/auto-deploy.sh`:

```bash
# Challenger must improve by:
quality_improvement > 0.2      # +0.2 quality score
completion_improvement > 5     # +5% completion rate
```

---

## Cost Estimation

### Training Data Collection
- **Cost:** $0 (uses existing task data)
- **Storage:** ~100MB per 1000 examples

### Fine-Tuning
- **Frequency:** Once per 1000 new HQ tasks
- **Cost:** ~$0.50-$1.00 per 1000 examples
- **Time:** 2-4 hours per model

### A/B Testing
- **Cost:** 10% traffic to challenger (minimal overhead)
- **Duration:** 3-5 days for 100+ tasks per variant

### Total Monthly Cost (Estimated)
- Collecting 1000 HQ tasks/month
- 1 fine-tuning run/month
- 1-2 A/B tests/month

**Total: ~$1-2/month** for continuous improvement

---

## Benefits

### Continuous Improvement
- System learns from every task
- Quality improves over time
- No manual data labeling needed

### Zero Manual Intervention
- Automatic data collection
- Automatic training triggers
- Automatic deployment
- Automatic promotion decisions

### Safe Deployment
- A/B testing before promotion
- 10% traffic to challenger initially
- Auto-rollback if performance degrades
- Champion always available as fallback

### Cost Effective
- Uses existing task data (no labeling cost)
- Fine-tunes smallest model first (Haiku)
- Only promotes if significant improvement
- Training cost amortized over many tasks

---

## Future Enhancements

1. **Multi-Model Fine-Tuning**
   - Fine-tune per master (security, development, etc.)
   - Specialized models for specialized tasks

2. **Active Learning**
   - Prioritize collecting data from underperforming areas
   - Request human feedback for edge cases

3. **Continuous Fine-Tuning**
   - Incremental updates instead of full retraining
   - Faster iteration cycles

4. **Performance Prediction**
   - Predict fine-tuned model performance before deployment
   - Skip deployment if unlikely to improve

5. **Multi-Objective Optimization**
   - Optimize for quality, speed, and cost simultaneously
   - Pareto-optimal model selection

---

## Troubleshooting

### Not Collecting HQ Outcomes

**Check:**
1. Medallion pipeline running? `ls coordination/medallion/silver/processed-tasks/`
2. Tasks have quality scores? `jq '.quality_score' coordination/medallion/silver/processed-tasks/*.jsonl | head`
3. Quality threshold too high? Lower `MIN_QUALITY_SCORE`

### Fine-Tuning Not Triggering

**Check:**
1. Enough training examples? `python3 llm-mesh/auto-learning/auto-fine-tune.py status`
2. Daemon running? `ps aux | grep auto-learning-daemon`
3. Already triggered? Check `.fine_tune_trigger` file

### Auto-Promotion Not Happening

**Check:**
1. Enough A/B test data? Need 100+ tasks per variant
2. Improvement significant enough? Check metrics
3. Review criteria in `auto-deploy.sh`

---

**The Auto-Learning System makes Cortex self-improving! 🚀**
