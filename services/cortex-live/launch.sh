#!/bin/bash
# Cortex Live Launcher

# Check if cortex-live is installed
if ! command -v cortex-live &> /dev/null; then
    echo "cortex-live not found, installing..."
    cd "$(dirname "$0")"
    pipx install -e .
fi

# Launch cortex-live
exec cortex-live
