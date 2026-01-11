# Cortex Testing Guide

Complete guide for testing in the Cortex automation system.

## Quick Start

```bash
# Setup test environment
cd /Users/ryandahlberg/Projects/cortex/testing
./scripts/setup-test-environment.sh

# Run all tests
./scripts/run-all-tests.sh

# View coverage report
open coverage/reports/index.html
```

## Test Pyramid

```
        /\
       /E2E\          Few, slow, expensive
      /------\
     /  Integ \       Moderate number, medium speed
    /----------\
   /    Unit    \     Many, fast, cheap
  /--------------\
```

### Unit Tests (Base)

- **Quantity**: Majority of tests
- **Speed**: < 1 second each
- **Scope**: Single function/class
- **Dependencies**: All mocked
- **Location**: `testing/unit/`

### Integration Tests (Middle)

- **Quantity**: Moderate number
- **Speed**: 1-10 seconds each
- **Scope**: Multiple components
- **Dependencies**: Real (via testcontainers)
- **Location**: `testing/integration/`

### E2E Tests (Top)

- **Quantity**: Critical paths only
- **Speed**: 10+ seconds each
- **Scope**: Full system
- **Dependencies**: Real K8s deployment
- **Location**: `testing/e2e/`

## Testing Strategy by Service

### Issue Parser Service

**What to test:**
- Issue parsing logic
- Task validation
- Redis storage
- Anthropic API integration
- Health checks

**Test files:**
- `/Users/ryandahlberg/Projects/cortex/testing/examples/issue-parser/issue-parser.unit.test.js`

**Run tests:**
```bash
cd testing/examples/issue-parser
npm test
```

### Repository Context Service

**What to test:**
- Repository indexing
- Pattern extraction
- ChromaDB storage
- Convention retrieval
- Instruction generation

**Test files:**
- `/Users/ryandahlberg/Projects/cortex/testing/examples/repo-context/repo-context.unit.test.py`

**Run tests:**
```bash
cd testing/examples/repo-context
pytest
```

### Code Generator Service

**What to test:**
- Code generation
- File editing
- Test generation
- Documentation generation
- Git operations

**Test files:**
- `/Users/ryandahlberg/Projects/cortex/testing/examples/code-generator/code-generator.unit.test.js`

**Run tests:**
```bash
cd testing/examples/code-generator
npm test
```

## Test Environments

### Local Development

```bash
# Unit tests (no dependencies needed)
npm test

# Integration tests (requires Docker)
docker-compose -f testing/docker-compose.test.yaml up -d
npm run test:integration
docker-compose -f testing/docker-compose.test.yaml down
```

### CI/CD

Tests run automatically in CI:

- **GitHub Actions**: On push/PR to main/develop
- **GitLab CI**: On commit, with scheduled daily runs
- **Coverage**: Uploaded to Codecov automatically

### Kubernetes

Tests can run as Jobs in K8s:

```bash
# Deploy test jobs
kubectl apply -f testing/k8s/test-runner-job.yaml

# Check results
kubectl logs -n cortex-test job/cortex-unit-tests-js

# Scheduled tests run daily at 2 AM
kubectl get cronjobs -n cortex-test
```

## Writing Tests

### 1. Choose Test Type

Ask yourself:

- Testing a single function? → **Unit test**
- Need real Redis/Postgres? → **Integration test**
- Testing multiple services? → **E2E test**

### 2. Use Templates

Start with a template from `testing/fixtures/`:

**API Endpoint Test:**
```javascript
// Copy from testing/fixtures/api/test-api-endpoint.template.js
describe('My API', () => {
  it('should handle GET requests', async () => {
    const response = await request(app).get('/api/endpoint');
    expect(response.status).toBe(200);
  });
});
```

**Database Test:**
```python
# Copy from testing/fixtures/database/test-database-operations.template.py
def test_insert_record(db_connection):
    """Test inserting a record"""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO test_items (name) VALUES (%s)", ('test',))
        db_connection.commit()
        assert cur.rowcount == 1
```

### 3. Follow AAA Pattern

**Arrange → Act → Assert**

```javascript
describe('Calculator', () => {
  it('should add two numbers', () => {
    // Arrange
    const calculator = new Calculator();
    const a = 5;
    const b = 3;

    // Act
    const result = calculator.add(a, b);

    // Assert
    expect(result).toBe(8);
  });
});
```

### 4. Test Both Paths

Always test success AND failure:

```javascript
describe('User authentication', () => {
  it('should authenticate valid credentials', async () => {
    const result = await auth.login('user', 'correct-password');
    expect(result.success).toBe(true);
  });

  it('should reject invalid credentials', async () => {
    const result = await auth.login('user', 'wrong-password');
    expect(result.success).toBe(false);
    expect(result.error).toBe('Invalid credentials');
  });
});
```

### 5. Use Fixtures

Load test data from fixtures:

```javascript
const testData = require('@testing/fixtures/test-data.json');

describe('Issue processing', () => {
  it('should parse issue', () => {
    const issue = testData.issues[0];
    const result = parseIssue(issue);
    expect(result).toBeDefined();
  });
});
```

## Mocking

### Mock External APIs

```javascript
const GitHubApiMock = require('@testing/mocks/github-api');

describe('GitHub integration', () => {
  let githubMock;

  beforeEach(() => {
    githubMock = new GitHubApiMock();
    githubMock.mockGetRepository('owner', 'repo', {
      id: 123,
      name: 'test-repo'
    });
  });

  afterEach(() => {
    githubMock.cleanup();
  });

  it('should fetch repository', async () => {
    const repo = await fetchRepo('owner', 'repo');
    expect(repo.id).toBe(123);
  });
});
```

### Mock LLM Responses

```javascript
const LLMApiMock = require('@testing/mocks/llm-api');

describe('Code generation', () => {
  let llmMock;

  beforeEach(() => {
    llmMock = new LLMApiMock();
    llmMock.mockCodeGeneration('prompt', 'function test() {}');
  });

  afterEach(() => {
    llmMock.cleanup();
  });

  it('should generate code', async () => {
    const code = await generateCode('prompt');
    expect(code).toContain('function test');
  });
});
```

## Coverage Goals

### Overall Targets

- **Minimum**: 70% coverage for all code
- **Target**: 80% coverage for services
- **Critical**: 90% coverage for core logic

### What to Cover

**High Priority:**
- Business logic
- Error handling
- Security features
- Data transformations

**Medium Priority:**
- API endpoints
- Database operations
- Utility functions

**Low Priority:**
- Getters/setters
- Configuration files
- Type definitions

### Checking Coverage

```bash
# JavaScript
npm test -- --coverage
open coverage/unit/js/html/index.html

# Python
pytest --cov --cov-report=html
open coverage/unit/python/html/index.html

# Combined report
./coverage/generate-report.sh
open coverage/reports/index.html
```

## Debugging Tests

### Enable Verbose Output

```bash
# Jest
npm test -- --verbose

# Pytest
pytest -vv
```

### Run Single Test

```bash
# Jest
npm test -- --testNamePattern="should parse issue"

# Pytest
pytest -k "test_parse_issue"
```

### Debug in IDE

**VSCode (JavaScript):**
```json
{
  "type": "node",
  "request": "launch",
  "name": "Jest Current File",
  "program": "${workspaceFolder}/node_modules/.bin/jest",
  "args": ["${file}"],
  "console": "integratedTerminal"
}
```

**VSCode (Python):**
```json
{
  "type": "python",
  "request": "launch",
  "name": "Pytest Current File",
  "module": "pytest",
  "args": ["${file}"]
}
```

## Performance Tips

### Keep Tests Fast

- Mock slow dependencies
- Use in-memory databases
- Minimize I/O operations
- Run expensive tests in CI only

### Parallel Execution

```bash
# Jest (default: parallel)
npm test -- --maxWorkers=4

# Pytest
pytest -n 4
```

### Skip Slow Tests Locally

```javascript
// Jest
describe.skip('Slow tests', () => {
  // Skipped locally, run in CI
});
```

```python
# Pytest
@pytest.mark.slow
def test_expensive_operation():
    # Run only in CI with: pytest -m "not slow"
    pass
```

## Common Issues

### "Cannot find module"

```bash
# Clear npm cache
rm -rf node_modules package-lock.json
npm install

# Clear Jest cache
npm test -- --clearCache
```

### "Connection refused" in integration tests

```bash
# Check Docker is running
docker ps

# Check testcontainers
docker ps --filter "label=testcontainers"

# View logs
docker logs <container-id>
```

### Tests pass locally but fail in CI

- Check environment variables
- Verify CI has correct versions
- Check for timing issues
- Review CI logs carefully

## Best Practices Checklist

- [ ] Tests are independent
- [ ] Tests are deterministic
- [ ] Tests have clear names
- [ ] Both success/failure paths tested
- [ ] External dependencies mocked (unit tests)
- [ ] Setup/teardown properly handled
- [ ] Error messages are descriptive
- [ ] Coverage meets minimum threshold
- [ ] Tests run fast
- [ ] CI pipeline passes

## Additional Resources

- [Main Testing README](/Users/ryandahlberg/Projects/cortex/testing/README.md)
- [Test Templates](/Users/ryandahlberg/Projects/cortex/testing/fixtures/)
- [Example Tests](/Users/ryandahlberg/Projects/cortex/testing/examples/)
- [CI Configuration](/Users/ryandahlberg/Projects/cortex/testing/ci/)

## Getting Help

1. Check this guide
2. Review example tests
3. Check test templates
4. Review CI logs
5. Ask the team
