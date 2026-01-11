#!/bin/bash
# Cortex Change Management Configuration
# ITIL/ITSM Configuration Settings

# ============================================================================
# General Settings
# ============================================================================

# Change Management enabled
export CHANGE_MGMT_ENABLED="${CHANGE_MGMT_ENABLED:-true}"

# Require all changes to go through change management
export REQUIRE_CHANGE_APPROVAL="${REQUIRE_CHANGE_APPROVAL:-true}"

# Auto-approve low-risk changes
export AUTO_APPROVE_LOW_RISK="${AUTO_APPROVE_LOW_RISK:-true}"

# ============================================================================
# CAB (Change Advisory Board) Settings
# ============================================================================

# CAB meeting schedule (cron format: minute hour day-of-month month day-of-week)
export CAB_MEETING_SCHEDULE="${CAB_MEETING_SCHEDULE:-0 14 * * 4}"  # Thursdays 2 PM

# CAB members (comma-separated)
export CAB_MEMBERS="${CAB_MEMBERS:-tech-lead,security-lead,ops-lead,product-lead}"

# Minimum CAB approvals required for high-risk changes
export CAB_MIN_APPROVALS="${CAB_MIN_APPROVALS:-2}"

# Emergency CAB members (24/7 on-call)
export ECAB_MEMBERS="${ECAB_MEMBERS:-tech-lead-oncall,security-oncall}"

# ============================================================================
# Risk Thresholds
# ============================================================================

# Risk score thresholds (0-100)
export RISK_THRESHOLD_LOW="${RISK_THRESHOLD_LOW:-30}"
export RISK_THRESHOLD_MEDIUM="${RISK_THRESHOLD_MEDIUM:-60}"
export RISK_THRESHOLD_HIGH="${RISK_THRESHOLD_HIGH:-80}"

# Auto-approval threshold (changes below this are auto-approved)
export AUTO_APPROVE_THRESHOLD="${AUTO_APPROVE_THRESHOLD:-25}"

# ============================================================================
# Approval Workflows
# ============================================================================

# Technical Lead approval timeout (seconds)
export TECH_LEAD_APPROVAL_TIMEOUT="${TECH_LEAD_APPROVAL_TIMEOUT:-14400}"  # 4 hours

# CAB approval timeout (seconds)
export CAB_APPROVAL_TIMEOUT="${CAB_APPROVAL_TIMEOUT:-604800}"  # 1 week

# Auto-reject if no approval received
export AUTO_REJECT_ON_TIMEOUT="${AUTO_REJECT_ON_TIMEOUT:-false}"

# ============================================================================
# Implementation Settings
# ============================================================================

# Enable automatic implementation after approval
export AUTO_IMPLEMENT="${AUTO_IMPLEMENT:-true}"

# Implementation delay after approval (seconds)
export IMPLEMENTATION_DELAY="${IMPLEMENTATION_DELAY:-300}"  # 5 minutes

# Enable automatic rollback on failure
export AUTO_ROLLBACK_ENABLED="${AUTO_ROLLBACK_ENABLED:-true}"

# Rollback timeout (seconds)
export ROLLBACK_TIMEOUT="${ROLLBACK_TIMEOUT:-300}"  # 5 minutes

# ============================================================================
# Monitoring & Validation
# ============================================================================

# Post-implementation validation period (seconds)
export VALIDATION_PERIOD="${VALIDATION_PERIOD:-1800}"  # 30 minutes

# Health check interval during validation (seconds)
export HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-60}"

# Error rate threshold for rollback (percentage)
export ERROR_RATE_THRESHOLD="${ERROR_RATE_THRESHOLD:-5}"

# Latency increase threshold for rollback (percentage)
export LATENCY_THRESHOLD="${LATENCY_THRESHOLD:-200}"  # 2x baseline

# ============================================================================
# Compliance Settings
# ============================================================================

# SOC2 compliance mode
export SOC2_COMPLIANCE="${SOC2_COMPLIANCE:-true}"

# HIPAA compliance mode
export HIPAA_COMPLIANCE="${HIPAA_COMPLIANCE:-false}"

# ISO27001 compliance mode
export ISO27001_COMPLIANCE="${ISO27001_COMPLIANCE:-false}"

# Require segregation of duties (requester cannot approve)
export SEGREGATION_OF_DUTIES="${SEGREGATION_OF_DUTIES:-true}"

# Require change documentation
export REQUIRE_DOCUMENTATION="${REQUIRE_DOCUMENTATION:-true}"

# Require rollback plan for all changes
export REQUIRE_ROLLBACK_PLAN="${REQUIRE_ROLLBACK_PLAN:-true}"

# ============================================================================
# Notifications
# ============================================================================

# Enable Slack notifications
export SLACK_NOTIFICATIONS="${SLACK_NOTIFICATIONS:-false}"
export SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
export SLACK_CHANNEL="${SLACK_CHANNEL:-#cortex-changes}"

# Enable email notifications
export EMAIL_NOTIFICATIONS="${EMAIL_NOTIFICATIONS:-false}"
export EMAIL_SMTP_SERVER="${EMAIL_SMTP_SERVER:-}"
export EMAIL_FROM="${EMAIL_FROM:-cortex-change-mgmt@example.com}"

# Enable PagerDuty for emergencies
export PAGERDUTY_ENABLED="${PAGERDUTY_ENABLED:-false}"
export PAGERDUTY_API_KEY="${PAGERDUTY_API_KEY:-}"

# ============================================================================
# Metrics & Reporting
# ============================================================================

# Enable metrics collection
export METRICS_ENABLED="${METRICS_ENABLED:-true}"

# Metrics backend (prometheus|influxdb|custom)
export METRICS_BACKEND="${METRICS_BACKEND:-prometheus}"

# Prometheus push gateway URL
export PROMETHEUS_PUSHGATEWAY="${PROMETHEUS_PUSHGATEWAY:-http://prometheus-pushgateway:9091}"

# Enable audit logging
export AUDIT_LOGGING="${AUDIT_LOGGING:-true}"

# Audit log retention (days)
export AUDIT_RETENTION_DAYS="${AUDIT_RETENTION_DAYS:-90}"

# ============================================================================
# Integration Settings
# ============================================================================

# CMDB integration
export CMDB_ENABLED="${CMDB_ENABLED:-true}"
export CMDB_PATH="${CMDB_PATH:-${SCRIPT_DIR}/../cmdb}"

# Governance integration
export GOVERNANCE_ENABLED="${GOVERNANCE_ENABLED:-true}"
export GOVERNANCE_PATH="${GOVERNANCE_PATH:-${SCRIPT_DIR}/../../lib/governance}"

# MoE Router integration
export MOE_ROUTER_ENABLED="${MOE_ROUTER_ENABLED:-true}"
export MOE_ROUTER_PATH="${MOE_ROUTER_PATH:-${SCRIPT_DIR}/../masters/coordinator/lib/moe-router.sh}"

# ============================================================================
# Standard Change Models
# ============================================================================

# Worker restart (standard change)
export STD_WORKER_RESTART_ENABLED="${STD_WORKER_RESTART_ENABLED:-true}"
export STD_WORKER_RESTART_MAX_FREQ="${STD_WORKER_RESTART_MAX_FREQ:-3}"  # per hour

# Auto-scaling (standard change)
export STD_AUTOSCALE_ENABLED="${STD_AUTOSCALE_ENABLED:-true}"
export STD_AUTOSCALE_MIN_REPLICAS="${STD_AUTOSCALE_MIN_REPLICAS:-1}"
export STD_AUTOSCALE_MAX_REPLICAS="${STD_AUTOSCALE_MAX_REPLICAS:-10}"

# Security patching (standard change)
export STD_SECURITY_PATCH_ENABLED="${STD_SECURITY_PATCH_ENABLED:-true}"
export STD_SECURITY_PATCH_MAX_SEVERITY="${STD_SECURITY_PATCH_MAX_SEVERITY:-high}"  # low|medium|high (critical requires CAB)

# Configuration updates (standard change)
export STD_CONFIG_UPDATE_ENABLED="${STD_CONFIG_UPDATE_ENABLED:-true}"
export STD_CONFIG_UPDATE_TOLERANCE="${STD_CONFIG_UPDATE_TOLERANCE:-20}"  # percentage deviation allowed

# ============================================================================
# Emergency Change Settings
# ============================================================================

# Enable emergency change process
export EMERGENCY_CHANGE_ENABLED="${EMERGENCY_CHANGE_ENABLED:-true}"

# Emergency change auto-approval (implement first, approve later)
export EMERGENCY_AUTO_APPROVE="${EMERGENCY_AUTO_APPROVE:-true}"

# Emergency CAB review required within (hours)
export EMERGENCY_CAB_REVIEW_SLA="${EMERGENCY_CAB_REVIEW_SLA:-24}"

# ============================================================================
# DevOps Integration
# ============================================================================

# CI/CD auto-change creation
export CICD_AUTO_CHANGE="${CICD_AUTO_CHANGE:-true}"

# Git branch to change category mapping
export GIT_MAIN_CATEGORY="${GIT_MAIN_CATEGORY:-deployment}"
export GIT_DEVELOP_CATEGORY="${GIT_DEVELOP_CATEGORY:-deployment}"
export GIT_HOTFIX_CATEGORY="${GIT_HOTFIX_CATEGORY:-emergency}"
export GIT_FEATURE_CATEGORY="${GIT_FEATURE_CATEGORY:-normal}"

# Kubernetes event integration
export K8S_EVENT_INTEGRATION="${K8S_EVENT_INTEGRATION:-true}"

# ============================================================================
# Feature Flags
# ============================================================================

# AI risk assessment
export AI_RISK_ASSESSMENT="${AI_RISK_ASSESSMENT:-true}"

# ML-based change success prediction
export ML_PREDICTION="${ML_PREDICTION:-true}"

# Automated dependency analysis
export AUTO_DEPENDENCY_ANALYSIS="${AUTO_DEPENDENCY_ANALYSIS:-true}"

# Automated rollback decision
export AUTO_ROLLBACK_DECISION="${AUTO_ROLLBACK_DECISION:-true}"

# Self-healing capabilities
export SELF_HEALING="${SELF_HEALING:-true}"

# ============================================================================
# Load local overrides
# ============================================================================

if [[ -f "${SCRIPT_DIR}/change-config.local.sh" ]]; then
  source "${SCRIPT_DIR}/change-config.local.sh"
fi
