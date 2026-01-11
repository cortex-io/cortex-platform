# Task Lineage Integration Points

Complete documentation of where to integrate lineage tracking throughout the cortex system.

## Overview

The task lineage tracking system provides complete observability of task lifecycle from creation to completion. This document identifies all integration points where lineage logging should be added.

**Integration Pattern**:
```bash
# Add to script headers
source "$SCRIPT_DIR/lib/lineage.sh"

# Log events at key lifecycle points
log_task_created "$task_id" "$creator_id" "$event_data_json"
log_worker_spawned "$task_id" "$master_id" "$worker_id" "$worker_type"
```

---

## Integration Points by Category

### 1. Task Creation & Assignment (7 integration points)

#### 1.1 scripts/create-task.sh
**Location**: After task is created and written to task queue
**Event Type**: `task_created`
**Priority**: HIGH
**Integration**:
```bash
# After: jq ".tasks += [$NEW_TASK]" coordination/task-queue.json
source "$SCRIPT_DIR/lib/lineage.sh"
event_data=$(jq -n --arg prio "$PRIORITY" --arg type "$TASK_TYPE" \
    '{priority: $prio, type: $type}')
log_task_created "$TASK_ID" "${CORTEX_PRINCIPAL:-user}" "$event_data"
```

#### 1.2 scripts/create-task-enhanced.sh
**Location**: After enhanced task creation
**Event Type**: `task_created`
**Priority**: HIGH
**Integration**: Same as 1.1

#### 1.3 scripts/wizards/create-task.sh
**Location**: After wizard completes task creation
**Event Type**: `task_created`
**Priority**: MEDIUM

#### 1.4 scripts/run-coordinator-master.sh
**Location**: When coordinator assigns task to specialist master
**Event Type**: `task_assigned`
**Priority**: HIGH
**Integration**:
```bash
# After routing decision is made
log_task_assigned "$task_id" "coordinator-master" "$assigned_master" "$priority"
```

#### 1.5 coordination/masters/coordinator/lib/moe-router.sh
**Location**: In routing decision function after master selection
**Event Type**: `task_assigned`
**Priority**: HIGH
**Function**: `route_task_to_expert()` or similar

#### 1.6 coordination/masters/coordinator/lib/routing-cascade.sh
**Location**: In hybrid routing cascade after assignment
**Event Type**: `task_assigned`
**Priority**: MEDIUM

#### 1.7 scripts/task-orchestrator-daemon.sh
**Location**: When orchestrator assigns tasks
**Event Type**: `task_assigned`
**Priority**: MEDIUM

---

### 2. Task Execution Start (5 integration points)

#### 2.1 scripts/run-development-master.sh
**Location**: When development master starts task execution
**Event Type**: `task_started`
**Priority**: HIGH
**Integration**:
```bash
# After accepting task from coordinator
log_task_started "$task_id" "development-master" '{}'
```

#### 2.2 scripts/run-security-master.sh
**Location**: When security master starts task
**Event Type**: `task_started`
**Priority**: HIGH

#### 2.3 scripts/run-inventory-master.sh
**Location**: When inventory master starts task
**Event Type**: `task_started`
**Priority**: MEDIUM

#### 2.4 scripts/run-cicd-master.sh
**Location**: When CI/CD master starts task
**Event Type**: `task_started`
**Priority**: MEDIUM

#### 2.5 coordination/masters/coordinator/lib/routing-integration.sh
**Location**: After successful task handoff
**Event Type**: `task_started`
**Priority**: MEDIUM

---

### 3. Worker Spawning (4 integration points)

#### 3.1 scripts/spawn-worker.sh
**Location**: After worker spec is created and written
**Event Type**: `worker_spawned`
**Priority**: CRITICAL
**Integration**:
```bash
# After: Write worker spec to coordination/worker-specs/
source "$SCRIPT_DIR/lib/lineage.sh"
event_data=$(jq -n --arg prio "$PRIORITY" \
    '{priority: $prio, token_budget: $TOKEN_BUDGET}')
log_worker_spawned "$TASK_ID" "$MASTER_AGENT" "$WORKER_ID" "$WORKER_TYPE" "$event_data"
```

#### 3.2 scripts/wizards/create-worker.sh
**Location**: After wizard creates worker
**Event Type**: `worker_spawned`
**Priority**: MEDIUM

#### 3.3 scripts/worker-daemon.sh
**Location**: When daemon spawns workers
**Event Type**: `worker_spawned`
**Priority**: MEDIUM

---

### 4. Worker Execution (6 integration points)

#### 4.1 scripts/start-worker.sh
**Location**: When worker actually begins execution
**Event Type**: `worker_started`
**Priority**: HIGH
**Integration**:
```bash
# At start of worker execution
log_worker_started "$TASK_ID" "$WORKER_ID" "$WORKER_TYPE" '{}'
```

#### 4.2 Worker Progress Updates
**Location**: Within worker execution (if progress tracking exists)
**Event Type**: `worker_progress`
**Priority**: LOW
**Note**: Optional - only if workers report progress

#### 4.3 scripts/aggregate-worker-results.sh
**Location**: When aggregating worker completion
**Event Type**: `worker_completed`
**Priority**: HIGH
**Integration**:
```bash
# For each completed worker
event_data=$(jq -n --argjson tokens "$token_usage" --argjson dur "$duration" \
    '{token_usage: $tokens, duration_ms: $dur, deliverables: $deliverables}')
log_worker_completed "$task_id" "$worker_id" "success" "$event_data"
```

#### 4.4 Worker Failure Handlers
**Location**: Any script that handles worker failures
**Event Type**: `worker_failed`
**Priority**: HIGH
**Integration**:
```bash
# On worker failure
log_worker_failed "$task_id" "$worker_id" "$error_message" "$event_data"
```

#### 4.5 scripts/archive-failed-workers.sh
**Location**: When archiving failed workers
**Event Type**: `worker_failed` (if not already logged)
**Priority**: MEDIUM

#### 4.6 scripts/cleanup-zombie-workers.sh
**Location**: When zombie worker is detected
**Event Type**: `worker_failed`
**Priority**: LOW
**Note**: Log as failed with reason "zombie_timeout"

---

### 5. Task Completion (4 integration points)

#### 5.1 scripts/task-completion-hook.sh
**Location**: When task completes successfully
**Event Type**: `task_completed`
**Priority**: CRITICAL
**Integration**:
```bash
# At task completion
event_data=$(jq -n \
    --argjson deliverables "$deliverables_array" \
    --argjson tokens "$total_tokens" \
    --argjson dur "$duration_ms" \
    '{completion_status: "success", deliverables: $deliverables,
      token_usage: {total_tokens: $tokens}, duration_ms: $dur}')
log_task_completed "$task_id" "$master_id" "success" "$event_data"
```

#### 5.2 Master Completion Handlers
**Location**: In each master when task finishes
**Event Type**: `task_completed` or `task_failed`
**Priority**: HIGH
**Scripts**:
- run-development-master.sh
- run-security-master.sh
- run-inventory-master.sh
- run-cicd-master.sh

#### 5.3 Task Failure Scenarios
**Location**: Anywhere tasks fail
**Event Type**: `task_failed`
**Priority**: HIGH
**Integration**:
```bash
log_task_failed "$task_id" "$master_id" "$failure_reason" "$event_data"
```

#### 5.4 scripts/coordinate-task-git.sh
**Location**: After git operations complete for task
**Event Type**: `task_completed` (for git-related tasks)
**Priority**: MEDIUM

---

### 6. Task State Changes (5 integration points)

#### 6.1 Task Blocking
**Location**: When task encounters blocking dependency
**Event Type**: `task_blocked`
**Priority**: MEDIUM
**Integration**:
```bash
log_task_blocked "$task_id" "$master_id" "Waiting for dependency: $dep_task_id" '{}'
```

#### 6.2 Task Unblocking
**Location**: When blocking dependency resolves
**Event Type**: `task_unblocked`
**Priority**: MEDIUM
**Integration**:
```bash
log_task_unblocked "$task_id" "$master_id" "Dependency completed: $dep_task_id" '{}'
```

#### 6.3 Task Reassignment
**Location**: When task is reassigned to different master
**Event Type**: `task_reassigned`
**Priority**: MEDIUM
**Integration**:
```bash
log_task_reassigned "$task_id" "$from_master" "$to_master" "$reason" '{}'
```

#### 6.4 Task Escalation
**Location**: When task needs manual intervention
**Event Type**: `task_escalated`
**Priority**: HIGH
**Integration**:
```bash
log_task_escalated "$task_id" "$master_id" "Requires manual review" '{}'
```

#### 6.5 Task Cancellation
**Location**: When user or system cancels task
**Event Type**: `task_cancelled`
**Priority**: MEDIUM
**Integration**:
```bash
log_task_cancelled "$task_id" "coordinator-master" "User requested cancellation" '{}'
```

---

### 7. Handoff Management (6 integration points)

#### 7.1 scripts/handoff-processor-daemon.sh
**Location**: When handoff is created
**Event Type**: `handoff_created`
**Priority**: HIGH
**Integration**:
```bash
# When creating handoff between masters
log_handoff_created "$task_id" "$handoff_id" "$from_master" "$to_master" '{}'
```

#### 7.2 Handoff Acceptance
**Location**: When destination master accepts handoff
**Event Type**: `handoff_accepted`
**Priority**: HIGH
**Integration**:
```bash
log_handoff_accepted "$task_id" "$handoff_id" "$accepting_master" '{}'
```

#### 7.3 Handoff Completion
**Location**: When handoff work is finished
**Event Type**: `handoff_completed`
**Priority**: HIGH
**Integration**:
```bash
log_handoff_completed "$task_id" "$handoff_id" "$completing_master" "$event_data"
```

#### 7.4 Development → CI/CD Handoffs
**Location**: In development master when handing to CI/CD
**Event Type**: `handoff_created`
**Priority**: MEDIUM

#### 7.5 Security → Development Handoffs
**Location**: In security master after scan completion
**Event Type**: `handoff_created`
**Priority**: MEDIUM

#### 7.6 Coordinator → Specialist Handoffs
**Location**: In coordinator when delegating to specialists
**Event Type**: `handoff_created`
**Priority**: MEDIUM

---

## Integration Priority Matrix

| Priority | Count | Scripts | Notes |
|----------|-------|---------|-------|
| CRITICAL | 2 | spawn-worker.sh, task-completion-hook.sh | Must implement first |
| HIGH | 18 | Task creation, assignment, completion, workers | Core lifecycle |
| MEDIUM | 16 | Handoffs, state changes, specialist masters | Important for complete picture |
| LOW | 3 | Progress updates, zombie cleanup | Nice to have |

**Total Integration Points: 39**

---

## Implementation Strategy

### Phase 1: Core Lifecycle (Week 1)
1. Task creation (scripts/create-task*.sh) - 3 points
2. Worker spawning (scripts/spawn-worker.sh) - 1 point
3. Task completion (scripts/task-completion-hook.sh) - 1 point
4. Worker completion (aggregate-worker-results.sh) - 1 point

**Deliverable**: Basic task-to-worker lifecycle tracking

### Phase 2: Master Integration (Week 1-2)
1. Coordinator task assignment - 3 points
2. Specialist master task starts - 4 points
3. Task completion in masters - 4 points

**Deliverable**: Complete master-level observability

### Phase 3: Advanced Events (Week 2)
1. Handoff lifecycle - 6 points
2. Task state changes - 5 points
3. Worker failures - 3 points

**Deliverable**: Full event coverage

### Phase 4: Optional Enhancements (Week 3)
1. Worker progress tracking - 1 point
2. Zombie worker detection - 1 point
3. Additional edge cases - 2 points

**Deliverable**: Complete observability system

---

## Testing Checklist

For each integration point:
- [ ] Lineage event is logged at correct time
- [ ] Event contains all required fields
- [ ] Event data is accurate and complete
- [ ] Parent lineage ID is set when applicable
- [ ] Query tools can retrieve the event
- [ ] Timeline shows event in correct order
- [ ] No performance degradation

---

## Validation Commands

After integration, validate with:

```bash
# Test task creation
./scripts/create-task.sh --title "Test" --type development --priority high
./scripts/query-lineage.sh --task task-XXX

# Test worker spawning
./scripts/spawn-worker.sh --type scan-worker --task-id task-XXX --master development-master
./scripts/query-lineage.sh --type worker_spawned

# Test timeline
./scripts/query-lineage.sh --timeline task-XXX

# Test statistics
./scripts/query-lineage.sh --stats

# Test worker tracking
./scripts/query-lineage.sh --workers task-XXX
```

---

## Performance Considerations

1. **JSONL Append**: Lineage uses append-only JSONL for fast writes
2. **Minimal Overhead**: Each log call is ~5ms
3. **No Blocking**: Writes don't block task execution
4. **Archive Strategy**: Daily files prevent unbounded growth
5. **Query Optimization**: Use jq streaming for large datasets

**Expected overhead per task**: 10-50ms total (across all events)

---

## Dependencies

All integrations require:
1. `scripts/lib/lineage.sh` sourced
2. `jq` available on system
3. `CORTEX_HOME` environment variable set
4. Write permissions to `coordination/lineage/`

Optional for enhanced tracking:
1. `CORTEX_SESSION_ID` for session grouping
2. `CORTEX_TRACE_ID` for distributed tracing
3. `CORTEX_PRINCIPAL` for actor attribution

---

## Example Integration

**Before**:
```bash
# scripts/spawn-worker.sh (line ~400)
echo "$WORKER_SPEC" > "coordination/worker-specs/${WORKER_ID}.json"
print_success "Worker spec created: $WORKER_ID"
```

**After**:
```bash
# scripts/spawn-worker.sh (line ~400)
echo "$WORKER_SPEC" > "coordination/worker-specs/${WORKER_ID}.json"

# Log lineage event
source "$SCRIPT_DIR/lib/lineage.sh"
event_data=$(jq -n \
    --arg prio "$PRIORITY" \
    --argjson budget "$TOKEN_BUDGET" \
    '{priority: $prio, token_budget: $budget}')
log_worker_spawned "$TASK_ID" "$MASTER_AGENT" "$WORKER_ID" "$WORKER_TYPE" "$event_data"

print_success "Worker spec created: $WORKER_ID"
```

---

## Maintenance

1. **Archive old lineage data**: Monthly rotation to `coordination/lineage/archive/`
2. **Monitor file sizes**: Alert if task-lineage.jsonl > 100MB
3. **Validate schema compliance**: Weekly validation with JSON schema
4. **Performance monitoring**: Track log write times
5. **Query optimization**: Create indices if needed

---

## Future Enhancements

1. **GraphQL API**: Query lineage via GraphQL
2. **Real-time streaming**: WebSocket for live events
3. **Visualization**: D3.js timeline visualization
4. **Alerting**: Alert on anomalous patterns
5. **ML Analysis**: Predict task durations from lineage
6. **Cross-task correlation**: Link related task lineages
7. **Distributed tracing**: OpenTelemetry integration

---

## Contact

For questions about lineage integration:
- Documentation: `coordination/lineage/README.md`
- Schema: `coordination/schemas/task-lineage.schema.json`
- Library: `scripts/lib/lineage.sh`
- Query tool: `scripts/query-lineage.sh`
