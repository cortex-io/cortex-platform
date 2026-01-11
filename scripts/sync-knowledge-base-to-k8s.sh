#!/usr/bin/env bash
# Knowledge Base Sync: Desktop → K8s
# Syncs contractor patterns and knowledge to k8s ConfigMaps

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KB_DIR="$CORTEX_ROOT/coordination/knowledge-base"
K8S_NAMESPACE="${K8S_NAMESPACE:-cortex}"

echo "🧠 Cortex Knowledge Base Sync"
echo "=============================="
echo ""

# Check if knowledge base directory exists
if [[ ! -d "$KB_DIR" ]]; then
  echo "❌ Knowledge base directory not found: $KB_DIR"
  exit 1
fi

# Function to create ConfigMap from patterns
create_pattern_configmap() {
  local category="$1"
  local configmap_name="kb-patterns-${category}"

  echo "📦 Creating ConfigMap: $configmap_name"

  # Find all pattern files for this category
  local pattern_files=$(find "$KB_DIR/patterns" -name "*.json" -exec grep -l "\"category\": \"$category\"" {} \;)

  if [[ -z "$pattern_files" ]]; then
    echo "  ⚠️  No patterns found for category: $category"
    return
  fi

  # Build kubectl command
  local kubectl_cmd="kubectl create configmap $configmap_name --namespace=$K8S_NAMESPACE --dry-run=client -o yaml"

  # Add each pattern file
  while IFS= read -r file; do
    local filename=$(basename "$file")
    kubectl_cmd="$kubectl_cmd --from-file=$filename=$file"
  done <<< "$pattern_files"

  # Apply the ConfigMap
  eval "$kubectl_cmd" | kubectl apply -f -

  echo "  ✅ Synced $(echo "$pattern_files" | wc -l | tr -d ' ') patterns"
}

# Function to create ConfigMap from schemas
create_schema_configmap() {
  echo "📐 Creating ConfigMap: kb-schemas"

  if [[ ! -d "$KB_DIR/schemas" ]]; then
    echo "  ⚠️  No schemas directory found"
    return
  fi

  kubectl create configmap kb-schemas \
    --namespace=$K8S_NAMESPACE \
    --from-file="$KB_DIR/schemas/" \
    --dry-run=client -o yaml | kubectl apply -f -

  echo "  ✅ Synced schemas"
}

# Main sync process
echo "🔄 Syncing knowledge base to k8s..."
echo ""

# Create namespace if it doesn't exist
kubectl create namespace $K8S_NAMESPACE --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null || true

# Sync schemas
create_schema_configmap

# Sync patterns by category
CATEGORIES=("performance" "reliability" "cost-optimization" "security" "troubleshooting" "workflow-composition" "resource-allocation")

for category in "${CATEGORIES[@]}"; do
  create_pattern_configmap "$category"
done

# Label all knowledge base ConfigMaps
echo ""
echo "🏷️  Labeling ConfigMaps..."
kubectl label configmap -n $K8S_NAMESPACE -l '!cortex.ai/knowledge-base' \
  cortex.ai/knowledge-base=true \
  cortex.ai/sync-source=desktop \
  cortex.ai/sync-timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --overwrite 2>/dev/null || true

echo ""
echo "✅ Knowledge base sync complete!"
echo ""
echo "📊 Summary:"
kubectl get configmaps -n $K8S_NAMESPACE -l cortex.ai/knowledge-base=true -o custom-columns=NAME:.metadata.name,AGE:.metadata.creationTimestamp

echo ""
echo "💡 MCP servers can now mount these ConfigMaps for contractor intelligence!"
echo ""
echo "Example usage in deployment:"
echo "---"
echo "volumes:"
echo "- name: kb-patterns"
echo "  configMap:"
echo "    name: kb-patterns-performance"
echo "volumeMounts:"
echo "- name: kb-patterns"
echo "  mountPath: /app/knowledge-base/patterns/performance"
echo "  readOnly: true"
