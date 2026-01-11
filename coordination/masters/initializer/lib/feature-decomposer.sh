#!/bin/bash

# Feature Decomposer - Breaks tasks into 50-200 atomic features using Claude

decompose_task() {
  local task_id=$1
  local description=$2
  local output_file=$3

  local prompt_file="$SCRIPT_DIR/prompts/decomposition-prompt.txt"

  if [ ! -f "$prompt_file" ]; then
    echo "ERROR: Prompt file not found: $prompt_file"
    return 1
  fi

  # Estimate task size to determine feature count target
  local target_features=$(estimate_feature_count "$description")

  # Load prompt template and substitute variables
  local prompt=$(cat "$prompt_file")
  prompt="${prompt//\{DESCRIPTION\}/$description}"
  prompt="${prompt//\{TARGET_COUNT\}/$target_features}"

  # Call Claude via LLM gateway
  local response=$(call_claude_for_decomposition "$prompt")

  if [ $? -ne 0 ]; then
    echo "ERROR: Claude API call failed"
    return 1
  fi

  # Parse response and create feature list
  create_feature_list "$task_id" "$response" "$output_file"

  return $?
}

estimate_feature_count() {
  local description=$1
  local word_count=$(echo "$description" | wc -w | tr -d ' ')

  # Simple heuristic: more words = more features
  if [ "$word_count" -lt 20 ]; then
    echo 50
  elif [ "$word_count" -lt 50 ]; then
    echo 100
  else
    echo 200
  fi
}

call_claude_for_decomposition() {
  local prompt=$1

  # Use the LLM gateway script if available
  if [ -f "$CORTEX_ROOT/gateway/llm-client.sh" ]; then
    source "$CORTEX_ROOT/gateway/llm-client.sh"

    # Call Claude with the decomposition prompt
    local response=$(call_llm "$prompt" "feature-decomposition")
    echo "$response"
    return $?
  else
    # Fallback: direct API call
    local api_key="${ANTHROPIC_API_KEY:-}"

    if [ -z "$api_key" ]; then
      echo "ERROR: ANTHROPIC_API_KEY not set"
      return 1
    fi

    local payload=$(jq -n \
      --arg prompt "$prompt" \
      '{
        model: "claude-sonnet-4-5-20250929",
        max_tokens: 8000,
        messages: [{role: "user", content: $prompt}]
      }')

    local response=$(curl -s -X POST https://api.anthropic.com/v1/messages \
      -H "Content-Type: application/json" \
      -H "x-api-key: $api_key" \
      -H "anthropic-version: 2023-06-01" \
      -d "$payload")

    # Extract content
    echo "$response" | jq -r '.content[0].text'
    return 0
  fi
}

create_feature_list() {
  local task_id=$1
  local response=$2
  local output_file=$3

  # Try to extract JSON from response (it might be wrapped in markdown)
  local json_content=$(echo "$response" | sed -n '/```json/,/```/p' | sed '1d;$d')

  if [ -z "$json_content" ]; then
    # Maybe it's raw JSON
    json_content="$response"
  fi

  # Validate JSON
  if ! echo "$json_content" | jq . > /dev/null 2>&1; then
    echo "ERROR: Invalid JSON in Claude response"
    return 1
  fi

  # Create feature list structure
  local created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  local feature_list=$(jq -n \
    --arg task_id "$task_id" \
    --arg created_at "$created_at" \
    --argjson features "$json_content" \
    '{
      task_id: $task_id,
      master: "initializer-master",
      total_features: ($features | length),
      completed: 0,
      created_at: $created_at,
      created_by: "initializer-master",
      features: $features
    }')

  # Add IDs and status to features if not present
  feature_list=$(echo "$feature_list" | jq '
    .features = [
      .features[] |
      .feature_id = (.feature_id // ("feature-" + ((.features | index(.) + 1) | tostring | split("") | if length == 1 then ["0", "0"] + . elif length == 2 then ["0"] + . else . end | join("")))) |
      .status = (.status // "failing") |
      .assigned_to = null |
      .completed_at = null |
      .test_results = null |
      .priority = (.priority // "medium")
    ]
  ')

  # Write to file
  echo "$feature_list" | jq . > "$output_file"

  return 0
}

generate_file_hints() {
  local task_id=$1
  local description=$2
  local feature_list_file=$3

  # Use grep to find relevant files based on task description
  local keywords=$(echo "$description" | tr '[:upper:]' '[:lower:]' | grep -oE '\b\w{4,}\b' | head -10)

  local file_hints=()

  for keyword in $keywords; do
    # Search for files containing this keyword
    local matches=$(find "$CORTEX_ROOT" -type f \( -name "*.sh" -o -name "*.js" -o -name "*.py" -o -name "*.ts" \) 2>/dev/null | \
      xargs grep -l "$keyword" 2>/dev/null | head -5 || true)

    if [ -n "$matches" ]; then
      while IFS= read -r file; do
        file_hints+=("$file")
      done <<< "$matches"
    fi
  done

  # Add file hints to task definition
  local task_file="$CORTEX_ROOT/coordination/tasks/${task_id}.json"

  if [ -f "$task_file" ] && [ ${#file_hints[@]} -gt 0 ]; then
    local hints_json=$(printf '%s\n' "${file_hints[@]}" | jq -R . | jq -s .)

    jq --argjson hints "$hints_json" \
      '.expected_files = $hints' \
      "$task_file" > "${task_file}.tmp" && mv "${task_file}.tmp" "$task_file"
  fi
}
