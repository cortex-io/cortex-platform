#!/bin/bash

################################################################################
# Phase 1 Verification Script
#
# Validates that all Phase 1 deliverables are present and correctly configured.
################################################################################

set -euo pipefail

MASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="/Users/ryandahlberg/Projects/cortex/k3s-deployments/cortex-governance"

PASS=0
FAIL=0

################################################################################
# Helper Functions
################################################################################

check_file() {
    local file="$1"
    local description="$2"

    if [[ -f "${file}" ]]; then
        echo "✅ ${description}"
        ((PASS++))
    else
        echo "❌ ${description} - MISSING: ${file}"
        ((FAIL++))
    fi
}

check_dir() {
    local dir="$1"
    local description="$2"

    if [[ -d "${dir}" ]]; then
        echo "✅ ${description}"
        ((PASS++))
    else
        echo "❌ ${description} - MISSING: ${dir}"
        ((FAIL++))
    fi
}

check_executable() {
    local file="$1"
    local description="$2"

    if [[ -x "${file}" ]]; then
        echo "✅ ${description}"
        ((PASS++))
    else
        echo "❌ ${description} - NOT EXECUTABLE: ${file}"
        ((FAIL++))
    fi
}

check_json() {
    local file="$1"
    local description="$2"

    if jq empty "${file}" 2>/dev/null; then
        echo "✅ ${description}"
        ((PASS++))
    else
        echo "❌ ${description} - INVALID JSON: ${file}"
        ((FAIL++))
    fi
}

################################################################################
# Verification Tests
################################################################################

echo "========================================"
echo "Phase 1 Verification - Documentation Master"
echo "========================================"
echo ""

echo "=== Directory Structure ==="
check_dir "${MASTER_DIR}/lib" "lib/ directory"
check_dir "${MASTER_DIR}/config" "config/ directory"
check_dir "${MASTER_DIR}/knowledge-base" "knowledge-base/ directory"
check_dir "${MASTER_DIR}/cache" "cache/ directory"
check_dir "${MASTER_DIR}/workers" "workers/ directory"
check_dir "${MASTER_DIR}/knowledge-base/sandfly" "knowledge-base/sandfly/ directory"
check_dir "${MASTER_DIR}/knowledge-base/proxmox" "knowledge-base/proxmox/ directory"
check_dir "${MASTER_DIR}/knowledge-base/k3s" "knowledge-base/k3s/ directory"
check_dir "${MASTER_DIR}/cache/indexed-content" "cache/indexed-content/ directory"
check_dir "${MASTER_DIR}/cache/embeddings" "cache/embeddings/ directory"
check_dir "${MASTER_DIR}/cache/metadata" "cache/metadata/ directory"
echo ""

echo "=== Core Scripts ==="
check_file "${MASTER_DIR}/master.sh" "master.sh exists"
check_executable "${MASTER_DIR}/master.sh" "master.sh is executable"
check_file "${MASTER_DIR}/lib/crawler.sh" "crawler.sh exists"
check_executable "${MASTER_DIR}/lib/crawler.sh" "crawler.sh is executable"
check_file "${MASTER_DIR}/lib/indexer.sh" "indexer.sh exists"
check_executable "${MASTER_DIR}/lib/indexer.sh" "indexer.sh is executable"
check_file "${MASTER_DIR}/lib/query-handler.sh" "query-handler.sh exists"
check_executable "${MASTER_DIR}/lib/query-handler.sh" "query-handler.sh is executable"
check_file "${MASTER_DIR}/lib/learner.sh" "learner.sh exists"
check_executable "${MASTER_DIR}/lib/learner.sh" "learner.sh is executable"
echo ""

echo "=== Worker Scripts ==="
check_file "${MASTER_DIR}/workers/crawler-worker.sh" "crawler-worker.sh exists"
check_executable "${MASTER_DIR}/workers/crawler-worker.sh" "crawler-worker.sh is executable"
check_file "${MASTER_DIR}/workers/indexer-worker.sh" "indexer-worker.sh exists"
check_executable "${MASTER_DIR}/workers/indexer-worker.sh" "indexer-worker.sh is executable"
check_file "${MASTER_DIR}/workers/learner-worker.sh" "learner-worker.sh exists"
check_executable "${MASTER_DIR}/workers/learner-worker.sh" "learner-worker.sh is executable"
echo ""

echo "=== Configuration Files ==="
check_file "${MASTER_DIR}/config/sources.json" "sources.json exists"
check_json "${MASTER_DIR}/config/sources.json" "sources.json is valid JSON"
check_file "${MASTER_DIR}/config/resource-limits.json" "resource-limits.json exists"
check_json "${MASTER_DIR}/config/resource-limits.json" "resource-limits.json is valid JSON"
check_file "${MASTER_DIR}/config/crawl-policy.json" "crawl-policy.json exists"
check_json "${MASTER_DIR}/config/crawl-policy.json" "crawl-policy.json is valid JSON"
check_file "${MASTER_DIR}/config/learning-policy.json" "learning-policy.json exists"
check_json "${MASTER_DIR}/config/learning-policy.json" "learning-policy.json is valid JSON"
echo ""

echo "=== Kubernetes Manifests ==="
check_file "${K8S_DIR}/documentation-master-pvc.yaml" "PVC manifest exists"
check_file "${K8S_DIR}/documentation-master-configmap.yaml" "ConfigMap manifest exists"
check_file "${K8S_DIR}/documentation-master-deployment.yaml" "Deployment manifest exists"
check_file "${K8S_DIR}/documentation-master-service.yaml" "Service manifest exists"
check_file "${K8S_DIR}/documentation-master-cronjob.yaml" "CronJob manifest exists"
echo ""

echo "=== Documentation ==="
check_file "${MASTER_DIR}/README.md" "README.md exists"
check_file "${MASTER_DIR}/PHASE1-COMPLETE.md" "PHASE1-COMPLETE.md exists"
echo ""

echo "========================================"
echo "Verification Summary"
echo "========================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"
echo ""

if [[ ${FAIL} -eq 0 ]]; then
    echo "🎉 Phase 1 verification PASSED - All deliverables present and valid!"
    exit 0
else
    echo "⚠️  Phase 1 verification FAILED - ${FAIL} issues found"
    exit 1
fi
