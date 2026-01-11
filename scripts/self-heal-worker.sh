#!/bin/bash
# Self-Healing Worker Script
# Diagnoses and attempts to fix service failures in the Cortex system

set -euo pipefail

# Input parameters
SERVICE_NAME="${1:-}"
ERROR_MESSAGE="${2:-}"
SERVER_URL="${3:-}"

# Logging
log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [HEAL-WORKER] $*"
}

progress() {
    echo "PROGRESS: $*"
}

# Validate inputs
if [[ -z "$SERVICE_NAME" ]]; then
    log "ERROR: SERVICE_NAME is required"
    echo '{"success": false, "diagnosis": "Missing service name parameter"}'
    exit 1
fi

log "Starting self-healing for service: $SERVICE_NAME"
log "Error: $ERROR_MESSAGE"
log "Server URL: $SERVER_URL"

# Extract namespace and deployment from service name
NAMESPACE="cortex-system"
DEPLOYMENT="$SERVICE_NAME"

# Diagnostic results
DIAGNOSIS=""
FIX_APPLIED=""
SUCCESS=false

# Function to check pod status
check_pod_status() {
    progress "Checking pod status for $DEPLOYMENT..."

    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" -o json 2>/dev/null || echo '{"items":[]}')

    local pod_count
    pod_count=$(echo "$pods" | jq -r '.items | length')

    if [[ "$pod_count" -eq 0 ]]; then
        DIAGNOSIS+="No pods found for deployment $DEPLOYMENT. "
        return 1
    fi

    log "Found $pod_count pod(s)"

    # Check pod states
    local ready_pods
    ready_pods=$(echo "$pods" | jq -r '[.items[] | select(.status.conditions[]? | select(.type=="Ready" and .status=="True"))] | length')

    local crash_looping
    crash_looping=$(echo "$pods" | jq -r '[.items[] | select(.status.containerStatuses[]? | select(.state.waiting?.reason=="CrashLoopBackOff"))] | length')

    local image_pull_errors
    image_pull_errors=$(echo "$pods" | jq -r '[.items[] | select(.status.containerStatuses[]? | select(.state.waiting?.reason | contains("ImagePull")))] | length')

    DIAGNOSIS+="Pods: total=$pod_count ready=$ready_pods crashloop=$crash_looping imagepull_errors=$image_pull_errors. "

    log "Pod status: total=$pod_count ready=$ready_pods crashloop=$crash_looping imagepull_errors=$image_pull_errors"

    # Return status codes for remediation
    if [[ "$crash_looping" -gt 0 ]]; then
        return 2  # CrashLoopBackOff
    elif [[ "$image_pull_errors" -gt 0 ]]; then
        return 3  # ImagePullBackOff
    elif [[ "$ready_pods" -eq 0 ]]; then
        return 4  # No ready pods
    elif [[ "$ready_pods" -lt "$pod_count" ]]; then
        return 5  # Some pods not ready
    fi

    return 0  # All good
}

# Function to check service endpoints
check_service_endpoints() {
    progress "Checking service endpoints..."

    local endpoints
    endpoints=$(kubectl get endpoints -n "$NAMESPACE" "$SERVICE_NAME" -o json 2>/dev/null || echo '{"subsets":[]}')

    local endpoint_count
    endpoint_count=$(echo "$endpoints" | jq -r '[.subsets[]?.addresses[]?] | length')

    if [[ "$endpoint_count" -eq 0 ]]; then
        DIAGNOSIS+="No service endpoints available. "
        log "No service endpoints found"
        return 1
    fi

    DIAGNOSIS+="Service has $endpoint_count endpoint(s). "
    log "Service has $endpoint_count endpoint(s)"
    return 0
}

# Function to check recent logs for errors
check_pod_logs() {
    progress "Checking recent pod logs..."

    local pod_name
    pod_name=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [[ -z "$pod_name" ]]; then
        log "No pod found to check logs"
        return 1
    fi

    local logs
    logs=$(kubectl logs -n "$NAMESPACE" "$pod_name" --tail=50 2>&1 || echo "")

    # Check for common error patterns
    if echo "$logs" | grep -qi "error\|exception\|failed\|refused"; then
        local error_lines
        error_lines=$(echo "$logs" | grep -i "error\|exception\|failed\|refused" | tail -3 | tr '\n' '; ')
        DIAGNOSIS+="Recent errors in logs: $error_lines "
        log "Found errors in logs: $error_lines"
    fi

    # Check for specific issues
    if echo "$logs" | grep -qi "connection refused"; then
        DIAGNOSIS+="Connection refused errors detected. "
    fi

    if echo "$logs" | grep -qi "econnrefused\|ENOTFOUND"; then
        DIAGNOSIS+="Network connectivity issues detected. "
    fi

    if echo "$logs" | grep -qi "auth\|unauthorized\|forbidden"; then
        DIAGNOSIS+="Authentication/authorization issues detected. "
    fi

    return 0
}

# Function to check deployment configuration
check_deployment_config() {
    progress "Checking deployment configuration..."

    local deployment
    deployment=$(kubectl get deployment -n "$NAMESPACE" "$DEPLOYMENT" -o json 2>/dev/null || echo '{}')

    if [[ $(echo "$deployment" | jq -r '.metadata.name // empty') == "" ]]; then
        DIAGNOSIS+="Deployment not found. "
        return 1
    fi

    # Check environment variables
    local has_required_env
    has_required_env=$(echo "$deployment" | jq -r '.spec.template.spec.containers[0].env | length')

    DIAGNOSIS+="Deployment has $has_required_env env vars configured. "

    return 0
}

# Function to restart pods
restart_pods() {
    progress "Restarting pods for $DEPLOYMENT..."

    if kubectl rollout restart deployment -n "$NAMESPACE" "$DEPLOYMENT" 2>&1; then
        FIX_APPLIED="Restarted deployment $DEPLOYMENT"
        log "Successfully restarted deployment"

        # Wait for rollout to complete (timeout 60s)
        progress "Waiting for rollout to complete..."
        if kubectl rollout status deployment -n "$NAMESPACE" "$DEPLOYMENT" --timeout=60s 2>&1; then
            log "Rollout completed successfully"
            return 0
        else
            log "Rollout timeout or failed"
            FIX_APPLIED+=" (rollout timeout)"
            return 1
        fi
    else
        log "Failed to restart deployment"
        return 1
    fi
}

# Function to scale deployment
scale_deployment() {
    local replicas="${1:-1}"
    progress "Scaling deployment to $replicas replicas..."

    if kubectl scale deployment -n "$NAMESPACE" "$DEPLOYMENT" --replicas="$replicas" 2>&1; then
        FIX_APPLIED="Scaled deployment to $replicas replicas"
        log "Successfully scaled deployment"

        # Wait for desired replicas
        sleep 5
        return 0
    else
        log "Failed to scale deployment"
        return 1
    fi
}

# Function to verify connectivity
verify_connectivity() {
    progress "Verifying service connectivity..."

    # Try to reach service endpoint from a test pod
    local test_result
    test_result=$(kubectl run test-connectivity-$RANDOM \
        --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        -n "$NAMESPACE" \
        --timeout=30s \
        -- curl -s -m 10 "http://$SERVICE_NAME:3000/health" 2>&1 || echo "FAILED")

    if echo "$test_result" | grep -qi "healthy\|ok\|success"; then
        DIAGNOSIS+="Service connectivity verified. "
        log "Service is reachable"
        return 0
    else
        DIAGNOSIS+="Service not reachable: $test_result "
        log "Service not reachable"
        return 1
    fi
}

# Function to check resource constraints
check_resource_limits() {
    progress "Checking resource limits..."

    local pod_name
    pod_name=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [[ -z "$pod_name" ]]; then
        return 1
    fi

    # Check if pod is being throttled or OOMKilled
    local pod_status
    pod_status=$(kubectl get pod -n "$NAMESPACE" "$pod_name" -o json 2>/dev/null || echo '{}')

    local oom_killed
    oom_killed=$(echo "$pod_status" | jq -r '.status.containerStatuses[]? | select(.lastState.terminated.reason=="OOMKilled") | .name' | wc -l)

    if [[ "$oom_killed" -gt 0 ]]; then
        DIAGNOSIS+="Pod was OOMKilled - insufficient memory. "
        log "Pod was terminated due to OOM"
        return 2
    fi

    # Check resource usage
    local metrics
    metrics=$(kubectl top pod -n "$NAMESPACE" "$pod_name" --no-headers 2>/dev/null || echo "")

    if [[ -n "$metrics" ]]; then
        DIAGNOSIS+="Resource usage: $metrics. "
        log "Resource metrics: $metrics"
    fi

    return 0
}

# Function to check network policies
check_network_policies() {
    progress "Checking network policies..."

    local netpols
    netpols=$(kubectl get networkpolicies -n "$NAMESPACE" -o json 2>/dev/null || echo '{"items":[]}')

    local netpol_count
    netpol_count=$(echo "$netpols" | jq -r '.items | length')

    if [[ "$netpol_count" -gt 0 ]]; then
        DIAGNOSIS+="$netpol_count network policies active. "
        log "Found $netpol_count network policies"

        # Check if any policies might be blocking our service
        local blocking_policies
        blocking_policies=$(echo "$netpols" | jq -r --arg svc "$SERVICE_NAME" '.items[] | select(.spec.podSelector.matchLabels.app==$svc) | .metadata.name')

        if [[ -n "$blocking_policies" ]]; then
            DIAGNOSIS+="Network policies affecting service: $blocking_policies. "
        fi
    fi

    return 0
}

# Function to delete failed pods
delete_failed_pods() {
    progress "Cleaning up failed pods..."

    local failed_pods
    failed_pods=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" \
        --field-selector=status.phase=Failed \
        -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

    if [[ -n "$failed_pods" ]]; then
        log "Deleting failed pods: $failed_pods"
        kubectl delete pods -n "$NAMESPACE" $failed_pods --grace-period=0 --force 2>&1 || true
        FIX_APPLIED+=" Cleaned up failed pods."
        return 0
    fi

    return 1
}

# Main healing workflow
main() {
    log "=== Starting Diagnosis Phase ==="

    # Step 1: Check pod status
    check_pod_status
    local pod_status=$?

    # Step 2: Check service endpoints
    check_service_endpoints
    local endpoint_status=$?

    # Step 3: Check logs
    check_pod_logs

    # Step 4: Check deployment config
    check_deployment_config

    # Step 5: Check resource limits
    check_resource_limits
    local resource_status=$?

    # Step 6: Check network policies
    check_network_policies

    # Step 7: Clean up failed pods
    delete_failed_pods

    log "=== Diagnosis Complete ==="
    log "Diagnosis: $DIAGNOSIS"

    # Determine remediation strategy
    log "=== Starting Remediation Phase ==="

    # Handle OOMKilled specifically
    if [[ "$resource_status" -eq 2 ]]; then
        log "Pod was OOMKilled - insufficient memory"
        DIAGNOSIS+="Cannot auto-fix OOMKilled pods - requires memory limit adjustment. "
        FIX_APPLIED="Cleaned up failed pods, but memory limits need to be increased."
        SUCCESS=false
    else
        case $pod_status in
            0)
                log "Pods are healthy, checking connectivity..."
                if ! verify_connectivity; then
                    log "Attempting pod restart to fix connectivity..."
                    if restart_pods; then
                        SUCCESS=true
                        verify_connectivity || true
                    fi
                else
                    SUCCESS=true
                    DIAGNOSIS+="Service is healthy after check. "
                fi
                ;;
            2)
                log "CrashLoopBackOff detected, restarting deployment..."
                if restart_pods; then
                    sleep 10
                    if check_pod_status && verify_connectivity; then
                        SUCCESS=true
                    fi
                fi
                ;;
            3)
                log "ImagePullBackOff detected, cannot auto-fix"
                DIAGNOSIS+="Manual intervention required: check image name/tags and registry access. "
                ;;
            4)
                log "No ready pods, attempting restart..."
                if restart_pods; then
                    sleep 10
                    if check_pod_status && verify_connectivity; then
                        SUCCESS=true
                    fi
                fi
                ;;
            5)
                log "Some pods not ready, waiting and rechecking..."
                sleep 10
                if check_pod_status; then
                    SUCCESS=true
                fi
                ;;
            *)
                log "No pods found, checking if deployment exists..."
                if check_deployment_config; then
                    log "Deployment exists but no pods, scaling up..."
                    if scale_deployment 1 && restart_pods; then
                        sleep 10
                        if check_pod_status && verify_connectivity; then
                            SUCCESS=true
                        fi
                    fi
                else
                    DIAGNOSIS+="Deployment not found, manual intervention required. "
                fi
                ;;
        esac
    fi

    log "=== Remediation Complete ==="

    # Generate final report
    if [[ "$SUCCESS" == true ]]; then
        log "Self-healing SUCCEEDED"
        echo "{
            \"success\": true,
            \"diagnosis\": \"$DIAGNOSIS\",
            \"fix_applied\": \"$FIX_APPLIED\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        }"
    else
        log "Self-healing FAILED"
        echo "{
            \"success\": false,
            \"diagnosis\": \"$DIAGNOSIS\",
            \"fix_attempted\": \"$FIX_APPLIED\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
            \"recommendation\": \"Manual intervention required. Check deployment configuration, image availability, and resource limits.\"
        }"
    fi
}

# Execute main workflow
main 2>&1 | tee /tmp/heal-worker-${SERVICE_NAME}-$(date +%s).log
