#!/usr/bin/env bash
# Cleanup Master - Core Scanner
# Detects dead code, unreferenced files, and structural issues

set -euo pipefail

# Get script directory and project root
LIB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PROJECT_ROOT:-}" ]]; then
    PROJECT_ROOT="$(cd "$LIB_SCRIPT_DIR/../../../.." && pwd)"
fi

# Config file path
CONFIG_FILE="${LIB_SCRIPT_DIR}/../config/cleanup-rules.json"

# ==============================================================================
# PROTECTED FILES HELPER
# ==============================================================================

# Load all protected files from config into a lookup file
load_protected_files() {
    local lookup_file="${1:-/tmp/protected-files-$$.txt}"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "Warning: Config file not found: $CONFIG_FILE" >&2
        touch "$lookup_file"
        echo "$lookup_file"
        return
    fi

    # Extract all protected file paths from all sections
    jq -r '
        [
            .protected_executables.scripts[]?,
            .protected_executables.cleanup_master[]?,
            .protected_executables.coordinator_master[]?,
            .protected_executables.security_master[]?,
            .protected_executables.other_masters[]?,
            .protected_core_modules.cortex_core[]?,
            .protected_core_modules.coordination[]?,
            .protected_core_modules.worker_pool[]?,
            .protected_core_modules.scheduler[]?,
            .protected_python_sdk.files[]?,
            .protected_analysis.files[]?
        ] | .[]
    ' "$CONFIG_FILE" 2>/dev/null | sort -u > "$lookup_file"

    echo "$lookup_file"
}

# Check if a file is protected
is_protected_file() {
    local file="$1"
    local lookup_file="$2"

    grep -qxF "$file" "$lookup_file" 2>/dev/null
}

# ==============================================================================
# DEAD CODE DETECTION
# ==============================================================================

find_unreferenced_files() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/unreferenced-files.json}"

    echo "Scanning for unreferenced files in $scan_dir..." >&2

    # Load protected files list
    local protected_files=$(load_protected_files "/tmp/protected-files-$$.txt")
    local protected_count=$(wc -l < "$protected_files" | tr -d ' ')
    echo "  Loaded $protected_count protected files from config" >&2

    # V2 Optimization: Use awk hash table instead of repeated greps
    # This reduces 46K greps × 10M lines to 1 pass through 10M lines

    echo "Step 1/3: Collecting file list..." >&2
    local temp_files="/tmp/file-list-$$.txt"
    find "$scan_dir" -type f \( -name "*.sh" -o -name "*.js" -o -name "*.py" \) 2>/dev/null | \
        grep -vE '(node_modules|\.git|\.venv|__pycache__)' > "$temp_files"

    local total=$(wc -l < "$temp_files" | tr -d ' ')
    echo "  Found $total files to check" >&2

    echo "Step 2/3: Streaming reference check (awk hash table)..." >&2

    # Use awk to build hash table and check in ONE pass
    local unreferenced_raw=$(awk '
        BEGIN {
            # Phase 1: Load all filenames into hash table
            while ((getline filepath < "'"$temp_files"'") > 0) {
                split(filepath, parts, "/")
                filename = parts[length(parts)]
                files[filename] = filepath
            }
            close("'"$temp_files"'")
        }

        # Phase 2: Stream through grep output, mark files as found
        {
            for (filename in files) {
                if (index($0, filename) > 0) {
                    delete files[filename]
                }
            }
        }

        END {
            # Phase 3: Print unreferenced files
            for (filename in files) {
                print files[filename]
            }
        }
    ' <(grep -rh --no-filename \
        --include="*.sh" \
        --include="*.js" \
        --include="*.py" \
        --include="*.json" \
        --exclude-dir=node_modules \
        --exclude-dir=.git \
        --exclude-dir=.venv \
        --exclude-dir=__pycache__ \
        "$PROJECT_ROOT" 2>/dev/null))

    echo "Step 3/3: Generating results..." >&2

    # Convert to relative paths and build array (excluding protected files)
    local unreferenced=()
    local skipped_protected=0
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"

        # Skip protected files
        if is_protected_file "$relative_path" "$protected_files"; then
            ((skipped_protected++))
            continue
        fi

        unreferenced+=("$relative_path")
    done <<< "$unreferenced_raw"

    echo "  Skipped $skipped_protected protected files" >&2

    # Cleanup
    rm -f "$temp_files" "$protected_files"

    echo "  Found ${#unreferenced[@]} unreferenced files" >&2

    # Generate JSON output
    jq -n \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --argjson files "$(printf '%s\n' "${unreferenced[@]}" | jq -R . | jq -s .)" \
        '{
            scan_type: "unreferenced_files",
            timestamp: $timestamp,
            count: ($files | length),
            files: $files
        }' > "$results_file"

    echo "${#unreferenced[@]}"
}

find_dead_functions() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/dead-functions.json}"

    echo "Scanning for dead functions in $scan_dir..." >&2

    local dead_functions=()

    # Find all function definitions in bash scripts
    while IFS= read -r line; do
        local file=$(echo "$line" | cut -d: -f1)
        local func_name=$(echo "$line" | sed -E 's/.*function\s+([a-zA-Z_][a-zA-Z0-9_]*).*/\1/' | sed -E 's/.*([a-zA-Z_][a-zA-Z0-9_]*)\(\).*/\1/')

        # Skip if empty
        [[ -z "$func_name" ]] && continue

        # Count references (excluding definition)
        local ref_count=$(grep -r "\b$func_name\b" "$PROJECT_ROOT" \
            --include="*.sh" \
            2>/dev/null | grep -v "^$file:" | grep -v "function $func_name" | wc -l | tr -d ' ')

        if [[ $ref_count -eq 0 ]]; then
            dead_functions+=("{\"file\": \"${file#$PROJECT_ROOT/}\", \"function\": \"$func_name\"}")
        fi
    done < <(grep -r "^[[:space:]]*\(function[[:space:]]\+\)\?[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*()[[:space:]]*{" "$scan_dir" \
        --include="*.sh" 2>/dev/null || true)

    # Generate JSON output
    if [[ ${#dead_functions[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${dead_functions[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "dead_functions",
                timestamp: $timestamp,
                count: (. | length),
                functions: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "dead_functions",
                timestamp: $timestamp,
                count: 0,
                functions: []
            }' > "$results_file"
    fi

    echo "${#dead_functions[@]}"
}

find_empty_directories() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/empty-directories.json}"

    echo "Scanning for empty directories in $scan_dir..." >&2

    local empty_dirs=()

    while IFS= read -r dir; do
        local relative_path="${dir#$PROJECT_ROOT/}"

        # Skip excluded patterns
        if echo "$relative_path" | grep -qE '(node_modules|\.git|\.venv|__pycache__)'; then
            continue
        fi

        # Check if truly empty (no files, only .gitkeep allowed)
        local file_count=$(find "$dir" -type f ! -name ".gitkeep" | wc -l | tr -d ' ')

        if [[ $file_count -eq 0 ]]; then
            empty_dirs+=("$relative_path")
        fi
    done < <(find "$scan_dir" -type d -empty 2>/dev/null || find "$scan_dir" -type d 2>/dev/null | while read d; do [[ $(find "$d" -maxdepth 1 -type f ! -name ".gitkeep" | wc -l) -eq 0 ]] && echo "$d"; done)

    # Generate JSON output
    jq -n \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --argjson dirs "$(printf '%s\n' "${empty_dirs[@]}" | jq -R . | jq -s .)" \
        '{
            scan_type: "empty_directories",
            timestamp: $timestamp,
            count: ($dirs | length),
            directories: $dirs
        }' > "$results_file"

    echo "${#empty_dirs[@]}"
}

# ==============================================================================
# FILE PERMISSION VALIDATION
# ==============================================================================

check_file_permissions() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/permission-issues.json}"

    echo "Checking file permissions in $scan_dir..." >&2

    local issues=()

    # Scripts should be executable
    while IFS= read -r file; do
        if [[ ! -x "$file" ]]; then
            local relative_path="${file#$PROJECT_ROOT/}"
            issues+=("{\"file\": \"$relative_path\", \"issue\": \"not_executable\", \"expected\": \"755\"}")
        fi
    done < <(find "$scan_dir" -type f -name "*.sh" 2>/dev/null)

    # Config files should NOT be executable
    while IFS= read -r file; do
        if [[ -x "$file" ]]; then
            local relative_path="${file#$PROJECT_ROOT/}"
            issues+=("{\"file\": \"$relative_path\", \"issue\": \"should_not_be_executable\", \"expected\": \"644\"}")
        fi
    done < <(find "$scan_dir" -type f \( -name "*.json" -o -name "*.md" -o -name "*.txt" \) 2>/dev/null)

    # Generate JSON output
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${issues[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "permission_issues",
                timestamp: $timestamp,
                count: (. | length),
                issues: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "permission_issues",
                timestamp: $timestamp,
                count: 0,
                issues: []
            }' > "$results_file"
    fi

    echo "${#issues[@]}"
}

# ==============================================================================
# DUPLICATE FILE DETECTION
# ==============================================================================

scan_for_duplicates() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/duplicate-files.json}"
    local max_files="${3:-20000}"  # Safety limit

    echo "Scanning for duplicate files in $scan_dir..." >&2

    # Quick file count check
    local file_count=$(find "$scan_dir" -type f \( -name "*.sh" -o -name "*.js" -o -name "*.py" -o -name "*.json" \) 2>/dev/null | wc -l | tr -d ' ')

    if [[ $file_count -gt $max_files ]]; then
        echo "  WARNING: $file_count files exceeds limit of $max_files" >&2
        echo "  Skipping duplicate scan (would take too long)" >&2

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

    echo "Step 1/3: Grouping $file_count files by size..." >&2

    local duplicates=()

    # Step 1: Group files by size (duplicates must have same size)
    # Bash 3.x compatible: Use temp file instead of associative array
    local size_groups_file="/tmp/size-groups-$$.txt"
    > "$size_groups_file"  # Create/clear file
    local total=0
    local processed=0

    while IFS= read -r file; do
        local relative_path="${file#$PROJECT_ROOT/}"

        # Skip excluded patterns
        if echo "$relative_path" | grep -qE '(node_modules|\.git|\.venv|__pycache__)'; then
            continue
        fi

        local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
        echo "$size|$file" >> "$size_groups_file"
        ((total++))
        ((processed++))

        # Progress indicator
        if (( processed % 1000 == 0 )); then
            echo "  Grouped $processed files..." >&2
        fi
    done < <(find "$scan_dir" -type f \( -name "*.sh" -o -name "*.js" -o -name "*.py" -o -name "*.json" \) 2>/dev/null)

    echo "Step 2/3: Identifying size groups with multiple files..." >&2

    # Step 2: Only hash files that have potential duplicates (same size)
    # Find sizes that appear more than once
    local candidate_sizes_file="/tmp/candidate-sizes-$$.txt"
    awk -F'|' '{count[$1]++; if(count[$1]==2) print $1}' "$size_groups_file" | sort -u > "$candidate_sizes_file"
    local candidates=$(awk -F'|' 'NR==FNR{sizes[$1]=1; next} $1 in sizes' "$candidate_sizes_file" "$size_groups_file" | wc -l | tr -d ' ')

    echo "Step 3/3: Computing hashes for $candidates/$total candidate files..." >&2

    # Step 3: Hash only the candidate files
    # Bash 3.x compatible: Use temp file instead of associative array
    local file_hashes_file="/tmp/file-hashes-$$.txt"
    > "$file_hashes_file"  # Create/clear file
    local hashed=0

    # Process each candidate size group
    while IFS= read -r size; do
        [[ -z "$size" ]] && continue

        # Get all files with this size
        local files_with_size=$(grep "^$size|" "$size_groups_file" | cut -d'|' -f2-)

        while IFS= read -r file; do
            [[ -z "$file" ]] && continue

            local relative_path="${file#$PROJECT_ROOT/}"
            local hash=$(md5sum "$file" 2>/dev/null | cut -d' ' -f1 || md5 -q "$file" 2>/dev/null)

            # Check if hash already exists in our tracking file
            local existing_file=$(grep "^$hash|" "$file_hashes_file" | cut -d'|' -f2- | head -1)

            if [[ -n "$existing_file" ]]; then
                duplicates+=("{\"hash\": \"$hash\", \"original\": \"$existing_file\", \"duplicate\": \"$relative_path\"}")
            else
                echo "$hash|$relative_path" >> "$file_hashes_file"
            fi

            ((hashed++))
            if (( hashed % 50 == 0 )); then
                echo "  Hashed $hashed/$candidates files..." >&2
            fi
        done <<< "$files_with_size"
    done < "$candidate_sizes_file"

    # Cleanup temp files
    rm -f "$size_groups_file" "$candidate_sizes_file" "$file_hashes_file"

    # Generate JSON output
    if [[ ${#duplicates[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${duplicates[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "duplicate_files",
                timestamp: $timestamp,
                count: (. | length),
                duplicates: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "duplicate_files",
                timestamp: $timestamp,
                count: 0,
                duplicates: []
            }' > "$results_file"
    fi

    echo "${#duplicates[@]}"
}

# ==============================================================================
# JUNK FILE DETECTION (Malformed command artifacts)
# ==============================================================================

find_junk_files() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/junk-files.json}"

    echo "Scanning for junk files (malformed command artifacts) in $scan_dir..." >&2

    local junk_files=()

    # Pattern 1: Files with shell metacharacters in names (|, >, <, &, ;, $, `)
    # These are almost always artifacts from broken shell commands
    echo "  Checking for shell metacharacter filenames..." >&2
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$PROJECT_ROOT/}"

        # Skip excluded directories
        if echo "$relative_path" | grep -qE '(node_modules|\.git|\.venv|__pycache__)'; then
            continue
        fi

        local filename=$(basename "$file")
        local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")

        junk_files+=("{\"file\": \"$relative_path\", \"reason\": \"shell_metacharacter_in_filename\", \"size\": $size}")
    done < <(find "$scan_dir" -maxdepth 3 -type f \( -name '*|*' -o -name '*>*' -o -name '*<*' -o -name '*&*' -o -name '*;*' -o -name '*\`*' \) 2>/dev/null)

    # Pattern 2: Very small files (< 50 bytes) in project root with no extension
    # that look like partial command fragments
    echo "  Checking for small fragment files in root..." >&2
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        local filename=$(basename "$file")
        local relative_path="${file#$PROJECT_ROOT/}"

        # Skip hidden files and known files
        [[ "$filename" == .* ]] && continue
        [[ "$filename" == "LICENSE" ]] && continue
        [[ "$filename" == "Makefile" ]] && continue

        # Check if file has no extension (likely junk)
        if [[ "$filename" != *.* ]]; then
            local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")

            # Only flag very small files (likely fragments)
            if [[ $size -lt 50 ]]; then
                junk_files+=("{\"file\": \"$relative_path\", \"reason\": \"small_fragment_no_extension\", \"size\": $size}")
            fi
        fi
    done < <(find "$scan_dir" -maxdepth 1 -type f 2>/dev/null)

    # Pattern 3: Files that look like partial words from common commands
    # e.g., "orld" from "Hello World", "ello" from "echo Hello"
    echo "  Checking for partial word fragments..." >&2
    local partial_patterns=("orld" "ello" "rint" "xport" "unction" "equire" "mport")
    for pattern in "${partial_patterns[@]}"; do
        while IFS= read -r file; do
            [[ -z "$file" ]] && continue
            local filename=$(basename "$file")
            local relative_path="${file#$PROJECT_ROOT/}"

            # Skip if in excluded directories
            if echo "$relative_path" | grep -qE '(node_modules|\.git|\.venv|__pycache__)'; then
                continue
            fi

            # Only flag if file is very small
            local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
            if [[ $size -lt 100 ]]; then
                junk_files+=("{\"file\": \"$relative_path\", \"reason\": \"partial_word_fragment\", \"pattern\": \"$pattern\", \"size\": $size}")
            fi
        done < <(find "$scan_dir" -maxdepth 2 -type f -name "*$pattern*" 2>/dev/null | grep -v '\.')
    done

    echo "  Found ${#junk_files[@]} junk files" >&2

    # Generate JSON output
    if [[ ${#junk_files[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${junk_files[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "junk_files",
                timestamp: $timestamp,
                count: (. | length),
                files: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "junk_files",
                timestamp: $timestamp,
                count: 0,
                files: []
            }' > "$results_file"
    fi

    echo "${#junk_files[@]}"
}

# ==============================================================================
# ANALYSIS ARTIFACTS SCANNER
# ==============================================================================

# Find analysis artifacts and cache directories that can be safely removed
# Detects: __marimo__, __pycache__, .pytest_cache, .mypy_cache, *.egg-info,
#          .ipynb_checkpoints, temp files, backup files, editor swap files
find_analysis_artifacts() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/analysis-artifacts.json}"

    echo "Scanning for analysis artifacts and cache directories in $scan_dir..." >&2

    local artifacts=()

    # Pattern 1: Python and notebook cache directories
    echo "  Checking for cache directories..." >&2
    local cache_patterns="__marimo__ __pycache__ .pytest_cache .mypy_cache .ipynb_checkpoints .coverage .nox .tox"
    for pattern in $cache_patterns; do
        while IFS= read -r dir; do
            [[ -z "$dir" ]] && continue
            local relative_path="${dir#$scan_dir/}"

            # Skip if inside node_modules or .git
            if echo "$relative_path" | grep -qE '(node_modules|\.git)/'; then
                continue
            fi

            # Get directory size
            local size=$(du -sk "$dir" 2>/dev/null | cut -f1)
            size=${size:-0}

            artifacts+=("{\"path\": \"$relative_path\", \"type\": \"cache_directory\", \"pattern\": \"$pattern\", \"size_kb\": $size}")
        done < <(find "$scan_dir" -type d -name "$pattern" 2>/dev/null)
    done

    # Pattern 2: Egg-info directories (Python packages)
    echo "  Checking for egg-info directories..." >&2
    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        local relative_path="${dir#$scan_dir/}"

        # Skip if inside node_modules, .git, or .venv
        if echo "$relative_path" | grep -qE '(node_modules|\.git|\.venv)/'; then
            continue
        fi

        local size=$(du -sk "$dir" 2>/dev/null | cut -f1)
        size=${size:-0}

        artifacts+=("{\"path\": \"$relative_path\", \"type\": \"egg_info\", \"size_kb\": $size}")
    done < <(find "$scan_dir" -type d -name "*.egg-info" 2>/dev/null)

    # Pattern 3: Temporary and backup files
    echo "  Checking for temp/backup files..." >&2
    local temp_patterns="*.tmp *.bak *.orig *.swp *~ *.pyc *.pyo"
    for pattern in $temp_patterns; do
        while IFS= read -r file; do
            [[ -z "$file" ]] && continue
            local relative_path="${file#$scan_dir/}"

            # Skip excluded directories
            if echo "$relative_path" | grep -qE '(node_modules|\.git|\.venv)/'; then
                continue
            fi

            local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")

            artifacts+=("{\"path\": \"$relative_path\", \"type\": \"temp_file\", \"pattern\": \"$pattern\", \"size\": $size}")
        done < <(find "$scan_dir" -type f -name "$pattern" 2>/dev/null)
    done

    # Pattern 4: Log files in analysis directories
    echo "  Checking for log files in analysis directories..." >&2
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        local relative_path="${file#$scan_dir/}"

        # Only consider logs in analysis directory
        if ! echo "$relative_path" | grep -q "^analysis/"; then
            continue
        fi

        local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")

        artifacts+=("{\"path\": \"$relative_path\", \"type\": \"analysis_log\", \"size\": $size}")
    done < <(find "$scan_dir/analysis" -type f -name "*.log" 2>/dev/null)

    # Generate JSON output
    local count=${#artifacts[@]}

    if [[ $count -gt 0 ]]; then
        local json_array=$(printf '%s\n' "${artifacts[@]}" | paste -sd ',' -)
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --argjson count "$count" \
            --argjson artifacts "[$json_array]" \
            '{
                scan_type: "analysis_artifacts",
                timestamp: $timestamp,
                count: $count,
                artifacts: $artifacts
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "analysis_artifacts",
                timestamp: $timestamp,
                count: 0,
                artifacts: []
            }' > "$results_file"
    fi

    echo "$count"
}

# ==============================================================================
# MAIN SCAN
# ==============================================================================

run_full_scan() {
    local output_dir="${1:-coordination/masters/cleanup/scans}"

    mkdir -p "$output_dir"

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local scan_id="scan-$timestamp"
    local scan_dir="$output_dir/$scan_id"

    mkdir -p "$scan_dir"

    echo "=== Cleanup Master - Full Scan ===" >&2
    echo "Scan ID: $scan_id" >&2
    echo "" >&2

    # Run all scans
    local unreferenced=$(find_unreferenced_files "$PROJECT_ROOT" "$scan_dir/unreferenced-files.json")
    local dead_funcs=$(find_dead_functions "$PROJECT_ROOT" "$scan_dir/dead-functions.json")
    local empty_dirs=$(find_empty_directories "$PROJECT_ROOT" "$scan_dir/empty-directories.json")
    local perm_issues=$(check_file_permissions "$PROJECT_ROOT" "$scan_dir/permission-issues.json")
    local duplicates=$(scan_for_duplicates "$PROJECT_ROOT" "$scan_dir/duplicate-files.json")
    local junk=$(find_junk_files "$PROJECT_ROOT" "$scan_dir/junk-files.json")
    local artifacts=$(find_analysis_artifacts "$PROJECT_ROOT" "$scan_dir/analysis-artifacts.json")

    # Generate summary
    jq -n \
        --arg scan_id "$scan_id" \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --argjson unreferenced "$unreferenced" \
        --argjson dead_funcs "$dead_funcs" \
        --argjson empty_dirs "$empty_dirs" \
        --argjson perm_issues "$perm_issues" \
        --argjson duplicates "$duplicates" \
        --argjson junk "$junk" \
        --argjson artifacts "$artifacts" \
        '{
            scan_id: $scan_id,
            timestamp: $timestamp,
            summary: {
                unreferenced_files: $unreferenced,
                dead_functions: $dead_funcs,
                empty_directories: $empty_dirs,
                permission_issues: $perm_issues,
                duplicate_files: $duplicates,
                junk_files: $junk,
                analysis_artifacts: $artifacts,
                total_issues: ($unreferenced + $dead_funcs + $empty_dirs + $perm_issues + $duplicates + $junk + $artifacts)
            },
            scan_directory: "'"$scan_dir"'"
        }' > "$scan_dir/summary.json"

    echo "" >&2
    echo "=== Scan Complete ===" >&2
    echo "Results: $scan_dir" >&2
    cat "$scan_dir/summary.json" | jq '.summary' >&2

    echo "$scan_dir"
}

# ==============================================================================
# EXPORTS
# ==============================================================================

export -f load_protected_files
export -f is_protected_file
export -f find_unreferenced_files
export -f find_dead_functions
export -f find_empty_directories
export -f check_file_permissions
export -f scan_for_duplicates
export -f find_junk_files
export -f find_analysis_artifacts
export -f run_full_scan
