#!/bin/bash
# Proxmox API Credentials
# Source this file in master and worker scripts
#
# Usage:
#   source /coordination/config/proxmox-credentials.sh
#
# Last Updated: 2025-12-14

export PROXMOX_TOKEN="root@pam!cortex-k3s-display=7e74841c-0eb1-4181-8926-aaa9f0103c58"
export PROXMOX_HOST="10.88.140.164"
export PROXMOX_PORT="8006"
export PROXMOX_NODE="pve01"

# K3s VM IDs (VLAN 145: 10.88.145.0/24)
export K3S_MASTER_VMID="300"
export K3S_MASTER_IP="10.88.145.190"

export K3S_WORKER1_VMID="301"
export K3S_WORKER1_IP="10.88.145.191"

export K3S_WORKER2_VMID="302"
export K3S_WORKER2_IP="10.88.145.192"

# API Base URL
export PROXMOX_API_BASE="https://${PROXMOX_HOST}:${PROXMOX_PORT}/api2/json"

# Verify credentials loaded
if [ -n "$PROXMOX_TOKEN" ]; then
    echo "[Proxmox] Credentials loaded: ${PROXMOX_TOKEN:0:30}..." >&2
fi
