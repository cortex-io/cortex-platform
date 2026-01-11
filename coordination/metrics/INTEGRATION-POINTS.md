# Metrics Framework Integration Points

## Overview

This document describes how to integrate the production metrics framework into various components of the cortex system. The framework is designed to be non-invasive and can be integrated incrementally without disrupting existing functionality.

**Status**: Ready for integration (documentation only - do not integrate yet)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Metrics Framework                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  scripts/lib/metrics.sh (Emission Functions)                 │
│          ↓                                                    │
│  coordination/observability/metrics/raw/*.jsonl              │
│          ↓                                                    │
│  scripts/aggregate-metrics.sh (Daily Summaries)              │
│          ↓                                                    │
│  coordination/metrics/aggregates/*.json                      │
│          ↓                                                    │
│  scripts/show-metrics.sh (Dashboard)                         │
│  scripts/check-alerts.sh (Alerting)                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Core Functions

### Metric Emission Functions

Located in `/Users/ryandahlberg/Projects/cortex/scripts/lib/metrics.sh`:

```bash
# Generic master metric
emit_master_metric <master_id> <metric_name> <value> [dimensions_json] [unit]

# Task processing
emit_task_processing_time <task_id> <duration_ms> [task_type] [master_id]

# Token usage
emit_token_usage <entity_id> <tokens_used> <entity_type> [operation]

# Worker lifecycle
emit_worker_spawn_result <worker_id> <result> [dimensions_json]
emit_worker_completion <worker_id> <duration_ms> <status> [tokens_used]

# Master coordination
emit_master_handoff <from_master> <to_master> <task_id> <success>

# Routing decisions
emit_routing_decision <task_id> <selected_master> <confidence> [method]

# System health
emit_system_health <component> <health_score> [details_json]

# RAG operations
emit_rag_retrieval <retrieval_time_ms> <num_results> <query_type>

# Alerts
emit_alert <alert_type> <severity> <message> [dimensions_json]
```

## Integration Points by Component

### 1. Master Agents (Development, Security, Inventory, CI/CD, Coordinator)

**Files to modify**:
- `scripts/run-*-master.sh`
- Master-specific worker spawning scripts

**Integration**:

```bash
#!/usr/bin/env bash
# In each master script

# Source metrics library
source "scripts/lib/metrics.sh"

MASTER_ID="development-master"  # or security-master, etc.

# At task start
task_start_time=$(date +%s%3N)

# ... process task ...

# At task completion
task_end_time=$(date +%s%3N)
task_duration=$((task_end_time - task_start_time))
emit_task_processing_time "$task_id" "$task_duration" "$task_type" "$MASTER_ID"

# When spawning workers
worker_id=$(generate_worker_id)
if spawn_worker "$worker_id" "$worker_spec"; then
    emit_worker_spawn_result "$worker_id" "success" '{"worker_type":"scan"}'
else
    emit_worker_spawn_result "$worker_id" "failed" '{"worker_type":"scan"}'
fi

# On worker completion
emit_worker_completion "$worker_id" "$worker_duration" "completed" "$tokens_used"

# Generic master metrics
emit_master_metric "$MASTER_ID" "custom_operation" 1 '{"operation_type":"analysis"}'
```

**Recommended metrics per master**:

| Master | Key Metrics |
|--------|-------------|
| Development | task_processing_time, worker_spawns, code_quality_score |
| Security | vulnerabilities_detected, scan_duration, false_positive_rate |
| Inventory | repos_scanned, files_indexed, inventory_freshness |
| CI/CD | deployments, pipeline_duration, success_rate |
| Coordinator | routing_decisions, routing_confidence, handoff_success_rate |

### 2. Worker Spawning & Management

**Files to modify**:
- `scripts/lib/worker-spec-builder.sh`
- `scripts/spawn-worker.sh`

**Integration**:

```bash
# In worker spawning logic
spawn_start=$(date +%s%3N)

worker_id=$(create_worker "$spec")
spawn_end=$(date +%s%3N)
spawn_duration=$((spawn_end - spawn_start))

if [[ -n "$worker_id" ]]; then
    emit_worker_spawn_result "$worker_id" "success" "{\"worker_type\":\"$worker_type\",\"spawn_time_ms\":$spawn_duration}"
else
    emit_worker_spawn_result "unknown" "failed" "{\"worker_type\":\"$worker_type\",\"error\":\"spawn_failed\"}"
fi

# In worker completion handlers
emit_worker_completion "$worker_id" "$duration_ms" "$final_status" "$tokens_consumed"
```

### 3. Coordinator Master - Routing

**Files to modify**:
- `coordination/masters/coordinator/route-task.sh`
- Hybrid routing scripts

**Integration**:

```bash
# After routing decision
emit_routing_decision "$task_id" "$selected_master" "$confidence" "$routing_method"

# After handoff attempt
if handoff_successful; then
    emit_master_handoff "$coordinator_master" "$selected_master" "$task_id" "true"
else
    emit_master_handoff "$coordinator_master" "$selected_master" "$task_id" "false"
fi
```

### 4. Token Budget Tracking

**Files to modify**:
- `scripts/lib/token-budget.sh`
- Worker execution scripts

**Integration**:

```bash
# After token consumption
emit_token_usage "$entity_id" "$tokens_consumed" "$entity_type" "$operation"

# Check token budget health
remaining_tokens=$(get_remaining_budget)
total_budget=$(get_total_budget)
budget_health=$(echo "scale=2; ($remaining_tokens / $total_budget) * 100" | bc)

emit_system_health "token_budget" "$budget_health" "{\"remaining\":$remaining_tokens,\"total\":$total_budget}"
```

### 5. RAG System

**Files to modify**:
- `scripts/lib/rag/*.sh`
- Semantic search scripts

**Integration**:

```bash
# RAG retrieval timing
retrieval_start=$(date +%s%3N)

results=$(perform_semantic_search "$query")

retrieval_end=$(date +%s%3N)
retrieval_time=$((retrieval_end - retrieval_start))
num_results=$(echo "$results" | jq 'length')

emit_rag_retrieval "$retrieval_time" "$num_results" "semantic"
```

### 6. Health Monitoring

**Files to modify**:
- Health check scripts
- System monitoring daemons

**Integration**:

```bash
# System component health
component="worker_pool"
health_score=$(calculate_component_health)

emit_system_health "$component" "$health_score" "{\"active_workers\":$active,\"failed\":$failed}"
```

### 7. Process Manager (PM)

**Files to modify**:
- `scripts/pm-daemon.sh`
- Process monitoring scripts

**Integration**:

```bash
# PM cycle metrics
cycle_start=$(date +%s%3N)

# ... perform PM operations ...

cycle_end=$(date +%s%3N)
cycle_duration=$((cycle_end - cycle_start))

emit_master_metric "process-manager" "pm_cycle_duration" "$cycle_duration" "{\"cycle_number\":$cycle_num}" "milliseconds"
```

## Aggregation & Reporting

### Daily Aggregation

Run daily via cron or systemd timer:

```bash
# Aggregate yesterday's metrics
./scripts/aggregate-metrics.sh --yesterday

# Or aggregate specific date
./scripts/aggregate-metrics.sh 2025-11-27

# Aggregate all historical data
./scripts/aggregate-metrics.sh --all
```

**Recommended schedule**: Daily at 00:05 UTC

### Dashboard Viewing

```bash
# View system summary
./scripts/show-metrics.sh --summary

# View specific master
./scripts/show-metrics.sh --master development --period 48

# View worker performance
./scripts/show-metrics.sh --workers --period 24

# View as JSON for external tools
./scripts/show-metrics.sh --summary --json | jq '.'

# Live dashboard (updates every 5 seconds)
./scripts/show-metrics.sh --live
```

### Alert Monitoring

Run periodically via cron (every 5-15 minutes):

```bash
# Check all alert conditions
./scripts/check-alerts.sh --check-all

# Check only critical conditions
./scripts/check-alerts.sh --critical-only

# Resolve specific alert
./scripts/check-alerts.sh --resolve alert-12345

# Clear all active alerts
./scripts/check-alerts.sh --clear-all
```

**Recommended schedule**: Every 5 minutes

## Deployment Strategy

### Phase 1: Non-Critical Instrumentation (Week 1)
- Integrate metrics into dashboard scripts (no runtime impact)
- Add metrics to non-critical paths (reporting, analytics)
- Test metric emission without impacting core operations

### Phase 2: Worker Metrics (Week 2)
- Instrument worker spawning
- Add worker completion metrics
- Monitor worker performance

### Phase 3: Master Metrics (Week 3)
- Instrument coordinator routing
- Add development master metrics
- Instrument security, inventory, CI/CD masters

### Phase 4: System-Wide (Week 4)
- Full token budget tracking
- RAG performance metrics
- Health monitoring integration
- Enable automated alerting

### Phase 5: Production Observability (Week 5)
- Daily aggregation automation
- Alert response procedures
- Dashboard monitoring
- Metric-driven optimization

## Configuration

### Alert Thresholds

Create `/Users/ryandahlberg/Projects/cortex/coordination/config/alert-thresholds.json`:

```json
{
  "task_processing": {
    "sla_ms": 300000,
    "warning_ms": 240000
  },
  "token_usage": {
    "high_threshold": 50000,
    "critical_threshold": 100000
  },
  "worker_spawns": {
    "failure_rate_threshold": 0.2,
    "critical_failure_rate": 0.5
  },
  "system_health": {
    "low_threshold": 70,
    "critical_threshold": 50
  },
  "routing": {
    "low_confidence_threshold": 0.5,
    "critical_confidence_threshold": 0.3
  },
  "handoffs": {
    "failure_rate_threshold": 0.1
  },
  "rag": {
    "slow_retrieval_ms": 5000
  }
}
```

### Metric Retention

Configure in environment or config:

```bash
export METRICS_RETENTION_DAYS=30        # Raw metrics
export METRICS_HOURLY_RETENTION_DAYS=90 # Hourly rollups
export METRICS_DAILY_RETENTION_DAYS=365 # Daily summaries
```

## Performance Considerations

### Overhead

- Metric emission: <5ms per call (target)
- Disk I/O: Append-only writes (minimal impact)
- Aggregation: Run during low-traffic periods
- Queries: Use indices for fast lookups

### Best Practices

1. **Batch metrics**: Emit multiple related metrics together
2. **Use dimensions**: Leverage dimensions for filtering instead of creating many metrics
3. **Sample high-frequency metrics**: For very high-frequency events, sample at 10-20%
4. **Async updates**: Index updates run in background
5. **Partition data**: Daily partitioned files prevent large file operations

## Monitoring the Monitors

The metrics framework itself should be monitored:

```bash
# Check metrics collection health
ls -lh coordination/observability/metrics/raw/

# Check aggregation health
ls -lh coordination/metrics/aggregates/daily/

# Verify alert system
cat coordination/metrics/alerts/active-alerts.json | jq '.alerts | length'

# Monitor metric emission rate
wc -l coordination/observability/metrics/raw/metrics-$(date +%Y-%m-%d).jsonl
```

## Example Integration: Development Master

Complete example for development master:

```bash
#!/usr/bin/env bash
# scripts/run-development-master.sh (with metrics)

set -euo pipefail

# Source libraries
source "scripts/lib/metrics.sh"
source "scripts/lib/token-budget.sh"

readonly MASTER_ID="development-master"

# Main execution loop
main() {
    local task_id="$1"

    # Start timing
    local task_start=$(date +%s%3N)

    # Check task type
    local task_type=$(jq -r '.task_type' "coordination/tasks/${task_id}.json")

    # Process task
    if process_development_task "$task_id" "$task_type"; then
        local task_end=$(date +%s%3N)
        local duration=$((task_end - task_start))

        # Emit success metrics
        emit_task_processing_time "$task_id" "$duration" "$task_type" "$MASTER_ID"
        emit_master_metric "$MASTER_ID" "tasks_completed" 1 "{\"task_type\":\"$task_type\"}"

        # Update system health
        emit_system_health "$MASTER_ID" 100 "{\"status\":\"healthy\"}"
    else
        # Emit failure metrics
        emit_alert "task_processing_failed" "high" \
            "Development master failed to process task $task_id" \
            "{\"task_id\":\"$task_id\",\"task_type\":\"$task_type\"}"
    fi
}

# Process development task
process_development_task() {
    local task_id="$1"
    local task_type="$2"

    # Spawn worker
    local worker_id="dev-worker-$(uuidgen)"
    local spawn_start=$(date +%s%3N)

    if spawn_development_worker "$worker_id" "$task_id"; then
        local spawn_end=$(date +%s%3N)
        local spawn_time=$((spawn_end - spawn_start))

        emit_worker_spawn_result "$worker_id" "success" \
            "{\"worker_type\":\"feature-implementer\",\"spawn_time_ms\":$spawn_time}"

        # Monitor worker completion
        monitor_worker_completion "$worker_id"
    else
        emit_worker_spawn_result "$worker_id" "failed" \
            "{\"worker_type\":\"feature-implementer\"}"
        return 1
    fi
}

# Monitor worker completion
monitor_worker_completion() {
    local worker_id="$1"
    local worker_start=$(date +%s%3N)

    # Wait for completion...

    local worker_end=$(date +%s%3N)
    local worker_duration=$((worker_end - worker_start))
    local tokens_used=$(get_worker_token_usage "$worker_id")

    emit_worker_completion "$worker_id" "$worker_duration" "completed" "$tokens_used"
    emit_token_usage "$worker_id" "$tokens_used" "worker" "feature_implementation"
}

main "$@"
```

## Testing

Before integration, test metric emission:

```bash
# Test metric emission
source scripts/lib/metrics.sh

# Emit test metrics
emit_master_metric "test-master" "test_metric" 100 '{"test":"true"}'
emit_task_processing_time "test-task-123" 5000 "test" "test-master"
emit_worker_spawn_result "test-worker-456" "success" '{"worker_type":"test"}'

# Verify emission
tail -5 coordination/observability/metrics/raw/metrics-$(date +%Y-%m-%d).jsonl | jq '.'

# Test aggregation
./scripts/aggregate-metrics.sh --today

# View results
./scripts/show-metrics.sh --summary --period 1
```

## Troubleshooting

### No metrics appearing

```bash
# Check ENABLE_METRICS flag
echo $ENABLE_METRICS  # should be "true"

# Check directory permissions
ls -ld coordination/observability/metrics/raw/

# Check for errors in metric emission
set -x  # Enable debug mode
source scripts/lib/metrics.sh
emit_master_metric "test" "test" 1
set +x
```

### Aggregation fails

```bash
# Check for malformed JSON
jq empty coordination/observability/metrics/raw/metrics-$(date +%Y-%m-%d).jsonl

# Run with verbose output
bash -x scripts/aggregate-metrics.sh --today
```

### Dashboard shows no data

```bash
# Check if metrics files exist
ls -lh coordination/observability/metrics/raw/

# Verify aggregation ran
ls -lh coordination/metrics/aggregates/daily/

# Check date alignment
date  # Ensure system time is correct
```

## Next Steps

After reviewing this documentation:

1. Choose integration phase (recommend Phase 1)
2. Select components to instrument
3. Test in development environment
4. Monitor performance impact
5. Gradually roll out to production
6. Set up automated aggregation and alerting

## Support

For questions or issues:
- Review existing metrics collector: `scripts/lib/observability/metrics-collector.sh`
- Check system metrics: `scripts/lib/observability/system-metrics.sh`
- Examine current metric daemons: `scripts/daemons/metrics-aggregator-daemon.sh`
