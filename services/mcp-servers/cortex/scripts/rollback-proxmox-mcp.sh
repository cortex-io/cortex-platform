#!/bin/bash
# Rollback Proxmox MCP Server Deployment
# Provides multiple rollback strategies for different scenarios

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="cortex-system"
DEPLOYMENT="proxmox-mcp-server"

# Parse arguments
ROLLBACK_TYPE="${1:-auto}"  # auto, revision, backup
REVISION="${2:-}"

echo -e "${RED}=== Proxmox MCP Server Rollback ===${NC}"
echo "Namespace: $NAMESPACE"
echo "Deployment: $DEPLOYMENT"
echo "Rollback Type: $ROLLBACK_TYPE"
echo ""

# Check deployment exists
if ! kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" &> /dev/null; then
    echo -e "${RED}Error: Deployment $DEPLOYMENT not found${NC}"
    exit 1
fi

# Function: Automatic rollback (to previous revision)
rollback_auto() {
    echo -e "${YELLOW}Performing automatic rollback to previous revision...${NC}"
    echo ""

    # Get current revision
    CURRENT_REV=$(kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE" | tail -1 | awk '{print $1}')
    echo "Current revision: $CURRENT_REV"

    # Perform rollback
    if kubectl rollout undo deployment/"$DEPLOYMENT" -n "$NAMESPACE"; then
        echo -e "${GREEN}Rollback initiated${NC}"

        # Monitor rollback
        echo ""
        echo -e "${YELLOW}Monitoring rollback...${NC}"
        if kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s; then
            echo ""
            echo -e "${GREEN}Rollback completed successfully${NC}"

            # Get new revision
            NEW_REV=$(kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE" | tail -1 | awk '{print $1}')
            echo "Rolled back to revision: $NEW_REV"
        else
            echo -e "${RED}Rollback failed or timed out${NC}"
            return 1
        fi
    else
        echo -e "${RED}Failed to initiate rollback${NC}"
        return 1
    fi
}

# Function: Rollback to specific revision
rollback_revision() {
    local target_rev="$1"

    if [ -z "$target_rev" ]; then
        echo -e "${RED}Error: No revision specified${NC}"
        echo "Usage: $0 revision <revision_number>"
        echo ""
        echo "Available revisions:"
        kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE"
        return 1
    fi

    echo -e "${YELLOW}Rolling back to revision $target_rev...${NC}"
    echo ""

    if kubectl rollout undo deployment/"$DEPLOYMENT" -n "$NAMESPACE" --to-revision="$target_rev"; then
        echo -e "${GREEN}Rollback to revision $target_rev initiated${NC}"

        # Monitor rollback
        echo ""
        echo -e "${YELLOW}Monitoring rollback...${NC}"
        if kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s; then
            echo ""
            echo -e "${GREEN}Rollback completed successfully${NC}"
        else
            echo -e "${RED}Rollback failed or timed out${NC}"
            return 1
        fi
    else
        echo -e "${RED}Failed to rollback to revision $target_rev${NC}"
        return 1
    fi
}

# Function: Rollback from backup file
rollback_backup() {
    echo -e "${YELLOW}Looking for backup files...${NC}"
    echo ""

    # Find most recent backup
    BACKUP_FILE=$(ls -t /tmp/${DEPLOYMENT}-backup-*.yaml 2>/dev/null | head -1 || echo "")

    if [ -z "$BACKUP_FILE" ]; then
        echo -e "${RED}Error: No backup files found in /tmp/${NC}"
        echo "Backup files should match pattern: /tmp/${DEPLOYMENT}-backup-*.yaml"
        return 1
    fi

    echo "Found backup: $BACKUP_FILE"
    echo ""

    # Ask for confirmation
    echo -e "${YELLOW}This will restore deployment from backup file.${NC}"
    read -p "Continue? (yes/no): " -r
    echo

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Rollback cancelled"
        return 1
    fi

    # Apply backup
    echo -e "${YELLOW}Applying backup...${NC}"
    if kubectl apply -f "$BACKUP_FILE"; then
        echo -e "${GREEN}Backup applied successfully${NC}"

        # Monitor rollout
        echo ""
        echo -e "${YELLOW}Monitoring rollout...${NC}"
        if kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s; then
            echo ""
            echo -e "${GREEN}Rollback from backup completed successfully${NC}"
        else
            echo -e "${RED}Rollback failed or timed out${NC}"
            return 1
        fi
    else
        echo -e "${RED}Failed to apply backup${NC}"
        return 1
    fi
}

# Function: Emergency rollback (scale down)
rollback_emergency() {
    echo -e "${RED}EMERGENCY ROLLBACK: Scaling down deployment${NC}"
    echo ""

    # Scale down to 0
    echo "Scaling down to 0 replicas..."
    kubectl scale deployment/"$DEPLOYMENT" -n "$NAMESPACE" --replicas=0

    sleep 5

    echo ""
    echo -e "${YELLOW}Deployment scaled down.${NC}"
    echo ""
    echo "To restore with previous working version:"
    echo "  1. Fix the issue (code, config, etc.)"
    echo "  2. Rebuild image: ./scripts/build-proxmox-mcp.sh"
    echo "  3. Scale up: kubectl scale deployment/$DEPLOYMENT -n $NAMESPACE --replicas=1"
    echo ""
    echo "Or use backup restore:"
    echo "  ./scripts/rollback-proxmox-mcp.sh backup"
}

# Main rollback logic
case "$ROLLBACK_TYPE" in
    auto)
        rollback_auto
        ;;
    revision)
        rollback_revision "$REVISION"
        ;;
    backup)
        rollback_backup
        ;;
    emergency)
        rollback_emergency
        ;;
    *)
        echo -e "${RED}Error: Invalid rollback type${NC}"
        echo ""
        echo "Usage: $0 [TYPE] [REVISION]"
        echo ""
        echo "Types:"
        echo "  auto      - Rollback to previous revision (default)"
        echo "  revision  - Rollback to specific revision (requires REVISION number)"
        echo "  backup    - Restore from backup file"
        echo "  emergency - Scale down deployment immediately"
        echo ""
        echo "Examples:"
        echo "  $0                    # Auto rollback to previous"
        echo "  $0 revision 5         # Rollback to revision 5"
        echo "  $0 backup             # Restore from backup file"
        echo "  $0 emergency          # Emergency scale down"
        echo ""
        echo "View revision history:"
        echo "  kubectl rollout history deployment/$DEPLOYMENT -n $NAMESPACE"
        exit 1
        ;;
esac

# Post-rollback verification
if [ "$ROLLBACK_TYPE" != "emergency" ]; then
    echo ""
    echo -e "${YELLOW}Running post-rollback verification...${NC}"
    sleep 5

    # Get pod info
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -n "$POD_NAME" ]; then
        POD_STATUS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        echo "Pod: $POD_NAME"
        echo "Status: $POD_STATUS"
        echo ""

        # Check for errors
        ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=30 2>&1 | grep -i "error\|exception" | grep -v "no error" | wc -l || echo "0")

        if [ "$ERROR_COUNT" -eq 0 ]; then
            echo -e "${GREEN}No errors in logs${NC}"
        else
            echo -e "${YELLOW}Warning: $ERROR_COUNT error(s) found in logs${NC}"
            kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=10
        fi
    else
        echo -e "${YELLOW}No pods found (yet)${NC}"
    fi

    echo ""
    echo -e "${GREEN}=== Rollback Complete ===${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Verify rollback: ./scripts/verify-proxmox-mcp.sh"
    echo "  2. Check logs: kubectl logs -n $NAMESPACE deployment/$DEPLOYMENT -f"
    echo "  3. Review what went wrong and fix before next deployment"
fi
