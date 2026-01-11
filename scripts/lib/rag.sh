#!/usr/bin/env bash
# RAG (Retrieval Augmented Generation) integration library
# Provides bash functions for querying and indexing the RAG system

RAG_BASE_PATH="/Users/ryandahlberg/Projects/cortex/llm-mesh/rag"
RAG_VENV="${RAG_BASE_PATH}/venv"
PYTHON_BIN="${RAG_VENV}/bin/python3"

# Activate virtual environment for RAG operations
activate_rag_env() {
    if [[ -f "${RAG_VENV}/bin/activate" ]]; then
        source "${RAG_VENV}/bin/activate"
    else
        echo "Warning: RAG virtual environment not found at ${RAG_VENV}" >&2
    fi
}

# Query RAG for similar tasks
# Usage: query_rag "search query" [top_k] [master_filter]
query_rag() {
    local query="$1"
    local top_k="${2:-5}"
    local master_filter="${3:-}"

    if [[ -z "$query" ]]; then
        echo "Error: query required" >&2
        return 1
    fi

    local cmd="${PYTHON_BIN} ${RAG_BASE_PATH}/retriever.py query '$query' --top-k $top_k --json"

    if [[ -n "$master_filter" ]]; then
        cmd="$cmd --master $master_filter"
    fi

    eval "$cmd"
}

# Query RAG for similar code patterns
# Usage: query_rag_patterns "search query" [top_k] [pattern_type_filter]
query_rag_patterns() {
    local query="$1"
    local top_k="${2:-3}"
    local pattern_type="${3:-}"

    if [[ -z "$query" ]]; then
        echo "Error: query required" >&2
        return 1
    fi

    local cmd="${PYTHON_BIN} ${RAG_BASE_PATH}/retriever.py query-patterns '$query' --top-k $top_k --json"

    if [[ -n "$pattern_type" ]]; then
        cmd="$cmd --pattern-type $pattern_type"
    fi

    eval "$cmd"
}

# Index a completed task
# Usage: index_current_task task_id description outcome [metadata_json]
index_current_task() {
    local task_id="$1"
    local description="$2"
    local outcome="$3"
    local metadata="${4:-}"

    if [[ -z "$task_id" ]] || [[ -z "$description" ]] || [[ -z "$outcome" ]]; then
        echo "Error: task_id, description, and outcome required" >&2
        return 1
    fi

    ${PYTHON_BIN} "${RAG_BASE_PATH}/indexer.py" index-task \
        --task-id "$task_id" \
        --description "$description" \
        --outcome "$outcome"
}

# Rebuild RAG index from coordination directory
# Usage: rebuild_rag_index [coordination_path]
rebuild_rag_index() {
    local coord_path="${1:-/Users/ryandahlberg/Projects/cortex/coordination}"

    echo "Rebuilding RAG index from $coord_path..."
    ${PYTHON_BIN} "${RAG_BASE_PATH}/indexer.py" rebuild --coordination-path "$coord_path"
}

# Get RAG system statistics
# Usage: rag_stats
rag_stats() {
    ${PYTHON_BIN} "${RAG_BASE_PATH}/retriever.py" stats
}

# Query and format results for master consumption
# Usage: query_rag_for_master master_name query [top_k]
query_rag_for_master() {
    local master_name="$1"
    local query="$2"
    local top_k="${3:-5}"

    if [[ -z "$master_name" ]] || [[ -z "$query" ]]; then
        echo "Error: master_name and query required" >&2
        return 1
    fi

    local results=$(query_rag "$query" "$top_k" "$master_name")

    # Format results for master context
    echo "=== RAG Retrieved Context ==="
    echo "Query: $query"
    echo "Master: $master_name"
    echo ""
    echo "$results" | jq -r '.[] | "[\(.score | . * 100 | round)%] \(.task_id)\n  Description: \(.description)\n  Outcome: \(.outcome)\n"'
    echo "=== End RAG Context ==="
}

# Extract relevant patterns and format for code generation
# Usage: query_patterns_for_implementation query [top_k]
query_patterns_for_implementation() {
    local query="$1"
    local top_k="${2:-3}"

    if [[ -z "$query" ]]; then
        echo "Error: query required" >&2
        return 1
    fi

    local results=$(query_rag_patterns "$query" "$top_k")

    # Format results for implementation context
    echo "=== Relevant Code Patterns ==="
    echo "Query: $query"
    echo ""
    echo "$results" | jq -r '.[] | "[\(.score | . * 100 | round)%] \(.pattern_type)\n  Description: \(.description)\n  Code:\n\(.code)\n"'
    echo "=== End Code Patterns ==="
}

# Check if RAG system is initialized
# Usage: rag_is_initialized
rag_is_initialized() {
    if [[ -f "${RAG_BASE_PATH}/storage/task_outcomes.index" ]]; then
        return 0
    else
        return 1
    fi
}

# Initialize RAG system (rebuild indexes)
# Usage: init_rag_system
init_rag_system() {
    echo "Initializing RAG system..."

    if ! rag_is_initialized; then
        echo "Building initial indexes..."
        rebuild_rag_index
    else
        echo "RAG system already initialized"
        rag_stats
    fi
}

# Augment master context with RAG retrieval
# Usage: augment_master_context master_name task_description
augment_master_context() {
    local master_name="$1"
    local task_description="$2"

    if [[ -z "$master_name" ]] || [[ -z "$task_description" ]]; then
        echo "Error: master_name and task_description required" >&2
        return 1
    fi

    echo "Retrieving relevant context for $master_name..."

    # Query for similar tasks
    local task_results=$(query_rag "$task_description" 3 "$master_name")

    # Query for relevant patterns
    local pattern_results=$(query_rag_patterns "$task_description" 2)

    # Create augmented context JSON
    cat <<EOF
{
  "rag_context": {
    "master": "$master_name",
    "query": "$task_description",
    "similar_tasks": $task_results,
    "relevant_patterns": $pattern_results,
    "retrieved_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }
}
EOF
}

# Auto-index task on completion (called from task completion hooks)
# Usage: auto_index_completed_task task_file
auto_index_completed_task() {
    local task_file="$1"

    if [[ ! -f "$task_file" ]]; then
        echo "Error: task file not found: $task_file" >&2
        return 1
    fi

    # Extract task details
    local task_id=$(jq -r '.task_id // .id' "$task_file")
    local description=$(jq -r '.description // .task' "$task_file")
    local outcome=$(jq -r '.outcome // ""' "$task_file")
    local status=$(jq -r '.status' "$task_file")

    # Only index completed tasks with outcomes
    if [[ "$status" == "completed" ]] && [[ -n "$outcome" ]]; then
        echo "Auto-indexing completed task: $task_id"
        index_current_task "$task_id" "$description" "$outcome"
    fi
}

# Export functions for use in other scripts
export -f query_rag
export -f query_rag_patterns
export -f index_current_task
export -f rebuild_rag_index
export -f rag_stats
export -f query_rag_for_master
export -f query_patterns_for_implementation
export -f rag_is_initialized
export -f init_rag_system
export -f augment_master_context
export -f auto_index_completed_task
