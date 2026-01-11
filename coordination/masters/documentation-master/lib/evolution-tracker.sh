#!/bin/bash

################################################################################
# Evolution Tracker
#
# Monitors documentation freshness, detects knowledge gaps, and triggers
# targeted re-crawls. Implements pruning for low-value cached docs.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
CONFIG_DIR="${MASTER_DIR}/config"
KNOWLEDGE_BASE_DIR="${MASTER_DIR}/knowledge-base"
CACHE_DIR="${MASTER_DIR}/cache"

################################################################################
# Logging
################################################################################

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"evolution-tracker\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# Configuration Loading
################################################################################

load_config() {
    local config_file="${1:-${CONFIG_DIR}/learning-policy.json}"

    if [[ ! -f "${config_file}" ]]; then
        log_error "Config file not found: ${config_file}"
        return 1
    fi

    # Extract key config values
    MIN_VALUE_SCORE=$(jq -r '.pruning.min_value_score // 0.3' "${config_file}")
    PRUNING_WINDOW_DAYS=$(jq -r '.pruning.window_days // 90' "${config_file}")
    FRESHNESS_THRESHOLD_HOURS=$(jq -r '.freshness.max_age_hours // 168' "${config_file}")  # 7 days default

    log_info "Config loaded - Min score: ${MIN_VALUE_SCORE}, Pruning window: ${PRUNING_WINDOW_DAYS} days"
}

################################################################################
# Freshness Monitoring
################################################################################

check_freshness() {
    local domain="$1"

    log_info "Checking documentation freshness for domain: ${domain}"

    local meta_dir="${CACHE_DIR}/metadata/${domain}"

    if [[ ! -d "${meta_dir}" ]]; then
        log_warn "No metadata found for domain: ${domain}"
        return 0
    fi

    local now_ts=$(date +%s)
    local stale_count=0
    local total_count=0
    local stale_urls=()

    for meta_file in "${meta_dir}"/*.json; do
        if [[ -f "${meta_file}" ]]; then
            ((total_count++))

            local last_crawled=$(jq -r '.last_crawled // ""' "${meta_file}")

            if [[ -n "${last_crawled}" ]]; then
                local crawl_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "${last_crawled}" +%s 2>/dev/null || date -d "${last_crawled}" +%s 2>/dev/null || echo 0)
                local age_hours=$(( (now_ts - crawl_ts) / 3600 ))

                if [[ ${age_hours} -gt ${FRESHNESS_THRESHOLD_HOURS} ]]; then
                    ((stale_count++))
                    local url=$(jq -r '.url // "unknown"' "${meta_file}")
                    stale_urls+=("${url}")
                fi
            fi
        fi
    done

    local freshness_percentage=0
    if [[ ${total_count} -gt 0 ]]; then
        freshness_percentage=$(echo "scale=2; (${total_count} - ${stale_count}) * 100 / ${total_count}" | bc)
    fi

    log_info "Freshness check - Domain: ${domain}, Total: ${total_count}, Stale: ${stale_count}, Fresh: ${freshness_percentage}%"

    # Store freshness report
    local report_file="${CACHE_DIR}/freshness-report-${domain}.json"
    cat > "${report_file}" <<EOF
{
  "domain": "${domain}",
  "total_documents": ${total_count},
  "stale_documents": ${stale_count},
  "freshness_percentage": ${freshness_percentage},
  "threshold_hours": ${FRESHNESS_THRESHOLD_HOURS},
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "stale_urls": $(printf '%s\n' "${stale_urls[@]}" | jq -R . | jq -s .)
}
EOF

    # Trigger re-crawl if freshness is below 80%
    if (( $(echo "${freshness_percentage} < 80" | bc -l) )); then
        log_warn "Documentation freshness below 80%, triggering re-crawl"
        return 2
    fi

    return 0
}

################################################################################
# Knowledge Gap Detection
################################################################################

detect_knowledge_gaps() {
    local domain="$1"

    log_info "Detecting knowledge gaps for domain: ${domain}"

    local outcome_dir="${CACHE_DIR}/outcomes"

    if [[ ! -d "${outcome_dir}" ]]; then
        log_warn "No outcomes to analyze for knowledge gaps"
        return 0
    fi

    # Analyze queries with low confidence
    local low_confidence_threshold=0.5
    local gap_topics=()

    for outcome_file in "${outcome_dir}"/*.json; do
        if [[ -f "${outcome_file}" ]]; then
            local outcome_domain=$(jq -r '.domain // ""' "${outcome_file}")

            if [[ "${outcome_domain}" == "${domain}" ]]; then
                local confidence=$(jq -r '.confidence // 1.0' "${outcome_file}")
                local success=$(jq -r '.success // true' "${outcome_file}")

                # Knowledge gap: low confidence OR failure
                if (( $(echo "${confidence} < ${low_confidence_threshold}" | bc -l) )) || [[ "${success}" == "false" ]]; then
                    local topic=$(jq -r '.topic // "unknown"' "${outcome_file}")
                    gap_topics+=("${topic}")
                fi
            fi
        fi
    done

    # Count unique gaps
    local unique_gaps=$(printf '%s\n' "${gap_topics[@]}" | sort -u | wc -l | tr -d ' ')

    if [[ ${unique_gaps} -gt 0 ]]; then
        log_warn "Knowledge gaps detected: ${unique_gaps} topics with low confidence"

        # Store gap report
        local gap_report="${CACHE_DIR}/knowledge-gaps-${domain}.json"
        cat > "${gap_report}" <<EOF
{
  "domain": "${domain}",
  "gap_count": ${unique_gaps},
  "gap_topics": $(printf '%s\n' "${gap_topics[@]}" | sort -u | jq -R . | jq -s .),
  "threshold": ${low_confidence_threshold},
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

        return 1
    fi

    log_info "No significant knowledge gaps detected"
    return 0
}

################################################################################
# Priority Scoring
################################################################################

calculate_priority_score() {
    local url_hash="$1"
    local domain="$2"

    # Load usage frequency
    local usage_count=0
    local success_count=0
    local outcome_dir="${CACHE_DIR}/outcomes"

    if [[ -d "${outcome_dir}" ]]; then
        for outcome_file in "${outcome_dir}"/*.json; do
            if [[ -f "${outcome_file}" ]]; then
                # Check if this URL was used in the outcome
                local doc_used=$(jq -r --arg hash "${url_hash}" '.documentation_used[]? | select(contains($hash))' "${outcome_file}" 2>/dev/null || echo "")

                if [[ -n "${doc_used}" ]]; then
                    ((usage_count++))

                    local success=$(jq -r '.success // false' "${outcome_file}")
                    if [[ "${success}" == "true" ]]; then
                        ((success_count++))
                    fi
                fi
            fi
        done
    fi

    # Calculate success rate
    local success_rate=0.5  # Default
    if [[ ${usage_count} -gt 0 ]]; then
        success_rate=$(echo "scale=4; ${success_count} / ${usage_count}" | bc)
    fi

    # Calculate recency score (1.0 if < 7 days old, decays to 0.1 over 90 days)
    local meta_file="${CACHE_DIR}/metadata/${domain}/${url_hash}.json"
    local recency_score=0.5  # Default

    if [[ -f "${meta_file}" ]]; then
        local last_crawled=$(jq -r '.last_crawled // ""' "${meta_file}")

        if [[ -n "${last_crawled}" ]]; then
            local now_ts=$(date +%s)
            local crawl_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "${last_crawled}" +%s 2>/dev/null || date -d "${last_crawled}" +%s 2>/dev/null || echo 0)
            local age_days=$(( (now_ts - crawl_ts) / 86400 ))

            if [[ ${age_days} -lt 7 ]]; then
                recency_score=1.0
            elif [[ ${age_days} -lt 30 ]]; then
                recency_score=0.8
            elif [[ ${age_days} -lt 60 ]]; then
                recency_score=0.5
            elif [[ ${age_days} -lt 90 ]]; then
                recency_score=0.3
            else
                recency_score=0.1
            fi
        fi
    fi

    # Normalize usage to 0-1 scale (cap at 100 uses = 1.0)
    local usage_normalized=$(echo "scale=4; ${usage_count} / 100" | bc)
    if (( $(echo "${usage_normalized} > 1.0" | bc -l) )); then
        usage_normalized=1.0
    fi

    # Priority formula: usage_frequency × success_rate × recency
    local priority=$(echo "scale=4; ${usage_normalized} * ${success_rate} * ${recency_score}" | bc)

    echo "${priority}"
}

################################################################################
# Pruning
################################################################################

prune_low_value_content() {
    local domain="$1"

    log_info "Starting pruning of low-value content for domain: ${domain}"

    local meta_dir="${CACHE_DIR}/metadata/${domain}"

    if [[ ! -d "${meta_dir}" ]]; then
        log_warn "No metadata found for domain: ${domain}"
        return 0
    fi

    local pruned_count=0
    local evaluated_count=0

    for meta_file in "${meta_dir}"/*.json; do
        if [[ -f "${meta_file}" ]]; then
            ((evaluated_count++))

            local url_hash=$(basename "${meta_file}" .json)
            local priority=$(calculate_priority_score "${url_hash}" "${domain}")

            # Prune if priority score is below minimum threshold
            if (( $(echo "${priority} < ${MIN_VALUE_SCORE}" | bc -l) )); then
                local url=$(jq -r '.url // "unknown"' "${meta_file}")
                log_info "Pruning low-value content: ${url} (score: ${priority})"

                # Remove content, metadata, and index files
                rm -f "${meta_file}"
                rm -f "${KNOWLEDGE_BASE_DIR}/${domain}/${url_hash}.txt"
                rm -f "${CACHE_DIR}/indexed-content/${domain}/${url_hash}.html"
                rm -f "${CACHE_DIR}/indexed-content/${domain}/${url_hash}.index.json"

                ((pruned_count++))
            fi
        fi
    done

    log_info "Pruning complete - Evaluated: ${evaluated_count}, Pruned: ${pruned_count}"

    # Update master index after pruning
    if [[ ${pruned_count} -gt 0 ]]; then
        log_info "Updating master index after pruning"
        "${SCRIPT_DIR}/indexer.sh" update-master "${domain}" 2>/dev/null || true
    fi

    # Store pruning report
    local prune_report="${CACHE_DIR}/pruning-report-${domain}.json"
    cat > "${prune_report}" <<EOF
{
  "domain": "${domain}",
  "evaluated": ${evaluated_count},
  "pruned": ${pruned_count},
  "min_score_threshold": ${MIN_VALUE_SCORE},
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
}

################################################################################
# Trigger Re-crawl
################################################################################

trigger_recrawl() {
    local domain="$1"
    local reason="$2"

    log_info "Triggering re-crawl for domain: ${domain}, reason: ${reason}"

    # Call crawler in background
    "${SCRIPT_DIR}/crawler.sh" schedule "${domain}" &

    local crawler_pid=$!

    log_info "Re-crawl triggered (PID: ${crawler_pid})"

    # Store trigger event
    local trigger_file="${CACHE_DIR}/recrawl-triggers-${domain}.jsonl"
    cat >> "${trigger_file}" <<EOF
{"domain":"${domain}","reason":"${reason}","timestamp":"$(date -u +"%Y-%m-%dT%H:%M:%SZ")","pid":${crawler_pid}}
EOF
}

################################################################################
# Evolution Status
################################################################################

get_status() {
    local domain="$1"

    log_info "Generating evolution status for domain: ${domain}"

    # Gather all status information
    local freshness_report="${CACHE_DIR}/freshness-report-${domain}.json"
    local gap_report="${CACHE_DIR}/knowledge-gaps-${domain}.json"
    local prune_report="${CACHE_DIR}/pruning-report-${domain}.json"
    local pattern_analysis="${CACHE_DIR}/pattern-analysis-${domain}.json"

    # Build status JSON
    cat <<EOF
{
  "domain": "${domain}",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "freshness": $(cat "${freshness_report}" 2>/dev/null || echo '{"status":"not_available"}'),
  "knowledge_gaps": $(cat "${gap_report}" 2>/dev/null || echo '{"status":"not_available"}'),
  "pruning": $(cat "${prune_report}" 2>/dev/null || echo '{"status":"not_available"}'),
  "learning": $(cat "${pattern_analysis}" 2>/dev/null || echo '{"status":"not_available"}')
}
EOF
}

################################################################################
# Evolution Monitor Loop
################################################################################

monitor() {
    local domain="${1:-sandfly}"
    local check_interval="${2:-3600}"  # 1 hour default

    log_info "Starting evolution monitor for domain: ${domain} (interval: ${check_interval}s)"

    # Load configuration
    load_config

    while true; do
        log_info "Running evolution check cycle"

        # Check freshness
        if check_freshness "${domain}"; then
            local freshness_status=$?

            if [[ ${freshness_status} -eq 2 ]]; then
                trigger_recrawl "${domain}" "low_freshness"
            fi
        fi

        # Detect knowledge gaps
        if ! detect_knowledge_gaps "${domain}"; then
            trigger_recrawl "${domain}" "knowledge_gaps_detected"
        fi

        # Prune low-value content (once per day)
        local hour=$(date +%H)
        if [[ "${hour}" == "02" ]]; then  # 2 AM
            prune_low_value_content "${domain}"
        fi

        # Sleep until next check
        sleep "${check_interval}"
    done
}

################################################################################
# Main
################################################################################

main() {
    local command="${1:-}"
    shift || true

    case "${command}" in
        check-freshness)
            local domain="${1:-sandfly}"
            load_config
            check_freshness "${domain}"
            ;;

        detect-gaps)
            local domain="${1:-sandfly}"
            load_config
            detect_knowledge_gaps "${domain}"
            ;;

        prune)
            local domain="${1:-sandfly}"
            load_config
            prune_low_value_content "${domain}"
            ;;

        trigger-recrawl)
            local domain="${1:-sandfly}"
            local reason="${2:-manual}"
            trigger_recrawl "${domain}" "${reason}"
            ;;

        status)
            local domain="${1:-sandfly}"
            get_status "${domain}"
            ;;

        monitor)
            local domain="${1:-sandfly}"
            local interval="${2:-3600}"
            monitor "${domain}" "${interval}"
            ;;

        *)
            echo "Usage: $0 {check-freshness|detect-gaps|prune|trigger-recrawl|status|monitor} [options]"
            echo ""
            echo "Commands:"
            echo "  check-freshness <domain>           - Check documentation freshness"
            echo "  detect-gaps <domain>               - Detect knowledge gaps"
            echo "  prune <domain>                     - Prune low-value content"
            echo "  trigger-recrawl <domain> [reason]  - Trigger re-crawl"
            echo "  status <domain>                    - Get evolution status"
            echo "  monitor <domain> [interval]        - Start monitoring loop"
            exit 1
            ;;
    esac
}

main "$@"
