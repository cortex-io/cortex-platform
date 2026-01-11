# Infrastructure Contractor - Quick Reference

**Role**: Multi-MCP Infrastructure Orchestration Specialist
**MCP Servers**: Proxmox, UniFi, Cloudflare
**Token Budget**: 25,000 tokens per session

---

## Core Capabilities

### 1. VM Provisioning (Proxmox MCP)
- Create VMs from templates
- Clone VMs for rapid provisioning
- Configure CPU, RAM, disk resources
- Manage VM lifecycle (start, stop, backup, delete)
- Monitor resource utilization

### 2. Network Configuration (UniFi MCP)
- Create VLANs for network segmentation
- Configure firewall rules and security policies
- Set up port forwarding and NAT
- Monitor network performance
- Manage client connectivity

### 3. DNS & Edge (Cloudflare MCP)
- Create and update DNS records
- Configure SSL/TLS certificates
- Set up Cloudflare Tunnels
- Manage CDN and caching
- Configure edge firewall rules

---

## VM Templates (Quick Reference)

| Size | CPU | RAM | Disk | Use Case |
|------|-----|-----|------|----------|
| Tiny | 1 | 2GB | 32GB | DNS, monitoring agents |
| Small | 2 | 4GB | 50GB | Dev, testing, small apps |
| Medium | 4 | 8GB | 100GB | Production apps, APIs |
| Large | 8 | 16GB | 200GB | Databases, data processing |
| XLarge | 16 | 32GB | 500GB | ML, large databases, virtualization |

---

## Standard VLAN Layout

| VLAN ID | Name | Subnet | Purpose | Security |
|---------|------|--------|---------|----------|
| 10 | management | 10.10.0.0/24 | Infrastructure management | Critical |
| 20 | app-servers | 10.20.0.0/24 | Production apps | High |
| 30 | databases | 10.30.0.0/24 | Database servers | Critical |
| 40 | development | 10.40.0.0/24 | Dev/test VMs | Medium |
| 50 | guest | 10.50.0.0/24 | Guest WiFi | Low |
| 60 | iot | 10.60.0.0/24 | IoT devices | Low |
| 70 | monitoring | 10.70.0.0/24 | Monitoring systems | High |

---

## Common Firewall Rules

### SSH Access
```
Allow: Management (10.10.0.0/24) → Any:22
Deny: WAN → Any:22
```

### Web Server
```
Allow: WAN → App Servers (10.20.0.0/24):80,443
Allow: LAN → App Servers (10.20.0.0/24):80,443
```

### Database Access
```
Allow: App Servers (10.20.0.0/24) → Databases (10.30.0.0/24):3306,5432
Deny: WAN → Databases (10.30.0.0/24):*
```

### Network Isolation
```
Deny: Development (10.40.0.0/24) → Production (10.20.0.0/24, 10.30.0.0/24)
Deny: Guest (10.50.0.0/24) → LAN (all internal VLANs)
Deny: IoT (10.60.0.0/24) → LAN (10.10.0.0/24, 10.20.0.0/24, 10.30.0.0/24)
```

---

## DNS Naming Conventions

### Production Servers
Format: `{service}-{env}-{number}.{domain}`
- `web-prod-01.example.com`
- `api-prod-02.example.com`
- `db-prod-01.example.com`

### Development
Format: `{service}-dev-{number}.dev.{domain}`
- `web-dev-01.dev.example.com`
- `api-dev-01.dev.example.com`

### Infrastructure
Format: `{type}-{location}-{number}.infra.{domain}`
- `proxmox-dc1-01.infra.example.com`
- `unifi-dc1-01.infra.example.com`

### Load Balanced
Format: `{service}.{domain}`
- `api.example.com`
- `www.example.com`
- `app.example.com`

---

## Infrastructure Provisioning Workflow

### Complete Stack (VM + Network + DNS)

```markdown
Phase 1: VM Provisioning (Proxmox)
1. Check node capacity
2. Clone from template
3. Configure resources (CPU, RAM, disk)
4. Start VM and note IP

Phase 2: Network Configuration (UniFi)
1. Create/verify VLAN exists
2. Configure firewall rules
3. Set up port forwarding (if needed)
4. Verify connectivity

Phase 3: DNS & Edge (Cloudflare)
1. Create DNS A record
2. Configure SSL certificate
3. Set up Cloudflare Tunnel (if needed)
4. Verify resolution and connectivity
```

---

## Backup Strategies

| Strategy | Schedule | Retention | VMs | Mode |
|----------|----------|-----------|-----|------|
| Daily Production | Daily 2AM | 7 days | Production apps/DBs | Snapshot |
| Weekly Full | Sunday 3AM | 4 weeks | All production | Stop |
| Monthly Archive | 1st of month | 12 months | Critical systems | Stop |
| Dev Minimal | Friday 10PM | 2 weeks | Dev/test | Snapshot |

---

## Common Operations

### Provision Single VM
```bash
1. Proxmox: Clone VM from template
2. Proxmox: Configure CPU, RAM, disk
3. Proxmox: Start VM
4. UniFi: Create DHCP reservation (optional)
5. Cloudflare: Create DNS record
```

### Create Isolated Network
```bash
1. UniFi: Create VLAN with subnet
2. UniFi: Configure firewall rules (isolation)
3. Proxmox: Attach VMs to VLAN
4. Cloudflare: Create DNS records (internal)
```

### Set Up Web Application
```bash
1. Proxmox: Create VM for app server
2. UniFi: Configure firewall (allow 80/443 from WAN)
3. Cloudflare: Create DNS with proxy enabled
4. Cloudflare: Configure SSL (Full Strict)
5. Verify connectivity and SSL
```

---

## Troubleshooting

### VM Won't Boot
- Check Proxmox node resources
- Verify VM config (disk, network, CPU)
- Review VM console for errors
- Check storage availability

### No Network Connectivity
- Verify VLAN configuration
- Check VM network interface settings
- Confirm DHCP is working
- Review firewall rules

### DNS Not Resolving
- Verify DNS record in Cloudflare
- Check DNS propagation (dig/nslookup)
- Confirm proxy status (orange/gray cloud)
- Test origin server connectivity

---

## Security Checklist

- [ ] Disable root SSH login
- [ ] Use SSH keys only (no passwords)
- [ ] Configure automatic security updates
- [ ] Enable firewall (ufw/iptables)
- [ ] Install fail2ban
- [ ] Set up log forwarding
- [ ] Enable backups
- [ ] Use least privilege for firewall rules
- [ ] Implement network segmentation
- [ ] Regular security scanning

---

## Files

- **Agent Definition**: `/Users/ryandahlberg/Projects/cortex/coordination/contractors/infrastructure-contractor.md`
- **Knowledge Base**: `/Users/ryandahlberg/Projects/cortex/coordination/contractors/infrastructure-contractor-knowledge.json`
- **Quick Reference**: `/Users/ryandahlberg/Projects/cortex/coordination/contractors/infrastructure-contractor-quick-reference.md` (this file)

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
