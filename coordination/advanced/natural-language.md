# Natural Language Interface for Cortex

## Overview

The Natural Language Interface (NLI) enables human operators to interact with the cortex automation system using plain language requests. The system translates intent into structured execution plans, coordinates contractors and workers, and provides clear feedback throughout.

## Architecture

```
User Request → Intent Parser → Task Decomposer → Contractor Mapper → Execution Plan
                                                                              ↓
User Feedback ← Response Generator ← Progress Monitor ← Worker Coordination
```

## 1. High-Level Intent Parsing Patterns

### Intent Classification Framework

Intent parsing uses a hierarchical classification system:

```
Level 1: Action Type (CREATE, READ, UPDATE, DELETE, DIAGNOSE, OPTIMIZE)
Level 2: Resource Category (infrastructure, workflow, configuration, monitoring)
Level 3: Specific Intent (deploy_cluster, setup_monitoring, fix_service)
Level 4: Constraints & Parameters (region, size, urgency, dependencies)
```

### Pattern Matching Strategies

**Keyword-Based Classification**:
```
"deploy" | "create" | "build" | "setup" → CREATE action
"show" | "list" | "describe" | "check" → READ action
"update" | "modify" | "change" | "upgrade" → UPDATE action
"delete" | "remove" | "destroy" | "clean" → DELETE action
"fix" | "repair" | "debug" | "troubleshoot" → DIAGNOSE action
"optimize" | "improve" | "tune" | "speed up" → OPTIMIZE action
```

**Resource Detection**:
```
"kubernetes" | "k8s" | "cluster" → infrastructure/kubernetes
"workflow" | "automation" | "n8n" → workflow/orchestration
"monitor" | "alert" | "prometheus" | "grafana" → monitoring/observability
"vault" | "secret" | "credential" → configuration/secrets
"backup" | "restore" | "snapshot" → infrastructure/backup
```

**Contextual Modifiers**:
```
"production" | "prod" → environment: production, priority: high
"test" | "staging" | "dev" → environment: non-production, priority: medium
"urgent" | "asap" | "critical" → priority: critical
"when done" | "later" | "low priority" → priority: low
"high availability" | "HA" → requirements: [ha, redundancy]
```

### Intent Parsing Algorithm

```python
def parse_intent(user_request):
    """
    Parse natural language into structured intent
    """
    # Step 1: Normalize input
    normalized = normalize_text(user_request)

    # Step 2: Extract entities
    entities = extract_entities(normalized)
    # entities: {action, resources, constraints, modifiers}

    # Step 3: Classify action
    action = classify_action(entities['action_keywords'])

    # Step 4: Identify resources
    resources = identify_resources(entities['resource_keywords'])

    # Step 5: Extract parameters
    parameters = extract_parameters(normalized, entities)

    # Step 6: Determine confidence
    confidence = calculate_confidence(entities, action, resources)

    # Step 7: Build structured intent
    intent = {
        "action": action,
        "resources": resources,
        "parameters": parameters,
        "confidence": confidence,
        "original_request": user_request,
        "entities": entities
    }

    return intent
```

### Example Intent Parsing

**Input**: "Build me a high availability k8s cluster in production"

**Parsed Intent**:
```json
{
  "action": "CREATE",
  "action_subtype": "deploy",
  "resources": [
    {
      "type": "infrastructure",
      "subtype": "kubernetes",
      "category": "cluster"
    }
  ],
  "parameters": {
    "environment": "production",
    "high_availability": true,
    "replicas": 3,
    "auto_scaling": true
  },
  "constraints": {
    "priority": "high",
    "approval_required": true,
    "destructive": false
  },
  "confidence": 0.95,
  "original_request": "Build me a high availability k8s cluster in production",
  "ambiguities": []
}
```

## 2. Task Decomposition Algorithms

### Hierarchical Task Network (HTN) Decomposition

The system uses HTN planning to break complex requests into executable subtasks:

```
Complex Task → Abstract Task Sequence → Concrete Task Assignments → Worker Execution
```

### Decomposition Rules

**Rule-Based Decomposition**:
```yaml
deploy_k8s_cluster:
  preconditions:
    - infrastructure_available
    - credentials_configured
  decomposition:
    - task: provision_infrastructure
      contractor: infrastructure-contractor
      subtasks:
        - create_network
        - create_load_balancer
        - provision_nodes
    - task: install_kubernetes
      contractor: talos-contractor
      dependencies: [provision_infrastructure]
      subtasks:
        - generate_config
        - bootstrap_control_plane
        - join_worker_nodes
    - task: configure_cluster
      contractor: infrastructure-contractor
      dependencies: [install_kubernetes]
      subtasks:
        - install_cni
        - configure_storage
        - setup_ingress
    - task: verify_deployment
      contractor: monitoring-contractor
      dependencies: [configure_cluster]
      subtasks:
        - health_check
        - smoke_tests
```

### Decomposition Algorithm

```python
def decompose_task(intent, context):
    """
    Decompose high-level intent into executable task graph
    """
    # Step 1: Retrieve decomposition template
    template = get_decomposition_template(intent['action'], intent['resources'])

    # Step 2: Check preconditions
    preconditions_met = verify_preconditions(template['preconditions'], context)
    if not preconditions_met:
        return handle_unmet_preconditions(preconditions_met)

    # Step 3: Instantiate task graph
    task_graph = instantiate_tasks(template['decomposition'], intent['parameters'])

    # Step 4: Resolve dependencies
    task_graph = resolve_dependencies(task_graph, context)

    # Step 5: Assign contractors
    task_graph = assign_contractors(task_graph)

    # Step 6: Estimate resources
    task_graph = estimate_resources(task_graph)

    # Step 7: Calculate critical path
    task_graph['critical_path'] = calculate_critical_path(task_graph)
    task_graph['estimated_duration'] = sum_critical_path_duration(task_graph)

    return task_graph
```

### Task Graph Structure

```json
{
  "task_id": "deploy-k8s-prod-001",
  "intent": { /* original intent */ },
  "tasks": [
    {
      "task_id": "task-001",
      "name": "provision_infrastructure",
      "contractor": "infrastructure-contractor",
      "dependencies": [],
      "estimated_duration": "15m",
      "token_allocation": 5000,
      "subtasks": [
        {
          "subtask_id": "subtask-001-1",
          "name": "create_network",
          "estimated_duration": "5m"
        }
      ]
    }
  ],
  "critical_path": ["task-001", "task-002", "task-003"],
  "estimated_total_duration": "45m",
  "estimated_total_tokens": 15000
}
```

### Parallel vs Sequential Decomposition

**Parallel Execution Opportunities**:
```
IF tasks have no dependencies AND share no conflicting resources:
  EXECUTE in parallel

EXAMPLE:
  - Setup monitoring (parallel to)
  - Configure backup system

Both can run simultaneously during cluster deployment
```

**Sequential Requirements**:
```
IF task_B depends on output of task_A:
  EXECUTE sequentially

EXAMPLE:
  1. Provision infrastructure
  2. THEN install Kubernetes (requires infrastructure)
  3. THEN configure networking (requires cluster)
```

## 3. Ambiguity Resolution Strategies

### Ambiguity Detection

The system detects several types of ambiguities:

1. **Missing Parameters**: Required information not provided
2. **Vague Specifications**: Unclear intent or scope
3. **Multiple Interpretations**: Request could mean different things
4. **Conflicting Requirements**: Incompatible parameters specified

### Resolution Strategies

#### Strategy 1: Intelligent Defaults with Confirmation

```python
def resolve_with_defaults(intent, ambiguities):
    """
    Apply intelligent defaults and ask for confirmation
    """
    defaults_applied = {}

    for ambiguity in ambiguities:
        if ambiguity['type'] == 'missing_parameter':
            # Apply context-aware default
            default_value = get_smart_default(
                parameter=ambiguity['parameter'],
                context=intent,
                environment=intent.get('parameters', {}).get('environment')
            )

            defaults_applied[ambiguity['parameter']] = {
                'value': default_value,
                'reason': f"Based on {intent['environment']} best practices"
            }

    # Generate confirmation request
    confirmation = generate_confirmation(intent, defaults_applied)

    return confirmation
```

**Example**:
```
User: "Deploy monitoring"
System: "I'll deploy monitoring with these defaults:
  - Stack: Prometheus + Grafana
  - Retention: 30 days
  - Scrape interval: 30s
  - Environment: production (based on current context)

Proceed with these settings? (yes/no/customize)"
```

#### Strategy 2: Clarification Questions

```python
def generate_clarification_questions(ambiguities):
    """
    Generate targeted questions to resolve ambiguities
    """
    questions = []

    for ambiguity in ambiguities:
        question = {
            'parameter': ambiguity['parameter'],
            'question': format_question(ambiguity),
            'options': get_valid_options(ambiguity),
            'default': get_recommended_option(ambiguity)
        }
        questions.append(question)

    return questions
```

**Example**:
```
User: "Fix the broken service"
System: "I need more information:
  1. Which service? (detected: [api-service, web-service, cache-service])
  2. What type of issue? (options: crashes, slow, unreachable, errors)
  3. Environment? (options: production, staging, development)

You can say 'api-service is crashing in production' or answer individually."
```

#### Strategy 3: Progressive Disclosure

For complex requests, gather information iteratively:

```
Turn 1: Understand primary intent
Turn 2: Clarify scope and environment
Turn 3: Confirm resource allocation
Turn 4: Execute with progress updates
```

### Ambiguity Scoring

```python
def calculate_ambiguity_score(intent):
    """
    Score how ambiguous a request is (0.0 = clear, 1.0 = very ambiguous)
    """
    score = 0.0

    # Missing critical parameters
    missing_critical = count_missing_critical_params(intent)
    score += missing_critical * 0.3

    # Vague terms used
    vague_terms = detect_vague_terms(intent['original_request'])
    score += len(vague_terms) * 0.1

    # Multiple possible interpretations
    interpretations = count_possible_interpretations(intent)
    if interpretations > 1:
        score += 0.2 * (interpretations - 1)

    # Low confidence entities
    low_confidence_entities = [e for e in intent['entities'] if e['confidence'] < 0.7]
    score += len(low_confidence_entities) * 0.15

    return min(score, 1.0)
```

## 4. Context Extraction from Requests

### Context Types

1. **Explicit Context**: Directly stated in request
2. **Implicit Context**: Inferred from environment, history, or patterns
3. **Conversational Context**: From previous turns in conversation
4. **System Context**: Current state of infrastructure

### Context Extraction Pipeline

```python
def extract_context(request, conversation_history, system_state):
    """
    Extract all relevant context from request and environment
    """
    context = {
        'explicit': {},
        'implicit': {},
        'conversational': {},
        'system': {}
    }

    # Explicit context: Parse directly from request
    context['explicit'] = {
        'environment': extract_environment(request),
        'region': extract_region(request),
        'scale': extract_scale_indicators(request),
        'urgency': extract_urgency(request),
        'constraints': extract_constraints(request)
    }

    # Implicit context: Infer from patterns
    context['implicit'] = {
        'time_of_day': get_current_time_context(),
        'user_role': infer_user_role(request),
        'project_phase': infer_project_phase(system_state),
        'resource_availability': check_resource_availability(system_state)
    }

    # Conversational context: From history
    if conversation_history:
        context['conversational'] = {
            'referenced_entities': extract_pronouns_references(request, conversation_history),
            'ongoing_tasks': get_ongoing_tasks(conversation_history),
            'previous_decisions': get_previous_decisions(conversation_history)
        }

    # System context: Current state
    context['system'] = {
        'existing_infrastructure': system_state.get('infrastructure', {}),
        'running_services': system_state.get('services', {}),
        'recent_incidents': system_state.get('incidents', []),
        'maintenance_windows': system_state.get('maintenance', [])
    }

    return context
```

### Pronoun and Reference Resolution

```python
def resolve_references(request, conversation_history):
    """
    Resolve pronouns and references to previous entities
    """
    references = {
        'it': None,
        'that': None,
        'them': None,
        'there': None
    }

    # Find reference words
    for ref_word in references.keys():
        if ref_word in request.lower():
            # Look back in conversation history
            references[ref_word] = find_most_recent_entity(
                conversation_history,
                entity_type=infer_entity_type(ref_word, request)
            )

    return references
```

**Example**:
```
Turn 1: "Deploy a k8s cluster in us-west"
Turn 2: "Add monitoring to it"
         └─> "it" resolves to "k8s cluster in us-west"

Turn 3: "Scale that up to 10 nodes"
         └─> "that" resolves to "k8s cluster in us-west"
```

### Environmental Context Inference

```python
def infer_environment(request, system_state):
    """
    Infer target environment when not explicitly stated
    """
    # Check for explicit mentions
    if any(env in request.lower() for env in ['prod', 'production']):
        return 'production'
    if any(env in request.lower() for env in ['test', 'staging', 'dev']):
        return 'non-production'

    # Infer from urgency
    if any(urgent in request.lower() for urgent in ['urgent', 'critical', 'asap']):
        return 'production'  # Urgent usually means production

    # Infer from time of day
    current_hour = get_current_hour()
    if 9 <= current_hour <= 17:  # Business hours
        return 'production'  # More likely production changes
    else:
        return 'non-production'  # Off-hours, probably testing

    # Infer from user role
    user_role = get_user_role()
    if user_role in ['operator', 'sre']:
        return 'production'

    # Default to safest option
    return 'non-production'
```

## 5. Confirmation Workflows for Destructive Operations

### Destructive Operation Detection

```python
DESTRUCTIVE_OPERATIONS = {
    'DELETE': {
        'keywords': ['delete', 'remove', 'destroy', 'terminate', 'drop'],
        'severity': 'critical',
        'requires_confirmation': True,
        'requires_backup': True
    },
    'UPDATE': {
        'keywords': ['update', 'upgrade', 'migrate', 'modify'],
        'severity': 'high',
        'requires_confirmation': True,
        'requires_backup': False
    },
    'SCALE_DOWN': {
        'keywords': ['scale down', 'reduce', 'downsize'],
        'severity': 'medium',
        'requires_confirmation': True,
        'requires_backup': False
    }
}

def is_destructive(intent):
    """
    Determine if operation is destructive
    """
    action = intent['action']
    resources = intent['resources']
    environment = intent.get('parameters', {}).get('environment')

    # Always destructive
    if action in ['DELETE', 'DESTROY']:
        return True, 'critical'

    # Conditionally destructive
    if action == 'UPDATE' and environment == 'production':
        return True, 'high'

    # Resource-specific
    if any(r['type'] == 'database' for r in resources):
        return True, 'critical'

    return False, None
```

### Confirmation Flow

```python
def generate_confirmation_workflow(intent, destructive_level):
    """
    Generate appropriate confirmation workflow
    """
    workflow = {
        'steps': [],
        'required_confirmations': 0,
        'estimated_impact': {}
    }

    # Step 1: Impact analysis
    workflow['steps'].append({
        'step': 'impact_analysis',
        'action': 'analyze_impact',
        'output': 'impact_report'
    })

    # Step 2: Show impact and ask for confirmation
    if destructive_level == 'critical':
        workflow['steps'].append({
            'step': 'explicit_confirmation',
            'message': generate_critical_confirmation_message(intent),
            'require_typed_confirmation': True,
            'confirmation_phrase': f"delete {intent['resources'][0]['name']}"
        })
        workflow['required_confirmations'] = 2  # Double confirmation

    elif destructive_level == 'high':
        workflow['steps'].append({
            'step': 'standard_confirmation',
            'message': generate_standard_confirmation_message(intent),
            'require_typed_confirmation': False,
            'options': ['yes', 'no', 'show-details']
        })
        workflow['required_confirmations'] = 1

    # Step 3: Backup (if required)
    if DESTRUCTIVE_OPERATIONS[intent['action']].get('requires_backup'):
        workflow['steps'].append({
            'step': 'create_backup',
            'action': 'backup_resources',
            'resources': intent['resources']
        })

    # Step 4: Execute with rollback plan
    workflow['steps'].append({
        'step': 'execute',
        'action': 'execute_operation',
        'rollback_plan': generate_rollback_plan(intent)
    })

    return workflow
```

### Confirmation Message Templates

**Critical Destructive Operation**:
```
⚠️  CRITICAL DESTRUCTIVE OPERATION ⚠️

You are about to DELETE the following resources:
  - Production Kubernetes Cluster "prod-k8s-west"
  - 12 worker nodes
  - 3 control plane nodes
  - Persistent volumes (5TB data)

IMPACT:
  - Downtime: All services in us-west region
  - Data Loss: Potential if backups not current
  - Recovery Time: 2-4 hours minimum
  - Affected Users: ~50,000

DEPENDENCIES:
  - api-service (production)
  - web-frontend (production)
  - cache-service (production)

A backup will be created before deletion.

To confirm, type: delete prod-k8s-west

Type 'cancel' to abort.
```

**Standard Confirmation**:
```
You are about to UPDATE:
  - Kubernetes cluster "staging-k8s"
  - Upgrade: v1.28 → v1.29

IMPACT:
  - Downtime: 15-20 minutes
  - Rolling update of nodes
  - No data loss expected

Proceed? (yes/no/show-details)
```

### Dry-Run Option

```python
def offer_dry_run(intent):
    """
    Offer dry-run for complex or destructive operations
    """
    return f"""
Would you like me to perform a dry-run first?

Dry-run will:
  ✓ Validate all configurations
  ✓ Check preconditions
  ✓ Estimate resource usage
  ✓ Identify potential issues
  ✗ Not make any actual changes

Options:
  1. dry-run - See what would happen
  2. proceed - Execute now
  3. cancel - Abort operation
"""
```

## 6. Progress Reporting Formats

### Progress Update Structure

```json
{
  "task_id": "deploy-k8s-001",
  "status": "in_progress",
  "current_phase": "configure_cluster",
  "progress_percentage": 65,
  "elapsed_time": "18m 34s",
  "estimated_remaining": "9m 15s",
  "completed_tasks": [
    "provision_infrastructure",
    "install_kubernetes"
  ],
  "current_task": {
    "name": "configure_cluster",
    "subtask": "install_cni",
    "progress": 80
  },
  "pending_tasks": [
    "verify_deployment"
  ],
  "events": [
    {
      "timestamp": "2025-12-09T10:15:00Z",
      "event": "Control plane bootstrapped",
      "level": "info"
    }
  ]
}
```

### Real-Time Progress Display

**Console Format**:
```
╔══════════════════════════════════════════════════════════════╗
║ Deploying Kubernetes Cluster: prod-k8s-west                 ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ Progress: [████████████████░░░░░░░░] 65% (18m 34s / ~28m)  ║
║                                                              ║
║ ✓ Provision Infrastructure          [COMPLETED] 5m 12s     ║
║ ✓ Install Kubernetes                 [COMPLETED] 8m 45s     ║
║ ⚙ Configure Cluster                  [IN PROGRESS] 4m 37s   ║
║   └─ Install CNI Plugin              [IN PROGRESS] 80%      ║
║ ○ Verify Deployment                  [PENDING]              ║
║                                                              ║
║ Recent Events:                                               ║
║ [10:15:23] ✓ Control plane bootstrapped                     ║
║ [10:16:41] ⚙ Installing Cilium CNI                          ║
║ [10:18:03] ⚙ Configuring network policies                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**Narrative Format**:
```
Deploying your Kubernetes cluster in production (us-west):

Step 1 of 4: Provision Infrastructure ✓ Complete (5m 12s)
  - Created VPC and subnets
  - Provisioned load balancer
  - Launched 12 worker nodes

Step 2 of 4: Install Kubernetes ✓ Complete (8m 45s)
  - Generated cluster configuration
  - Bootstrapped control plane
  - Joined worker nodes

Step 3 of 4: Configure Cluster ⚙ In Progress (4m 37s so far)
  - Installing Cilium CNI (80% complete)
  - Configuring network policies...
  - Next: Setup persistent storage

Step 4 of 4: Verify Deployment ○ Pending
  - Estimated to start in ~5 minutes

Overall: 65% complete, about 9 minutes remaining
```

### Milestone-Based Updates

```python
def generate_milestone_update(task, milestone):
    """
    Generate update when significant milestone reached
    """
    templates = {
        'started': "Started {task_name}. Estimated duration: {estimated_duration}",
        'halfway': "{task_name} is 50% complete. Everything looking good so far.",
        'blocked': "⚠️  {task_name} is blocked: {reason}. Working on resolution...",
        'completed': "✓ {task_name} completed successfully in {actual_duration}",
        'failed': "✗ {task_name} failed: {error}. Initiating rollback..."
    }

    return templates[milestone['type']].format(
        task_name=task['name'],
        **milestone
    )
```

### Error and Warning Integration

```python
def format_progress_with_issues(progress, issues):
    """
    Integrate warnings and errors into progress updates
    """
    output = f"Progress: {progress['progress_percentage']}%\n"

    # Show current status
    output += f"Current: {progress['current_task']['name']}\n"

    # Highlight issues
    if issues['errors']:
        output += "\n⚠️  ERRORS:\n"
        for error in issues['errors']:
            output += f"  - {error['message']}\n"
            output += f"    Action: {error['remediation']}\n"

    if issues['warnings']:
        output += "\n⚡ Warnings:\n"
        for warning in issues['warnings']:
            output += f"  - {warning['message']}\n"

    return output
```

## 7. Error Explanation in Plain Language

### Error Translation Framework

```python
def translate_error_to_plain_language(error, context):
    """
    Convert technical errors to user-friendly explanations
    """
    # Match error pattern
    error_pattern = match_error_pattern(error)

    # Generate explanation
    explanation = {
        'what_happened': explain_what_happened(error, context),
        'why_it_happened': explain_root_cause(error, context),
        'impact': explain_impact(error, context),
        'next_steps': suggest_remediation(error, context),
        'technical_details': error  # Keep for reference
    }

    return format_error_explanation(explanation)
```

### Error Pattern Library

```python
ERROR_PATTERNS = {
    'connection_refused': {
        'template': "I couldn't connect to {resource}",
        'common_causes': [
            "The service might not be running",
            "Firewall rules might be blocking access",
            "The resource might not exist yet"
        ],
        'suggestions': [
            "Check if {resource} is running",
            "Verify network connectivity",
            "Review firewall rules"
        ]
    },
    'authentication_failed': {
        'template': "I don't have permission to access {resource}",
        'common_causes': [
            "Credentials might be expired",
            "API token might be invalid",
            "Permissions might not be configured"
        ],
        'suggestions': [
            "Verify credentials are up to date",
            "Check IAM permissions",
            "Regenerate API tokens if needed"
        ]
    },
    'resource_not_found': {
        'template': "I couldn't find {resource}",
        'common_causes': [
            "Resource might have been deleted",
            "Name might be misspelled",
            "Looking in wrong region/namespace"
        ],
        'suggestions': [
            "Check resource name spelling",
            "Verify correct region/namespace",
            "List available resources to confirm"
        ]
    },
    'insufficient_resources': {
        'template': "Not enough {resource_type} available",
        'common_causes': [
            "Resource quota exceeded",
            "Infrastructure at capacity",
            "Cost limits reached"
        ],
        'suggestions': [
            "Increase resource quotas",
            "Scale down other services",
            "Upgrade infrastructure tier"
        ]
    }
}
```

### Error Explanation Examples

**Technical Error**:
```
Error: dial tcp 10.0.1.45:6443: connect: connection refused
```

**Plain Language Explanation**:
```
Problem: I couldn't connect to your Kubernetes cluster

What happened:
The cluster's API server at 10.0.1.45 isn't responding to connection requests.

Why this might be happening:
  1. The API server might not be running yet (if we just started it)
  2. A firewall might be blocking port 6443
  3. The control plane node might be down

Impact:
I can't proceed with cluster configuration until we can connect to the API server.

What I'm doing:
  1. Checking if the API server process is running
  2. Verifying network security rules
  3. Will retry connection in 30 seconds

What you can do:
If this persists, you can check the control plane node logs with:
  talosctl logs -n 10.0.1.45 apid

Want me to run diagnostics? (yes/no)
```

### Progressive Error Detail

```python
def format_error_with_progressive_detail(error, detail_level='simple'):
    """
    Provide error information at different detail levels
    """
    if detail_level == 'simple':
        return f"⚠️  {error['simple_message']}\n" \
               f"Next step: {error['suggested_action']}"

    elif detail_level == 'standard':
        return f"⚠️  {error['simple_message']}\n\n" \
               f"What happened: {error['what_happened']}\n" \
               f"Why: {error['likely_cause']}\n" \
               f"Next step: {error['suggested_action']}\n\n" \
               f"Type 'details' for technical information"

    elif detail_level == 'detailed':
        return f"⚠️  {error['simple_message']}\n\n" \
               f"What happened: {error['what_happened']}\n" \
               f"Root cause: {error['likely_cause']}\n" \
               f"Impact: {error['impact']}\n" \
               f"Remediation: {error['suggested_action']}\n\n" \
               f"Technical details:\n{error['stack_trace']}\n\n" \
               f"Related documentation: {error['doc_links']}"
```

## 8. Multi-Turn Conversation Handling

### Conversation State Management

```python
class ConversationState:
    def __init__(self):
        self.turns = []
        self.context = {}
        self.active_tasks = {}
        self.pending_confirmations = {}
        self.entity_history = []

    def add_turn(self, user_input, system_response):
        """Add a conversation turn"""
        turn = {
            'turn_id': len(self.turns) + 1,
            'timestamp': get_timestamp(),
            'user_input': user_input,
            'system_response': system_response,
            'extracted_entities': extract_entities(user_input),
            'intent': parse_intent(user_input, self.context)
        }
        self.turns.append(turn)
        self.update_context(turn)

    def update_context(self, turn):
        """Update conversation context"""
        # Add entities to history
        for entity in turn['extracted_entities']:
            self.entity_history.append({
                'turn': turn['turn_id'],
                'entity': entity,
                'timestamp': turn['timestamp']
            })

        # Update active context
        if turn['intent']['action'] == 'CREATE':
            self.active_tasks[turn['intent']['task_id']] = turn['intent']

    def resolve_reference(self, reference_text):
        """Resolve pronouns and references"""
        # Look back through entity history
        for entity in reversed(self.entity_history):
            if entity_matches_reference(entity, reference_text):
                return entity
        return None
```

### Multi-Turn Patterns

#### Pattern 1: Progressive Refinement

```
Turn 1 (User): "Deploy monitoring"
Turn 1 (System): "I'll deploy monitoring. Which stack would you prefer?
                  1. Prometheus + Grafana (recommended)
                  2. Datadog
                  3. Custom configuration"

Turn 2 (User): "Prometheus"
Turn 2 (System): "Great. Where should I deploy it?
                  1. Same cluster as your app (uses existing resources)
                  2. Dedicated monitoring cluster (better isolation)
                  3. Let me choose based on your setup"

Turn 3 (User): "Same cluster"
Turn 3 (System): "Perfect. Deploying Prometheus + Grafana to your existing
                  cluster with these settings:
                  - Retention: 30 days
                  - Scrape interval: 30s
                  - Storage: 50GB

                  Starting deployment now..."
```

#### Pattern 2: Interruption Handling

```
Turn 1 (User): "Deploy k8s cluster"
Turn 1 (System): "Starting deployment... (5% complete)"

Turn 2 (User): "Wait, cancel that"
Turn 2 (System): "Stopping deployment. I've paused at:
                  ✓ Created network infrastructure
                  ✗ Not started: node provisioning

                  Would you like me to:
                  1. Roll back changes (delete network)
                  2. Keep current progress (you can resume later)
                  3. Continue with different settings"

Turn 3 (User): "Roll back"
Turn 3 (System): "Rolling back... Deleted network infrastructure.
                  All clean. What would you like to do instead?"
```

#### Pattern 3: Context Switching

```
Turn 1 (User): "Deploy k8s cluster"
Turn 1 (System): "Deploying cluster... (running in background)"

Turn 2 (User): "Show me recent alerts"
Turn 2 (System): "Here are recent alerts:
                  - API latency spike (resolved)
                  - Disk space warning on node-3

                  Meanwhile, your cluster deployment is 40% complete."

Turn 3 (User): "Go back to the deployment"
Turn 3 (System): "Back to cluster deployment (now 55% complete):
                  ✓ Infrastructure provisioned
                  ⚙ Installing Kubernetes
                  ○ Configure cluster (next)"
```

### Conversation Memory Management

```python
def manage_conversation_memory(conversation_state, max_history=10):
    """
    Manage conversation memory to stay within token limits
    """
    # Keep recent turns
    recent_turns = conversation_state.turns[-max_history:]

    # Keep entities mentioned in recent turns
    recent_entities = []
    for turn in recent_turns:
        recent_entities.extend(turn['extracted_entities'])

    # Keep active tasks regardless of age
    active_task_refs = list(conversation_state.active_tasks.keys())

    # Summarize older turns
    if len(conversation_state.turns) > max_history:
        older_turns = conversation_state.turns[:-max_history]
        summary = summarize_conversation_history(older_turns)
    else:
        summary = None

    return {
        'recent_turns': recent_turns,
        'recent_entities': recent_entities,
        'active_tasks': active_task_refs,
        'history_summary': summary
    }
```

## 9. Intent-to-Contractor Mapping

### Contractor Capability Registry

```json
{
  "contractors": {
    "infrastructure-contractor": {
      "capabilities": [
        "provision_infrastructure",
        "manage_network",
        "configure_load_balancer",
        "setup_storage",
        "manage_dns"
      ],
      "resource_types": ["compute", "network", "storage", "dns"],
      "platforms": ["aws", "gcp", "azure", "bare-metal"],
      "specializations": ["terraform", "ansible"]
    },
    "talos-contractor": {
      "capabilities": [
        "install_kubernetes",
        "configure_talos",
        "bootstrap_cluster",
        "upgrade_cluster",
        "manage_nodes"
      ],
      "resource_types": ["kubernetes", "container-orchestration"],
      "platforms": ["talos-linux"],
      "specializations": ["kubernetes", "talos"]
    },
    "n8n-contractor": {
      "capabilities": [
        "create_workflow",
        "manage_automation",
        "configure_integrations",
        "schedule_tasks"
      ],
      "resource_types": ["workflow", "automation", "integration"],
      "platforms": ["n8n"],
      "specializations": ["workflow-orchestration", "automation"]
    }
  }
}
```

### Mapping Algorithm

```python
def map_intent_to_contractors(intent, contractor_registry):
    """
    Map intent to appropriate contractor(s)
    """
    required_contractors = []

    # Step 1: Direct mapping by resource type
    for resource in intent['resources']:
        matching_contractors = find_contractors_by_resource_type(
            resource['type'],
            contractor_registry
        )
        required_contractors.extend(matching_contractors)

    # Step 2: Capability-based mapping
    required_capabilities = infer_required_capabilities(intent)
    for capability in required_capabilities:
        matching_contractors = find_contractors_by_capability(
            capability,
            contractor_registry
        )
        required_contractors.extend(matching_contractors)

    # Step 3: Remove duplicates and rank
    unique_contractors = deduplicate_contractors(required_contractors)
    ranked_contractors = rank_contractors_by_relevance(
        unique_contractors,
        intent
    )

    # Step 4: Identify coordination requirements
    if len(ranked_contractors) > 1:
        coordination = identify_coordination_needs(
            ranked_contractors,
            intent
        )
    else:
        coordination = None

    return {
        'primary_contractor': ranked_contractors[0],
        'supporting_contractors': ranked_contractors[1:],
        'coordination_required': coordination
    }
```

### Intent Mapping Examples

**Example 1: Simple Mapping**
```json
{
  "intent": {
    "action": "CREATE",
    "resources": [{"type": "kubernetes", "subtype": "cluster"}]
  },
  "mapping": {
    "primary_contractor": "talos-contractor",
    "supporting_contractors": ["infrastructure-contractor"],
    "coordination_required": {
      "type": "sequential",
      "order": ["infrastructure-contractor", "talos-contractor"]
    }
  }
}
```

**Example 2: Complex Multi-Contractor Workflow**
```json
{
  "intent": {
    "action": "CREATE",
    "resources": [
      {"type": "kubernetes", "subtype": "cluster"},
      {"type": "monitoring", "subtype": "prometheus"},
      {"type": "workflow", "subtype": "backup-automation"}
    ]
  },
  "mapping": {
    "primary_contractor": "talos-contractor",
    "supporting_contractors": [
      "infrastructure-contractor",
      "monitoring-contractor",
      "n8n-contractor"
    ],
    "coordination_required": {
      "type": "dag",
      "dependencies": {
        "talos-contractor": ["infrastructure-contractor"],
        "monitoring-contractor": ["talos-contractor"],
        "n8n-contractor": ["talos-contractor"]
      }
    }
  }
}
```

### Contractor Selection Heuristics

```python
def rank_contractors_by_relevance(contractors, intent):
    """
    Rank contractors by how well they match the intent
    """
    scored_contractors = []

    for contractor in contractors:
        score = 0

        # Exact resource type match
        if contractor_handles_resource_type(contractor, intent['resources']):
            score += 10

        # Capability match
        required_caps = infer_required_capabilities(intent)
        matching_caps = count_matching_capabilities(contractor, required_caps)
        score += matching_caps * 5

        # Platform match
        if 'platform' in intent.get('parameters', {}):
            if intent['parameters']['platform'] in contractor['platforms']:
                score += 8

        # Specialization match
        for specialization in contractor['specializations']:
            if specialization in intent['original_request'].lower():
                score += 3

        scored_contractors.append({
            'contractor': contractor,
            'score': score
        })

    # Sort by score descending
    scored_contractors.sort(key=lambda x: x['score'], reverse=True)

    return [c['contractor'] for c in scored_contractors]
```

## 10. Natural Language Response Generation

### Response Templates by Intent Type

```python
RESPONSE_TEMPLATES = {
    'acknowledgment': [
        "I'll {action} {resource} for you.",
        "Starting {action} of {resource}.",
        "Got it. I'll {action} {resource}."
    ],
    'clarification': [
        "Just to confirm, you want me to {action} {resource} with {parameters}?",
        "I'll {action} {resource}. Is that correct?",
        "Before I proceed, let me verify: {summary}. Correct?"
    ],
    'progress': [
        "I'm currently {current_action}. About {percentage}% done.",
        "{current_action} is in progress ({percentage}% complete).",
        "Making progress on {current_action}. {time_remaining} remaining."
    ],
    'completion': [
        "Done! I've successfully {action} {resource}.",
        "All set. {resource} is now {state}.",
        "Completed. Your {resource} is ready."
    ],
    'error': [
        "I ran into an issue: {error}. {remediation}",
        "Something went wrong with {action}: {error}. Here's what I'm doing: {remediation}",
        "Problem: {error}. I'm working on {remediation}"
    ]
}
```

### Dynamic Response Generation

```python
def generate_response(response_type, context):
    """
    Generate natural language response
    """
    # Select appropriate template
    templates = RESPONSE_TEMPLATES[response_type]
    template = select_best_template(templates, context)

    # Fill in variables
    response = template.format(**context)

    # Add contextual enhancements
    response = add_personality(response, context)
    response = add_helpful_details(response, context)

    # Add follow-up suggestions
    if should_suggest_next_steps(context):
        response += "\n\n" + generate_next_step_suggestions(context)

    return response
```

### Personality and Tone

```python
def add_personality(response, context):
    """
    Add appropriate personality to response
    """
    # Formal for critical operations
    if context.get('operation_severity') == 'critical':
        return response  # Keep formal

    # Friendly for routine operations
    if context.get('operation_severity') == 'low':
        # Add friendly touches
        response = add_friendly_touches(response)

    # Professional but warm
    return response

FRIENDLY_TOUCHES = [
    ("I'll", "I'll happily"),
    ("Done!", "Done! "),
    ("All set.", "All set!"),
    ("Completed.", "Completed successfully!")
]
```

### Context-Aware Response Examples

**Simple Acknowledgment**:
```
User: "Deploy monitoring"
System: "I'll deploy Prometheus and Grafana monitoring to your cluster.
         This will take about 5 minutes."
```

**With Inferred Context**:
```
User: "Deploy monitoring"
[System detects existing cluster from conversation history]
System: "I'll deploy Prometheus and Grafana to your prod-k8s-west cluster.
         I'll use these settings based on your cluster size:
         - Retention: 30 days
         - Scrape interval: 30s
         - Resources: 2 CPU, 4GB RAM

         Sound good?"
```

**Progress Update**:
```
System: "I'm installing Kubernetes on your nodes. About 60% done.

         What's complete:
         ✓ Control plane is up and running
         ✓ 8 of 12 worker nodes joined

         What's next:
         ⚙ Joining remaining 4 nodes
         ○ Installing CNI plugin

         Should be done in about 5 minutes."
```

**Error with Helpful Context**:
```
System: "I hit a snag while configuring storage. The persistent volume claim
         couldn't be created because there's no storage class configured.

         I can fix this by:
         1. Installing a default storage class (recommended)
         2. Using local storage (simpler but not recommended for production)

         Want me to go with option 1?"
```

### Progressive Disclosure in Responses

```python
def generate_progressive_response(content, user_expertise):
    """
    Adjust response detail based on user expertise
    """
    if user_expertise == 'beginner':
        return {
            'summary': content['simple_explanation'],
            'details_available': True,
            'prompt': "Type 'details' for more information"
        }

    elif user_expertise == 'intermediate':
        return {
            'summary': content['standard_explanation'],
            'technical_notes': content['key_technical_points'],
            'prompt': "Type 'technical' for full details"
        }

    else:  # expert
        return {
            'summary': content['technical_explanation'],
            'commands': content['relevant_commands'],
            'links': content['documentation_links']
        }
```

## Complete Examples

### Example 1: "Build me a k8s cluster"

**Full Execution Flow**:

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: "Build me a k8s cluster"                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ INTENT PARSING                                              │
├─────────────────────────────────────────────────────────────┤
│ Action: CREATE                                              │
│ Resource: kubernetes/cluster                                │
│ Environment: [AMBIGUOUS - need to ask]                     │
│ Parameters: [INCOMPLETE - need defaults]                   │
│ Confidence: 0.75                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ AMBIGUITY RESOLUTION                                        │
├─────────────────────────────────────────────────────────────┤
│ System: "I'll build a Kubernetes cluster for you.          │
│                                                              │
│ A few quick questions:                                      │
│ 1. Environment? (production/staging/development)            │
│ 2. Size? (small: 3 nodes / medium: 6 nodes / large: 12)   │
│ 3. Region? (us-west/us-east/eu-west)                       │
│                                                              │
│ Or I can use smart defaults:                                │
│ - Environment: development (safer default)                  │
│ - Size: small (3 nodes, can scale later)                   │
│ - Region: us-west (lowest latency from your location)      │
│                                                              │
│ Proceed with defaults? (yes/customize)"                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
         User: "use defaults but make it production"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ REFINED INTENT                                              │
├─────────────────────────────────────────────────────────────┤
│ Action: CREATE                                              │
│ Resource: kubernetes/cluster                                │
│ Environment: production                                     │
│ Parameters:                                                 │
│   - size: small (3 nodes)                                   │
│   - region: us-west                                         │
│   - ha: true (auto-enabled for production)                 │
│ Confidence: 0.95                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ TASK DECOMPOSITION                                          │
├─────────────────────────────────────────────────────────────┤
│ Task Graph:                                                 │
│   1. provision_infrastructure                               │
│      - create_network (5m)                                  │
│      - create_load_balancer (3m)                            │
│      - provision_nodes (8m)                                 │
│                                                              │
│   2. install_kubernetes [depends: 1]                        │
│      - generate_config (2m)                                 │
│      - bootstrap_control_plane (5m)                         │
│      - join_workers (6m)                                    │
│                                                              │
│   3. configure_cluster [depends: 2]                         │
│      - install_cni (4m)                                     │
│      - configure_storage (3m)                               │
│      - setup_ingress (3m)                                   │
│                                                              │
│   4. verify_deployment [depends: 3]                         │
│      - health_checks (2m)                                   │
│      - smoke_tests (3m)                                     │
│                                                              │
│ Estimated Total: ~44 minutes                                │
│ Estimated Tokens: 18,000                                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ CONTRACTOR MAPPING                                          │
├─────────────────────────────────────────────────────────────┤
│ Task 1 → infrastructure-contractor                          │
│ Task 2 → talos-contractor                                   │
│ Task 3 → infrastructure-contractor + talos-contractor       │
│ Task 4 → monitoring-contractor                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ CONFIRMATION (Production = Destructive)                     │
├─────────────────────────────────────────────────────────────┤
│ System: "Ready to build your production Kubernetes cluster │
│                                                              │
│ Configuration:                                              │
│ - Environment: Production                                   │
│ - Region: us-west                                           │
│ - Nodes: 3 (1 control plane, 2 workers)                    │
│ - High Availability: Enabled                                │
│ - Estimated time: ~44 minutes                               │
│ - Estimated cost: $X/month                                  │
│                                                              │
│ This will create production infrastructure.                 │
│                                                              │
│ Proceed? (yes/no/customize)"                                │
└─────────────────────────────────────────────────────────────┘
                           ↓
                      User: "yes"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ EXECUTION WITH PROGRESS UPDATES                             │
├─────────────────────────────────────────────────────────────┤
│ [00:00] Starting deployment of prod-k8s-west                │
│                                                              │
│ [00:05] ✓ Created VPC and subnets                          │
│ [00:08] ✓ Configured load balancer                         │
│ [00:16] ✓ Provisioned 3 nodes                              │
│                                                              │
│ Progress: [███████░░░░░░░░░] 35% (~28m remaining)          │
│                                                              │
│ [00:18] ⚙ Generating cluster configuration                 │
│ [00:20] ⚙ Bootstrapping control plane                      │
│ [00:25] ⚙ Joining worker nodes                             │
│                                                              │
│ Progress: [██████████████░░] 65% (~15m remaining)          │
│                                                              │
│ [00:31] ✓ Kubernetes installed successfully                │
│ [00:35] ⚙ Installing Cilium CNI                            │
│ [00:38] ⚙ Configuring storage classes                      │
│                                                              │
│ Progress: [████████████████████] 90% (~4m remaining)       │
│                                                              │
│ [00:42] ✓ Cluster configuration complete                   │
│ [00:44] ⚙ Running health checks                            │
│ [00:46] ✓ All checks passed                                │
│                                                              │
│ ────────────────────────────────────────────────────────    │
│ ✓ SUCCESS                                                   │
│ ────────────────────────────────────────────────────────    │
│                                                              │
│ Your Kubernetes cluster is ready!                           │
│                                                              │
│ Cluster: prod-k8s-west                                      │
│ API: https://10.0.1.45:6443                                │
│ Nodes: 3 (all healthy)                                      │
│                                                              │
│ Next steps:                                                 │
│ 1. Deploy your applications                                 │
│ 2. Setup monitoring (I can do this - just ask!)            │
│ 3. Configure backups                                        │
│                                                              │
│ Total time: 46 minutes                                      │
└─────────────────────────────────────────────────────────────┘
```

### Example 2: "Deploy monitoring"

**With Conversational Context**:

```
[Previous context: User just deployed k8s cluster prod-k8s-west]

User: "Deploy monitoring"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ INTENT PARSING WITH CONTEXT                                 │
├─────────────────────────────────────────────────────────────┤
│ Action: CREATE                                              │
│ Resource: monitoring/stack                                  │
│ Context Resolution:                                         │
│   - Target: prod-k8s-west (from conversation history)      │
│   - Environment: production (inherited)                     │
│   - Stack: prometheus+grafana (default)                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ SMART DEFAULTS WITH CONTEXT                                 │
├─────────────────────────────────────────────────────────────┤
│ System: "I'll deploy Prometheus and Grafana monitoring to  │
│ your prod-k8s-west cluster.                                 │
│                                                              │
│ I've configured it based on your cluster size:              │
│ - Retention: 30 days                                        │
│ - Scrape interval: 30 seconds                               │
│ - Storage: 50GB                                             │
│ - Auto-discovery: Enabled for all pods                      │
│                                                              │
│ I'll also configure these default dashboards:               │
│ - Cluster overview                                          │
│ - Node metrics                                              │
│ - Pod resources                                             │
│                                                              │
│ Proceed? (yes/customize)"                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
                      User: "yes"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ EXECUTION                                                   │
├─────────────────────────────────────────────────────────────┤
│ [00:00] Installing Prometheus...                            │
│ [00:03] Installing Grafana...                               │
│ [00:06] Configuring auto-discovery...                       │
│ [00:08] Importing dashboards...                             │
│ [00:10] ✓ Monitoring deployed successfully                 │
│                                                              │
│ Access your dashboards:                                     │
│ Grafana: https://grafana.prod-k8s-west.local               │
│ Prometheus: https://prometheus.prod-k8s-west.local         │
│                                                              │
│ Default credentials sent to your email.                     │
└─────────────────────────────────────────────────────────────┘
```

### Example 3: "Fix the broken service"

**Diagnostic and Remediation Flow**:

```
User: "Fix the broken service"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ AMBIGUITY DETECTION                                         │
├─────────────────────────────────────────────────────────────┤
│ Ambiguities:                                                │
│ 1. Which service? (multiple services detected)             │
│ 2. What kind of broken? (crash/slow/unreachable)           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ INTELLIGENT CLARIFICATION                                   │
├─────────────────────────────────────────────────────────────┤
│ System: "I can help fix that. I've checked recent alerts   │
│ and found issues with these services:                       │
│                                                              │
│ 1. api-service: High error rate (500s)                     │
│ 2. cache-service: Connection timeouts                       │
│ 3. db-service: Slow queries                                │
│                                                              │
│ Which one should I investigate? (or 'all' for all of them)"│
└─────────────────────────────────────────────────────────────┘
                           ↓
              User: "api-service"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ DIAGNOSTIC PHASE                                            │
├─────────────────────────────────────────────────────────────┤
│ System: "Investigating api-service..."                      │
│                                                              │
│ [00:05] Checking service logs                               │
│ [00:08] Analyzing error patterns                            │
│ [00:12] Reviewing recent deployments                        │
│ [00:15] Checking dependencies                               │
│                                                              │
│ ──────────────────────────────────────────────────────      │
│ DIAGNOSIS                                                   │
│ ──────────────────────────────────────────────────────      │
│                                                              │
│ Problem found: api-service is running out of memory         │
│                                                              │
│ What I found:                                               │
│ - Memory usage: 95% (limit: 512MB)                         │
│ - OOMKilled events: 12 in last hour                        │
│ - Memory leak in new deployment (v2.3.1)                   │
│                                                              │
│ Root cause:                                                 │
│ The v2.3.1 deployment from 2 hours ago has a memory leak.  │
│ The service is restarting every 5-10 minutes.              │
│                                                              │
│ I can fix this by:                                          │
│ 1. Rollback to v2.3.0 (quick, safe)                        │
│ 2. Increase memory limit to 1GB (temporary workaround)     │
│ 3. Both: rollback + increase limit                         │
│                                                              │
│ Recommendation: Option 1 (rollback)                         │
│                                                              │
│ What should I do? (1/2/3)"                                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
                       User: "1"
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ REMEDIATION                                                 │
├─────────────────────────────────────────────────────────────┤
│ System: "Rolling back api-service to v2.3.0..."            │
│                                                              │
│ [00:00] Scaling up v2.3.0 deployment                        │
│ [00:15] New pods healthy                                    │
│ [00:20] Shifting traffic to v2.3.0                          │
│ [00:25] Scaling down v2.3.1                                 │
│ [00:30] Monitoring error rate...                            │
│                                                              │
│ ✓ Rollback complete!                                        │
│                                                              │
│ Status:                                                     │
│ - Error rate: 0.1% (was 45%)                               │
│ - Memory usage: 280MB (stable)                              │
│ - Response time: 95ms avg                                   │
│ - No restarts in last 5 minutes                             │
│                                                              │
│ The service is healthy again.                               │
│                                                              │
│ Next steps:                                                 │
│ - Investigate memory leak in v2.3.1                         │
│ - Update deployment with fix                                │
│ - Re-deploy when ready                                      │
│                                                              │
│ Want me to create a ticket for the memory leak              │
│ investigation? (yes/no)"                                    │
└─────────────────────────────────────────────────────────────┘
```

## Prompt Engineering Patterns

### System Prompt Structure

```
You are the Natural Language Interface for the cortex automation system.

CORE CAPABILITIES:
- Parse natural language into structured intents
- Decompose complex tasks into executable workflows
- Coordinate multiple contractors
- Provide clear progress updates
- Explain errors in plain language
- Handle multi-turn conversations

PRINCIPLES:
1. Always confirm destructive operations
2. Use intelligent defaults but ask when ambiguous
3. Explain technical issues in user-friendly language
4. Provide actionable next steps
5. Learn from conversation context
6. Be proactive about potential issues

TONE:
- Professional but friendly
- Clear and concise
- Helpful and patient
- Technical when needed, simple when possible

CONTEXT AWARENESS:
You have access to:
- Conversation history
- System state
- Available contractors
- Resource inventory
- Recent incidents
```

### Intent Parsing Prompt

```
Parse the following user request into a structured intent:

User request: "{user_input}"

Context:
- Previous conversation: {conversation_summary}
- Active tasks: {active_tasks}
- System state: {system_state_summary}

Generate:
1. Action classification (CREATE/READ/UPDATE/DELETE/DIAGNOSE/OPTIMIZE)
2. Resource identification
3. Parameter extraction
4. Confidence score
5. Ambiguities detected
6. Suggested clarifications (if needed)

Format as JSON.
```

### Task Decomposition Prompt

```
Decompose this intent into an executable task graph:

Intent: {structured_intent}

Available contractors: {contractor_list}

Generate:
1. Task sequence (with dependencies)
2. Contractor assignments
3. Estimated durations
4. Resource requirements
5. Critical path
6. Parallel execution opportunities

Consider:
- Task dependencies
- Resource constraints
- Token budgets
- Failure scenarios
```

### Error Explanation Prompt

```
Translate this technical error into plain language:

Error: {error_details}
Context: {operation_context}

Generate:
1. Simple explanation (what happened)
2. Root cause (why it happened)
3. Impact assessment
4. Suggested remediation
5. User action items
6. Progressive detail levels (simple/standard/detailed)

Make it:
- Clear and non-technical
- Actionable
- Empathetic
- Solution-focused
```

## Best Practices

### 1. Always Maintain Context
- Track conversation history
- Resolve references and pronouns
- Remember user preferences
- Learn from past interactions

### 2. Be Proactive
- Suggest next steps
- Warn about potential issues
- Offer optimizations
- Provide relevant information

### 3. Confirm When Uncertain
- Ask clarifying questions
- Provide intelligent defaults
- Show confidence levels
- Explain reasoning

### 4. Communicate Clearly
- Use plain language
- Provide progress updates
- Explain technical concepts
- Offer different detail levels

### 5. Handle Errors Gracefully
- Explain what went wrong
- Suggest solutions
- Provide recovery options
- Learn from failures

## Integration Points

- **Coordinator Master**: Receives tasks from NLI
- **All Contractors**: Execute decomposed tasks
- **Monitoring**: Provides system state for context
- **Knowledge Base**: Stores interaction patterns
- **Dashboard**: Displays execution progress

## Metrics to Track

- Intent parsing accuracy
- Ambiguity resolution success rate
- Task decomposition efficiency
- User satisfaction scores
- Time to task completion
- Error explanation clarity

## Future Enhancements

- Voice interface support
- Multi-language support
- Learning user communication styles
- Predictive intent classification
- Automated workflow suggestions
- Context-aware defaults refinement
