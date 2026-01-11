# Medallion Architecture

**Version:** 1.0
**Last Updated:** 2025-11-27

## Overview

The Medallion Architecture implements a Bronze → Silver → Gold data quality pipeline for Cortex coordination data. This pattern from Databricks provides clear data quality tiers and supports analytics, reporting, and ML model training.

## Architecture Layers

```
coordination/medallion/
├── bronze/              # Raw data ingestion
│   ├── events/          # Raw events
│   ├── raw-tasks/       # Raw task files
│   └── raw-metrics/     # Raw metrics
├── silver/              # Processed & validated
│   ├── processed-tasks/      # Validated, enriched tasks
│   ├── aggregated-metrics/   # Aggregated metrics
│   └── validated-lineage/    # Clean lineage events
└── gold/                # Analytics ready
    ├── analytics/       # Daily/weekly analytics
    ├── reports/         # Master reports
    └── kpis/            # Key performance indicators
```

## Data Flow

```
Raw Events → Bronze → Silver → Gold → Insights
    ↓          ↓         ↓        ↓
  Append    Validate  Aggregate  Report
```

## Layer Details

### Bronze Layer (Raw)

**Purpose**: Immutable raw data storage

**Characteristics**:
- Append-only (never modified)
- Preserves original format
- Includes ingestion timestamp
- No validation or transformation
- Complete audit trail

**Functions**:
```bash
source scripts/lib/medallion.sh

# Ingest raw event
ingest_to_bronze "task_created" '{"task_id": "task-001", "status": "queued"}'

# Ingest task file
ingest_task_to_bronze "task-001" "coordination/tasks/task-001.json"

# Ingest metrics
ingest_metrics_to_bronze "security-master" "coordination/metrics/security-master-metrics.jsonl"
```

**File Format**:
```json
{
  "task_id": "task-001",
  "status": "queued",
  "ingested_at": "2025-11-27T10:00:00-0600",
  "layer": "bronze",
  "source_file": "coordination/tasks/task-001.json"
}
```

### Silver Layer (Processed)

**Purpose**: Clean, validated, enriched data

**Characteristics**:
- Schema validated
- Null handling
- Deduplication
- Computed fields added
- Type conversions
- Business logic applied

**Functions**:
```bash
# Process tasks: validate schema, add computed fields
process_tasks_to_silver "20251127"

# Aggregate metrics by type
aggregate_metrics_to_silver "security-master" "20251127"

# Validate and clean lineage
validate_lineage_to_silver "20251127"
```

**Transformations**:
- **Validation**: Check required fields exist
- **Enrichment**: Add `duration_seconds`, `is_success`, `is_failure`
- **Deduplication**: Remove duplicate events
- **Sorting**: Order by timestamp

**File Format**:
```json
{
  "task_id": "task-001",
  "status": "completed",
  "layer": "silver",
  "processed_at": "2025-11-27T11:00:00-0600",
  "duration_seconds": 45.3,
  "is_success": true,
  "is_failure": false,
  "has_error": false
}
```

### Gold Layer (Analytics)

**Purpose**: Business-ready analytics and reports

**Characteristics**:
- Aggregated metrics
- KPIs calculated
- Reports generated
- Optimized for queries
- Business context added

**Functions**:
```bash
# Generate daily analytics
generate_daily_analytics "20251127"

# Generate KPIs for date range
generate_kpis "20251120" "20251127"

# Generate master-specific report
generate_master_report "security-master" "20251127"
```

**Daily Analytics Output**:
```json
{
  "date": "20251127",
  "layer": "gold",
  "summary": {
    "total_tasks": 150,
    "completed_tasks": 143,
    "failed_tasks": 7,
    "completion_rate": 95.3,
    "avg_duration_seconds": 42.5
  },
  "by_master": [
    {
      "master": "security-master",
      "total": 45,
      "completed": 43,
      "completion_rate": 95.6
    }
  ],
  "performance": {
    "p50_duration": 38.2,
    "p95_duration": 78.5,
    "p99_duration": 120.3
  }
}
```

## Complete Pipeline

Run full medallion pipeline for a date:

```bash
source scripts/lib/medallion.sh

# Initialize (first time only)
init_medallion

# Run complete pipeline
run_medallion_pipeline "20251127"
```

Pipeline steps:
1. Process bronze tasks → silver
2. Validate bronze lineage → silver
3. Generate daily analytics → gold

## Use Cases

### 1. Daily Reporting

```bash
# Generate daily report
generate_daily_analytics $(date +%Y%m%d)

# View results
cat coordination/medallion/gold/analytics/daily-$(date +%Y%m%d).json | jq '.summary'
```

### 2. Master Performance Analysis

```bash
# Generate report for specific master
generate_master_report "security-master" $(date +%Y%m%d)

# View metrics
cat coordination/medallion/gold/reports/security-master-$(date +%Y%m%d).json | jq '.metrics'
```

### 3. KPI Tracking

```bash
# Weekly KPIs
start_date=$(date -d '7 days ago' +%Y%m%d)
end_date=$(date +%Y%m%d)

generate_kpis "$start_date" "$end_date"
```

### 4. ML Model Training

```bash
# Silver layer has clean data for training
cat coordination/medallion/silver/processed-tasks/*.jsonl | \
    jq -c 'select(.is_success == true) | {
        task_description: .description,
        duration: .duration_seconds,
        master: .master
    }' > training_data.jsonl
```

### 5. Audit Trail

```bash
# Bronze layer has complete raw history
cat coordination/medallion/bronze/raw-tasks/*.jsonl | \
    jq -c 'select(.task_id == "task-001")'
```

## Data Quality Rules

### Bronze → Silver Promotion

**Required Fields**:
- `task_id` must not be null
- `status` must not be null
- `timestamp` must be valid ISO 8601

**Enrichment**:
- Calculate `duration_seconds` if `created_at` and `completed_at` exist
- Add boolean flags: `is_success`, `is_failure`, `has_error`

**Validation**:
- Remove duplicate events (by task_id + timestamp)
- Sort by timestamp
- Schema validation against coordination/schemas/

### Silver → Gold Promotion

**Aggregation**:
- Group by master, status, date
- Calculate summary statistics (count, avg, min, max)
- Compute percentiles (p50, p95, p99)

**Business Logic**:
- Completion rate = completed / total * 100
- Success rate excludes cancelled tasks
- Performance buckets: fast (<30s), normal (30-60s), slow (>60s)

## Scheduled Processing

Automate medallion pipeline with cron:

```bash
# Add to crontab
0 1 * * * cd /path/to/cortex && bash scripts/lib/medallion.sh run_medallion_pipeline $(date +%Y%m%d)
```

Or create daemon:

```bash
#!/bin/bash
# scripts/daemons/medallion-daemon.sh

while true; do
    date_today=$(date +%Y%m%d)

    source scripts/lib/medallion.sh
    run_medallion_pipeline "$date_today"

    # Run once per day
    sleep 86400
done
```

## Performance Considerations

**Bronze Layer**:
- Append-only is fast
- No indexes needed
- Partitioned by date for efficient reads

**Silver Layer**:
- Process in batches (daily recommended)
- Use jq streaming for large files
- Parallel processing possible

**Gold Layer**:
- Pre-computed aggregations
- Fast query performance
- Optimized for dashboards

## Best Practices

1. **Immutability**: Never modify bronze layer
2. **Idempotency**: Pipeline should be re-runnable
3. **Partitioning**: Partition by date for manageability
4. **Retention**: Keep bronze for 90 days, silver for 30 days, gold forever
5. **Validation**: Always validate silver before promoting to gold
6. **Documentation**: Document transformations and business logic

## Integration Points

### With Lineage Tracking

```bash
# Lineage events → Bronze
source scripts/lib/lineage.sh
source scripts/lib/medallion.sh

log_task_event "task-001" "task_completed" "{}"

# Copy to bronze
ingest_to_bronze "lineage" "$(get_latest_lineage_event)"
```

### With Metrics

```bash
# Metrics → Bronze
emit_master_metric "security-master" "tasks_completed" 1

# Daily aggregation → Silver → Gold
aggregate_metrics_to_silver "security-master" $(date +%Y%m%d)
```

### With Evaluation Framework

```bash
# Gold analytics → Evaluation
cat coordination/medallion/gold/analytics/daily-*.json | \
    jq '.summary.completion_rate' | \
    awk '{sum+=$1; count++} END {print "Avg completion rate:", sum/count "%"}'
```

## Troubleshooting

### Missing Data in Silver

- Check bronze layer has data for that date
- Verify processing completed without errors
- Check file permissions

### Incorrect Aggregations

- Validate input data in silver layer
- Check for null values in critical fields
- Review business logic in jq queries

### Performance Issues

- Process smaller date ranges
- Use jq streaming mode for large files
- Consider parallel processing

## Future Enhancements

- Automated data quality monitoring
- Schema evolution tracking
- Incremental processing (only new data)
- Cross-environment aggregation
- Real-time silver processing (streaming)
- Data lineage visualization
