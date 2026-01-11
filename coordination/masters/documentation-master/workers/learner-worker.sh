#!/bin/bash

################################################################################
# Learner Worker
#
# Integrates with MoE learning system to track documentation usage patterns
# and update priorities based on outcomes.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
CONFIG_DIR="${MASTER_DIR}/config"
CACHE_DIR="${MASTER_DIR}/cache"

# Worker ID
WORKER_ID="${WORKER_ID:-$(uuidgen 2>/dev/null || echo "worker-$$")}"

# MoE endpoints (from config)
MOE_ROUTER_ENDPOINT="${MOE_ROUTER_ENDPOINT:-http://llm-mesh-moe-router:8080}"
MOE_LEARNER_ENDPOINT="${MOE_LEARNER_ENDPOINT:-http://llm-mesh-moe-learner:8080}"

# Cleanup handler
cleanup() {
    local exit_code=$?
    log_info "Worker cleanup (exit code: ${exit_code})"

    # Remove any temporary outcome files
    find "${CACHE_DIR}/outcomes" -name "*.tmp" -delete 2>/dev/null || true

    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

################################################################################
# Logging
################################################################################

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"learner-worker\",\"worker_id\":\"${WORKER_ID}\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# MoE Integration
################################################################################

register_with_moe() {
    local role="documentation-master"

    log_info "Registering with MoE learning system"

    # Register routing pattern
    local pattern='{
      "task_type": "documentation_query",
      "patterns": {
        "sandfly_api": "documentation-master",
        "sandfly_concepts": "documentation-master",
        "external_integration_docs": "documentation-master"
      },
      "confidence_threshold": 0.7
    }'

    # Send registration (if MoE is available)
    if curl -s -f -X POST "${MOE_ROUTER_ENDPOINT}/register" \
        -H "Content-Type: application/json" \
        -d "${pattern}" > /dev/null 2>&1; then
        log_info "Successfully registered with MoE router"
    else
        log_warn "MoE router not available, continuing without learning integration"
    fi
}

track_outcome() {
    local outcome_id="$1"
    local task_id="$2"
    local domain="$3"
    local topic="$4"
    local success="$5"
    local confidence="$6"

    # Input validation
    if [[ -z "${outcome_id}" ]] || [[ -z "${task_id}" ]] || [[ -z "${domain}" ]]; then
        log_error "Missing required parameters for outcome tracking"
        return 1
    fi

    # Sanitize inputs
    outcome_id=$(echo "${outcome_id}" | tr -cd '[:alnum:]-_')
    task_id=$(echo "${task_id}" | tr -cd '[:alnum:]-_')
    domain=$(echo "${domain}" | tr -cd '[:alnum:]-_')

    log_info "Tracking outcome: ${outcome_id}"

    # Build outcome record
    local outcome="{
      \"outcome_id\": \"${outcome_id}\",
      \"task_id\": \"${task_id}\",
      \"domain\": \"${domain}\",
      \"topic\": \"${topic}\",
      \"success\": ${success},
      \"confidence\": ${confidence},
      \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
      \"worker_id\": \"${WORKER_ID}\"
    }"

    # Store locally with atomic write
    local outcome_dir="${CACHE_DIR}/outcomes"
    mkdir -p "${outcome_dir}"

    local outcome_file="${outcome_dir}/${outcome_id}.json"
    echo "${outcome}" > "${outcome_file}.tmp"

    # Validate JSON before committing
    if jq empty "${outcome_file}.tmp" 2>/dev/null; then
        mv "${outcome_file}.tmp" "${outcome_file}"
        log_info "Outcome stored locally: ${outcome_file}"
    else
        log_error "Invalid outcome JSON generated"
        rm -f "${outcome_file}.tmp"
        return 1
    fi

    # Send to MoE learner with retry
    local max_retries=3
    local retry_count=0

    while [[ ${retry_count} -lt ${max_retries} ]]; do
        if curl -s -f -X POST "${MOE_LEARNER_ENDPOINT}/outcome" \
            -H "Content-Type: application/json" \
            -d "${outcome}" \
            --max-time 10 > /dev/null 2>&1; then
            log_info "Outcome tracked in MoE system"
            return 0
        fi

        ((retry_count++))
        if [[ ${retry_count} -lt ${max_retries} ]]; then
            log_warn "Failed to reach MoE learner, retry ${retry_count}/${max_retries}"
            sleep $((2 ** retry_count))
        fi
    done

    log_warn "MoE learner not available after ${max_retries} retries, outcome stored locally only"
    return 0
}

analyze_patterns() {
    local domain="$1"

    log_info "Analyzing usage patterns for domain: ${domain}"

    local outcome_dir="${CACHE_DIR}/outcomes"

    if [[ ! -d "${outcome_dir}" ]]; then
        log_warn "No outcomes to analyze"
        return 0
    fi

    # Aggregate outcomes
    local total_queries=0
    local successful_queries=0
    local total_confidence=0

    for outcome_file in "${outcome_dir}"/*.json; do
        if [[ -f "${outcome_file}" ]]; then
            local outcome_domain=$(jq -r '.domain // ""' "${outcome_file}")

            if [[ "${outcome_domain}" == "${domain}" ]]; then
                ((total_queries++))

                local success=$(jq -r '.success // false' "${outcome_file}")
                if [[ "${success}" == "true" ]]; then
                    ((successful_queries++))
                fi

                local confidence=$(jq -r '.confidence // 0' "${outcome_file}")
                total_confidence=$(echo "${total_confidence} + ${confidence}" | bc)
            fi
        fi
    done

    if [[ ${total_queries} -gt 0 ]]; then
        local success_rate=$(echo "scale=2; ${successful_queries} / ${total_queries}" | bc)
        local avg_confidence=$(echo "scale=2; ${total_confidence} / ${total_queries}" | bc)

        log_info "Pattern analysis - Domain: ${domain}, Queries: ${total_queries}, Success Rate: ${success_rate}, Avg Confidence: ${avg_confidence}"

        # Store analysis
        cat > "${CACHE_DIR}/pattern-analysis-${domain}.json" <<EOF
{
  "domain": "${domain}",
  "total_queries": ${total_queries},
  "successful_queries": ${successful_queries},
  "success_rate": ${success_rate},
  "avg_confidence": ${avg_confidence},
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    fi
}

################################################################################
# Main
################################################################################

main() {
    local command="${1:-register}"

    case "${command}" in
        register)
            register_with_moe
            ;;

        track)
            shift
            if [[ $# -lt 6 ]]; then
                log_error "Usage: $0 track <outcome_id> <task_id> <domain> <topic> <success> <confidence>"
                exit 1
            fi
            track_outcome "$@"
            ;;

        analyze)
            shift
            local domain="${1:-sandfly}"
            analyze_patterns "${domain}"
            ;;

        monitor)
            log_info "Starting MoE learning monitor"
            register_with_moe

            # Continuous monitoring loop
            while true; do
                sleep 300  # Every 5 minutes
                analyze_patterns "sandfly"
            done
            ;;

        *)
            echo "Usage: $0 {register|track|analyze|monitor}"
            echo ""
            echo "Commands:"
            echo "  register                                                    - Register with MoE"
            echo "  track <outcome_id> <task_id> <domain> <topic> <success> <confidence>"
            echo "  analyze <domain>                                            - Analyze patterns"
            echo "  monitor                                                     - Start monitoring loop"
            exit 1
            ;;
    esac
}

main "$@"
