#!/bin/bash
set -euo pipefail

# 3-Larry Distributed Orchestration Execution Script
# This script launches all 3 Larry instances with their worker pools
# and monitors the execution until convergence

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
COORDINATION_PATH="/coordination"
REDIS_HOST="redis-cluster.redis-ha.svc.cluster.local"
REDIS_PORT="6379"
TIMEOUT=2400  # 40 minutes

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_larry() {
    local larry_id=$1
    local message=$2
    local color=$3
    echo -e "${color}[${larry_id}]${NC} $message"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi

    # Check redis-cli
    if ! command -v redis-cli &> /dev/null; then
        log_error "redis-cli not found. Please install redis-cli."
        exit 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to K8s cluster"
        exit 1
    fi

    # Check Redis connectivity
    if ! redis-cli -h $REDIS_HOST -p $REDIS_PORT ping &> /dev/null; then
        log_error "Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
        exit 1
    fi

    # Check K8s nodes
    local master_count=$(kubectl get nodes -l node-role.kubernetes.io/master --no-headers | wc -l)
    local worker_count=$(kubectl get nodes -l '!node-role.kubernetes.io/master' --no-headers | wc -l)

    if [ $master_count -lt 3 ]; then
        log_error "Expected 3 master nodes, found $master_count"
        exit 1
    fi

    if [ $worker_count -lt 4 ]; then
        log_error "Expected 4 worker nodes, found $worker_count"
        exit 1
    fi

    log_success "All prerequisites met"
    log_info "  - Masters: $master_count"
    log_info "  - Workers: $worker_count"
    log_info "  - Redis: Connected"
}

# Initialize Redis state
initialize_redis() {
    log_info "Initializing Redis coordination state..."

    # Clear previous execution state
    redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "phase:larry-*" | \
        xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true
    redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "task:*" | \
        xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true
    redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "worker:*" | \
        xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true
    redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "metrics:larry-*" | \
        xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true

    # Initialize Larry-01 state
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-01:status "pending"
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-01:progress 0

    # Initialize Larry-02 state
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-02:status "pending"
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-02:progress 0
    redis-cli -h $REDIS_HOST -p $REDIS_PORT HSET phase:larry-02:findings critical 0 high 0 medium 0 low 0

    # Initialize Larry-03 state
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-03:status "pending"
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-03:progress 0
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-03:inventory:assets_discovered 0
    redis-cli -h $REDIS_HOST -p $REDIS_PORT SET phase:larry-03:development:prs_created 0

    log_success "Redis initialized"
}

# Deploy Larry instances
deploy_larrys() {
    log_info "Deploying 3 Larry instances..."

    # Deploy Larry-01 (Infrastructure)
    log_larry "LARRY-01" "Deploying infrastructure phase..." "$PURPLE"
    kubectl apply -f k8s/deployments/larry-01-phase.yaml

    # Deploy Larry-02 (Security)
    log_larry "LARRY-02" "Deploying security phase..." "$RED"
    kubectl apply -f k8s/deployments/larry-02-phase.yaml

    # Deploy Larry-03 (Development)
    log_larry "LARRY-03" "Deploying development phase..." "$GREEN"
    kubectl apply -f k8s/deployments/larry-03-phase.yaml

    log_success "All Larrys deployed"

    # Wait for coordinators to be ready
    log_info "Waiting for coordinator pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=larry-coordinator -n larry-01 --timeout=120s
    kubectl wait --for=condition=ready pod -l app=larry-coordinator -n larry-02 --timeout=120s
    kubectl wait --for=condition=ready pod -l app=larry-coordinator -n larry-03 --timeout=120s

    log_success "All coordinators ready"
}

# Monitor Larry progress
monitor_progress() {
    log_info "Monitoring Larry progress..."
    echo ""

    local start_time=$(date +%s)

    while true; do
        local current_time=$(date +%s)
        local elapsed=$(( current_time - start_time ))

        if [ $elapsed -gt $TIMEOUT ]; then
            log_error "Timeout after ${TIMEOUT}s"
            return 1
        fi

        # Get status from Redis
        local status_01=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-01:status)
        local status_02=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-02:status)
        local status_03=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-03:status)

        local progress_01=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-01:progress || echo 0)
        local progress_02=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-02:progress || echo 0)
        local progress_03=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-03:progress || echo 0)

        # Clear screen and show progress
        clear
        echo -e "${CYAN}=== 3-Larry Distributed Orchestration ===${NC}"
        echo -e "Elapsed: ${elapsed}s / ${TIMEOUT}s"
        echo ""

        # Larry-01 progress
        printf "${PURPLE}[LARRY-01 Infrastructure]${NC} Status: %-12s Progress: %3d%% " "$status_01" "$progress_01"
        print_progress_bar $progress_01
        echo ""

        # Larry-02 progress
        printf "${RED}[LARRY-02 Security]${NC}       Status: %-12s Progress: %3d%% " "$status_02" "$progress_02"
        print_progress_bar $progress_02
        echo ""

        # Larry-03 progress
        printf "${GREEN}[LARRY-03 Development]${NC}   Status: %-12s Progress: %3d%% " "$status_03" "$progress_03"
        print_progress_bar $progress_03
        echo ""

        # Show worker counts
        echo ""
        echo -e "${CYAN}Worker Status:${NC}"
        local workers_01=$(kubectl get pods -n larry-01 -l app=larry-worker --no-headers 2>/dev/null | wc -l || echo 0)
        local workers_02=$(kubectl get pods -n larry-02 -l app=larry-worker --no-headers 2>/dev/null | wc -l || echo 0)
        local workers_03=$(kubectl get pods -n larry-03 -l app=larry-worker --no-headers 2>/dev/null | wc -l || echo 0)

        local completed_01=$(kubectl get jobs -n larry-01 -l larry-instance=larry-01 --field-selector status.successful=1 -o json 2>/dev/null | jq '.items | length' || echo 0)
        local completed_02=$(kubectl get jobs -n larry-02 -l larry-instance=larry-02 --field-selector status.successful=1 -o json 2>/dev/null | jq '.items | length' || echo 0)
        local completed_03=$(kubectl get jobs -n larry-03 -l larry-instance=larry-03 --field-selector status.successful=1 -o json 2>/dev/null | jq '.items | length' || echo 0)

        printf "  Larry-01: %d/4 workers completed\n" "$completed_01"
        printf "  Larry-02: %d/4 workers completed\n" "$completed_02"
        printf "  Larry-03: %d/8 workers completed\n" "$completed_03"

        # Show Larry-02 findings
        if [ "$progress_02" -gt 0 ]; then
            echo ""
            echo -e "${CYAN}Security Findings (Larry-02):${NC}"
            local critical=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT HGET phase:larry-02:findings critical || echo 0)
            local high=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT HGET phase:larry-02:findings high || echo 0)
            local medium=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT HGET phase:larry-02:findings medium || echo 0)
            printf "  Critical: %d | High: %d | Medium: %d\n" "$critical" "$high" "$medium"
        fi

        # Show Larry-03 metrics
        if [ "$progress_03" -gt 0 ]; then
            echo ""
            echo -e "${CYAN}Development Metrics (Larry-03):${NC}"
            local assets=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-03:inventory:assets_discovered || echo 0)
            local prs=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-03:development:prs_created || echo 0)
            printf "  Assets Cataloged: %d | PRs Created: %d\n" "$assets" "$prs"
        fi

        # Check if all completed
        if [ "$status_01" = "completed" ] && [ "$status_02" = "completed" ] && [ "$status_03" = "completed" ]; then
            echo ""
            log_success "All Larrys completed!"
            return 0
        fi

        # Check for failures
        if [ "$status_01" = "failed" ] || [ "$status_02" = "failed" ] || [ "$status_03" = "failed" ]; then
            echo ""
            log_error "One or more Larrys failed"
            return 1
        fi

        sleep 5
    done
}

# Print progress bar
print_progress_bar() {
    local progress=$1
    local bar_length=30
    local filled=$(( progress * bar_length / 100 ))
    local empty=$(( bar_length - filled ))

    printf "["
    for ((i=0; i<filled; i++)); do printf "="; done
    for ((i=0; i<empty; i++)); do printf " "; done
    printf "]"
}

# Phase 4: Convergence
run_phase_4() {
    log_info "Starting Phase 4: Convergence & Validation"

    # Wait for all Larry reports
    log_info "Waiting for Larry reports..."
    while true; do
        if [ -f "$COORDINATION_PATH/reports/larry-01-final.json" ] && \
           [ -f "$COORDINATION_PATH/reports/larry-02-final.json" ] && \
           [ -f "$COORDINATION_PATH/reports/larry-03-final.json" ]; then
            break
        fi
        sleep 2
    done

    log_success "All reports generated"

    # Aggregate reports
    log_info "Aggregating final report..."
    python3 scripts/aggregate-larry-reports.py \
        --larry-01-report "$COORDINATION_PATH/reports/larry-01-final.json" \
        --larry-02-report "$COORDINATION_PATH/reports/larry-02-final.json" \
        --larry-03-report "$COORDINATION_PATH/reports/larry-03-final.json" \
        --output "$COORDINATION_PATH/reports/3-LARRY-EXECUTION-SUMMARY.md"

    log_success "Final report generated: $COORDINATION_PATH/reports/3-LARRY-EXECUTION-SUMMARY.md"
}

# Generate summary
generate_summary() {
    log_info "Generating execution summary..."

    local end_time=$(date +%s)
    local total_duration=$(( end_time - START_TIME ))
    local minutes=$(( total_duration / 60 ))
    local seconds=$(( total_duration % 60 ))

    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}  3-Larry Orchestration Complete!${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo ""
    echo "Total Duration: ${minutes}m ${seconds}s"
    echo ""

    # Larry-01 summary
    echo -e "${PURPLE}Larry-01 (Infrastructure):${NC}"
    kubectl get jobs -n larry-01 -l larry-instance=larry-01
    echo ""

    # Larry-02 summary
    echo -e "${RED}Larry-02 (Security):${NC}"
    kubectl get jobs -n larry-02 -l larry-instance=larry-02
    local critical=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT HGET phase:larry-02:findings critical || echo 0)
    local high=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT HGET phase:larry-02:findings high || echo 0)
    echo "  CVEs Found: Critical=$critical, High=$high"
    echo ""

    # Larry-03 summary
    echo -e "${GREEN}Larry-03 (Development):${NC}"
    kubectl get jobs -n larry-03 -l larry-instance=larry-03
    local assets=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-03:inventory:assets_discovered || echo 0)
    local prs=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT GET phase:larry-03:development:prs_created || echo 0)
    echo "  Assets Cataloged: $assets"
    echo "  PRs Created: $prs"
    echo ""

    echo -e "${CYAN}Final Report:${NC} $COORDINATION_PATH/reports/3-LARRY-EXECUTION-SUMMARY.md"
    echo ""
}

# Cleanup
cleanup() {
    log_info "Cleaning up..."

    # Option to keep or delete Larry deployments
    read -p "Delete Larry deployments? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace larry-01 --ignore-not-found
        kubectl delete namespace larry-02 --ignore-not-found
        kubectl delete namespace larry-03 --ignore-not-found
        log_success "Deployments deleted"
    else
        log_info "Deployments preserved for inspection"
    fi

    # Clean up Redis
    read -p "Clean up Redis state? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "phase:larry-*" | \
            xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true
        redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "task:*" | \
            xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true
        redis-cli -h $REDIS_HOST -p $REDIS_PORT --scan --pattern "worker:*" | \
            xargs -r redis-cli -h $REDIS_HOST -p $REDIS_PORT del || true
        log_success "Redis state cleaned"
    else
        log_info "Redis state preserved for debugging"
    fi
}

# Main execution
main() {
    START_TIME=$(date +%s)

    echo -e "${CYAN}"
    echo "========================================"
    echo "  3-Larry Distributed Orchestration"
    echo "========================================"
    echo -e "${NC}"
    echo ""

    # Pre-flight checks
    check_prerequisites

    # Initialize
    initialize_redis

    # Deploy all Larrys
    deploy_larrys

    # Monitor execution
    if monitor_progress; then
        # Run Phase 4
        run_phase_4

        # Generate summary
        generate_summary

        # Cleanup
        cleanup

        log_success "3-Larry orchestration completed successfully!"
        exit 0
    else
        log_error "3-Larry orchestration failed"
        exit 1
    fi
}

# Trap errors
trap 'log_error "Script failed at line $LINENO"' ERR

# Run main
main "$@"
