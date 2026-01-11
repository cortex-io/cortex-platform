#!/bin/bash
# Cortex Change Manager - ITIL/ITSM Change Management Service
# Implements RFC (Request for Change) workflow with CAB oversight

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANGES_DIR="${SCRIPT_DIR}/changes"
POLICIES_DIR="${SCRIPT_DIR}/policies"
AUDIT_DIR="${SCRIPT_DIR}/audit"
CMDB_DIR="${SCRIPT_DIR}/../cmdb"

# Ensure directories exist
mkdir -p "$CHANGES_DIR"/{pending,approved,rejected,implemented,closed}
mkdir -p "$POLICIES_DIR"
mkdir -p "$AUDIT_DIR"

# Load configuration
source "${SCRIPT_DIR}/config/change-config.sh" 2>/dev/null || true

# ANSI colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Core Functions
# ============================================================================

# Generate unique change ID
generate_change_id() {
  local prefix="${1:-CHG}"
  local timestamp=$(date +%Y%m%d%H%M%S)
  local random=$(openssl rand -hex 3)
  echo "${prefix}-${timestamp}-${random}"
}

# Create RFC (Request for Change)
create_rfc() {
  local change_type="$1"
  local category="$2"
  local title="$3"
  local description="$4"
  local requester="${5:-cortex-system}"
  local impact="${6:-medium}"
  local urgency="${7:-medium}"

  local change_id=$(generate_change_id "RFC")
  local change_file="${CHANGES_DIR}/pending/${change_id}.json"

  cat > "$change_file" <<EOF
{
  "change_id": "${change_id}",
  "type": "${change_type}",
  "category": "${category}",
  "title": "${title}",
  "description": "${description}",
  "requested_by": "${requester}",
  "requested_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "state": "pending_assessment",
  "impact": "${impact}",
  "urgency": "${urgency}",
  "priority": null,
  "risk_score": null,
  "approval_required": null,
  "assigned_to": null,
  "implementation_plan": {},
  "rollback_plan": {},
  "affected_services": [],
  "affected_cis": [],
  "dependencies": [],
  "test_plan": {},
  "audit_trail": [
    {
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "action": "created",
      "actor": "${requester}",
      "details": "RFC created"
    }
  ],
  "compliance": {
    "soc2": null,
    "hipaa": null,
    "iso27001": null
  },
  "metrics": {
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "assessed_at": null,
    "approved_at": null,
    "implemented_at": null,
    "closed_at": null,
    "mtta": null,
    "mtti": null
  }
}
EOF

  echo "$change_id"
  log_audit "$change_id" "created" "$requester" "RFC created: $title"
}

# Assess change risk (ITIL Change Assessment)
assess_change() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  if [[ -z "$change_file" ]]; then
    echo "ERROR: Change $change_id not found" >&2
    return 1
  fi

  echo -e "${BLUE}[ChangeAssessment] Assessing RFC: $change_id${NC}"

  # Extract change details
  local impact=$(jq -r '.impact' "$change_file")
  local urgency=$(jq -r '.urgency' "$change_file")
  local category=$(jq -r '.category' "$change_file")
  local affected_services=$(jq -r '.affected_services | length' "$change_file")

  # Calculate priority matrix (ITIL)
  local priority=$(calculate_priority "$impact" "$urgency")

  # Calculate risk score
  local risk_score=$(calculate_risk_score "$change_file")

  # Determine approval requirements
  local approval_required=$(determine_approval "$risk_score" "$category")

  # Determine assigned assessor
  local assessor=$(assign_assessor "$category" "$risk_score")

  # Update change record
  jq --arg priority "$priority" \
     --arg risk "$risk_score" \
     --arg approval "$approval_required" \
     --arg assessor "$assessor" \
     --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.priority = $priority |
      .risk_score = ($risk | tonumber) |
      .approval_required = $approval |
      .assigned_to = $assessor |
      .state = "assessed" |
      .metrics.assessed_at = $timestamp |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "assessed",
        "actor": "ai-risk-engine",
        "details": "Risk score: \($risk), Priority: \($priority), Approval: \($approval)"
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  echo -e "${GREEN}[ChangeAssessment] Assessment complete${NC}"
  echo "  Priority: $priority"
  echo "  Risk Score: $risk_score"
  echo "  Approval Required: $approval_required"
  echo "  Assigned To: $assessor"

  log_audit "$change_id" "assessed" "ai-risk-engine" "Risk: $risk_score, Priority: $priority"

  # Auto-route based on approval requirements
  route_change "$change_id" "$approval_required"
}

# Calculate priority using ITIL matrix
calculate_priority() {
  local impact="$1"
  local urgency="$2"

  # ITIL Priority Matrix
  case "$impact-$urgency" in
    critical-critical|critical-high) echo "P1" ;;
    critical-medium|high-critical|high-high) echo "P2" ;;
    critical-low|high-medium|medium-critical|medium-high) echo "P3" ;;
    high-low|medium-medium|low-critical|low-high) echo "P4" ;;
    medium-low|low-medium|low-low) echo "P5" ;;
    *) echo "P3" ;;
  esac
}

# Calculate risk score (0-100)
calculate_risk_score() {
  local change_file="$1"

  # Extract factors
  local impact=$(jq -r '.impact' "$change_file")
  local urgency=$(jq -r '.urgency' "$change_file")
  local affected_count=$(jq -r '.affected_services | length' "$change_file")
  local category=$(jq -r '.category' "$change_file")

  # Impact scoring (0-40)
  local impact_score=0
  case "$impact" in
    critical) impact_score=40 ;;
    high) impact_score=30 ;;
    medium) impact_score=20 ;;
    low) impact_score=10 ;;
  esac

  # Complexity scoring (0-30)
  local complexity_score=$((affected_count * 5))
  [[ $complexity_score -gt 30 ]] && complexity_score=30

  # Category risk (0-20)
  local category_risk=0
  case "$category" in
    security|infrastructure) category_risk=20 ;;
    deployment|configuration) category_risk=15 ;;
    patch|update) category_risk=10 ;;
    documentation) category_risk=5 ;;
  esac

  # Historical success rate (0-10) - default to middle
  local history_score=5

  # Total risk score
  local total=$((impact_score + complexity_score + category_risk + history_score))

  echo "$total"
}

# Determine approval requirements based on risk
determine_approval() {
  local risk_score="$1"
  local category="$2"

  if [[ "$category" == "standard" ]]; then
    echo "pre-approved"
  elif [[ $risk_score -lt 30 ]]; then
    echo "auto-approved"
  elif [[ $risk_score -lt 60 ]]; then
    echo "technical-lead"
  else
    echo "cab"
  fi
}

# Assign assessor based on category and risk
assign_assessor() {
  local category="$1"
  local risk_score="$2"

  case "$category" in
    security) echo "security-master" ;;
    deployment) echo "development-master" ;;
    infrastructure) echo "cicd-master" ;;
    inventory) echo "inventory-master" ;;
    *)
      if [[ $risk_score -ge 60 ]]; then
        echo "coordinator-master"
      else
        echo "development-master"
      fi
      ;;
  esac
}

# Route change to appropriate workflow
route_change() {
  local change_id="$1"
  local approval_type="$2"

  echo -e "${BLUE}[ChangeRouter] Routing $change_id to $approval_type workflow${NC}"

  case "$approval_type" in
    pre-approved|auto-approved)
      approve_change "$change_id" "auto-approval-system" "Automatically approved (low risk)"
      ;;
    technical-lead)
      request_technical_lead_approval "$change_id"
      ;;
    cab)
      submit_to_cab "$change_id"
      ;;
    *)
      echo "ERROR: Unknown approval type: $approval_type" >&2
      return 1
      ;;
  esac
}

# Request Technical Lead approval
request_technical_lead_approval() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  echo -e "${YELLOW}[Approval] Requesting Technical Lead approval for $change_id${NC}"

  # Update state
  jq --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.state = "pending_approval" |
      .approval_required = "technical-lead" |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "approval_requested",
        "actor": "change-manager",
        "details": "Awaiting Technical Lead approval"
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  # TODO: Send notification (Slack, email, etc.)
  # send_notification "technical-lead" "$change_id"

  log_audit "$change_id" "approval_requested" "change-manager" "Technical Lead approval requested"
}

# Submit to CAB (Change Advisory Board)
submit_to_cab() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  echo -e "${YELLOW}[CAB] Submitting $change_id to Change Advisory Board${NC}"

  # Update state
  jq --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.state = "pending_cab" |
      .approval_required = "cab" |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "submitted_to_cab",
        "actor": "change-manager",
        "details": "Submitted for CAB review"
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  # Move to CAB queue
  local cab_dir="${CHANGES_DIR}/cab_queue"
  mkdir -p "$cab_dir"
  cp "$change_file" "$cab_dir/"

  log_audit "$change_id" "submitted_to_cab" "change-manager" "Awaiting CAB review"

  # TODO: Schedule CAB meeting if needed
  # schedule_cab_meeting "$change_id"
}

# Approve change
approve_change() {
  local change_id="$1"
  local approver="${2:-auto-approval-system}"
  local reason="${3:-Approved}"

  local change_file=$(find_change_file "$change_id")

  if [[ -z "$change_file" ]]; then
    echo "ERROR: Change $change_id not found" >&2
    return 1
  fi

  echo -e "${GREEN}[Approval] Approving $change_id by $approver${NC}"

  # Update state
  jq --arg approver "$approver" \
     --arg reason "$reason" \
     --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.state = "approved" |
      .approved_by = $approver |
      .approved_at = $timestamp |
      .metrics.approved_at = $timestamp |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "approved",
        "actor": $approver,
        "details": $reason
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  # Move to approved directory
  mv "$change_file" "${CHANGES_DIR}/approved/"

  log_audit "$change_id" "approved" "$approver" "$reason"

  # Auto-schedule implementation if ready
  if should_auto_implement "$change_id"; then
    implement_change "$change_id"
  fi
}

# Reject change
reject_change() {
  local change_id="$1"
  local rejector="$2"
  local reason="$3"

  local change_file=$(find_change_file "$change_id")

  echo -e "${RED}[Rejection] Rejecting $change_id by $rejector${NC}"

  # Update state
  jq --arg rejector "$rejector" \
     --arg reason "$reason" \
     --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.state = "rejected" |
      .rejected_by = $rejector |
      .rejected_at = $timestamp |
      .rejection_reason = $reason |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "rejected",
        "actor": $rejector,
        "details": $reason
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  # Move to rejected directory
  mv "$change_file" "${CHANGES_DIR}/rejected/"

  log_audit "$change_id" "rejected" "$rejector" "$reason"
}

# Implement change
implement_change() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  echo -e "${BLUE}[Implementation] Starting implementation of $change_id${NC}"

  # Update state
  jq --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     '.state = "implementing" |
      .implementation_started_at = $timestamp |
      .metrics.implemented_at = $timestamp |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "implementation_started",
        "actor": "cortex-deployer",
        "details": "Change implementation started"
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  # Move to implemented directory
  mv "$change_file" "${CHANGES_DIR}/implemented/"

  log_audit "$change_id" "implementation_started" "cortex-deployer" "Implementation started"

  # TODO: Trigger actual implementation
  # execute_implementation_plan "$change_id"
}

# Close change
close_change() {
  local change_id="$1"
  local status="${2:-successful}"
  local notes="${3:-Change completed successfully}"

  local change_file=$(find_change_file "$change_id")

  echo -e "${GREEN}[Close] Closing $change_id with status: $status${NC}"

  # Calculate MTTA and MTTI
  local created=$(jq -r '.metrics.created_at' "$change_file")
  local approved=$(jq -r '.metrics.approved_at' "$change_file")
  local implemented=$(jq -r '.metrics.implemented_at' "$change_file")
  local closed=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Update state
  jq --arg status "$status" \
     --arg notes "$notes" \
     --arg timestamp "$closed" \
     '.state = "closed" |
      .closure_status = $status |
      .closure_notes = $notes |
      .metrics.closed_at = $timestamp |
      .audit_trail += [{
        "timestamp": $timestamp,
        "action": "closed",
        "actor": "change-manager",
        "details": $notes
      }]' "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  # Move to closed directory
  mv "$change_file" "${CHANGES_DIR}/closed/"

  log_audit "$change_id" "closed" "change-manager" "Status: $status - $notes"

  # Update metrics database
  update_metrics "$change_id"
}

# ============================================================================
# Utility Functions
# ============================================================================

find_change_file() {
  local change_id="$1"
  find "$CHANGES_DIR" -type f -name "${change_id}.json" 2>/dev/null | head -n 1
}

should_auto_implement() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")
  local category=$(jq -r '.category' "$change_file")

  # Auto-implement standard and emergency changes
  [[ "$category" == "standard" || "$category" == "emergency" ]]
}

log_audit() {
  local change_id="$1"
  local action="$2"
  local actor="$3"
  local details="$4"

  local audit_file="${AUDIT_DIR}/$(date +%Y-%m-%d).log"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $change_id | $action | $actor | $details" >> "$audit_file"
}

update_metrics() {
  local change_id="$1"
  # TODO: Send metrics to time-series database
  echo "[Metrics] Updated metrics for $change_id"
}

# Display change details
show_change() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  if [[ -z "$change_file" ]]; then
    echo "ERROR: Change $change_id not found" >&2
    return 1
  fi

  echo -e "${BLUE}=== Change Details: $change_id ===${NC}"
  jq . "$change_file"
}

# List changes by state
list_changes() {
  local state="${1:-all}"

  if [[ "$state" == "all" ]]; then
    find "$CHANGES_DIR" -type f -name "*.json" | sort
  else
    find "${CHANGES_DIR}/${state}" -type f -name "*.json" 2>/dev/null | sort
  fi
}

# Generate metrics report
generate_metrics_report() {
  local period="${1:-today}"

  echo -e "${BLUE}=== Change Management Metrics Report ===${NC}"
  echo "Period: $period"
  echo ""

  # Count changes by state
  echo "Changes by State:"
  for state in pending approved rejected implemented closed; do
    local count=$(ls -1 "${CHANGES_DIR}/${state}"/*.json 2>/dev/null | wc -l | tr -d ' ')
    echo "  $state: $count"
  done

  echo ""

  # Success rate
  local total_closed=$(ls -1 "${CHANGES_DIR}/closed"/*.json 2>/dev/null | wc -l | tr -d ' ')
  local successful=$(grep -l '"closure_status": "successful"' "${CHANGES_DIR}/closed"/*.json 2>/dev/null | wc -l | tr -d ' ')

  if [[ $total_closed -gt 0 ]]; then
    local success_rate=$(echo "scale=2; $successful * 100 / $total_closed" | bc)
    echo "Success Rate: ${success_rate}%"
  fi
}

# ============================================================================
# CLI Interface
# ============================================================================

usage() {
  cat <<EOF
Cortex Change Manager - ITIL/ITSM Change Management

Usage: $0 <command> [options]

Commands:
  create <type> <category> <title> <description>  Create new RFC
  assess <change-id>                              Assess change risk
  approve <change-id> <approver> <reason>         Approve change
  reject <change-id> <rejector> <reason>          Reject change
  implement <change-id>                           Start implementation
  close <change-id> <status> <notes>              Close change
  show <change-id>                                Show change details
  list [state]                                    List changes
  metrics [period]                                Generate metrics report

Change Types:
  standard    - Pre-approved routine changes
  normal      - Regular changes requiring assessment
  emergency   - Urgent changes (expedited approval)

Categories:
  deployment, configuration, security, infrastructure,
  patch, update, inventory, documentation

States:
  pending, assessed, pending_approval, pending_cab,
  approved, rejected, implementing, implemented, closed

Examples:
  $0 create normal deployment "Deploy error recovery" "Fix YouTube bug"
  $0 assess RFC-20251230180000-abc123
  $0 approve RFC-20251230180000-abc123 tech-lead "Looks good"
  $0 list approved
  $0 metrics today

EOF
}

# Main entry point
main() {
  local command="${1:-}"

  if [[ -z "$command" ]]; then
    usage
    exit 1
  fi

  case "$command" in
    create)
      shift
      create_rfc "$@"
      ;;
    assess)
      assess_change "$2"
      ;;
    approve)
      approve_change "$2" "$3" "$4"
      ;;
    reject)
      reject_change "$2" "$3" "$4"
      ;;
    implement)
      implement_change "$2"
      ;;
    close)
      close_change "$2" "$3" "$4"
      ;;
    show)
      show_change "$2"
      ;;
    list)
      list_changes "${2:-all}"
      ;;
    metrics)
      generate_metrics_report "${2:-today}"
      ;;
    help|--help|-h)
      usage
      ;;
    *)
      echo "ERROR: Unknown command: $command" >&2
      usage
      exit 1
      ;;
  esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
