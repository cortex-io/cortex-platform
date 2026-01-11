# API Reference

Auto-generated API documentation for Cortex scripts and functions.

> **Note**: This documentation is auto-generated. Do not edit manually.

---

## Core Scripts

### NLP Task Classifier

**Path**: `coordination/masters/coordinator/lib/nlp-classifier.sh`

**Description**:

NLP Task Classifier - 3-Layer Hybrid Architecture
Layer 1: Keyword Dictionary (80% cases, instant)
Layer 2: Pattern Matching (15% cases, fast)
Layer 3: Claude API Fallback (5% cases, accurate)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

Configuration
CONFIDENCE_THRESHOLD=0.7
LAYER1_KEYWORDS_FILE="${CORTEX_ROOT}/coordination/masters/coordinator/lib/keywords.json"
LAYER2_PATTERNS_FILE="${CORTEX_ROOT}/coordination/masters/coordinator/lib/patterns.json"

Logging
log_classification() {
    local task_desc="$1"
    local method="$2"
    local master="$3"

**Functions**:

- `log_classification()`
- `classify_by_keywords()`
- `classify_by_patterns()`
- `classify_by_claude_api()`
- `classify_task()`

**CLI Usage**:

```bash
        echo "Usage: $0 <task_description>"
        echo "Example: $0 'Scan repository for CVE-2024-12345'"
        exit 1
    fi

    classify_task "$*"
```

---

### Template Validator

**Path**: `coordination/templates/validator.sh`

**Description**:

Template Validator
Validates task submissions against templates

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR"

Validate a task against a template
validate_task() {
    local template_id="$1"
    local task_json="$2"

    local template_file="${TEMPLATES_DIR}/${template_id}.json"

    if [[ ! -f "$template_file" ]]; then
        echo "{\"valid\":false,\"errors\":[\"Template '${template_id}' not found\"]}"
        return 1
    fi
--

**Functions**:

- `validate_task()`
- `list_templates()`
- `get_template()`
- `suggest_template()`
- `generate_task_from_template()`

**CLI Usage**:

```bash
                echo "Usage: $0 validate <template_id> <task_json>"
                exit 1
            fi
            validate_task "$2" "$3"
            ;;

--
                echo "Usage: $0 get <template_id>"
                exit 1
            fi
```

---

### Knowledge Base Search

**Path**: `coordination/knowledge-base/search.sh`

**Description**:

Knowledge Base Search
Search across master knowledge bases, routing history, and completed tasks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

Configuration
MASTERS_DIR="${CORTEX_ROOT}/coordination/masters"
TASKS_DIR="${CORTEX_ROOT}/coordination/tasks"
ROUTING_LOG="${CORTEX_ROOT}/coordination/masters/coordinator/knowledge-base/routing-decisions.jsonl"

Search by keywords across all knowledge bases
search_by_keywords() {
    local query="$1"
    local max_results="${2:-10}"

    local results=()
    local result_count=0

**Functions**:

- `search_by_keywords()`
- `find_similar_tasks()`
- `get_routing_history()`
- `suggest_master()`
- `search_task_by_id()`

**CLI Usage**:

```bash
                echo "Usage: $0 search <query> [max_results]"
                exit 1
            fi
            search_by_keywords "$2" "${3:-10}"
            ;;

--
                echo "Usage: $0 similar <task_description> [max_results]"
                exit 1
            fi
```

---

### Cortex CLI

**Path**: `scripts/cortex-cli.sh`

**Description**:

Cortex CLI - Interactive Task Management
Enhanced CLI with wizard-based task submission and management

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

Import dependencies
NLP_CLASSIFIER="${CORTEX_ROOT}/coordination/masters/coordinator/lib/nlp-classifier.sh"
TEMPLATE_VALIDATOR="${CORTEX_ROOT}/coordination/templates/validator.sh"
KB_SEARCH="${CORTEX_ROOT}/coordination/knowledge-base/search.sh"
SPAWN_WORKER="${CORTEX_ROOT}/scripts/spawn-worker.sh"

Configuration
TASKS_DIR="${CORTEX_ROOT}/coordination/tasks"
WORKERS_DIR="${CORTEX_ROOT}/coordination/worker-specs/active"

Color output (if terminal supports it)
if [[ -t 1 ]]; then

**Functions**:

- `print_header()`
- `print_success()`
- `print_error()`
- `print_warning()`
- `print_info()`
- `cmd_submit()`
- `cmd_status()`
- `cmd_list()`
- `cmd_workers()`
- `cmd_masters()`

**CLI Usage**:

```bash
        print_error "Usage: cortex status <task_id>"
        exit 1
    fi

    local task_file="${TASKS_DIR}/${task_id}.json"

--
                print_error "Usage: cortex status <task_id>"
                exit 1
            fi
```

---

