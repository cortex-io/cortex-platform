# Pre-Deployment Testing Framework

Comprehensive testing framework to ensure safe deployments of Cortex masters and workers to production.

## Overview

The pre-deployment testing framework validates system readiness through four test stages:

1. **Readiness Checks** - Deployment gates (configuration, dependencies, resources)
2. **Smoke Tests** - Quick sanity checks (<2 minutes)
3. **Integration Tests** - End-to-end scenarios (8+ test cases)
4. **Load Tests** - Performance validation under concurrent load

## Quick Start

```bash
# Run all validation stages
./scripts/validate-deployment.sh

# Run with options
./scripts/validate-deployment.sh --stop-on-failure
./scripts/validate-deployment.sh --skip-load-tests

# Run individual test suites
./testing/pre-deployment/readiness-checks.sh
./testing/pre-deployment/smoke-tests.sh
CORTEX_ENV=staging ./testing/pre-deployment/integration-tests.sh
CORTEX_ENV=staging ./testing/pre-deployment/load-tests.sh
```

## Directory Structure

```
testing/
├── pre-deployment/
│   ├── readiness-checks.sh      # Deployment gates
│   ├── integration-tests.sh     # End-to-end scenarios
│   ├── load-tests.sh            # Performance validation
│   ├── smoke-tests.sh           # Quick sanity checks
│   └── test-suites/
│       ├── master-tests/        # Master-specific tests
│       ├── worker-tests/        # Worker-specific tests
│       └── daemon-tests/        # Daemon tests
├── fixtures/
│   ├── sample-tasks.json        # Sample task payloads
│   ├── sample-workers.json      # Sample worker specs
│   └── sample-routing-queries.json  # Routing test data
└── pre-deployment.md            # This documentation
```

## Test Stages

### Stage 1: Readiness Checks

**Purpose**: Validate deployment gates before proceeding

**Duration**: ~30 seconds

**Checks**:
- ✓ Configuration files present (masters, lineage, governance)
- ✓ Dependencies available (jq, python3, git, bc)
- ✓ Resource availability (disk space, API key, directories)
- ✓ JSON schema validation (all JSON files valid)
- ✓ Master prompts available
- ✓ Worker type registry
- ✓ Routing system components (5 layers)
- ✓ Lineage and tracing setup
- ✓ Governance and security components
- ✓ Version consistency (git status)

**Exit Codes**:
- `0` - All checks passed, deployment ready
- `1` - One or more checks failed, not ready

**Example**:
```bash
./testing/pre-deployment/readiness-checks.sh
```

**Output**:
```
╔════════════════════════════════════════╗
║  Cortex Pre-Deployment Readiness Check ║
╔════════════════════════════════════════╗

=========================================
1. Configuration Files
=========================================
✓ Directory exists: coordination/masters/coordinator
✓ Directory exists: coordination/masters/development
...

READINESS CHECK SUMMARY
=========================================
Passed:   42
Failed:   0
Warnings: 3

✓ DEPLOYMENT READY
```

### Stage 2: Smoke Tests

**Purpose**: Quick validation suite for rapid feedback

**Duration**: <2 minutes

**Target Time**: <120 seconds

**Tests**:
1. ✓ Can spawn a worker
2. ✓ Can route a task
3. ✓ Can log to lineage
4. ✓ Can emit metrics
5. ✓ File system permissions
6. ✓ Essential commands available
7. ✓ Configuration files present
8. ✓ Basic task flow

**Example**:
```bash
./testing/pre-deployment/smoke-tests.sh
```

**When to Use**:
- After code changes
- Before running full validation
- Quick sanity check during development

### Stage 3: Integration Tests

**Purpose**: End-to-end testing of Cortex workflows

**Duration**: <5 minutes

**Environment**: Staging (isolated from production)

**Test Cases**:
1. ✓ Coordinator → Master → Worker flow
2. ✓ Task lifecycle (queued → assigned → in_progress → completed)
3. ✓ Lineage tracking end-to-end
4. ✓ Metrics emission and aggregation
5. ✓ Distributed tracing with correlation IDs
6. ✓ MoE routing with all 5 layers
7. ✓ Worker restart after failure
8. ✓ Token budget enforcement

**Example**:
```bash
CORTEX_ENV=staging ./testing/pre-deployment/integration-tests.sh
```

**Output**:
```
╔════════════════════════════════════════╗
║  Cortex Integration Test Suite         ║
╔════════════════════════════════════════╗

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEST: Coordinator → Master → Worker Flow
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ PASS: Task created successfully
✓ PASS: Master handoff created

INTEGRATION TEST SUMMARY
=========================================
Passed:  16
Failed:  0
Skipped: 0

Test Report: /tmp/cortex-integration-test-report-*.json

✓ ALL TESTS PASSED
```

### Stage 4: Load Tests

**Purpose**: Performance validation under concurrent load

**Duration**: ~2 minutes

**Environment**: Staging

**Performance Targets**:
- **Throughput**: ≥5 tasks/min
- **P95 Latency**: <30 seconds
- **Worker Spawn Time**: <1 second average
- **Success Rate**: ≥95% under load

**Tests**:
1. ✓ Coordinator throughput (10 concurrent tasks)
2. ✓ Master response time (P50, P95, P99)
3. ✓ Worker spawn time
4. ✓ Resource leak detection
5. ✓ Graceful degradation under load
6. ✓ Routing performance under load

**Example**:
```bash
CORTEX_ENV=staging ./testing/pre-deployment/load-tests.sh
```

**Output**:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEST: Coordinator Throughput
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tasks created: 10
Total time: 12.5s
Throughput: 48.0 tasks/min

✓ PASS: Throughput meets target (48.0 >= 5 tasks/min)

LOAD TEST SUMMARY
=========================================
Passed: 6
Failed: 0

Detailed metrics: /tmp/cortex-load-test-*.json

✓ ALL LOAD TESTS PASSED
```

## Full Validation Suite

### Running All Tests

```bash
./scripts/validate-deployment.sh
```

**Options**:
- `--stop-on-failure` - Stop validation on first failure
- `--skip-load-tests` - Skip load testing stage
- `--help` - Show help message

**Environment Variables**:
- `CORTEX_ENV` - Set environment (default: staging)
- `CORTEX_HOME` - Set Cortex home directory
- `STOP_ON_FAILURE` - Stop on first failure (true/false)
- `SKIP_LOAD_TESTS` - Skip load tests (true/false)

### Validation Flow

```
┌─────────────────────────────┐
│   Prerequisites Check        │
│   (tools, scripts)           │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Stage 1: Readiness Checks  │ (~30s)
│   • Configuration            │
│   • Dependencies             │
│   • Resources                │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Stage 2: Smoke Tests       │ (<2min)
│   • Quick validation         │
│   • Core functionality       │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Stage 3: Integration Tests │ (<5min)
│   • End-to-end scenarios     │
│   • Staging environment      │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Stage 4: Load Tests        │ (~2min)
│   • Performance validation   │
│   • Concurrent load          │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Generate Report            │
│   • JSON summary             │
│   • Deployment decision      │
└──────────┬──────────────────┘
           │
           ▼
     ✓ DEPLOYMENT READY
     or
     ✗ NOT READY
```

### Example Output

```
╔════════════════════════════════════════════════════════════════╗
║              Cortex Deployment Validation Suite                ║
╔════════════════════════════════════════════════════════════════╗

Environment: staging
Cortex Home: /Users/user/cortex
Start Time: 2025-11-27T12:00:00Z

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 1: Readiness Checks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ STAGE PASSED: Readiness Checks (28s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 2: Smoke Tests (Quick Validation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ STAGE PASSED: Smoke Tests (95s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 3: Integration Tests (End-to-End Scenarios)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ STAGE PASSED: Integration Tests (187s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 4: Load Tests (Performance Validation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ STAGE PASSED: Load Tests (134s)

Validation Summary
Total Duration: 7m 24s

Results:
  ✓ Readiness Checks (28s)
  ✓ Smoke Tests (95s)
  ✓ Integration Tests (187s)
  ✓ Load Tests (134s)

Results:
  Passed:  4
  Failed:  0
  Skipped: 0

╔════════════════════════════════════════════════════════════════╗
║                  ✓ DEPLOYMENT READY                            ║
╔════════════════════════════════════════════════════════════════╗

All validation stages passed. Safe to deploy to production.
```

## Test Data and Fixtures

### Sample Tasks

Located in `/Users/ryandahlberg/Projects/cortex/testing/fixtures/sample-tasks.json`

Contains 10 sample tasks covering different masters:
- Security vulnerabilities
- Feature implementation
- Database optimization
- Documentation updates
- Code refactoring
- Bug fixes
- Testing tasks
- Deployment tasks
- Compliance scans
- Analytics reports

### Sample Workers

Located in `/Users/ryandahlberg/Projects/cortex/testing/fixtures/sample-workers.json`

Contains 5 sample worker specs:
- feature-implementer
- bug-fixer
- refactorer
- optimizer
- security-analyst

### Sample Routing Queries

Located in `/Users/ryandahlberg/Projects/cortex/testing/fixtures/sample-routing-queries.json`

Contains 10 routing test queries with expected outcomes for validation.

## Interpreting Results

### Success Criteria

**Readiness Checks**:
- All critical checks must pass (exit code 0)
- Warnings are acceptable but should be reviewed

**Smoke Tests**:
- All 8 tests must pass
- Must complete in <2 minutes

**Integration Tests**:
- All 8 test scenarios must pass
- Test report generated with detailed results

**Load Tests**:
- Throughput ≥5 tasks/min
- P95 latency <30s
- No resource leaks
- Success rate ≥95%

### What to Do If Tests Fail

#### Readiness Check Failures

**Missing Dependencies**:
```bash
# Install missing tools
brew install jq        # macOS
apt-get install jq     # Linux

pip install anthropic  # Python packages
```

**Configuration Issues**:
- Check `.env` file has valid API key
- Verify directory structure is intact
- Validate all JSON files with `jq`

**Resource Issues**:
- Free up disk space (need >1GB)
- Check write permissions on coordination directories

#### Smoke Test Failures

**Worker Spawn Failures**:
- Check worker type registry
- Verify JSON schema validity

**Routing Failures**:
- Ensure routing cascade script exists
- Check routing component availability

**Lineage/Metrics Failures**:
- Verify directory permissions
- Check JSONL file format

#### Integration Test Failures

**Task Lifecycle Issues**:
- Review task state transitions
- Check staging environment setup

**Lineage Tracking Issues**:
- Verify correlation ID propagation
- Check lineage file format

**Routing Issues**:
- Test individual routing layers
- Check confidence thresholds

#### Load Test Failures

**Low Throughput**:
- Check system resources (CPU, memory)
- Verify no blocking operations
- Consider scaling limits

**High Latency**:
- Profile slow operations
- Check for bottlenecks
- Optimize critical paths

**Resource Leaks**:
- Check for orphaned processes
- Verify cleanup routines
- Monitor system resources

## Adding New Tests

### Adding a Readiness Check

Edit `/Users/ryandahlberg/Projects/cortex/testing/pre-deployment/readiness-checks.sh`:

```bash
check_new_component() {
  section_header "11. New Component Check"

  if [ -f "$CORTEX_HOME/path/to/component" ]; then
    check_pass "New component present"
  else
    check_fail "New component missing"
  fi
}

# Add to main()
main() {
  # ... existing checks
  check_new_component
  # ...
}
```

### Adding an Integration Test

Edit `/Users/ryandahlberg/Projects/cortex/testing/pre-deployment/integration-tests.sh`:

```bash
test_new_feature() {
  test_start "Test 9: New Feature Test"
  local test_name="new_feature"
  local start_time=$($PYTHON -c "import time; print(int(time.time() * 1000))")

  # Test implementation
  # ...

  local duration=$(($($PYTHON -c "import time; print(int(time.time() * 1000))") - start_time))
  test_pass "New feature works" "$test_name" "$duration"
}

# Add to main()
main() {
  # ... existing tests
  test_new_feature
  # ...
}
```

### Adding a Load Test

Edit `/Users/ryandahlberg/Projects/cortex/testing/pre-deployment/load-tests.sh`:

```bash
test_new_performance_metric() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "TEST: New Performance Metric"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # Test implementation
  # ...

  emit_metric "new_metric" "$value" "ms"
}

# Add to main()
main() {
  # ... existing tests
  if test_new_performance_metric; then ((tests_passed++)); else ((tests_failed++)); fi
  # ...
}
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/pre-deployment.yml`:

```yaml
name: Pre-Deployment Validation

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install anthropic numpy torch
          sudo apt-get install -y jq bc

      - name: Run validation suite
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          CORTEX_ENV: staging
        run: |
          ./scripts/validate-deployment.sh --stop-on-failure

      - name: Upload test reports
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-reports
          path: /tmp/cortex-*-report-*.json
```

### Manual Validation Process

**Before Major Changes**:
1. Run readiness checks: `./testing/pre-deployment/readiness-checks.sh`
2. Run smoke tests: `./testing/pre-deployment/smoke-tests.sh`

**Before Releases**:
1. Run full validation: `./scripts/validate-deployment.sh`
2. Review all test reports
3. Fix any failures
4. Re-run validation
5. Deploy when all stages pass

**After Code Changes**:
1. Quick smoke test: `./testing/pre-deployment/smoke-tests.sh`
2. If smoke tests pass, proceed with development
3. Run full validation before merging to main

## Performance Benchmarks

### Target Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Coordinator Throughput | ≥5 tasks/min | TBD | ⏳ |
| Master Response Time (P95) | <30s | TBD | ⏳ |
| Worker Spawn Time | <1s avg | TBD | ⏳ |
| Routing Latency (avg) | <500ms | TBD | ⏳ |
| Success Rate Under Load | ≥95% | TBD | ⏳ |

### Historical Performance

Track performance over time:
- Store test results in `/coordination/metrics/test-results/`
- Generate trend reports
- Alert on performance degradation

## Troubleshooting

### Common Issues

**Issue**: Tests timeout
**Solution**: Increase timeout values or optimize slow operations

**Issue**: Staging environment conflicts
**Solution**: Clean up staging directory: `rm -rf /coordination/staging`

**Issue**: Permission denied errors
**Solution**: Check file permissions: `chmod +x testing/pre-deployment/*.sh`

**Issue**: Python module not found
**Solution**: Install in venv: `pip install -r python-sdk/requirements.txt`

## Best Practices

1. **Run tests before every deployment**
2. **Keep tests fast** (<5 minutes total)
3. **Use staging environment** (never test on production)
4. **Review warnings** (even if tests pass)
5. **Track performance trends** (detect degradation early)
6. **Update tests** (when adding new features)
7. **Document failures** (for future debugging)
8. **Automate in CI/CD** (prevent manual errors)

## Next Steps

After validation passes:

1. **Review test reports** - Check for warnings or edge cases
2. **Update changelog** - Document changes being deployed
3. **Create deployment plan** - Schedule deployment window
4. **Backup production** - Before making changes
5. **Deploy to production** - With monitoring enabled
6. **Verify deployment** - Run smoke tests in production
7. **Monitor metrics** - Watch for anomalies

## Support

For issues or questions:
- Check troubleshooting section above
- Review test output logs
- Consult system documentation
- Open issue with test report attached
