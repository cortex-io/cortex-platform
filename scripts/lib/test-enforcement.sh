#!/bin/bash

# Test Enforcement - Validation gates for task completion

CORTEX_ROOT="${CORTEX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

source "$CORTEX_ROOT/lib/feature-list-validator.sh" 2>/dev/null || true

# Validate worker completion before allowing task to be marked complete
validate_worker_completion() {
  local worker_id=$1
  local task_id=$2
  local feature_id=${3:-}

  echo "Validating completion for worker: $worker_id, task: $task_id, feature: $feature_id"

  local violations=()

  # Check 1: Feature list exists for this task
  local feature_list="$CORTEX_ROOT/coordination/feature-lists/${task_id}-features.json"

  if [ ! -f "$feature_list" ]; then
    echo "WARNING: No feature list found for task $task_id - skipping feature validation"
    # Legacy tasks without feature lists - apply basic validation only
    validate_basic_completion "$worker_id" "$task_id"
    return $?
  fi

  # Check 2: If feature_id provided, validate that specific feature
  if [ -n "$feature_id" ]; then
    validate_feature_completion "$worker_id" "$task_id" "$feature_id" "$feature_list"
    return $?
  fi

  # Check 3: If no feature_id, validate entire task is complete
  validate_task_completion "$worker_id" "$task_id" "$feature_list"
  return $?
}

# Validate a specific feature is complete
validate_feature_completion() {
  local worker_id=$1
  local task_id=$2
  local feature_id=$3
  local feature_list=$4

  local violations=()

  # Get feature details
  local feature=$(jq --arg fid "$feature_id" \
    '.features[] | select(.feature_id == $fid)' \
    "$feature_list")

  if [ -z "$feature" ]; then
    echo "ERROR: Feature $feature_id not found in feature list"
    return 1
  fi

  local test_command=$(echo "$feature" | jq -r '.test_command')
  local status=$(echo "$feature" | jq -r '.status')

  # Validation 1: Test command must be defined
  if [ "$test_command" = "null" ] || [ -z "$test_command" ]; then
    violations+=("Feature $feature_id has no test command defined")
  else
    # Validation 2: Test must have been run and passed
    local test_results=$(echo "$feature" | jq -r '.test_results')

    if [ "$test_results" = "null" ]; then
      echo "No test results found - running tests now..."

      if run_feature_test "$test_command" "$feature_id"; then
        echo "Tests passed"
      else
        violations+=("Tests failed for feature $feature_id")
      fi
    else
      local exit_code=$(echo "$test_results" | jq -r '.exit_code')

      if [ "$exit_code" != "0" ]; then
        violations+=("Tests failed for feature $feature_id (exit code: $exit_code)")
      fi
    fi
  fi

  # Validation 3: Progress file must exist
  if ! validate_progress_file "$worker_id"; then
    violations+=("No progress file found for worker $worker_id")
  fi

  # Validation 4: Git commits must exist
  if ! validate_git_commits; then
    violations+=("No recent git commits found")
  fi

  # Check for violations
  if [ ${#violations[@]} -gt 0 ]; then
    echo "VALIDATION FAILED - Violations found:"
    printf '%s\n' "${violations[@]}"
    return 1
  fi

  echo "Validation passed for feature $feature_id"
  return 0
}

# Validate entire task is complete
validate_task_completion() {
  local worker_id=$1
  local task_id=$2
  local feature_list=$3

  # Check if all features are passing
  local total_features=$(jq '.total_features' "$feature_list")
  local passing_features=$(jq '[.features[] | select(.status == "passing")] | length' "$feature_list")

  if [ "$passing_features" -ne "$total_features" ]; then
    echo "ERROR: Task not complete - $passing_features/$total_features features passing"
    return 1
  fi

  echo "Task $task_id validation passed - all features complete"
  return 0
}

# Basic validation for tasks without feature lists (legacy)
validate_basic_completion() {
  local worker_id=$1
  local task_id=$2

  local violations=()

  # Check progress file
  if ! validate_progress_file "$worker_id"; then
    violations+=("No progress file found")
  fi

  # Check git commits
  if ! validate_git_commits; then
    violations+=("No recent git commits found")
  fi

  if [ ${#violations[@]} -gt 0 ]; then
    echo "VALIDATION FAILED:"
    printf '%s\n' "${violations[@]}"
    return 1
  fi

  echo "Basic validation passed"
  return 0
}

# Run a feature test
run_feature_test() {
  local test_command=$1
  local feature_id=$2

  echo "Running test: $test_command"

  local start_time=$(date +%s%3N)
  local output_file=$(mktemp)

  # Run the test
  if eval "$test_command" > "$output_file" 2>&1; then
    local exit_code=0
  else
    local exit_code=$?
  fi

  local end_time=$(date +%s%3N)
  local duration=$((end_time - start_time))

  local stdout=$(cat "$output_file")
  rm -f "$output_file"

  # Store test results
  if [ -n "$FEATURE_LIST" ] && [ -f "$FEATURE_LIST" ]; then
    local test_results=$(jq -n \
      --arg exit_code "$exit_code" \
      --arg stdout "$stdout" \
      --arg duration "$duration" \
      '{
        exit_code: ($exit_code | tonumber),
        stdout: $stdout,
        duration_ms: ($duration | tonumber),
        timestamp: (now | todate)
      }')

    source "$CORTEX_ROOT/lib/feature-list-validator.sh"
    update_feature_status "$FEATURE_LIST" "$feature_id" "passing" "$test_results"
  fi

  return $exit_code
}

# Validate progress file exists
validate_progress_file() {
  local worker_id=$1

  local progress_dir="$CORTEX_ROOT/coordination/workers/${worker_id}/progress"

  if [ ! -d "$progress_dir" ]; then
    echo "Progress directory not found: $progress_dir"
    return 1
  fi

  if [ ! -f "${progress_dir}/current-session.json" ]; then
    echo "No current session found"
    return 1
  fi

  return 0
}

# Validate git commits exist
validate_git_commits() {
  # Check for commits in last hour
  local commits=$(git log --oneline --since="1 hour ago" --author="cortex" 2>/dev/null)

  if [ -z "$commits" ]; then
    # Try without author filter
    commits=$(git log --oneline --since="1 hour ago" 2>/dev/null)
  fi

  if [ -z "$commits" ]; then
    echo "No recent git commits found"
    return 1
  fi

  return 0
}

# Enforce test requirement before marking feature complete
enforce_test_requirement() {
  local task_id=$1
  local feature_id=$2

  local feature_list="$CORTEX_ROOT/coordination/feature-lists/${task_id}-features.json"

  if [ ! -f "$feature_list" ]; then
    echo "WARNING: No feature list found - cannot enforce test requirement"
    return 0
  fi

  local feature=$(jq --arg fid "$feature_id" \
    '.features[] | select(.feature_id == $fid)' \
    "$feature_list")

  local test_command=$(echo "$feature" | jq -r '.test_command')

  if [ "$test_command" = "null" ] || [ -z "$test_command" ]; then
    echo "ERROR: Feature $feature_id has no test command - cannot mark as complete"
    return 1
  fi

  echo "Test requirement enforced for feature $feature_id"
  return 0
}

# Export functions if sourced
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
  export -f validate_worker_completion
  export -f validate_feature_completion
  export -f validate_task_completion
  export -f validate_basic_completion
  export -f run_feature_test
  export -f validate_progress_file
  export -f validate_git_commits
  export -f enforce_test_requirement
fi
