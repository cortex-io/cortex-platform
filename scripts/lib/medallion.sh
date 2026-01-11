#!/usr/bin/env bash
# Medallion Architecture for Cortex
# Bronze (raw) → Silver (processed) → Gold (analytics)

set -euo pipefail

# Prevent re-sourcing
if [ -n "${MEDALLION_LIB_LOADED:-}" ]; then
    return 0
fi
MEDALLION_LIB_LOADED=1

# ==============================================================================
# CONFIGURATION
# ==============================================================================

readonly MEDALLION_BASE="coordination/medallion"
readonly BRONZE_DIR="$MEDALLION_BASE/bronze"
readonly SILVER_DIR="$MEDALLION_BASE/silver"
readonly GOLD_DIR="$MEDALLION_BASE/gold"

# ==============================================================================
# BRONZE LAYER - Raw Data Ingestion
# ==============================================================================

# Ingest raw event to bronze layer
# Args: $1=event_type, $2=event_data (JSON string)
ingest_to_bronze() {
    local event_type="$1"
    local event_data="$2"

    local bronze_file="$BRONZE_DIR/events/${event_type}.jsonl"

    # Add timestamp and append
    echo "$event_data" | jq '. + {
        ingested_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
        layer: "bronze"
    }' >> "$bronze_file"
}

# Ingest raw task to bronze layer
ingest_task_to_bronze() {
    local task_id="$1"
    local task_file="$2"

    local bronze_file="$BRONZE_DIR/raw-tasks/$(date +%Y%m%d).jsonl"

    # Copy task with metadata
    jq '. + {
        ingested_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
        layer: "bronze",
        source_file: "'$task_file'"
    }' "$task_file" >> "$bronze_file"
}

# Ingest raw metrics to bronze layer
ingest_metrics_to_bronze() {
    local master_name="$1"
    local metrics_file="$2"

    local bronze_file="$BRONZE_DIR/raw-metrics/${master_name}-$(date +%Y%m%d).jsonl"

    # Append all metrics
    cat "$metrics_file" | jq '. + {
        ingested_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
        layer: "bronze"
    }' >> "$bronze_file"
}

# ==============================================================================
# SILVER LAYER - Data Processing & Validation
# ==============================================================================

# Process bronze tasks to silver (validated, enriched)
process_tasks_to_silver() {
    local date_filter="${1:-$(date +%Y%m%d)}"

    local bronze_file="$BRONZE_DIR/raw-tasks/${date_filter}.jsonl"
    local silver_file="$SILVER_DIR/processed-tasks/${date_filter}.jsonl"

    if [[ ! -f "$bronze_file" ]]; then
        echo "No bronze tasks found for date: $date_filter" >&2
        return 1
    fi

    # Process each task: validate schema, enrich with computed fields
    cat "$bronze_file" | jq -c '
        # Validate required fields
        select(.task_id != null and .status != null) |
        # Enrich with computed fields
        . + {
            layer: "silver",
            processed_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
            duration_seconds: (
                if .completed_at and .created_at then
                    (((.completed_at | fromdateiso8601) - (.created_at | fromdateiso8601)))
                else null end
            ),
            is_success: (.status == "completed"),
            is_failure: (.status == "failed"),
            has_error: (.error != null)
        }
    ' > "$silver_file"

    local count=$(wc -l < "$silver_file")
    echo "Processed $count tasks to silver layer"
}

# Aggregate metrics to silver layer
aggregate_metrics_to_silver() {
    local master_name="$1"
    local date_filter="${2:-$(date +%Y%m%d)}"

    local bronze_file="$BRONZE_DIR/raw-metrics/${master_name}-${date_filter}.jsonl"
    local silver_file="$SILVER_DIR/aggregated-metrics/${master_name}-${date_filter}.json"

    if [[ ! -f "$bronze_file" ]]; then
        echo "No bronze metrics found for $master_name on $date_filter" >&2
        return 1
    fi

    # Aggregate metrics by type
    cat "$bronze_file" | jq -s '
        group_by(.metric_name) | map({
            metric_name: .[0].metric_name,
            count: length,
            sum: (map(.metric_value | tonumber) | add),
            avg: (map(.metric_value | tonumber) | add / length),
            min: (map(.metric_value | tonumber) | min),
            max: (map(.metric_value | tonumber) | max),
            first_timestamp: (map(.timestamp) | min),
            last_timestamp: (map(.timestamp) | max)
        }) | {
            master: "'$master_name'",
            date: "'$date_filter'",
            layer: "silver",
            processed_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
            metrics: .
        }
    ' > "$silver_file"

    echo "Aggregated metrics for $master_name to silver layer"
}

# Validate lineage data to silver layer
validate_lineage_to_silver() {
    local date_filter="${1:-$(date +%Y%m%d)}"

    # Find all bronze lineage files for date
    local bronze_pattern="$BRONZE_DIR/events/lineage*.jsonl"
    local silver_file="$SILVER_DIR/validated-lineage/${date_filter}.jsonl"

    # Validate: ensure all required fields, remove duplicates, sort by timestamp
    cat $bronze_pattern 2>/dev/null | jq -c '
        select(
            .task_id != null and
            .event_type != null and
            .timestamp != null
        ) |
        . + {
            layer: "silver",
            validated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
        }
    ' | sort -u > "$silver_file"

    local count=$(wc -l < "$silver_file" 2>/dev/null || echo 0)
    echo "Validated $count lineage events to silver layer"
}

# ==============================================================================
# GOLD LAYER - Analytics & Reporting
# ==============================================================================

# Generate daily analytics (gold layer)
generate_daily_analytics() {
    local date_filter="${1:-$(date +%Y%m%d)}"

    local silver_tasks="$SILVER_DIR/processed-tasks/${date_filter}.jsonl"
    local gold_analytics="$GOLD_DIR/analytics/daily-${date_filter}.json"

    if [[ ! -f "$silver_tasks" ]]; then
        echo "No silver tasks found for date: $date_filter" >&2
        return 1
    fi

    # Generate comprehensive analytics
    cat "$silver_tasks" | jq -s '{
        date: "'$date_filter'",
        layer: "gold",
        generated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
        summary: {
            total_tasks: length,
            completed_tasks: (map(select(.is_success)) | length),
            failed_tasks: (map(select(.is_failure)) | length),
            completion_rate: (map(select(.is_success)) | length / length * 100),
            avg_duration_seconds: (
                map(select(.duration_seconds != null) | .duration_seconds) |
                if length > 0 then (add / length) else 0 end
            )
        },
        by_master: (
            group_by(.master) | map({
                master: .[0].master,
                total: length,
                completed: (map(select(.is_success)) | length),
                failed: (map(select(.is_failure)) | length),
                completion_rate: (map(select(.is_success)) | length / length * 100)
            })
        ),
        by_status: (
            group_by(.status) | map({
                status: .[0].status,
                count: length,
                percentage: (length / (reduce .[] as $x (0; . + 1)) * 100))
            })
        ),
        performance: {
            p50_duration: (
                map(select(.duration_seconds != null) | .duration_seconds) |
                sort | .[length / 2]
            ),
            p95_duration: (
                map(select(.duration_seconds != null) | .duration_seconds) |
                sort | .[length * 0.95 | floor]
            ),
            p99_duration: (
                map(select(.duration_seconds != null) | .duration_seconds) |
                sort | .[length * 0.99 | floor]
            )
        }
    }' > "$gold_analytics"

    echo "Generated daily analytics for $date_filter"
}

# Generate KPIs (gold layer)
generate_kpis() {
    local start_date="$1"
    local end_date="$2"

    local kpi_file="$GOLD_DIR/kpis/kpis-${start_date}-to-${end_date}.json"

    # Aggregate all daily analytics in date range
    echo '[]' | jq '.' > "$kpi_file"

    for analytics_file in "$GOLD_DIR/analytics"/daily-*.json; do
        if [[ -f "$analytics_file" ]]; then
            local file_date=$(basename "$analytics_file" | sed 's/daily-//;s/.json//')

            # Check if in date range
            if [[ "$file_date" -ge "$start_date" ]] && [[ "$file_date" -le "$end_date" ]]; then
                # Aggregate KPIs
                jq -s '
                    {
                        date_range: {
                            start: "'$start_date'",
                            end: "'$end_date'"
                        },
                        layer: "gold",
                        generated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
                        kpis: {
                            total_tasks: (map(.summary.total_tasks) | add),
                            avg_completion_rate: (map(.summary.completion_rate) | add / length),
                            avg_task_duration: (map(.summary.avg_duration_seconds) | add / length)
                        }
                    }
                ' "$analytics_file" > "$kpi_file"
            fi
        fi
    done

    echo "Generated KPIs for $start_date to $end_date"
}

# Generate master performance report (gold layer)
generate_master_report() {
    local master_name="$1"
    local date_filter="${2:-$(date +%Y%m%d)}"

    local silver_tasks="$SILVER_DIR/processed-tasks/${date_filter}.jsonl"
    local report_file="$GOLD_DIR/reports/${master_name}-${date_filter}.json"

    if [[ ! -f "$silver_tasks" ]]; then
        echo "No silver tasks found for date: $date_filter" >&2
        return 1
    fi

    # Generate master-specific report
    cat "$silver_tasks" | jq -s --arg master "$master_name" '
        map(select(.master == $master)) | {
            master: $master,
            date: "'$date_filter'",
            layer: "gold",
            generated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
            metrics: {
                total_tasks: length,
                completed: (map(select(.is_success)) | length),
                failed: (map(select(.is_failure)) | length),
                completion_rate: (
                    if length > 0 then
                        (map(select(.is_success)) | length / length * 100)
                    else 0 end
                ),
                avg_duration: (
                    map(select(.duration_seconds != null) | .duration_seconds) |
                    if length > 0 then (add / length) else 0 end
                )
            },
            task_list: map({
                task_id,
                status,
                duration_seconds,
                created_at,
                completed_at
            })
        }
    ' > "$report_file"

    echo "Generated report for $master_name on $date_filter"
}

# ==============================================================================
# PROMOTION PIPELINE
# ==============================================================================

# Run full medallion pipeline for a date
run_medallion_pipeline() {
    local date_filter="${1:-$(date +%Y%m%d)}"

    echo "=== Running Medallion Pipeline for $date_filter ==="

    echo "Step 1: Processing tasks to silver..."
    process_tasks_to_silver "$date_filter"

    echo "Step 2: Validating lineage to silver..."
    validate_lineage_to_silver "$date_filter"

    echo "Step 3: Generating daily analytics (gold)..."
    generate_daily_analytics "$date_filter"

    echo "Pipeline complete!"
}

# Initialize medallion architecture
init_medallion() {
    mkdir -p "$BRONZE_DIR"/{events,raw-tasks,raw-metrics}
    mkdir -p "$SILVER_DIR"/{processed-tasks,aggregated-metrics,validated-lineage}
    mkdir -p "$GOLD_DIR"/{analytics,reports,kpis}

    echo "Medallion architecture initialized"
    echo "  Bronze: $BRONZE_DIR"
    echo "  Silver: $SILVER_DIR"
    echo "  Gold: $GOLD_DIR"
}

# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

export -f ingest_to_bronze
export -f ingest_task_to_bronze
export -f ingest_metrics_to_bronze
export -f process_tasks_to_silver
export -f aggregate_metrics_to_silver
export -f validate_lineage_to_silver
export -f generate_daily_analytics
export -f generate_kpis
export -f generate_master_report
export -f run_medallion_pipeline
export -f init_medallion
