#!/bin/bash
# Master Deployment Script for Proxmox MCP Server
# Orchestrates the complete deployment pipeline with safety checks

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_MODE="${1:-full}"  # full, build-only, deploy-only, test-only

# Display banner
clear
echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║    Proxmox MCP Server - Complete Deployment Pipeline         ║
║                                                               ║
║    Cortex Holdings - Infrastructure Automation               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${BLUE}Deployment Mode: $DEPLOYMENT_MODE${NC}"
echo -e "${BLUE}Script Directory: $SCRIPT_DIR${NC}"
echo ""

# Check script dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq not found (optional)${NC}"
fi

echo -e "${GREEN}Dependencies OK${NC}"
echo ""

# Pre-deployment checks
echo -e "${YELLOW}Running pre-deployment checks...${NC}"

# Check k8s connection
if ! kubectl get nodes &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi

# Check namespace
if ! kubectl get namespace cortex-system &> /dev/null; then
    echo -e "${RED}Error: Namespace cortex-system not found${NC}"
    exit 1
fi

# Check current deployment
if kubectl get deployment proxmox-mcp-server -n cortex-system &> /dev/null; then
    echo -e "${GREEN}Current deployment found${NC}"
    CURRENT_IMAGE=$(kubectl get deployment proxmox-mcp-server -n cortex-system -o jsonpath='{.spec.template.spec.containers[0].image}')
    echo -e "${BLUE}Current Image: $CURRENT_IMAGE${NC}"
else
    echo -e "${YELLOW}No existing deployment found${NC}"
fi

echo ""

# Function: Build phase
run_build() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                     BUILD PHASE                               ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ ! -f "$SCRIPT_DIR/scripts/build-proxmox-mcp.sh" ]; then
        echo -e "${RED}Error: Build script not found${NC}"
        return 1
    fi

    if "$SCRIPT_DIR/scripts/build-proxmox-mcp.sh"; then
        echo -e "${GREEN}Build phase completed successfully${NC}"
        return 0
    else
        echo -e "${RED}Build phase failed${NC}"
        return 1
    fi
}

# Function: Deploy phase
run_deploy() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    DEPLOY PHASE                               ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ ! -f "$SCRIPT_DIR/scripts/deploy-proxmox-mcp.sh" ]; then
        echo -e "${RED}Error: Deploy script not found${NC}"
        return 1
    fi

    if "$SCRIPT_DIR/scripts/deploy-proxmox-mcp.sh"; then
        echo -e "${GREEN}Deploy phase completed successfully${NC}"
        return 0
    else
        echo -e "${RED}Deploy phase failed${NC}"
        return 1
    fi
}

# Function: Verify phase
run_verify() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    VERIFY PHASE                               ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ ! -f "$SCRIPT_DIR/scripts/verify-proxmox-mcp.sh" ]; then
        echo -e "${RED}Error: Verify script not found${NC}"
        return 1
    fi

    if "$SCRIPT_DIR/scripts/verify-proxmox-mcp.sh"; then
        echo -e "${GREEN}Verify phase completed successfully${NC}"
        return 0
    else
        echo -e "${RED}Verify phase failed${NC}"
        return 1
    fi
}

# Function: Integration test phase
run_integration_tests() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                INTEGRATION TEST PHASE                         ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ ! -f "$SCRIPT_DIR/scripts/test-proxmox-integration.sh" ]; then
        echo -e "${RED}Error: Integration test script not found${NC}"
        return 1
    fi

    if "$SCRIPT_DIR/scripts/test-proxmox-integration.sh"; then
        echo -e "${GREEN}Integration test phase completed successfully${NC}"
        return 0
    else
        echo -e "${RED}Integration test phase failed${NC}"
        return 1
    fi
}

# Function: Rollback
run_rollback() {
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                    ROLLBACK INITIATED                         ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ -f "$SCRIPT_DIR/scripts/rollback-proxmox-mcp.sh" ]; then
        "$SCRIPT_DIR/scripts/rollback-proxmox-mcp.sh"
    else
        echo -e "${RED}Error: Rollback script not found${NC}"
        echo "Manual rollback required:"
        echo "  kubectl rollout undo deployment/proxmox-mcp-server -n cortex-system"
    fi
}

# Main deployment pipeline
case "$DEPLOYMENT_MODE" in
    full)
        echo -e "${YELLOW}Running FULL deployment pipeline...${NC}"
        echo ""

        # Phase 1: Build
        if ! run_build; then
            echo -e "${RED}Pipeline failed at BUILD phase${NC}"
            exit 1
        fi

        echo ""
        sleep 2

        # Phase 2: Deploy
        if ! run_deploy; then
            echo -e "${RED}Pipeline failed at DEPLOY phase${NC}"
            echo -e "${YELLOW}Build completed but deployment failed${NC}"
            exit 1
        fi

        echo ""
        sleep 2

        # Phase 3: Verify
        if ! run_verify; then
            echo -e "${RED}Pipeline failed at VERIFY phase${NC}"
            echo -e "${YELLOW}Deployment completed but verification failed${NC}"
            echo ""
            read -p "Rollback deployment? (yes/no): " -r
            if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                run_rollback
            fi
            exit 1
        fi

        echo ""
        sleep 2

        # Phase 4: Integration Tests
        if ! run_integration_tests; then
            echo -e "${RED}Pipeline failed at INTEGRATION TEST phase${NC}"
            echo -e "${YELLOW}Deployment verified but integration tests failed${NC}"
            echo ""
            read -p "Rollback deployment? (yes/no): " -r
            if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                run_rollback
            fi
            exit 1
        fi

        ;;

    build-only)
        echo -e "${YELLOW}Running BUILD ONLY...${NC}"
        echo ""
        if ! run_build; then
            exit 1
        fi
        ;;

    deploy-only)
        echo -e "${YELLOW}Running DEPLOY ONLY (using existing image)...${NC}"
        echo ""
        if ! run_deploy; then
            exit 1
        fi
        if ! run_verify; then
            echo -e "${YELLOW}Deployment completed but verification failed${NC}"
        fi
        ;;

    test-only)
        echo -e "${YELLOW}Running TESTS ONLY...${NC}"
        echo ""
        if ! run_verify; then
            exit 1
        fi
        if ! run_integration_tests; then
            exit 1
        fi
        ;;

    *)
        echo -e "${RED}Invalid deployment mode: $DEPLOYMENT_MODE${NC}"
        echo ""
        echo "Usage: $0 [mode]"
        echo ""
        echo "Modes:"
        echo "  full         - Complete pipeline (build, deploy, verify, test) [default]"
        echo "  build-only   - Build image only"
        echo "  deploy-only  - Deploy existing image"
        echo "  test-only    - Run verification and integration tests"
        echo ""
        exit 1
        ;;
esac

# Success banner
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}║           DEPLOYMENT PIPELINE COMPLETED SUCCESSFULLY          ║${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Display deployment info
echo -e "${CYAN}Deployment Information:${NC}"
POD_NAME=$(kubectl get pods -n cortex-system -l app=proxmox-mcp-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "N/A")
POD_STATUS=$(kubectl get pod "$POD_NAME" -n cortex-system -o jsonpath='{.status.phase}' 2>/dev/null || echo "N/A")
POD_IMAGE=$(kubectl get pod "$POD_NAME" -n cortex-system -o jsonpath='{.spec.containers[0].image}' 2>/dev/null || echo "N/A")

echo "  Pod Name: $POD_NAME"
echo "  Pod Status: $POD_STATUS"
echo "  Image: $POD_IMAGE"
echo ""

echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Monitor logs: kubectl logs -n cortex-system $POD_NAME -f"
echo "  2. Test from Cortex Chat interface"
echo "  3. Monitor for 24 hours"
echo "  4. Update documentation"
echo ""

echo -e "${CYAN}Useful Commands:${NC}"
echo "  - View logs:     kubectl logs -n cortex-system $POD_NAME -f"
echo "  - Get status:    kubectl get pod $POD_NAME -n cortex-system"
echo "  - Exec into pod: kubectl exec -it -n cortex-system $POD_NAME -- /bin/bash"
echo "  - Rollback:      $SCRIPT_DIR/scripts/rollback-proxmox-mcp.sh"
echo ""

echo -e "${GREEN}Deployment completed at: $(date)${NC}"
echo ""
