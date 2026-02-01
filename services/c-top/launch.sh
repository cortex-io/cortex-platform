#!/bin/bash
# c-top Launcher - Cortex Operations Dashboard

# Check if c-top is installed
if ! command -v c-top &> /dev/null; then
    echo "c-top not found, installing..."
    cd "$(dirname "$0")"
    pip install -e .
fi

# Launch c-top
exec c-top
