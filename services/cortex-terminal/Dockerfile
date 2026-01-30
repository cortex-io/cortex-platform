# Cortex Terminal
# Claude Code + tmux + Cortex Live in a K3s pod, accessible via Tailscale

FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/ry-ops/cortex-platform"
LABEL org.opencontainers.image.description="Cortex Terminal - Claude Code + tmux for remote access"
LABEL org.opencontainers.image.licenses="MIT"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    tmux \
    openssh-server \
    vim \
    less \
    jq \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Cortex Live TUI dependencies (optional - install at runtime if needed)
# To install: pip install git+https://github.com/ry-ops/cortex-platform.git#subdirectory=services/cortex-live
RUN pip install --no-cache-dir textual kubernetes prometheus-api-client || true

# Create cortex user
RUN useradd -m -s /bin/bash -u 1000 cortex \
    && mkdir -p /home/cortex/.config/claude-code \
    && mkdir -p /home/cortex/.ssh \
    && chown -R cortex:cortex /home/cortex

# Configure SSH (for Tailscale SSH or direct access)
RUN mkdir -p /var/run/sshd \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Configure tmux for mouse support
COPY <<'EOF' /home/cortex/.tmux.conf
# Enable mouse support
set -g mouse on

# Increase history
set -g history-limit 50000

# Status bar styling (amber theme to match Cortex Live)
set -g status-style 'bg=#1a1a1a fg=#ffb000'
set -g status-left '#[fg=#ffb000,bold][CORTEX] '
set -g status-right '#[fg=#cc8800]%Y-%m-%d %H:%M '

# Pane borders
set -g pane-border-style 'fg=#333333'
set -g pane-active-border-style 'fg=#ffb000'

# Window status
set -g window-status-current-style 'fg=#ffb000 bold'
set -g window-status-style 'fg=#666666'

# Activity monitoring
setw -g monitor-activity on
set -g visual-activity off

# Start windows and panes at 1, not 0
set -g base-index 1
setw -g pane-base-index 1

# Reload config
bind r source-file ~/.tmux.conf \; display "Config reloaded"

# Split panes using | and -
bind | split-window -h
bind - split-window -v

# Save session state on detach
set-hook -g client-detached 'run-shell "echo $(date -Iseconds) detached >> ~/.tmux-session.log"'
EOF

# Configure Claude Code MCP servers
COPY <<'EOF' /home/cortex/.config/claude-code/config.json
{
  "mcpServers": {
    "cortex-unified": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://cortex-unified-mcp.cortex-system:3000"],
      "env": {}
    }
  },
  "model": "claude-sonnet-4-20250514",
  "maxTurns": 25,
  "dangerouslyAllowAllTools": false
}
EOF

# Entrypoint script
COPY <<'ENTRYPOINT' /entrypoint.sh
#!/bin/bash
set -e

# Start SSH daemon if enabled
if [ "${ENABLE_SSH:-false}" = "true" ]; then
    echo "Starting SSH daemon..."
    /usr/sbin/sshd -D &
fi

# Set Anthropic API key from secret (mounted as env or file)
if [ -f /secrets/anthropic-api-key ]; then
    export ANTHROPIC_API_KEY=$(cat /secrets/anthropic-api-key)
fi

# Create default tmux session for cortex user
su - cortex -c "
    # Start tmux server
    tmux start-server

    # Create main session if it doesn't exist
    if ! tmux has-session -t cortex 2>/dev/null; then
        echo 'Creating new tmux session: cortex'
        tmux new-session -d -s cortex -n 'claude'

        # Initial context injection prompt
        tmux send-keys -t cortex:claude 'echo \"Welcome to Cortex Terminal\"' Enter
        tmux send-keys -t cortex:claude 'echo \"Run: claude to start Claude Code\"' Enter
        tmux send-keys -t cortex:claude 'echo \"First command: Use cortex_context_inject to see cluster state\"' Enter
        tmux send-keys -t cortex:claude '' Enter
    fi
"

echo "Cortex Terminal ready"
echo "  - SSH: ${ENABLE_SSH:-false}"
echo "  - User: cortex"
echo "  - tmux session: cortex"

# Keep container running
if [ "${ENABLE_SSH:-false}" = "true" ]; then
    wait
else
    # Just sleep, user will exec into the pod
    while true; do
        sleep 3600
    done
fi
ENTRYPOINT

RUN chmod +x /entrypoint.sh \
    && chown -R cortex:cortex /home/cortex

# Set working directory
WORKDIR /home/cortex

# Environment
ENV TERM=xterm-256color
ENV PYTHONUNBUFFERED=1

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
