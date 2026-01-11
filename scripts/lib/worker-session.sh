#!/bin/bash

# Worker Session Management
# Handles session start/end, progress tracking, and context continuity

CORTEX_ROOT="${CORTEX_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Start a new worker session
start_worker_session() {
  local worker_id=$1
  local task_id=$2
  local feature_id=${3:-"none"}

  local session_dir="$CORTEX_ROOT/coordination/workers/${worker_id}/progress"
  mkdir -p "$session_dir"

  # Find next session number
  local session_num=$(find "$session_dir" -name "session-*-progress.txt" 2>/dev/null | wc -l | tr -d ' ')
  session_num=$((session_num + 1))

  local session_file="${session_dir}/session-$(printf '%03d' $session_num)-progress.txt"

  # Initialize session
  cat > "$session_file" <<EOF
Session: $(printf '%03d' $session_num)
Worker: $worker_id
Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Task: $task_id
Feature: $feature_id

=== What Was Done ===
(Session in progress...)

=== Files Modified ===
(To be updated on session end)

=== Tests Run ===
(To be updated on session end)

=== Git Commits ===
(To be updated on session end)

=== Next Steps ===
(To be determined)

=== Blockers ===
None
EOF

  # Create current session pointer
  echo "$session_file" > "${session_dir}/current-session-path.txt"

  # Create machine-readable session JSON
  jq -n \
    --arg session_num "$(printf '%03d' $session_num)" \
    --arg worker_id "$worker_id" \
    --arg task_id "$task_id" \
    --arg feature_id "$feature_id" \
    --arg started_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{
      session_num: $session_num,
      worker_id: $worker_id,
      task_id: $task_id,
      feature_id: $feature_id,
      started_at: $started_at,
      status: "in_progress"
    }' > "${session_dir}/current-session.json"

  echo "$session_file"
}

# End a worker session
end_worker_session() {
  local worker_id=$1
  local session_file=${2:-}
  local summary=${3:-"Session completed"}

  local session_dir="$CORTEX_ROOT/coordination/workers/${worker_id}/progress"

  # Get session file if not provided
  if [ -z "$session_file" ] && [ -f "${session_dir}/current-session-path.txt" ]; then
    session_file=$(cat "${session_dir}/current-session-path.txt")
  fi

  if [ ! -f "$session_file" ]; then
    echo "ERROR: Session file not found: $session_file"
    return 1
  fi

  # Get modified files from git
  local modified_files=$(git diff --name-only HEAD~1..HEAD 2>/dev/null || echo "None")

  # Get git commits from last 30 minutes
  local git_commits=$(git log --oneline --since="30 minutes ago" --author="cortex" 2>/dev/null || echo "None")

  # Update session end time
  local ended_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Update progress file
  sed -i '' "s/Started: \\(.*\\)/Started: \\1\\nEnded: $ended_at/" "$session_file"

  # Update files modified section
  sed -i '' "/=== Files Modified ===/,/===/{
    /=== Files Modified ===/!{
      /===/!d
    }
  }" "$session_file"

  cat >> "$session_file" <<EOF

=== Files Modified ===
$modified_files

EOF

  # Update git commits section if any
  if [ "$git_commits" != "None" ]; then
    sed -i '' "/=== Git Commits ===/,/===/{
      /=== Git Commits ===/!{
        /===/!d
      }
    }" "$session_file"

    cat >> "$session_file" <<EOF

=== Git Commits ===
$git_commits

EOF
  fi

  # Add summary
  echo "" >> "$session_file"
  echo "=== Session Summary ===" >> "$session_file"
  echo "$summary" >> "$session_file"

  # Update JSON
  if [ -f "${session_dir}/current-session.json" ]; then
    jq \
      --arg ended_at "$ended_at" \
      --arg summary "$summary" \
      '
      .ended_at = $ended_at |
      .status = "completed" |
      .summary = $summary
      ' "${session_dir}/current-session.json" > "${session_dir}/current-session.json.tmp"

    mv "${session_dir}/current-session.json.tmp" "${session_dir}/current-session.json"

    # Archive to history
    local session_num=$(jq -r '.session_num' "${session_dir}/current-session.json")
    cp "${session_dir}/current-session.json" "${session_dir}/session-${session_num}.json"
  fi

  echo "Session ended: $session_file"
}

# Load previous session context
load_previous_session() {
  local worker_id=$1

  local session_dir="$CORTEX_ROOT/coordination/workers/${worker_id}/progress"

  if [ ! -d "$session_dir" ]; then
    echo "No previous sessions found"
    return 0
  fi

  # Get most recent session
  local latest_session=$(find "$session_dir" -name "session-*-progress.txt" | sort -r | head -1)

  if [ -z "$latest_session" ]; then
    echo "No previous sessions found"
    return 0
  fi

  echo "=== Previous Session Context ==="
  echo ""
  tail -30 "$latest_session"
  echo ""
  echo "================================"
}

# Add progress note to current session
add_progress_note() {
  local worker_id=$1
  local note=$2

  local session_dir="$CORTEX_ROOT/coordination/workers/${worker_id}/progress"

  if [ -f "${session_dir}/current-session-path.txt" ]; then
    local session_file=$(cat "${session_dir}/current-session-path.txt")

    if [ -f "$session_file" ]; then
      # Find the "What Was Done" section and append
      local temp_file="${session_file}.tmp"

      awk -v note="$note" '
        /=== What Was Done ===/ {
          print
          getline
          if ($0 ~ /\(Session in progress\.\.\.\)/) {
            print note
          } else {
            print
            print note
          }
          next
        }
        { print }
      ' "$session_file" > "$temp_file"

      mv "$temp_file" "$session_file"
    fi
  fi
}

# Get session statistics
get_session_stats() {
  local worker_id=$1

  local session_dir="$CORTEX_ROOT/coordination/workers/${worker_id}/progress"

  if [ ! -d "$session_dir" ]; then
    echo "{\"total_sessions\": 0}"
    return 0
  fi

  local total_sessions=$(find "$session_dir" -name "session-*.json" | wc -l | tr -d ' ')
  local current_session=$([ -f "${session_dir}/current-session.json" ] && cat "${session_dir}/current-session.json" || echo '{}')

  jq -n \
    --arg total "$total_sessions" \
    --argjson current "$current_session" \
    '{
      total_sessions: ($total | tonumber),
      current_session: $current
    }'
}

# Export functions if sourced
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
  export -f start_worker_session
  export -f end_worker_session
  export -f load_previous_session
  export -f add_progress_note
  export -f get_session_stats
fi
