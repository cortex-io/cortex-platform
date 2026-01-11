#!/bin/bash
# Example: YouTube Ingestion Bug Fix with Change Management
# This demonstrates how today's actual bug fix would flow through ITIL change management

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CM_DIR="$(dirname "$SCRIPT_DIR")"

source "${CM_DIR}/integrations/cortex-integration.sh"

echo "==================================================================="
echo "Cortex Change Management - Real-World Example"
echo "YouTube Ingestion [object Object] Bug Fix"
echo "==================================================================="
echo ""

# ============================================================================
# Scenario: Production Bug Detected
# ============================================================================

echo "STEP 1: Production Bug Detected"
echo "-------------------------------------------------------------------"
echo "Error Detection System found [object Object] in YouTube analysis"
echo "Severity: HIGH (user-facing bug)"
echo "Impact: All YouTube video analyses display incorrectly"
echo ""

# ============================================================================
# STEP 2: Create Emergency RFC
# ============================================================================

echo "STEP 2: Creating Emergency RFC"
echo "-------------------------------------------------------------------"

CHANGE_ID=$(integrate_youtube_ingestion emergency_fix '{
  "bug": "YouTube improvement descriptions showing [object Object]",
  "root_cause": "Object serialization error in youtube-workflow.ts:154",
  "fix": "Extract description field from actionable items objects",
  "files_changed": [
    "backend-simple/src/services/youtube-workflow.ts",
    "backend-simple/src/services/error-recovery.ts"
  ],
  "testing": "Reprocess existing video with corrected code",
  "rollback_plan": "Revert to previous image tag"
}')

echo "RFC Created: $CHANGE_ID"
echo ""

sleep 2

# ============================================================================
# STEP 3: Automatic Risk Assessment
# ============================================================================

echo "STEP 3: Automatic Risk Assessment"
echo "-------------------------------------------------------------------"

# The assess_change was already called in integrate_youtube_ingestion
# Let's show the results

"${CM_DIR}/change-manager.sh" show "$CHANGE_ID" | jq '{
  change_id,
  type,
  category,
  priority,
  risk_score,
  approval_required,
  assigned_to,
  state
}'

echo ""

sleep 2

# ============================================================================
# STEP 4: Emergency CAB Approval
# ============================================================================

echo "STEP 4: Emergency CAB Approval (Auto-Approved for Emergency)"
echo "-------------------------------------------------------------------"
echo "Emergency changes are pre-approved and implemented immediately"
echo "Retrospective review required within 24 hours"
echo ""

# Already approved in integrate_youtube_ingestion
# Show approval in audit trail

"${CM_DIR}/change-manager.sh" show "$CHANGE_ID" | jq -r '.audit_trail[] | "\(.timestamp) | \(.action) | \(.actor) | \(.details)"'

echo ""

sleep 2

# ============================================================================
# STEP 5: Implementation
# ============================================================================

echo "STEP 5: Implementation"
echo "-------------------------------------------------------------------"
echo "1. Fix code bug (youtube-workflow.ts)"
echo "2. Implement error recovery system (error-recovery.ts)"
echo "3. Build new container image"
echo "4. Deploy with zero downtime"
echo "5. Reprocess affected conversation"
echo ""

# Simulate implementation
echo "Building container image..."
sleep 1
echo "✓ Build complete: cortex-chat-backend-simple:latest"
echo ""

echo "Deploying to Kubernetes..."
sleep 1
echo "✓ Deployment rolled out successfully"
echo ""

echo "Running post-deployment validation..."
sleep 1
echo "✓ All health checks passed"
echo "✓ Error detection system verified"
echo "✓ User conversation reprocessed with correct data"
echo ""

# Update change to implemented
"${CM_DIR}/change-manager.sh" show "$CHANGE_ID" > /dev/null  # Already in implemented state

sleep 2

# ============================================================================
# STEP 6: Monitoring & Validation
# ============================================================================

echo "STEP 6: Post-Implementation Monitoring"
echo "-------------------------------------------------------------------"
echo "Monitoring Period: 30 minutes"
echo "Health Checks: Every 60 seconds"
echo ""

echo "Validation Results:"
echo "  ✓ Error rate: 0% (threshold: <5%)"
echo "  ✓ Response time: 250ms (baseline: 240ms, threshold: <480ms)"
echo "  ✓ User conversation updated successfully"
echo "  ✓ No new errors detected"
echo "  ✓ Improvement descriptions now showing correctly"
echo ""

sleep 2

# ============================================================================
# STEP 7: Close Change
# ============================================================================

echo "STEP 7: Closing Change Request"
echo "-------------------------------------------------------------------"

"${CM_DIR}/change-manager.sh" close "$CHANGE_ID" "successful" "Emergency fix deployed successfully. Bug resolved, error recovery system implemented, user experience restored."

echo "Change $CHANGE_ID closed successfully"
echo ""

# Show final state
"${CM_DIR}/change-manager.sh" show "$CHANGE_ID" | jq '{
  change_id,
  state,
  closure_status,
  closure_notes,
  metrics
}'

echo ""

sleep 2

# ============================================================================
# STEP 8: Metrics & Reporting
# ============================================================================

echo "STEP 8: Change Metrics"
echo "-------------------------------------------------------------------"

"${CM_DIR}/change-manager.sh" metrics today

echo ""

# ============================================================================
# STEP 9: Post-Implementation Review (PIR)
# ============================================================================

echo "STEP 9: Post-Implementation Review"
echo "-------------------------------------------------------------------"
echo "Emergency CAB Review scheduled for: Tomorrow 10 AM"
echo ""
echo "Review Topics:"
echo "  1. Root cause analysis"
echo "  2. Detection time analysis"
echo "  3. Implementation effectiveness"
echo "  4. Preventive measures"
echo "  5. Process improvements"
echo ""

cat <<EOF
Post-Implementation Review Notes:
==================================

What Went Well:
---------------
✓ Error detection system caught the bug automatically
✓ Emergency change process enabled rapid response
✓ Zero downtime deployment
✓ User was transparently notified of issue and fix
✓ Automated reprocessing delivered corrected results
✓ Comprehensive audit trail maintained

What Could Be Improved:
-----------------------
• Implement pre-deployment validation to catch serialization errors
• Add automated tests for object-to-string conversions
• Enhance CI/CD pipeline with better type checking
• Consider staged rollouts for backend changes

Preventive Actions:
-------------------
1. Add lint rule to detect object serialization issues
2. Implement comprehensive integration tests for workflows
3. Add monitoring for [object Object] patterns in outputs
4. Create standard change model for error recovery deployments

Compliance Check:
-----------------
✓ SOC2: Complete audit trail maintained
✓ Segregation of duties: Development created, CAB approved
✓ Rollback plan: Container image revert available
✓ Documentation: All changes documented in Git and CMDB

ITIL Metrics:
-------------
- MTTA (Mean Time to Approve): 5 minutes (emergency fast-track)
- MTTI (Mean Time to Implement): 25 minutes
- MTTR (Mean Time to Restore): 30 minutes
- Success Rate: 100%
- Rollback Required: No

Lessons Learned:
----------------
The auto-recovery system implemented as part of this fix demonstrates
the value of self-healing capabilities. By detecting errors and
automatically correcting them, we transformed a potential service
degradation into a transparent user experience improvement.

This change validates our ITIL change management approach:
- Structured process enabled rapid emergency response
- Automation reduced manual overhead
- Transparency built user trust
- Audit trail ensures compliance

Next Steps:
-----------
1. Apply error detection patterns to other workflows
2. Expand standard change models based on this success
3. Share learnings with team in next CAB meeting
4. Update runbooks with emergency change procedures

Approval:
---------
PIR Completed By: Cortex Change Manager
Date: $(date +%Y-%m-%d)
CAB Sign-Off: Pending (2025-12-31 10:00 AM)

EOF

echo ""

# ============================================================================
# Summary
# ============================================================================

echo "==================================================================="
echo "Change Management Summary"
echo "==================================================================="
echo ""
echo "This example demonstrated a complete ITIL change management lifecycle:"
echo ""
echo "  RFC Creation → Risk Assessment → Approval → Implementation"
echo "    → Monitoring → Validation → Closure → Review"
echo ""
echo "Key ITIL Principles Applied:"
echo "  • Standardized change process"
echo "  • Risk-based assessment and routing"
echo "  • Emergency change procedures"
echo "  • Automated approvals for low-risk changes"
echo "  • Complete audit trail"
echo "  • Post-implementation review"
echo "  • Continuous improvement"
echo ""
echo "Result: Production bug fixed in 30 minutes with full compliance"
echo "==================================================================="
