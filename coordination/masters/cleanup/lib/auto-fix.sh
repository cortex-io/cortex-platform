#!/usr/bin/env bash
# Cleanup Master - Auto-Fix
# Safely fixes common issues automatically

set -euo pipefail

# Get project root
if [[ -z "${PROJECT_ROOT:-}" ]]; then
    LIB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$LIB_SCRIPT_DIR/../../../.." && pwd)"
fi

# Load configuration
CONFIG_FILE="$PROJECT_ROOT/coordination/masters/cleanup/config/cleanup-rules.json"

# ==============================================================================
# SAFE AUTO-FIXES
# ==============================================================================

remove_empty_directories() {
    local scan_file="$1"
    local dry_run="${2:-true}"

    echo "Removing empty directories..." >&2

    local removed=0

    while IFS= read -r dir; do
        local full_path="$PROJECT_ROOT/$dir"

        if [[ -d "$full_path" ]]; then
            if [[ "$dry_run" == "false" ]]; then
                rmdir "$full_path" 2>/dev/null && {
                    echo "  Removed: $dir" >&2
                    ((removed++))
                } || echo "  Failed to remove: $dir" >&2
            else
                echo "  Would remove: $dir" >&2
                ((removed++))
            fi
        fi
    done < <(jq -r '.directories[]' "$scan_file" 2>/dev/null || echo "")

    echo "$removed"
}

fix_file_permissions() {
    local scan_file="$1"
    local dry_run="${2:-true}"

    echo "Fixing file permissions..." >&2

    local fixed=0

    while IFS= read -r issue; do
        local file=$(echo "$issue" | jq -r '.file')
        local issue_type=$(echo "$issue" | jq -r '.issue')
        local full_path="$PROJECT_ROOT/$file"

        if [[ ! -f "$full_path" ]]; then
            continue
        fi

        if [[ "$issue_type" == "not_executable" ]]; then
            if [[ "$dry_run" == "false" ]]; then
                chmod +x "$full_path" && {
                    echo "  Made executable: $file" >&2
                    ((fixed++))
                }
            else
                echo "  Would make executable: $file" >&2
                ((fixed++))
            fi
        elif [[ "$issue_type" == "should_not_be_executable" ]]; then
            if [[ "$dry_run" == "false" ]]; then
                chmod -x "$full_path" && {
                    echo "  Removed executable: $file" >&2
                    ((fixed++))
                }
            else
                echo "  Would remove executable: $file" >&2
                ((fixed++))
            fi
        fi
    done < <(jq -c '.issues[]' "$scan_file" 2>/dev/null || echo "")

    echo "$fixed"
}

remove_duplicate_files() {
    local scan_file="$1"
    local dry_run="${2:-true}"

    echo "Removing duplicate files (keeping newest)..." >&2

    local removed=0

    # Process duplicates from scan file (Bash 3.x compatible)
    while IFS= read -r dup; do
        local hash=$(echo "$dup" | jq -r '.hash')
        local original=$(echo "$dup" | jq -r '.original')
        local duplicate=$(echo "$dup" | jq -r '.duplicate')

        # Compare modification times
        local orig_time=$(stat -f %m "$PROJECT_ROOT/$original" 2>/dev/null || stat -c %Y "$PROJECT_ROOT/$original" 2>/dev/null || echo "0")
        local dup_time=$(stat -f %m "$PROJECT_ROOT/$duplicate" 2>/dev/null || stat -c %Y "$PROJECT_ROOT/$duplicate" 2>/dev/null || echo "0")

        local file_to_remove
        if [[ $orig_time -gt $dup_time ]]; then
            file_to_remove="$duplicate"
        else
            file_to_remove="$original"
        fi

        if [[ "$dry_run" == "false" ]]; then
            rm "$PROJECT_ROOT/$file_to_remove" && {
                echo "  Removed duplicate: $file_to_remove" >&2
                ((removed++))
            }
        else
            echo "  Would remove duplicate: $file_to_remove" >&2
            ((removed++))
        fi
    done < <(jq -c '.duplicates[]' "$scan_file" 2>/dev/null || echo "")

    echo "$removed"
}

remove_unreferenced_files() {
    local scan_file="$1"
    local dry_run="${2:-true}"
    local confidence_threshold="${3:-0.9}"

    echo "Removing unreferenced files (confidence >= $confidence_threshold)..." >&2

    # Load exclusion patterns from config
    local exclude_patterns=()
    if [[ -f "$CONFIG_FILE" ]]; then
        while IFS= read -r pattern; do
            exclude_patterns+=("$pattern")
        done < <(jq -r '.safe_to_remove.exclude_patterns[]' "$CONFIG_FILE" 2>/dev/null || echo "")
    fi

    local removed=0

    while IFS= read -r file; do
        local skip=false

        # Check exclusion patterns
        for pattern in "${exclude_patterns[@]}"; do
            if [[ "$file" == *"$pattern"* ]]; then
                echo "  Skipping (excluded): $file" >&2
                skip=true
                break
            fi
        done

        [[ "$skip" == "true" ]] && continue

        # Additional safety checks
        if [[ "$file" == *"/lib/"* || "$file" == *"/config/"* || "$file" == *"README"* ]]; then
            echo "  Skipping (safety): $file" >&2
            continue
        fi

        if [[ "$dry_run" == "false" ]]; then
            rm "$PROJECT_ROOT/$file" && {
                echo "  Removed: $file" >&2
                ((removed++))
            }
        else
            echo "  Would remove: $file" >&2
            ((removed++))
        fi
    done < <(jq -r '.files[]' "$scan_file" 2>/dev/null || echo "")

    echo "$removed"
}

clean_gitignore_violations() {
    local scan_file="$1"
    local dry_run="${2:-true}"

    echo "Cleaning .gitignore violations..." >&2

    local fixed=0

    while IFS= read -r issue; do
        local file=$(echo "$issue" | jq -r '.file')
        local issue_type=$(echo "$issue" | jq -r '.issue')

        if [[ "$issue_type" == "tracked_but_should_ignore" ]]; then
            if [[ "$dry_run" == "false" ]]; then
                git rm --cached "$file" 2>/dev/null && {
                    echo "  Untracked: $file" >&2
                    ((fixed++))
                }
            else
                echo "  Would untrack: $file" >&2
                ((fixed++))
            fi
        fi
    done < <(jq -c '.issues[]' "$scan_file" 2>/dev/null || echo "")

    echo "$fixed"
}

# ==============================================================================
# MAIN AUTO-FIX
# ==============================================================================

run_auto_fix() {
    local scan_dir="$1"
    local dry_run="${2:-true}"

    echo "=== Cleanup Master - Auto-Fix ===" >&2
    echo "Mode: $([ "$dry_run" == "true" ] && echo "DRY RUN" || echo "LIVE")" >&2
    echo "" >&2

    local fixes=()

    # Empty directories (safest)
    if [[ -f "$scan_dir/empty-directories.json" ]]; then
        local count=$(remove_empty_directories "$scan_dir/empty-directories.json" "$dry_run")
        fixes+=("empty_directories:$count")
        echo "" >&2
    fi

    # File permissions
    if [[ -f "$scan_dir/permission-issues.json" ]]; then
        local count=$(fix_file_permissions "$scan_dir/permission-issues.json" "$dry_run")
        fixes+=("file_permissions:$count")
        echo "" >&2
    fi

    # Duplicates
    if [[ -f "$scan_dir/duplicate-files.json" ]]; then
        local count=$(remove_duplicate_files "$scan_dir/duplicate-files.json" "$dry_run")
        fixes+=("duplicate_files:$count")
        echo "" >&2
    fi

    # .gitignore violations
    if [[ -f "$scan_dir/gitignore-issues.json" ]]; then
        local count=$(clean_gitignore_violations "$scan_dir/gitignore-issues.json" "$dry_run")
        fixes+=("gitignore_violations:$count")
        echo "" >&2
    fi

    # Unreferenced files (with high confidence only)
    if [[ -f "$scan_dir/unreferenced-files.json" ]]; then
        local count=$(remove_unreferenced_files "$scan_dir/unreferenced-files.json" "$dry_run" 0.95)
        fixes+=("unreferenced_files:$count")
        echo "" >&2
    fi

    # Generate fix summary
    local fix_json="["
    for fix in "${fixes[@]}"; do
        local fix_type=$(echo "$fix" | cut -d: -f1)
        local fix_count=$(echo "$fix" | cut -d: -f2)
        fix_json+="{\"type\": \"$fix_type\", \"count\": $fix_count},"
    done
    fix_json="${fix_json%,}]"

    jq -n \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg mode "$([ "$dry_run" == "true" ] && echo "dry_run" || echo "live")" \
        --argjson fixes "$fix_json" \
        '{
            timestamp: $timestamp,
            mode: $mode,
            fixes: $fixes,
            total_fixes: ($fixes | map(.count) | add)
        }' > "$scan_dir/auto-fix-summary.json"

    echo "=== Auto-Fix Complete ===" >&2
    cat "$scan_dir/auto-fix-summary.json" | jq >&2
}

# ==============================================================================
# EXPORTS
# ==============================================================================

export -f remove_empty_directories
export -f fix_file_permissions
export -f remove_duplicate_files
export -f remove_unreferenced_files
export -f clean_gitignore_violations
export -f run_auto_fix
