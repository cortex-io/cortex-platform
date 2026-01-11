#!/bin/bash
#
# Sandfly Mission - Phase 1 & 3 Worker Launcher
# Development Master: Parallel Worker Execution
#

set -e

WORKERS_DIR="/Users/ryandahlberg/Projects/cortex/coordination/workers"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║   SANDFLY MCP INTEGRATION - DEVELOPMENT MASTER              ║
║   Phase 1 & 3: Parallel Worker Execution                   ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${GREEN}Launching 2 Daryl workers in parallel...${NC}\n"

echo -e "${YELLOW}Worker 1: Sandfly MCP K8s Deployment${NC}"
echo "  Worker ID: daryl-sandfly-k8s-001"
echo "  Task: task-sandfly-integration-001"
echo "  Directory: $WORKERS_DIR/daryl-sandfly-k8s-001"
echo ""

echo -e "${YELLOW}Worker 2: Context Persistence Fix${NC}"
echo "  Worker ID: daryl-context-fix-002"
echo "  Task: task-context-persistence-003"
echo "  Directory: $WORKERS_DIR/daryl-context-fix-002"
echo ""

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}\n"

echo "To launch workers, open 2 terminals and run:"
echo ""
echo -e "${GREEN}# Terminal 1 - Daryl-1 (Sandfly K8s)${NC}"
cat << 'EOF'
cd /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001
claude chat "You are Daryl, worker ID: daryl-sandfly-k8s-001

Read your mission brief: /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001/WORKER_BRIEF.md

Execute the Sandfly MCP K8s deployment. GOVERNANCE_BYPASS=true. Start by reading the WORKER_BRIEF.md file."
EOF

echo ""
echo -e "${GREEN}# Terminal 2 - Daryl-2 (Context Fix)${NC}"
cat << 'EOF'
cd /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002
claude chat "You are Daryl, worker ID: daryl-context-fix-002

Read your mission brief: /Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002/WORKER_BRIEF.md

Execute the conversation context persistence fix. GOVERNANCE_BYPASS=true. Start by reading the WORKER_BRIEF.md file."
EOF

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}\n"

echo "Monitor progress:"
echo "  watch -n 10 'jq \".status\" $WORKERS_DIR/daryl-*/worker-spec.json'"
echo ""

echo -e "${YELLOW}When both workers complete, report back for Phase 2 & 4!${NC}\n"
