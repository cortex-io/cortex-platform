# K3s Cluster Ingress Investigation Report

**Date:** December 24, 2025
**Investigator:** Daryl (Brother #2)
**Status:** PARTIALLY COMPLETE - Node located but inaccessible

---

## Objective

Find k3s-cluster-ingress node and configure port forwarding from Tailscale to Traefik LoadBalancer (10.88.145.200).

---

## Findings

### k3s-cluster-ingress Located

**Tailscale Information:**
- **Hostname:** k3s-cluster-ingress
- **Tailscale IP:** 100.81.79.19
- **Status:** Active (relay connection through "ord")
- **Tailnet:** ry-ops

**Discovered via:**
```bash
ssh k3s@10.88.145.190  # k3s-master01
tailscale status | grep ingress
# Output: 100.81.79.19  k3s-cluster-ingress  ry-ops@  linux  active; relay "ord"
```

### Access Issues

**Problem:** k3s-cluster-ingress is not responding to:
- SSH connections (port 22)
- Ping (ICMP)
- Connection attempts from other Tailscale nodes

**Attempts made:**
1. Direct SSH to 100.81.79.19 - Connection refused/timeout
2. SSH via jump host (k3s-master01) - Connection timeout
3. Ping from k3s-master01 - 100% packet loss

**Possible causes:**
1. VM is powered off
2. SSH service not running
3. Firewall blocking connections
4. Network misconfiguration
5. VM exists in Tailscale but not actually running

---

## K3s Cluster Topology

### Existing Nodes (All Accessible)

**Masters:**
- k3s-master01: 10.88.145.190 (VMID 300) - Tailscale: 100.96.201.102
- k3s-master02: 10.88.145.193 (VMID 303) - Tailscale: 100.93.204.60
- k3s-master03: 10.88.145.196 (VMID 306) - Tailscale: 100.106.46.15

**Workers:**
- k3s-worker01: 10.88.145.191 (VMID 301) - Tailscale: 100.79.120.4
- k3s-worker02: 10.88.145.192 (VMID 302) - Tailscale: 100.87.213.61
- k3s-worker03: 10.88.145.194 (VMID 304) - Tailscale: 100.72.159.4
- k3s-worker04: 10.88.145.195 (VMID 305) - Tailscale: 100.89.5.80

**k3s-cluster-ingress:**
- Local IP: UNKNOWN
- VMID: UNKNOWN (not in range 300-306)
- Tailscale: 100.81.79.19
- Status: In Tailscale network but not accessible

---

## Current Network Configuration

### DNS Configuration (Problematic)
```
chat.ry-ops.dev → 100.81.79.19 (k3s-cluster-ingress Tailscale IP)
                     ↓
                  NOT ACCESSIBLE
```

### Traefik LoadBalancer (Working)
```
Direct access: http://10.88.145.200
Host header: chat.ry-ops.dev
Result: 200 OK (confirmed working)
```

### Required Configuration
```
Internet/Tailscale
        ↓
k3s-cluster-ingress (100.81.79.19)
  Port 80  → NAT → 10.88.145.200:80
  Port 443 → NAT → 10.88.145.200:443
        ↓
    Traefik
        ↓
  cortex-chat pod
```

---

## Solution Options

### Option 1: Find and Fix k3s-cluster-ingress (RECOMMENDED)

**Steps:**
1. Access Proxmox Web UI: https://10.88.140.164:8006
   - Credentials: root@pam / (token: root@pam!cortex-k3s-display)
2. Search for VM named "ingress" or "k3s-cluster-ingress"
3. Check VM power state
4. Access via noVNC console
5. Diagnose network/SSH issues
6. Run setup script: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/K3S_INGRESS_SETUP.sh`

### Option 2: Use k3s-master01 as Temporary Ingress

**Pros:**
- Node is accessible and working
- Already has Tailscale configured
- Can be set up immediately

**Cons:**
- Not the intended architecture
- Master node should focus on control plane
- Temporary solution only

**Implementation:**
```bash
# SSH to k3s-master01
ssh k3s@10.88.145.190  # password: toor

# Copy and run the setup script
curl -o /tmp/setup-ingress.sh https://path/to/K3S_INGRESS_SETUP.sh
chmod +x /tmp/setup-ingress.sh
sudo /tmp/setup-ingress.sh

# Update DNS to point to k3s-master01's Tailscale IP
# chat.ry-ops.dev → 100.96.201.102
```

### Option 3: Create New Ingress Node

If k3s-cluster-ingress doesn't exist or is irreparably broken:

1. Create new VM in Proxmox
2. Install Ubuntu Server
3. Configure static IP in 10.88.145.x range
4. Install Tailscale
5. Name it k3s-cluster-ingress
6. Run port forwarding setup script

---

## Setup Script Created

**Location:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/K3S_INGRESS_SETUP.sh`

**What it does:**
1. Installs iptables-persistent
2. Enables IP forwarding
3. Configures NAT rules for ports 80/443 → 10.88.145.200
4. Saves rules permanently
5. Verifies configuration

**Usage:**
```bash
# Copy to target node
scp K3S_INGRESS_SETUP.sh k3s@<target-ip>:/tmp/

# SSH to target node
ssh k3s@<target-ip>

# Run setup
chmod +x /tmp/K3S_INGRESS_SETUP.sh
sudo /tmp/K3S_INGRESS_SETUP.sh
```

---

## Next Steps (Requires User Action)

1. **Access k3s-cluster-ingress:**
   - Via Proxmox console (noVNC)
   - OR via physical/IPMI console if it's a physical machine
   - Determine why SSH is not accessible

2. **Get Local IP:**
   ```bash
   # On k3s-cluster-ingress console
   ip addr show
   hostname
   ```

3. **Run Port Forwarding Setup:**
   ```bash
   # Transfer script to node
   # Run: sudo /path/to/K3S_INGRESS_SETUP.sh
   ```

4. **Verify Tailscale IP:**
   ```bash
   tailscale status --self
   ```

5. **Update DNS:**
   - Confirm Tailscale IP is 100.81.79.19
   - OR update chat.ry-ops.dev DNS to actual Tailscale IP

6. **Test Access:**
   ```bash
   curl -I http://chat.ry-ops.dev
   # Should return 200 OK
   ```

---

## Manual Configuration (If Script Fails)

```bash
# 1. Install iptables-persistent
sudo apt update
sudo apt install -y iptables-persistent

# 2. Enable IP forwarding
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# 3. Configure NAT forwarding
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 10.88.145.200:80
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j DNAT --to-destination 10.88.145.200:443
sudo iptables -t nat -A POSTROUTING -j MASQUERADE

# 4. Save rules
sudo netfilter-persistent save

# 5. Verify
sudo iptables -t nat -L -n -v
curl -I http://10.88.145.200 -H "Host: chat.ry-ops.dev"
```

---

## DNS Update Information

Once port forwarding is configured, update DNS:

**Domain:** chat.ry-ops.dev
**Current A Record:** 100.81.79.19 (k3s-cluster-ingress)
**Should point to:** Tailscale IP of node running port forwarding

If using k3s-master01 temporarily:
- Update to: 100.96.201.102

---

## References

- **Network Diagnosis:** `/Users/ryandahlberg/Projects/cortex/NETWORK_DIAGNOSIS.md`
- **Proxmox Credentials:** `/Users/ryandahlberg/Projects/cortex/coordination/config/proxmox-credentials.sh`
- **Sandfly Deployment (Tailscale IPs):** `/Users/ryandahlberg/Projects/cortex/sandfly-integration/DEPLOYMENT-COMPLETE.md`
- **K3s Deployment:** `/Users/ryandahlberg/Projects/cortex/K3S-DEPLOYMENT-COMPLETE.md`

---

## Status

**INCOMPLETE** - Waiting for access to k3s-cluster-ingress node

**Blocker:** Cannot access k3s-cluster-ingress (100.81.79.19) via SSH or network

**Recommendation:** Use Proxmox console to access the VM and diagnose connectivity issues.
