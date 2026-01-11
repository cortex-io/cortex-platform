#!/usr/bin/env bash
# Cleanup Master - Pattern Analyzer
# Detects legacy patterns, broken references, and anti-patterns

set -euo pipefail

# Get project root
if [[ -z "${PROJECT_ROOT:-}" ]]; then
    LIB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$LIB_SCRIPT_DIR/../../../.." && pwd)"
fi

# ==============================================================================
# BROKEN REFERENCE DETECTION
# ==============================================================================

find_broken_references() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/broken-references.json}"

    echo "Scanning for broken references in $scan_dir..." >&2

    local broken=()
    local checked=0

    # Find source/require statements
    echo "Checking source statements..." >&2
    while IFS= read -r line; do
        ((checked++))

        local file=$(echo "$line" | cut -d: -f1)
        local referenced=$(echo "$line" | sed -E 's/.*source[[:space:]]+([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")

        # Skip if empty or variable reference
        [[ -z "$referenced" || "$referenced" =~ \$ ]] && continue

        # Convert to absolute path
        local abs_path
        if [[ "$referenced" =~ ^/ ]]; then
            abs_path="$referenced"
        else
            abs_path="$(dirname "$file")/$referenced"
        fi

        # Normalize path (with error handling)
        abs_path=$(realpath "$abs_path" 2>/dev/null || echo "$abs_path")

        # Check if exists
        if [[ ! -f "$abs_path" ]]; then
            local relative_file="${file#$PROJECT_ROOT/}"
            broken+=("{\"file\": \"$relative_file\", \"missing_reference\": \"$referenced\", \"type\": \"source\"}")
        fi
    done < <(grep -r "^[[:space:]]*source[[:space:]]" "$scan_dir" --include="*.sh" 2>/dev/null || true)

    echo "Checked $checked source statements" >&2

    # Find script executions
    echo "Checking script executions..." >&2
    local exec_checked=0
    while IFS= read -r line; do
        ((exec_checked++))

        local file=$(echo "$line" | cut -d: -f1)
        local script=$(echo "$line" | sed -E 's/.*\.\/([^[:space:]]+).*/\1/')

        # Skip if variable or common commands
        [[ -z "$script" || "$script" =~ \$ || "$script" =~ ^(ls|cd|mkdir|rm|cp|mv|echo) ]] && continue

        local script_path="$(dirname "$file")/$script"

        if [[ ! -f "$script_path" && ! -f "$PROJECT_ROOT/$script" ]]; then
            local relative_file="${file#$PROJECT_ROOT/}"
            broken+=("{\"file\": \"$relative_file\", \"missing_reference\": \"$script\", \"type\": \"script\"}")
        fi
    done < <(grep -r "\./[a-zA-Z0-9_/-]\+\.sh" "$scan_dir" --include="*.sh" 2>/dev/null || true)

    echo "Checked $exec_checked script executions" >&2

    # Generate JSON output with error handling
    echo "Generating JSON output..." >&2

    if [[ ${#broken[@]} -gt 0 ]]; then
        # Build JSON array manually to avoid pipe failures
        local json_array="[$(IFS=,; echo "${broken[*]}")]"
        echo "$json_array" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "broken_references",
                timestamp: $timestamp,
                count: (. | length),
                references: .
            }' > "$results_file" 2>&1 || {
                echo "Error: jq failed, writing basic JSON" >&2
                echo "{\"scan_type\":\"broken_references\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"count\":${#broken[@]},\"error\":\"jq_failed\"}" > "$results_file"
            }
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "broken_references",
                timestamp: $timestamp,
                count: 0,
                references: []
            }' > "$results_file" 2>&1 || {
                echo "Error: jq failed, writing basic JSON" >&2
                echo "{\"scan_type\":\"broken_references\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"count\":0,\"references\":[]}" > "$results_file"
            }
    fi

    echo "Found ${#broken[@]} broken references" >&2
    echo "${#broken[@]}"
}

# ==============================================================================
# LEGACY PATTERN DETECTION
# ==============================================================================

find_legacy_api_calls() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/legacy-api-calls.json}"

    echo "Scanning for legacy API calls in $scan_dir..." >&2

    local legacy_patterns=(
        "localhost:3000"
        "localhost:8080"
        "localhost:9000"
        "http://localhost"
        "api/achievements"
        "api/dashboard"
        "api/metrics"
        "api/health"
    )

    local findings=()

    for pattern in "${legacy_patterns[@]}"; do
        while IFS= read -r line; do
            local file=$(echo "$line" | cut -d: -f1)
            local line_num=$(echo "$line" | cut -d: -f2)
            local content=$(echo "$line" | cut -d: -f3-)
            local relative_file="${file#$PROJECT_ROOT/}"

            findings+=("{\"file\": \"$relative_file\", \"line\": $line_num, \"pattern\": \"$pattern\", \"content\": $(echo "$content" | jq -R .)}")
        done < <(grep -rn "$pattern" "$scan_dir" \
            --include="*.sh" \
            --include="*.js" \
            --include="*.py" \
            2>/dev/null || true)
    done

    # Generate JSON output
    if [[ ${#findings[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${findings[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "legacy_api_calls",
                timestamp: $timestamp,
                count: (. | length),
                findings: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "legacy_api_calls",
                timestamp: $timestamp,
                count: 0,
                findings: []
            }' > "$results_file"
    fi

    echo "${#findings[@]}"
}

find_legacy_patterns() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/legacy-patterns.json}"

    echo "Scanning for legacy code patterns in $scan_dir..." >&2

    local patterns=(
        "commit-relay:File references old project name"
        "api-server:References removed API server"
        "dashboard-events:References old dashboard events"
        "worker-pool.json:References old worker pool system"
        "TODO.*remove:TODO comments about removal"
        "DEPRECATED:Deprecated code markers"
    )

    local findings=()

    for pattern_def in "${patterns[@]}"; do
        local pattern=$(echo "$pattern_def" | cut -d: -f1)
        local description=$(echo "$pattern_def" | cut -d: -f2-)

        while IFS= read -r line; do
            local file=$(echo "$line" | cut -d: -f1)
            local line_num=$(echo "$line" | cut -d: -f2)
            local relative_file="${file#$PROJECT_ROOT/}"

            findings+=("{\"file\": \"$relative_file\", \"line\": $line_num, \"pattern\": \"$pattern\", \"description\": \"$description\"}")
        done < <(grep -rn "$pattern" "$scan_dir" \
            --include="*.sh" \
            --include="*.js" \
            --include="*.py" \
            --include="*.md" \
            2>/dev/null || true)
    done

    # Generate JSON output
    if [[ ${#findings[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${findings[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "legacy_patterns",
                timestamp: $timestamp,
                count: (. | length),
                findings: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "legacy_patterns",
                timestamp: $timestamp,
                count: 0,
                findings: []
            }' > "$results_file"
    fi

    echo "${#findings[@]}"
}

# ==============================================================================
# GITIGNORE CONSISTENCY
# ==============================================================================

check_gitignore_consistency() {
    local scan_dir="${1:-$PROJECT_ROOT}"
    local results_file="${2:-/tmp/gitignore-issues.json}"

    echo "Checking .gitignore consistency in $scan_dir..." >&2

    local issues=()

    # Files that should be ignored but are tracked
    local should_ignore=(
        "*.log"
        "*.tmp"
        ".env"
        ".env.local"
        "node_modules"
        "__pycache__"
        "*.pyc"
    )

    for pattern in "${should_ignore[@]}"; do
        while IFS= read -r file; do
            # Check if tracked by git
            if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
                local relative_file="${file#$PROJECT_ROOT/}"
                issues+=("{\"file\": \"$relative_file\", \"issue\": \"tracked_but_should_ignore\", \"pattern\": \"$pattern\"}")
            fi
        done < <(find "$scan_dir" -name "$pattern" -type f 2>/dev/null || true)
    done

    # Check for files ignored but not in .gitignore
    if [[ -f "$PROJECT_ROOT/.gitignore" ]]; then
        while IFS= read -r ignored_file; do
            if [[ ! -f "$ignored_file" ]]; then
                continue
            fi

            # Check if pattern exists in .gitignore
            local basename=$(basename "$ignored_file")
            local pattern_found=false

            while IFS= read -r gitignore_pattern; do
                [[ -z "$gitignore_pattern" || "$gitignore_pattern" =~ ^# ]] && continue

                if [[ "$basename" == $gitignore_pattern || "$ignored_file" == *"$gitignore_pattern"* ]]; then
                    pattern_found=true
                    break
                fi
            done < "$PROJECT_ROOT/.gitignore"

            if [[ "$pattern_found" == "false" ]]; then
                local relative_file="${ignored_file#$PROJECT_ROOT/}"
                issues+=("{\"file\": \"$relative_file\", \"issue\": \"ignored_but_not_in_gitignore\"}")
            fi
        done < <(git ls-files --others --ignored --exclude-standard 2>/dev/null || true)
    fi

    # Generate JSON output
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "[$(IFS=,; echo "${issues[*]}")]" | jq \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "gitignore_issues",
                timestamp: $timestamp,
                count: (. | length),
                issues: .
            }' > "$results_file"
    else
        jq -n \
            --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                scan_type: "gitignore_issues",
                timestamp: $timestamp,
                count: 0,
                issues: []
            }' > "$results_file"
    fi

    echo "${#issues[@]}"
}

# ==============================================================================
# MAIN ANALYSIS
# ==============================================================================

run_full_analysis() {
    local output_dir="${1:-coordination/masters/cleanup/scans}"

    local latest_scan=$(ls -t "$output_dir" | grep "^scan-" | head -1)

    if [[ -z "$latest_scan" ]]; then
        echo "Error: No scan found. Run scanner first." >&2
        return 1
    fi

    local scan_dir="$output_dir/$latest_scan"

    echo "=== Cleanup Master - Pattern Analysis ===" >&2
    echo "Analyzing scan: $latest_scan" >&2
    echo "" >&2

    # Run all analyses
    local broken_refs=$(find_broken_references "$PROJECT_ROOT" "$scan_dir/broken-references.json")
    local legacy_apis=$(find_legacy_api_calls "$PROJECT_ROOT" "$scan_dir/legacy-api-calls.json")
    local legacy_patterns=$(find_legacy_patterns "$PROJECT_ROOT" "$scan_dir/legacy-patterns.json")
    local gitignore_issues=$(check_gitignore_consistency "$PROJECT_ROOT" "$scan_dir/gitignore-issues.json")

    # Update summary
    jq \
        --argjson broken_refs "$broken_refs" \
        --argjson legacy_apis "$legacy_apis" \
        --argjson legacy_patterns "$legacy_patterns" \
        --argjson gitignore_issues "$gitignore_issues" \
        '.summary += {
            broken_references: $broken_refs,
            legacy_api_calls: $legacy_apis,
            legacy_patterns: $legacy_patterns,
            gitignore_issues: $gitignore_issues
        } | .summary.total_issues += ($broken_refs + $legacy_apis + $legacy_patterns + $gitignore_issues)' \
        "$scan_dir/summary.json" > "$scan_dir/summary.json.tmp"

    mv "$scan_dir/summary.json.tmp" "$scan_dir/summary.json"

    echo "" >&2
    echo "=== Analysis Complete ===" >&2
    cat "$scan_dir/summary.json" | jq '.summary' >&2

    echo "$scan_dir"
}

# ==============================================================================
# EXPORTS
# ==============================================================================

export -f find_broken_references
export -f find_legacy_api_calls
export -f find_legacy_patterns
export -f check_gitignore_consistency
export -f run_full_analysis
