#!/bin/bash

################################################################################
# Crawler Worker
#
# Spawnable worker for parallel crawling tasks. Designed to be launched
# multiple times for concurrent crawling with proper resource limits.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
LIB_DIR="${MASTER_DIR}/lib"

# Worker ID (can be set externally)
WORKER_ID="${WORKER_ID:-$(uuidgen 2>/dev/null || echo "worker-$$")}"

# Cleanup handler
cleanup() {
    local exit_code=$?
    log_info "Crawler worker cleanup (exit code: ${exit_code})"
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
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"crawler-worker\",\"worker_id\":\"${WORKER_ID}\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# Worker Main
################################################################################

main() {
    local url="$1"
    local domain="$2"
    local depth="${3:-0}"
    local max_depth="${4:-5}"

    # Validate inputs
    if [[ -z "${url}" ]] || [[ -z "${domain}" ]]; then
        log_error "URL and domain are required"
        exit 1
    fi

    # Validate crawler script exists
    if [[ ! -x "${LIB_DIR}/crawler.sh" ]]; then
        log_error "Crawler script not found or not executable: ${LIB_DIR}/crawler.sh"
        exit 1
    fi

    log_info "Starting crawl - URL: ${url}, Domain: ${domain}, Depth: ${depth}/${max_depth}"

    # Delegate to main crawler with timeout (30 minutes)
    if timeout 1800 "${LIB_DIR}/crawler.sh" url "${url}" "${domain}" "${max_depth}"; then
        log_info "Crawl completed successfully"
        exit 0
    else
        local exit_code=$?
        if [[ ${exit_code} -eq 124 ]]; then
            log_error "Crawl timeout after 1800 seconds"
        else
            log_error "Crawl failed (exit code: ${exit_code})"
        fi
        exit "${exit_code}"
    fi
}

# Validate arguments
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <url> <domain> [depth] [max_depth]"
    exit 1
fi

main "$@"
