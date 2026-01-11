#!/bin/bash

# Init Script Generator - Creates environment setup scripts for workers

generate_init_script() {
  local task_id=$1
  local feature_list_file=$2

  # Create a generic init script template
  local init_script_template="$CORTEX_ROOT/coordination/workers/init-${task_id}.sh"

  cat > "$init_script_template" <<'INIT_SCRIPT'
#!/bin/bash
# Auto-generated init script for task: {TASK_ID}
# Generated: {TIMESTAMP}

set -euo pipefail

# Verify working directory
CORTEX_ROOT="{CORTEX_ROOT}"
cd "$CORTEX_ROOT" || exit 1

echo "Initializing worker environment for task {TASK_ID}..."

# Load environment
if [ -f "./config/load-env.sh" ]; then
  source ./config/load-env.sh
fi

# Check for required dependencies
check_dependencies() {
  local missing=0

  # Check for jq
  if ! command -v jq &> /dev/null; then
    echo "ERROR: jq is not installed"
    missing=1
  fi

  # Check for git
  if ! command -v git &> /dev/null; then
    echo "ERROR: git is not installed"
    missing=1
  fi

  return $missing
}

if ! check_dependencies; then
  echo "Missing required dependencies"
  exit 1
fi

# Install Node.js dependencies if needed
if [ -f "package.json" ] && [ ! -d "node_modules" ]; then
  echo "Installing Node.js dependencies..."
  npm install --silent
fi

# Install Python dependencies if needed
if [ -f "requirements.txt" ]; then
  echo "Installing Python dependencies..."
  pip install -q -r requirements.txt 2>/dev/null || true
fi

# Load feature list
export FEATURE_LIST="{FEATURE_LIST}"

if [ ! -f "$FEATURE_LIST" ]; then
  echo "ERROR: Feature list not found: $FEATURE_LIST"
  exit 1
fi

# Load previous progress if exists
WORKER_ID="${WORKER_ID:-unknown}"
PROGRESS_DIR="$CORTEX_ROOT/coordination/workers/$WORKER_ID/progress"

if [ -d "$PROGRESS_DIR" ] && [ -f "$PROGRESS_DIR/current-session.txt" ]; then
  echo "Found previous session, loading context..."
  echo "---"
  tail -20 "$PROGRESS_DIR/current-session.txt"
  echo "---"
fi

# Verify git is initialized
if [ ! -d ".git" ]; then
  echo "WARNING: Not a git repository. Initializing..."
  git init
  git add .
  git commit -m "Initial commit by Cortex Initializer" || true
fi

# Feature list summary
TOTAL_FEATURES=$(jq '.total_features' "$FEATURE_LIST")
COMPLETED_FEATURES=$(jq '[.features[] | select(.status == "passing")] | length' "$FEATURE_LIST")
FAILING_FEATURES=$(jq '[.features[] | select(.status == "failing")] | length' "$FEATURE_LIST")

echo ""
echo "Environment ready!"
echo "Feature List: $FEATURE_LIST"
echo "Total Features: $TOTAL_FEATURES"
echo "Completed: $COMPLETED_FEATURES"
echo "Remaining: $FAILING_FEATURES"
echo ""

# List next available features
echo "Next available features:"
jq -r '.features[] | select(.status == "failing" and (.dependencies | length == 0 or all(. as $dep | any(.features[] | select(.feature_id == $dep and .status == "passing"))))) | "  - \(.feature_id): \(.description)"' "$FEATURE_LIST" | head -5

echo ""
echo "Initialization complete."
INIT_SCRIPT

  # Replace template variables
  sed -i '' "s|{TASK_ID}|$task_id|g" "$init_script_template"
  sed -i '' "s|{TIMESTAMP}|$(date -u +%Y-%m-%dT%H:%M:%SZ)|g" "$init_script_template"
  sed -i '' "s|{CORTEX_ROOT}|$CORTEX_ROOT|g" "$init_script_template"
  sed -i '' "s|{FEATURE_LIST}|$feature_list_file|g" "$init_script_template"

  chmod +x "$init_script_template"

  echo "Init script created: $init_script_template"
  return 0
}
