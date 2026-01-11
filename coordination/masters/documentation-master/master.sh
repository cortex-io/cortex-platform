#!/bin/bash

################################################################################
# Documentation Master - Main Orchestration Script
#
# Manages documentation crawling, indexing, and evolution across all external
# integrations. Provides documentation-as-a-service to other masters and MCP
# servers.
#
# Part of the Cortex Holdings coordination layer.
################################################################################

set -euo pipefail

# Directories
MASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="${MASTER_DIR}/lib"
CONFIG_DIR="${MASTER_DIR}/config"
KNOWLEDGE_BASE_DIR="${MASTER_DIR}/knowledge-base"
CACHE_DIR="${MASTER_DIR}/cache"
WORKERS_DIR="${MASTER_DIR}/workers"

# Configuration
HEALTH_CHECK_PORT="${HEALTH_CHECK_PORT:-8080}"
QUERY_PORT="${QUERY_PORT:-8080}"
LOG_LEVEL="${LOG_LEVEL:-info}"
MOE_ENABLED="${MOE_ENABLED:-true}"

# State
PID_FILE="${CACHE_DIR}/master.pid"
LOG_FILE="${CACHE_DIR}/master.log"

################################################################################
# Logging
################################################################################

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"documentation-master\",\"message\":\"${message}\"}" | tee -a "${LOG_FILE}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }
log_debug() {
    if [[ "${LOG_LEVEL}" == "debug" ]]; then
        log "debug" "$@"
    fi
}

################################################################################
# Health Check Server
################################################################################

start_health_server() {
    log_info "Starting health check server on port ${HEALTH_CHECK_PORT}"

    # Simple HTTP server for health checks
    while true; do
        {
            echo -e "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"healthy\",\"service\":\"documentation-master\",\"uptime\":$(cat /proc/uptime | awk '{print $1}' 2>/dev/null || echo 0)}"
        } | nc -l -p "${HEALTH_CHECK_PORT}" -q 1 2>/dev/null || true
        sleep 0.1
    done &

    HEALTH_SERVER_PID=$!
    log_info "Health server started (PID: ${HEALTH_SERVER_PID})"
}

################################################################################
# Query Handler Server
################################################################################

start_query_server() {
    log_info "Starting query handler server"

    # Launch query handler in background
    "${LIB_DIR}/query-handler.sh" serve --port "${QUERY_PORT}" &
    QUERY_SERVER_PID=$!

    log_info "Query server started (PID: ${QUERY_SERVER_PID})"
}

################################################################################
# Crawler Scheduler
################################################################################

schedule_crawlers() {
    log_info "Initializing crawler scheduler"

    # Load sources configuration
    if [[ ! -f "${CONFIG_DIR}/sources.json" ]]; then
        log_error "Sources configuration not found: ${CONFIG_DIR}/sources.json"
        return 1
    fi

    # Schedule initial crawl for all enabled sources
    local sources=$(cat "${CONFIG_DIR}/sources.json" | jq -r 'to_entries[] | select(.value.enabled == true) | .key')

    for source in ${sources}; do
        log_info "Scheduling crawler for source: ${source}"
        "${LIB_DIR}/crawler.sh" schedule --source "${source}" &
    done
}

################################################################################
# MoE Integration
################################################################################

init_moe_integration() {
    if [[ "${MOE_ENABLED}" != "true" ]]; then
        log_info "MoE integration disabled"
        return 0
    fi

    log_info "Initializing MoE learning integration"

    # Register with MoE learning system
    if [[ -f "${LIB_DIR}/learner.sh" ]]; then
        "${LIB_DIR}/learner.sh" register --role "documentation-master" &
        MOE_LEARNER_PID=$!
        log_info "MoE learner started (PID: ${MOE_LEARNER_PID})"
    else
        log_warn "MoE learner script not found, continuing without learning integration"
    fi
}

################################################################################
# Cleanup
################################################################################

cleanup() {
    log_info "Shutting down documentation master..."

    # Kill background processes
    [[ -n "${HEALTH_SERVER_PID:-}" ]] && kill "${HEALTH_SERVER_PID}" 2>/dev/null || true
    [[ -n "${QUERY_SERVER_PID:-}" ]] && kill "${QUERY_SERVER_PID}" 2>/dev/null || true
    [[ -n "${MOE_LEARNER_PID:-}" ]] && kill "${MOE_LEARNER_PID}" 2>/dev/null || true

    # Remove PID file
    rm -f "${PID_FILE}"

    log_info "Documentation master stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

################################################################################
# Status Check
################################################################################

check_status() {
    log_info "Checking documentation master status"

    # Check if master is running
    if [[ -f "${PID_FILE}" ]]; then
        local pid=$(cat "${PID_FILE}")
        if ps -p "${pid}" > /dev/null 2>&1; then
            echo "Documentation Master is running (PID: ${pid})"

            # Check component status
            echo ""
            echo "Component Status:"
            echo "  Health Server: $(nc -z localhost ${HEALTH_CHECK_PORT} && echo 'Running' || echo 'Stopped')"
            echo "  Query Server: $(nc -z localhost ${QUERY_PORT} && echo 'Running' || echo 'Stopped')"

            # Check knowledge base stats
            echo ""
            echo "Knowledge Base Statistics:"
            for domain in "${KNOWLEDGE_BASE_DIR}"/*; do
                if [[ -d "${domain}" ]]; then
                    local domain_name=$(basename "${domain}")
                    local file_count=$(find "${domain}" -type f | wc -l)
                    echo "  ${domain_name}: ${file_count} files"
                fi
            done

            return 0
        fi
    fi

    echo "Documentation Master is not running"
    return 1
}

################################################################################
# Main
################################################################################

main() {
    local command="${1:-start}"

    case "${command}" in
        start)
            log_info "Starting Documentation Master"

            # Save PID
            echo $$ > "${PID_FILE}"

            # Start components
            start_health_server
            start_query_server
            schedule_crawlers
            init_moe_integration

            log_info "Documentation Master started successfully"
            log_info "Health endpoint: http://localhost:${HEALTH_CHECK_PORT}/health"
            log_info "Query endpoint: http://localhost:${QUERY_PORT}/query"

            # Keep alive
            wait
            ;;

        status)
            check_status
            ;;

        stop)
            if [[ -f "${PID_FILE}" ]]; then
                local pid=$(cat "${PID_FILE}")
                log_info "Stopping Documentation Master (PID: ${pid})"
                kill -TERM "${pid}"
            else
                log_warn "PID file not found, master may not be running"
            fi
            ;;

        restart)
            "$0" stop
            sleep 2
            "$0" start
            ;;

        query)
            shift
            "${LIB_DIR}/query-handler.sh" query "$@"
            ;;

        crawl)
            shift
            "${LIB_DIR}/crawler.sh" "$@"
            ;;

        index)
            shift
            "${LIB_DIR}/indexer.sh" "$@"
            ;;

        *)
            echo "Usage: $0 {start|stop|restart|status|query|crawl|index}"
            echo ""
            echo "Commands:"
            echo "  start     - Start the Documentation Master"
            echo "  stop      - Stop the Documentation Master"
            echo "  restart   - Restart the Documentation Master"
            echo "  status    - Check master status"
            echo "  query     - Query documentation"
            echo "  crawl     - Manually trigger crawl"
            echo "  index     - Manually trigger indexing"
            exit 1
            ;;
    esac
}

# Initialize log file
mkdir -p "${CACHE_DIR}"
touch "${LOG_FILE}"

# Run main
main "$@"
