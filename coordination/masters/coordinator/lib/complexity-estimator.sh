#!/bin/bash

# Complexity Estimator - Determines if tasks should be routed to Initializer
# Tasks with complexity > threshold get decomposed into feature lists first

estimate_task_complexity() {
  local task_description=$1

  # Complexity signals
  local word_count=$(echo "$task_description" | wc -w | tr -d ' ')
  local complexity_score=0

  # Signal 1: Word count (more words = more complex)
  if [ "$word_count" -lt 10 ]; then
    complexity_score=$((complexity_score + 1))
  elif [ "$word_count" -lt 30 ]; then
    complexity_score=$((complexity_score + 2))
  else
    complexity_score=$((complexity_score + 3))
  fi

  # Signal 2: Multiple components mentioned
  local component_keywords=("implement" "add" "create" "refactor" "migrate" "integrate" "setup" "configure")
  local component_count=0

  for keyword in "${component_keywords[@]}"; do
    if echo "$task_description" | grep -qi "$keyword"; then
      component_count=$((component_count + 1))
    fi
  done

  if [ "$component_count" -ge 3 ]; then
    complexity_score=$((complexity_score + 2))
  elif [ "$component_count" -ge 2 ]; then
    complexity_score=$((complexity_score + 1))
  fi

  # Signal 3: Security tasks (often need thorough decomposition)
  if echo "$task_description" | grep -Eqi "security|vulnerability|CVE|audit|compliance"; then
    complexity_score=$((complexity_score + 1))
  fi

  # Signal 4: System-level changes
  if echo "$task_description" | grep -Eqi "architecture|system|infrastructure|database|authentication"; then
    complexity_score=$((complexity_score + 1))
  fi

  # Signal 5: Testing requirements mentioned
  if echo "$task_description" | grep -Eqi "test|testing|validate|verify"; then
    complexity_score=$((complexity_score + 1))
  fi

  # Signal 6: Multiple actions (and, then, also, etc.)
  local connector_count=$(echo "$task_description" | grep -oi -E '\b(and|then|also|additionally|plus|with)\b' | wc -l | tr -d ' ')
  if [ "$connector_count" -ge 3 ]; then
    complexity_score=$((complexity_score + 2))
  elif [ "$connector_count" -ge 2 ]; then
    complexity_score=$((complexity_score + 1))
  fi

  echo "$complexity_score"
}

# Check if task should be routed to initializer first
should_route_to_initializer() {
  local task_description=$1
  local complexity_threshold=${2:-3}

  local complexity=$(estimate_task_complexity "$task_description")

  if [ "$complexity" -gt "$complexity_threshold" ]; then
    echo "true"
    return 0
  else
    echo "false"
    return 1
  fi
}

# Get complexity level as string
get_complexity_level() {
  local complexity=$1

  if [ "$complexity" -le 2 ]; then
    echo "simple"
  elif [ "$complexity" -le 4 ]; then
    echo "moderate"
  elif [ "$complexity" -le 6 ]; then
    echo "complex"
  else
    echo "very-complex"
  fi
}

# Export functions if sourced
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
  export -f estimate_task_complexity
  export -f should_route_to_initializer
  export -f get_complexity_level
fi
