#!/bin/bash
# Build and deploy Cortex Desktop MCP Server
set -e

echo "=== Cortex Desktop MCP Server Build and Deploy ==="

NAMESPACE="cortex"
IMAGE_NAME="cortex-desktop-mcp"
REGISTRY="10.43.170.72:5000"
TAG="latest"

# Clean up previous build resources
echo "Cleaning up previous build resources..."
kubectl delete job cortex-desktop-mcp-build -n $NAMESPACE --ignore-not-found=true
kubectl delete pod cortex-desktop-mcp-copy -n $NAMESPACE --ignore-not-found=true
kubectl delete pvc cortex-desktop-mcp-context -n $NAMESPACE --ignore-not-found=true

# Create namespace if needed
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Create ConfigMap with source files
echo "Creating ConfigMap with source files..."
kubectl create configmap cortex-desktop-mcp-source \
  --from-file=server.js=server.js \
  --from-file=package.json=package.json \
  --from-file=Dockerfile=Dockerfile \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# Create build PVC
echo "Creating build context PVC..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: cortex-desktop-mcp-context
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
EOF

# Copy source files to PVC
echo "Copying source files to PVC..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cortex-desktop-mcp-copy
  namespace: $NAMESPACE
spec:
  restartPolicy: Never
  volumes:
  - name: build-context
    persistentVolumeClaim:
      claimName: cortex-desktop-mcp-context
  - name: source
    configMap:
      name: cortex-desktop-mcp-source
  containers:
  - name: copy
    image: busybox
    command: ["/bin/sh", "-c"]
    args:
      - |
        echo "Copying files to build context..."
        cp /source/Dockerfile /workspace/
        cp /source/server.js /workspace/
        cp /source/package.json /workspace/
        echo "Files copied:"
        ls -la /workspace/
    volumeMounts:
    - name: build-context
      mountPath: /workspace
    - name: source
      mountPath: /source
EOF

# Wait for copy to complete
echo "Waiting for copy to complete..."
kubectl wait --for=condition=Ready pod/cortex-desktop-mcp-copy -n $NAMESPACE --timeout=60s || true
sleep 5
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/cortex-desktop-mcp-copy -n $NAMESPACE --timeout=60s

echo "Copy completed. Starting Kaniko build..."

# Run Kaniko build
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: cortex-desktop-mcp-build
  namespace: $NAMESPACE
spec:
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      volumes:
      - name: build-context
        persistentVolumeClaim:
          claimName: cortex-desktop-mcp-context
      - name: docker-config
        emptyDir: {}
      initContainers:
      - name: create-docker-config
        image: busybox
        command: ["/bin/sh", "-c"]
        args:
          - |
            mkdir -p /kaniko/.docker
            echo '{"insecureRegistries":["$REGISTRY"]}' > /kaniko/.docker/config.json
        volumeMounts:
        - name: docker-config
          mountPath: /kaniko/.docker
      containers:
      - name: kaniko
        image: gcr.io/kaniko-project/executor:latest
        args:
          - "--dockerfile=/workspace/Dockerfile"
          - "--context=/workspace"
          - "--destination=$REGISTRY/$IMAGE_NAME:$TAG"
          - "--insecure"
          - "--skip-tls-verify"
          - "--verbosity=info"
        volumeMounts:
        - name: build-context
          mountPath: /workspace
        - name: docker-config
          mountPath: /kaniko/.docker
EOF

echo ""
echo "Build job created. Monitoring progress..."
echo "Run: kubectl logs -f job/cortex-desktop-mcp-build -n $NAMESPACE"
echo ""
echo "After build completes, deploy with:"
echo "  kubectl apply -f deployment.yaml"
echo ""
