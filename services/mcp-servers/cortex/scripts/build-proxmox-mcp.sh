#!/bin/bash
# Build Proxmox MCP Server using Kaniko in-cluster builder
# This script creates a Kaniko build job that clones the repo and builds the image

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="cortex-system"
BUILD_JOB_NAME="kaniko-proxmox-mcp-build-$(date +%s)"
REGISTRY="docker-registry.cortex-system.svc.cluster.local:5000"
IMAGE_NAME="cortex-mcp-server"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo -e "${GREEN}=== Proxmox MCP Server Build Pipeline ===${NC}"
echo "Namespace: $NAMESPACE"
echo "Build Job: $BUILD_JOB_NAME"
echo "Registry: $REGISTRY"
echo "Image Tags: latest, $TIMESTAMP"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found${NC}"
    exit 1
fi

# Check namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo -e "${RED}Error: Namespace $NAMESPACE not found${NC}"
    exit 1
fi

# Check if Kaniko service account exists
if ! kubectl get serviceaccount kaniko-builder -n "$NAMESPACE" &> /dev/null; then
    echo -e "${YELLOW}Creating Kaniko service account...${NC}"
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: kaniko-builder
  namespace: $NAMESPACE
  labels:
    app: cortex-mcp-server
    component: builder
EOF
fi

# Check if docker config exists
if ! kubectl get configmap docker-config -n "$NAMESPACE" &> /dev/null; then
    echo -e "${YELLOW}Creating Docker config...${NC}"
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: docker-config
  namespace: $NAMESPACE
  labels:
    app: cortex-mcp-server
    component: builder
data:
  config.json: |
    {
      "auths": {
        "$REGISTRY": {
          "auth": ""
        }
      },
      "insecure-registries": [
        "$REGISTRY"
      ]
    }
EOF
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# Create Kaniko build job
echo -e "${YELLOW}Creating Kaniko build job...${NC}"

cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: $BUILD_JOB_NAME
  namespace: $NAMESPACE
  labels:
    app: cortex-mcp-server
    component: builder
    build-type: kaniko
    build-timestamp: "$TIMESTAMP"
spec:
  ttlSecondsAfterFinished: 3600
  backoffLimit: 2
  template:
    metadata:
      labels:
        app: cortex-mcp-server
        component: builder
    spec:
      restartPolicy: Never
      serviceAccountName: kaniko-builder

      initContainers:
      # Clone the cortex repository
      - name: git-clone
        image: alpine/git:latest
        command:
        - /bin/sh
        - -c
        - |
          set -e
          echo "Cloning cortex repository..."
          git clone https://github.com/ryandahlberg/cortex.git /workspace/cortex
          cd /workspace/cortex
          echo "Repository cloned successfully"
          echo "Contents:"
          ls -la /workspace/cortex/mcp-servers/cortex/
        volumeMounts:
        - name: workspace
          mountPath: /workspace

      containers:
      - name: kaniko
        image: gcr.io/kaniko-project/executor:latest
        args:
        - "--dockerfile=/workspace/cortex/mcp-servers/cortex/Dockerfile"
        - "--context=/workspace/cortex/mcp-servers/cortex"
        - "--destination=$REGISTRY/$IMAGE_NAME:latest"
        - "--destination=$REGISTRY/$IMAGE_NAME:$TIMESTAMP"
        - "--insecure"
        - "--skip-tls-verify"
        - "--cache=true"
        - "--cache-repo=$REGISTRY/cache"
        - "--compressed-caching=false"
        - "--snapshot-mode=redo"
        - "--log-format=text"
        - "--verbosity=info"

        volumeMounts:
        - name: workspace
          mountPath: /workspace
        - name: docker-config
          mountPath: /kaniko/.docker

        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"

      volumes:
      - name: workspace
        emptyDir: {}
      - name: docker-config
        configMap:
          name: docker-config
EOF

echo -e "${GREEN}Build job created: $BUILD_JOB_NAME${NC}"
echo ""

# Wait for job to start
echo -e "${YELLOW}Waiting for build job to start...${NC}"
sleep 3

# Follow build logs
echo -e "${YELLOW}Following build logs (Ctrl+C to stop watching, build continues)...${NC}"
echo ""

# Try to get pod name
POD_NAME=""
for i in {1..30}; do
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "job-name=$BUILD_JOB_NAME" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$POD_NAME" ]; then
        break
    fi
    sleep 2
done

if [ -z "$POD_NAME" ]; then
    echo -e "${RED}Error: Could not find build pod${NC}"
    echo "Check job status with: kubectl get job $BUILD_JOB_NAME -n $NAMESPACE"
    exit 1
fi

# Follow logs from init container first
echo -e "${YELLOW}=== Git Clone Logs ===${NC}"
kubectl logs -n "$NAMESPACE" "$POD_NAME" -c git-clone -f 2>/dev/null || true

# Then follow main container logs
echo ""
echo -e "${YELLOW}=== Kaniko Build Logs ===${NC}"
kubectl logs -n "$NAMESPACE" "$POD_NAME" -c kaniko -f 2>/dev/null || true

# Wait for job completion
echo ""
echo -e "${YELLOW}Waiting for build completion...${NC}"

if kubectl wait --for=condition=complete --timeout=600s "job/$BUILD_JOB_NAME" -n "$NAMESPACE"; then
    echo -e "${GREEN}Build completed successfully!${NC}"
    echo ""
    echo "Image tags created:"
    echo "  - $REGISTRY/$IMAGE_NAME:latest"
    echo "  - $REGISTRY/$IMAGE_NAME:$TIMESTAMP"
    echo ""
    echo "Next steps:"
    echo "  1. Verify image: kubectl run test-image --rm -it --image=$REGISTRY/$IMAGE_NAME:latest -- /bin/sh"
    echo "  2. Deploy: ./scripts/deploy-proxmox-mcp.sh"
    echo "  3. Verify: ./scripts/verify-proxmox-mcp.sh"
    exit 0
else
    echo -e "${RED}Build failed or timed out${NC}"
    echo ""
    echo "Check build logs with:"
    echo "  kubectl logs -n $NAMESPACE job/$BUILD_JOB_NAME"
    echo ""
    echo "Debug build with:"
    echo "  kubectl describe job $BUILD_JOB_NAME -n $NAMESPACE"
    exit 1
fi
