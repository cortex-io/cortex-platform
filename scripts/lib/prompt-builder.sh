#!/usr/bin/env bash
# Prompt Builder - 9-Step Framework
# Phase 2: Quality & Validation
# Implements the 9-step prompt engineering framework from LearnWorlds

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="${CORTEX_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Prompt templates directory
TEMPLATES_DIR="$CORTEX_HOME/templates/prompt-templates"
mkdir -p "$TEMPLATES_DIR"

##############################################################################
# build_prompt: Construct engineered prompt using 9-step framework
# Args:
#   --role: Define expertise and role
#   --audience: Specify your audience
#   --task: Define your task(s)
#   --method: Set the learning/execution method
#   --input: Provide additional input data
#   --constraints: Set constraints
#   --tone: Set tone and style
#   --format: Set output format
#   --validation: Validation criteria
# Returns: Engineered prompt text
##############################################################################
build_prompt() {
    local role=""
    local audience=""
    local task=""
    local method=""
    local input=""
    local constraints=""
    local tone=""
    local format=""
    local validation=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --role)
                role="$2"
                shift 2
                ;;
            --audience)
                audience="$2"
                shift 2
                ;;
            --task)
                task="$2"
                shift 2
                ;;
            --method)
                method="$2"
                shift 2
                ;;
            --input)
                input="$2"
                shift 2
                ;;
            --constraints)
                constraints="$2"
                shift 2
                ;;
            --tone)
                tone="$2"
                shift 2
                ;;
            --format)
                format="$2"
                shift 2
                ;;
            --validation)
                validation="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Build engineered prompt
    local prompt=""

    # Step 1: Role Definition
    if [ -n "$role" ]; then
        prompt+="# Role\n"
        prompt+="$role\n\n"
    fi

    # Step 2: Audience
    if [ -n "$audience" ]; then
        prompt+="# Audience\n"
        prompt+="This output is for: $audience\n\n"
    fi

    # Step 3: Task Definition
    if [ -n "$task" ]; then
        prompt+="# Task\n"
        prompt+="$task\n\n"
    else
        echo "Error: Task is required"
        exit 1
    fi

    # Step 4: Method
    if [ -n "$method" ]; then
        prompt+="# Method\n"
        prompt+="$method\n\n"
    fi

    # Step 5: Input Data
    if [ -n "$input" ]; then
        prompt+="# Input Data\n"
        prompt+="$input\n\n"
    fi

    # Step 6: Constraints
    if [ -n "$constraints" ]; then
        prompt+="# Constraints\n"
        prompt+="$constraints\n\n"
    fi

    # Step 7: Tone and Style
    if [ -n "$tone" ]; then
        prompt+="# Tone and Style\n"
        prompt+="$tone\n\n"
    fi

    # Step 8: Output Format
    if [ -n "$format" ]; then
        prompt+="# Output Format\n"
        prompt+="$format\n\n"
    fi

    # Step 9: Validation
    if [ -n "$validation" ]; then
        prompt+="# Validation Criteria\n"
        prompt+="$validation\n\n"
    fi

    echo -e "$prompt"
}

##############################################################################
# build_worker_prompt: Build prompt for Cortex worker
# Args:
#   $1: worker_type
#   $2: task_description
#   $3: additional_context (optional)
##############################################################################
build_worker_prompt() {
    local worker_type="$1"
    local task_description="$2"
    local additional_context="${3:-}"

    # Define role based on worker type
    local role=""
    local method=""
    local constraints=""
    local format=""

    case "$worker_type" in
        implementation-worker)
            role="You are an expert software engineer specialized in implementing features, writing clean code, and following best practices."
            method="1. Analyze the task requirements\n2. Design the solution\n3. Implement the code\n4. Test the implementation\n5. Document the changes"
            constraints="- Write production-quality code\n- Follow existing code style\n- Include error handling\n- Add inline comments for complex logic\n- DO NOT over-engineer solutions"
            format="Code files with clear structure, comments, and documentation"
            ;;
        security-scanner)
            role="You are a security expert specialized in identifying vulnerabilities, CVEs, and security risks."
            method="1. Scan for known vulnerabilities\n2. Analyze security configurations\n3. Check for exposed secrets\n4. Validate access controls\n5. Generate security report"
            constraints="- Focus on actionable findings\n- Prioritize by severity\n- Provide remediation guidance\n- Use industry-standard CVE references"
            format="Security report with findings, severity, and remediation steps"
            ;;
        documenter)
            role="You are a technical writer specialized in creating clear, comprehensive documentation."
            method="1. Understand the system/feature\n2. Identify key concepts\n3. Structure the documentation\n4. Write clear explanations\n5. Add examples and diagrams"
            constraints="- Use clear, concise language\n- Include practical examples\n- Add code snippets where helpful\n- Follow markdown formatting"
            format="Markdown documentation with sections, examples, and cross-references"
            ;;
        *)
            role="You are an expert AI assistant specialized in completing tasks efficiently and accurately."
            method="1. Understand the task\n2. Plan the approach\n3. Execute the task\n4. Verify the result"
            constraints="- Follow best practices\n- Produce high-quality output\n- Be thorough and accurate"
            format="Clear, well-structured output appropriate for the task"
            ;;
    esac

    # Build prompt using 9-step framework
    build_prompt \
        --role "$role" \
        --audience "Cortex autonomous system and human developers" \
        --task "$task_description" \
        --method "$method" \
        --input "$additional_context" \
        --constraints "$constraints" \
        --tone "Professional, technical, and precise" \
        --format "$format" \
        --validation "Output must be complete, functional, and well-documented"
}

##############################################################################
# save_template: Save prompt template for reuse
# Args:
#   $1: template_name
#   $2: prompt_content
##############################################################################
save_template() {
    local template_name="$1"
    local prompt_content="$2"

    local template_file="$TEMPLATES_DIR/${template_name}.md"

    echo "$prompt_content" > "$template_file"

    echo "Template saved: $template_file"
}

##############################################################################
# load_template: Load prompt template
# Args:
#   $1: template_name
##############################################################################
load_template() {
    local template_name="$1"
    local template_file="$TEMPLATES_DIR/${template_name}.md"

    if [ ! -f "$template_file" ]; then
        echo "Template not found: $template_name"
        exit 1
    fi

    cat "$template_file"
}

##############################################################################
# list_templates: List available prompt templates
##############################################################################
list_templates() {
    echo "Available prompt templates:"
    echo ""

    if [ ! -d "$TEMPLATES_DIR" ]; then
        echo "  (No templates found)"
        return 0
    fi

    local templates=$(ls "$TEMPLATES_DIR"/*.md 2>/dev/null || echo "")

    if [ -z "$templates" ]; then
        echo "  (No templates found)"
        return 0
    fi

    for template in $templates; do
        local name=$(basename "$template" .md)
        local size=$(wc -c < "$template" | tr -d ' ')
        echo "  - $name (${size} bytes)"
    done
}

##############################################################################
# validate_prompt: Validate prompt against 9-step framework
# Args:
#   $1: prompt_content
# Returns: Validation result
##############################################################################
validate_prompt() {
    local prompt_content="$1"

    local has_role=$(echo "$prompt_content" | grep -c "# Role" || echo "0")
    local has_task=$(echo "$prompt_content" | grep -c "# Task" || echo "0")
    local has_format=$(echo "$prompt_content" | grep -c "# Output Format" || echo "0")
    local has_validation=$(echo "$prompt_content" | grep -c "# Validation" || echo "0")

    local score=0
    local issues=()

    # Required components
    [ "$has_task" -gt 0 ] && score=$((score + 40)) || issues+=("Missing: Task definition")
    [ "$has_role" -gt 0 ] && score=$((score + 20)) || issues+=("Missing: Role definition")
    [ "$has_format" -gt 0 ] && score=$((score + 20)) || issues+=("Missing: Output format")
    [ "$has_validation" -gt 0 ] && score=$((score + 20)) || issues+=("Missing: Validation criteria")

    local status="incomplete"
    [ "$score" -eq 100 ] && status="complete"
    [ "$score" -ge 60 ] && status="partial"

    echo "Prompt Validation:"
    echo "  Status: $status"
    echo "  Score: $score/100"
    echo ""

    if [ ${#issues[@]} -gt 0 ]; then
        echo "Issues:"
        for issue in "${issues[@]}"; do
            echo "  - $issue"
        done
    else
        echo "✅ Prompt follows 9-step framework"
    fi
}

##############################################################################
# Main execution
##############################################################################
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        build)
            shift
            build_prompt "$@"
            ;;
        worker)
            shift
            if [ $# -lt 2 ]; then
                echo "Error: worker requires <worker_type> <task_description> [context]"
                exit 1
            fi
            build_worker_prompt "$@"
            ;;
        save)
            shift
            if [ $# -lt 2 ]; then
                echo "Error: save requires <template_name> <prompt_content>"
                exit 1
            fi
            save_template "$@"
            ;;
        load)
            shift
            if [ -z "${1:-}" ]; then
                echo "Error: load requires <template_name>"
                exit 1
            fi
            load_template "$1"
            ;;
        list)
            list_templates
            ;;
        validate)
            shift
            if [ -z "${1:-}" ]; then
                echo "Error: validate requires <prompt_content or file>"
                exit 1
            fi
            if [ -f "$1" ]; then
                validate_prompt "$(cat "$1")"
            else
                validate_prompt "$1"
            fi
            ;;
        *)
            cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  build --role <role> --task <task> [--audience <audience>] [--method <method>]
        [--input <input>] [--constraints <constraints>] [--tone <tone>]
        [--format <format>] [--validation <validation>]
    Build prompt using 9-step framework

  worker <worker_type> <task_description> [context]
    Build worker prompt with appropriate role and constraints

  save <template_name> <prompt_content>
    Save prompt as reusable template

  load <template_name>
    Load saved prompt template

  list
    List available templates

  validate <prompt_content or file>
    Validate prompt against 9-step framework

9-Step Framework:
  1. Role: Define expertise and role
  2. Audience: Specify your audience
  3. Task: Define your task(s)
  4. Method: Set the execution method
  5. Input: Provide additional input data
  6. Constraints: Set constraints
  7. Tone: Set tone and style
  8. Format: Set output format
  9. Validation: Validation criteria

Examples:
  # Build custom prompt
  $0 build --role "Expert Python developer" --task "Implement API endpoint" --format "Python code with tests"

  # Build worker prompt
  $0 worker implementation-worker "Create user authentication module"

  # Validate existing prompt
  $0 validate coordination/prompts/workers/implementation-worker.md

Templates stored in: $TEMPLATES_DIR
EOF
            ;;
    esac
fi
