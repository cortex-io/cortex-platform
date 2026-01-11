#!/bin/bash

################################################################################
# Documentation Query Handler
#
# Handles queries from other masters and MCP servers. Searches indexed content
# and returns relevant excerpts with confidence scores.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
CONFIG_DIR="${MASTER_DIR}/config"
KNOWLEDGE_BASE_DIR="${MASTER_DIR}/knowledge-base"
CACHE_DIR="${MASTER_DIR}/cache"

# Defaults
DEFAULT_PORT=8080
DEFAULT_MAX_TOKENS=5000
DEFAULT_FORMAT="summary"

# Server PID tracking
SERVER_PID=""

# Cleanup handler
cleanup() {
    local exit_code=$?
    log_info "Cleanup triggered (exit code: ${exit_code})"

    # Kill server if running
    if [[ -n "${SERVER_PID}" ]]; then
        log_info "Stopping server (PID: ${SERVER_PID})"
        kill -TERM "${SERVER_PID}" 2>/dev/null || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi

    # Clean up any lingering netcat processes
    pkill -f "nc -l.*${DEFAULT_PORT}" 2>/dev/null || true

    log_info "Cleanup complete"
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
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"query-handler\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# Query Processing
################################################################################

process_query() {
    local domain="$1"
    local topic="$2"
    local format="${3:-${DEFAULT_FORMAT}}"
    local max_tokens="${4:-${DEFAULT_MAX_TOKENS}}"

    # Input validation
    if [[ -z "${domain}" ]] || [[ -z "${topic}" ]]; then
        log_error "Domain and topic are required"
        echo '{"error":"Domain and topic are required","confidence":0.0}'
        return 1
    fi

    # Sanitize inputs to prevent injection
    domain=$(echo "${domain}" | tr -cd '[:alnum:]-_')
    topic=$(echo "${topic}" | head -c 200)  # Limit topic length

    log_info "Processing query - Domain: ${domain}, Topic: ${topic}, Format: ${format}"

    # Search index with timeout
    local search_results="[]"
    if ! search_results=$(timeout 30 bash "${SCRIPT_DIR}/indexer.sh" search "${domain}" "${topic}" 10 2>/dev/null || echo "[]"); then
        log_error "Search timeout or error for query: ${topic}"
        echo '{"error":"Search timeout","confidence":0.0}'
        return 1
    fi

    if [[ "${search_results}" == "[]" ]]; then
        log_warn "No results found for query: ${topic}"

        # Return empty result
        cat <<EOF
{
  "domain": "${domain}",
  "topic": "${topic}",
  "results": [],
  "confidence": 0.0,
  "format": "${format}",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "documentation_used": []
}
EOF
        return 0
    fi

    # Extract top results
    local result_count=$(echo "${search_results}" | jq 'length')
    local top_result=$(echo "${search_results}" | jq '.[0]')

    if [[ "${top_result}" == "null" ]] || [[ -z "${top_result}" ]]; then
        log_warn "No valid results found"
        echo "{\"domain\":\"${domain}\",\"topic\":\"${topic}\",\"results\":[],\"confidence\":0.0}"
        return 0
    fi

    local relevance=$(echo "${top_result}" | jq -r '.relevance // 0')
    local url=$(echo "${top_result}" | jq -r '.url // "unknown"')
    local content_file=$(echo "${top_result}" | jq -r '.content_file // ""')
    local preview=$(echo "${top_result}" | jq -r '.preview // ""')

    # Calculate confidence (0.0 - 1.0)
    # Relevance score / 20 gives us a rough confidence
    local confidence=$(echo "scale=2; ${relevance} / 20" | bc 2>/dev/null || echo "0.5")
    if (( $(echo "${confidence} > 1.0" | bc -l 2>/dev/null || echo 0) )); then
        confidence="1.0"
    fi

    # Read content based on format
    local content=""
    if [[ "${format}" == "detailed" ]] && [[ -f "${content_file}" ]]; then
        # Return full content (truncated to max_tokens)
        # Rough approximation: 4 chars per token
        local max_chars=$((max_tokens * 4))
        content=$(head -c "${max_chars}" "${content_file}" | jq -R -s '.')
    else
        # Return preview only
        content=$(echo "${preview}" | jq -R -s '.')
    fi

    # Extract all URLs from results
    local documentation_used=$(echo "${search_results}" | jq -c '[.[].url]')

    # Build response
    cat <<EOF
{
  "domain": "${domain}",
  "topic": "${topic}",
  "results": [
    {
      "url": "${url}",
      "preview": $(echo "${preview}" | jq -R -s '.'),
      "content": ${content},
      "relevance": ${relevance}
    }
  ],
  "confidence": ${confidence},
  "result_count": ${result_count},
  "format": "${format}",
  "max_tokens": ${max_tokens},
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "documentation_used": ${documentation_used}
}
EOF

    log_info "Query processed - Results: ${result_count}, Confidence: ${confidence}"
}

################################################################################
# HTTP Server
################################################################################

handle_request() {
    local request_line="$1"

    # Parse request
    local method=$(echo "${request_line}" | awk '{print $1}')
    local path=$(echo "${request_line}" | awk '{print $2}')

    log_info "Handling request: ${method} ${path}"

    # Health check
    if [[ "${path}" == "/health" ]]; then
        cat <<EOF
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"healthy","service":"documentation-query-handler"}
EOF
        return 0
    fi

    # Query endpoint
    if [[ "${path}" =~ ^/query ]]; then
        # Read POST body (simplified - in production use proper HTTP parsing)
        local body=""
        while IFS= read -r line; do
            line=$(echo "$line" | tr -d '\r')
            [[ -z "$line" ]] && break
        done
        while IFS= read -r -t 0.1 line 2>/dev/null; do
            body="${body}${line}"
        done

        # Parse JSON body
        if [[ -n "${body}" ]]; then
            local domain=$(echo "${body}" | jq -r '.domain // "sandfly"')
            local topic=$(echo "${body}" | jq -r '.topic // ""')
            local format=$(echo "${body}" | jq -r '.format // "summary"')
            local max_tokens=$(echo "${body}" | jq -r '.maxTokens // 5000')

            if [[ -z "${topic}" ]]; then
                cat <<EOF
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error":"Topic is required"}
EOF
                return 1
            fi

            local result=$(process_query "${domain}" "${topic}" "${format}" "${max_tokens}")

            cat <<EOF
HTTP/1.1 200 OK
Content-Type: application/json

${result}
EOF
        else
            cat <<EOF
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error":"Request body required"}
EOF
        fi

        return 0
    fi

    # Not found
    cat <<EOF
HTTP/1.1 404 Not Found
Content-Type: application/json

{"error":"Not found"}
EOF
}

serve() {
    local port="${1:-${DEFAULT_PORT}}"

    log_info "Starting query handler server on port ${port}"

    # Simple HTTP server loop
    while true; do
        # Read request using netcat
        {
            request_line=$(head -n 1)
            handle_request "${request_line}"
        } | nc -l -p "${port}" -q 1 2>/dev/null || true

        sleep 0.1
    done
}

################################################################################
# CLI Query
################################################################################

cli_query() {
    local domain="$1"
    local topic="$2"
    local format="${3:-summary}"
    local max_tokens="${4:-5000}"

    process_query "${domain}" "${topic}" "${format}" "${max_tokens}"
}

################################################################################
# Main
################################################################################

main() {
    local command="${1:-}"
    shift || true

    case "${command}" in
        serve)
            local port="${1:-${DEFAULT_PORT}}"
            serve "${port}"
            ;;

        query)
            local domain="${1:-}"
            local topic="${2:-}"
            local format="${3:-summary}"
            local max_tokens="${4:-5000}"

            if [[ -z "${domain}" ]] || [[ -z "${topic}" ]]; then
                log_error "Domain and topic required"
                exit 1
            fi

            cli_query "${domain}" "${topic}" "${format}" "${max_tokens}"
            ;;

        *)
            echo "Usage: $0 {serve|query} [options]"
            echo ""
            echo "Commands:"
            echo "  serve [port]                                    - Start HTTP server"
            echo "  query <domain> <topic> [format] [max_tokens]    - Query documentation"
            echo ""
            echo "Formats: summary, detailed"
            exit 1
            ;;
    esac
}

main "$@"
