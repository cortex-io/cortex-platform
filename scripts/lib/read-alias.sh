#!/usr/bin/env bash

################################################################################
# Master Version Alias Reader Library
#
# Purpose: Reads version aliases for safe master deployments
# Supports: Champion/Challenger/Shadow deployment patterns
#
# Usage:
#   source scripts/lib/read-alias.sh
#   version=$(get_master_version "coordinator" "champion")
#   version_path=$(get_master_version_path "security" "challenger")
################################################################################

set -euo pipefail

# Source environment library (masters are shared across environments)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/environment.sh" ]; then
    source "$SCRIPT_DIR/environment.sh"
fi

# Masters directory is shared across environments
if type get_masters_dir &>/dev/null; then
    MASTERS_BASE=$(get_masters_dir)
else
    MASTERS_BASE="coordination/masters"
fi

# Get the version for a specific alias
# Args: $1=master_id, $2=alias (champion|challenger|shadow)
# Returns: version string (e.g., "v1.0.0") or empty if not set
get_master_version() {
    local master_id="$1"
    local alias_name="$2"

    local aliases_file="${MASTERS_BASE}/${master_id}/versions/aliases.json"

    if [ ! -f "$aliases_file" ]; then
        echo "ERROR: Aliases file not found: $aliases_file" >&2
        return 1
    fi

    local version=$(jq -r ".aliases.${alias_name}.version // empty" "$aliases_file")

    if [ -z "$version" ] || [ "$version" = "null" ]; then
        return 1
    fi

    echo "$version"
}

# Get the full path to a master version directory
# Args: $1=master_id, $2=alias (champion|challenger|shadow)
# Returns: absolute path to version directory
get_master_version_path() {
    local master_id="$1"
    local alias_name="$2"

    local version=$(get_master_version "$master_id" "$alias_name")

    if [ -z "$version" ]; then
        echo "ERROR: No version set for ${master_id}/${alias_name}" >&2
        return 1
    fi

    local base_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    echo "${base_dir}/${MASTERS_BASE}/${master_id}/versions/${version}"
}

# Get the champion (active production) version
# Args: $1=master_id
# Returns: version string
get_champion_version() {
    get_master_version "$1" "champion"
}

# Get the challenger (canary testing) version
# Args: $1=master_id
# Returns: version string or empty if not set
get_challenger_version() {
    get_master_version "$1" "challenger" 2>/dev/null || echo ""
}

# Get the shadow (silent monitoring) version
# Args: $1=master_id
# Returns: version string or empty if not set
get_shadow_version() {
    get_master_version "$1" "shadow" 2>/dev/null || echo ""
}

# Check if a version exists
# Args: $1=master_id, $2=version
# Returns: 0 if exists, 1 if not
version_exists() {
    local master_id="$1"
    local version="$2"

    local version_dir="${MASTERS_BASE}/${master_id}/versions/${version}"

    if [ -d "$version_dir" ]; then
        return 0
    else
        return 1
    fi
}

# Get all available versions for a master
# Args: $1=master_id
# Returns: list of version strings (one per line)
get_available_versions() {
    local master_id="$1"
    local versions_dir="${MASTERS_BASE}/${master_id}/versions"

    if [ ! -d "$versions_dir" ]; then
        return 1
    fi

    # List version directories, excluding aliases.json
    find "$versions_dir" -maxdepth 1 -type d -name "v*.*.*" | \
        xargs -n 1 basename | \
        sort -V
}

# Get alias status (active/inactive)
# Args: $1=master_id, $2=alias
# Returns: status string
get_alias_status() {
    local master_id="$1"
    local alias_name="$2"

    local aliases_file="${MASTERS_BASE}/${master_id}/versions/aliases.json"

    if [ ! -f "$aliases_file" ]; then
        echo "unknown"
        return 1
    fi

    jq -r ".aliases.${alias_name}.status // \"unknown\"" "$aliases_file"
}

# Get full alias information
# Args: $1=master_id, $2=alias
# Returns: JSON object with alias details
get_alias_info() {
    local master_id="$1"
    local alias_name="$2"

    local aliases_file="${MASTERS_BASE}/${master_id}/versions/aliases.json"

    if [ ! -f "$aliases_file" ]; then
        echo "{\"error\": \"aliases file not found\"}"
        return 1
    fi

    jq ".aliases.${alias_name}" "$aliases_file"
}

# Get all aliases for a master
# Args: $1=master_id
# Returns: JSON object with all alias configurations
get_all_aliases() {
    local master_id="$1"

    local aliases_file="${MASTERS_BASE}/${master_id}/versions/aliases.json"

    if [ ! -f "$aliases_file" ]; then
        echo "{\"error\": \"aliases file not found\"}"
        return 1
    fi

    jq ".aliases" "$aliases_file"
}

# Validate that champion version is set and exists
# Args: $1=master_id
# Returns: 0 if valid, 1 if invalid
validate_champion() {
    local master_id="$1"

    local champion_version=$(get_champion_version "$master_id" 2>/dev/null)

    if [ -z "$champion_version" ]; then
        echo "ERROR: No champion version set for $master_id" >&2
        return 1
    fi

    if ! version_exists "$master_id" "$champion_version"; then
        echo "ERROR: Champion version $champion_version does not exist for $master_id" >&2
        return 1
    fi

    return 0
}

# Export functions for use in other scripts
export -f get_master_version
export -f get_master_version_path
export -f get_champion_version
export -f get_challenger_version
export -f get_shadow_version
export -f version_exists
export -f get_available_versions
export -f get_alias_status
export -f get_alias_info
export -f get_all_aliases
export -f validate_champion
