# Quick Fix: K3s Cluster Ingress Port Forwarding

This is the quick reference for setting up port forwarding once you have access to k3s-cluster-ingress.

---

## Found Information

**k3s-cluster-ingress:**
- Tailscale IP: 100.81.79.19
- Local IP: UNKNOWN (need console access to determine)
- Status: Visible in Tailscale but not accessible via SSH

---

## Access k3s-cluster-ingress

### Option 1: Via Proxmox Console
1. Open: https://10.88.140.164:8006
2. Login with root@pam token
3. Find VM named "k3s-cluster-ingress" or search VMs
4. Click "Console" button for noVNC access
5. Login (likely k3s/toor or root)

### Option 2: If You Know Local IP
```bash
ssh k3s@<local-ip>
# password: toor
```

---

## Run Setup Script (EASIEST)

### Transfer Script to Node
```bash
# From your local machine (if you have access to local IP)
scp /Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/K3S_INGRESS_SETUP.sh k3s@<node-ip>:/tmp/

# OR via Proxmox console, create the file manually
```

### Run Script
```bash
chmod +x /tmp/K3S_INGRESS_SETUP.sh
sudo /tmp/K3S_INGRESS_SETUP.sh
```

The script will:
- Install iptables-persistent
- Enable IP forwarding
- Configure NAT rules
- Save rules permanently
- Test Traefik connectivity

---

## Manual Setup (If Script Not Available)

Copy-paste these commands directly into the console:

```bash
# 1. Install iptables-persistent
sudo apt update && sudo apt install -y iptables-persistent

# 2. Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# 3. Forward port 80 to Traefik
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 10.88.145.200:80

# 4. Forward port 443 to Traefik
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j DNAT --to-destination 10.88.145.200:443

# 5. Enable masquerading
sudo iptables -t nat -A POSTROUTING -j MASQUERADE

# 6. Save rules
sudo netfilter-persistent save

# 7. Verify rules
sudo iptables -t nat -L -n -v

# 8. Test connection to Traefik
curl -I http://10.88.145.200 -H "Host: chat.ry-ops.dev"
```

---

## Verify Configuration

```bash
# Check IP forwarding is enabled
cat /proc/sys/net/ipv4/ip_forward
# Should output: 1

# Check NAT rules
sudo iptables -t nat -L -n -v

# Test Traefik connectivity
curl -I http://10.88.145.200 -H "Host: chat.ry-ops.dev"
# Should return: HTTP/1.1 200 OK

# Get Tailscale IP (for DNS update)
tailscale status --self | grep "^100\."
# Should show: 100.81.79.19
```

---

## DNS Update (After Port Forwarding Works)

Once port forwarding is configured:

**Current DNS:**
```
chat.ry-ops.dev → 100.81.79.19
```

**Verify it's correct:**
- If k3s-cluster-ingress Tailscale IP is 100.81.79.19, no DNS change needed
- If different, update DNS to match actual Tailscale IP

**Test:**
```bash
# From any machine on Tailscale network
curl -I http://chat.ry-ops.dev
# Should return: HTTP/1.1 200 OK
```

---

## Troubleshooting

### Port forwarding not working

```bash
# Check if Traefik is reachable from ingress node
ping 10.88.145.200
curl -I http://10.88.145.200

# Verify NAT rules are active
sudo iptables -t nat -L -n -v | grep 10.88.145.200

# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward
```

### Tailscale not responding

```bash
# Check Tailscale status
sudo systemctl status tailscaled

# Restart Tailscale
sudo systemctl restart tailscaled

# Re-check status
tailscale status
```

### Rules not persisting after reboot

```bash
# Manually save rules
sudo iptables-save | sudo tee /etc/iptables/rules.v4

# Check netfilter-persistent service
sudo systemctl status netfilter-persistent
sudo systemctl enable netfilter-persistent
```

---

## Alternative: Use k3s-master01 as Temporary Ingress

If k3s-cluster-ingress is unavailable, use k3s-master01:

```bash
# SSH to k3s-master01
ssh k3s@10.88.145.190
# password: toor

# Run the same setup commands above

# Get its Tailscale IP
tailscale status --self
# Output: 100.96.201.102

# Update DNS: chat.ry-ops.dev → 100.96.201.102
```

---

## Files Created

1. **Investigation Report:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/K3S_INGRESS_INVESTIGATION.md`
2. **Setup Script:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/K3S_INGRESS_SETUP.sh`
3. **This Quick Reference:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/QUICK_FIX_INGRESS.md`

---

## Summary

**What was found:**
- k3s-cluster-ingress exists at Tailscale IP 100.81.79.19
- Node is not accessible via SSH or network
- Need console access to configure it

**What's ready:**
- Automated setup script
- Manual setup commands
- Verification procedures
- Troubleshooting guide

**What's needed:**
- Physical/console access to k3s-cluster-ingress
- OR use k3s-master01 as temporary solution

**Estimated time:** 5-10 minutes once you have access
