#!/bin/bash

################################################################################
# Documentation Master MoE Learner Integration
#
# Connects to the MoE learning system to track documentation usage and
# continuously improve based on outcomes.
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$(dirname "${SCRIPT_DIR}")"
WORKERS_DIR="${MASTER_DIR}/workers"

################################################################################
# Main
################################################################################

main() {
    local command="${1:-register}"
    shift || true

    # Delegate to learner worker
    "${WORKERS_DIR}/learner-worker.sh" "${command}" "$@"
}

main "$@"
