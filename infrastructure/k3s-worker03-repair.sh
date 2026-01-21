#!/bin/bash
# =============================================================================
# k3s-worker03 DNS Repair Script
# =============================================================================
#
# This script diagnoses and repairs DNS issues on k3s-worker03
#
# Run this on k3s-worker03 directly via SSH:
#   ssh k3s-worker03 'bash -s' < k3s-worker03-repair.sh
#
# =============================================================================

set -e

echo "=== k3s-worker03 DNS Diagnostic and Repair Script ==="
echo "Running at: $(date)"
echo "Hostname: $(hostname)"
echo ""

# -----------------------------------------------------------------------------
# 1. Check basic DNS configuration
# -----------------------------------------------------------------------------
echo "=== 1. Checking /etc/resolv.conf ==="
cat /etc/resolv.conf
echo ""

# -----------------------------------------------------------------------------
# 2. Test DNS resolution
# -----------------------------------------------------------------------------
echo "=== 2. Testing DNS Resolution ==="
echo "--- Testing with host command ---"
host pypi.org 2>&1 || echo "FAILED: host command"
echo ""

echo "--- Testing with nslookup ---"
nslookup pypi.org 2>&1 || echo "FAILED: nslookup"
echo ""

echo "--- Testing against CoreDNS directly (10.43.0.10) ---"
nslookup pypi.org 10.43.0.10 2>&1 || echo "FAILED: CoreDNS lookup"
echo ""

# -----------------------------------------------------------------------------
# 3. Check network connectivity to CoreDNS
# -----------------------------------------------------------------------------
echo "=== 3. Checking CoreDNS Connectivity ==="
echo "--- Ping CoreDNS IP ---"
ping -c 3 10.43.0.10 2>&1 || echo "FAILED: Cannot ping CoreDNS"
echo ""

echo "--- Check route to CoreDNS ---"
ip route get 10.43.0.10 2>&1 || echo "FAILED: No route"
echo ""

# -----------------------------------------------------------------------------
# 4. Check flannel/CNI status
# -----------------------------------------------------------------------------
echo "=== 4. Checking CNI/Network Status ==="
echo "--- Network interfaces ---"
ip addr show | grep -E "^[0-9]+:|inet "
echo ""

echo "--- Flannel interface ---"
ip addr show flannel.1 2>&1 || echo "No flannel.1 interface found"
echo ""

echo "--- cni0 interface ---"
ip addr show cni0 2>&1 || echo "No cni0 interface found"
echo ""

# -----------------------------------------------------------------------------
# 5. Check iptables rules for DNS
# -----------------------------------------------------------------------------
echo "=== 5. Checking iptables DNS rules ==="
iptables -t nat -L KUBE-SERVICES 2>&1 | grep -i dns | head -5 || echo "No DNS iptables rules found"
echo ""

# -----------------------------------------------------------------------------
# 6. Check k3s service status
# -----------------------------------------------------------------------------
echo "=== 6. k3s Service Status ==="
systemctl status k3s-agent --no-pager 2>&1 | head -20 || systemctl status k3s --no-pager | head -20
echo ""

# -----------------------------------------------------------------------------
# 7. Repair Steps
# -----------------------------------------------------------------------------
echo "=== 7. Attempting Repairs ==="

echo "--- Restarting k3s-agent ---"
sudo systemctl restart k3s-agent 2>/dev/null || sudo systemctl restart k3s
sleep 10

echo "--- Flushing iptables and reloading ---"
sudo iptables -F 2>/dev/null || true
sudo iptables -t nat -F 2>/dev/null || true

echo "--- Testing DNS after repair ---"
sleep 5
nslookup pypi.org 2>&1 && echo "SUCCESS: DNS working!" || echo "STILL FAILING"

echo ""
echo "=== Repair Complete ==="
echo "If DNS is still failing, consider:"
echo "1. Rebooting the node: sudo reboot"
echo "2. Draining and uncordoning: kubectl drain k3s-worker03 --ignore-daemonsets && kubectl uncordon k3s-worker03"
echo "3. Checking CoreDNS pod logs: kubectl logs -n kube-system -l k8s-app=kube-dns"
