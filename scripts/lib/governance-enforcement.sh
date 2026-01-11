#!/usr/bin/env bash
# Governance Enforcement Layer
# Provides pre-flight validation, hard budget limits, and audit trails
#
# CRITICAL POLICIES:
# 1. Port Assignment: NEVER assign ports or create portals without explicit approval
#    - Cortex must NEVER automatically assign ports (conflicts with other apps)
#    - All port changes require human approval via critical task approval
#    - Default Cortex API port: 9000 (do not change without permission)
# 2. Token Budget: Hard limit at 95% of daily budget
# 3. Dangerous Operations: Block destructive operations without approval
# 4. Critical Tasks: Require human approval within 1-hour window

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
GOVERNANCE_DIR="$CORTEX_HOME/coordination/governance"
OVERRIDES_LOG="$GOVERNANCE_DIR/overrides.jsonl"
TOKEN_BUDGET="$CORTEX_HOME/coordination/token-budget.json"

# Ensure governance directory exists
mkdir -p "$GOVERNANCE_DIR"

##############################################################################
# validate_task_governance: Pre-flight validation before spawning worker
# Args:
#   $1: task_id
#   $2: task_description
#   $3: master (development, security, inventory)
#   $4: priority (low, medium, high, critical)
# Returns: 0 if allowed, 1 if blocked
##############################################################################
validate_task_governance() {
    local task_id="$1"
    local task_description="$2"
    local master="$3"
    local priority="${4:-medium}"
    
    local violations=()
    
    # Check 1: Token budget check (HARD limit)
    if ! check_token_budget "$task_id"; then
        violations+=("Token budget exceeded - hard limit reached")
    fi
    
    # Check 2: Dangerous operation detection
    local dangerous_ops=$(detect_dangerous_operations "$task_description")
    if [ -n "$dangerous_ops" ]; then
        violations+=("Dangerous operations detected: $dangerous_ops")
    fi
    
    # Check 3: Critical task approval requirement
    if [ "$priority" = "critical" ]; then
        if ! check_critical_approval "$task_id"; then
            violations+=("Critical tasks require human approval")
        fi
    fi
    
    # Check 4: Master-specific governance rules
    if ! check_master_rules "$master" "$task_description"; then
        violations+=("Master-specific governance rules violated")
    fi
    
    # If any violations, block and log
    if [ ${#violations[@]} -gt 0 ]; then
        log_governance_block "$task_id" "$task_description" "${violations[@]}"
        return 1
    fi
    
    return 0
}

##############################################################################
# check_token_budget: Enforce HARD token budget limits
##############################################################################
check_token_budget() {
    local task_id="$1"
    
    if [ ! -f "$TOKEN_BUDGET" ]; then
        # No budget file = allow (fail open for now)
        return 0
    fi
    
    local daily_used=$(jq -r '.budget.daily.used // 0' "$TOKEN_BUDGET" 2>/dev/null || echo "0")
    local daily_limit=$(jq -r '.budget.daily.limit // 270000' "$TOKEN_BUDGET" 2>/dev/null || echo "270000")
    
    # Hard limit: If 95% of budget used, block new tasks
    local threshold=$(echo "scale=0; $daily_limit * 0.95" | bc)
    
    if (( $(echo "$daily_used >= $threshold" | bc -l) )); then
        return 1
    fi
    
    return 0
}

##############################################################################
# detect_dangerous_operations: Detect operations requiring human approval
##############################################################################
detect_dangerous_operations() {
    local task_description="$1"
    local desc_lower=$(echo "$task_description" | tr '[:upper:]' '[:lower:]')
    
    local dangerous_keywords=(
        "rm -rf"
        "delete database"
        "drop table"
        "force push"
        "reset --hard"
        "revoke"
        "destroy"
        "terminate"
        "shutdown"
        "assign port"
        "create portal"
        "port:"
        "listen on"
        "app.listen"
        "start server"
        "expose port"
    )
    
    local detected=()
    for keyword in "${dangerous_keywords[@]}"; do
        if echo "$desc_lower" | grep -q "$keyword"; then
            detected+=("$keyword")
        fi
    done
    
    if [ ${#detected[@]} -gt 0 ]; then
        echo "${detected[*]}"
    fi
}

##############################################################################
# check_critical_approval: Verify human approval for critical tasks
##############################################################################
check_critical_approval() {
    local task_id="$1"
    
    # Check if approval file exists
    local approval_file="$GOVERNANCE_DIR/approvals/$task_id.approved"
    
    if [ -f "$approval_file" ]; then
        # Check approval is recent (within 1 hour)
        local approval_time=$(stat -f %m "$approval_file" 2>/dev/null || stat -c %Y "$approval_file" 2>/dev/null)
        local current_time=$(date +%s)
        local age=$((current_time - approval_time))
        
        if [ $age -lt 3600 ]; then
            return 0
        fi
    fi
    
    return 1
}

##############################################################################
# check_master_rules: Check master-specific governance rules
##############################################################################
check_master_rules() {
    local master="$1"
    local task_description="$2"
    
    # Security master: High-severity CVEs require immediate action
    if [ "$master" = "security" ]; then
        if echo "$task_description" | grep -qi "CVE.*critical"; then
            # Allow critical CVEs to bypass budget limits (security exception)
            return 0
        fi
    fi
    
    # Development master: Prevent production deployments without approval
    if [ "$master" = "development" ]; then
        if echo "$task_description" | grep -qi "deploy.*production"; then
            if [ ! -f "$GOVERNANCE_DIR/production-deploy-approved" ]; then
                return 1
            fi
        fi
    fi
    
    return 0
}

##############################################################################
# log_governance_block: Log blocked tasks for audit trail
##############################################################################
log_governance_block() {
    local task_id="$1"
    local task_description="$2"
    shift 2
    local violations=("$@")
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local violations_json=$(printf '%s\n' "${violations[@]}" | jq -R . | jq -s .)
    
    jq -n \
        --arg timestamp "$timestamp" \
        --arg task_id "$task_id" \
        --arg description "$task_description" \
        --argjson violations "$violations_json" \
        '{
            timestamp: $timestamp,
            event: "task_blocked",
            task_id: $task_id,
            description: $description,
            violations: $violations
        }' >> "$OVERRIDES_LOG"
    
    echo "❌ Task $task_id BLOCKED by governance" >&2
    echo "   Violations:" >&2
    for violation in "${violations[@]}"; do
        echo "   - $violation" >&2
    done
}

##############################################################################
# log_governance_override: Log when governance rules are bypassed
##############################################################################
log_governance_override() {
    local task_id="$1"
    local reason="$2"
    local approved_by="${3:-system}"
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    jq -n \
        --arg timestamp "$timestamp" \
        --arg task_id "$task_id" \
        --arg reason "$reason" \
        --arg approved_by "$approved_by" \
        '{
            timestamp: $timestamp,
            event: "governance_override",
            task_id: $task_id,
            reason: $reason,
            approved_by: $approved_by
        }' >> "$OVERRIDES_LOG"
}

##############################################################################
# approve_critical_task: Create approval for critical task
##############################################################################
approve_critical_task() {
    local task_id="$1"
    local approved_by="${2:-user}"
    
    mkdir -p "$GOVERNANCE_DIR/approvals"
    local approval_file="$GOVERNANCE_DIR/approvals/$task_id.approved"
    
    echo "Approved by: $approved_by" > "$approval_file"
    echo "Approved at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$approval_file"
    
    log_governance_override "$task_id" "Critical task manually approved" "$approved_by"
    
    echo "✓ Task $task_id approved for 1 hour"
}

##############################################################################
# get_governance_stats: Get governance enforcement statistics
##############################################################################
get_governance_stats() {
    if [ ! -f "$OVERRIDES_LOG" ]; then
        echo "{\"total_blocks\": 0, \"total_overrides\": 0}"
        return
    fi
    
    local total_blocks=$(grep -c '"event":"task_blocked"' "$OVERRIDES_LOG" || echo "0")
    local total_overrides=$(grep -c '"event":"governance_override"' "$OVERRIDES_LOG" || echo "0")
    
    jq -n \
        --argjson blocks "$total_blocks" \
        --argjson overrides "$total_overrides" \
        '{
            total_blocks: $blocks,
            total_overrides: $overrides,
            enforcement_rate: (if ($blocks + $overrides) > 0 then ($blocks / ($blocks + $overrides)) else 0 end)
        }'
}

# Export functions for use in other scripts
export -f validate_task_governance
export -f check_token_budget
export -f detect_dangerous_operations
export -f log_governance_override
export -f approve_critical_task
export -f get_governance_stats
