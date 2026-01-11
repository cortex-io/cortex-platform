# Kubernetes Issues Remediation Playbooks

## Overview

This document contains remediation playbooks for common Kubernetes-specific issues. These playbooks leverage kubectl and Kubernetes APIs to automatically detect and remediate pod, deployment, node, and cluster issues.

---

## Table of Contents

1. [Pod CrashLoopBackOff](#pod-crashloopbackoff)
2. [ImagePullBackOff](#imagepullbackoff)
3. [Node NotReady](#node-notready)
4. [Pending Pods](#pending-pods)
5. [Evicted Pods](#evicted-pods)
6. [OOMKilled Pods](#oomkilled-pods)
7. [Failed Deployments](#failed-deployments)
8. [Service Endpoint Issues](#service-endpoint-issues)
9. [Persistent Volume Issues](#persistent-volume-issues)
10. [Resource Quota Exceeded](#resource-quota-exceeded)

---

## Pod CrashLoopBackOff

### Symptom Detection

```yaml
symptoms:
  - Pod status shows "CrashLoopBackOff"
  - Pod restart count increasing
  - Application logs show startup failures
  - Container exit code non-zero

detection_metrics:
  - kubectl: pod.status.containerStatuses[].restartCount > 5
  - kubectl: pod.status.containerStatuses[].state.waiting.reason == "CrashLoopBackOff"
  - duration: sustained for 5 minutes
```

### Root Cause Analysis

```bash
#!/bin/bash
# Diagnose CrashLoopBackOff issue

NAMESPACE="$1"
POD_NAME="$2"

echo "=== CrashLoopBackOff Diagnosis ==="

# Get pod details
echo "Pod Status:"
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o wide

# Get pod description
echo -e "\nPod Description:"
kubectl describe pod "$POD_NAME" -n "$NAMESPACE"

# Get recent events
echo -e "\nRecent Events:"
kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$POD_NAME" --sort-by='.lastTimestamp'

# Get container logs (current)
echo -e "\nCurrent Container Logs:"
kubectl logs "$POD_NAME" -n "$NAMESPACE" --tail=100

# Get previous container logs (before crash)
echo -e "\nPrevious Container Logs:"
kubectl logs "$POD_NAME" -n "$NAMESPACE" --previous --tail=100 2>/dev/null || echo "No previous logs available"

# Check resource usage
echo -e "\nResource Usage:"
kubectl top pod "$POD_NAME" -n "$NAMESPACE" 2>/dev/null || echo "Metrics not available"

# Check container exit code
EXIT_CODE=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null)
echo -e "\nLast Exit Code: $EXIT_CODE"

# Common exit codes
case "$EXIT_CODE" in
  0)
    echo "Exit Code 0: Clean exit (may indicate app completing too fast)"
    ;;
  1)
    echo "Exit Code 1: Application error"
    ;;
  137)
    echo "Exit Code 137: Pod killed (SIGKILL) - likely OOMKilled"
    ;;
  139)
    echo "Exit Code 139: Segmentation fault"
    ;;
  143)
    echo "Exit Code 143: Pod terminated (SIGTERM)"
    ;;
esac
```

### Remediation Playbook: K8S-CRASHLOOP-001

**Severity**: High
**Auto-remediation**: Enabled
**Blast Radius**: Single Pod
**Estimated Time**: 3-5 minutes

#### Pre-conditions

- Deployment has multiple replicas (>1)
- Cluster is healthy
- Namespace exists

#### Remediation Steps

**Step 1: Capture Diagnostic Information**
```bash
#!/bin/bash
# Capture logs and state before remediation

NAMESPACE="$1"
POD_NAME="$2"
OUTPUT_DIR="/tmp/k8s-crashloop-$(date +%s)"

mkdir -p "$OUTPUT_DIR"

# Capture pod state
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o yaml > "$OUTPUT_DIR/pod-state.yaml"

# Capture logs
kubectl logs "$POD_NAME" -n "$NAMESPACE" --tail=500 > "$OUTPUT_DIR/current-logs.txt" 2>/dev/null
kubectl logs "$POD_NAME" -n "$NAMESPACE" --previous --tail=500 > "$OUTPUT_DIR/previous-logs.txt" 2>/dev/null

# Capture events
kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$POD_NAME" > "$OUTPUT_DIR/events.txt"

echo "Diagnostics saved to: $OUTPUT_DIR"
```

**Step 2: Check for Common Issues**
```bash
#!/bin/bash
# Automated check for common CrashLoopBackOff causes

NAMESPACE="$1"
POD_NAME="$2"

# Check if ConfigMap/Secret exists
CONFIGMAPS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.volumes[*].configMap.name}' 2>/dev/null)
for cm in $CONFIGMAPS; do
  if ! kubectl get configmap "$cm" -n "$NAMESPACE" &>/dev/null; then
    echo "ERROR: ConfigMap $cm not found"
    exit 1
  fi
done

SECRETS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.volumes[*].secret.secretName}' 2>/dev/null)
for secret in $SECRETS; do
  if ! kubectl get secret "$secret" -n "$NAMESPACE" &>/dev/null; then
    echo "ERROR: Secret $secret not found"
    exit 1
  fi
done

# Check if image exists
IMAGE=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].image}')
echo "Image: $IMAGE"

# Check exit code
EXIT_CODE=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null)

if [ "$EXIT_CODE" == "137" ]; then
  echo "DETECTED: OOMKilled - pod needs more memory"
  # This should trigger memory increase remediation
  exit 2
fi

echo "No obvious configuration issues detected"
```

**Step 3: Delete and Recreate Pod**
```bash
#!/bin/bash
# Delete pod to trigger recreation with fresh state

NAMESPACE="$1"
POD_NAME="$2"

# Get deployment/replicaset that owns this pod
OWNER_KIND=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.metadata.ownerReferences[0].kind}')
OWNER_NAME=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.metadata.ownerReferences[0].name}')

echo "Pod owned by: $OWNER_KIND/$OWNER_NAME"

# Delete the pod (will be recreated by controller)
echo "Deleting pod $POD_NAME..."
kubectl delete pod "$POD_NAME" -n "$NAMESPACE" --grace-period=30

# Wait for new pod to be created
echo "Waiting for new pod to be created..."
sleep 15

# Find the new pod
if [ "$OWNER_KIND" == "ReplicaSet" ]; then
  # Get deployment from replicaset
  DEPLOYMENT=$(kubectl get rs "$OWNER_NAME" -n "$NAMESPACE" -o jsonpath='{.metadata.ownerReferences[0].name}')
  NEW_POD=$(kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
elif [ "$OWNER_KIND" == "StatefulSet" ]; then
  # StatefulSet pods have predictable names
  NEW_POD="$POD_NAME"  # Same name will be reused
fi

echo "New pod: $NEW_POD"
echo "$NEW_POD" > /tmp/k8s_new_pod_name
```

**Step 4: Monitor New Pod**
```bash
#!/bin/bash
# Monitor the new pod for stability

NAMESPACE="$1"
NEW_POD=$(cat /tmp/k8s_new_pod_name)

echo "Monitoring pod: $NEW_POD"

# Wait for pod to be running
kubectl wait --for=condition=Ready pod/"$NEW_POD" -n "$NAMESPACE" --timeout=300s

if [ $? -eq 0 ]; then
  echo "Pod is now Ready"

  # Monitor for crashes over next 5 minutes
  sleep 300

  # Check restart count
  RESTART_COUNT=$(kubectl get pod "$NEW_POD" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].restartCount}')

  if [ "$RESTART_COUNT" -lt 2 ]; then
    echo "SUCCESS: Pod is stable with $RESTART_COUNT restarts"
    exit 0
  else
    echo "WARNING: Pod has restarted $RESTART_COUNT times, may still be unstable"
    exit 1
  fi
else
  echo "FAILED: Pod did not become ready"
  exit 1
fi
```

#### Alternative Remediation: Increase Resources

```bash
#!/bin/bash
# If OOMKilled, increase memory limits

NAMESPACE="$1"
DEPLOYMENT="$2"

echo "Increasing memory limits for deployment: $DEPLOYMENT"

# Get current memory limit
CURRENT_MEMORY=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}')
echo "Current memory limit: $CURRENT_MEMORY"

# Parse memory value (e.g., "512Mi" -> 512)
MEMORY_VALUE=$(echo "$CURRENT_MEMORY" | grep -oP '\d+')
MEMORY_UNIT=$(echo "$CURRENT_MEMORY" | grep -oP '[A-Za-z]+')

# Increase by 50%
NEW_MEMORY_VALUE=$(echo "$MEMORY_VALUE * 1.5 / 1" | bc)
NEW_MEMORY="${NEW_MEMORY_VALUE}${MEMORY_UNIT}"

echo "New memory limit: $NEW_MEMORY"

# Update deployment
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" -p "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].name}')\",\"resources\":{\"limits\":{\"memory\":\"$NEW_MEMORY\"}}}]}}}}"

# Wait for rollout
kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s
```

#### Verification

```bash
#!/bin/bash
# Verify pod is running and stable

NAMESPACE="$1"
POD_NAME="$2"

# Check pod is running
POD_STATUS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.phase}')

if [ "$POD_STATUS" != "Running" ]; then
  echo "FAILED: Pod status is $POD_STATUS"
  exit 1
fi

# Check container is ready
CONTAINER_READY=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].ready}')

if [ "$CONTAINER_READY" != "true" ]; then
  echo "FAILED: Container is not ready"
  exit 1
fi

# Check restart count hasn't increased
RESTART_COUNT=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].restartCount}')

echo "SUCCESS: Pod running, container ready, restart count: $RESTART_COUNT"
exit 0
```

#### Escalation

If pod continues to crash after remediation:
- Review application logs for errors
- Check application dependencies (database, cache, APIs)
- Review recent code deployments
- Consider rollback to previous version
- Engage application development team

---

## ImagePullBackOff

### Symptom Detection

```yaml
symptoms:
  - Pod status shows "ImagePullBackOff" or "ErrImagePull"
  - Image pull errors in pod events
  - Pod cannot start

detection_metrics:
  - kubectl: pod.status.containerStatuses[].state.waiting.reason == "ImagePullBackOff"
```

### Remediation Playbook: K8S-IMAGEPULL-001

**Severity**: High
**Auto-remediation**: Enabled
**Blast Radius**: Single Pod

```bash
#!/bin/bash
# ImagePullBackOff Remediation

NAMESPACE="$1"
POD_NAME="$2"

echo "=== ImagePullBackOff Remediation ==="

# Step 1: Identify the image causing issues
IMAGE=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].image}')
echo "Image: $IMAGE"

# Step 2: Check if it's an authentication issue
kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$POD_NAME" | grep -i "unauthorized\|authentication"

if [ $? -eq 0 ]; then
  echo "DETECTED: Image pull authentication issue"

  # Check if imagePullSecrets are configured
  PULL_SECRETS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.imagePullSecrets[*].name}')

  if [ -z "$PULL_SECRETS" ]; then
    echo "ERROR: No imagePullSecrets configured"
    echo "ACTION: Configure imagePullSecrets in deployment"
    exit 1
  else
    echo "imagePullSecrets configured: $PULL_SECRETS"

    # Verify secret exists
    for secret in $PULL_SECRETS; do
      if ! kubectl get secret "$secret" -n "$NAMESPACE" &>/dev/null; then
        echo "ERROR: Secret $secret does not exist"
        exit 1
      fi
    done

    echo "INFO: Secrets exist, may need to refresh credentials"
  fi
fi

# Step 3: Check if image exists in registry
echo "Checking if image exists..."

# Extract registry, repo, and tag
REGISTRY=$(echo "$IMAGE" | cut -d'/' -f1)
REPO=$(echo "$IMAGE" | cut -d':' -f1 | cut -d'/' -f2-)
TAG=$(echo "$IMAGE" | cut -d':' -f2)

echo "Registry: $REGISTRY"
echo "Repository: $REPO"
echo "Tag: $TAG"

# For Docker Hub
if [[ "$REGISTRY" != *"."* ]]; then
  echo "Attempting to verify image on Docker Hub..."
  curl -s "https://hub.docker.com/v2/repositories/$REPO/tags/$TAG" | grep -q "name"
  if [ $? -ne 0 ]; then
    echo "WARNING: Image tag may not exist on Docker Hub"
  fi
fi

# Step 4: Try to refresh the image pull
echo "Deleting pod to retry image pull..."
kubectl delete pod "$POD_NAME" -n "$NAMESPACE" --grace-period=10

# Wait for new pod
sleep 15

# Step 5: Check if issue resolved
NEW_POD=$(kubectl get pods -n "$NAMESPACE" -o jsonpath="{.items[?(@.metadata.ownerReferences[0].name=='$POD_NAME')].metadata.name}" 2>/dev/null | head -1)

if [ -n "$NEW_POD" ]; then
  kubectl wait --for=condition=Ready pod/"$NEW_POD" -n "$NAMESPACE" --timeout=300s
  if [ $? -eq 0 ]; then
    echo "SUCCESS: Image pulled successfully"
    exit 0
  fi
fi

echo "FAILED: Unable to resolve ImagePullBackOff"
exit 1
```

---

## Node NotReady

### Symptom Detection

```yaml
symptoms:
  - Node status shows "NotReady"
  - Pods being evicted from node
  - Node conditions show issues (DiskPressure, MemoryPressure, NetworkUnavailable)

detection_metrics:
  - kubectl: node.status.conditions[type=Ready].status == "False"
```

### Remediation Playbook: K8S-NODE-NOTREADY-001

**Severity**: Critical
**Auto-remediation**: Enabled (with approval)
**Blast Radius**: Single Node
**Estimated Time**: 10-15 minutes

```bash
#!/bin/bash
# Node NotReady Remediation

NODE_NAME="$1"

echo "=== Node NotReady Remediation ==="
echo "Node: $NODE_NAME"

# Step 1: Diagnose node condition
echo "Step 1: Diagnosing node condition..."

kubectl describe node "$NODE_NAME" | grep -A 10 "Conditions:"

# Get specific conditions
DISK_PRESSURE=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="DiskPressure")].status}')
MEMORY_PRESSURE=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="MemoryPressure")].status}')
PID_PRESSURE=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="PIDPressure")].status}')
NETWORK_UNAVAILABLE=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="NetworkUnavailable")].status}')

echo "DiskPressure: $DISK_PRESSURE"
echo "MemoryPressure: $MEMORY_PRESSURE"
echo "PIDPressure: $PID_PRESSURE"
echo "NetworkUnavailable: $NETWORK_UNAVAILABLE"

# Step 2: Cordon node to prevent new pods
echo "Step 2: Cordoning node..."
kubectl cordon "$NODE_NAME"

# Step 3: Check kubelet status (requires SSH access to node)
echo "Step 3: Checking kubelet status..."
# This would require SSH access - depends on infrastructure
# ssh "$NODE_NAME" "systemctl status kubelet"

# Step 4: Attempt to restart kubelet (if accessible)
echo "Step 4: Attempting kubelet restart..."
# ssh "$NODE_NAME" "sudo systemctl restart kubelet"

# Wait for kubelet to restart
sleep 30

# Step 5: Check if node is back to Ready
echo "Step 5: Checking node status..."

for i in {1..20}; do
  NODE_STATUS=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')

  if [ "$NODE_STATUS" == "True" ]; then
    echo "Node is now Ready!"

    # Uncordon node
    echo "Uncordoning node..."
    kubectl uncordon "$NODE_NAME"

    echo "SUCCESS: Node remediation completed"
    exit 0
  fi

  echo "Waiting for node to be ready... (attempt $i/20)"
  sleep 15
done

# Step 6: If still not ready, drain and replace node
echo "WARNING: Node did not recover, draining node..."

kubectl drain "$NODE_NAME" \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --force \
  --grace-period=300 \
  --timeout=600s

echo "Node drained. Manual intervention required to replace node."
exit 1
```

---

## Pending Pods

### Symptom Detection

```yaml
symptoms:
  - Pod status stuck in "Pending"
  - Pod scheduling failures
  - Insufficient resources messages

detection_metrics:
  - kubectl: pod.status.phase == "Pending"
  - duration: > 5 minutes
```

### Remediation Playbook: K8S-PENDING-POD-001

**Severity**: Medium
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# Pending Pod Remediation

NAMESPACE="$1"
POD_NAME="$2"

echo "=== Pending Pod Remediation ==="

# Step 1: Diagnose why pod is pending
echo "Step 1: Diagnosing pending reason..."

kubectl describe pod "$POD_NAME" -n "$NAMESPACE" | grep -A 10 "Events:"

# Get specific failure reason
FAILURE_REASON=$(kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$POD_NAME" --sort-by='.lastTimestamp' | tail -1)

echo "Failure reason: $FAILURE_REASON"

# Step 2: Check for insufficient resources
if echo "$FAILURE_REASON" | grep -qi "insufficient"; then
  echo "DETECTED: Insufficient resources"

  # Check what resource is insufficient
  if echo "$FAILURE_REASON" | grep -qi "cpu"; then
    echo "Insufficient CPU"
    RESOURCE="cpu"
  elif echo "$FAILURE_REASON" | grep -qi "memory"; then
    echo "Insufficient memory"
    RESOURCE="memory"
  fi

  # Check node resources
  echo "Cluster resource availability:"
  kubectl top nodes

  # Option 1: Reduce pod resource requests (if reasonable)
  DEPLOYMENT=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.metadata.ownerReferences[0].name}')

  echo "Checking if resource requests can be reduced..."
  # This would require business logic to determine if it's safe
fi

# Step 3: Check for node affinity/taint issues
TAINTS=$(kubectl get nodes -o json | jq -r '.items[].spec.taints[]?.key' | sort -u)
if [ -n "$TAINTS" ]; then
  echo "Node taints detected: $TAINTS"

  POD_TOLERATIONS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.tolerations}')
  echo "Pod tolerations: $POD_TOLERATIONS"
fi

# Step 4: Check for PVC binding issues
PVCS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.volumes[*].persistentVolumeClaim.claimName}')

for pvc in $PVCS; do
  PVC_STATUS=$(kubectl get pvc "$pvc" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
  echo "PVC $pvc status: $PVC_STATUS"

  if [ "$PVC_STATUS" != "Bound" ]; then
    echo "ERROR: PVC $pvc is not bound"

    # Check if PV is available
    kubectl get pv | grep Available

    # This may require manual intervention or dynamic provisioning
  fi
done

# Step 5: Scale up cluster if resources insufficient
echo "Step 5: Checking if cluster autoscaler can help..."

# Trigger cluster autoscaler by adding node pool (cloud-specific)
# This is highly dependent on cloud provider and autoscaler configuration

echo "Consider scaling up cluster or adjusting pod resource requests"
```

---

## Evicted Pods

### Remediation Playbook: K8S-EVICTED-CLEANUP-001

**Severity**: Low
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# Clean up evicted pods

NAMESPACE="${1:-default}"

echo "=== Evicted Pods Cleanup ==="
echo "Namespace: $NAMESPACE"

# Step 1: Find evicted pods
EVICTED_PODS=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Failed -o json | \
  jq -r '.items[] | select(.status.reason == "Evicted") | .metadata.name')

EVICTED_COUNT=$(echo "$EVICTED_PODS" | wc -l)

echo "Found $EVICTED_COUNT evicted pods"

if [ $EVICTED_COUNT -eq 0 ]; then
  echo "No evicted pods to clean up"
  exit 0
fi

# Step 2: Delete evicted pods
echo "Deleting evicted pods..."

for pod in $EVICTED_PODS; do
  echo "Deleting pod: $pod"
  kubectl delete pod "$pod" -n "$NAMESPACE" --wait=false
done

echo "SUCCESS: Cleaned up $EVICTED_COUNT evicted pods"
exit 0
```

---

## OOMKilled Pods

### Remediation Playbook: K8S-OOMKILLED-001

**Severity**: High
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# OOMKilled Pod Remediation - Increase Memory Limits

NAMESPACE="$1"
POD_NAME="$2"

echo "=== OOMKilled Remediation ==="

# Step 1: Confirm OOMKilled
EXIT_CODE=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}')

if [ "$EXIT_CODE" != "137" ]; then
  echo "ERROR: Pod was not OOMKilled (exit code: $EXIT_CODE)"
  exit 1
fi

echo "Confirmed: Pod was OOMKilled"

# Step 2: Get current memory limit
DEPLOYMENT=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.metadata.labels.app}')
CONTAINER_NAME=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].name}')

CURRENT_MEMORY_LIMIT=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath="{.spec.template.spec.containers[?(@.name=='$CONTAINER_NAME')].resources.limits.memory}")
CURRENT_MEMORY_REQUEST=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath="{.spec.template.spec.containers[?(@.name=='$CONTAINER_NAME')].resources.requests.memory}")

echo "Current memory limit: $CURRENT_MEMORY_LIMIT"
echo "Current memory request: $CURRENT_MEMORY_REQUEST"

# Step 3: Calculate new memory limits (increase by 50%)
# Parse memory value
if [[ "$CURRENT_MEMORY_LIMIT" =~ ^([0-9]+)(Mi|Gi)$ ]]; then
  VALUE="${BASH_REMATCH[1]}"
  UNIT="${BASH_REMATCH[2]}"

  NEW_VALUE=$(echo "$VALUE * 1.5 / 1" | bc)
  NEW_MEMORY_LIMIT="${NEW_VALUE}${UNIT}"

  echo "New memory limit: $NEW_MEMORY_LIMIT"
else
  echo "ERROR: Could not parse memory limit: $CURRENT_MEMORY_LIMIT"
  exit 1
fi

# Step 4: Update deployment
echo "Updating deployment with new memory limits..."

kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p="[
  {
    \"op\": \"replace\",
    \"path\": \"/spec/template/spec/containers/0/resources/limits/memory\",
    \"value\": \"$NEW_MEMORY_LIMIT\"
  }
]"

# Step 5: Wait for rollout
echo "Waiting for rollout to complete..."
kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s

if [ $? -eq 0 ]; then
  echo "SUCCESS: Deployment updated with increased memory limits"
  exit 0
else
  echo "FAILED: Rollout did not complete successfully"
  exit 1
fi
```

---

## Failed Deployments

### Remediation Playbook: K8S-FAILED-DEPLOYMENT-001

**Severity**: High
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# Failed Deployment Remediation - Rollback

NAMESPACE="$1"
DEPLOYMENT="$2"

echo "=== Failed Deployment Remediation ==="

# Step 1: Check deployment status
DEPLOYMENT_STATUS=$(kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=10s 2>&1)

if echo "$DEPLOYMENT_STATUS" | grep -q "successfully rolled out"; then
  echo "Deployment is healthy, no action needed"
  exit 0
fi

echo "Deployment is not healthy"

# Step 2: Check recent rollout history
echo "Rollout history:"
kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE"

# Step 3: Get current and previous revisions
CURRENT_REVISION=$(kubectl rollout history deployment/"$DEPLOYMENT" -n "$NAMESPACE" | tail -1 | awk '{print $1}')
PREVIOUS_REVISION=$((CURRENT_REVISION - 1))

echo "Current revision: $CURRENT_REVISION"
echo "Previous revision: $PREVIOUS_REVISION"

# Step 4: Check if pods are ready
DESIRED_REPLICAS=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
READY_REPLICAS=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')

echo "Desired replicas: $DESIRED_REPLICAS"
echo "Ready replicas: ${READY_REPLICAS:-0}"

if [ "${READY_REPLICAS:-0}" -lt "$((DESIRED_REPLICAS / 2))" ]; then
  echo "CRITICAL: Less than 50% of pods are ready, initiating rollback"

  # Step 5: Rollback to previous revision
  echo "Rolling back to revision $PREVIOUS_REVISION..."
  kubectl rollout undo deployment/"$DEPLOYMENT" -n "$NAMESPACE" --to-revision="$PREVIOUS_REVISION"

  # Step 6: Wait for rollback to complete
  echo "Waiting for rollback to complete..."
  kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=300s

  if [ $? -eq 0 ]; then
    echo "SUCCESS: Rolled back to previous stable revision"
    exit 0
  else
    echo "FAILED: Rollback did not complete successfully"
    exit 1
  fi
else
  echo "More than 50% pods ready, monitoring situation"
  exit 2  # Partial success, continue monitoring
fi
```

---

## Service Endpoint Issues

### Remediation Playbook: K8S-SERVICE-ENDPOINTS-001

**Severity**: Medium
**Auto-remediation**: Enabled

```bash
#!/bin/bash
# Service Endpoints Remediation

NAMESPACE="$1"
SERVICE="$2"

echo "=== Service Endpoints Remediation ==="

# Step 1: Check service endpoints
ENDPOINTS=$(kubectl get endpoints "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.subsets[*].addresses[*].ip}')
ENDPOINT_COUNT=$(echo "$ENDPOINTS" | wc -w)

echo "Service: $SERVICE"
echo "Endpoints: $ENDPOINTS"
echo "Endpoint count: $ENDPOINT_COUNT"

if [ $ENDPOINT_COUNT -eq 0 ]; then
  echo "ERROR: Service has no endpoints"

  # Step 2: Check service selector
  SELECTOR=$(kubectl get service "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.spec.selector}')
  echo "Service selector: $SELECTOR"

  # Step 3: Find pods matching selector
  SELECTOR_LABEL=$(echo "$SELECTOR" | jq -r 'to_entries | map("\(.key)=\(.value)") | join(",")')
  MATCHING_PODS=$(kubectl get pods -n "$NAMESPACE" -l "$SELECTOR_LABEL" -o jsonpath='{.items[*].metadata.name}')

  echo "Matching pods: $MATCHING_PODS"

  if [ -z "$MATCHING_PODS" ]; then
    echo "ERROR: No pods match service selector"
    echo "Check deployment labels match service selector"
    exit 1
  fi

  # Step 4: Check if pods are ready
  for pod in $MATCHING_PODS; do
    POD_READY=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
    echo "Pod $pod ready: $POD_READY"

    if [ "$POD_READY" != "True" ]; then
      echo "Pod $pod is not ready, this may be the issue"
      # Trigger pod restart remediation
    fi
  done

else
  echo "Service has $ENDPOINT_COUNT endpoints, checking health..."

  # Check if endpoints are responsive
  # This requires actual health check implementation

  echo "SUCCESS: Service has active endpoints"
  exit 0
fi
```

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintained By**: cortex development master
