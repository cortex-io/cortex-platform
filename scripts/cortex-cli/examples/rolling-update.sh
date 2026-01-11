#!/usr/bin/env bash
#
# Example: Rolling update workflow
#
# Demonstrates a complete rolling update process:
# 1. Build new image
# 2. Push to registry
# 3. Deploy to staging
# 4. Test in staging
# 5. Deploy to production
#
# Usage:
#   ./rolling-update.sh <service> [version]
#
# Examples:
#   ./rolling-update.sh cortex-api
#   ./rolling-update.sh cortex-chat v1.2.0
#

set -euo pipefail

# Configuration
SERVICE="${1:-cortex-api}"
VERSION="${2:-$(git rev-parse --short HEAD)}"
REGISTRY="${REGISTRY:-cortex}"

echo "Rolling Update: ${SERVICE} -> ${VERSION}"
echo ""

# Step 1: Build
echo "Step 1: Building Docker image..."
if cortex-k8s build "${SERVICE}" "${VERSION}"; then
    echo "✓ Build successful"
else
    echo "✗ Build failed"
    exit 1
fi

echo ""

# Step 2: Push
echo "Step 2: Pushing to registry..."
if cortex-k8s build "${SERVICE}" "${VERSION}" --push; then
    echo "✓ Push successful"
else
    echo "✗ Push failed"
    exit 1
fi

echo ""

# Step 3: Deploy to staging
echo "Step 3: Deploying to staging..."
if cortex-k8s deploy "${SERVICE}" --namespace=staging; then
    echo "✓ Staging deployment successful"
else
    echo "✗ Staging deployment failed"
    exit 1
fi

echo ""

# Step 4: Test in staging
echo "Step 4: Testing in staging..."
if cortex-k8s test "${SERVICE}" --namespace=staging; then
    echo "✓ Staging tests passed"
else
    echo "✗ Staging tests failed"
    exit 1
fi

echo ""

# Step 5: Prompt for production
echo "Staging deployment successful!"
echo ""
read -p "Deploy to production? [y/N] " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Step 5: Deploying to production..."

    if cortex-k8s deploy "${SERVICE}" --namespace=production; then
        echo "✓ Production deployment successful"
    else
        echo "✗ Production deployment failed"
        exit 1
    fi

    echo ""
    echo "Monitoring production deployment..."
    cortex-k8s logs "${SERVICE}" --namespace=production -f --tail=50
else
    echo ""
    echo "Production deployment skipped"
fi

echo ""
echo "Rolling update complete!"
