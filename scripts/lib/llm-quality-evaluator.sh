#!/usr/bin/env bash
# LLM Quality Evaluator
# Phase 2: Quality & Validation
# Evaluates quality of LLM outputs across multiple dimensions

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Quality scores storage
QUALITY_SCORES_FILE="$CORTEX_HOME/coordination/quality-scores.jsonl"
mkdir -p "$(dirname "$QUALITY_SCORES_FILE")"
touch "$QUALITY_SCORES_FILE"

##############################################################################
# evaluate_quality: Comprehensive quality evaluation
# Args:
#   $1: worker_output (text or file path)
#   $2: task_spec (task description or file path)
#   $3: worker_id (optional)
#   $4: task_id (optional)
# Returns: Quality score JSON
##############################################################################
evaluate_quality() {
    local worker_output="$1"
    local task_spec="$2"
    local worker_id="${3:-unknown}"
    local task_id="${4:-unknown}"

    # Read from file if path provided
    if [ -f "$worker_output" ]; then
        worker_output=$(cat "$worker_output")
    fi

    if [ -f "$task_spec" ]; then
        task_spec=$(cat "$task_spec" | jq -r '.description // .')
    fi

    # 1. Topic Relevancy (0.0-1.0)
    local relevancy=$(check_topic_relevancy "$worker_output" "$task_spec")

    # 2. Task Completion (boolean → 0.0 or 1.0)
    local completion=$(verify_task_completion "$worker_output" "$task_spec")

    # 3. Output Coherence (0.0-1.0)
    local coherence=$(assess_coherence "$worker_output")

    # 4. Sentiment Analysis (positive/neutral/negative → score)
    local sentiment_category=$(analyze_sentiment "$worker_output")
    local sentiment_score=$(sentiment_to_score "$sentiment_category")

    # 5. Calculate composite score (weighted average)
    local composite_score=$(calculate_composite_score "$relevancy" "$completion" "$coherence" "$sentiment_score")

    # Build quality result
    local timestamp=$(date -Iseconds)

    local quality_result=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg worker_id "$worker_id" \
        --arg task_id "$task_id" \
        --arg relevancy "$relevancy" \
        --arg completion "$completion" \
        --arg coherence "$coherence" \
        --arg sentiment "$sentiment_category" \
        --arg sentiment_score "$sentiment_score" \
        --arg composite_score "$composite_score" \
        '{
            timestamp: $timestamp,
            worker_id: $worker_id,
            task_id: $task_id,
            quality_dimensions: {
                topic_relevancy: ($relevancy | tonumber),
                task_completion: ($completion | tonumber),
                output_coherence: ($coherence | tonumber),
                sentiment: {
                    category: $sentiment,
                    score: ($sentiment_score | tonumber)
                }
            },
            composite_score: ($composite_score | tonumber),
            grade: (
                if ($composite_score | tonumber) >= 0.9 then "excellent"
                elif ($composite_score | tonumber) >= 0.8 then "good"
                elif ($composite_score | tonumber) >= 0.7 then "acceptable"
                else "needs_improvement"
                end
            )
        }')

    # Save to quality scores log
    echo "$quality_result" >> "$QUALITY_SCORES_FILE"

    echo "$quality_result"
}

##############################################################################
# check_topic_relevancy: Check if output is relevant to task
# Args:
#   $1: worker_output
#   $2: task_spec
# Returns: Relevancy score (0.0-1.0)
##############################################################################
check_topic_relevancy() {
    local worker_output="$1"
    local task_spec="$2"

    # Extract key terms from task
    local task_terms=$(echo "$task_spec" | tr '[:upper:]' '[:lower:]' | \
        grep -oE '\b[a-z]{4,}\b' | sort | uniq)

    local total_terms=$(echo "$task_terms" | wc -w | tr -d ' ')
    local matched_terms=0

    # Count matching terms in output
    local output_lower=$(echo "$worker_output" | tr '[:upper:]' '[:lower:]')

    for term in $task_terms; do
        if echo "$output_lower" | grep -q "$term"; then
            matched_terms=$((matched_terms + 1))
        fi
    done

    # Calculate relevancy score
    if [ "$total_terms" -eq 0 ]; then
        echo "0.5"  # Default if no terms to match
    else
        local relevancy=$(echo "scale=2; $matched_terms / $total_terms" | bc -l)
        # Cap at 1.0
        if [ "$(echo "$relevancy > 1" | bc -l)" -eq 1 ]; then
            relevancy="1.0"
        fi
        printf "%.2f" "$relevancy"
    fi
}

##############################################################################
# verify_task_completion: Check if task appears completed
# Args:
#   $1: worker_output
#   $2: task_spec
# Returns: Completion score (0.0 or 1.0)
##############################################################################
verify_task_completion() {
    local worker_output="$1"
    local task_spec="$2"

    local output_length=${#worker_output}

    # Heuristics for task completion
    local has_content=false
    local has_structure=false
    local has_conclusion=false

    # Check for minimum content
    [ "$output_length" -gt 100 ] && has_content=true

    # Check for code blocks, lists, or structured content
    if echo "$worker_output" | grep -qE '```|^- |^[0-9]+\.|^#|function |class '; then
        has_structure=true
    fi

    # Check for completion indicators
    if echo "$worker_output" | grep -qiE 'complete|done|finished|implemented|created|ready'; then
        has_conclusion=true
    fi

    # Calculate completion score
    local score=0
    $has_content && score=$((score + 33))
    $has_structure && score=$((score + 33))
    $has_conclusion && score=$((score + 34))

    printf "%.2f" "$(echo "scale=2; $score / 100" | bc -l)"
}

##############################################################################
# assess_coherence: Assess logical coherence and readability
# Args:
#   $1: worker_output
# Returns: Coherence score (0.0-1.0)
##############################################################################
assess_coherence() {
    local worker_output="$1"

    local score=50  # Start at 50%

    # Check for proper sentence structure
    local sentence_count=$(echo "$worker_output" | grep -cE '\. |\? |! ' || echo "1")
    local avg_sentence_length=$(echo "scale=0; ${#worker_output} / $sentence_count" | bc)

    # Ideal sentence length: 15-25 words (assuming 5 chars per word)
    if [ "$avg_sentence_length" -ge 75 ] && [ "$avg_sentence_length" -le 125 ]; then
        score=$((score + 15))
    fi

    # Check for paragraph breaks
    local paragraph_count=$(echo "$worker_output" | grep -c '^$' || echo "0")
    if [ "$paragraph_count" -gt 0 ]; then
        score=$((score + 10))
    fi

    # Check for transition words
    if echo "$worker_output" | grep -qiE 'however|therefore|additionally|furthermore|consequently'; then
        score=$((score + 10))
    fi

    # Check for code quality (if code present)
    if echo "$worker_output" | grep -q '```'; then
        # Has code comments
        echo "$worker_output" | grep -qE '#|//|/\*' && score=$((score + 10))
        # Has proper indentation (multiple spaces or tabs)
        echo "$worker_output" | grep -qE '^  |^\t' && score=$((score + 5))
    fi

    # Cap at 100
    [ "$score" -gt 100 ] && score=100

    printf "%.2f" "$(echo "scale=2; $score / 100" | bc -l)"
}

##############################################################################
# analyze_sentiment: Analyze sentiment of output
# Args:
#   $1: worker_output
# Returns: positive|neutral|negative
##############################################################################
analyze_sentiment() {
    local worker_output="$1"

    local positive_words="success|complete|excellent|good|improved|optimized|efficient|working|resolved|fixed"
    local negative_words="fail|error|broken|issue|problem|bug|crash|unable|cannot|failed"

    local positive_count=$(echo "$worker_output" | grep -oiE "$positive_words" | wc -l | tr -d ' ')
    local negative_count=$(echo "$worker_output" | grep -oiE "$negative_words" | wc -l | tr -d ' ')

    if [ "$positive_count" -gt "$negative_count" ] && [ "$positive_count" -gt 0 ]; then
        echo "positive"
    elif [ "$negative_count" -gt "$positive_count" ] && [ "$negative_count" -gt 0 ]; then
        echo "negative"
    else
        echo "neutral"
    fi
}

##############################################################################
# sentiment_to_score: Convert sentiment to numeric score
# Args:
#   $1: sentiment (positive|neutral|negative)
# Returns: Score (0.0-1.0)
##############################################################################
sentiment_to_score() {
    local sentiment="$1"

    case "$sentiment" in
        positive)
            echo "1.0"
            ;;
        neutral)
            echo "0.7"
            ;;
        negative)
            echo "0.4"
            ;;
        *)
            echo "0.5"
            ;;
    esac
}

##############################################################################
# calculate_composite_score: Calculate weighted composite score
# Args:
#   $1: relevancy (0.0-1.0)
#   $2: completion (0.0-1.0)
#   $3: coherence (0.0-1.0)
#   $4: sentiment_score (0.0-1.0)
# Returns: Composite score (0.0-1.0)
##############################################################################
calculate_composite_score() {
    local relevancy="$1"
    local completion="$2"
    local coherence="$3"
    local sentiment="$4"

    # Weighted formula:
    # 35% relevancy, 30% completion, 25% coherence, 10% sentiment
    local composite=$(echo "scale=2; ($relevancy * 0.35) + ($completion * 0.30) + ($coherence * 0.25) + ($sentiment * 0.10)" | bc -l)

    printf "%.2f" "$composite"
}

##############################################################################
# get_quality_summary: Get summary of recent quality scores
# Args:
#   $1: count (default: 50)
##############################################################################
get_quality_summary() {
    local count="${1:-50}"

    if [ ! -f "$QUALITY_SCORES_FILE" ]; then
        echo "No quality scores recorded yet"
        return 1
    fi

    echo "=== Quality Scores Summary (Last $count evaluations) ==="
    echo ""

    tail -"$count" "$QUALITY_SCORES_FILE" | jq -s '
        {
            total_evaluations: length,
            avg_composite_score: (map(.composite_score) | add / length),
            avg_relevancy: (map(.quality_dimensions.topic_relevancy) | add / length),
            avg_completion: (map(.quality_dimensions.task_completion) | add / length),
            avg_coherence: (map(.quality_dimensions.output_coherence) | add / length),
            grade_distribution: group_by(.grade) | map({
                grade: .[0].grade,
                count: length
            }),
            sentiment_distribution: group_by(.quality_dimensions.sentiment.category) | map({
                sentiment: .[0].quality_dimensions.sentiment.category,
                count: length
            })
        }
    '
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        evaluate)
            shift
            if [ $# -lt 2 ]; then
                echo "Error: evaluate requires <output> <task_spec> [worker_id] [task_id]"
                exit 1
            fi
            evaluate_quality "$@" | jq '.'
            ;;
        summary)
            get_quality_summary "${2:-50}"
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  evaluate <output> <task_spec> [worker_id] [task_id]
    Evaluate quality of worker output

  summary [count]
    Display quality summary (default: last 50)

Examples:
  # Evaluate output file
  $0 evaluate output.txt task-spec.json worker-001 task-123

  # Evaluate inline text
  $0 evaluate "Worker output text here" "Task: implement feature X"

  # Get summary
  $0 summary 100

Quality Dimensions:
  - Topic Relevancy (0.0-1.0): How relevant is output to task
  - Task Completion (0.0-1.0): Does output appear complete
  - Output Coherence (0.0-1.0): Is output well-structured
  - Sentiment: positive/neutral/negative tone

Composite Score: Weighted average of all dimensions
Grade: excellent (0.9+) | good (0.8+) | acceptable (0.7+) | needs_improvement (<0.7)

Scores stored in: $QUALITY_SCORES_FILE
EOF
            ;;
    esac
fi
