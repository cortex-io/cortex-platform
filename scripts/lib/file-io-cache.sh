#!/usr/bin/env bash
# File I/O Caching and Optimization Library
# Reduces redundant file reads and improves performance

set -euo pipefail

# Prevent re-sourcing
if [ -n "${FILE_IO_CACHE_LOADED:-}" ]; then
    return 0
fi
FILE_IO_CACHE_LOADED=1

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Cache directory
readonly CACHE_DIR="/tmp/cortex-file-cache-$$"
readonly CACHE_TTL=300  # 5 minutes

# Batch operation buffer
declare -a BATCH_READ_BUFFER=()
declare -a BATCH_WRITE_BUFFER=()

# Initialize cache
init_file_cache() {
    mkdir -p "$CACHE_DIR"
}

# Cleanup cache
cleanup_file_cache() {
    rm -rf "$CACHE_DIR"
}

# Register cleanup on exit
trap cleanup_file_cache EXIT

# ==============================================================================
# CACHED FILE OPERATIONS
# ==============================================================================

# Cached file read
# Args: $1=file_path
# Returns: file contents
cached_read() {
    local file_path="$1"
    local cache_key=$(echo -n "$file_path" | md5sum | cut -d' ' -f1)
    local cache_file="$CACHE_DIR/$cache_key"

    # Check if cached and not expired
    if [[ -f "$cache_file" ]]; then
        local cache_age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file")))

        if [[ $cache_age -lt $CACHE_TTL ]]; then
            # Cache hit
            cat "$cache_file"
            return 0
        fi
    fi

    # Cache miss - read from disk and cache
    if [[ -f "$file_path" ]]; then
        cat "$file_path" | tee "$cache_file"
    else
        echo "ERROR: File not found: $file_path" >&2
        return 1
    fi
}

# Invalidate cache for file
# Args: $1=file_path
invalidate_cache() {
    local file_path="$1"
    local cache_key=$(echo -n "$file_path" | md5sum | cut -d' ' -f1)
    local cache_file="$CACHE_DIR/$cache_key"

    rm -f "$cache_file"
}

# ==============================================================================
# BATCH OPERATIONS
# ==============================================================================

# Add file to batch read buffer
# Args: $1=file_path
batch_read_add() {
    local file_path="$1"
    BATCH_READ_BUFFER+=("$file_path")
}

# Execute batch read
# Returns: all file contents concatenated
batch_read_execute() {
    if [[ ${#BATCH_READ_BUFFER[@]} -eq 0 ]]; then
        return 0
    fi

    # Read all files in parallel
    for file_path in "${BATCH_READ_BUFFER[@]}"; do
        if [[ -f "$file_path" ]]; then
            cat "$file_path" &
        fi
    done
    wait

    # Clear buffer
    BATCH_READ_BUFFER=()
}

# Add content to batch write buffer
# Args: $1=file_path, $2=content
batch_write_add() {
    local file_path="$1"
    local content="$2"

    BATCH_WRITE_BUFFER+=("$file_path:::$content")
}

# Execute batch write
batch_write_execute() {
    if [[ ${#BATCH_WRITE_BUFFER[@]} -eq 0 ]]; then
        return 0
    fi

    # Write all files in parallel
    for entry in "${BATCH_WRITE_BUFFER[@]}"; do
        local file_path="${entry%%:::*}"
        local content="${entry#*:::}"

        echo "$content" > "$file_path" &
    done
    wait

    # Clear buffer
    BATCH_WRITE_BUFFER=()
}

# ==============================================================================
# JSON OPTIMIZATION
# ==============================================================================

# Cached jq query (memoization)
# Args: $1=file_path, $2=jq_query
cached_jq() {
    local file_path="$1"
    local jq_query="$2"
    local cache_key=$(echo -n "$file_path:$jq_query" | md5sum | cut -d' ' -f1)
    local cache_file="$CACHE_DIR/jq-$cache_key"

    # Check cache
    if [[ -f "$cache_file" ]]; then
        local cache_age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file")))

        if [[ $cache_age -lt $CACHE_TTL ]]; then
            cat "$cache_file"
            return 0
        fi
    fi

    # Execute and cache
    jq "$jq_query" "$file_path" | tee "$cache_file"
}

# Batch jq queries (single file, multiple queries)
# Args: $1=file_path, $@=jq_queries
batch_jq() {
    local file_path="$1"
    shift
    local queries=("$@")

    # Read file once, execute all queries
    local file_content=$(cat "$file_path")

    for query in "${queries[@]}"; do
        echo "$file_content" | jq "$query"
    done
}

# ==============================================================================
# STREAMING OPERATIONS
# ==============================================================================

# Stream large JSONL file (avoid loading into memory)
# Args: $1=file_path, $2=jq_filter
stream_jsonl() {
    local file_path="$1"
    local jq_filter="${2:-.}"

    # Process line by line
    while IFS= read -r line; do
        echo "$line" | jq -c "$jq_filter"
    done < "$file_path"
}

# Append to JSONL without full read
# Args: $1=file_path, $2=json_object
append_jsonl() {
    local file_path="$1"
    local json_object="$2"

    # Direct append (O(1))
    echo "$json_object" >> "$file_path"
}

# ==============================================================================
# FILE WATCHING
# ==============================================================================

# Check if file changed since last read
# Args: $1=file_path, $2=last_mtime
file_changed() {
    local file_path="$1"
    local last_mtime="$2"

    if [[ ! -f "$file_path" ]]; then
        return 1
    fi

    local current_mtime=$(stat -f %m "$file_path" 2>/dev/null || stat -c %Y "$file_path")

    if [[ "$current_mtime" -gt "$last_mtime" ]]; then
        return 0  # Changed
    else
        return 1  # Not changed
    fi
}

# Get file modification time
# Args: $1=file_path
get_mtime() {
    local file_path="$1"
    stat -f %m "$file_path" 2>/dev/null || stat -c %Y "$file_path"
}

# ==============================================================================
# PERFORMANCE MONITORING
# ==============================================================================

# Track read performance
declare -i CACHE_HITS=0
declare -i CACHE_MISSES=0

get_cache_stats() {
    local hit_rate=0
    local total=$((CACHE_HITS + CACHE_MISSES))

    if [[ $total -gt 0 ]]; then
        hit_rate=$((CACHE_HITS * 100 / total))
    fi

    jq -n \
        --arg hits "$CACHE_HITS" \
        --arg misses "$CACHE_MISSES" \
        --arg rate "$hit_rate" \
        '{
            cache_hits: ($hits | tonumber),
            cache_misses: ($misses | tonumber),
            hit_rate_percent: ($rate | tonumber),
            total_requests: ($hits | tonumber) + ($misses | tonumber)
        }'
}

# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

export -f init_file_cache
export -f cleanup_file_cache
export -f cached_read
export -f invalidate_cache
export -f batch_read_add
export -f batch_read_execute
export -f batch_write_add
export -f batch_write_execute
export -f cached_jq
export -f batch_jq
export -f stream_jsonl
export -f append_jsonl
export -f file_changed
export -f get_mtime
export -f get_cache_stats

# Initialize on load
init_file_cache
