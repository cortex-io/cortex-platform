#!/bin/bash
# Cortex Change Management Integration Layer
# Connects ITIL Change Management to all Cortex components

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CM_DIR="$(dirname "$SCRIPT_DIR")"

source "${CM_DIR}/change-manager.sh"
source "${CM_DIR}/config/change-config.sh"

# ============================================================================
# Master Agent Integrations
# ============================================================================

# Development Master - Change initiator for code changes
integrate_development_master() {
  local action="$1"
  local details="$2"

  case "$action" in
    deploy)
      # Create RFC for deployment
      local change_id=$(create_rfc \
        "normal" \
        "deployment" \
        "Deploy development changes: ${details}" \
        "Automated deployment from development-master" \
        "development-master" \
        "medium" \
        "medium")

      # Assess and route
      assess_change "$change_id"

      echo "$change_id"
      ;;

    fix_bug)
      # Emergency change for bug fixes
      local change_id=$(create_rfc \
        "emergency" \
        "deployment" \
        "Emergency bug fix: ${details}" \
        "Critical bug fix requiring immediate deployment" \
        "development-master" \
        "high" \
        "critical")

      # Fast-track assessment
      assess_change "$change_id"

      # Emergency changes are pre-approved
      approve_change "$change_id" "emergency-cab" "Emergency fix approved for immediate implementation"

      echo "$change_id"
      ;;

    *)
      echo "Unknown development-master action: $action" >&2
      return 1
      ;;
  esac
}

# Security Master - Change initiator for security operations
integrate_security_master() {
  local action="$1"
  local details="$2"

  case "$action" in
    patch_cve)
      local severity=$(echo "$details" | jq -r '.severity')

      if [[ "$severity" == "critical" ]]; then
        # Emergency change for critical CVEs
        local change_id=$(create_rfc \
          "emergency" \
          "security" \
          "Critical CVE patch: $(echo "$details" | jq -r '.cve_id')" \
          "$(echo "$details" | jq -r '.description')" \
          "security-master" \
          "critical" \
          "critical")
      else
        # Standard change for non-critical patches
        local change_id=$(create_rfc \
          "standard" \
          "security" \
          "Security patch: $(echo "$details" | jq -r '.cve_id')" \
          "$(echo "$details" | jq -r '.description')" \
          "security-master" \
          "medium" \
          "high")
      fi

      assess_change "$change_id"
      echo "$change_id"
      ;;

    scan_repository)
      # Documentation change (informational)
      local change_id=$(create_rfc \
        "standard" \
        "security" \
        "Security scan initiated: ${details}" \
        "Automated security vulnerability scan" \
        "security-master" \
        "low" \
        "low")

      # Auto-approved
      assess_change "$change_id"
      echo "$change_id"
      ;;

    *)
      echo "Unknown security-master action: $action" >&2
      return 1
      ;;
  esac
}

# CI/CD Master - Change operator for build/deploy operations
integrate_cicd_master() {
  local action="$1"
  local details="$2"

  case "$action" in
    build)
      # Standard change for builds
      local change_id=$(create_rfc \
        "standard" \
        "cicd" \
        "Build: ${details}" \
        "Automated build process" \
        "cicd-master" \
        "low" \
        "medium")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    deploy)
      # Normal change for deployments
      local environment=$(echo "$details" | jq -r '.environment')
      local impact="medium"
      local urgency="medium"

      if [[ "$environment" == "production" ]]; then
        impact="high"
      fi

      local change_id=$(create_rfc \
        "normal" \
        "deployment" \
        "Deploy to ${environment}: $(echo "$details" | jq -r '.service')" \
        "$(echo "$details" | jq -r '.description')" \
        "cicd-master" \
        "$impact" \
        "$urgency")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    rollback)
      # Emergency change for rollbacks
      local change_id=$(create_rfc \
        "emergency" \
        "rollback" \
        "Rollback: ${details}" \
        "Emergency rollback due to deployment issues" \
        "cicd-master" \
        "high" \
        "critical")

      assess_change "$change_id"
      approve_change "$change_id" "emergency-cab" "Rollback approved"
      echo "$change_id"
      ;;

    *)
      echo "Unknown cicd-master action: $action" >&2
      return 1
      ;;
  esac
}

# Inventory Master - Change initiator for documentation/cataloging
integrate_inventory_master() {
  local action="$1"
  local details="$2"

  case "$action" in
    catalog_repository)
      # Standard change for cataloging
      local change_id=$(create_rfc \
        "standard" \
        "inventory" \
        "Catalog repository: ${details}" \
        "Automated repository cataloging" \
        "inventory-master" \
        "low" \
        "low")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    update_dependencies)
      # Normal change for dependency updates
      local change_id=$(create_rfc \
        "normal" \
        "update" \
        "Update dependencies: ${details}" \
        "Dependency version updates" \
        "inventory-master" \
        "medium" \
        "medium")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    *)
      echo "Unknown inventory-master action: $action" >&2
      return 1
      ;;
  esac
}

# Coordinator Master - Change approver and router
integrate_coordinator_master() {
  local action="$1"
  local change_id="$2"
  local decision="${3:-}"

  case "$action" in
    review)
      # Coordinator reviews and routes high-risk changes
      show_change "$change_id"
      ;;

    approve)
      approve_change "$change_id" "coordinator-master" "$decision"
      ;;

    reject)
      reject_change "$change_id" "coordinator-master" "$decision"
      ;;

    route)
      # Route to appropriate master based on category
      local change_file=$(find_change_file "$change_id")
      local category=$(jq -r '.category' "$change_file")

      local target_master=$(assign_assessor "$category" 50)
      echo "Routing $change_id to $target_master"

      # Update assignment
      jq --arg master "$target_master" \
         '.assigned_to = $master' \
         "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"
      ;;

    *)
      echo "Unknown coordinator-master action: $action" >&2
      return 1
      ;;
  esac
}

# ============================================================================
# Worker Integrations
# ============================================================================

# Worker - Change implementer
integrate_worker() {
  local worker_id="$1"
  local action="$2"
  local change_id="${3:-}"

  case "$action" in
    execute)
      # Worker executes approved change
      echo "[$worker_id] Executing change: $change_id"

      # Update change to implementing state
      implement_change "$change_id"

      # Return execution context
      local change_file=$(find_change_file "$change_id")
      jq -r '.implementation_plan' "$change_file"
      ;;

    report_success)
      # Worker reports successful implementation
      echo "[$worker_id] Change $change_id completed successfully"

      close_change "$change_id" "successful" "Implemented by $worker_id"
      ;;

    report_failure)
      local error_msg="${4:-Unknown error}"

      echo "[$worker_id] Change $change_id failed: $error_msg"

      # Trigger rollback
      if [[ "$AUTO_ROLLBACK_ENABLED" == "true" ]]; then
        trigger_rollback "$change_id" "$worker_id" "$error_msg"
      fi

      close_change "$change_id" "failed" "Failed during implementation: $error_msg"
      ;;

    *)
      echo "Unknown worker action: $action" >&2
      return 1
      ;;
  esac
}

# ============================================================================
# Service Integrations
# ============================================================================

# YouTube Ingestion Service
integrate_youtube_ingestion() {
  local action="$1"
  local details="$2"

  case "$action" in
    update_service)
      # Normal change for service updates
      local change_id=$(create_rfc \
        "normal" \
        "deployment" \
        "Update YouTube ingestion service: ${details}" \
        "Service update with bug fixes and improvements" \
        "development-master" \
        "medium" \
        "medium")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    emergency_fix)
      # Emergency change for bug fixes (like today's fix!)
      local change_id=$(create_rfc \
        "emergency" \
        "deployment" \
        "Emergency fix for YouTube ingestion: ${details}" \
        "Critical bug fix with auto-recovery implementation" \
        "development-master" \
        "high" \
        "critical")

      assess_change "$change_id"
      approve_change "$change_id" "emergency-cab" "Auto-recovery bug fix approved"
      echo "$change_id"
      ;;

    *)
      echo "Unknown youtube-ingestion action: $action" >&2
      return 1
      ;;
  esac
}

# Cortex Chat Backend
integrate_cortex_chat() {
  local action="$1"
  local details="$2"

  case "$action" in
    deploy_feature)
      # Normal change for new features
      local change_id=$(create_rfc \
        "normal" \
        "deployment" \
        "Deploy Cortex Chat feature: ${details}" \
        "New feature deployment" \
        "development-master" \
        "medium" \
        "medium")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    hotfix)
      # Emergency change for hotfixes
      local change_id=$(create_rfc \
        "emergency" \
        "deployment" \
        "Cortex Chat hotfix: ${details}" \
        "Critical production hotfix" \
        "development-master" \
        "high" \
        "critical")

      assess_change "$change_id"
      approve_change "$change_id" "emergency-cab" "Hotfix approved"
      echo "$change_id"
      ;;

    *)
      echo "Unknown cortex-chat action: $action" >&2
      return 1
      ;;
  esac
}

# ============================================================================
# Infrastructure Integrations
# ============================================================================

# Kubernetes Operations
integrate_kubernetes() {
  local action="$1"
  local details="$2"

  case "$action" in
    scale)
      local replicas=$(echo "$details" | jq -r '.replicas')

      if [[ $replicas -le $STD_AUTOSCALE_MAX_REPLICAS ]]; then
        # Standard change for auto-scaling within limits
        local change_id=$(create_rfc \
          "standard" \
          "infrastructure" \
          "Auto-scale deployment: $(echo "$details" | jq -r '.deployment')" \
          "Scale to $replicas replicas" \
          "cicd-master" \
          "low" \
          "medium")
      else
        # Normal change for scaling beyond limits
        local change_id=$(create_rfc \
          "normal" \
          "infrastructure" \
          "Scale deployment beyond limits: $(echo "$details" | jq -r '.deployment')" \
          "Scale to $replicas replicas (above threshold)" \
          "cicd-master" \
          "medium" \
          "high")
      fi

      assess_change "$change_id"
      echo "$change_id"
      ;;

    restart_pod)
      # Standard change for pod restarts
      local change_id=$(create_rfc \
        "standard" \
        "infrastructure" \
        "Restart pod: ${details}" \
        "Automated pod restart due to health check failure" \
        "cicd-master" \
        "low" \
        "medium")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    update_config)
      # Normal change for configuration updates
      local change_id=$(create_rfc \
        "normal" \
        "configuration" \
        "Update Kubernetes config: ${details}" \
        "ConfigMap or Secret update" \
        "cicd-master" \
        "medium" \
        "medium")

      assess_change "$change_id"
      echo "$change_id"
      ;;

    *)
      echo "Unknown kubernetes action: $action" >&2
      return 1
      ;;
  esac
}

# ============================================================================
# Governance Integration
# ============================================================================

# Check if change complies with governance policies
check_governance_compliance() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  if [[ "$GOVERNANCE_ENABLED" != "true" ]]; then
    echo "true"
    return 0
  fi

  # Extract change details
  local category=$(jq -r '.category' "$change_file")
  local affected_services=$(jq -r '.affected_services' "$change_file")

  # Call governance validation
  if [[ -f "${GOVERNANCE_PATH}/compliance.js" ]]; then
    local compliance_result=$(node "${GOVERNANCE_PATH}/compliance.js" check-change "$change_id")

    # Update change with compliance status
    jq --argjson compliance "$compliance_result" \
       '.compliance = $compliance' \
       "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

    # Return result
    echo "$compliance_result" | jq -r '.passed'
  else
    echo "true"  # Default to compliant if governance not available
  fi
}

# ============================================================================
# CMDB Integration
# ============================================================================

# Update CMDB with change information
update_cmdb() {
  local change_id="$1"
  local change_file=$(find_change_file "$change_id")

  if [[ "$CMDB_ENABLED" != "true" ]]; then
    return 0
  fi

  # Extract affected CIs
  local affected_cis=$(jq -r '.affected_cis[]' "$change_file")

  # Update each CI with change reference
  for ci in $affected_cis; do
    local ci_file="${CMDB_PATH}/${ci}.json"

    if [[ -f "$ci_file" ]]; then
      # Append change to CI history
      jq --arg change_id "$change_id" \
         --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
         '.change_history += [{
           "change_id": $change_id,
           "timestamp": $timestamp
         }]' "$ci_file" > "${ci_file}.tmp" && mv "${ci_file}.tmp" "$ci_file"

      echo "Updated CMDB for CI: $ci"
    fi
  done
}

# ============================================================================
# Rollback Integration
# ============================================================================

# Trigger automated rollback
trigger_rollback() {
  local change_id="$1"
  local initiator="$2"
  local reason="$3"

  echo "Triggering rollback for change: $change_id"
  echo "Initiator: $initiator"
  echo "Reason: $reason"

  # Create rollback RFC
  local rollback_id=$(create_rfc \
    "emergency" \
    "rollback" \
    "Rollback of $change_id" \
    "Automatic rollback due to: $reason" \
    "$initiator" \
    "high" \
    "critical")

  # Auto-approve and implement
  assess_change "$rollback_id"
  approve_change "$rollback_id" "auto-rollback-system" "Automatic rollback triggered"
  implement_change "$rollback_id"

  # Link to original change
  local change_file=$(find_change_file "$change_id")
  jq --arg rollback_id "$rollback_id" \
     '.rollback_change_id = $rollback_id |
      .state = "rolled_back"' \
     "$change_file" > "${change_file}.tmp" && mv "${change_file}.tmp" "$change_file"

  log_audit "$change_id" "rolled_back" "$initiator" "Rolled back via $rollback_id"

  echo "$rollback_id"
}

# ============================================================================
# CLI Interface for Integrations
# ============================================================================

usage_integration() {
  cat <<EOF
Cortex Change Management Integration CLI

Usage: $0 <component> <action> [options]

Components:
  development-master  - Development Master integrations
  security-master     - Security Master integrations
  cicd-master         - CI/CD Master integrations
  inventory-master    - Inventory Master integrations
  coordinator-master  - Coordinator Master integrations
  worker              - Worker integrations
  youtube-ingestion   - YouTube Ingestion Service
  cortex-chat         - Cortex Chat Backend
  kubernetes          - Kubernetes Operations

Examples:
  $0 development-master deploy "New error recovery feature"
  $0 security-master patch_cve '{"cve_id":"CVE-2024-12345","severity":"critical"}'
  $0 cicd-master deploy '{"environment":"production","service":"cortex-chat"}'
  $0 worker worker-001 execute CHG-20251230-abc123
  $0 kubernetes scale '{"deployment":"cortex-chat","replicas":5}'

EOF
}

main_integration() {
  local component="${1:-}"
  local action="${2:-}"
  shift 2 || true

  if [[ -z "$component" || -z "$action" ]]; then
    usage_integration
    exit 1
  fi

  case "$component" in
    development-master)
      integrate_development_master "$action" "${1:-}"
      ;;
    security-master)
      integrate_security_master "$action" "${1:-}"
      ;;
    cicd-master)
      integrate_cicd_master "$action" "${1:-}"
      ;;
    inventory-master)
      integrate_inventory_master "$action" "${1:-}"
      ;;
    coordinator-master)
      integrate_coordinator_master "$action" "${1:-}" "${2:-}"
      ;;
    worker)
      integrate_worker "$action" "${1:-}" "${2:-}" "${3:-}"
      ;;
    youtube-ingestion)
      integrate_youtube_ingestion "$action" "${1:-}"
      ;;
    cortex-chat)
      integrate_cortex_chat "$action" "${1:-}"
      ;;
    kubernetes)
      integrate_kubernetes "$action" "${1:-}"
      ;;
    *)
      echo "ERROR: Unknown component: $component" >&2
      usage_integration
      exit 1
      ;;
  esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main_integration "$@"
fi
