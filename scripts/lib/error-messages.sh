#!/usr/bin/env bash
# Standardized Error Messages for Cortex
# Provides consistent, actionable error reporting

set -euo pipefail

# Prevent re-sourcing
if [ -n "${ERROR_MESSAGES_LOADED:-}" ]; then
    return 0
fi
ERROR_MESSAGES_LOADED=1

# ==============================================================================
# ERROR CODES
# ==============================================================================

readonly ERR_FILE_NOT_FOUND=101
readonly ERR_INVALID_JSON=102
readonly ERR_MISSING_DEPENDENCY=103
readonly ERR_INVALID_CONFIG=104
readonly ERR_API_FAILURE=105
readonly ERR_TIMEOUT=106
readonly ERR_PERMISSION_DENIED=107
readonly ERR_INVALID_ARGUMENT=108
readonly ERR_WORKER_SPAWN_FAILED=109
readonly ERR_ROUTING_FAILED=110
readonly ERR_TOKEN_BUDGET_EXCEEDED=111

# ==============================================================================
# ERROR LOGGING
# ==============================================================================

# Log error with code and context
# Args: $1=error_code, $2=message, $3=context (optional)
log_error() {
    local error_code="$1"
    local message="$2"
    local context="${3:-}"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Create error object
    local error_json=$(jq -n \
        --arg code "$error_code" \
        --arg msg "$message" \
        --arg ctx "$context" \
        --arg ts "$timestamp" \
        --arg component "${COMPONENT_NAME:-unknown}" \
        '{
            error_code: ($code | tonumber),
            message: $msg,
            context: $ctx,
            timestamp: $ts,
            component: $component
        }')

    # Log to stderr with formatting
    echo "ERROR [$error_code]: $message" >&2

    if [[ -n "$context" ]]; then
        echo "  Context: $context" >&2
    fi

    # Log to error file
    echo "$error_json" >> coordination/logs/errors.jsonl 2>/dev/null || true
}

# ==============================================================================
# COMMON ERROR HANDLERS
# ==============================================================================

# File not found error
# Args: $1=file_path, $2=suggestion (optional)
error_file_not_found() {
    local file_path="$1"
    local suggestion="${2:-Check file path and permissions}"

    log_error $ERR_FILE_NOT_FOUND \
        "File not found: $file_path" \
        "$suggestion"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Verify file path: $file_path" >&2
    echo "  2. Check file exists: ls -la $(dirname "$file_path")" >&2
    echo "  3. Check permissions: stat $file_path" >&2
    echo "  4. $suggestion" >&2

    return $ERR_FILE_NOT_FOUND
}

# Invalid JSON error
# Args: $1=file_path
error_invalid_json() {
    local file_path="$1"

    log_error $ERR_INVALID_JSON \
        "Invalid JSON in file: $file_path" \
        "Run: jq . $file_path to see error details"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Validate JSON: jq . $file_path" >&2
    echo "  2. Check for trailing commas" >&2
    echo "  3. Check for unquoted strings" >&2
    echo "  4. Use a JSON linter" >&2

    return $ERR_INVALID_JSON
}

# Missing dependency error
# Args: $1=dependency_name, $2=install_command
error_missing_dependency() {
    local dependency="$1"
    local install_cmd="$2"

    log_error $ERR_MISSING_DEPENDENCY \
        "Missing required dependency: $dependency" \
        "Install with: $install_cmd"

    echo "" >&2
    echo "💡 How to fix:" >&2
    echo "  Run: $install_cmd" >&2

    return $ERR_MISSING_DEPENDENCY
}

# API failure error
# Args: $1=api_name, $2=status_code, $3=response
error_api_failure() {
    local api_name="$1"
    local status_code="$2"
    local response="$3"

    log_error $ERR_API_FAILURE \
        "$api_name API failed with status $status_code" \
        "Response: $response"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Check API key: echo \$ANTHROPIC_API_KEY" >&2
    echo "  2. Check network connectivity" >&2
    echo "  3. Check API status: https://status.anthropic.com" >&2
    echo "  4. Review response: $response" >&2

    return $ERR_API_FAILURE
}

# Timeout error
# Args: $1=operation, $2=timeout_seconds
error_timeout() {
    local operation="$1"
    local timeout="$2"

    log_error $ERR_TIMEOUT \
        "Operation timed out: $operation" \
        "Timeout: ${timeout}s"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Increase timeout value" >&2
    echo "  2. Check if service is running" >&2
    echo "  3. Check system resources (CPU, memory)" >&2
    echo "  4. Consider breaking into smaller operations" >&2

    return $ERR_TIMEOUT
}

# Worker spawn failed error
# Args: $1=worker_type, $2=reason
error_worker_spawn_failed() {
    local worker_type="$1"
    local reason="$2"

    log_error $ERR_WORKER_SPAWN_FAILED \
        "Failed to spawn $worker_type worker" \
        "$reason"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Check worker script exists: scripts/spawn-worker.sh" >&2
    echo "  2. Check worker type is valid: $worker_type" >&2
    echo "  3. Check token budget: scripts/show-metrics.sh" >&2
    echo "  4. Check system resources" >&2
    echo "  5. Review error: $reason" >&2

    return $ERR_WORKER_SPAWN_FAILED
}

# Routing failed error
# Args: $1=task_description, $2=reason
error_routing_failed() {
    local task="$1"
    local reason="$2"

    log_error $ERR_ROUTING_FAILED \
        "Failed to route task" \
        "Task: $task, Reason: $reason"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Check routing config: coordination/routing/config.json" >&2
    echo "  2. Verify all routing layers are operational" >&2
    echo "  3. Check task description clarity" >&2
    echo "  4. Review routing logs: coordination/routing/performance.jsonl" >&2
    echo "  5. Reason: $reason" >&2

    return $ERR_ROUTING_FAILED
}

# Token budget exceeded error
# Args: $1=requested, $2=remaining
error_token_budget_exceeded() {
    local requested="$1"
    local remaining="$2"

    log_error $ERR_TOKEN_BUDGET_EXCEEDED \
        "Token budget exceeded" \
        "Requested: $requested, Remaining: $remaining"

    echo "" >&2
    echo "💡 Suggestions:" >&2
    echo "  1. Wait for daily budget reset" >&2
    echo "  2. Check token usage: scripts/show-metrics.sh" >&2
    echo "  3. Optimize task descriptions (use fewer tokens)" >&2
    echo "  4. Consider increasing daily budget limit" >&2
    echo "  5. Current remaining: $remaining tokens" >&2

    return $ERR_TOKEN_BUDGET_EXCEEDED
}

# ==============================================================================
# WARNING MESSAGES
# ==============================================================================

# Warn with actionable message
# Args: $1=message, $2=suggestion (optional)
warn() {
    local message="$1"
    local suggestion="${2:-}"

    echo "⚠️  WARNING: $message" >&2

    if [[ -n "$suggestion" ]]; then
        echo "💡 $suggestion" >&2
    fi
}

# ==============================================================================
# INFO MESSAGES
# ==============================================================================

# Info message
# Args: $1=message
info() {
    local message="$1"
    echo "ℹ️  $message"
}

# Success message
# Args: $1=message
success() {
    local message="$1"
    echo "✅ $message"
}

# ==============================================================================
# ERROR REPORTING
# ==============================================================================

# Generate error report from logs
generate_error_report() {
    local error_log="coordination/logs/errors.jsonl"

    if [[ ! -f "$error_log" ]]; then
        echo "No errors logged"
        return 0
    fi

    echo "=== Error Report ==="
    echo ""

    # Group by error code
    jq -s 'group_by(.error_code) | map({
        error_code: .[0].error_code,
        count: length,
        message: .[0].message,
        last_occurrence: (map(.timestamp) | max)
    })' "$error_log"
}

# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

export -f log_error
export -f error_file_not_found
export -f error_invalid_json
export -f error_missing_dependency
export -f error_api_failure
export -f error_timeout
export -f error_worker_spawn_failed
export -f error_routing_failed
export -f error_token_budget_exceeded
export -f warn
export -f info
export -f success
export -f generate_error_report
