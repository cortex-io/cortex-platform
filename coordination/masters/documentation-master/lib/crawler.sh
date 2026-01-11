#!/bin/bash

################################################################################
# Documentation Crawler
#
# Crawls external documentation sources with respect for robots.txt, rate
# limiting, and resource constraints. Stores raw content for indexing.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
CONFIG_DIR="${MASTER_DIR}/config"
KNOWLEDGE_BASE_DIR="${MASTER_DIR}/knowledge-base"
CACHE_DIR="${MASTER_DIR}/cache"

# Track child processes for cleanup
declare -a CHILD_PIDS=()

# Cleanup handler
cleanup() {
    local exit_code=$?
    log_info "Cleanup triggered (exit code: ${exit_code})"

    # Kill all child processes
    if [[ ${#CHILD_PIDS[@]} -gt 0 ]]; then
        log_info "Killing ${#CHILD_PIDS[@]} child processes"
        for pid in "${CHILD_PIDS[@]}"; do
            kill -TERM "${pid}" 2>/dev/null || true
        done
        wait 2>/dev/null || true
    fi

    # Remove incomplete files
    find "${CACHE_DIR}/indexed-content" -name "*.tmp" -delete 2>/dev/null || true
    find "${KNOWLEDGE_BASE_DIR}" -name "*.tmp" -delete 2>/dev/null || true

    log_info "Cleanup complete"
    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

# Load resource limits
if [[ -f "${CONFIG_DIR}/resource-limits.json" ]]; then
    RATE_LIMIT_RPM=$(jq -r '.rate_limiting.requests_per_minute // 60' "${CONFIG_DIR}/resource-limits.json")
    MAX_CONCURRENT=$(jq -r '.rate_limiting.concurrent_crawls // 5' "${CONFIG_DIR}/resource-limits.json")
else
    RATE_LIMIT_RPM=60
    MAX_CONCURRENT=5
fi

# Calculate delay between requests (in seconds)
REQUEST_DELAY=$(echo "scale=2; 60 / ${RATE_LIMIT_RPM}" | bc)

################################################################################
# Logging
################################################################################

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"crawler\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# Robots.txt Handler
################################################################################

check_robots_txt() {
    local base_url="$1"
    local path="$2"

    # Extract domain
    local domain=$(echo "${base_url}" | awk -F[/:] '{print $4}')

    # Cache robots.txt
    local robots_cache="${CACHE_DIR}/metadata/robots_${domain}.txt"

    if [[ ! -f "${robots_cache}" ]] || [[ $(find "${robots_cache}" -mtime +1) ]]; then
        log_info "Fetching robots.txt for ${domain}"
        curl -s -L "${base_url}/robots.txt" -o "${robots_cache}" 2>/dev/null || echo "" > "${robots_cache}"
    fi

    # Simple robots.txt parser (checks User-agent: * Disallow rules)
    if grep -q "Disallow: ${path}" "${robots_cache}" 2>/dev/null; then
        log_warn "Path ${path} is disallowed by robots.txt"
        return 1
    fi

    return 0
}

################################################################################
# Content Fetcher
################################################################################

fetch_content() {
    local url="$1"
    local output_file="$2"
    local max_retries=3
    local retry_count=0

    log_info "Fetching: ${url}"

    # Rate limiting delay
    sleep "${REQUEST_DELAY}"

    # Retry loop with exponential backoff
    while [[ ${retry_count} -lt ${max_retries} ]]; do
        # Fetch with curl
        local http_code=$(curl -s -L -w "%{http_code}" -o "${output_file}.tmp" \
            -H "User-Agent: CortexDocumentationBot/1.0 (+https://cortex.holdings/bot)" \
            -H "Accept: text/html,application/xhtml+xml" \
            --max-time 30 \
            --compressed \
            "${url}" 2>/dev/null || echo "000")

        if [[ "${http_code}" == "200" ]]; then
            # Verify file size
            local file_size=$(stat -f%z "${output_file}.tmp" 2>/dev/null || stat -c%s "${output_file}.tmp" 2>/dev/null || echo 0)

            if [[ ${file_size} -gt 100 ]]; then  # Minimum valid file size
                mv "${output_file}.tmp" "${output_file}"
                log_info "Successfully fetched: ${url} (${http_code}, ${file_size} bytes)"
                return 0
            else
                log_warn "Fetched file too small (${file_size} bytes), retrying..."
            fi
        else
            log_warn "Failed to fetch: ${url} (HTTP ${http_code}), retry ${retry_count}/${max_retries}"
        fi

        # Exponential backoff
        ((retry_count++))
        if [[ ${retry_count} -lt ${max_retries} ]]; then
            local backoff_delay=$((2 ** retry_count))
            sleep "${backoff_delay}"
        fi
    done

    # All retries failed
    log_error "Failed to fetch after ${max_retries} retries: ${url}"
    rm -f "${output_file}" "${output_file}.tmp"
    return 1
}

################################################################################
# HTML Parser
################################################################################

extract_links() {
    local html_file="$1"
    local base_url="$2"

    # Extract links using grep and sed (simple parser)
    grep -oP 'href=["'"'"']\K[^"'"'"']+' "${html_file}" 2>/dev/null | while read -r link; do
        # Skip anchors, javascript, mailto, etc.
        if [[ "${link}" =~ ^# ]] || [[ "${link}" =~ ^javascript: ]] || [[ "${link}" =~ ^mailto: ]]; then
            continue
        fi

        # Convert relative URLs to absolute
        if [[ "${link}" =~ ^/ ]]; then
            echo "${base_url}${link}"
        elif [[ "${link}" =~ ^http ]]; then
            echo "${link}"
        else
            echo "${base_url}/${link}"
        fi
    done | sort -u
}

extract_content() {
    local html_file="$1"
    local selectors="$2"

    # For now, just strip HTML tags and extract text
    # In production, would use proper HTML parser (pup, xmllint, etc.)

    # Simple text extraction
    sed 's/<[^>]*>//g' "${html_file}" | \
        sed 's/&nbsp;/ /g' | \
        sed 's/&amp;/\&/g' | \
        sed 's/&lt;/</g' | \
        sed 's/&gt;/>/g' | \
        sed '/^[[:space:]]*$/d' | \
        head -n 10000  # Limit to prevent huge files
}

################################################################################
# Crawler Logic
################################################################################

crawl_url() {
    local url="$1"
    local domain="$2"
    local current_depth="${3:-0}"
    local max_depth="${4:-5}"

    # Check depth limit
    if [[ "${current_depth}" -ge "${max_depth}" ]]; then
        log_info "Max depth reached for ${url}"
        return 0
    fi

    # Check robots.txt
    local path=$(echo "${url}" | sed "s|https\?://[^/]*||")
    local base_url=$(echo "${url}" | grep -oP 'https?://[^/]+')

    if ! check_robots_txt "${base_url}" "${path}"; then
        return 0
    fi

    # Generate output filename
    local url_hash=$(echo -n "${url}" | sha256sum | awk '{print $1}')
    local html_file="${CACHE_DIR}/indexed-content/${domain}/${url_hash}.html"
    local content_file="${KNOWLEDGE_BASE_DIR}/${domain}/${url_hash}.txt"
    local meta_file="${CACHE_DIR}/metadata/${domain}/${url_hash}.json"

    # Create directories
    mkdir -p "${CACHE_DIR}/indexed-content/${domain}"
    mkdir -p "${KNOWLEDGE_BASE_DIR}/${domain}"
    mkdir -p "${CACHE_DIR}/metadata/${domain}"

    # Skip if already crawled recently (within 24 hours)
    if [[ -f "${meta_file}" ]]; then
        local last_crawl=$(jq -r '.last_crawled // ""' "${meta_file}")
        if [[ -n "${last_crawl}" ]]; then
            local last_crawl_ts=$(date -d "${last_crawl}" +%s 2>/dev/null || echo 0)
            local now_ts=$(date +%s)
            local age=$((now_ts - last_crawl_ts))

            if [[ ${age} -lt 86400 ]]; then
                log_info "Skipping recently crawled URL: ${url}"
                return 0
            fi
        fi
    fi

    # Fetch content
    if ! fetch_content "${url}" "${html_file}"; then
        return 1
    fi

    # Extract text content
    extract_content "${html_file}" "" > "${content_file}"

    # Store metadata
    cat > "${meta_file}" <<EOF
{
  "url": "${url}",
  "domain": "${domain}",
  "last_crawled": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "depth": ${current_depth},
  "file_size": $(stat -f%z "${html_file}" 2>/dev/null || stat -c%s "${html_file}" 2>/dev/null || echo 0),
  "content_hash": "${url_hash}"
}
EOF

    log_info "Crawled and stored: ${url}"

    # Extract and queue links for deeper crawl
    if [[ "${current_depth}" -lt "${max_depth}" ]]; then
        local next_depth=$((current_depth + 1))

        extract_links "${html_file}" "${base_url}" | while read -r link; do
            # Only crawl links within same domain
            if [[ "${link}" =~ ^${base_url} ]]; then
                crawl_url "${link}" "${domain}" "${next_depth}" "${max_depth}" &
                local child_pid=$!
                CHILD_PIDS+=("${child_pid}")

                # Limit concurrent crawls
                while [[ $(jobs -r | wc -l) -ge ${MAX_CONCURRENT} ]]; do
                    sleep 1
                done
            fi
        done

        # Wait for child processes with timeout
        local wait_timeout=300  # 5 minutes max
        local wait_start=$(date +%s)

        while [[ $(jobs -r | wc -l) -gt 0 ]]; do
            local now=$(date +%s)
            local elapsed=$((now - wait_start))

            if [[ ${elapsed} -ge ${wait_timeout} ]]; then
                log_warn "Child processes timeout, terminating..."
                for pid in $(jobs -p); do
                    kill -TERM "${pid}" 2>/dev/null || true
                done
                break
            fi

            sleep 1
        done
    fi
}

################################################################################
# Scheduled Crawler
################################################################################

schedule_crawler() {
    local source="$1"

    log_info "Starting scheduled crawler for source: ${source}"

    # Load source configuration
    if [[ ! -f "${CONFIG_DIR}/sources.json" ]]; then
        log_error "Sources configuration not found"
        return 1
    fi

    local enabled=$(jq -r ".${source}.enabled // false" "${CONFIG_DIR}/sources.json")
    if [[ "${enabled}" != "true" ]]; then
        log_warn "Source ${source} is not enabled"
        return 0
    fi

    # Get source URLs
    local urls=$(jq -r ".${source}.sources[].url" "${CONFIG_DIR}/sources.json")
    local crawl_depth=$(jq -r ".${source}.sources[0].crawl_depth // 5" "${CONFIG_DIR}/sources.json")

    for url in ${urls}; do
        log_info "Crawling ${url} (max depth: ${crawl_depth})"
        crawl_url "${url}" "${source}" 0 "${crawl_depth}"
    done

    log_info "Scheduled crawl completed for ${source}"
}

################################################################################
# Main
################################################################################

main() {
    local command="${1:-}"
    shift || true

    case "${command}" in
        schedule)
            local source="${1:-}"
            if [[ -z "${source}" ]]; then
                log_error "Source name required"
                exit 1
            fi
            schedule_crawler "${source}"
            ;;

        url)
            local url="${1:-}"
            local domain="${2:-default}"
            local depth="${3:-5}"

            if [[ -z "${url}" ]]; then
                log_error "URL required"
                exit 1
            fi

            crawl_url "${url}" "${domain}" 0 "${depth}"
            ;;

        *)
            echo "Usage: $0 {schedule|url} [options]"
            echo ""
            echo "Commands:"
            echo "  schedule <source>              - Run scheduled crawl for source"
            echo "  url <url> <domain> [depth]     - Crawl specific URL"
            exit 1
            ;;
    esac
}

main "$@"
