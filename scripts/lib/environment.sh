#!/usr/bin/env bash

################################################################################
# Environment Library
#
# Purpose: Provides environment separation for dev/staging/prod deployments
# Supports: CORTEX_ENV variable-based environment selection
#
# Usage:
#   source scripts/lib/environment.sh
#   env=$(get_env)
#   path=$(get_coordination_path "tasks")
#   can_read=$(can_read_from_env "dev" "prod")
#
# Environment Rules:
#   - dev: Can read from staging and prod, writes to dev only
#   - staging: Can read from prod, writes to staging only
#   - prod: Isolated, writes to prod only
################################################################################

set -euo pipefail

# Prevent re-sourcing
if [ -n "${ENVIRONMENT_LIB_LOADED:-}" ]; then
    return 0
fi
ENVIRONMENT_LIB_LOADED=1

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Valid environments
readonly VALID_ENVIRONMENTS=("dev" "staging" "prod")

# Default environment (prod for production safety)
readonly DEFAULT_ENV="prod"

# Base coordination directory
readonly CORTEX_HOME="${CORTEX_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
readonly COORDINATION_BASE="$CORTEX_HOME/coordination"

# ==============================================================================
# CORE FUNCTIONS
# ==============================================================================

# Get current environment
# Returns: environment name (dev/staging/prod)
# Example: env=$(get_env)
get_env() {
    local env="${CORTEX_ENV:-$DEFAULT_ENV}"

    # Validate environment
    if ! is_valid_env "$env"; then
        echo "ERROR: Invalid environment '$env'. Must be one of: ${VALID_ENVIRONMENTS[*]}" >&2
        echo "$DEFAULT_ENV"
        return 1
    fi

    echo "$env"
}

# Check if environment name is valid
# Args: $1=environment
# Returns: 0 if valid, 1 if invalid
is_valid_env() {
    local env="$1"

    for valid_env in "${VALID_ENVIRONMENTS[@]}"; do
        if [ "$env" = "$valid_env" ]; then
            return 0
        fi
    done

    return 1
}

# Get environment-specific coordination path
# Args: $1=subdirectory (e.g., "tasks", "metrics", "lineage")
# Returns: absolute path to environment-specific directory
# Example: tasks_dir=$(get_coordination_path "tasks")
get_coordination_path() {
    local subdir="${1:-}"
    local env
    env=$(get_env)

    if [ -z "$subdir" ]; then
        # Return base environment directory
        echo "$COORDINATION_BASE/$env"
    else
        # Return specific subdirectory
        echo "$COORDINATION_BASE/$env/$subdir"
    fi
}

# Get path for a specific environment (for cross-env reads)
# Args: $1=target_env, $2=subdirectory
# Returns: absolute path to target environment directory
# Example: prod_tasks=$(get_env_path "prod" "tasks")
get_env_path() {
    local target_env="$1"
    local subdir="${2:-}"

    if ! is_valid_env "$target_env"; then
        echo "ERROR: Invalid target environment '$target_env'" >&2
        return 1
    fi

    if [ -z "$subdir" ]; then
        echo "$COORDINATION_BASE/$target_env"
    else
        echo "$COORDINATION_BASE/$target_env/$subdir"
    fi
}

# Check if current environment can read from target environment
# Args: $1=target_env
# Returns: 0 if allowed, 1 if not allowed
# Example: if can_read_from_env "prod"; then ... fi
can_read_from_env() {
    local target_env="$1"
    local current_env
    current_env=$(get_env)

    # Validate both environments
    if ! is_valid_env "$target_env"; then
        echo "ERROR: Invalid target environment '$target_env'" >&2
        return 1
    fi

    # Same environment - always allowed
    if [ "$current_env" = "$target_env" ]; then
        return 0
    fi

    # Cross-environment access rules
    case "$current_env" in
        dev)
            # Dev can read from staging and prod
            if [ "$target_env" = "staging" ] || [ "$target_env" = "prod" ]; then
                return 0
            fi
            ;;
        staging)
            # Staging can read from prod only
            if [ "$target_env" = "prod" ]; then
                return 0
            fi
            ;;
        prod)
            # Prod is isolated - no cross-env reads
            return 1
            ;;
    esac

    # Default deny
    return 1
}

# Check if current environment can write to target environment
# Args: $1=target_env
# Returns: 0 if allowed, 1 if not allowed
can_write_to_env() {
    local target_env="$1"
    local current_env
    current_env=$(get_env)

    # Can only write to own environment
    if [ "$current_env" = "$target_env" ]; then
        return 0
    fi

    # All cross-environment writes are denied
    return 1
}

# ==============================================================================
# PATH MIGRATION HELPERS
# ==============================================================================

# Get environment-aware path for common coordination directories
# These functions replace hardcoded "coordination/X" paths

get_tasks_dir() {
    get_coordination_path "tasks"
}

get_routing_dir() {
    get_coordination_path "routing"
}

get_metrics_dir() {
    get_coordination_path "metrics"
}

get_lineage_dir() {
    get_coordination_path "lineage"
}

get_events_dir() {
    get_coordination_path "events"
}

get_traces_dir() {
    get_coordination_path "traces"
}

get_logs_dir() {
    get_coordination_path "logs"
}

# ==============================================================================
# SHARED RESOURCES
# ==============================================================================

# Get path to shared resources (not environment-specific)
# Args: $1=resource_type (e.g., "prompts", "schemas", "masters")
# Returns: absolute path to shared resource directory
get_shared_path() {
    local resource_type="$1"
    echo "$COORDINATION_BASE/$resource_type"
}

# Common shared resources
get_prompts_dir() {
    get_shared_path "prompts"
}

get_schemas_dir() {
    get_shared_path "schemas"
}

get_masters_dir() {
    get_shared_path "masters"
}

get_workers_dir() {
    get_shared_path "workers"
}

get_config_dir() {
    get_shared_path "config"
}

get_catalog_dir() {
    get_shared_path "catalog"
}

# ==============================================================================
# ENVIRONMENT STATUS
# ==============================================================================

# Get environment status information
# Returns: JSON with environment details
get_env_status() {
    local current_env
    current_env=$(get_env)

    local can_read_staging="false"
    local can_read_prod="false"

    if can_read_from_env "staging" 2>/dev/null; then
        can_read_staging="true"
    fi

    if can_read_from_env "prod" 2>/dev/null; then
        can_read_prod="true"
    fi

    jq -n \
        --arg env "$current_env" \
        --arg home "$CORTEX_HOME" \
        --arg coord_base "$COORDINATION_BASE" \
        --arg can_staging "$can_read_staging" \
        --arg can_prod "$can_read_prod" \
        '{
            current_environment: $env,
            cortex_home: $home,
            coordination_base: $coord_base,
            cross_env_read_access: {
                staging: ($can_staging == "true"),
                prod: ($can_prod == "true")
            },
            write_isolation: "enabled",
            paths: {
                tasks: ($coord_base + "/" + $env + "/tasks"),
                routing: ($coord_base + "/" + $env + "/routing"),
                metrics: ($coord_base + "/" + $env + "/metrics"),
                lineage: ($coord_base + "/" + $env + "/lineage"),
                events: ($coord_base + "/" + $env + "/events"),
                traces: ($coord_base + "/" + $env + "/traces"),
                logs: ($coord_base + "/" + $env + "/logs")
            }
        }'
}

# Display environment information
display_env_info() {
    local current_env
    current_env=$(get_env)

    echo "=== Cortex Environment Information ==="
    echo "Current Environment: $current_env"
    echo "Coordination Base: $COORDINATION_BASE"
    echo ""
    echo "Environment Paths:"
    echo "  Tasks:   $(get_tasks_dir)"
    echo "  Routing: $(get_routing_dir)"
    echo "  Metrics: $(get_metrics_dir)"
    echo "  Lineage: $(get_lineage_dir)"
    echo ""
    echo "Shared Resources:"
    echo "  Prompts: $(get_prompts_dir)"
    echo "  Schemas: $(get_schemas_dir)"
    echo "  Masters: $(get_masters_dir)"
    echo ""
    echo "Cross-Environment Read Access:"
    if can_read_from_env "dev" 2>/dev/null; then
        echo "  dev: allowed"
    fi
    if can_read_from_env "staging" 2>/dev/null; then
        echo "  staging: allowed"
    fi
    if can_read_from_env "prod" 2>/dev/null; then
        echo "  prod: allowed"
    fi
    echo ""
}

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Initialize environment directories
# Creates necessary subdirectories for current environment
init_env_directories() {
    local env
    env=$(get_env)

    local env_base="$COORDINATION_BASE/$env"

    # Create standard subdirectories
    mkdir -p "$env_base"/{tasks,routing,metrics,lineage,events,traces,logs}

    echo "Initialized directories for environment: $env"
}

# Migrate data from legacy coordination/ to prod environment
# This is a one-time migration helper
migrate_to_env_structure() {
    local legacy_dirs=("tasks" "routing" "metrics" "lineage" "events" "traces" "logs")
    local prod_base="$COORDINATION_BASE/prod"

    echo "Starting migration to environment structure..."
    echo "This will move existing data to prod environment"
    echo ""

    for dir in "${legacy_dirs[@]}"; do
        local legacy_path="$COORDINATION_BASE/$dir"
        local prod_path="$prod_base/$dir"

        if [ -d "$legacy_path" ] && [ ! -L "$legacy_path" ]; then
            # Check if directory has content
            if [ "$(ls -A "$legacy_path" 2>/dev/null)" ]; then
                echo "Migrating $dir..."

                # Ensure prod directory exists
                mkdir -p "$prod_path"

                # Move contents (not the directory itself)
                cp -R "$legacy_path/"* "$prod_path/" 2>/dev/null || true

                echo "  Moved to: $prod_path"
            fi
        fi
    done

    echo ""
    echo "Migration complete!"
    echo "Review prod environment data before removing legacy directories"
}

# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

export -f get_env
export -f is_valid_env
export -f get_coordination_path
export -f get_env_path
export -f can_read_from_env
export -f can_write_to_env
export -f get_tasks_dir
export -f get_routing_dir
export -f get_metrics_dir
export -f get_lineage_dir
export -f get_events_dir
export -f get_traces_dir
export -f get_logs_dir
export -f get_shared_path
export -f get_prompts_dir
export -f get_schemas_dir
export -f get_masters_dir
export -f get_workers_dir
export -f get_config_dir
export -f get_catalog_dir
export -f get_env_status
export -f display_env_info
export -f init_env_directories
export -f migrate_to_env_structure
