# Infrastructure Issues Remediation Playbooks

## Overview

This document contains remediation playbooks for infrastructure-level issues including VM failures, network partitions, storage problems, and datacenter/cloud provider issues. These playbooks are designed for automated execution where safe, with appropriate escalation for high-risk operations.

---

## Table of Contents

1. [VM/Instance Down](#vminstance-down)
2. [Network Partition](#network-partition)
3. [Storage Mount Failures](#storage-mount-failures)
4. [Load Balancer Issues](#load-balancer-issues)
5. [Database Cluster Failures](#database-cluster-failures)
6. [Network Interface Down](#network-interface-down)
7. [Routing Table Corruption](#routing-table-corruption)
8. [Firewall Blocking Legitimate Traffic](#firewall-blocking-legitimate-traffic)
9. [Cloud Provider API Failures](#cloud-provider-api-failures)
10. [Backup System Failures](#backup-system-failures)

---

## VM/Instance Down

### Symptom Detection

```yaml
symptoms:
  - Instance not responding to ping
  - SSH connection refused
  - Health checks failing
  - Cloud provider reports instance in stopped/terminated state

detection_metrics:
  - metric: instance_status_check
  - threshold: failed for 3 consecutive checks
  - duration: > 5 minutes
```

### Root Cause Analysis

```bash
#!/bin/bash
# Diagnose VM/Instance failure

INSTANCE_ID="$1"
CLOUD_PROVIDER="${2:-aws}"  # aws, gcp, azure

echo "=== VM/Instance Diagnosis ==="
echo "Instance: $INSTANCE_ID"
echo "Cloud Provider: $CLOUD_PROVIDER"

case "$CLOUD_PROVIDER" in
  aws)
    # AWS-specific checks
    echo "Checking AWS instance status..."

    # Get instance state
    aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text

    # Get status checks
    aws ec2 describe-instance-status --instance-ids "$INSTANCE_ID"

    # Get system logs
    echo "Recent system logs:"
    aws ec2 get-console-output --instance-id "$INSTANCE_ID" --latest --output text | tail -100

    # Check for auto-recovery actions
    aws ec2 describe-instance-status --instance-ids "$INSTANCE_ID" --query 'InstanceStatuses[0].Events'
    ;;

  gcp)
    # GCP-specific checks
    echo "Checking GCP instance status..."

    ZONE=$(gcloud compute instances list --filter="name=$INSTANCE_ID" --format="value(zone)")

    gcloud compute instances describe "$INSTANCE_ID" --zone="$ZONE" --format="value(status)"

    # Get serial port output (system logs)
    gcloud compute instances get-serial-port-output "$INSTANCE_ID" --zone="$ZONE" | tail -100
    ;;

  azure)
    # Azure-specific checks
    echo "Checking Azure VM status..."

    RESOURCE_GROUP=$(az vm list --query "[?name=='$INSTANCE_ID'].resourceGroup" -o tsv)

    az vm get-instance-view --name "$INSTANCE_ID" --resource-group "$RESOURCE_GROUP"
    ;;
esac

# Check network connectivity
echo "Checking network connectivity..."
ping -c 5 "$INSTANCE_ID" 2>&1 || echo "Ping failed"

# Check if SSH port is open
timeout 5 bash -c "cat < /dev/null > /dev/tcp/$INSTANCE_ID/22" 2>&1 && echo "SSH port open" || echo "SSH port unreachable"
```

### Remediation Playbook: INFRA-VM-DOWN-001

**Severity**: Critical
**Auto-remediation**: Enabled (with approval for production)
**Blast Radius**: Single Instance
**Estimated Time**: 5-10 minutes

#### Pre-conditions

- Instance exists in cloud provider
- Not part of critical singleton service
- Auto-scaling group or replacement strategy exists

#### Remediation Steps

**Step 1: Attempt Instance Reboot**
```bash
#!/bin/bash
# Attempt graceful reboot of instance

INSTANCE_ID="$1"
CLOUD_PROVIDER="${2:-aws}"

echo "Step 1: Attempting instance reboot"

case "$CLOUD_PROVIDER" in
  aws)
    echo "Rebooting AWS instance: $INSTANCE_ID"
    aws ec2 reboot-instances --instance-ids "$INSTANCE_ID"

    # Wait for instance to come back up
    echo "Waiting for instance to restart..."
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --timeout 300

    # Additional wait for instance initialization
    aws ec2 wait instance-status-ok --instance-ids "$INSTANCE_ID" --timeout 600
    ;;

  gcp)
    ZONE=$(gcloud compute instances list --filter="name=$INSTANCE_ID" --format="value(zone)")
    echo "Rebooting GCP instance: $INSTANCE_ID in zone $ZONE"

    gcloud compute instances reset "$INSTANCE_ID" --zone="$ZONE"

    # Wait for instance to be running
    for i in {1..60}; do
      STATUS=$(gcloud compute instances describe "$INSTANCE_ID" --zone="$ZONE" --format="value(status)")
      if [ "$STATUS" == "RUNNING" ]; then
        echo "Instance is running"
        break
      fi
      sleep 5
    done
    ;;

  azure)
    RESOURCE_GROUP=$(az vm list --query "[?name=='$INSTANCE_ID'].resourceGroup" -o tsv)
    echo "Restarting Azure VM: $INSTANCE_ID"

    az vm restart --name "$INSTANCE_ID" --resource-group "$RESOURCE_GROUP"
    ;;
esac

echo "Instance reboot initiated"
```

**Step 2: Verify Instance Health**
```bash
#!/bin/bash
# Verify instance is healthy after reboot

INSTANCE_ID="$1"
CLOUD_PROVIDER="${2:-aws}"

echo "Step 2: Verifying instance health"

# Wait for instance to be accessible
sleep 30

case "$CLOUD_PROVIDER" in
  aws)
    # Check instance status
    INSTANCE_STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text)
    echo "Instance state: $INSTANCE_STATE"

    if [ "$INSTANCE_STATE" != "running" ]; then
      echo "ERROR: Instance is not running"
      exit 1
    fi

    # Check status checks
    STATUS_CHECK=$(aws ec2 describe-instance-status --instance-ids "$INSTANCE_ID" --query 'InstanceStatuses[0].InstanceStatus.Status' --output text)
    echo "Status check: $STATUS_CHECK"

    if [ "$STATUS_CHECK" != "ok" ]; then
      echo "WARNING: Status checks not passing yet"
    fi
    ;;

  gcp)
    ZONE=$(gcloud compute instances list --filter="name=$INSTANCE_ID" --format="value(zone)")
    STATUS=$(gcloud compute instances describe "$INSTANCE_ID" --zone="$ZONE" --format="value(status)")

    if [ "$STATUS" != "RUNNING" ]; then
      echo "ERROR: Instance is not running"
      exit 1
    fi
    ;;

  azure)
    RESOURCE_GROUP=$(az vm list --query "[?name=='$INSTANCE_ID'].resourceGroup" -o tsv)
    POWER_STATE=$(az vm get-instance-view --name "$INSTANCE_ID" --resource-group "$RESOURCE_GROUP" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus" -o tsv)

    if [ "$POWER_STATE" != "VM running" ]; then
      echo "ERROR: VM is not running"
      exit 1
    fi
    ;;
esac

# Test SSH connectivity
INSTANCE_IP=$(get_instance_ip "$INSTANCE_ID" "$CLOUD_PROVIDER")

if timeout 10 bash -c "cat < /dev/null > /dev/tcp/$INSTANCE_IP/22"; then
  echo "SUCCESS: Instance is accessible"
  exit 0
else
  echo "WARNING: Instance is running but SSH not accessible yet"
  exit 2
fi
```

**Step 3: If Reboot Fails, Replace Instance**
```bash
#!/bin/bash
# Replace failed instance if reboot didn't work

INSTANCE_ID="$1"
CLOUD_PROVIDER="${2:-aws}"

echo "Step 3: Instance reboot failed, initiating replacement"

case "$CLOUD_PROVIDER" in
  aws)
    # Check if instance is part of auto-scaling group
    ASG_NAME=$(aws autoscaling describe-auto-scaling-instances --instance-ids "$INSTANCE_ID" --query 'AutoScalingInstances[0].AutoScalingGroupName' --output text 2>/dev/null)

    if [ -n "$ASG_NAME" ] && [ "$ASG_NAME" != "None" ]; then
      echo "Instance is part of Auto Scaling Group: $ASG_NAME"

      # Terminate instance, ASG will replace it
      echo "Terminating instance, ASG will create replacement..."
      aws autoscaling terminate-instance-in-auto-scaling-group \
        --instance-id "$INSTANCE_ID" \
        --should-decrement-desired-capacity false

      # Wait for replacement to be healthy
      sleep 60

      # Verify new instance is running
      NEW_INSTANCE_COUNT=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$ASG_NAME" --query 'AutoScalingGroups[0].Instances[?HealthStatus==`Healthy`]' --output json | jq 'length')

      echo "Healthy instances in ASG: $NEW_INSTANCE_COUNT"

      if [ "$NEW_INSTANCE_COUNT" -ge 1 ]; then
        echo "SUCCESS: Replacement instance is healthy"
        exit 0
      else
        echo "WARNING: Replacement instance not yet healthy"
        exit 2
      fi

    else
      echo "Instance is NOT part of Auto Scaling Group"
      echo "Manual replacement may be required"
      exit 1
    fi
    ;;

  gcp)
    # Check if instance is part of managed instance group
    MIG=$(gcloud compute instances list --filter="name=$INSTANCE_ID" --format="value(metadata.items.created-by)" | grep -oP 'instanceGroupManagers/\K[^/]+' || echo "")

    if [ -n "$MIG" ]; then
      echo "Instance is part of Managed Instance Group: $MIG"

      ZONE=$(gcloud compute instances list --filter="name=$INSTANCE_ID" --format="value(zone)")

      # Delete instance, MIG will recreate it
      gcloud compute instance-groups managed delete-instances "$MIG" \
        --instances="$INSTANCE_ID" \
        --zone="$ZONE"

      echo "Instance deleted, MIG will create replacement"
      exit 0
    else
      echo "Instance is NOT part of Managed Instance Group"
      echo "Manual replacement required"
      exit 1
    fi
    ;;

  azure)
    # Check if VM is part of scale set
    VMSS=$(az vmss list --query "[].{name:name, vmList:virtualMachines}" --output json | jq -r ".[] | select(.vmList // [] | any(.name == \"$INSTANCE_ID\")) | .name")

    if [ -n "$VMSS" ]; then
      echo "VM is part of scale set: $VMSS"

      RESOURCE_GROUP=$(az vmss list --query "[?name=='$VMSS'].resourceGroup" -o tsv)

      # Delete VM instance, scale set will replace it
      az vmss delete-instances --name "$VMSS" --resource-group "$RESOURCE_GROUP" --instance-ids "$INSTANCE_ID"

      echo "VM deleted, scale set will create replacement"
      exit 0
    else
      echo "VM is NOT part of scale set"
      echo "Manual replacement required"
      exit 1
    fi
    ;;
esac
```

#### Verification

```bash
#!/bin/bash
# Verify instance is healthy and serving traffic

INSTANCE_ID="$1"
CLOUD_PROVIDER="${2:-aws}"

# Get instance IP
INSTANCE_IP=$(get_instance_ip "$INSTANCE_ID" "$CLOUD_PROVIDER")

# Test network connectivity
if ! ping -c 3 "$INSTANCE_IP" > /dev/null 2>&1; then
  echo "FAILED: Cannot ping instance"
  exit 1
fi

# Test SSH connectivity
if ! timeout 10 bash -c "cat < /dev/null > /dev/tcp/$INSTANCE_IP/22"; then
  echo "FAILED: SSH port not accessible"
  exit 1
fi

# If instance runs HTTP service, test it
if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$INSTANCE_IP/80"; then
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://$INSTANCE_IP/health" || echo "000")
  if [ "$HTTP_STATUS" == "200" ]; then
    echo "SUCCESS: Instance is healthy and serving HTTP traffic"
  else
    echo "WARNING: Instance accessible but health check returned $HTTP_STATUS"
  fi
fi

echo "SUCCESS: Instance is healthy"
exit 0
```

#### Escalation

If instance cannot be recovered:
- Notify infrastructure team immediately
- Create SEV1 incident
- Check for wider infrastructure issues
- Review instance logs for root cause
- Consider manual intervention or complete rebuild

---

## Network Partition

### Symptom Detection

```yaml
symptoms:
  - Cannot reach certain subnets or regions
  - Split-brain scenarios in distributed systems
  - Cross-datacenter connectivity lost
  - High packet loss or latency

detection_metrics:
  - metric: network_reachability
  - threshold: packet_loss > 30%
  - duration: > 2 minutes
```

### Root Cause Analysis

```bash
#!/bin/bash
# Diagnose network partition

SOURCE_HOST="$1"
TARGET_HOST="$2"

echo "=== Network Partition Diagnosis ==="
echo "Source: $SOURCE_HOST"
echo "Target: $TARGET_HOST"

# Test basic connectivity
echo "1. Testing ICMP connectivity..."
ping -c 10 "$TARGET_HOST" | tee /tmp/ping_output.txt

PACKET_LOSS=$(grep "packet loss" /tmp/ping_output.txt | grep -oP '\d+(?=%)')
echo "Packet loss: ${PACKET_LOSS}%"

# Test different protocols
echo "2. Testing TCP connectivity..."
timeout 5 bash -c "cat < /dev/null > /dev/tcp/$TARGET_HOST/22" && echo "TCP port 22: OK" || echo "TCP port 22: FAILED"
timeout 5 bash -c "cat < /dev/null > /dev/tcp/$TARGET_HOST/80" && echo "TCP port 80: OK" || echo "TCP port 80: FAILED"

# Traceroute to identify where packets are being dropped
echo "3. Traceroute analysis..."
traceroute -n -m 30 "$TARGET_HOST" 2>&1 | tee /tmp/traceroute_output.txt

# MTR for combined ping + traceroute
echo "4. MTR analysis (if available)..."
if command -v mtr &> /dev/null; then
  mtr -r -c 10 "$TARGET_HOST" | tee /tmp/mtr_output.txt
fi

# Check local routing table
echo "5. Local routing table..."
ip route show

# Check if there are any firewall rules blocking
echo "6. Checking firewall rules..."
iptables -L -n -v | grep "$TARGET_HOST" || echo "No specific firewall rules for target"

# Check for network interface issues
echo "7. Network interface status..."
ip link show

# Check for high network errors
echo "8. Network interface errors..."
ip -s link show | grep -A 2 "RX:\|TX:"

# DNS resolution check
echo "9. DNS resolution..."
nslookup "$TARGET_HOST" || echo "DNS resolution failed"
```

### Remediation Playbook: INFRA-NETWORK-PARTITION-001

**Severity**: Critical
**Auto-remediation**: Limited (diagnostics only, escalate for fixes)
**Blast Radius**: Network segment
**Estimated Time**: 5-15 minutes

#### Remediation Steps

**Step 1: Identify Partition Scope**
```bash
#!/bin/bash
# Identify which hosts/networks are unreachable

KNOWN_HOSTS_FILE="/etc/cortex/known_hosts.txt"

echo "Step 1: Identifying partition scope"

REACHABLE=0
UNREACHABLE=0

while read -r host; do
  if ping -c 2 -W 2 "$host" > /dev/null 2>&1; then
    echo "REACHABLE: $host"
    ((REACHABLE++))
  else
    echo "UNREACHABLE: $host"
    echo "$host" >> /tmp/unreachable_hosts.txt
    ((UNREACHABLE++))
  fi
done < "$KNOWN_HOSTS_FILE"

echo "Summary: $REACHABLE reachable, $UNREACHABLE unreachable"

if [ $UNREACHABLE -gt 0 ]; then
  echo "Network partition detected affecting $UNREACHABLE hosts"
  exit 1
else
  echo "No network partition detected"
  exit 0
fi
```

**Step 2: Check and Restart Network Services**
```bash
#!/bin/bash
# Restart network services to recover from transient issues

echo "Step 2: Restarting network services"

# Flush routing cache
ip route flush cache

# Restart network manager (if using NetworkManager)
if systemctl is-active --quiet NetworkManager; then
  echo "Restarting NetworkManager..."
  systemctl restart NetworkManager
  sleep 10
fi

# Restart networking service (Debian/Ubuntu)
if [ -f /etc/init.d/networking ]; then
  echo "Restarting networking service..."
  systemctl restart networking
  sleep 10
fi

# Restart systemd-networkd (if using systemd-networkd)
if systemctl is-active --quiet systemd-networkd; then
  echo "Restarting systemd-networkd..."
  systemctl restart systemd-networkd
  sleep 10
fi

echo "Network services restarted"
```

**Step 3: Reset Network Interfaces**
```bash
#!/bin/bash
# Reset network interfaces (use with caution!)

INTERFACE="${1:-eth0}"

echo "Step 3: Resetting network interface: $INTERFACE"

# WARNING: This will temporarily disconnect the interface
# Ensure you have console access or this is not the only network path

# Bring interface down
echo "Bringing $INTERFACE down..."
ip link set "$INTERFACE" down
sleep 2

# Bring interface up
echo "Bringing $INTERFACE up..."
ip link set "$INTERFACE" up
sleep 5

# Renew DHCP lease if using DHCP
if grep -q "dhcp" /etc/network/interfaces; then
  dhclient -r "$INTERFACE"
  dhclient "$INTERFACE"
fi

# Verify interface is up
ip link show "$INTERFACE" | grep "state UP" && echo "Interface is UP" || echo "Interface is DOWN"
```

**Step 4: Check Cloud Network Configuration**
```bash
#!/bin/bash
# Check cloud provider network configuration

CLOUD_PROVIDER="${1:-aws}"
INSTANCE_ID="$2"

echo "Step 4: Checking cloud network configuration"

case "$CLOUD_PROVIDER" in
  aws)
    # Check security groups
    echo "Security Groups:"
    aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].SecurityGroups'

    # Check network ACLs
    SUBNET_ID=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].SubnetId' --output text)

    echo "Network ACLs for subnet $SUBNET_ID:"
    aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=$SUBNET_ID"

    # Check route tables
    echo "Route Tables for subnet $SUBNET_ID:"
    aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$SUBNET_ID"
    ;;

  gcp)
    ZONE=$(gcloud compute instances list --filter="name=$INSTANCE_ID" --format="value(zone)")

    # Check firewall rules
    echo "Firewall Rules:"
    gcloud compute firewall-rules list

    # Check routes
    echo "Routes:"
    gcloud compute routes list
    ;;

  azure)
    RESOURCE_GROUP=$(az vm list --query "[?name=='$INSTANCE_ID'].resourceGroup" -o tsv)

    # Check NSG rules
    echo "Network Security Groups:"
    az network nsg list --resource-group "$RESOURCE_GROUP"

    # Check route tables
    echo "Route Tables:"
    az network route-table list --resource-group "$RESOURCE_GROUP"
    ;;
esac
```

#### Verification

```bash
#!/bin/bash
# Verify network partition is resolved

echo "Verifying network connectivity..."

# Re-test unreachable hosts
if [ -f /tmp/unreachable_hosts.txt ]; then
  STILL_UNREACHABLE=0

  while read -r host; do
    if ! ping -c 3 -W 3 "$host" > /dev/null 2>&1; then
      echo "STILL UNREACHABLE: $host"
      ((STILL_UNREACHABLE++))
    else
      echo "NOW REACHABLE: $host"
    fi
  done < /tmp/unreachable_hosts.txt

  if [ $STILL_UNREACHABLE -eq 0 ]; then
    echo "SUCCESS: All hosts are now reachable"
    rm -f /tmp/unreachable_hosts.txt
    exit 0
  else
    echo "FAILED: $STILL_UNREACHABLE hosts still unreachable"
    exit 1
  fi
else
  echo "No unreachable hosts to verify"
  exit 0
fi
```

#### Escalation

Network partitions often require manual intervention:
- Escalate to network engineering team immediately
- Check with cloud provider for any network issues
- Review recent network configuration changes
- Consider activating disaster recovery procedures if partition is prolonged
- Coordinate with database teams to prevent split-brain scenarios

---

## Storage Mount Failures

### Symptom Detection

```yaml
symptoms:
  - Mount points not accessible
  - I/O errors on mounted filesystems
  - Stale NFS file handle errors
  - Applications cannot write to storage

detection_metrics:
  - metric: filesystem_mount_status
  - threshold: unmounted or read-only
```

### Remediation Playbook: INFRA-STORAGE-MOUNT-001

**Severity**: High
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# Storage Mount Failure Remediation

MOUNT_POINT="$1"
DEVICE="$2"

echo "=== Storage Mount Remediation ==="
echo "Mount point: $MOUNT_POINT"
echo "Device: $DEVICE"

# Step 1: Check current mount status
echo "Step 1: Checking mount status..."
mount | grep "$MOUNT_POINT"

if mount | grep -q "$MOUNT_POINT"; then
  echo "Mount point exists, checking if accessible..."

  # Try to access the mount point
  if timeout 5 ls "$MOUNT_POINT" > /dev/null 2>&1; then
    echo "Mount point is accessible"
    exit 0
  else
    echo "Mount point is not accessible (stale or hung)"

    # Step 2: Force unmount
    echo "Step 2: Force unmounting..."
    umount -f "$MOUNT_POINT" || umount -l "$MOUNT_POINT"
    sleep 2
  fi
else
  echo "Mount point is not mounted"
fi

# Step 3: Check if device is available
echo "Step 3: Checking device availability..."

if [ -b "$DEVICE" ]; then
  echo "Block device $DEVICE exists"
elif [[ "$DEVICE" == *":"* ]]; then
  echo "Network device (NFS): $DEVICE"

  # For NFS, check if server is reachable
  NFS_SERVER=$(echo "$DEVICE" | cut -d':' -f1)
  if ! ping -c 3 "$NFS_SERVER" > /dev/null 2>&1; then
    echo "ERROR: NFS server $NFS_SERVER is not reachable"
    exit 1
  fi
else
  echo "ERROR: Device $DEVICE not found"
  exit 1
fi

# Step 4: Attempt to remount
echo "Step 4: Attempting to mount..."

# Create mount point if it doesn't exist
mkdir -p "$MOUNT_POINT"

# Try to mount
if mount "$DEVICE" "$MOUNT_POINT"; then
  echo "Mount successful"

  # Verify accessibility
  if timeout 5 ls "$MOUNT_POINT" > /dev/null 2>&1; then
    echo "SUCCESS: Mount point is accessible"
    exit 0
  else
    echo "WARNING: Mounted but not accessible"
    exit 2
  fi
else
  echo "FAILED: Mount operation failed"

  # Check system logs for errors
  dmesg | tail -50 | grep -i "error\|fail"

  exit 1
fi
```

---

## Load Balancer Issues

### Remediation Playbook: INFRA-LB-FAILURE-001

**Severity**: Critical
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# Load Balancer Failure Remediation

LB_NAME="$1"
CLOUD_PROVIDER="${2:-aws}"

echo "=== Load Balancer Remediation ==="
echo "Load Balancer: $LB_NAME"

case "$CLOUD_PROVIDER" in
  aws)
    # Check ELB/ALB health
    echo "Checking ELB/ALB health..."

    # Check target health
    TARGET_GROUPS=$(aws elbv2 describe-target-groups --load-balancer-arn "$LB_NAME" --query 'TargetGroups[*].TargetGroupArn' --output text)

    for tg in $TARGET_GROUPS; do
      echo "Target Group: $tg"

      # Get target health
      aws elbv2 describe-target-health --target-group-arn "$tg"

      # Count healthy targets
      HEALTHY_TARGETS=$(aws elbv2 describe-target-health --target-group-arn "$tg" --query 'TargetHealthDescriptions[?TargetHealth.State==`healthy`]' --output json | jq 'length')

      TOTAL_TARGETS=$(aws elbv2 describe-target-health --target-group-arn "$tg" --query 'TargetHealthDescriptions' --output json | jq 'length')

      echo "Healthy targets: $HEALTHY_TARGETS / $TOTAL_TARGETS"

      if [ "$HEALTHY_TARGETS" -eq 0 ]; then
        echo "ERROR: No healthy targets in target group"

        # Check if targets exist but are unhealthy
        UNHEALTHY_TARGETS=$(aws elbv2 describe-target-health --target-group-arn "$tg" --query 'TargetHealthDescriptions[?TargetHealth.State!=`healthy`].Target.Id' --output text)

        for target_id in $UNHEALTHY_TARGETS; do
          echo "Unhealthy target: $target_id"

          # Get unhealthy reason
          REASON=$(aws elbv2 describe-target-health --target-group-arn "$tg" --targets Id="$target_id" --query 'TargetHealthDescriptions[0].TargetHealth.Reason' --output text)

          echo "Reason: $REASON"

          # If target is not registered, re-register it
          if [ "$REASON" == "Target.NotRegistered" ]; then
            echo "Re-registering target: $target_id"
            aws elbv2 register-targets --target-group-arn "$tg" --targets Id="$target_id"
          fi
        done
      fi
    done
    ;;

  gcp)
    # Check GCP load balancer
    echo "Checking GCP load balancer..."

    # Get backend service health
    BACKEND_SERVICE=$(gcloud compute backend-services list --filter="name:$LB_NAME" --format="value(name)" --limit=1)

    if [ -n "$BACKEND_SERVICE" ]; then
      echo "Backend Service: $BACKEND_SERVICE"
      gcloud compute backend-services get-health "$BACKEND_SERVICE" --global
    fi
    ;;

  azure)
    # Check Azure load balancer
    echo "Checking Azure load balancer..."

    RESOURCE_GROUP=$(az network lb list --query "[?name=='$LB_NAME'].resourceGroup" -o tsv)

    # Get backend pool health
    az network lb show --name "$LB_NAME" --resource-group "$RESOURCE_GROUP"

    # Check backend pool members
    BACKEND_POOLS=$(az network lb address-pool list --lb-name "$LB_NAME" --resource-group "$RESOURCE_GROUP" --query '[].name' -o tsv)

    for pool in $BACKEND_POOLS; do
      echo "Backend Pool: $pool"
      az network lb address-pool show --lb-name "$LB_NAME" --name "$pool" --resource-group "$RESOURCE_GROUP"
    done
    ;;
esac
```

---

## Database Cluster Failures

### Remediation Playbook: INFRA-DB-CLUSTER-001

**Severity**: Critical
**Auto-remediation**: Limited (requires approval)
**Blast Radius**: Database cluster

```bash
#!/bin/bash
# Database Cluster Failure Remediation

DB_CLUSTER="$1"
DB_TYPE="${2:-postgresql}"  # postgresql, mysql, redis, mongodb

echo "=== Database Cluster Remediation ==="
echo "Cluster: $DB_CLUSTER"
echo "Type: $DB_TYPE"

case "$DB_TYPE" in
  postgresql)
    # PostgreSQL cluster remediation
    echo "Checking PostgreSQL cluster status..."

    # Check if primary is accessible
    PRIMARY_HOST=$(psql -h "$DB_CLUSTER" -U postgres -t -c "SELECT inet_server_addr();" 2>/dev/null)

    if [ -z "$PRIMARY_HOST" ]; then
      echo "ERROR: Cannot connect to primary database"

      # Check replication status
      echo "Checking replicas..."

      # List of replica hosts (should be in config)
      REPLICA_HOSTS="${REPLICA_HOSTS:-replica1,replica2}"

      for replica in ${REPLICA_HOSTS//,/ }; do
        echo "Checking replica: $replica"

        if psql -h "$replica" -U postgres -t -c "SELECT 1" > /dev/null 2>&1; then
          echo "Replica $replica is accessible"

          # Check if replica can be promoted
          REPLICATION_LAG=$(psql -h "$replica" -U postgres -t -c "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()));" 2>/dev/null)

          echo "Replication lag: ${REPLICATION_LAG} seconds"

          if (( $(echo "$REPLICATION_LAG < 10" | bc -l) )); then
            echo "Replica is up-to-date, can be promoted"

            # CRITICAL: Requires manual approval for failover
            echo "ESCALATION: Database failover required"
            echo "Recommended action: Promote replica $replica to primary"

            # Create incident ticket
            # Notify on-call DBA

            exit 1
          fi
        fi
      done
    else
      echo "Primary database is accessible: $PRIMARY_HOST"

      # Check for long-running queries
      LONG_QUERIES=$(psql -h "$DB_CLUSTER" -U postgres -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';" 2>/dev/null)

      if [ "$LONG_QUERIES" -gt 0 ]; then
        echo "WARNING: $LONG_QUERIES long-running queries detected"

        # Kill long-running queries (with caution)
        echo "Terminating long-running queries..."
        psql -h "$DB_CLUSTER" -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '10 minutes' AND usename != 'postgres';"
      fi

      echo "SUCCESS: Database cluster is healthy"
      exit 0
    fi
    ;;

  mysql)
    # MySQL cluster remediation
    echo "Checking MySQL cluster status..."

    # Check if master is accessible
    if mysql -h "$DB_CLUSTER" -u root -e "SELECT 1" > /dev/null 2>&1; then
      echo "MySQL master is accessible"

      # Check replication status
      mysql -h "$DB_CLUSTER" -u root -e "SHOW SLAVE STATUS\G"

      exit 0
    else
      echo "ERROR: Cannot connect to MySQL master"
      exit 1
    fi
    ;;

  redis)
    # Redis cluster remediation
    echo "Checking Redis cluster status..."

    if redis-cli -h "$DB_CLUSTER" ping > /dev/null 2>&1; then
      echo "Redis is accessible"

      # Check cluster info
      redis-cli -h "$DB_CLUSTER" cluster info

      # Check for failed nodes
      FAILED_NODES=$(redis-cli -h "$DB_CLUSTER" cluster nodes | grep "fail" | wc -l)

      if [ "$FAILED_NODES" -gt 0 ]; then
        echo "WARNING: $FAILED_NODES failed nodes in cluster"

        # Attempt to fix cluster
        redis-cli -h "$DB_CLUSTER" cluster fix
      fi

      exit 0
    else
      echo "ERROR: Cannot connect to Redis"
      exit 1
    fi
    ;;
esac
```

---

## Backup System Failures

### Remediation Playbook: INFRA-BACKUP-FAILURE-001

**Severity**: High
**Auto-remediation**: Limited

```bash
#!/bin/bash
# Backup System Failure Remediation

BACKUP_JOB="$1"
BACKUP_TYPE="${2:-filesystem}"  # filesystem, database, cloud

echo "=== Backup Failure Remediation ==="
echo "Backup Job: $BACKUP_JOB"
echo "Type: $BACKUP_TYPE"

# Step 1: Check backup status
echo "Step 1: Checking backup status..."

case "$BACKUP_TYPE" in
  filesystem)
    # Check if backup destination is accessible
    BACKUP_DEST="/var/backups"

    if [ ! -d "$BACKUP_DEST" ]; then
      echo "ERROR: Backup destination does not exist: $BACKUP_DEST"
      mkdir -p "$BACKUP_DEST"
    fi

    # Check disk space
    BACKUP_SPACE=$(df -h "$BACKUP_DEST" | tail -1 | awk '{print $5}' | sed 's/%//')

    if [ "$BACKUP_SPACE" -gt 90 ]; then
      echo "ERROR: Backup destination is ${BACKUP_SPACE}% full"

      # Clean old backups
      echo "Cleaning old backups..."
      find "$BACKUP_DEST" -type f -mtime +30 -delete

      echo "Old backups cleaned"
    fi
    ;;

  database)
    # Check database backup
    echo "Checking database backup..."

    # Verify last backup
    LAST_BACKUP=$(ls -t /var/lib/postgresql/backups/*.dump 2>/dev/null | head -1)

    if [ -z "$LAST_BACKUP" ]; then
      echo "ERROR: No recent database backups found"

      # Trigger manual backup
      echo "Triggering manual backup..."
      pg_dump -h localhost -U postgres -Fc database_name > "/var/lib/postgresql/backups/manual_backup_$(date +%Y%m%d_%H%M%S).dump"

      exit 0
    else
      BACKUP_AGE=$(find "$LAST_BACKUP" -mtime +1 | wc -l)

      if [ "$BACKUP_AGE" -gt 0 ]; then
        echo "WARNING: Last backup is older than 24 hours"

        # Trigger new backup
        echo "Triggering new backup..."
        pg_dump -h localhost -U postgres -Fc database_name > "/var/lib/postgresql/backups/backup_$(date +%Y%m%d_%H%M%S).dump"
      else
        echo "Recent backup found: $LAST_BACKUP"
      fi
    fi
    ;;

  cloud)
    # Check cloud backup (S3, GCS, Azure Blob)
    echo "Checking cloud backup..."

    # Example for AWS S3
    BUCKET="s3://backups-bucket"

    LAST_BACKUP=$(aws s3 ls "$BUCKET/" --recursive | sort | tail -1 | awk '{print $4}')

    if [ -z "$LAST_BACKUP" ]; then
      echo "ERROR: No backups found in $BUCKET"
      exit 1
    else
      echo "Last backup: $LAST_BACKUP"
    fi
    ;;
esac

echo "SUCCESS: Backup system remediated"
exit 0
```

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintained By**: cortex development master
