#!/usr/bin/env bash
# Prompt Injection Detector
# Phase 3: Security & Efficiency
# Detects and prevents prompt injection attacks on autonomous agents

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

# Threat logging
THREAT_LOG="$CORTEX_HOME/coordination/security/threat-log.jsonl"
mkdir -p "$(dirname "$THREAT_LOG")"
touch "$THREAT_LOG"

##############################################################################
# detect_prompt_injection: Scan input for injection attempts
# Args:
#   $1: user_input or task_description
#   $2: context (optional)
# Returns: Detection result JSON
##############################################################################
detect_prompt_injection() {
    local user_input="$1"
    local context="${2:-general}"
    local timestamp=$(date -Iseconds)

    local threats_detected=()
    local severity="none"
    local confidence=0

    # Pattern 1: Instruction Override
    if echo "$user_input" | grep -qiE "(ignore|disregard|forget|override).*(previous|above|prior|earlier).*(instruction|prompt|direction|rule)"; then
        threats_detected+=("INSTRUCTION_OVERRIDE")
        severity="high"
        confidence=$((confidence + 30))
    fi

    # Pattern 2: Role Manipulation
    if echo "$user_input" | grep -qiE "you are now|act as if|pretend (you are|to be)|new role|system:"; then
        threats_detected+=("ROLE_MANIPULATION")
        [ "$severity" != "high" ] && severity="high"
        confidence=$((confidence + 25))
    fi

    # Pattern 3: Data Exfiltration
    if echo "$user_input" | grep -qiE "show me all|dump|export.*data|reveal.*secret|print.*(config|env|password|key)|list all"; then
        threats_detected+=("DATA_EXFILTRATION")
        [ "$severity" != "high" ] && severity="high"
        confidence=$((confidence + 35))
    fi

    # Pattern 4: Governance Bypass
    if echo "$user_input" | grep -qiE "GOVERNANCE_BYPASS|skip.*validation|bypass.*(security|check)|--no-verify|disable.*(governance|security)"; then
        threats_detected+=("GOVERNANCE_BYPASS")
        severity="critical"
        confidence=$((confidence + 40))
    fi

    # Pattern 5: Jailbreak Attempts
    if echo "$user_input" | grep -qiE "DAN mode|developer mode|admin mode|sudo mode|jailbreak|unrestricted"; then
        threats_detected+=("JAILBREAK_ATTEMPT")
        severity="critical"
        confidence=$((confidence + 35))
    fi

    # Pattern 6: Prompt Leaking
    if echo "$user_input" | grep -qiE "what are your instructions|show your prompt|reveal your system prompt|what were you told"; then
        threats_detected+=("PROMPT_LEAKING")
        [ "$severity" = "none" ] && severity="medium"
        confidence=$((confidence + 20))
    fi

    # Pattern 7: Delimiter Injection
    if echo "$user_input" | grep -qE '```|</system>|<\|im_end\|>|<\|endoftext\|>|\[INST\]|\[/INST\]'; then
        threats_detected+=("DELIMITER_INJECTION")
        [ "$severity" = "none" ] && severity="medium"
        confidence=$((confidence + 15))
    fi

    # Pattern 8: Encoded Payloads
    if echo "$user_input" | grep -qE 'base64|rot13|%[0-9a-f]{2}|\\x[0-9a-f]{2}|&#[0-9]+;'; then
        threats_detected+=("ENCODED_PAYLOAD")
        [ "$severity" = "none" ] && severity="low"
        confidence=$((confidence + 10))
    fi

    # Determine final severity and action
    local threat_count=${#threats_detected[@]}
    local action="allow"

    if [ "$severity" = "critical" ] || [ "$confidence" -ge 60 ]; then
        action="block"
    elif [ "$severity" = "high" ] || [ "$confidence" -ge 40 ]; then
        action="warn"
    elif [ "$severity" = "medium" ] || [ "$confidence" -ge 20 ]; then
        action="flag"
    fi

    # Build detection result
    local threats_json="[]"
    if [ "$threat_count" -gt 0 ]; then
        threats_json=$(printf '%s\n' "${threats_detected[@]}" | jq -R . | jq -s .)
    fi

    local detection_result=$(jq -n \
        --arg timestamp "$timestamp" \
        --arg context "$context" \
        --arg severity "$severity" \
        --arg action "$action" \
        --argjson confidence "$confidence" \
        --argjson threat_count "$threat_count" \
        --argjson threats "$threats_json" \
        --arg input_preview "${user_input:0:100}" \
        '{
            timestamp: $timestamp,
            context: $context,
            detection: {
                threats_detected: $threats,
                threat_count: $threat_count,
                severity: $severity,
                confidence: $confidence,
                action: $action
            },
            input_preview: $input_preview
        }')

    # Log if threats detected
    if [ "$threat_count" -gt 0 ]; then
        echo "$detection_result" >> "$THREAT_LOG"
    fi

    echo "$detection_result"
}

##############################################################################
# scan_task_input: Scan task description for injection
# Args:
#   $1: task_id
#   $2: task_description
##############################################################################
scan_task_input() {
    local task_id="$1"
    local task_description="$2"

    local result=$(detect_prompt_injection "$task_description" "task_$task_id")
    local action=$(echo "$result" | jq -r '.detection.action')
    local severity=$(echo "$result" | jq -r '.detection.severity')

    echo "$result" | jq '.'

    # Exit with error if should block
    if [ "$action" = "block" ]; then
        echo ""
        echo "🚨 SECURITY ALERT: Prompt injection detected!"
        echo "   Severity: $severity"
        echo "   Action: BLOCKED"
        echo "   Task ID: $task_id"
        return 1
    elif [ "$action" = "warn" ]; then
        echo ""
        echo "⚠️  WARNING: Suspicious input detected"
        echo "   Severity: $severity"
        echo "   Proceeding with caution..."
        return 0
    fi

    return 0
}

##############################################################################
# get_threat_summary: Get summary of detected threats
# Args:
#   $1: days (default: 7)
##############################################################################
get_threat_summary() {
    local days="${1:-7}"

    if [ ! -f "$THREAT_LOG" ]; then
        echo "No threats detected yet"
        return 0
    fi

    echo "=== Threat Summary (Last $days days) ==="
    echo ""

    # Get threats from last N days
    local cutoff_date=$(date -v-${days}d +%Y-%m-%d 2>/dev/null || date -d "$days days ago" +%Y-%m-%d)

    cat "$THREAT_LOG" | jq -s '
        map(select(.timestamp >= "'"$cutoff_date"'")) |
        {
            total_threats: length,
            by_severity: group_by(.detection.severity) | map({
                severity: .[0].detection.severity,
                count: length
            }),
            by_type: (map(.detection.threats_detected[]) | group_by(.) | map({
                type: .[0],
                count: length
            })),
            by_action: group_by(.detection.action) | map({
                action: .[0].detection.action,
                count: length
            }),
            avg_confidence: (map(.detection.confidence) | add / length)
        }
    '
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        detect)
            shift
            if [ -z "${1:-}" ]; then
                echo "Error: detect requires <input> [context]"
                exit 1
            fi
            detect_prompt_injection "$@" | jq '.'
            ;;
        scan-task)
            shift
            if [ $# -lt 2 ]; then
                echo "Error: scan-task requires <task_id> <task_description>"
                exit 1
            fi
            scan_task_input "$@"
            ;;
        summary)
            get_threat_summary "${2:-7}"
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  detect <input> [context]
    Detect prompt injection in user input

  scan-task <task_id> <task_description>
    Scan task description for injection attempts

  summary [days]
    Display threat summary (default: 7 days)

Detection Patterns:
  - Instruction Override: Attempts to ignore/override instructions
  - Role Manipulation: Attempts to change AI role/behavior
  - Data Exfiltration: Attempts to extract sensitive data
  - Governance Bypass: Attempts to bypass security controls
  - Jailbreak: Attempts to unlock restricted capabilities
  - Prompt Leaking: Attempts to reveal system prompts
  - Delimiter Injection: Special token/delimiter injection
  - Encoded Payloads: Base64, URL encoding, etc.

Severity Levels:
  - critical: Immediate block required
  - high: Block recommended
  - medium: Flag and monitor
  - low: Log for analysis

Actions:
  - block: Reject input immediately
  - warn: Allow with warning
  - flag: Log for review
  - allow: No action needed

Threats logged to: $THREAT_LOG
EOF
            ;;
    esac
fi
