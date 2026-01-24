#!/bin/bash
#
# Cortex Bridge Installation Script
# Sets up the local bridge for Claude Desktop integration
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$(dirname "$SCRIPT_DIR")"
BRIDGE_DIR="$PLATFORM_DIR/services/cortex-bridge"
VENV_DIR="$BRIDGE_DIR/.venv"

echo "=== Cortex Bridge Installation ==="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Created venv at $VENV_DIR"
else
    echo "Using existing venv at $VENV_DIR"
fi

# Activate and install dependencies
source "$VENV_DIR/bin/activate"
echo "Installing Python dependencies..."
pip install -q websockets watchdog

# Verify bridge script
if [ ! -f "$BRIDGE_DIR/main.py" ]; then
    echo "Error: Bridge script not found at $BRIDGE_DIR/main.py"
    exit 1
fi

echo "Bridge script found at: $BRIDGE_DIR/main.py"

# Configure Claude Desktop
echo ""
echo "=== Claude Desktop Configuration ==="
echo ""

CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
CLAUDE_CONFIG_FILE="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

# Create config directory if needed
mkdir -p "$CLAUDE_CONFIG_DIR"

# Use Python from the venv
VENV_PYTHON="$VENV_DIR/bin/python"

# Check if config exists
if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    echo "Existing Claude Desktop config found."
    echo ""
    echo "To add Cortex Fabric, merge this into your config:"
    echo ""
    cat <<EOF
{
  "mcpServers": {
    "cortex-fabric": {
      "command": "$VENV_PYTHON",
      "args": [
        "$BRIDGE_DIR/main.py",
        "--mcp-stdio"
      ],
      "env": {
        "FABRIC_URL": "ws://10.88.145.190:30080/ws/fabric",
        "CLIENT_TYPE": "desktop",
        "CORTEX_PLATFORM_PATH": "$PLATFORM_DIR",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
EOF
else
    echo "Creating Claude Desktop config..."
    cat > "$CLAUDE_CONFIG_FILE" <<EOF
{
  "mcpServers": {
    "cortex-fabric": {
      "command": "$VENV_PYTHON",
      "args": [
        "$BRIDGE_DIR/main.py",
        "--mcp-stdio"
      ],
      "env": {
        "FABRIC_URL": "ws://10.88.145.190:30080/ws/fabric",
        "CLIENT_TYPE": "desktop",
        "CORTEX_PLATFORM_PATH": "$PLATFORM_DIR",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
EOF
    echo "Config created at: $CLAUDE_CONFIG_FILE"
fi

echo ""
echo "=== Testing Connection ==="
echo ""

# Test connection
echo "Testing connection to Fabric Gateway..."
if curl -s -o /dev/null -w "%{http_code}" "http://10.88.145.190:30080/health" | grep -q "200"; then
    echo "✓ Fabric Gateway is reachable"
else
    echo "✗ Fabric Gateway not reachable yet (may need to deploy first)"
    echo ""
    echo "To deploy the Fabric Gateway, push to cortex-gitops and wait for ArgoCD sync,"
    echo "or run: kubectl apply -f $PLATFORM_DIR/../cortex-gitops/apps/cortex-system/fabric-gateway-deployment.yaml"
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Usage:"
echo ""
echo "  1. Restart Claude Desktop to pick up the new MCP server"
echo ""
echo "  2. In Claude Desktop, you can now use:"
echo "     - fabric_status - Check connection status"
echo "     - fabric_infrastructure - View k3s state"
echo "     - mcp_call - Call any MCP server through the fabric"
echo ""
echo "  3. To run the bridge standalone (for testing):"
echo "     python3 $BRIDGE_DIR/main.py"
echo ""
echo "  4. To use local port-forward instead of public endpoint:"
echo "     python3 $BRIDGE_DIR/main.py --local"
echo "     (requires: kubectl port-forward svc/fabric-gateway 8080:8080 -n cortex-system)"
echo ""
