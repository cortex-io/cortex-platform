#!/bin/bash

################################################################################
# Indexer Worker
#
# Spawnable worker for parallel indexing tasks. Processes content files
# and builds search indexes.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
LIB_DIR="${MASTER_DIR}/lib"

# Worker ID
WORKER_ID="${WORKER_ID:-$(uuidgen 2>/dev/null || echo "worker-$$")}"

# Cleanup handler
cleanup() {
    local exit_code=$?
    log_info "Indexer worker cleanup (exit code: ${exit_code})"
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
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"indexer-worker\",\"worker_id\":\"${WORKER_ID}\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# Worker Main
################################################################################

main() {
    local domain="$1"

    # Validate inputs
    if [[ -z "${domain}" ]]; then
        log_error "Domain is required"
        exit 1
    fi

    # Validate indexer script exists
    if [[ ! -x "${LIB_DIR}/indexer.sh" ]]; then
        log_error "Indexer script not found or not executable: ${LIB_DIR}/indexer.sh"
        exit 1
    fi

    log_info "Starting indexing for domain: ${domain}"

    # Delegate to main indexer with timeout (20 minutes)
    if timeout 1200 "${LIB_DIR}/indexer.sh" index "${domain}"; then
        log_info "Indexing completed successfully"
        exit 0
    else
        local exit_code=$?
        if [[ ${exit_code} -eq 124 ]]; then
            log_error "Indexing timeout after 1200 seconds"
        else
            log_error "Indexing failed (exit code: ${exit_code})"
        fi
        exit "${exit_code}"
    fi
}

# Validate arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <domain>"
    exit 1
fi

main "$@"
