#!/usr/bin/env bash

# NLP Task Classifier - 3-Layer Hybrid Architecture
# Layer 1: Keyword Dictionary (80% cases, instant)
# Layer 2: Pattern Matching (15% cases, fast)
# Layer 3: Claude API Fallback (5% cases, accurate)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Configuration
CONFIDENCE_THRESHOLD=0.7
LAYER1_KEYWORDS_FILE="${CORTEX_ROOT}/coordination/masters/coordinator/lib/keywords.json"
LAYER2_PATTERNS_FILE="${CORTEX_ROOT}/coordination/masters/coordinator/lib/patterns.json"

# Logging
log_classification() {
    local task_desc="$1"
    local method="$2"
    local master="$3"
    local confidence="$4"

    echo "{\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"task\":\"${task_desc}\",\"method\":\"${method}\",\"master\":\"${master}\",\"confidence\":${confidence}}" >> "${CORTEX_ROOT}/coordination/masters/coordinator/knowledge-base/classification-log.jsonl"
}

# Layer 1: Keyword Dictionary Classification
classify_by_keywords() {
    local task_description="$1"
    local task_lower
    task_lower=$(echo "$task_description" | tr '[:upper:]' '[:lower:]')

    local security_score=0
    local development_score=0
    local inventory_score=0
    local cicd_score=0

    # Security keywords
    local security_keywords=(
        "vulnerability" "cve" "audit" "compliance" "scan" "penetration"
        "security" "exploit" "threat" "risk" "authentication" "authorization"
        "encryption" "ssl" "tls" "certificate" "firewall" "malware"
        "intrusion" "breach" "hardening" "owasp" "sast" "dast"
    )

    # Development keywords
    local development_keywords=(
        "implement" "feature" "api" "endpoint" "refactor" "bug"
        "develop" "code" "function" "method" "class" "module"
        "library" "framework" "database" "query" "optimize" "performance"
        "integration" "service" "microservice" "rest" "graphql" "websocket"
    )

    # Inventory keywords
    local inventory_keywords=(
        "document" "catalog" "dependency" "repository" "portfolio"
        "documentation" "readme" "wiki" "guide" "tutorial" "reference"
        "inventory" "asset" "component" "package" "version" "upgrade"
        "deprecate" "maintenance" "changelog" "release-notes" "sbom"
    )

    # CI/CD keywords
    local cicd_keywords=(
        "deploy" "build" "pipeline" "test" "release" "automation"
        "ci" "cd" "continuous" "jenkins" "github-actions" "gitlab-ci"
        "docker" "kubernetes" "helm" "terraform" "ansible" "vagrant"
        "staging" "production" "rollback" "canary" "blue-green"
    )

    # Score each category
    for keyword in "${security_keywords[@]}"; do
        if [[ "$task_lower" == *"$keyword"* ]]; then
            security_score=$((security_score + 1))
        fi
    done

    for keyword in "${development_keywords[@]}"; do
        if [[ "$task_lower" == *"$keyword"* ]]; then
            development_score=$((development_score + 1))
        fi
    done

    for keyword in "${inventory_keywords[@]}"; do
        if [[ "$task_lower" == *"$keyword"* ]]; then
            inventory_score=$((inventory_score + 1))
        fi
    done

    for keyword in "${cicd_keywords[@]}"; do
        if [[ "$task_lower" == *"$keyword"* ]]; then
            cicd_score=$((cicd_score + 1))
        fi
    done

    # Determine winner and confidence
    local max_score=0
    local recommended_master=""
    local fallback_masters=()

    if [[ $security_score -gt $max_score ]]; then
        max_score=$security_score
        recommended_master="security-master"
    fi

    if [[ $development_score -gt $max_score ]]; then
        max_score=$development_score
        recommended_master="development-master"
    fi

    if [[ $inventory_score -gt $max_score ]]; then
        max_score=$inventory_score
        recommended_master="inventory-master"
    fi

    if [[ $cicd_score -gt $max_score ]]; then
        max_score=$cicd_score
        recommended_master="coordinator-master"  # CI/CD handled by coordinator
    fi

    # Calculate confidence (normalize to 0-1 range)
    local total_score=$((security_score + development_score + inventory_score + cicd_score))
    local confidence=0.0

    if [[ $total_score -gt 0 ]]; then
        # Confidence based on how dominant the winner is
        confidence=$(echo "scale=2; ($max_score / $total_score) * 0.9" | bc)
    fi

    # Determine fallback masters (scores > 0 but not winner)
    if [[ $security_score -gt 0 && "$recommended_master" != "security-master" ]]; then
        fallback_masters+=("security-master")
    fi
    if [[ $development_score -gt 0 && "$recommended_master" != "development-master" ]]; then
        fallback_masters+=("development-master")
    fi
    if [[ $inventory_score -gt 0 && "$recommended_master" != "inventory-master" ]]; then
        fallback_masters+=("inventory-master")
    fi

    # Format fallback masters as JSON array
    local fallback_json="[]"
    if [[ ${#fallback_masters[@]} -gt 0 ]]; then
        fallback_json="[\"$(IFS='","'; echo "${fallback_masters[*]}")\"]"
    fi

    echo "{\"classification_method\":\"keyword\",\"recommended_master\":\"${recommended_master}\",\"confidence\":${confidence},\"reasoning\":\"Keyword analysis: security=$security_score, development=$development_score, inventory=$inventory_score, cicd=$cicd_score\",\"fallback_masters\":${fallback_json}}"
}

# Layer 2: Pattern Matching Classification
classify_by_patterns() {
    local task_description="$1"
    local task_lower
    task_lower=$(echo "$task_description" | tr '[:upper:]' '[:lower:]')

    local recommended_master=""
    local confidence=0.0
    local reasoning=""
    local fallback_masters="[]"

    # Multi-master patterns (require coordination)
    if [[ "$task_lower" =~ (security.*audit.*feature|audit.*new.*feature|security.*review.*implementation) ]]; then
        recommended_master="coordinator-master"
        confidence=0.85
        reasoning="Multi-master task detected: security audit of new feature requires both security-master and development-master"
        fallback_masters='["security-master","development-master"]'

    # Security + deployment patterns
    elif [[ "$task_lower" =~ (security.*deploy|secure.*deployment|deploy.*security) ]]; then
        recommended_master="security-master"
        confidence=0.82
        reasoning="Security-focused deployment task"
        fallback_masters='["coordinator-master"]'

    # CVE-specific patterns
    elif [[ "$task_lower" =~ cve-[0-9]{4}-[0-9]+ ]]; then
        recommended_master="security-master"
        confidence=0.95
        reasoning="CVE reference detected - security vulnerability task"
        fallback_masters='[]'

    # Emergency/urgent patterns
    elif [[ "$task_lower" =~ (urgent|critical|emergency|asap|hotfix|immediate) ]]; then
        # Try to determine type, default to coordinator for triage
        if [[ "$task_lower" =~ (vulnerability|security|breach|exploit) ]]; then
            recommended_master="security-master"
            confidence=0.88
            reasoning="Urgent security task detected"
            fallback_masters='[]'
        elif [[ "$task_lower" =~ (bug|fix|broken|error|crash) ]]; then
            recommended_master="development-master"
            confidence=0.88
            reasoning="Urgent bug fix detected"
            fallback_masters='[]'
        else
            recommended_master="coordinator-master"
            confidence=0.75
            reasoning="Urgent task requires coordinator triage"
            fallback_masters='[]'
        fi

    # Complex implementation patterns
    elif [[ "$task_lower" =~ (implement.*and.*document|feature.*with.*tests|develop.*and.*test) ]]; then
        recommended_master="development-master"
        confidence=0.80
        reasoning="Complex development task with multiple deliverables"
        fallback_masters='["inventory-master"]'

    # Documentation-heavy patterns
    elif [[ "$task_lower" =~ (update.*documentation|generate.*docs|document.*changes|write.*readme) ]]; then
        recommended_master="inventory-master"
        confidence=0.87
        reasoning="Documentation-focused task"
        fallback_masters='[]'

    # Dependency/package patterns
    elif [[ "$task_lower" =~ (update.*dependencies|upgrade.*packages|dependency.*audit|npm.*audit|yarn.*audit) ]]; then
        recommended_master="inventory-master"
        confidence=0.84
        reasoning="Dependency management task"
        fallback_masters='["security-master"]'

    # CI/CD pipeline patterns
    elif [[ "$task_lower" =~ (github.*actions|gitlab.*ci|jenkins.*pipeline|build.*pipeline|deployment.*pipeline) ]]; then
        recommended_master="coordinator-master"
        confidence=0.86
        reasoning="CI/CD pipeline task"
        fallback_masters='[]'
    else
        # No pattern match
        recommended_master=""
        confidence=0.0
        reasoning="No pattern matched"
        fallback_masters='[]'
    fi

    if [[ -n "$recommended_master" ]]; then
        echo "{\"classification_method\":\"pattern\",\"recommended_master\":\"${recommended_master}\",\"confidence\":${confidence},\"reasoning\":\"${reasoning}\",\"fallback_masters\":${fallback_masters}}"
    else
        echo ""
    fi
}

# Layer 3: Claude API Fallback Classification
classify_by_claude_api() {
    local task_description="$1"

    if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
        echo "{\"classification_method\":\"error\",\"recommended_master\":\"coordinator-master\",\"confidence\":0.5,\"reasoning\":\"ANTHROPIC_API_KEY not set, defaulting to coordinator\",\"fallback_masters\":[]}" >&2
        return 1
    fi

    local prompt="You are a task classifier for the Cortex multi-agent system. Classify the following task and recommend which master agent should handle it.

Available masters:
- security-master: Security audits, vulnerability scans, CVE analysis, compliance checks, penetration testing
- development-master: Feature implementation, bug fixes, code refactoring, API development, performance optimization
- inventory-master: Documentation, repository cataloging, dependency management, portfolio tracking, SBOM generation
- coordinator-master: Multi-master coordination, CI/CD pipelines, complex workflows requiring multiple specialists

Task: ${task_description}

Respond with ONLY a JSON object in this exact format:
{
  \"recommended_master\": \"master-name\",
  \"confidence\": 0.95,
  \"reasoning\": \"brief explanation\",
  \"fallback_masters\": [\"optional-fallback-1\"]
}"

    local response
    response=$(curl -s https://api.anthropic.com/v1/messages \
        -H "Content-Type: application/json" \
        -H "x-api-key: ${ANTHROPIC_API_KEY}" \
        -H "anthropic-version: 2023-06-01" \
        -d '{
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": "'"${prompt}"'"
            }]
        }' 2>/dev/null)

    if [[ $? -ne 0 || -z "$response" ]]; then
        echo "{\"classification_method\":\"error\",\"recommended_master\":\"coordinator-master\",\"confidence\":0.5,\"reasoning\":\"Claude API call failed, defaulting to coordinator\",\"fallback_masters\":[]}" >&2
        return 1
    fi

    # Extract content from Claude response
    local content
    content=$(echo "$response" | jq -r '.content[0].text' 2>/dev/null)

    if [[ -z "$content" || "$content" == "null" ]]; then
        echo "{\"classification_method\":\"error\",\"recommended_master\":\"coordinator-master\",\"confidence\":0.5,\"reasoning\":\"Failed to parse Claude response, defaulting to coordinator\",\"fallback_masters\":[]}" >&2
        return 1
    fi

    # Validate JSON structure
    local validated
    validated=$(echo "$content" | jq -c '{recommended_master,confidence,reasoning,fallback_masters}' 2>/dev/null)

    if [[ -z "$validated" || "$validated" == "null" ]]; then
        echo "{\"classification_method\":\"error\",\"recommended_master\":\"coordinator-master\",\"confidence\":0.5,\"reasoning\":\"Invalid JSON from Claude, defaulting to coordinator\",\"fallback_masters\":[]}" >&2
        return 1
    fi

    # Add classification method
    echo "$validated" | jq -c '. + {classification_method: "claude"}'
}

# Main classification function
classify_task() {
    local task_description="$1"

    if [[ -z "$task_description" ]]; then
        echo "{\"classification_method\":\"error\",\"recommended_master\":\"coordinator-master\",\"confidence\":0.5,\"reasoning\":\"Empty task description\",\"fallback_masters\":[]}" >&2
        return 1
    fi

    # Layer 1: Try keyword classification
    local layer1_result
    layer1_result=$(classify_by_keywords "$task_description")

    local layer1_confidence
    layer1_confidence=$(echo "$layer1_result" | jq -r '.confidence' 2>/dev/null || echo "0.0")

    # If confidence is high enough, use Layer 1
    if (( $(echo "$layer1_confidence >= $CONFIDENCE_THRESHOLD" | bc -l) )); then
        log_classification "$task_description" "keyword" "$(echo "$layer1_result" | jq -r '.recommended_master')" "$layer1_confidence"
        echo "$layer1_result"
        return 0
    fi

    # Layer 2: Try pattern matching
    local layer2_result
    layer2_result=$(classify_by_patterns "$task_description")

    if [[ -n "$layer2_result" ]]; then
        local layer2_confidence
        layer2_confidence=$(echo "$layer2_result" | jq -r '.confidence' 2>/dev/null || echo "0.0")

        if (( $(echo "$layer2_confidence >= $CONFIDENCE_THRESHOLD" | bc -l) )); then
            log_classification "$task_description" "pattern" "$(echo "$layer2_result" | jq -r '.recommended_master')" "$layer2_confidence"
            echo "$layer2_result"
            return 0
        fi
    fi

    # Layer 3: Use Claude API fallback
    local layer3_result
    layer3_result=$(classify_by_claude_api "$task_description" 2>/dev/null)

    if [[ $? -eq 0 && -n "$layer3_result" ]]; then
        local layer3_confidence
        layer3_confidence=$(echo "$layer3_result" | jq -r '.confidence' 2>/dev/null || echo "0.0")
        log_classification "$task_description" "claude" "$(echo "$layer3_result" | jq -r '.recommended_master')" "$layer3_confidence"
        echo "$layer3_result"
        return 0
    fi

    # Fallback: Use best available result (prefer Layer 2 > Layer 1 > coordinator)
    if [[ -n "$layer2_result" ]]; then
        log_classification "$task_description" "pattern-fallback" "$(echo "$layer2_result" | jq -r '.recommended_master')" "$(echo "$layer2_result" | jq -r '.confidence')"
        echo "$layer2_result"
    elif [[ -n "$layer1_result" ]]; then
        log_classification "$task_description" "keyword-fallback" "$(echo "$layer1_result" | jq -r '.recommended_master')" "$layer1_confidence"
        echo "$layer1_result"
    else
        # Ultimate fallback
        echo "{\"classification_method\":\"fallback\",\"recommended_master\":\"coordinator-master\",\"confidence\":0.5,\"reasoning\":\"All classification layers failed, defaulting to coordinator for triage\",\"fallback_masters\":[]}"
    fi
}

# CLI interface
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <task_description>"
        echo "Example: $0 'Scan repository for CVE-2024-12345'"
        exit 1
    fi

    classify_task "$*"
fi
