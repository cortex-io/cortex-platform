#!/usr/bin/env bash
# A/B Testing Framework for Cortex
# Enables controlled experiments with master versions and prompts

set -euo pipefail

# Prevent re-sourcing
if [ -n "${AB_TESTING_LIB_LOADED:-}" ]; then
    return 0
fi
AB_TESTING_LIB_LOADED=1

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/environment.sh"

# ==============================================================================
# CONFIGURATION
# ==============================================================================

readonly AB_TESTS_DIR="coordination/ab-tests"
readonly AB_RESULTS_DIR="coordination/ab-tests/results"

# ==============================================================================
# TEST MANAGEMENT
# ==============================================================================

# Create new A/B test
# Args: $1=test_name, $2=master_name, $3=variant_a, $4=variant_b, $5=traffic_split
create_ab_test() {
    local test_name="$1"
    local master_name="$2"
    local variant_a="$3"  # e.g., "v1.0.0" or "prompt-v1"
    local variant_b="$4"  # e.g., "v1.1.0" or "prompt-v2"
    local traffic_split="${5:-50}"  # Default 50/50 split

    local test_file="$AB_TESTS_DIR/${test_name}.json"

    # Validate inputs
    if [[ -f "$test_file" ]]; then
        echo "Error: A/B test '$test_name' already exists" >&2
        return 1
    fi

    if [[ $traffic_split -lt 0 ]] || [[ $traffic_split -gt 100 ]]; then
        echo "Error: Traffic split must be 0-100" >&2
        return 1
    fi

    # Create test configuration
    jq -n \
        --arg test_name "$test_name" \
        --arg master "$master_name" \
        --arg variant_a "$variant_a" \
        --arg variant_b "$variant_b" \
        --arg split "$traffic_split" \
        '{
            test_id: $test_name,
            master: $master,
            variants: {
                a: {
                    name: $variant_a,
                    traffic_percentage: ($split | tonumber)
                },
                b: {
                    name: $variant_b,
                    traffic_percentage: (100 - ($split | tonumber))
                }
            },
            status: "active",
            created_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
            metrics: {
                tasks_assigned: {a: 0, b: 0},
                tasks_completed: {a: 0, b: 0},
                tasks_failed: {a: 0, b: 0},
                avg_duration: {a: 0, b: 0},
                avg_quality_score: {a: 0, b: 0}
            }
        }' > "$test_file"

    echo "Created A/B test: $test_name"
    echo "  Variant A ($variant_a): ${traffic_split}%"
    echo "  Variant B ($variant_b): $((100 - traffic_split))%"
}

# Get variant for incoming task (A/B split decision)
# Args: $1=test_name, $2=task_id
# Returns: "a" or "b"
get_variant() {
    local test_name="$1"
    local task_id="$2"

    local test_file="$AB_TESTS_DIR/${test_name}.json"

    if [[ ! -f "$test_file" ]]; then
        echo "Error: A/B test '$test_name' not found" >&2
        return 1
    fi

    # Check if test is active
    local status=$(jq -r '.status' "$test_file")
    if [[ "$status" != "active" ]]; then
        echo "Error: A/B test '$test_name' is not active" >&2
        return 1
    fi

    # Get traffic split
    local split_a=$(jq -r '.variants.a.traffic_percentage' "$test_file")

    # Use task_id hash for deterministic assignment
    local hash=$(echo -n "$task_id" | md5sum | cut -c1-8)
    local hash_int=$((16#$hash % 100))

    if [[ $hash_int -lt $split_a ]]; then
        echo "a"
    else
        echo "b"
    fi
}

# Record A/B test result
# Args: $1=test_name, $2=task_id, $3=variant, $4=status, $5=duration, $6=quality_score
record_ab_result() {
    local test_name="$1"
    local task_id="$2"
    local variant="$3"
    local status="$4"
    local duration="${5:-0}"
    local quality_score="${6:-0}"

    local results_file="$AB_RESULTS_DIR/${test_name}-results.jsonl"

    # Create result entry
    jq -n \
        --arg test "$test_name" \
        --arg task "$task_id" \
        --arg variant "$variant" \
        --arg status "$status" \
        --arg duration "$duration" \
        --arg quality "$quality_score" \
        '{
            test_id: $test,
            task_id: $task,
            variant: $variant,
            status: $status,
            duration_seconds: ($duration | tonumber),
            quality_score: ($quality | tonumber),
            timestamp: (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
        }' >> "$results_file"

    # Update test metrics
    update_ab_metrics "$test_name" "$variant" "$status" "$duration" "$quality_score"
}

# Update A/B test aggregate metrics
update_ab_metrics() {
    local test_name="$1"
    local variant="$2"
    local status="$3"
    local duration="$4"
    local quality_score="$5"

    local test_file="$AB_TESTS_DIR/${test_name}.json"

    # Increment task counters
    local metric_key="metrics.tasks_assigned.$variant"
    jq --arg key "$variant" \
       '.metrics.tasks_assigned[$key] += 1' \
       "$test_file" > "$test_file.tmp" && mv "$test_file.tmp" "$test_file"

    if [[ "$status" == "completed" ]]; then
        jq --arg key "$variant" \
           '.metrics.tasks_completed[$key] += 1' \
           "$test_file" > "$test_file.tmp" && mv "$test_file.tmp" "$test_file"
    elif [[ "$status" == "failed" ]]; then
        jq --arg key "$variant" \
           '.metrics.tasks_failed[$key] += 1' \
           "$test_file" > "$test_file.tmp" && mv "$test_file.tmp" "$test_file"
    fi

    # Update running averages (simplified - should use proper moving average)
    if [[ "$duration" != "0" ]]; then
        jq --arg key "$variant" --arg dur "$duration" \
           '.metrics.avg_duration[$key] = ((.metrics.avg_duration[$key] + ($dur | tonumber)) / 2)' \
           "$test_file" > "$test_file.tmp" && mv "$test_file.tmp" "$test_file"
    fi

    if [[ "$quality_score" != "0" ]]; then
        jq --arg key "$variant" --arg qual "$quality_score" \
           '.metrics.avg_quality_score[$key] = ((.metrics.avg_quality_score[$key] + ($qual | tonumber)) / 2)' \
           "$test_file" > "$test_file.tmp" && mv "$test_file.tmp" "$test_file"
    fi
}

# Get A/B test results summary
get_ab_summary() {
    local test_name="$1"
    local test_file="$AB_TESTS_DIR/${test_name}.json"

    if [[ ! -f "$test_file" ]]; then
        echo "Error: A/B test '$test_name' not found" >&2
        return 1
    fi

    jq '{
        test_id,
        master,
        status,
        variants: {
            a: {
                name: .variants.a.name,
                traffic: .variants.a.traffic_percentage,
                tasks_assigned: .metrics.tasks_assigned.a,
                tasks_completed: .metrics.tasks_completed.a,
                completion_rate: (if .metrics.tasks_assigned.a > 0 then
                    (.metrics.tasks_completed.a / .metrics.tasks_assigned.a * 100)
                else 0 end),
                avg_duration: .metrics.avg_duration.a,
                avg_quality: .metrics.avg_quality_score.a
            },
            b: {
                name: .variants.b.name,
                traffic: .variants.b.traffic_percentage,
                tasks_assigned: .metrics.tasks_assigned.b,
                tasks_completed: .metrics.tasks_completed.b,
                completion_rate: (if .metrics.tasks_assigned.b > 0 then
                    (.metrics.tasks_completed.b / .metrics.tasks_assigned.b * 100)
                else 0 end),
                avg_duration: .metrics.avg_duration.b,
                avg_quality: .metrics.avg_quality_score.b
            }
        }
    }' "$test_file"
}

# Stop A/B test and declare winner
# Args: $1=test_name, $2=winner (a or b)
stop_ab_test() {
    local test_name="$1"
    local winner="$2"

    local test_file="$AB_TESTS_DIR/${test_name}.json"

    if [[ ! -f "$test_file" ]]; then
        echo "Error: A/B test '$test_name' not found" >&2
        return 1
    fi

    jq --arg winner "$winner" \
       '.status = "completed" | .winner = $winner | .completed_at = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))' \
       "$test_file" > "$test_file.tmp" && mv "$test_file.tmp" "$test_file"

    echo "A/B test '$test_name' stopped. Winner: variant $winner"

    # Show final summary
    get_ab_summary "$test_name"
}

# List all active A/B tests
list_ab_tests() {
    local status_filter="${1:-all}"

    if [[ ! -d "$AB_TESTS_DIR" ]]; then
        echo "No A/B tests found"
        return 0
    fi

    echo "=== A/B Tests ==="
    for test_file in "$AB_TESTS_DIR"/*.json; do
        if [[ -f "$test_file" ]]; then
            local status=$(jq -r '.status' "$test_file")

            if [[ "$status_filter" == "all" ]] || [[ "$status" == "$status_filter" ]]; then
                local test_name=$(jq -r '.test_id' "$test_file")
                local master=$(jq -r '.master' "$test_file")
                local variant_a=$(jq -r '.variants.a.name' "$test_file")
                local variant_b=$(jq -r '.variants.b.name' "$test_file")

                echo "[$status] $test_name ($master)"
                echo "  Variant A: $variant_a"
                echo "  Variant B: $variant_b"
            fi
        fi
    done
}

# Initialize A/B testing infrastructure
init_ab_testing() {
    mkdir -p "$AB_TESTS_DIR"
    mkdir -p "$AB_RESULTS_DIR"
    echo "A/B testing infrastructure initialized"
}

# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

export -f create_ab_test
export -f get_variant
export -f record_ab_result
export -f update_ab_metrics
export -f get_ab_summary
export -f stop_ab_test
export -f list_ab_tests
export -f init_ab_testing
