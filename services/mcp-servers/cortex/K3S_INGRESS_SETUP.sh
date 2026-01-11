#!/bin/bash
# K3s Cluster Ingress Port Forwarding Setup
# Run this on k3s-cluster-ingress node (100.81.79.19 / unknown local IP)
# OR temporarily on k3s-master01 (10.88.145.190)

set -e

echo "=== K3s Cluster Ingress Port Forwarding Setup ==="
echo ""
echo "This script will configure port forwarding from this node to Traefik LoadBalancer"
echo "Target: 10.88.145.200:80/443 (Traefik)"
echo ""

# Step 1: Install iptables-persistent
echo "[1/5] Installing iptables-persistent..."
sudo apt update
sudo apt install -y iptables-persistent netfilter-persistent

# Step 2: Enable IP forwarding
echo "[2/5] Enabling IP forwarding..."
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Step 3: Set up NAT forwarding rules
echo "[3/5] Configuring NAT forwarding rules..."

# Forward port 80 to Traefik
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 10.88.145.200:80

# Forward port 443 to Traefik
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j DNAT --to-destination 10.88.145.200:443

# Enable masquerading for return traffic
sudo iptables -t nat -A POSTROUTING -j MASQUERADE

# Step 4: Save rules
echo "[4/5] Saving iptables rules..."
sudo netfilter-persistent save

# Step 5: Verify configuration
echo "[5/5] Verifying configuration..."
echo ""
echo "IP Forwarding status:"
cat /proc/sys/net/ipv4/ip_forward

echo ""
echo "NAT rules:"
sudo iptables -t nat -L -n -v

echo ""
echo "=== Testing Connection to Traefik ==="
curl -I http://10.88.145.200 -H "Host: chat.ry-ops.dev" --max-time 5 || echo "WARNING: Could not reach Traefik directly"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Get this node's Tailscale IP: tailscale status --self | grep TailscaleIPs"
echo "2. Update DNS: chat.ry-ops.dev → <this-node-tailscale-ip>"
echo "3. Test: curl -I http://chat.ry-ops.dev"
echo ""
echo "Current node info:"
echo "  Hostname: $(hostname)"
echo "  Local IPs:"
ip addr show | grep "inet " | grep -v "127.0.0.1"
echo "  Tailscale IP:"
tailscale status --self 2>/dev/null | grep "^100\." | head -1 || echo "  Tailscale not found or not logged in"
