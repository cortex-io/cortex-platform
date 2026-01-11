#!/bin/bash
# Build and deploy Cortex MCP Server

set -e

echo "Building Cortex MCP Server..."
cd "$(dirname "$0")/.."

# Build locally with Docker (if available) or use Kaniko in k3s
if command -v docker &> /dev/null; then
  echo "Building with Docker..."
  docker build -t cortex-mcp-server:latest .

  # Tag for registry
  docker tag cortex-mcp-server:latest docker-registry.cortex-system.svc.cluster.local:5000/cortex-mcp-server:latest

  # Push to k3s registry
  echo "Pushing to k3s registry..."
  docker push docker-registry.cortex-system.svc.cluster.local:5000/cortex-mcp-server:latest || echo "Warning: Could not push to k3s registry (may need port forward)"

  echo "✓ Build complete!"
else
  echo "Docker not found. Use Kaniko build job in k3s:"
  echo "  kubectl apply -f k8s/build-job.yaml"
fi
