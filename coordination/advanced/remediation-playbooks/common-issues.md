# Common Issues Remediation Playbooks

## Overview

This document contains remediation playbooks for common infrastructure and system issues that occur frequently across environments. These playbooks are designed to be executed automatically by the self-healing system or manually by operations teams.

---

## Table of Contents

1. [Disk Space Issues](#disk-space-issues)
2. [Out of Memory (OOM)](#out-of-memory-oom)
3. [High CPU Usage](#high-cpu-usage)
4. [Connection Timeouts](#connection-timeouts)
5. [Service Unresponsive](#service-unresponsive)
6. [Log File Growth](#log-file-growth)
7. [Inode Exhaustion](#inode-exhaustion)
8. [DNS Resolution Failures](#dns-resolution-failures)
9. [Certificate Expiration](#certificate-expiration)
10. [Process Zombies](#process-zombies)

---

## Disk Space Issues

### Symptom Detection

```yaml
symptoms:
  - disk_usage > 85%
  - df_output shows near-full partitions
  - "No space left on device" errors in logs
  - Applications failing to write files

detection_metrics:
  - metric: node_filesystem_avail_bytes
  - threshold: < 15% available
  - duration: sustained for 5 minutes
```

### Root Cause Analysis

```bash
# Check disk usage by partition
df -h

# Find largest directories
du -sh /* 2>/dev/null | sort -hr | head -20

# Find largest files
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -hr | head -20

# Check for deleted but open files (disk space not released)
lsof +L1 | grep deleted

# Check inode usage
df -i
```

### Remediation Playbook: DISK-CLEANUP-001

**Severity**: High
**Auto-remediation**: Enabled
**Blast Radius**: Single Host
**Estimated Time**: 10-15 minutes

#### Pre-conditions

- Writable filesystem
- No active backup operations
- Sufficient permissions (root/sudo)

#### Remediation Steps

**Step 1: Clean Temporary Files**
```bash
#!/bin/bash
# Clean /tmp and /var/tmp directories (files older than 7 days)

# Check current disk usage
df -h / | tail -1 | awk '{print $5}' | sed 's/%//'

# Clean /tmp
find /tmp -type f -atime +7 -delete
find /tmp -type d -empty -delete

# Clean /var/tmp
find /var/tmp -type f -atime +7 -delete
find /var/tmp -type d -empty -delete

# Verify improvement
df -h / | tail -1 | awk '{print $5}' | sed 's/%//'
```

**Expected Recovery**: 5-10% disk space

**Step 2: Rotate and Compress Logs**
```bash
#!/bin/bash
# Force log rotation and compress old logs

# Force logrotate
logrotate -f /etc/logrotate.conf

# Compress uncompressed logs older than 1 day
find /var/log -type f -name "*.log" -mtime +1 ! -name "*.gz" -exec gzip {} \;

# Remove compressed logs older than 30 days
find /var/log -type f -name "*.gz" -mtime +30 -delete

# Verify improvement
df -h /var | tail -1 | awk '{print $5}' | sed 's/%//'
```

**Expected Recovery**: 10-20% disk space

**Step 3: Clean Package Manager Cache**
```bash
#!/bin/bash
# Clean package manager caches

OS_TYPE=$(cat /etc/os-release | grep "^ID=" | cut -d= -f2 | tr -d '"')

case "$OS_TYPE" in
  ubuntu|debian)
    apt-get clean
    apt-get autoclean
    apt-get autoremove -y
    ;;
  centos|rhel|fedora)
    yum clean all
    dnf clean all 2>/dev/null || true
    ;;
  alpine)
    rm -rf /var/cache/apk/*
    ;;
esac

# Clean npm cache if present
if command -v npm &> /dev/null; then
  npm cache clean --force
fi

# Clean pip cache if present
if command -v pip3 &> /dev/null; then
  pip3 cache purge 2>/dev/null || true
fi

df -h / | tail -1 | awk '{print $5}' | sed 's/%//'
```

**Expected Recovery**: 5-15% disk space

**Step 4: Clean Docker Resources (if applicable)**
```bash
#!/bin/bash
# Clean unused Docker resources

if command -v docker &> /dev/null; then
  # Remove dangling images
  docker image prune -f

  # Remove unused containers
  docker container prune -f

  # Remove unused volumes (careful!)
  docker volume prune -f

  # Remove unused networks
  docker network prune -f

  # Remove build cache
  docker builder prune -f --filter "until=24h"
fi

df -h / | tail -1 | awk '{print $5}' | sed 's/%//'
```

**Expected Recovery**: 10-40% disk space

**Step 5: Archive Old Backups**
```bash
#!/bin/bash
# Move old backups to archive storage or delete

BACKUP_DIR="/var/backups"
ARCHIVE_AGE_DAYS=30

if [ -d "$BACKUP_DIR" ]; then
  # Find backups older than 30 days
  find "$BACKUP_DIR" -type f -mtime +${ARCHIVE_AGE_DAYS} | while read file; do
    # Option 1: Archive to S3 (if configured)
    if command -v aws &> /dev/null; then
      aws s3 cp "$file" "s3://backup-archive/$(basename $file)"
      rm -f "$file"
    else
      # Option 2: Just delete old backups
      rm -f "$file"
    fi
  done
fi

df -h / | tail -1 | awk '{print $5}' | sed 's/%//'
```

**Expected Recovery**: 20-40% disk space

#### Verification

```bash
#!/bin/bash
# Verify disk usage is below 75%

DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$DISK_USAGE" -lt 75 ]; then
  echo "SUCCESS: Disk usage is now ${DISK_USAGE}%"
  exit 0
else
  echo "FAILED: Disk usage is still ${DISK_USAGE}%"
  exit 1
fi
```

#### Rollback

Not applicable - cleanup operations are not reversible.

#### Escalation

If disk usage remains above 75% after all steps:
- Notify infrastructure team
- Create incident ticket
- Consider emergency disk expansion
- Identify and remove application-specific large files

---

## Out of Memory (OOM)

### Symptom Detection

```yaml
symptoms:
  - OOM killer activated (dmesg shows "Out of memory")
  - Process killed due to memory pressure
  - System swap usage at 100%
  - Memory usage > 95% sustained
  - Kernel logs show "memory: usage XXkB, limit XXkB"

detection_metrics:
  - metric: node_memory_MemAvailable_bytes
  - threshold: < 5% of total memory
  - duration: sustained for 2 minutes
```

### Root Cause Analysis

```bash
# Check current memory usage
free -h

# Check swap usage
swapon --show

# Find top memory-consuming processes
ps aux --sort=-%mem | head -20

# Check for memory leaks (increasing RSS over time)
ps -eo pid,ppid,cmd,%mem,rss,vsz --sort=-%mem | head -20

# Check OOM killer logs
dmesg | grep -i "killed process"
journalctl -k | grep -i "out of memory"

# Check for memory cgroup limits
cat /sys/fs/cgroup/memory/memory.limit_in_bytes
cat /sys/fs/cgroup/memory/memory.usage_in_bytes
```

### Remediation Playbook: OOM-MITIGATION-001

**Severity**: Critical
**Auto-remediation**: Enabled (with caution)
**Blast Radius**: Single Host
**Estimated Time**: 2-5 minutes

#### Pre-conditions

- System responsive (not completely frozen)
- SSH access available
- Root/sudo access

#### Remediation Steps

**Step 1: Identify Memory Hog**
```bash
#!/bin/bash
# Identify the process consuming most memory

# Get top memory consumer
TOP_MEM_PID=$(ps aux --sort=-%mem | awk 'NR==2 {print $2}')
TOP_MEM_PROCESS=$(ps aux --sort=-%mem | awk 'NR==2 {print $11}')
TOP_MEM_USAGE=$(ps aux --sort=-%mem | awk 'NR==2 {print $4}')

echo "Top memory consumer: PID=$TOP_MEM_PID, Process=$TOP_MEM_PROCESS, Usage=${TOP_MEM_USAGE}%"

# Save to context for next steps
echo $TOP_MEM_PID > /tmp/oom_remediation_pid
```

**Step 2: Check if Process is Critical**
```bash
#!/bin/bash
# Determine if the process is critical before killing

PID=$(cat /tmp/oom_remediation_pid)
PROCESS_NAME=$(ps -p $PID -o comm=)

# Define critical processes that should not be killed
CRITICAL_PROCESSES=("systemd" "sshd" "kubelet" "docker" "containerd")

for critical in "${CRITICAL_PROCESSES[@]}"; do
  if [[ "$PROCESS_NAME" == "$critical" ]]; then
    echo "CRITICAL: Process $PROCESS_NAME is critical, escalating instead of killing"
    exit 1  # Escalate to human
  fi
done

echo "Process $PROCESS_NAME is not critical, safe to restart"
```

**Step 3: Clear Page Cache and Buffers**
```bash
#!/bin/bash
# Free up memory by clearing caches (safe operation)

# Sync to ensure no data loss
sync

# Drop page cache, dentries, and inodes
echo 3 > /proc/sys/vm/drop_caches

# Check memory freed
free -h

echo "Page cache cleared"
```

**Expected Recovery**: 10-30% memory freed

**Step 4: Restart Memory-Hungry Process**
```bash
#!/bin/bash
# Gracefully restart the memory-hungry process

PID=$(cat /tmp/oom_remediation_pid)
PROCESS_NAME=$(ps -p $PID -o comm=)
SERVICE_NAME=$(systemctl status $PID 2>/dev/null | grep "Loaded:" | awk '{print $2}')

if [ -n "$SERVICE_NAME" ]; then
  # It's a systemd service, restart it
  echo "Restarting systemd service: $SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
else
  # Kill the process and let it respawn
  echo "Killing process: $PROCESS_NAME (PID: $PID)"
  kill -15 $PID  # SIGTERM for graceful shutdown

  # Wait up to 30 seconds for graceful shutdown
  for i in {1..30}; do
    if ! ps -p $PID > /dev/null; then
      echo "Process terminated gracefully"
      break
    fi
    sleep 1
  done

  # Force kill if still running
  if ps -p $PID > /dev/null; then
    echo "Forcefully killing process"
    kill -9 $PID
  fi
fi
```

**Step 5: Enable Emergency Swap (if not present)**
```bash
#!/bin/bash
# Create emergency swap file if system has no swap

SWAP_SIZE=$(swapon --show | wc -l)

if [ "$SWAP_SIZE" -le 1 ]; then
  echo "No swap detected, creating emergency swap file"

  # Create 2GB swap file
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile

  echo "Emergency swap activated: 2GB"
fi
```

#### Verification

```bash
#!/bin/bash
# Verify memory usage is back to acceptable levels

MEM_AVAILABLE=$(free | grep Mem | awk '{print ($7/$2) * 100.0}')

if (( $(echo "$MEM_AVAILABLE > 10.0" | bc -l) )); then
  echo "SUCCESS: Memory available is now ${MEM_AVAILABLE}%"
  exit 0
else
  echo "FAILED: Memory still critically low: ${MEM_AVAILABLE}% available"
  exit 1
fi
```

#### Rollback

```bash
#!/bin/bash
# Ensure critical services are running

# Check and restart sshd if needed
if ! systemctl is-active --quiet sshd; then
  systemctl start sshd
fi

# Check and restart other critical services
for service in docker kubelet containerd; do
  if systemctl list-unit-files | grep -q "^${service}.service"; then
    if ! systemctl is-active --quiet $service; then
      systemctl start $service
    fi
  fi
done
```

#### Escalation

If memory usage remains critical:
- Notify on-call SRE immediately
- Create SEV1 incident
- Consider:
  - Scaling up instance size
  - Investigating memory leak
  - Reducing application memory limits
  - Adding more swap space

---

## High CPU Usage

### Symptom Detection

```yaml
symptoms:
  - CPU usage > 90% sustained
  - System load average > number of CPU cores
  - Applications slow or unresponsive
  - High context switching rate

detection_metrics:
  - metric: node_cpu_seconds_total (rate)
  - threshold: > 90% utilization
  - duration: sustained for 5 minutes
```

### Root Cause Analysis

```bash
# Check current CPU usage
top -b -n 1 | head -20

# Check load average
uptime

# Find CPU-intensive processes
ps aux --sort=-%cpu | head -20

# Check CPU usage per core
mpstat -P ALL 1 5

# Check for runaway processes
ps -eo pid,ppid,cmd,%cpu,time --sort=-%cpu | head -20

# Check I/O wait (could indicate I/O bottleneck, not CPU)
iostat -x 1 5
```

### Remediation Playbook: HIGH-CPU-001

**Severity**: High
**Auto-remediation**: Enabled
**Blast Radius**: Single Host
**Estimated Time**: 3-5 minutes

#### Remediation Steps

**Step 1: Identify CPU Hog**
```bash
#!/bin/bash
# Find the process consuming most CPU

TOP_CPU_PID=$(ps aux --sort=-%cpu | awk 'NR==2 {print $2}')
TOP_CPU_PROCESS=$(ps aux --sort=-%cpu | awk 'NR==2 {print $11}')
TOP_CPU_USAGE=$(ps aux --sort=-%cpu | awk 'NR==2 {print $3}')

echo "Top CPU consumer: PID=$TOP_CPU_PID, Process=$TOP_CPU_PROCESS, Usage=${TOP_CPU_USAGE}%"
echo $TOP_CPU_PID > /tmp/high_cpu_pid
```

**Step 2: Check if Process is Legitimate**
```bash
#!/bin/bash
# Check if high CPU usage is from a known legitimate process

PID=$(cat /tmp/high_cpu_pid)
PROCESS_NAME=$(ps -p $PID -o comm=)
CPU_TIME=$(ps -p $PID -o time=)

# Known CPU-intensive legitimate processes during certain operations
LEGITIMATE_HIGH_CPU=("gcc" "make" "node" "python" "java" "postgres")

for legit in "${LEGITIMATE_HIGH_CPU[@]}"; do
  if [[ "$PROCESS_NAME" == *"$legit"* ]]; then
    echo "INFO: High CPU from potentially legitimate process: $PROCESS_NAME"
    echo "CPU Time: $CPU_TIME"
    # Could be a build or intensive operation, monitor but don't kill immediately
    exit 2  # Special code: monitor but don't remediate yet
  fi
done
```

**Step 3: Nice Down the Process**
```bash
#!/bin/bash
# Reduce priority (nice) of CPU-hogging process before killing

PID=$(cat /tmp/high_cpu_pid)

# Set to lowest priority (nice value 19)
renice +19 -p $PID

echo "Reduced priority for PID $PID to nice value 19"

# Give it 60 seconds to complete or reduce CPU usage
sleep 60

# Check if CPU usage improved
CURRENT_CPU=$(ps -p $PID -o %cpu= 2>/dev/null || echo "0")

if (( $(echo "$CURRENT_CPU < 50.0" | bc -l) )); then
  echo "SUCCESS: CPU usage reduced to ${CURRENT_CPU}% after nice adjustment"
  exit 0
fi

echo "CPU usage still high: ${CURRENT_CPU}%"
```

**Step 4: Kill Runaway Process**
```bash
#!/bin/bash
# If nice didn't help, kill the process

PID=$(cat /tmp/high_cpu_pid)
PROCESS_NAME=$(ps -p $PID -o comm=)

# Try graceful termination first
echo "Attempting graceful termination of PID $PID ($PROCESS_NAME)"
kill -15 $PID

# Wait up to 30 seconds
for i in {1..30}; do
  if ! ps -p $PID > /dev/null 2>&1; then
    echo "Process terminated gracefully"
    exit 0
  fi
  sleep 1
done

# Force kill if still running
if ps -p $PID > /dev/null 2>&1; then
  echo "Force killing PID $PID"
  kill -9 $PID
fi
```

#### Verification

```bash
#!/bin/bash
# Verify CPU usage is back to normal

CPU_USAGE=$(top -b -n 1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)

if (( $(echo "$CPU_USAGE < 80.0" | bc -l) )); then
  echo "SUCCESS: CPU usage is now ${CPU_USAGE}%"
  exit 0
else
  echo "FAILED: CPU usage still high: ${CPU_USAGE}%"
  exit 1
fi
```

---

## Connection Timeouts

### Symptom Detection

```yaml
symptoms:
  - Connection refused errors
  - Connection timeout errors
  - High connection latency
  - TCP retransmissions

detection_metrics:
  - metric: connection_timeout_rate
  - threshold: > 5% of connections
  - duration: sustained for 2 minutes
```

### Root Cause Analysis

```bash
# Check network connectivity
ping -c 5 8.8.8.8

# Check DNS resolution
nslookup google.com

# Check if service port is listening
netstat -tlnp | grep :80
ss -tlnp | grep :80

# Check connection states
netstat -an | awk '{print $6}' | sort | uniq -c | sort -rn

# Check TCP retransmissions
netstat -s | grep -i retrans

# Check firewall rules
iptables -L -n -v

# Check for port exhaustion
cat /proc/sys/net/ipv4/ip_local_port_range
netstat -an | grep TIME_WAIT | wc -l
```

### Remediation Playbook: CONNECTION-TIMEOUT-001

**Severity**: High
**Auto-remediation**: Enabled
**Blast Radius**: Single Service

#### Remediation Steps

**Step 1: Verify Network Connectivity**
```bash
#!/bin/bash
# Basic network connectivity check

# Check if network interface is up
ip link show | grep "state UP"

# Ping gateway
GATEWAY=$(ip route | grep default | awk '{print $3}')
if ! ping -c 3 $GATEWAY > /dev/null 2>&1; then
  echo "WARNING: Cannot reach gateway $GATEWAY"
  exit 1
fi

# Check DNS
if ! nslookup google.com > /dev/null 2>&1; then
  echo "WARNING: DNS resolution failing"
  # Try to fix DNS
  systemctl restart systemd-resolved
fi
```

**Step 2: Flush Connection Tracking Table**
```bash
#!/bin/bash
# Clear connection tracking table (can help with stale connections)

# Check if conntrack is available
if command -v conntrack &> /dev/null; then
  echo "Flushing connection tracking table"
  conntrack -F
  echo "Connection tracking table flushed"
else
  echo "conntrack not available, skipping"
fi
```

**Step 3: Tune TCP Parameters**
```bash
#!/bin/bash
# Optimize TCP settings for better connection handling

# Increase local port range
sysctl -w net.ipv4.ip_local_port_range="10000 65535"

# Reduce TIME_WAIT timeout
sysctl -w net.ipv4.tcp_fin_timeout=30

# Enable TCP reuse
sysctl -w net.ipv4.tcp_tw_reuse=1

# Increase syn backlog
sysctl -w net.ipv4.tcp_max_syn_backlog=8192

# Increase connection tracking size
sysctl -w net.netfilter.nf_conntrack_max=262144

echo "TCP parameters tuned for better connection handling"
```

**Step 4: Restart Service with Connection Issues**
```bash
#!/bin/bash
# Restart the service experiencing connection timeouts

SERVICE_NAME="$1"  # Passed as parameter

if [ -z "$SERVICE_NAME" ]; then
  echo "ERROR: Service name not provided"
  exit 1
fi

echo "Restarting service: $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# Wait for service to be ready
sleep 10

# Verify service is listening
PORT=$(systemctl status "$SERVICE_NAME" | grep -oP ':\d+' | head -1 | tr -d ':')
if [ -n "$PORT" ]; then
  if netstat -tlnp | grep ":$PORT" > /dev/null; then
    echo "Service $SERVICE_NAME is now listening on port $PORT"
  else
    echo "ERROR: Service not listening on expected port"
    exit 1
  fi
fi
```

#### Verification

```bash
#!/bin/bash
# Test connection to service

HOST="localhost"
PORT="$1"

# Try to connect
if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$HOST/$PORT"; then
  echo "SUCCESS: Connection to $HOST:$PORT successful"
  exit 0
else
  echo "FAILED: Cannot connect to $HOST:$PORT"
  exit 1
fi
```

---

## Service Unresponsive

### Remediation Playbook: SERVICE-RESTART-001

**Severity**: High
**Auto-remediation**: Enabled
**Blast Radius**: Single Service

```bash
#!/bin/bash
# Complete service restart playbook

SERVICE_NAME="$1"

echo "=== Service Restart Remediation ==="
echo "Service: $SERVICE_NAME"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Step 1: Capture current state
echo "Step 1: Capturing service state..."
systemctl status "$SERVICE_NAME" > /tmp/service_state_before.txt
journalctl -u "$SERVICE_NAME" -n 100 > /tmp/service_logs_before.txt

# Step 2: Attempt graceful restart
echo "Step 2: Attempting graceful restart..."
systemctl restart "$SERVICE_NAME"

# Step 3: Wait and verify
echo "Step 3: Waiting for service to stabilize..."
sleep 15

# Step 4: Health check
echo "Step 4: Performing health check..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "SUCCESS: Service $SERVICE_NAME is active"

  # Additional health check if health endpoint is available
  HEALTH_ENDPOINT=$(grep -i "health" /etc/systemd/system/"$SERVICE_NAME".service 2>/dev/null || echo "")
  if [ -n "$HEALTH_ENDPOINT" ]; then
    if curl -sf "$HEALTH_ENDPOINT" > /dev/null; then
      echo "SUCCESS: Health endpoint check passed"
    else
      echo "WARNING: Health endpoint check failed"
    fi
  fi

  exit 0
else
  echo "FAILED: Service $SERVICE_NAME is not active"
  systemctl status "$SERVICE_NAME"
  exit 1
fi
```

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintained By**: cortex development master
