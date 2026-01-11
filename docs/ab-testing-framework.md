# A/B Testing Framework

**Version:** 1.0
**Last Updated:** 2025-11-27

## Overview

The A/B Testing Framework enables controlled experiments with different master versions, prompts, and configurations in Cortex. It provides statistical rigor for evaluating changes before full deployment.

## Architecture

```
coordination/
├── ab-tests/           # Test configurations
│   ├── test-001.json   # Individual test config
│   └── results/        # Test results
│       └── test-001-results.jsonl
scripts/lib/
└── ab-testing.sh       # A/B testing library
```

## Quick Start

### 1. Initialize A/B Testing

```bash
source scripts/lib/ab-testing.sh
init_ab_testing
```

### 2. Create A/B Test

```bash
# Test two versions of security-master
create_ab_test "security-v1-vs-v2" \
    "security-master" \
    "v1.0.0" \
    "v1.1.0" \
    50  # 50/50 traffic split
```

### 3. Get Variant for Task

When processing a task, determine which variant to use:

```bash
variant=$(get_variant "security-v1-vs-v2" "task-001")
echo "Using variant: $variant"  # Returns "a" or "b"
```

### 4. Record Results

After task completion:

```bash
record_ab_result "security-v1-vs-v2" \
    "task-001" \
    "a" \
    "completed" \
    45 \
    4.5  # quality score 1-5
```

### 5. View Results

```bash
# Get summary
get_ab_summary "security-v1-vs-v2"

# List all tests
list_ab_tests

# List only active tests
list_ab_tests "active"
```

### 6. Stop Test and Declare Winner

```bash
stop_ab_test "security-v1-vs-v2" "b"
```

## Test Configuration

A/B test configuration JSON:

```json
{
  "test_id": "security-v1-vs-v2",
  "master": "security-master",
  "variants": {
    "a": {
      "name": "v1.0.0",
      "traffic_percentage": 50
    },
    "b": {
      "name": "v1.1.0",
      "traffic_percentage": 50
    }
  },
  "status": "active",
  "created_at": "2025-11-27T10:00:00-0600",
  "metrics": {
    "tasks_assigned": {"a": 0, "b": 0},
    "tasks_completed": {"a": 0, "b": 0},
    "tasks_failed": {"a": 0, "b": 0},
    "avg_duration": {"a": 0, "b": 0},
    "avg_quality_score": {"a": 0, "b": 0}
  }
}
```

## Traffic Splitting

Traffic is split deterministically using task ID hashing:

- Same task ID → always same variant
- Ensures reproducibility
- No randomness across runs
- Respects configured traffic percentages

## Use Cases

### 1. Version Testing

Test new master version against current champion:

```bash
create_ab_test "dev-master-upgrade" \
    "development-master" \
    "v1.0.0" \  # Current champion
    "v1.2.0" \  # New candidate
    80  # 80% champion, 20% candidate (gradual rollout)
```

### 2. Prompt Testing

Test different system prompts:

```bash
create_ab_test "security-prompt-test" \
    "security-master" \
    "prompt-v1" \
    "prompt-v2-more-context" \
    50
```

### 3. Configuration Testing

Test different routing configurations:

```bash
create_ab_test "routing-config-test" \
    "coordinator-master" \
    "config-conservative" \
    "config-aggressive" \
    50
```

## Metrics Tracked

For each variant:

- **Tasks Assigned**: Total tasks routed to variant
- **Tasks Completed**: Successfully completed tasks
- **Tasks Failed**: Failed tasks
- **Completion Rate**: Percentage of successful completions
- **Average Duration**: Mean task duration in seconds
- **Average Quality Score**: Mean quality score (1-5)

## Statistical Significance

For reliable results:

- Minimum 30 tasks per variant
- Run for at least 24 hours
- Consider external factors (time of day, task types)
- Use evaluation framework for quality assessment

## Integration with Master Selection

```bash
# In master spawning logic
if is_ab_test_active "$master_name"; then
    variant=$(get_variant "$test_name" "$task_id")

    if [[ "$variant" == "a" ]]; then
        version=$(get_variant_a_version "$test_name")
    else
        version=$(get_variant_b_version "$test_name")
    fi
else
    # Use champion version
    version=$(get_champion_version "$master_name")
fi
```

## Best Practices

1. **Start Small**: Begin with 90/10 or 80/20 splits for new versions
2. **Monitor Closely**: Check metrics frequently in first hour
3. **Have Rollback Plan**: Keep ability to stop test quickly
4. **Test One Thing**: Vary only one parameter (version, prompt, or config)
5. **Document Hypothesis**: Record what you expect to improve
6. **Use Evaluation Framework**: Run evaluation on both variants

## Example Workflow

```bash
# 1. Create test
create_ab_test "security-cve-scan-v2" \
    "security-master" \
    "v1.0.0" \
    "v2.0.0" \
    70  # Conservative 70/30 split

# 2. Let it run (collect >= 30 samples per variant)

# 3. Check results
get_ab_summary "security-cve-scan-v2"

# Output:
# {
#   "variants": {
#     "a": {
#       "name": "v1.0.0",
#       "completion_rate": 92.5,
#       "avg_duration": 45.2,
#       "avg_quality": 4.1
#     },
#     "b": {
#       "name": "v2.0.0",
#       "completion_rate": 95.8,
#       "avg_duration": 38.7,
#       "avg_quality": 4.4
#     }
#   }
# }

# 4. Variant B wins! (higher completion rate, faster, better quality)
stop_ab_test "security-cve-scan-v2" "b"

# 5. Promote winner to champion
./scripts/promote-master.sh security-master v2.0.0
```

## Troubleshooting

### Test Not Assigning Traffic

- Check test status is "active"
- Verify test_name matches exactly
- Ensure test file exists in coordination/ab-tests/

### Metrics Not Updating

- Verify record_ab_result is called after task completion
- Check write permissions on results directory
- Validate JSON syntax in test configuration

### Uneven Traffic Split

- Hashing is deterministic but may not be exactly even for small samples
- Need 100+ tasks for accurate distribution
- Check traffic_percentage configuration

## Future Enhancements

- Multi-variant testing (A/B/C/D)
- Automatic winner determination (Bayesian optimization)
- Integration with monitoring alerts
- Scheduled test rotation
- Multi-dimensional experiments (version + prompt + config)
