#!/usr/bin/env bash
# MCP Port Forward Script for Claude Desktop
# Forwards all MCP services to localhost ports
# Uses correct API server based on pod location to work around k3s HA proxy issue

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# PID file to track running port-forwards
PID_FILE="$HOME/.mcp-port-forwards.pids"

# Node to API server mapping
declare -A NODE_TO_API=(
    ["k3s-master01"]="https://10.88.145.190:6443"
    ["k3s-master02"]="https://10.88.145.193:6443"
    ["k3s-master03"]="https://10.88.145.196:6443"
    ["k3s-worker01"]="https://10.88.145.190:6443"  # Workers use master01
    ["k3s-worker02"]="https://10.88.145.190:6443"
    ["k3s-worker03"]="https://10.88.145.190:6443"
    ["k3s-worker04"]="https://10.88.145.190:6443"
)

# Port mappings: local_port:namespace:service:remote_port
declare -a SERVICES=(
    "13000:cortex-system:cortex-mcp-server:3000"
    "13001:cortex-system:kubernetes-mcp-server:3001"
    "13002:cortex-system:github-mcp-server:3002"
    "13003:cortex-system:github-security-mcp-server:3003"
    "13004:cortex-system:proxmox-mcp-server:3000"
    "13005:cortex-system:unifi-mcp-server:3000"
    "13006:cortex-system:cloudflare-mcp-server:3000"
    "13007:cortex-system:sandfly-mcp-server:3000"
    "13008:cortex-system:n8n-mcp-server:3002"
    "13009:cortex-system:langflow-chat-mcp-server:3000"
    "13010:cortex-knowledge:mcp-server:3000"
    "13011:cortex:cortex-desktop-mcp:8765"
)

get_pod_node() {
    local namespace=$1
    local service=$2

    # Get the selector from the service
    local selector=$(kubectl get svc -n "$namespace" "$service" -o jsonpath='{.spec.selector}' 2>/dev/null | jq -r 'to_entries | map("\(.key)=\(.value)") | join(",")' 2>/dev/null)

    if [[ -z "$selector" ]]; then
        echo ""
        return
    fi

    # Get the node running the first pod matching the selector
    kubectl get pods -n "$namespace" -l "$selector" -o jsonpath='{.items[0].spec.nodeName}' 2>/dev/null
}

start_forwards() {
    echo -e "${GREEN}Starting MCP port forwards...${NC}"
    echo -e "${CYAN}Using node-aware API server routing to work around k3s HA proxy issue${NC}"
    echo ""

    # Kill any existing forwards
    stop_forwards 2>/dev/null || true

    > "$PID_FILE"

    for service in "${SERVICES[@]}"; do
        IFS=':' read -r local_port namespace svc remote_port <<< "$service"

        printf "  %-35s " "$svc"

        # Check if service exists
        if ! kubectl get svc -n "$namespace" "$svc" &>/dev/null; then
            echo -e "${YELLOW}SKIP (not found)${NC}"
            continue
        fi

        # Find which node the pod is on
        node=$(get_pod_node "$namespace" "$svc")

        if [[ -z "$node" ]]; then
            echo -e "${YELLOW}SKIP (no pods)${NC}"
            continue
        fi

        # Get the appropriate API server
        api_server="${NODE_TO_API[$node]:-https://10.88.145.190:6443}"

        # Start port-forward in background with correct API server
        kubectl --server="$api_server" port-forward -n "$namespace" "svc/$svc" "$local_port:$remote_port" &>/dev/null &
        pid=$!

        # Brief wait to check if it started
        sleep 1
        if kill -0 $pid 2>/dev/null; then
            echo "$pid" >> "$PID_FILE"
            echo -e "${GREEN}OK${NC} (via ${node})"
        else
            echo -e "${RED}FAILED${NC}"
        fi
    done

    echo ""
    echo -e "${GREEN}Port forwards started!${NC}"
    echo "Use '$0 status' to check status"
    echo "Use '$0 stop' to stop all"
}

stop_forwards() {
    echo -e "${YELLOW}Stopping MCP port forwards...${NC}"

    if [[ -f "$PID_FILE" ]]; then
        while read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi

    # Also kill any kubectl port-forward processes for our services
    pkill -f "kubectl.*port-forward.*mcp" 2>/dev/null || true

    echo -e "${GREEN}Stopped.${NC}"
}

status_forwards() {
    echo -e "${GREEN}MCP Port Forward Status:${NC}"
    echo ""
    printf "%-35s %-12s %-10s\n" "SERVICE" "LOCAL PORT" "STATUS"
    printf "%-35s %-12s %-10s\n" "-------" "----------" "------"

    for service in "${SERVICES[@]}"; do
        IFS=':' read -r local_port namespace svc remote_port <<< "$service"

        # Check if port is listening
        if nc -z localhost "$local_port" 2>/dev/null; then
            status="${GREEN}RUNNING${NC}"
        else
            status="${RED}DOWN${NC}"
        fi

        printf "%-35s %-12s " "$svc" "$local_port"
        echo -e "$status"
    done
}

test_forwards() {
    echo -e "${GREEN}Testing MCP SSE endpoints...${NC}"
    echo ""

    for service in "${SERVICES[@]}"; do
        IFS=':' read -r local_port namespace svc remote_port <<< "$service"

        printf "  %-35s " "$svc"

        # Test the SSE endpoint
        response=$(curl -s --max-time 3 "http://localhost:$local_port/sse" 2>&1 | head -c 100)

        if [[ "$response" == *"SSE"* ]] || [[ "$response" == *"event"* ]] || [[ "$response" == *":"* ]]; then
            echo -e "${GREEN}SSE OK${NC}"
        elif [[ "$response" == *"error"* ]] || [[ "$response" == *"Not found"* ]]; then
            echo -e "${YELLOW}HTTP OK (no SSE)${NC}"
        elif nc -z localhost "$local_port" 2>/dev/null; then
            echo -e "${YELLOW}LISTENING${NC}"
        else
            echo -e "${RED}FAILED${NC}"
        fi
    done
}

case "${1:-start}" in
    start)
        start_forwards
        ;;
    stop)
        stop_forwards
        ;;
    status)
        status_forwards
        ;;
    test)
        test_forwards
        ;;
    restart)
        stop_forwards
        sleep 1
        start_forwards
        ;;
    *)
        echo "Usage: $0 {start|stop|status|test|restart}"
        exit 1
        ;;
esac
