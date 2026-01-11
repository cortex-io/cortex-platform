#!/bin/bash

################################################################################
# Documentation Indexer
#
# Indexes crawled documentation content for fast querying. Creates searchable
# metadata, extracts headers, code blocks, and key concepts.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
CONFIG_DIR="${MASTER_DIR}/config"
KNOWLEDGE_BASE_DIR="${MASTER_DIR}/knowledge-base"
CACHE_DIR="${MASTER_DIR}/cache"

# Cleanup handler
cleanup() {
    local exit_code=$?

    # Remove temporary files
    find "${CACHE_DIR}/indexed-content" -name "*.tmp" -delete 2>/dev/null || true
    find "${CACHE_DIR}/indexed-content" -name "*.index.tmp" -delete 2>/dev/null || true

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
    echo "{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"component\":\"indexer\",\"message\":\"${message}\"}"
}

log_info() { log "info" "$@"; }
log_warn() { log "warn" "$@"; }
log_error() { log "error" "$@"; }

################################################################################
# Content Analysis
################################################################################

extract_headers() {
    local content_file="$1"

    # Extract lines that look like headers (all caps, short lines, etc.)
    grep -E '^[A-Z][A-Z ]{3,50}$' "${content_file}" 2>/dev/null || true
}

extract_code_blocks() {
    local content_file="$1"

    # Extract code-like patterns (indented blocks, common code keywords)
    awk '
        /^    / { in_code=1; code=code $0 "\n"; next }
        /function |class |def |import |const |let |var / { in_code=1; code=code $0 "\n"; next }
        {
            if (in_code && NF > 0) {
                code = code $0 "\n"
            } else if (in_code) {
                print code
                code = ""
                in_code = 0
            }
        }
        END { if (code) print code }
    ' "${content_file}" 2>/dev/null || true
}

extract_keywords() {
    local content_file="$1"
    local domain="$2"

    # Domain-specific keyword extraction
    case "${domain}" in
        sandfly)
            grep -oiE '\b(alert|host|process|forensic|policy|scan|threat|detection|malware|rootkit|security|api|endpoint)\b' "${content_file}" | \
                tr '[:upper:]' '[:lower:]' | \
                sort | uniq -c | sort -rn | head -20
            ;;
        proxmox)
            grep -oiE '\b(vm|container|cluster|node|storage|network|backup|snapshot|template|qemu|lxc)\b' "${content_file}" | \
                tr '[:upper:]' '[:lower:]' | \
                sort | uniq -c | sort -rn | head -20
            ;;
        k3s)
            grep -oiE '\b(pod|deployment|service|ingress|namespace|configmap|secret|node|cluster|kubectl)\b' "${content_file}" | \
                tr '[:upper:]' '[:lower:]' | \
                sort | uniq -c | sort -rn | head -20
            ;;
        *)
            # Generic keyword extraction - most common meaningful words
            tr -cs '[:alnum:]' '\n' < "${content_file}" | \
                tr '[:upper:]' '[:lower:]' | \
                grep -E '^[a-z]{4,}$' | \
                sort | uniq -c | sort -rn | head -20
            ;;
    esac
}

################################################################################
# Index Builder
################################################################################

build_index() {
    local content_file="$1"
    local domain="$2"
    local url_hash="$3"

    local index_file="${CACHE_DIR}/indexed-content/${domain}/${url_hash}.index.json"

    # Validate input file
    if [[ ! -f "${content_file}" ]]; then
        log_error "Content file not found: ${content_file}"
        return 1
    fi

    # Check file size limits (from config)
    local max_file_size=$((10 * 1024 * 1024))  # 10MB default
    if [[ -f "${CONFIG_DIR}/resource-limits.json" ]]; then
        max_file_size=$(jq -r '.indexing.max_file_size_bytes // 10485760' "${CONFIG_DIR}/resource-limits.json")
    fi

    local file_size=$(stat -f%z "${content_file}" 2>/dev/null || stat -c%s "${content_file}" 2>/dev/null || echo 0)
    if [[ ${file_size} -gt ${max_file_size} ]]; then
        log_warn "File too large (${file_size} bytes), skipping: ${content_file}"
        return 1
    fi

    log_info "Building index for ${content_file}"

    # Extract metadata with error handling
    local meta_file="${CACHE_DIR}/metadata/${domain}/${url_hash}.json"
    local url="unknown"
    local last_crawled="unknown"

    if [[ -f "${meta_file}" ]]; then
        url=$(jq -r '.url // "unknown"' "${meta_file}" 2>/dev/null || echo "unknown")
        last_crawled=$(jq -r '.last_crawled // "unknown"' "${meta_file}" 2>/dev/null || echo "unknown")
    fi

    # Get file stats with error handling
    local line_count=$(wc -l < "${content_file}" 2>/dev/null || echo 0)
    local word_count=$(wc -w < "${content_file}" 2>/dev/null || echo 0)
    local char_count=${file_size}

    # Extract headers with error handling
    local headers="[]"
    if headers=$(extract_headers "${content_file}" 2>/dev/null | jq -R -s -c 'split("\n") | map(select(length > 0))' 2>/dev/null); then
        [[ -z "${headers}" ]] && headers="[]"
    else
        headers="[]"
    fi

    # Extract keywords with error handling
    local keywords="[]"
    if keywords=$(extract_keywords "${content_file}" "${domain}" 2>/dev/null | awk '{print $2}' | jq -R -s -c 'split("\n") | map(select(length > 0))' 2>/dev/null); then
        [[ -z "${keywords}" ]] && keywords="[]"
    else
        keywords="[]"
    fi

    # Generate preview (first 500 chars) with error handling
    local preview=""
    if preview=$(head -c 500 "${content_file}" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g'); then
        [[ -z "${preview}" ]] && preview="No preview available"
    else
        preview="No preview available"
    fi

    # Create index JSON with temp file for atomicity
    cat > "${index_file}.tmp" <<EOF
{
  "url": "${url}",
  "domain": "${domain}",
  "hash": "${url_hash}",
  "last_indexed": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "last_crawled": "${last_crawled}",
  "stats": {
    "lines": ${line_count},
    "words": ${word_count},
    "chars": ${char_count}
  },
  "headers": ${headers},
  "keywords": ${keywords},
  "preview": $(echo "${preview}" | jq -R -s '.'),
  "content_file": "${content_file}"
}
EOF

    # Validate generated JSON before moving
    if jq empty "${index_file}.tmp" 2>/dev/null; then
        mv "${index_file}.tmp" "${index_file}"
        log_info "Index created: ${index_file}"
        return 0
    else
        log_error "Invalid JSON generated for index: ${index_file}"
        rm -f "${index_file}.tmp"
        return 1
    fi
}

################################################################################
# Master Index
################################################################################

update_master_index() {
    local domain="$1"

    local master_index="${CACHE_DIR}/indexed-content/${domain}/master-index.json"
    local temp_index="${master_index}.tmp"

    log_info "Updating master index for domain: ${domain}"

    # Collect all individual indexes
    echo "[" > "${temp_index}"

    local first=true
    for index_file in "${CACHE_DIR}/indexed-content/${domain}"/*.index.json; do
        if [[ -f "${index_file}" ]]; then
            if [[ "${first}" == "true" ]]; then
                first=false
            else
                echo "," >> "${temp_index}"
            fi
            cat "${index_file}" >> "${temp_index}"
        fi
    done

    echo "]" >> "${temp_index}"

    # Validate JSON
    if jq empty "${temp_index}" 2>/dev/null; then
        mv "${temp_index}" "${master_index}"
        log_info "Master index updated: ${master_index}"

        # Generate statistics
        local total_docs=$(jq 'length' "${master_index}")
        local total_words=$(jq '[.[].stats.words] | add' "${master_index}")
        local avg_words=$(jq '[.[].stats.words] | add / length' "${master_index}")

        log_info "Index stats - Docs: ${total_docs}, Total words: ${total_words}, Avg words: ${avg_words}"
    else
        log_error "Invalid JSON generated for master index"
        rm -f "${temp_index}"
        return 1
    fi
}

################################################################################
# Batch Indexing
################################################################################

index_domain() {
    local domain="$1"

    log_info "Starting batch indexing for domain: ${domain}"

    local content_dir="${KNOWLEDGE_BASE_DIR}/${domain}"

    if [[ ! -d "${content_dir}" ]]; then
        log_error "Content directory not found: ${content_dir}"
        return 1
    fi

    # Create index directory
    mkdir -p "${CACHE_DIR}/indexed-content/${domain}"

    # Index all content files
    local count=0
    for content_file in "${content_dir}"/*.txt; do
        if [[ -f "${content_file}" ]]; then
            local filename=$(basename "${content_file}" .txt)
            build_index "${content_file}" "${domain}" "${filename}"
            ((count++))
        fi
    done

    log_info "Indexed ${count} documents for ${domain}"

    # Update master index
    update_master_index "${domain}"
}

################################################################################
# Search Index
################################################################################

search_index() {
    local domain="$1"
    local query="$2"
    local limit="${3:-10}"

    local master_index="${CACHE_DIR}/indexed-content/${domain}/master-index.json"

    if [[ ! -f "${master_index}" ]]; then
        log_error "Master index not found for domain: ${domain}"
        return 1
    fi

    log_info "Searching index for: ${query} (limit: ${limit})"

    # Simple keyword-based search
    # In production, this would use vector embeddings or full-text search
    local query_lower=$(echo "${query}" | tr '[:upper:]' '[:lower:]')

    jq --arg query "${query_lower}" --arg limit "${limit}" '
        map(
            select(
                (.keywords | map(ascii_downcase) | any(contains($query))) or
                (.preview | ascii_downcase | contains($query)) or
                (.headers | map(ascii_downcase) | any(contains($query)))
            ) |
            . + {
                "relevance": (
                    (.keywords | map(select(ascii_downcase | contains($query))) | length) * 3 +
                    (if (.preview | ascii_downcase | contains($query)) then 2 else 0 end) +
                    (.headers | map(select(ascii_downcase | contains($query))) | length) * 5
                )
            }
        ) |
        sort_by(-.relevance) |
        limit($limit | tonumber)
    ' "${master_index}"
}

################################################################################
# Main
################################################################################

main() {
    local command="${1:-}"
    shift || true

    case "${command}" in
        index)
            local domain="${1:-}"
            if [[ -z "${domain}" ]]; then
                log_error "Domain name required"
                exit 1
            fi
            index_domain "${domain}"
            ;;

        search)
            local domain="${1:-}"
            local query="${2:-}"
            local limit="${3:-10}"

            if [[ -z "${domain}" ]] || [[ -z "${query}" ]]; then
                log_error "Domain and query required"
                exit 1
            fi

            search_index "${domain}" "${query}" "${limit}"
            ;;

        update-master)
            local domain="${1:-}"
            if [[ -z "${domain}" ]]; then
                log_error "Domain name required"
                exit 1
            fi
            update_master_index "${domain}"
            ;;

        *)
            echo "Usage: $0 {index|search|update-master} [options]"
            echo ""
            echo "Commands:"
            echo "  index <domain>                    - Index all content for domain"
            echo "  search <domain> <query> [limit]   - Search indexed content"
            echo "  update-master <domain>            - Update master index"
            exit 1
            ;;
    esac
}

main "$@"
