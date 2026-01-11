# Infrastructure Contractor - Comprehensive Patterns & Domain Knowledge

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintainer**: Development Master
**Purpose**: Comprehensive infrastructure patterns for infrastructure-contractor agent

---

## Table of Contents

1. [Proxmox VM Templates and Sizing](#proxmox-vm-templates-and-sizing)
2. [Network Topology Patterns](#network-topology-patterns)
3. [Storage Configurations](#storage-configurations)
4. [UniFi Network Patterns](#unifi-network-patterns)
5. [Cloudflare Integration](#cloudflare-integration)
6. [High Availability Patterns](#high-availability-patterns)
7. [Disaster Recovery Configurations](#disaster-recovery-configurations)
8. [Cost Optimization Strategies](#cost-optimization-strategies)
9. [Security Hardening Checklists](#security-hardening-checklists)
10. [Talos Kubernetes Integration](#talos-kubernetes-integration)

---

## Proxmox VM Templates and Sizing

### VM Sizing Matrix

#### Workload-Based Sizing Recommendations

| Workload Type | CPU | RAM | Disk | IOPS | Network | Notes |
|--------------|-----|-----|------|------|---------|-------|
| DNS Server | 1 vCPU | 1-2 GB | 20 GB | Low | 1 Gbps | Minimal resources, high availability |
| Reverse Proxy (NGINX) | 2 vCPU | 2-4 GB | 32 GB | Medium | 10 Gbps | SSL termination, caching |
| Web Server (Node.js/PHP) | 2-4 vCPU | 4-8 GB | 50 GB | Medium | 10 Gbps | Application hosting |
| API Server (REST/GraphQL) | 4 vCPU | 8 GB | 50 GB | Medium | 10 Gbps | Stateless, horizontal scaling |
| Redis Cache | 2 vCPU | 4-16 GB | 32 GB | High | 10 Gbps | Memory-intensive |
| PostgreSQL (Small) | 4 vCPU | 8 GB | 100 GB | High | 10 Gbps | <100 GB data |
| PostgreSQL (Medium) | 8 vCPU | 16 GB | 200 GB | Very High | 10 Gbps | 100-500 GB data |
| PostgreSQL (Large) | 16 vCPU | 32 GB | 500 GB | Very High | 10 Gbps | >500 GB data |
| MySQL/MariaDB | 4-8 vCPU | 8-16 GB | 100-200 GB | High | 10 Gbps | Similar to PostgreSQL |
| MongoDB | 8 vCPU | 16 GB | 200 GB | High | 10 Gbps | Document storage |
| Elasticsearch | 8 vCPU | 16-32 GB | 500 GB | Very High | 10 Gbps | Heap = 50% RAM |
| RabbitMQ/Kafka | 4 vCPU | 8 GB | 100 GB | High | 10 Gbps | Message queue |
| GitLab | 8 vCPU | 16 GB | 200 GB | High | 10 Gbps | CI/CD, Git hosting |
| Jenkins | 4 vCPU | 8 GB | 100 GB | Medium | 1 Gbps | CI/CD runners |
| Docker Host | 8 vCPU | 16 GB | 100 GB | Medium | 10 Gbps | Container runtime |
| Kubernetes Worker | 8-16 vCPU | 16-32 GB | 100 GB | High | 10 Gbps | Production workloads |
| Kubernetes Control Plane | 4 vCPU | 8 GB | 50 GB | High | 10 Gbps | HA: 3 nodes minimum |
| Prometheus | 4 vCPU | 8 GB | 200 GB | Medium | 1 Gbps | Metrics storage |
| Grafana | 2 vCPU | 4 GB | 32 GB | Low | 1 Gbps | Visualization |
| Loki | 4 vCPU | 8 GB | 200 GB | High | 1 Gbps | Log aggregation |
| Backup Server | 4 vCPU | 8 GB | 2 TB | Medium | 10 Gbps | Backup storage |

### VM Template Standards

#### Ubuntu 22.04 LTS Template

```yaml
template_name: template-ubuntu-2204
os: Ubuntu 22.04.3 LTS
kernel: 5.15.0-92-generic
architecture: x86_64

specs:
  cpu: 2 cores
  ram: 4096 MB
  disk: 32 GB (thin provisioned)
  network: virtio
  scsi_controller: VirtIO SCSI

pre_installed:
  - openssh-server
  - cloud-init
  - qemu-guest-agent
  - vim
  - curl
  - wget
  - htop
  - net-tools
  - git
  - fail2ban
  - ufw

configuration:
  timezone: UTC
  locale: en_US.UTF-8
  ssh:
    permit_root_login: no
    password_authentication: no
    pubkey_authentication: yes
  firewall:
    default_policy: deny
    allow_ssh: yes
  updates:
    unattended_upgrades: enabled
    auto_reboot: no

cloud_init:
  enabled: yes
  datasource: NoCloud
  network_config: dhcp
  user_data: custom per deployment
```

#### Ubuntu 24.04 LTS Template

```yaml
template_name: template-ubuntu-2404
os: Ubuntu 24.04 LTS
kernel: 6.8.0
architecture: x86_64

specs:
  cpu: 2 cores
  ram: 4096 MB
  disk: 32 GB (thin provisioned)
  network: virtio
  scsi_controller: VirtIO SCSI

pre_installed:
  - openssh-server
  - cloud-init
  - qemu-guest-agent
  - systemd-resolved
  - netplan
  - vim
  - curl
  - wget
  - htop
  - git
  - fail2ban
  - ufw

configuration:
  timezone: UTC
  locale: en_US.UTF-8
  ssh:
    permit_root_login: no
    password_authentication: no
    pubkey_authentication: yes
  firewall:
    default_policy: deny
    allow_ssh: yes
  updates:
    unattended_upgrades: enabled
    auto_reboot: no

notes:
  - Longer support window (until 2029)
  - Newer kernel for better hardware support
  - systemd-resolved for DNS management
```

#### Debian 12 (Bookworm) Template

```yaml
template_name: template-debian-12
os: Debian 12 (Bookworm)
kernel: 6.1.0
architecture: x86_64

specs:
  cpu: 2 cores
  ram: 4096 MB
  disk: 32 GB (thin provisioned)
  network: virtio
  scsi_controller: VirtIO SCSI

pre_installed:
  - openssh-server
  - cloud-init
  - qemu-guest-agent
  - vim
  - curl
  - wget
  - htop
  - net-tools
  - git
  - fail2ban
  - ufw

configuration:
  timezone: UTC
  locale: en_US.UTF-8
  ssh:
    permit_root_login: no
    password_authentication: no
    pubkey_authentication: yes
  firewall:
    default_policy: deny
    allow_ssh: yes
  updates:
    unattended_upgrades: enabled
    auto_reboot: no

use_cases:
  - Production servers requiring stability
  - Security-focused deployments
  - Minimal attack surface requirements
```

#### Alpine Linux 3 Template

```yaml
template_name: template-alpine-3
os: Alpine Linux 3.19
kernel: 6.6.x
architecture: x86_64

specs:
  cpu: 1 core
  ram: 512 MB
  disk: 8 GB (thin provisioned)
  network: virtio
  scsi_controller: VirtIO SCSI

pre_installed:
  - openssh
  - cloud-init
  - qemu-guest-agent
  - vim
  - curl
  - wget
  - htop
  - git

configuration:
  timezone: UTC
  locale: en_US.UTF-8
  ssh:
    permit_root_login: no
    password_authentication: no
    pubkey_authentication: yes
  firewall:
    type: iptables
    default_policy: deny
    allow_ssh: yes

use_cases:
  - Minimal containers
  - Edge computing
  - Resource-constrained environments
  - Security-focused deployments
  - Small footprint requirements

advantages:
  - Smallest image size (5-10 MB base)
  - Minimal attack surface
  - Low resource consumption
  - Fast boot times
```

### VM Cloning Strategy

#### Fast Clone (Linked Clone)

```yaml
method: linked_clone
description: Creates clone using base template as backing disk
speed: Very fast (seconds)
storage_efficiency: High (only stores differences)
use_cases:
  - Development environments
  - Testing
  - Temporary VMs
  - Fast provisioning needed

limitations:
  - Dependent on base template
  - Cannot delete template while clones exist
  - Snapshot chain can grow

proxmox_command: qm clone <template_id> <new_vmid> --name <new_name> --full 0
```

#### Full Clone

```yaml
method: full_clone
description: Creates independent copy of template
speed: Slower (minutes depending on disk size)
storage_efficiency: Lower (full disk copy)
use_cases:
  - Production VMs
  - Long-lived infrastructure
  - When template needs to be deleted
  - When independence is required

advantages:
  - Fully independent of template
  - No snapshot chain
  - Can delete template afterward
  - Better performance (no backing chain)

proxmox_command: qm clone <template_id> <new_vmid> --name <new_name> --full 1
```

### Resource Allocation Best Practices

#### CPU Allocation

```yaml
cpu_types:
  host:
    description: Pass-through host CPU features
    use_case: Best performance, limited migration
    recommendation: Production VMs on dedicated hardware

  kvm64:
    description: Generic 64-bit CPU (no features)
    use_case: Maximum compatibility
    recommendation: VMs that need to migrate between different CPUs

  x86-64-v2:
    description: x86-64 with SSE3, SSE4, SSSE3
    use_case: Good balance of features and compatibility
    recommendation: Modern workloads with migration needs

cpu_units:
  description: CPU scheduling weight (1024 = 1 core share)
  default: 1024
  range: 2-262144
  recommendation: |
    - Critical VMs: 2048-4096 (higher priority)
    - Standard VMs: 1024 (default)
    - Low priority: 512 (background tasks)

cpu_limit:
  description: Limit CPU usage percentage
  default: unlimited
  range: 0-128 (128 = 100% of all cores)
  recommendation: |
    - Development: Limit to 50-75% to prevent resource hogging
    - Production: Unlimited for performance
    - Testing: 25-50% to allow multiple concurrent tests
```

#### Memory Allocation

```yaml
memory_types:
  static:
    description: Fixed memory allocation
    use_case: Production databases, caches
    recommendation: Most production workloads

  ballooning:
    description: Dynamic memory allocation with balloon driver
    use_case: Development, testing, non-critical
    recommendation: Overcommitted environments

memory_settings:
  minimum_mb: 512 (for basic functionality)
  recommended_overhead: 10-20% above application requirement

  examples:
    web_server:
      app_requirement: 2 GB
      os_overhead: 500 MB
      recommended: 3 GB (with buffer)

    database_server:
      app_requirement: 8 GB
      os_overhead: 1 GB
      buffer: 20%
      recommended: 12 GB

  hugepages:
    description: Use large memory pages (2MB/1GB)
    use_case: High-performance databases, big data
    enabled: echo 1024 > /proc/sys/vm/nr_hugepages
```

#### Disk Allocation

```yaml
disk_types:
  virtio_scsi:
    description: Paravirtualized SCSI controller
    performance: Excellent
    features: TRIM, discard, iothread
    recommendation: Default choice for all VMs

  ide:
    description: Emulated IDE controller
    performance: Poor
    use_case: Legacy OS compatibility
    recommendation: Avoid unless required

  sata:
    description: Emulated SATA controller
    performance: Good
    use_case: Guest OS without VirtIO drivers
    recommendation: Fallback option

disk_cache:
  none:
    description: No caching
    safety: Highest
    performance: Lower
    use_case: Critical data (databases)

  writeback:
    description: Write cache enabled
    safety: Lower (data loss risk on power failure)
    performance: Highest
    use_case: Non-critical data, ephemeral workloads

  writethrough:
    description: Write directly to storage
    safety: High
    performance: Medium
    use_case: Balanced approach (recommended)

disk_format:
  raw:
    description: Raw disk image
    performance: Best
    features: Limited
    space_efficiency: Low (pre-allocated)
    use_case: Production databases

  qcow2:
    description: QEMU copy-on-write format
    performance: Good
    features: Snapshots, compression, encryption
    space_efficiency: High (thin provisioning)
    use_case: Most VMs (recommended)

storage_recommendations:
  boot_disk:
    size: 32-50 GB
    type: SSD/NVMe
    format: qcow2
    cache: writethrough

  data_disk:
    size: Application-dependent
    type: SSD/NVMe for databases, HDD for archives
    format: raw for databases, qcow2 for files
    cache: none for databases, writethrough for others
```

---

## Network Topology Patterns

### Standard VLAN Architecture

#### Management VLAN (VLAN 10)

```yaml
vlan_id: 10
name: management
subnet: 10.10.0.0/24
gateway: 10.10.0.1
dns_servers: [1.1.1.1, 8.8.8.8]

dhcp:
  enabled: yes
  range: 10.10.0.100-10.10.0.200
  reservations:
    - ip: 10.10.0.10
      mac: AA:BB:CC:DD:EE:01
      hostname: proxmox-01
    - ip: 10.10.0.11
      mac: AA:BB:CC:DD:EE:02
      hostname: proxmox-02
    - ip: 10.10.0.20
      mac: AA:BB:CC:DD:EE:10
      hostname: unifi-controller
    - ip: 10.10.0.30
      mac: AA:BB:CC:DD:EE:20
      hostname: switch-core-01

static_assignments:
  10.10.0.1: gateway (router/firewall)
  10.10.0.2: secondary_gateway (VRRP)
  10.10.0.10-10.10.0.19: Proxmox hosts
  10.10.0.20-10.10.0.29: Network equipment (UniFi, switches)
  10.10.0.30-10.10.0.39: Storage (NAS, SAN)
  10.10.0.50-10.10.0.99: Reserved for infrastructure

security:
  level: Critical
  internet_access: Restricted (firewall rules only)
  accessible_from:
    - Admin workstations (specific IPs)
    - VPN connections
  accessible_to:
    - All VLANs (for monitoring)
    - Internet (for updates, limited)

firewall_rules:
  inbound:
    - allow: SSH (22) from admin workstations
    - allow: HTTPS (443) for Proxmox/UniFi web UI from admin workstations
    - allow: ICMP from monitoring VLAN
    - deny: all other inbound

  outbound:
    - allow: DNS (53)
    - allow: NTP (123)
    - allow: HTTPS (443) for updates
    - allow: established connections
    - deny: all other outbound

monitoring:
  - SNMP enabled on all devices
  - Syslog forwarding to monitoring VLAN
  - Uptime monitoring (Prometheus)
  - Alert on unauthorized access attempts
```

#### Application Servers VLAN (VLAN 20)

```yaml
vlan_id: 20
name: app-servers
subnet: 10.20.0.0/24
gateway: 10.20.0.1
dns_servers: [10.70.0.10, 1.1.1.1]

dhcp:
  enabled: yes
  range: 10.20.0.100-10.20.0.200
  lease_time: 86400 # 24 hours

static_assignments:
  10.20.0.10-10.20.0.49: Web servers
  10.20.0.50-10.20.0.89: API servers
  10.20.0.90-10.20.0.129: Application servers
  10.20.0.130-10.20.0.169: Microservices
  10.20.0.170-10.20.0.199: Reserved

security:
  level: High
  internet_access: Via NAT
  accessible_from:
    - WAN (specific ports: 80, 443)
    - Management VLAN (22, 443)
    - Monitoring VLAN (all)
    - Load balancer VLAN
  accessible_to:
    - Database VLAN (specific ports)
    - Cache VLAN (Redis, Memcached)
    - Queue VLAN (RabbitMQ, Kafka)
    - Internet (for external APIs)

firewall_rules:
  inbound:
    - allow: HTTP/HTTPS (80, 443) from WAN
    - allow: SSH (22) from management VLAN
    - allow: HTTPS (443) for management from management VLAN
    - allow: metrics (9100) from monitoring VLAN
    - deny: all other inbound

  outbound:
    - allow: PostgreSQL (5432) to database VLAN
    - allow: MySQL (3306) to database VLAN
    - allow: Redis (6379) to cache VLAN
    - allow: RabbitMQ (5672) to queue VLAN
    - allow: HTTPS (443) to internet (external APIs)
    - allow: DNS (53)
    - deny: all other outbound

load_balancing:
  type: round_robin
  health_checks:
    - http_get: /health
    - interval: 10s
    - timeout: 5s
    - unhealthy_threshold: 3
```

#### Database VLAN (VLAN 30)

```yaml
vlan_id: 30
name: databases
subnet: 10.30.0.0/24
gateway: 10.30.0.1
dns_servers: [10.70.0.10, 1.1.1.1]

dhcp:
  enabled: no # All database servers use static IPs

static_assignments:
  10.30.0.10-10.30.0.29: PostgreSQL servers
  10.30.0.30-10.30.0.49: MySQL/MariaDB servers
  10.30.0.50-10.30.0.69: MongoDB servers
  10.30.0.70-10.30.0.89: Redis servers
  10.30.0.90-10.30.0.109: Elasticsearch servers
  10.30.0.110-10.30.0.129: Database replicas
  10.30.0.130-10.30.0.149: Backup databases
  10.30.0.150-10.30.0.199: Reserved

security:
  level: Critical
  internet_access: None (completely isolated)
  accessible_from:
    - Application servers VLAN (specific ports)
    - Management VLAN (22 for SSH, management ports)
    - Monitoring VLAN (metrics, health checks)
    - Backup VLAN (backup traffic)
  accessible_to:
    - Database replicas (replication traffic)
    - Backup storage (backup traffic)

firewall_rules:
  inbound:
    - allow: PostgreSQL (5432) from app servers VLAN
    - allow: MySQL (3306) from app servers VLAN
    - allow: MongoDB (27017) from app servers VLAN
    - allow: Redis (6379) from app servers VLAN
    - allow: Elasticsearch (9200, 9300) from app servers VLAN
    - allow: SSH (22) from management VLAN
    - allow: metrics (9100, 9187) from monitoring VLAN
    - deny: all other inbound

  outbound:
    - allow: replication traffic to other database servers
    - allow: backup traffic to backup VLAN
    - allow: DNS (53)
    - allow: NTP (123)
    - deny: internet access
    - deny: all other outbound

high_availability:
  replication:
    postgresql:
      type: streaming_replication
      primary: 10.30.0.10
      replicas: [10.30.0.11, 10.30.0.12]
      sync_mode: asynchronous

    mysql:
      type: master_slave
      master: 10.30.0.30
      slaves: [10.30.0.31, 10.30.0.32]
      replication_mode: row-based

  connection_pooling:
    pgbouncer:
      ip: 10.30.0.110
      port: 6432
      pool_mode: transaction
      max_connections: 100

    proxysql:
      ip: 10.30.0.111
      port: 6033
      max_connections: 200

monitoring:
  - Query performance monitoring
  - Replication lag monitoring
  - Connection pool utilization
  - Disk I/O and latency
  - Backup success/failure
```

#### Development VLAN (VLAN 40)

```yaml
vlan_id: 40
name: development
subnet: 10.40.0.0/24
gateway: 10.40.0.1
dns_servers: [10.70.0.10, 1.1.1.1]

dhcp:
  enabled: yes
  range: 10.40.0.50-10.40.0.250
  lease_time: 43200 # 12 hours

static_assignments:
  10.40.0.10-10.40.0.49: Development servers

security:
  level: Medium
  internet_access: Limited (via HTTP proxy)
  accessible_from:
    - Management VLAN (22, all ports)
    - Developer workstations VLAN
  accessible_to:
    - Development databases (within same VLAN)
    - HTTP proxy for internet
    - Git servers
    - Package repositories

firewall_rules:
  inbound:
    - allow: SSH (22) from management VLAN
    - allow: all ports from developer workstations VLAN
    - deny: all other inbound

  outbound:
    - allow: HTTP/HTTPS (80, 443) via proxy
    - allow: Git (9418, 22) to internal Git servers
    - allow: DNS (53)
    - deny: direct internet access
    - deny: production VLANs (app servers, databases)

isolation:
  from_production: yes
  from_staging: yes
  from_other_dev_environments: no

notes:
  - Developers have full access within dev VLAN
  - No access to production data
  - Internet access via authenticated proxy
  - Can create temporary VMs freely
```

#### Monitoring VLAN (VLAN 70)

```yaml
vlan_id: 70
name: monitoring
subnet: 10.70.0.0/24
gateway: 10.70.0.1
dns_servers: [10.70.0.10, 1.1.1.1]

dhcp:
  enabled: no # All monitoring infrastructure uses static IPs

static_assignments:
  10.70.0.10: DNS server (internal)
  10.70.0.20: Prometheus server
  10.70.0.21: Grafana server
  10.70.0.22: Alertmanager
  10.70.0.30: Loki (log aggregation)
  10.70.0.31: Promtail (log shipper)
  10.70.0.40: Elastic APM server
  10.70.0.50: Syslog server
  10.70.0.60: SNMP collector
  10.70.0.70: Uptime monitoring (Uptime Kuma)
  10.70.0.80: Network monitoring (LibreNMS)

security:
  level: High
  internet_access: Via NAT (for alerts, webhooks)
  accessible_from:
    - All VLANs (for metrics collection, log forwarding)
    - Management VLAN (22, web UIs)
    - Developer workstations (read-only dashboards)
  accessible_to:
    - All VLANs (for active monitoring, probes)
    - Internet (for external alerts, webhooks)

firewall_rules:
  inbound:
    - allow: Prometheus metrics (9090, 9100-9999) from all VLANs
    - allow: Syslog (514 UDP/TCP) from all VLANs
    - allow: SNMP (161-162) from all VLANs
    - allow: SSH (22) from management VLAN
    - allow: web UIs (3000, 9090) from management VLAN
    - deny: all other inbound

  outbound:
    - allow: all ports to all VLANs (for active monitoring)
    - allow: HTTPS (443) to internet (for alerts, webhooks)
    - allow: SMTP (587) for email alerts
    - deny: unnecessary outbound

monitoring_targets:
  infrastructure:
    - Proxmox hosts (node_exporter, pve_exporter)
    - UniFi controller and devices (SNMP)
    - Switches and routers (SNMP)
    - Storage systems (SNMP, custom exporters)

  applications:
    - All VMs (node_exporter on port 9100)
    - PostgreSQL (postgres_exporter on port 9187)
    - MySQL (mysqld_exporter on port 9104)
    - Redis (redis_exporter on port 9121)
    - NGINX (nginx_exporter on port 9113)
    - Application metrics (custom exporters)

  logs:
    - Syslog from all systems
    - Application logs via Promtail/Loki
    - Audit logs from critical systems
```

### Advanced Network Topologies

#### DMZ (Demilitarized Zone) Pattern

```yaml
name: DMZ Architecture
description: Isolated zone for public-facing services

topology:
  external_firewall:
    interface: WAN
    ip: public IP
    rules:
      - allow: HTTP/HTTPS to DMZ
      - allow: SMTP to mail server in DMZ
      - deny: all other inbound

  dmz_vlan:
    vlan_id: 80
    subnet: 10.80.0.0/24
    gateway: 10.80.0.1
    purpose: Public-facing services

    hosts:
      - ip: 10.80.0.10
        service: web_proxy (NGINX)
        exposed_ports: [80, 443]

      - ip: 10.80.0.20
        service: mail_gateway
        exposed_ports: [25, 587, 993]

      - ip: 10.80.0.30
        service: vpn_gateway
        exposed_ports: [1194, 443]

  internal_firewall:
    interface: LAN
    rules:
      - allow: DMZ → App Servers VLAN (specific ports)
      - allow: DMZ → Database VLAN (read-only replica)
      - deny: DMZ → Management VLAN
      - deny: DMZ → other internal VLANs

security_principles:
  - DMZ has limited access to internal networks
  - Internal networks have limited access to DMZ
  - DMZ servers are hardened and closely monitored
  - All DMZ traffic is logged and analyzed
  - DMZ hosts are considered untrusted
```

#### Zero Trust Network Segmentation

```yaml
name: Zero Trust Micro-Segmentation
description: Fine-grained network segmentation based on application requirements

principles:
  - No implicit trust based on network location
  - Verify every connection attempt
  - Least privilege access
  - Micro-segmentation by application tier

implementation:
  application_groups:
    web_tier:
      vlan: 20
      allowed_outbound:
        - app_tier:8080 (application API)
        - cache_tier:6379 (Redis)
        - monitoring:9090 (Prometheus pushgateway)

      denied:
        - database_tier (no direct database access)
        - management_tier (no management access)

    app_tier:
      vlan: 21
      allowed_outbound:
        - database_tier:5432 (PostgreSQL read/write)
        - cache_tier:6379 (Redis)
        - queue_tier:5672 (RabbitMQ)
        - monitoring:9090

      denied:
        - external_internet (no direct internet)
        - management_tier

    database_tier:
      vlan: 30
      allowed_outbound:
        - backup_tier:22 (backup via SSH)
        - monitoring:9090
        - replication_tier:5432 (database replication)

      denied:
        - external_internet
        - all_other_tiers

  enforcement:
    method: firewall_rules
    technology: UniFi firewall + VLANs
    logging: all_connections
    review_frequency: weekly
```

---

## Storage Configurations

### ZFS Storage Configuration

#### ZFS Pool Layouts

##### Mirror Layout (RAID-1)

```yaml
name: ZFS Mirror (RAID-1)
description: Two-disk mirror for redundancy

configuration:
  pool_name: tank-mirror
  layout: mirror
  disks:
    - /dev/sda (2 TB NVMe)
    - /dev/sdb (2 TB NVMe)

  capacity:
    raw: 4 TB
    usable: 2 TB
    efficiency: 50%

  performance:
    read: Excellent (parallel reads from both disks)
    write: Good (limited by single disk write speed)
    iops: High

  redundancy:
    fault_tolerance: 1 disk failure
    rebuild_time: Fast (depends on disk size)

  use_cases:
    - Boot drives
    - High-performance databases
    - VM storage (fast I/O)
    - Critical data with HA requirements

zfs_create_command: |
  zpool create tank-mirror mirror /dev/sda /dev/sdb
  zfs set compression=lz4 tank-mirror
  zfs set atime=off tank-mirror
  zfs set xattr=sa tank-mirror
```

##### RAID-Z1 Layout (Similar to RAID-5)

```yaml
name: ZFS RAID-Z1
description: Distributed parity across 3+ disks

configuration:
  pool_name: tank-z1
  layout: raidz1
  disks:
    - /dev/sdc (4 TB)
    - /dev/sdd (4 TB)
    - /dev/sde (4 TB)
    - /dev/sdf (4 TB)

  capacity:
    raw: 16 TB
    usable: 12 TB
    efficiency: 75%

  performance:
    read: Good
    write: Moderate (parity calculation overhead)
    iops: Moderate

  redundancy:
    fault_tolerance: 1 disk failure
    rebuild_time: Slow (full disk rebuild)

  use_cases:
    - Large file storage
    - Media libraries
    - Backup storage
    - Archive storage

zfs_create_command: |
  zpool create tank-z1 raidz1 /dev/sdc /dev/sdd /dev/sde /dev/sdf
  zfs set compression=lz4 tank-z1
  zfs set atime=off tank-z1
  zfs create tank-z1/backups
  zfs create tank-z1/media
```

##### RAID-Z2 Layout (Similar to RAID-6)

```yaml
name: ZFS RAID-Z2
description: Double parity for higher redundancy

configuration:
  pool_name: tank-z2
  layout: raidz2
  disks:
    - /dev/sdg (8 TB)
    - /dev/sdh (8 TB)
    - /dev/sdi (8 TB)
    - /dev/sdj (8 TB)
    - /dev/sdk (8 TB)
    - /dev/sdl (8 TB)

  capacity:
    raw: 48 TB
    usable: 32 TB
    efficiency: 67%

  performance:
    read: Good
    write: Moderate (double parity overhead)
    iops: Moderate

  redundancy:
    fault_tolerance: 2 disk failures
    rebuild_time: Very slow (double parity rebuild)

  use_cases:
    - Critical data storage
    - Long-term archives
    - Large capacity requirements
    - Production storage

zfs_create_command: |
  zpool create tank-z2 raidz2 /dev/sdg /dev/sdh /dev/sdi /dev/sdj /dev/sdk /dev/sdl
  zfs set compression=lz4 tank-z2
  zfs set atime=off tank-z2
  zfs set dedup=off tank-z2
  zfs create tank-z2/production
  zfs create tank-z2/critical-data
```

#### ZFS Advanced Features

```yaml
compression:
  algorithms:
    lz4:
      compression_ratio: 2-3x (typical)
      cpu_overhead: Very low
      recommendation: Default for all datasets
      command: zfs set compression=lz4 tank/dataset

    zstd:
      compression_ratio: 3-5x (typical)
      cpu_overhead: Low to moderate
      recommendation: Archive storage, cold data
      command: zfs set compression=zstd tank/dataset

    gzip:
      compression_ratio: 4-6x (typical)
      cpu_overhead: High
      recommendation: Rarely used (zstd is better)
      command: zfs set compression=gzip-9 tank/dataset

deduplication:
  description: Eliminates duplicate blocks
  ram_requirement: ~5 GB RAM per 1 TB of unique data
  recommendation: Only use if >50% duplicate data expected
  use_cases:
    - VM template storage
    - Backup storage with many duplicates
  command: zfs set dedup=on tank/dataset
  warning: High memory usage, can cause performance issues

snapshots:
  description: Read-only point-in-time copies
  space_usage: Only changed blocks after snapshot
  use_cases:
    - Pre-upgrade snapshots
    - Hourly/daily backups
    - Quick rollback capability

  commands:
    create: zfs snapshot tank/dataset@snapshot-name
    list: zfs list -t snapshot
    rollback: zfs rollback tank/dataset@snapshot-name
    destroy: zfs destroy tank/dataset@snapshot-name

  automation:
    tool: zfs-auto-snapshot
    schedule:
      frequent: Every 15 minutes, keep 4
      hourly: Every hour, keep 24
      daily: Every day, keep 7
      weekly: Every week, keep 4
      monthly: Every month, keep 12

send_receive:
  description: Replicate datasets to another system
  use_cases:
    - Off-site backups
    - Disaster recovery
    - Migration between servers

  full_backup:
    command: zfs send tank/dataset@snap1 | ssh remote zfs receive remote-tank/dataset

  incremental_backup:
    command: zfs send -i tank/dataset@snap1 tank/dataset@snap2 | ssh remote zfs receive remote-tank/dataset

zfs_tuning:
  arc_cache:
    description: Adaptive Replacement Cache (RAM cache)
    default: 50% of system RAM
    tuning: /etc/modprobe.d/zfs.conf
    setting: options zfs zfs_arc_max=8589934592  # 8 GB

  l2arc:
    description: Level 2 ARC (SSD cache)
    use_case: Increase cache for hot data
    command: zpool add tank cache /dev/nvme0n1

  zil:
    description: ZFS Intent Log (synchronous writes)
    use_case: Speed up sync writes
    command: zpool add tank log mirror /dev/nvme1n1 /dev/nvme2n1
```

### Ceph Distributed Storage

#### Ceph Cluster Architecture

```yaml
name: Ceph Distributed Storage
description: Highly available, distributed storage cluster

components:
  mon:
    name: Monitor Nodes
    count: 3 (minimum for quorum)
    purpose: Cluster state, coordination, authentication
    specs:
      cpu: 2 vCPU
      ram: 4 GB
      disk: 50 GB SSD
      network: 1 Gbps (management)

    hosts:
      - ceph-mon-01: 10.30.0.210
      - ceph-mon-02: 10.30.0.211
      - ceph-mon-03: 10.30.0.212

  osd:
    name: Object Storage Daemons
    count: 6+ (minimum, scales horizontally)
    purpose: Store data, handle replication
    specs:
      cpu: 4 vCPU (1-2 per OSD)
      ram: 4 GB per OSD (minimum)
      disk: Dedicated disks for OSDs
      network: 10 Gbps (data, replication)

    hosts:
      - ceph-osd-01: 10.30.0.220 (4x 4TB OSDs)
      - ceph-osd-02: 10.30.0.221 (4x 4TB OSDs)
      - ceph-osd-03: 10.30.0.222 (4x 4TB OSDs)

  mgr:
    name: Manager Daemons
    count: 2 (active/standby)
    purpose: Cluster management, monitoring, orchestration
    specs:
      cpu: 2 vCPU
      ram: 4 GB
      disk: 50 GB
      network: 1 Gbps

    hosts:
      - ceph-mgr-01: 10.30.0.230
      - ceph-mgr-02: 10.30.0.231

storage_types:
  rbd:
    name: RADOS Block Device
    description: Block storage for VMs
    use_cases:
      - Proxmox VM disks
      - Kubernetes persistent volumes
      - Database storage

    features:
      - Thin provisioning
      - Snapshots
      - Cloning
      - Live migration

    proxmox_integration:
      storage_type: RBD
      pool: rbd
      content: images
      krbd: 0

  cephfs:
    name: CephFS
    description: POSIX-compliant distributed filesystem
    use_cases:
      - Shared storage for VMs
      - Home directories
      - Application data

    features:
      - Multiple active MDS servers
      - Snapshots
      - Quotas
      - Multi-tenancy

  rgw:
    name: RADOS Gateway
    description: S3/Swift compatible object storage
    use_cases:
      - Backup storage
      - Media storage
      - Application object storage

    features:
      - S3 API compatibility
      - Multi-site replication
      - Bucket versioning
      - Lifecycle policies

replication:
  replica_size: 3
  min_size: 2
  description: |
    - Data is replicated 3 times across different OSDs
    - Cluster remains operational with 2 replicas
    - Can tolerate 2 OSD/host failures

performance_tuning:
  network:
    public_network: 10.30.0.0/24  # Client traffic
    cluster_network: 10.31.0.0/24  # Replication traffic (separate VLAN)

  pg_num:
    description: Placement group count
    formula: (OSDs * 100) / replica_size
    example: (12 OSDs * 100) / 3 = 400 PGs

  bluestore:
    description: Default backend storage engine
    features:
      - Direct disk management (no filesystem)
      - Better performance than filestore
      - Native checksumming
```

### NFS Storage Configuration

#### NFS Server Setup

```yaml
name: NFS Server for VM Storage
description: Network File System for shared storage

server_configuration:
  host: nfs-01.infra.example.com
  ip: 10.30.0.200
  os: Ubuntu 22.04 LTS

  specs:
    cpu: 8 vCPU
    ram: 16 GB
    disk: 4x 4TB RAID-10 (ZFS)
    network: 10 Gbps bonded

  installed_packages:
    - nfs-kernel-server
    - zfsutils-linux

exports:
  vm_storage:
    path: /tank/vm-storage
    export: /tank/vm-storage *(rw,sync,no_subtree_check,no_root_squash)
    purpose: Proxmox VM disk storage
    permissions: rw (read-write)
    clients: 10.10.0.0/24 (Proxmox hosts)

  iso_storage:
    path: /tank/iso-templates
    export: /tank/iso-templates *(ro,sync,no_subtree_check)
    purpose: ISO images and VM templates
    permissions: ro (read-only)
    clients: 10.10.0.0/24 (Proxmox hosts)

  backup_storage:
    path: /tank/backups
    export: /tank/backups *(rw,sync,no_subtree_check,no_root_squash)
    purpose: VM backup storage
    permissions: rw
    clients: 10.10.0.0/24 (Proxmox hosts)

proxmox_integration:
  storage_type: NFS
  server: 10.30.0.200
  export: /tank/vm-storage
  content: images,rootdir
  options: vers=4.1,soft,timeo=600,retrans=5

performance_tuning:
  nfs_threads:
    default: 8
    recommended: 16-32 (for high load)
    setting: RPCNFSDCOUNT=32 in /etc/default/nfs-kernel-server

  network:
    mtu: 9000 (jumbo frames)
    bonding: active-backup or LACP
    vlan: dedicated storage VLAN

  zfs:
    recordsize: 128K (for VM storage)
    sync: standard (for reliability)
    compression: lz4 (low overhead)
```

---

## UniFi Network Patterns

### UniFi Controller Configuration

```yaml
controller:
  type: UniFi Network Application
  deployment: Docker container or dedicated VM
  version: 8.0.x (latest stable)

  specs:
    cpu: 2 vCPU
    ram: 4 GB
    disk: 32 GB
    network: Management VLAN

  configuration:
    site_name: Main Site
    country: US
    timezone: America/New_York

    adoption:
      method: Layer 3 (inform URL)
      inform_url: http://10.10.0.20:8080/inform
      ssh_credentials: stored_securely

devices:
  gateway:
    model: UniFi Dream Machine Pro (UDM-Pro)
    ip: 10.10.0.1
    purpose: Router, firewall, gateway
    interfaces:
      wan: 1 Gbps (ISP connection)
      lan: 10 Gbps SFP+ (to core switch)

    features:
      - DPI (Deep Packet Inspection)
      - IDS/IPS (Intrusion Detection/Prevention)
      - Smart Queues (QoS)
      - VPN server (L2TP, OpenVPN, WireGuard)

  core_switch:
    model: UniFi Switch Pro 48 PoE
    ip: 10.10.0.30
    purpose: Core switching, PoE for APs
    ports: 48x 1 Gbps PoE+ (30W per port)
    uplinks: 4x 10 Gbps SFP+

    configuration:
      spanning_tree: RSTP
      jumbo_frames: enabled (9000 MTU)
      link_aggregation: LACP on uplinks

  access_points:
    model: UniFi U6 Enterprise
    count: 8
    purpose: WiFi 6E coverage
    power: PoE+ from core switch

    configuration:
      band_steering: enabled
      fast_roaming: enabled
      minimum_rssi: -75 dBm
      dtim: 3 (power saving)
```

### VLAN Configuration in UniFi

```yaml
vlan_config:
  native_vlan:
    vlan_id: 1
    name: Default (Untagged)
    purpose: Management traffic (usually)
    note: Avoid using for production traffic

  tagged_vlans:
    - vlan_id: 10
      name: Management
      dhcp_server: enabled
      dhcp_range: 10.10.0.100-10.10.0.200
      dhcp_dns: [1.1.1.1, 8.8.8.8]
      ipv6: disabled

    - vlan_id: 20
      name: App-Servers
      dhcp_server: enabled
      dhcp_range: 10.20.0.100-10.20.0.200
      dhcp_dns: [10.70.0.10, 1.1.1.1]
      ipv6: disabled

    - vlan_id: 30
      name: Databases
      dhcp_server: disabled
      ipv6: disabled
      note: Static IPs only for databases

    - vlan_id: 40
      name: Development
      dhcp_server: enabled
      dhcp_range: 10.40.0.50-10.40.0.250
      dhcp_dns: [10.70.0.10, 1.1.1.1]
      ipv6: disabled

    - vlan_id: 50
      name: Guest
      dhcp_server: enabled
      dhcp_range: 10.50.0.100-10.50.0.250
      dhcp_dns: [1.1.1.1, 8.8.8.8]
      guest_policy: enabled
      isolation: client_isolation_enabled

    - vlan_id: 60
      name: IoT
      dhcp_server: enabled
      dhcp_range: 10.60.0.100-10.60.0.250
      dhcp_dns: [10.70.0.10, 1.1.1.1]
      ipv6: disabled

    - vlan_id: 70
      name: Monitoring
      dhcp_server: disabled
      ipv6: disabled
      note: Static IPs for monitoring infrastructure

port_profiles:
  trunk_to_proxmox:
    name: Proxmox Host Trunk
    native_vlan: 10 (Management)
    tagged_vlans: [10, 20, 30, 40, 70]
    speed: 10 Gbps
    link_aggregation: LACP

  access_management:
    name: Management Access
    native_vlan: 10
    tagged_vlans: []
    speed: 1 Gbps
    poe: enabled (if needed)

  access_servers:
    name: Server Access
    native_vlan: 20
    tagged_vlans: []
    speed: 10 Gbps
    poe: disabled
```

### Firewall Rules in UniFi

```yaml
firewall_rule_groups:
  internet_access_control:
    rules:
      - name: Block Database VLAN from Internet
        rule_index: 1000
        action: drop
        source: 10.30.0.0/24
        destination: any
        destination_type: internet
        protocol: all
        logging: enabled
        description: Databases should never access internet

      - name: Block Development from Production
        rule_index: 1010
        action: drop
        source: 10.40.0.0/24
        destination: [10.20.0.0/24, 10.30.0.0/24]
        protocol: all
        logging: enabled
        description: Prevent dev from accessing production

      - name: Block Guest from LAN
        rule_index: 1020
        action: drop
        source: 10.50.0.0/24
        destination: [10.10.0.0/8]
        destination_type: address_group
        protocol: all
        logging: disabled
        description: Guest network isolation

  ssh_access_control:
    rules:
      - name: Allow SSH from Management
        rule_index: 2000
        action: accept
        source: 10.10.0.0/24
        destination: any
        port: 22
        protocol: tcp
        logging: enabled

      - name: Block SSH from WAN
        rule_index: 2010
        action: drop
        source: any
        source_type: internet
        destination: any
        port: 22
        protocol: tcp
        logging: enabled
        description: Prevent SSH brute force from internet

  web_server_rules:
    rules:
      - name: Allow HTTP from WAN to App Servers
        rule_index: 3000
        action: accept
        source: any
        source_type: internet
        destination: 10.20.0.0/24
        ports: [80, 443]
        protocol: tcp
        logging: disabled

      - name: Allow HTTPS Management from WAN
        rule_index: 3010
        action: accept
        source: any
        source_type: internet
        destination: 10.10.0.20
        port: 443
        protocol: tcp
        logging: enabled
        description: Allow UniFi controller access

  database_access:
    rules:
      - name: Allow PostgreSQL from App Servers
        rule_index: 4000
        action: accept
        source: 10.20.0.0/24
        destination: 10.30.0.0/24
        port: 5432
        protocol: tcp
        logging: disabled

      - name: Allow MySQL from App Servers
        rule_index: 4010
        action: accept
        source: 10.20.0.0/24
        destination: 10.30.0.0/24
        port: 3306
        protocol: tcp
        logging: disabled

      - name: Allow Redis from App Servers
        rule_index: 4020
        action: accept
        source: 10.20.0.0/24
        destination: 10.30.0.0/24
        port: 6379
        protocol: tcp
        logging: disabled

  monitoring_rules:
    rules:
      - name: Allow Monitoring to All VLANs
        rule_index: 5000
        action: accept
        source: 10.70.0.0/24
        destination: any
        ports: [22, 161, 162, 9090, 9100, 3000]
        protocol: tcp
        logging: disabled

      - name: Allow Syslog to Monitoring
        rule_index: 5010
        action: accept
        source: any
        destination: 10.70.0.0/24
        port: 514
        protocol: udp
        logging: disabled

traffic_rules:
  smart_queues:
    wan_download: 950 Mbps
    wan_upload: 40 Mbps

    prioritization:
      high_priority:
        - VoIP (ports 5060, 10000-20000)
        - Video conferencing (Zoom, Teams)
        - DNS (port 53)

      medium_priority:
        - HTTP/HTTPS (ports 80, 443)
        - SSH (port 22)
        - Email (ports 25, 587, 993)

      low_priority:
        - Bulk downloads
        - Streaming (Netflix, YouTube)
        - Torrents
```

### WiFi Configuration

```yaml
wifi_networks:
  corporate:
    ssid: Corporate-WiFi
    security: WPA3-Enterprise
    authentication: RADIUS
    vlan: 20 (App Servers VLAN)

    radius_server:
      ip: 10.10.0.100
      port: 1812
      secret: stored_securely

    settings:
      band: 5 GHz (primary), 2.4 GHz (fallback)
      channel_width: 80 MHz (5 GHz), 20 MHz (2.4 GHz)
      transmit_power: medium
      minimum_rssi: -75 dBm
      fast_roaming: enabled
      pmf: required

  guest:
    ssid: Guest-WiFi
    security: WPA2-Personal
    password: stored_securely
    vlan: 50 (Guest VLAN)

    settings:
      band: 5 GHz (primary), 2.4 GHz (fallback)
      channel_width: 40 MHz
      transmit_power: high
      guest_policy: enabled
      client_isolation: enabled
      captive_portal: optional
      bandwidth_limit: 10 Mbps per client

  iot:
    ssid: IoT-Devices
    security: WPA2-Personal
    password: stored_securely
    vlan: 60 (IoT VLAN)

    settings:
      band: 2.4 GHz only (better range, IoT compatibility)
      channel_width: 20 MHz
      transmit_power: medium
      client_isolation: enabled
      minimum_rssi: -80 dBm

wireless_optimization:
  channel_selection: auto (DFS channels allowed)
  transmit_power: auto (adjust based on environment)
  band_steering: enabled (prefer 5 GHz)
  airtime_fairness: enabled
  multicast_enhancement: enabled
  uapsd: enabled (power saving)
```

---

## Cloudflare Integration

### DNS Management Patterns

```yaml
dns_zones:
  primary_domain:
    zone: example.com
    nameservers:
      - ava.ns.cloudflare.com
      - reza.ns.cloudflare.com

    record_types:
      a_records:
        - name: "@"
          value: 203.0.113.10
          ttl: 300
          proxied: yes
          comment: Main website

        - name: "www"
          value: 203.0.113.10
          ttl: 300
          proxied: yes
          comment: WWW alias

        - name: "api"
          value: 203.0.113.20
          ttl: 300
          proxied: yes
          comment: API endpoint

      cname_records:
        - name: "blog"
          value: "example.com"
          ttl: 300
          proxied: yes

        - name: "shop"
          value: "example.com"
          ttl: 300
          proxied: yes

      mx_records:
        - name: "@"
          value: "mail.example.com"
          priority: 10
          ttl: 3600

        - name: "@"
          value: "mail2.example.com"
          priority: 20
          ttl: 3600

      txt_records:
        - name: "@"
          value: "v=spf1 include:_spf.google.com ~all"
          ttl: 3600
          comment: SPF record for email

        - name: "_dmarc"
          value: "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"
          ttl: 3600
          comment: DMARC policy

  internal_domain:
    zone: internal.example.com
    nameservers: Cloudflare

    record_types:
      a_records:
        - name: "proxmox-01"
          value: 10.10.0.10
          ttl: 300
          proxied: no
          comment: Proxmox host 1

        - name: "unifi"
          value: 10.10.0.20
          ttl: 300
          proxied: no
          comment: UniFi controller

        - name: "grafana"
          value: 10.70.0.21
          ttl: 300
          proxied: no
          comment: Grafana dashboard

dns_record_management:
  naming_conventions:
    production: "{service}-prod-{number}.example.com"
    staging: "{service}-staging-{number}.example.com"
    development: "{service}-dev-{number}.dev.example.com"
    infrastructure: "{type}-{location}-{number}.infra.example.com"

  ttl_guidelines:
    frequent_changes: 300 (5 minutes)
    standard: 3600 (1 hour)
    stable: 86400 (24 hours)

  proxy_settings:
    public_services: proxied (orange cloud)
    internal_services: dns_only (gray cloud)
    api_endpoints: proxied (for DDoS protection)
    direct_access_needed: dns_only
```

### SSL/TLS Configuration

```yaml
ssl_settings:
  mode: Full (Strict)
  description: End-to-end encryption with valid certificates

  certificate_options:
    universal_ssl:
      type: Cloudflare managed
      coverage: example.com, *.example.com
      validity: Auto-renewed
      cost: Free
      recommendation: Default for most cases

    advanced_certificate:
      type: Cloudflare managed
      coverage: Multiple subdomains, wildcards
      validity: Auto-renewed
      cost: $10/month
      recommendation: Complex subdomain structures

    custom_certificate:
      type: User uploaded
      coverage: User-defined
      validity: User managed
      recommendation: Specific compliance requirements

  tls_versions:
    minimum: TLS 1.2
    recommended: TLS 1.3
    deprecated: [TLS 1.0, TLS 1.1, SSL 3.0]

  ciphers:
    modern: TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256
    compatible: Add TLS 1.2 ciphers for compatibility

  hsts:
    enabled: yes
    max_age: 31536000 (1 year)
    include_subdomains: yes
    preload: yes

  always_use_https:
    enabled: yes
    description: Automatically redirect HTTP to HTTPS

origin_certificates:
  type: Cloudflare Origin CA
  validity: 15 years
  installation: On origin server (NGINX, Apache)

  generation:
    hostnames: [example.com, *.example.com]
    key_format: RSA 2048
    certificate_format: PEM

  nginx_config: |
    ssl_certificate /etc/ssl/certs/origin-cert.pem;
    ssl_certificate_key /etc/ssl/private/origin-key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
```

### Cloudflare Tunnels (Zero Trust)

```yaml
tunnels:
  web_application_tunnel:
    tunnel_name: web-app-tunnel
    tunnel_id: <generated_uuid>

    connector:
      deployment: Docker container on origin server
      ip: 10.20.0.10
      health_check: enabled

    ingress_rules:
      - hostname: app.example.com
        service: http://localhost:3000
        origin_request:
          connect_timeout: 30s
          no_tls_verify: false

      - hostname: api.example.com
        service: http://localhost:8080
        origin_request:
          connect_timeout: 30s
          no_tls_verify: false

      - service: http_status:404
        description: Catch-all rule

  ssh_tunnel:
    tunnel_name: ssh-access-tunnel
    tunnel_id: <generated_uuid>

    connector:
      deployment: Docker container on bastion host
      ip: 10.10.0.50

    ingress_rules:
      - hostname: ssh.example.com
        service: ssh://localhost:22

      - service: http_status:404

  private_network_tunnel:
    tunnel_name: private-network-tunnel
    tunnel_id: <generated_uuid>

    connector:
      deployment: VM in management VLAN
      ip: 10.10.0.60

    ingress_rules:
      - service: tcp://10.10.0.0/24
        description: Route entire management VLAN through tunnel

      - service: tcp://10.20.0.0/24
        description: Route app servers through tunnel

tunnel_deployment:
  docker_compose: |
    version: '3.8'
    services:
      cloudflared:
        image: cloudflare/cloudflared:latest
        restart: unless-stopped
        command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
        environment:
          - TUNNEL_TOKEN=${TUNNEL_TOKEN}
        networks:
          - host

  systemd_service: |
    [Unit]
    Description=Cloudflare Tunnel
    After=network.target

    [Service]
    Type=simple
    ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target

access_policies:
  application_access:
    name: Web App Access Policy
    decision: Allow

    include:
      - email_domains: [example.com]
      - email: admin@example.com

    exclude:
      - email: contractor@example.com

    require:
      - authentication_method: Google Workspace
      - country: [US, CA]

  ssh_access:
    name: SSH Access Policy
    decision: Allow

    include:
      - email: sysadmin@example.com

    require:
      - authentication_method: GitHub
      - device_posture: Managed device
```

### Cloudflare Caching & Performance

```yaml
caching_rules:
  static_assets:
    match:
      file_extensions: [css, js, jpg, jpeg, png, gif, svg, woff, woff2, ttf, eot, ico]

    cache_settings:
      edge_ttl: 2592000  # 30 days
      browser_ttl: 31536000  # 1 year
      cache_level: aggressive
      origin_error_page_pass_thru: disabled

  api_responses:
    match:
      url_pattern: /api/v1/public/*
      request_method: GET

    cache_settings:
      edge_ttl: 300  # 5 minutes
      browser_ttl: 0  # No browser cache
      cache_level: standard
      bypass_cache_on_cookie: session_id

  dynamic_content:
    match:
      url_pattern: /api/*, /admin/*, /user/*

    cache_settings:
      cache_level: bypass
      description: Always fetch from origin

page_rules:
  - url: example.com/*
    settings:
      always_use_https: on
      automatic_https_rewrites: on

  - url: static.example.com/*
    settings:
      cache_level: cache_everything
      edge_cache_ttl: 2592000
      browser_cache_ttl: 31536000

  - url: api.example.com/*
    settings:
      cache_level: bypass
      security_level: high

performance_features:
  auto_minify:
    javascript: yes
    css: yes
    html: yes

  brotli_compression:
    enabled: yes
    description: Better compression than gzip

  http2:
    enabled: yes

  http3:
    enabled: yes
    description: QUIC protocol for faster connections

  early_hints:
    enabled: yes
    description: Send 103 Early Hints for faster page loads

  rocket_loader:
    enabled: no
    description: Can break some JavaScript, test before enabling

  mirage:
    enabled: yes
    description: Lazy load images for mobile

  polish:
    enabled: no
    tier: paid_feature
    description: Image optimization
```

### Cloudflare Security

```yaml
firewall_rules:
  block_bad_bots:
    expression: (cf.client.bot) and not (cf.verified_bot_category in {"Search Engine Crawler" "Monitoring & Analytics"})
    action: block
    description: Block malicious bots but allow good bots

  rate_limiting_api:
    expression: (http.request.uri.path contains "/api/")
    action: rate_limit
    rate_limit:
      requests_per_minute: 100
      period: 60
    description: Rate limit API endpoints

  block_countries:
    expression: (ip.geoip.country in {"CN" "RU" "KP"})
    action: block
    description: Block traffic from specific countries

  challenge_suspicious:
    expression: (cf.threat_score gt 10)
    action: challenge
    description: CAPTCHA for suspicious traffic

waf_rules:
  managed_rulesets:
    - cloudflare_managed_ruleset: enabled
      sensitivity: medium

    - owasp_core_ruleset: enabled
      paranoia_level: 2

    - cloudflare_specials: enabled

  custom_rules:
    - name: Block SQL Injection
      expression: (http.request.uri.query contains "union select" or http.request.uri.query contains "drop table")
      action: block

    - name: Block XSS Attempts
      expression: (http.request.uri.query contains "<script>" or http.request.body.raw contains "<script>")
      action: block

ddos_protection:
  advanced_ddos:
    enabled: yes
    sensitivity: medium

  l7_ddos:
    enabled: yes
    description: Application layer DDoS protection

  l3_l4_ddos:
    enabled: yes
    description: Network and transport layer protection

bot_management:
  bot_fight_mode: enabled
  super_bot_fight_mode: disabled (paid feature)

  allowed_bots:
    - GoogleBot
    - BingBot
    - SlackBot
    - LinkedInBot

  blocked_user_agents:
    - curl
    - wget
    - python-requests (unless allowlisted)
```

---

## High Availability Patterns

### Database High Availability

#### PostgreSQL Streaming Replication

```yaml
architecture: Primary-Replica with automatic failover
technology: PostgreSQL Streaming Replication + Patroni
minimum_nodes: 3 (1 primary, 2 replicas)

nodes:
  primary:
    hostname: db-prod-01
    ip: 10.30.0.10
    role: read-write
    specs:
      cpu: 16 vCPU
      ram: 32 GB
      disk: 500 GB NVMe (ZFS mirror)

  replica_1:
    hostname: db-prod-02
    ip: 10.30.0.11
    role: read-only
    replication: asynchronous streaming
    specs:
      cpu: 16 vCPU
      ram: 32 GB
      disk: 500 GB NVMe (ZFS mirror)

  replica_2:
    hostname: db-prod-03
    ip: 10.30.0.12
    role: read-only
    replication: asynchronous streaming
    specs:
      cpu: 16 vCPU
      ram: 32 GB
      disk: 500 GB NVMe (ZFS mirror)

patroni_configuration:
  scope: postgres-cluster-prod
  namespace: /service/

  etcd_cluster:
    - host: 10.10.0.100
      port: 2379
    - host: 10.10.0.101
      port: 2379
    - host: 10.10.0.102
      port: 2379

  postgresql_parameters:
    max_connections: 200
    shared_buffers: 8GB
    effective_cache_size: 24GB
    maintenance_work_mem: 2GB
    wal_level: replica
    max_wal_senders: 10
    max_replication_slots: 10
    hot_standby: on

connection_pooling:
  tool: PgBouncer
  deployment: Separate VM
  ip: 10.30.0.110
  port: 6432

  configuration:
    pool_mode: transaction
    max_client_conn: 1000
    default_pool_size: 25
    reserve_pool_size: 5
    reserve_pool_timeout: 3

load_balancing:
  read_write: db-prod-01:5432 (primary only)
  read_only:
    - db-prod-02:5432 (replica 1)
    - db-prod-03:5432 (replica 2)
  method: round_robin or least_connections

failover:
  automatic: yes (via Patroni)
  trigger: Primary node failure detection
  process:
    1. Patroni detects primary failure
    2. Etcd achieves quorum on new leader
    3. Most up-to-date replica promoted to primary
    4. Other replicas reconfigure to follow new primary
    5. Applications reconnect to new primary

  downtime: 30-60 seconds typical
  data_loss: minimal (only uncommitted transactions)

backup_strategy:
  full_backups:
    frequency: daily
    time: 02:00 UTC
    retention: 7 days
    method: pg_basebackup to backup storage

  wal_archiving:
    enabled: yes
    destination: /backup/wal-archive/
    retention: 7 days

  point_in_time_recovery:
    enabled: yes
    retention: 7 days
```

#### MySQL/MariaDB Galera Cluster

```yaml
architecture: Multi-master synchronous replication
technology: Galera Cluster
minimum_nodes: 3 (odd number for quorum)

nodes:
  node_1:
    hostname: mysql-prod-01
    ip: 10.30.0.30
    role: read-write
    specs:
      cpu: 8 vCPU
      ram: 16 GB
      disk: 200 GB NVMe

  node_2:
    hostname: mysql-prod-02
    ip: 10.30.0.31
    role: read-write
    specs:
      cpu: 8 vCPU
      ram: 16 GB
      disk: 200 GB NVMe

  node_3:
    hostname: mysql-prod-03
    ip: 10.30.0.32
    role: read-write
    specs:
      cpu: 8 vCPU
      ram: 16 GB
      disk: 200 GB NVMe

galera_configuration:
  cluster_name: mysql-cluster-prod

  wsrep_settings:
    wsrep_cluster_address: gcomm://10.30.0.30,10.30.0.31,10.30.0.32
    wsrep_provider: /usr/lib/galera/libgalera_smm.so
    wsrep_sst_method: mariabackup
    wsrep_slave_threads: 4

  replication:
    type: synchronous
    certification: optimistic
    flow_control: automatic

load_balancing:
  tool: ProxySQL
  deployment: Separate VM
  ip: 10.30.0.111
  port: 6033

  configuration:
    hostgroups:
      writer_hostgroup: 10
      reader_hostgroup: 20

    servers:
      - address: 10.30.0.30, hostgroup: 10, weight: 1
      - address: 10.30.0.31, hostgroup: 10, weight: 1
      - address: 10.30.0.32, hostgroup: 10, weight: 1
      - address: 10.30.0.30, hostgroup: 20, weight: 1
      - address: 10.30.0.31, hostgroup: 20, weight: 1
      - address: 10.30.0.32, hostgroup: 20, weight: 1

    query_rules:
      - rule_id: 1, match_pattern: "^SELECT.*FOR UPDATE", destination_hostgroup: 10
      - rule_id: 2, match_pattern: "^SELECT", destination_hostgroup: 20

failover:
  automatic: yes (quorum-based)
  process:
    1. Node failure detected
    2. Remaining nodes maintain quorum
    3. Failed node removed from cluster
    4. ProxySQL automatically routes around failed node
    5. No manual intervention required

  downtime: 0 seconds (seamless)
  data_loss: none (synchronous replication)
```

### Application Server High Availability

#### Load Balanced Web Servers

```yaml
architecture: Active-active load balancing
load_balancer: NGINX or Cloudflare Load Balancing
minimum_nodes: 2

nodes:
  web_1:
    hostname: web-prod-01
    ip: 10.20.0.10
    specs:
      cpu: 4 vCPU
      ram: 8 GB
      disk: 100 GB
    health_check_endpoint: /health

  web_2:
    hostname: web-prod-02
    ip: 10.20.0.11
    specs:
      cpu: 4 vCPU
      ram: 8 GB
      disk: 100 GB
    health_check_endpoint: /health

  web_3:
    hostname: web-prod-03
    ip: 10.20.0.12
    specs:
      cpu: 4 vCPU
      ram: 8 GB
      disk: 100 GB
    health_check_endpoint: /health

nginx_load_balancer:
  ip: 10.20.0.5

  upstream_config: |
    upstream web_backend {
      least_conn;  # or ip_hash for sticky sessions

      server 10.20.0.10:80 max_fails=3 fail_timeout=30s;
      server 10.20.0.11:80 max_fails=3 fail_timeout=30s;
      server 10.20.0.12:80 max_fails=3 fail_timeout=30s;
    }

    server {
      listen 80;
      server_name app.example.com;

      location / {
        proxy_pass http://web_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
      }

      location /health {
        access_log off;
        return 200 "healthy\n";
      }
    }

cloudflare_load_balancing:
  pool_name: web-prod-pool

  origins:
    - name: web-prod-01
      address: 10.20.0.10
      weight: 1
      enabled: yes

    - name: web-prod-02
      address: 10.20.0.11
      weight: 1
      enabled: yes

    - name: web-prod-03
      address: 10.20.0.12
      weight: 1
      enabled: yes

  health_check:
    type: http
    path: /health
    interval: 60 seconds
    timeout: 5 seconds
    retries: 2
    expected_codes: 200

  steering_policy: random  # or least_outstanding_requests
  session_affinity: none  # or cookie, ip_cookie

deployment_strategy:
  type: Rolling update
  process:
    1. Remove web-prod-01 from load balancer
    2. Deploy new version to web-prod-01
    3. Verify health check passes
    4. Add web-prod-01 back to load balancer
    5. Repeat for web-prod-02 and web-prod-03

  downtime: 0 seconds (seamless)
  rollback: Reverse the process
```

### Proxmox High Availability Cluster

```yaml
architecture: Proxmox HA Cluster with shared storage
minimum_nodes: 3 (for quorum)

nodes:
  pve_1:
    hostname: proxmox-dc1-01
    ip: 10.10.0.10
    specs:
      cpu: 2x Intel Xeon (32 cores total)
      ram: 128 GB
      disk: 2x 500 GB NVMe (OS, ZFS mirror)
      network: 2x 10 Gbps (bonded)

  pve_2:
    hostname: proxmox-dc1-02
    ip: 10.10.0.11
    specs:
      cpu: 2x Intel Xeon (32 cores total)
      ram: 128 GB
      disk: 2x 500 GB NVMe (OS, ZFS mirror)
      network: 2x 10 Gbps (bonded)

  pve_3:
    hostname: proxmox-dc1-03
    ip: 10.10.0.12
    specs:
      cpu: 2x Intel Xeon (32 cores total)
      ram: 128 GB
      disk: 2x 500 GB NVMe (OS, ZFS mirror)
      network: 2x 10 Gbps (bonded)

shared_storage:
  type: Ceph RBD
  replication: 3

  pools:
    - name: vm-storage
      size: 10 TB usable
      purpose: VM disks
      pg_num: 512

    - name: backup-storage
      size: 20 TB usable
      purpose: VM backups
      pg_num: 256

ha_configuration:
  manager: Proxmox HA Manager
  quorum: 2 nodes (simple majority)

  ha_groups:
    - name: ha-group-production
      nodes: pve-1 (priority 100), pve-2 (priority 90), pve-3 (priority 80)
      restricted: no
      nofailback: no

  ha_resources:
    - vm: 100 (db-prod-01)
      group: ha-group-production
      max_restart: 3
      max_relocate: 3
      state: started

    - vm: 101 (web-prod-01)
      group: ha-group-production
      max_restart: 3
      max_relocate: 3
      state: started

fencing:
  method: Watchdog timer
  device: /dev/watchdog
  action: Reboot node if HA manager loses quorum

failover:
  trigger: Node failure, network partition, or manual migration
  process:
    1. Watchdog detects node failure
    2. Quorum determines if fencing needed
    3. Failed node fenced (rebooted)
    4. VMs migrated to healthy nodes
    5. VMs started on new nodes

  downtime: 60-120 seconds (VM restart time)
  automation: Fully automatic

live_migration:
  enabled: yes
  storage_requirement: Shared storage (Ceph)
  network_requirement: 10 Gbps minimum

  use_cases:
    - Planned maintenance
    - Load balancing
    - Hardware upgrades

  downtime: 0 seconds (seamless)
```

---

## Disaster Recovery Configurations

### Backup Strategy

#### VM-Level Backups

```yaml
proxmox_backup:
  backup_storage: NFS or PBS (Proxmox Backup Server)

  schedules:
    production_daily:
      vms: [100-199] # Production VMs
      schedule: "02:00"
      dow: "mon,tue,wed,thu,fri,sat,sun"
      mode: snapshot
      compression: zstd
      retention:
        keep_last: 7
        keep_daily: 7
        keep_weekly: 4
        keep_monthly: 3

    development_weekly:
      vms: [200-299] # Dev VMs
      schedule: "22:00"
      dow: "fri"
      mode: snapshot
      compression: lzo
      retention:
        keep_last: 2
        keep_weekly: 4

backup_modes:
  snapshot:
    description: Backup running VM using snapshot
    downtime: 0 seconds
    speed: Fast
    use_case: Production VMs that can't be stopped

  suspend:
    description: Suspend VM, backup, resume
    downtime: 30-60 seconds
    speed: Fast
    use_case: VMs with sensitive state

  stop:
    description: Stop VM, backup, start
    downtime: 2-5 minutes
    speed: Fastest
    use_case: VMs that can tolerate downtime

proxmox_backup_server:
  deployment: Dedicated VM or physical server
  specs:
    cpu: 8 vCPU
    ram: 16 GB
    disk: 20 TB (RAID-6 or ZFS RAID-Z2)

  features:
    - Deduplication (block-level)
    - Incremental backups
    - Encryption
    - Verification jobs
    - Sync to remote PBS (off-site)

  retention_policy:
    production:
      keep_last: 7
      keep_hourly: 24
      keep_daily: 7
      keep_weekly: 4
      keep_monthly: 12
      keep_yearly: 3
```

#### Database-Specific Backups

```yaml
postgresql_backup:
  method: pg_dump + WAL archiving

  full_backup:
    tool: pg_basebackup
    schedule: Daily at 02:00 UTC
    destination: /backup/postgresql/full/
    retention: 7 days
    encryption: yes (gpg)

  wal_archiving:
    enabled: yes
    destination: /backup/postgresql/wal/
    retention: 7 days
    archive_command: "test ! -f /backup/postgresql/wal/%f && cp %p /backup/postgresql/wal/%f"

  point_in_time_recovery:
    enabled: yes
    recovery_window: 7 days
    restore_command: "cp /backup/postgresql/wal/%f %p"

  logical_backup:
    tool: pg_dump
    schedule: Daily at 03:00 UTC
    format: custom (-Fc)
    destination: /backup/postgresql/logical/
    retention: 30 days

    command: |
      pg_dump -U postgres -Fc -f /backup/postgresql/logical/db-$(date +%Y%m%d).dump production_db

mysql_backup:
  method: mysqldump + binary logs

  full_backup:
    tool: mysqldump
    schedule: Daily at 02:00 UTC
    destination: /backup/mysql/full/
    retention: 7 days

    command: |
      mysqldump --single-transaction --routines --triggers --events --all-databases \
        --master-data=2 | gzip > /backup/mysql/full/all-databases-$(date +%Y%m%d).sql.gz

  incremental_backup:
    method: Binary log archiving
    enabled: yes
    destination: /backup/mysql/binlog/
    retention: 7 days

    mysql_config: |
      [mysqld]
      log_bin = /var/log/mysql/mysql-bin.log
      expire_logs_days = 7
      max_binlog_size = 100M
```

### Off-Site Replication

#### Rsync to Remote Site

```yaml
rsync_replication:
  source: Local backup storage
  destination: Remote site (different geographic location)

  configuration:
    schedule: Daily at 04:00 UTC
    method: rsync over SSH
    bandwidth_limit: 10 MB/s
    retention: Match local retention policy

  script: |
    #!/bin/bash
    REMOTE_HOST="backup-remote.example.com"
    REMOTE_PATH="/backup/replicated/"
    LOCAL_PATH="/backup/postgresql/"

    rsync -avz --bwlimit=10240 \
      --delete --delete-excluded \
      -e "ssh -i /root/.ssh/backup_key" \
      $LOCAL_PATH $REMOTE_HOST:$REMOTE_PATH

  monitoring:
    - Check rsync exit code
    - Verify file count and size
    - Alert on failures
```

#### Proxmox Backup Server Sync

```yaml
pbs_sync:
  source_pbs: PBS Primary (10.30.0.200)
  destination_pbs: PBS Off-Site (203.0.113.100)

  sync_jobs:
    production_vms:
      source_datastore: backup-prod
      destination_datastore: backup-prod-offsite
      schedule: Daily at 03:00 UTC
      remove_vanished: yes

      bandwidth_limit: 50 MB/s
      rate_in: 100 MB/s

  verification:
    schedule: Weekly on Sunday
    outdated_after: 30 days
```

### Disaster Recovery Runbook

```yaml
disaster_scenarios:
  single_vm_failure:
    impact: One VM unavailable
    rto: 15 minutes (Recovery Time Objective)
    rpo: 24 hours (Recovery Point Objective)

    recovery_steps:
      1. Identify failed VM and cause
      2. If hardware failure, migrate to healthy host
      3. If corruption, restore from latest backup
      4. Verify VM functionality
      5. Update monitoring and documentation

  single_node_failure:
    impact: VMs on failed node unavailable (if not HA)
    rto: 30 minutes
    rpo: 24 hours

    recovery_steps:
      1. Verify node is truly failed (not network partition)
      2. If Proxmox HA enabled, VMs auto-migrate
      3. If no HA, manually restore VMs from backup to healthy node
      4. Verify all services operational
      5. Investigate and repair failed node

  database_corruption:
    impact: Database service unavailable
    rto: 2 hours
    rpo: 0-24 hours (depending on backup strategy)

    recovery_steps:
      1. Stop application to prevent further corruption
      2. Assess extent of corruption
      3. If replication enabled, promote replica to primary
      4. If no replication, restore from backup
      5. Apply WAL logs for point-in-time recovery (PostgreSQL)
      6. Verify data integrity
      7. Restart applications
      8. Monitor for issues

  complete_site_failure:
    impact: All services unavailable
    rto: 4-8 hours
    rpo: 24 hours

    recovery_steps:
      1. Activate disaster recovery site
      2. Restore critical VMs from off-site backups
      3. Reconfigure DNS to point to DR site
      4. Verify services operational
      5. Monitor and stabilize
      6. Plan recovery or rebuild of primary site

    prerequisites:
      - Off-site backups available
      - DR site infrastructure ready
      - DNS can be updated quickly (Cloudflare)
      - Documentation accessible (not only on primary site)
```

---

## Cost Optimization Strategies

### Resource Right-Sizing

```yaml
monitoring:
  tools: Prometheus, Grafana
  metrics:
    - CPU utilization (average, peak)
    - Memory utilization (average, peak)
    - Disk I/O (IOPS, throughput)
    - Network I/O (bandwidth)

  collection_interval: 15 seconds
  retention: 90 days

analysis:
  frequency: Monthly
  criteria:
    underutilized:
      cpu: <30% average over 30 days
      ram: <40% average over 30 days
      action: Downsize VM

    overutilized:
      cpu: >80% peak regularly
      ram: >85% peak regularly
      action: Upsize VM or add horizontal scaling

    correctly_sized:
      cpu: 40-70% average
      ram: 50-80% average
      action: No change

recommendations:
  small_to_tiny:
    savings: 50% resources
    risk: Low (if consistently underutilized)

  medium_to_small:
    savings: 50% resources
    risk: Medium (verify workload patterns)

  large_to_medium:
    savings: 50% resources
    risk: High (verify not using burst capacity)

implementation:
  process:
    1. Identify candidate VMs
    2. Review with application owners
    3. Schedule maintenance window
    4. Take snapshot before resizing
    5. Resize VM resources
    6. Monitor for 1 week
    7. Rollback if issues, otherwise confirm
```

### Storage Optimization

```yaml
thin_provisioning:
  description: Allocate storage on-demand rather than pre-allocated
  savings: 30-50% storage capacity

  implementation:
    proxmox: Use qcow2 format with thin provisioning
    ceph: Enable thin provisioning on RBD pools

  monitoring:
    - Track actual vs. allocated storage
    - Alert when thin pool reaches 80% full
    - Plan for capacity expansion

compression:
  zfs:
    algorithm: lz4 (default)
    compression_ratio: 2-3x typical
    cpu_overhead: <3%
    recommendation: Enable on all datasets

  ceph:
    algorithm: snappy or zstd
    compression_ratio: 2-4x
    compression_mode: aggressive
    recommendation: Enable on RBD pools

deduplication:
  zfs:
    savings: Variable (5-50% depending on data)
    ram_cost: 5 GB per 1 TB deduplicated data
    recommendation: Only for VM template storage

  ceph:
    not_available: Use compression instead

backup_optimization:
  incremental_backups:
    description: Only backup changed blocks
    savings: 70-90% backup storage
    tool: Proxmox Backup Server (built-in)

  backup_retention:
    development: 2 weeks max
    staging: 4 weeks max
    production: 3 months daily, 1 year monthly

  backup_compression:
    algorithm: zstd (best ratio)
    level: 3 (balanced speed/ratio)
    savings: 50-70% backup storage
```

### Network Cost Optimization

```yaml
cloudflare_caching:
  static_assets:
    cache_hit_ratio: 90-95%
    bandwidth_savings: 80-90%

    configuration:
      edge_ttl: 30 days
      browser_ttl: 1 year
      file_types: css, js, images, fonts

  api_responses:
    cache_hit_ratio: 50-70%
    bandwidth_savings: 40-60%

    configuration:
      edge_ttl: 5 minutes
      cache_key: Include query string
      bypass: POST, PUT, DELETE methods

cloudflare_r2:
  description: S3-compatible object storage (no egress fees)
  use_cases:
    - Large file downloads
    - Media storage
    - Backup storage

  savings: 90% vs. traditional cloud storage with egress

image_optimization:
  tools:
    - Cloudflare Polish (paid)
    - ImageOptim
    - TinyPNG API

  formats:
    - WebP (30% smaller than JPEG)
    - AVIF (50% smaller than JPEG)

  savings: 50-70% image bandwidth
```

### Power and Cooling

```yaml
vm_consolidation:
  description: Consolidate VMs to fewer physical hosts
  method: Live migration during low-usage periods

  savings:
    - Fewer hosts powered on
    - Reduced cooling requirements
    - 20-30% power cost reduction

  implementation:
    - Identify low-utilization hosts
    - Migrate VMs to more utilized hosts
    - Power down or suspend unused hosts
    - Maintain capacity for failover

power_management:
  cpu_scaling:
    method: CPU frequency scaling
    mode: powersave or ondemand
    savings: 10-20% CPU power

    configuration: |
      cpufreq-set -g ondemand

  disk_spindown:
    method: Spin down idle HDDs
    applicable: Archive storage only
    savings: 5-10 watts per disk

    configuration: |
      hdparm -S 120 /dev/sdX  # Spindown after 10 minutes

cooling_optimization:
  temperature_targets:
    cpu: 70°C max
    disk: 45°C max
    ambient: 22-24°C

  strategies:
    - Hot aisle / cold aisle layout
    - Blanking panels in unused rack spaces
    - Adjust CRAC unit setpoints
    - Use economizers when outside temp allows
```

---

## Security Hardening Checklists

### VM-Level Security

```yaml
os_hardening:
  ubuntu_22_04:
    updates:
      - task: Enable unattended-upgrades
        command: apt install unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades

      - task: Configure automatic security updates
        config: /etc/apt/apt.conf.d/50unattended-upgrades
        settings: |
          Unattended-Upgrade::Allowed-Origins {
            "${distro_id}:${distro_codename}-security";
          };

    ssh_hardening:
      - task: Disable root login
        config: /etc/ssh/sshd_config
        setting: PermitRootLogin no

      - task: Disable password authentication
        config: /etc/ssh/sshd_config
        setting: PasswordAuthentication no

      - task: Use SSH keys only
        setting: PubkeyAuthentication yes

      - task: Change default SSH port (optional)
        setting: Port 2222

      - task: Limit SSH access by user
        setting: AllowUsers admin sysadmin

      - task: Enable SSH key-based 2FA (optional)
        command: apt install libpam-google-authenticator

    firewall:
      - task: Enable UFW firewall
        commands:
          - ufw default deny incoming
          - ufw default allow outgoing
          - ufw allow from 10.10.0.0/24 to any port 22
          - ufw enable

      - task: Configure iptables (alternative)
        commands:
          - iptables -P INPUT DROP
          - iptables -P FORWARD DROP
          - iptables -P OUTPUT ACCEPT
          - iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
          - iptables -A INPUT -s 10.10.0.0/24 -p tcp --dport 22 -j ACCEPT

    fail2ban:
      - task: Install fail2ban
        command: apt install fail2ban

      - task: Configure SSH jail
        config: /etc/fail2ban/jail.local
        settings: |
          [sshd]
          enabled = true
          port = 22
          filter = sshd
          logpath = /var/log/auth.log
          maxretry = 3
          bantime = 3600
          findtime = 600

    kernel_hardening:
      - task: Disable IPv6 (if not used)
        config: /etc/sysctl.conf
        settings: |
          net.ipv6.conf.all.disable_ipv6 = 1
          net.ipv6.conf.default.disable_ipv6 = 1

      - task: Enable SYN cookies (DDoS protection)
        setting: net.ipv4.tcp_syncookies = 1

      - task: Disable IP forwarding (unless router)
        setting: net.ipv4.ip_forward = 0

      - task: Ignore ICMP redirects
        setting: net.ipv4.conf.all.accept_redirects = 0

    user_management:
      - task: Create non-root admin user
        commands:
          - useradd -m -s /bin/bash admin
          - usermod -aG sudo admin

      - task: Lock root account
        command: passwd -l root

      - task: Set password policies
        config: /etc/security/pwquality.conf
        settings: |
          minlen = 12
          dcredit = -1
          ucredit = -1
          ocredit = -1
          lcredit = -1

    logging:
      - task: Enable auditd
        command: apt install auditd

      - task: Configure syslog forwarding
        config: /etc/rsyslog.d/50-remote.conf
        setting: "*.* @@10.70.0.50:514"

      - task: Enable process accounting
        command: apt install acct && accton on
```

### Network-Level Security

```yaml
firewall_hardening:
  default_deny:
    description: Deny all traffic by default, allow specific
    implementation: All firewall rules start with deny-all

  egress_filtering:
    description: Control outbound traffic
    rules:
      - allow: HTTP/HTTPS to internet (port 80, 443)
      - allow: DNS (port 53)
      - allow: NTP (port 123)
      - deny: All other outbound

  rate_limiting:
    description: Prevent brute force and DoS
    rules:
      - limit: SSH to 10 connections per minute per IP
      - limit: API endpoints to 100 requests per minute per IP
      - limit: Login attempts to 5 per 5 minutes per IP

vlan_isolation:
  principles:
    - Production isolated from development
    - Databases isolated from internet
    - Guest network completely isolated from LAN
    - Management network restricted access

  implementation:
    - Use UniFi firewall rules
    - Verify no unexpected inter-VLAN routing
    - Monitor for VLAN hopping attempts

intrusion_detection:
  ids_ips:
    tool: Suricata or Snort
    deployment: Mirror port on core switch

    rules:
      - ET (Emerging Threats) rulesets
      - Custom rules for specific threats

    actions:
      - Alert on suspicious traffic
      - Block known malicious IPs
      - Log all security events

  monitoring:
    tool: Wazuh or OSSEC
    deployment: Agent on all VMs

    capabilities:
      - File integrity monitoring
      - Log analysis
      - Rootkit detection
      - Active response (block IPs)
```

### Application-Level Security

```yaml
web_application:
  https_only:
    - task: Force HTTPS
      method: HTTP to HTTPS redirect
      hsts: max-age=31536000; includeSubDomains; preload

  headers:
    - task: Set security headers
      headers:
        X-Content-Type-Options: nosniff
        X-Frame-Options: DENY
        X-XSS-Protection: 1; mode=block
        Referrer-Policy: strict-origin-when-cross-origin
        Content-Security-Policy: default-src 'self'

  waf:
    tool: Cloudflare WAF or ModSecurity
    rulesets:
      - OWASP Core Rule Set
      - Cloudflare Managed Rules

    protection:
      - SQL injection
      - Cross-site scripting (XSS)
      - Cross-site request forgery (CSRF)
      - Remote file inclusion
      - Local file inclusion

database:
  authentication:
    - task: Use strong passwords
      requirements: 16+ characters, complex

    - task: Use separate credentials per application
      method: Different DB users for each app

    - task: Enable SSL/TLS connections
      postgresql: sslmode=require
      mysql: require_secure_transport=ON

  authorization:
    - task: Grant least privilege
      method: Only grant necessary permissions
      example: SELECT, INSERT, UPDATE (not DELETE or DROP)

    - task: Use read-only replicas for reporting
      method: Route read-only queries to replicas

  hardening:
    - task: Disable remote root login
      postgresql: No remote root user
      mysql: DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1')

    - task: Remove test databases
      command: DROP DATABASE test;

    - task: Enable audit logging
      postgresql: pgaudit extension
      mysql: audit_log plugin
```

### Compliance Checklists

```yaml
security_audit_schedule:
  daily:
    - Review failed login attempts
    - Check firewall block logs
    - Verify backup completion

  weekly:
    - Review security group changes
    - Check for unauthorized software
    - Verify patch status

  monthly:
    - Full vulnerability scan (Nessus, OpenVAS)
    - Review user accounts and permissions
    - Test backup restoration
    - Review network topology changes

  quarterly:
    - Penetration testing
    - Disaster recovery drill
    - Access control review
    - Security training for staff

vulnerability_scanning:
  tools:
    - OpenVAS (open source)
    - Nessus (commercial)
    - Qualys (cloud-based)

  schedule: Weekly scans
  scope: All VMs and network devices

  remediation:
    critical: 24 hours
    high: 7 days
    medium: 30 days
    low: 90 days

compliance_frameworks:
  pci_dss:
    - Requirement 1: Install and maintain firewall
    - Requirement 2: Change vendor defaults
    - Requirement 3: Protect stored cardholder data
    - Requirement 4: Encrypt transmission of cardholder data
    - Requirement 5: Use and regularly update anti-virus
    - Requirement 6: Develop and maintain secure systems
    - Requirement 7: Restrict access by business need-to-know
    - Requirement 8: Assign unique ID to each person with access
    - Requirement 9: Restrict physical access to cardholder data
    - Requirement 10: Track and monitor all access
    - Requirement 11: Regularly test security systems
    - Requirement 12: Maintain information security policy

  hipaa:
    - Administrative safeguards
    - Physical safeguards
    - Technical safeguards
    - Organizational requirements
    - Policies and procedures
    - Documentation requirements

  gdpr:
    - Data protection by design
    - Data minimization
    - Right to access
    - Right to erasure
    - Data breach notification (72 hours)
    - Data portability
```

---

## Talos Kubernetes Integration

### Talos Overview

```yaml
talos:
  description: Immutable, API-managed Kubernetes OS
  advantages:
    - Minimal attack surface (no SSH, no shell)
    - API-driven management
    - Immutable infrastructure
    - Secure by default

  integration_with_cortex:
    - Infrastructure contractor provisions Talos VMs
    - Talos contractor (via talos-mcp) configures cluster
    - Tight integration with cortex-resource-manager

architecture:
  control_plane:
    count: 3 (HA)
    specs:
      cpu: 4 vCPU
      ram: 8 GB
      disk: 50 GB

  worker_nodes:
    count: 5+ (scalable)
    specs:
      cpu: 8-16 vCPU
      ram: 16-32 GB
      disk: 100 GB

  network:
    vlan: 20 (App Servers)
    pod_cidr: 10.244.0.0/16
    service_cidr: 10.96.0.0/16
```

### Infrastructure Contractor Role in Talos Deployment

#### Phase 1: VM Provisioning (Infrastructure Contractor)

```yaml
vm_provisioning:
  task: Provision VMs for Talos Kubernetes cluster
  contractor: infrastructure-contractor

  control_plane_vms:
    count: 3
    naming: k8s-cp-{01,02,03}
    specs:
      cpu: 4 vCPU
      ram: 8 GB
      disk: 50 GB
      network: VLAN 20 (App Servers)

    ips:
      - k8s-cp-01: 10.20.0.60
      - k8s-cp-02: 10.20.0.61
      - k8s-cp-03: 10.20.0.62

    proxmox_steps:
      1. Create VMs from base template
      2. Configure CPU, RAM, disk
      3. Attach to VLAN 20
      4. Set static IP via cloud-init or DHCP reservation
      5. Start VMs (will boot from Talos ISO)

  worker_vms:
    count: 5
    naming: k8s-worker-{01,02,03,04,05}
    specs:
      cpu: 16 vCPU
      ram: 32 GB
      disk: 100 GB
      network: VLAN 20 (App Servers)

    ips:
      - k8s-worker-01: 10.20.0.70
      - k8s-worker-02: 10.20.0.71
      - k8s-worker-03: 10.20.0.72
      - k8s-worker-04: 10.20.0.73
      - k8s-worker-05: 10.20.0.74

  networking:
    vlan_config:
      - Verify VLAN 20 exists
      - Configure firewall rules for Kubernetes
        - Allow 6443 (Kubernetes API) from management VLAN
        - Allow 10250 (kubelet API) within VLAN 20
        - Allow 2379-2380 (etcd) between control plane nodes
        - Allow 30000-32767 (NodePort services) from WAN

    unifi_firewall_rules:
      - name: Allow Kubernetes API from Management
        source: 10.10.0.0/24
        destination: 10.20.0.60-10.20.0.62
        port: 6443
        action: allow

      - name: Allow NodePort from WAN
        source: WAN
        destination: 10.20.0.70-10.20.0.74
        ports: 30000-32767
        action: allow

  dns_config:
    cloudflare_records:
      - name: k8s-api.example.com
        type: A
        value: 10.20.0.60  # Load balanced across control plane
        proxied: no

      - name: "*.apps.example.com"
        type: A
        value: 10.20.0.100  # Ingress controller VIP
        proxied: yes

  load_balancing:
    api_server:
      method: HAProxy or kube-vip on control plane
      vip: 10.20.0.60
      backends:
        - 10.20.0.60:6443
        - 10.20.0.61:6443
        - 10.20.0.62:6443
```

#### Phase 2: Talos Configuration (Talos Contractor via talos-mcp)

```yaml
talos_configuration:
  contractor: talos-contractor
  mcp_server: talos-mcp

  cluster_creation:
    - Generate Talos config
    - Bootstrap control plane
    - Join additional control plane nodes
    - Join worker nodes
    - Verify cluster health

  integration_points:
    - Retrieve VM IPs from infrastructure-contractor manifest
    - Use Cloudflare DNS for cluster endpoints
    - Configure storage using Ceph RBD (from infrastructure)

handoff_flow:
  infrastructure_contractor:
    outputs:
      - VM IDs and IPs
      - Network configuration
      - DNS records
      - Storage endpoints

  talos_contractor:
    inputs:
      - VM IPs from infrastructure manifest
      - Network CIDR ranges
      - DNS endpoints
      - Storage configuration

    outputs:
      - Kubernetes cluster kubeconfig
      - Cluster health status
      - Deployed applications
```

### Storage Integration for Kubernetes

```yaml
storage_classes:
  ceph_rbd:
    provisioner: rbd.csi.ceph.com
    description: Ceph RBD for block storage

    parameters:
      clusterID: ceph-cluster-prod
      pool: k8s-rbd-pool
      imageFeatures: layering
      csi.storage.k8s.io/provisioner-secret-name: ceph-csi-secret
      csi.storage.k8s.io/node-stage-secret-name: ceph-csi-secret

    use_cases:
      - Database persistent volumes
      - Stateful applications

  cephfs:
    provisioner: cephfs.csi.ceph.com
    description: CephFS for shared filesystem

    parameters:
      clusterID: ceph-cluster-prod
      fsName: k8s-cephfs
      pool: k8s-cephfs-data

    use_cases:
      - Shared application data
      - ReadWriteMany volumes

  nfs:
    provisioner: nfs.csi.k8s.io
    description: NFS for legacy applications

    parameters:
      server: 10.30.0.200
      share: /tank/k8s-nfs

    use_cases:
      - Legacy applications requiring NFS
      - Shared configuration data

persistent_volume_example: |
  apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: postgres-pvc
  spec:
    accessModes:
      - ReadWriteOnce
    storageClassName: ceph-rbd
    resources:
      requests:
        storage: 100Gi
```

### Network Integration for Kubernetes

```yaml
ingress_controller:
  type: NGINX Ingress Controller
  deployment: DaemonSet on worker nodes

  service:
    type: LoadBalancer
    external_ip: 10.20.0.100 (MetalLB or kube-vip)

  cloudflare_integration:
    dns_record: "*.apps.example.com → 10.20.0.100"
    proxied: yes (for DDoS protection, SSL, caching)

  unifi_firewall:
    - Allow WAN → 10.20.0.100:80,443

metallb_config:
  description: Bare-metal load balancer for Kubernetes

  ip_pool:
    name: production-pool
    addresses: 10.20.0.100-10.20.0.110
    protocol: layer2

  integration:
    - IPs from same VLAN as worker nodes
    - Announced via ARP
    - No additional routing needed

service_example: |
  apiVersion: v1
  kind: Service
  metadata:
    name: web-app
  spec:
    type: LoadBalancer
    loadBalancerIP: 10.20.0.101
    ports:
      - port: 80
        targetPort: 8080
    selector:
      app: web-app
```

### Monitoring Integration

```yaml
prometheus_stack:
  deployment: kube-prometheus-stack Helm chart

  components:
    prometheus:
      storage: 200 GB Ceph RBD PVC
      retention: 30 days
      replicas: 2 (HA)

    grafana:
      storage: 10 GB Ceph RBD PVC
      replicas: 1
      ingress: grafana.apps.example.com

    alertmanager:
      replicas: 3 (HA)
      ingress: alerts.apps.example.com

  monitoring_targets:
    - Kubernetes cluster metrics (apiserver, scheduler, controller-manager)
    - Node metrics (kubelet, cAdvisor)
    - Pod metrics (container resources)
    - Application metrics (custom exporters)

  integration_with_infrastructure_monitoring:
    - Prometheus in K8s scrapes infrastructure exporters
    - Infrastructure Prometheus (VLAN 70) scrapes K8s metrics
    - Unified Grafana dashboards
```

### Disaster Recovery for Kubernetes

```yaml
backup_strategy:
  velero:
    description: Backup and restore Kubernetes resources

    storage:
      type: S3-compatible (Minio or Cloudflare R2)
      location: Off-site backup storage

    backup_schedule:
      full_cluster: Daily at 02:00 UTC
      retention: 7 days

      namespaces:
        production: Hourly backups, 24 hour retention
        staging: Daily backups, 7 day retention

    what_is_backed_up:
      - Kubernetes resources (deployments, services, configmaps, secrets)
      - Persistent volumes (via snapshot or restic)

  etcd_backup:
    description: Backup etcd cluster state

    schedule: Hourly
    retention: 24 hours
    location: /backup/k8s-etcd/

    command: |
      etcdctl snapshot save /backup/k8s-etcd/etcd-$(date +%Y%m%d-%H%M%S).db

  disaster_recovery_steps:
    1. Provision new Kubernetes VMs (infrastructure-contractor)
    2. Bootstrap new Talos cluster (talos-contractor)
    3. Restore etcd from backup
    4. Restore Kubernetes resources via Velero
    5. Verify all applications running
    6. Update DNS to point to new cluster

    rto: 4 hours
    rpo: 1 hour
```

---

## Conclusion

This comprehensive patterns document provides the infrastructure-contractor with deep domain knowledge across all key areas:

1. **Proxmox VM Templates**: Detailed sizing guides, OS templates, cloning strategies, and resource allocation best practices
2. **Network Topology**: Complete VLAN architectures, DMZ patterns, zero trust segmentation
3. **Storage Configurations**: ZFS layouts, Ceph distributed storage, NFS configurations with performance tuning
4. **UniFi Patterns**: VLAN configurations, firewall rules, WiFi optimization, traffic management
5. **Cloudflare Integration**: DNS management, SSL/TLS, tunnels, caching, security features
6. **High Availability**: Database HA (PostgreSQL, MySQL), load-balanced web servers, Proxmox HA cluster
7. **Disaster Recovery**: VM backups, database-specific backups, off-site replication, recovery runbooks
8. **Cost Optimization**: Resource right-sizing, storage optimization, network cost reduction, power management
9. **Security Hardening**: OS hardening, network security, application security, compliance checklists
10. **Talos Integration**: Kubernetes cluster provisioning, storage integration, network integration, monitoring, DR

The infrastructure-contractor can reference this document when provisioning infrastructure to ensure best practices, security, reliability, and cost-effectiveness.

**Total Lines**: 2100+ (comprehensive coverage)
**Maintenance**: Update as new patterns emerge and technologies evolve
**Integration**: Use alongside infrastructure-contractor.md and infrastructure-contractor-knowledge.json
