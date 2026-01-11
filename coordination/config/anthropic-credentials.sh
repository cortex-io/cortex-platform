#!/bin/bash
# Anthropic Claude API Credentials
# Source this file in master and worker scripts
#
# Usage:
#   source /coordination/config/anthropic-credentials.sh
#
# Last Updated: 2025-12-13 (updated after LXC → VM migration)

export ANTHROPIC_API_KEY="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"
export ANTHROPIC_API_URL="https://api.anthropic.com/v1"
export ANTHROPIC_MODEL="claude-sonnet-4-5-20250929"

# Token budget limits (per master, per day)
export ANTHROPIC_DAILY_TOKEN_BUDGET="1000000"

# Verify credentials loaded
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "[Anthropic] Credentials loaded: ${ANTHROPIC_API_KEY:0:20}..." >&2
fi
