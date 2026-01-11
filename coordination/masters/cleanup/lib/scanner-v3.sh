#!/usr/bin/env bash
# Cleanup Master - Scanner V3 (Cache-Aware)
# Uses SQLite cache for instant lookups

set -euo pipefail

# Get project root
if [[ -z "${PROJECT_ROOT:-}" ]]; then
    LIB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$LIB_SCRIPT_DIR/../../../.." && pwd)"
fi

CACHE_DIR="$PROJECT_ROOT/coordination/masters/cleanup/cache"
CACHE_MANAGER="$CACHE_DIR/cache-manager.sh"

# ==============================================================================
# CACHE-AWARE UNREFERENCED FILES SCAN
# ==============================================================================

find_unreferenced_files_v3() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/unreferenced-files.json}"

    echo "Scanning for unreferenced files (V3 - cache-aware)..." >&2

    # Ensure cache is ready
    if [[ ! -x "$CACHE_MANAGER" ]]; then
        echo "  ERROR: Cache manager not found, falling back to V2..." >&2
        # Fall back to V2 if cache not available
        source "$PROJECT_ROOT/coordination/masters/cleanup/lib/scanner.sh"
        find_unreferenced_files "$scan_dir" "$results_file"
        return
    fi

    echo "Step 1/3: Checking cache status..." >&2
    source "$CACHE_MANAGER"

    local cache_status=$(cache_status)
    if [[ "$cache_status" != "fresh" ]]; then
        echo "  Cache is $cache_status, ensuring..." >&2
        ensure_cache
    else
        echo "  Cache is fresh!" >&2
    fi

    echo "Step 2/3: Collecting files to check..." >&2
    local temp_files="/tmp/file-list-v3-$$.txt"
    find "$scan_dir" -type f \( -name "*.sh" -o -name "*.js" -o -name "*.py" \) 2>/dev/null | \
        grep -vE '(node_modules|\.git|\.venv|__pycache__|archives)' > "$temp_files"

    local total=$(wc -l < "$temp_files" | tr -d ' ')
    echo "  Found $total files to check" >&2

    echo "Step 3/3: Querying cache for unreferenced files..." >&2

    local unreferenced_temp="/tmp/unreferenced-v3-$$.txt"
    : > "$unreferenced_temp"  # Clear temp file

    local checked=0
    local unreferenced_count=0

    CACHE_DB="$CACHE_DIR/file-reference-cache.db"

    while IFS= read -r filepath; do
        ((checked++))

        local filename=$(basename "$filepath")
        local relative_path="${filepath#$PROJECT_ROOT/}"

        # Query cache (instant SQLite lookup!)
        local is_referenced=$(sqlite3 "$CACHE_DB" \
            "SELECT is_referenced FROM file_references WHERE filename = '$filename';" 2>/dev/null || echo "0")

        if [[ "$is_referenced" != "1" ]]; then
            echo "$relative_path" >> "$unreferenced_temp"
            ((unreferenced_count++))
        fi

        # Progress indicator
        if (( checked % 1000 == 0 )); then
            echo "  Checked $checked/$total files..." >&2
        fi

    done < "$temp_files"

    rm -f "$temp_files"

    echo "  Found $unreferenced_count unreferenced files (checked $checked)" >&2

    # Generate JSON output by streaming from temp file
    {
        echo '{'
        echo "  \"scan_type\": \"unreferenced_files\","
        echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
        echo "  \"count\": $unreferenced_count,"
        echo "  \"method\": \"v3-cache\","
        echo '  "files": ['

        # Stream files array
        first=true
        while IFS= read -r file; do
            if [[ "$first" == "true" ]]; then
                first=false
            else
                echo ","
            fi
            jq -Rn --arg f "$file" '$f' | tr -d '\n'
        done < "$unreferenced_temp"

        echo ''
        echo '  ]'
        echo '}'
    } > "$results_file"

    rm -f "$unreferenced_temp"

    echo "$unreferenced_count"
}

# ==============================================================================
# CACHE-AWARE DUPLICATE FILES SCAN
# ==============================================================================

scan_for_duplicates_v3() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/duplicate-files.json}"
    local max_files="${3:-20000}"

    echo "Scanning for duplicate files (V3 - cache-aware)..." >&2

    # Check cache for file list
    if [[ ! -x "$CACHE_MANAGER" ]]; then
        echo "  ERROR: Cache manager not found, falling back to V2..." >&2
        source "$PROJECT_ROOT/coordination/masters/cleanup/lib/scanner.sh"
        scan_for_duplicates "$scan_dir" "$results_file" "$max_files"
        return
    fi

    source "$CACHE_MANAGER"
    ensure_cache

    CACHE_DB="$CACHE_DIR/file-reference-cache.db"

    # Get file count from cache
    local file_count=$(sqlite3 "$CACHE_DB" "SELECT COUNT(*) FROM files;" 2>/dev/null || echo "0")

    if [[ $file_count -gt $max_files ]]; then
        echo "  WARNING: $file_count files exceeds limit of $max_files" >&2
        echo "  Skipping duplicate scan" >&2

        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg reason "File count ($file_count) exceeds limit ($max_files)" \
            '{
                scan_type: "duplicate_files",
                timestamp: $timestamp,
                count: 0,
                duplicates: [],
                skipped: true,
                reason: $reason
            }' > "$results_file"

        echo "0"
        return 0
    fi

    echo "  Processing $file_count files from cache..." >&2

    # Use cache to group files by size
    local duplicates=()
    declare -A size_groups

    # Query files grouped by size
    while IFS='|' read -r size_bytes filepath; do
        size_groups[$size_bytes]="${size_groups[$size_bytes]:-}$filepath"$'\n'
    done < <(sqlite3 "$CACHE_DB" \
        "SELECT size_bytes, filepath FROM files WHERE size_bytes > 0 ORDER BY size_bytes;" 2>/dev/null)

    # Find duplicates within size groups
    local candidates=0
    for size in "${!size_groups[@]}"; do
        local file_list="${size_groups[$size]}"
        local count=$(echo "$file_list" | grep -c '^' || echo 0)

        if [[ $count -gt 1 ]]; then
            ((candidates += count))
        fi
    done

    echo "  Found $candidates candidate files to hash..." >&2

    # Hash candidates (same as V2)
    declare -A file_hashes
    local hashed=0

    for size in "${!size_groups[@]}"; do
        local file_list="${size_groups[$size]}"
        local count=$(echo "$file_list" | grep -c '^' || echo 0)

        if [[ $count -gt 1 ]]; then
            while IFS= read -r relative_path; do
                [[ -z "$relative_path" ]] && continue

                local full_path="$PROJECT_ROOT/$relative_path"
                [[ ! -f "$full_path" ]] && continue

                local hash=$(md5sum "$full_path" 2>/dev/null | cut -d' ' -f1 || md5 -q "$full_path" 2>/dev/null)

                if [[ -n "${file_hashes[$hash]:-}" ]]; then
                    duplicates+=("{\"hash\": \"$hash\", \"original\": \"${file_hashes[$hash]}\", \"duplicate\": \"$relative_path\"}")
                else
                    file_hashes[$hash]="$relative_path"
                fi

                ((hashed++))
                if (( hashed % 50 == 0 )); then
                    echo "  Hashed $hashed/$candidates files..." >&2
                fi
            done <<< "$file_list"
        fi
    done

    # Generate JSON output
    if [[ ${#duplicates[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${duplicates[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg method "v3-cache" \
            '{
                scan_type: "duplicate_files",
                timestamp: $timestamp,
                count: (. | length),
                duplicates: .,
                method: $method
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg method "v3-cache" \
            '{
                scan_type: "duplicate_files",
                timestamp: $timestamp,
                count: 0,
                duplicates: [],
                method: $method
            }' > "$results_file"
    fi

    echo "${#duplicates[@]}"
}

# ==============================================================================
# EXPORTS
# ==============================================================================

export -f find_unreferenced_files_v3
export -f scan_for_duplicates_v3
