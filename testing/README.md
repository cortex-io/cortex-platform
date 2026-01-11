# Cortex Testing Infrastructure

Comprehensive testing strategy for the Cortex automation system, including unit tests, integration tests, E2E tests, and CI/CD pipelines.

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Test Types](#test-types)
- [Getting Started](#getting-started)
- [Running Tests](#running-tests)
- [CI/CD Integration](#cicd-integration)
- [Coverage Reports](#coverage-reports)
- [Writing Tests](#writing-tests)
- [Best Practices](#best-practices)

## Overview

The Cortex testing infrastructure provides:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: Tests with real dependencies (Redis, PostgreSQL) using testcontainers
- **E2E Tests**: Full system tests in Kubernetes environment
- **Test Templates**: Reusable patterns for common test scenarios
- **CI/CD Pipelines**: Automated testing in GitHub Actions and GitLab CI
- **Coverage Reports**: Comprehensive code coverage tracking

## Directory Structure

```
testing/
├── unit/                    # Unit tests
│   ├── js/                 # JavaScript unit tests (Jest)
│   │   ├── jest.config.js
│   │   ├── setup.js
│   │   └── package.json
│   └── python/             # Python unit tests (pytest)
│       ├── pytest.ini
│       ├── conftest.py
│       └── requirements.txt
├── integration/            # Integration tests with testcontainers
│   ├── js/
│   │   ├── jest.config.js
│   │   ├── setup.js        # Testcontainers setup
│   │   └── package.json
│   └── python/
│       ├── pytest.ini
│       ├── conftest.py     # Testcontainers fixtures
│       └── requirements.txt
├── e2e/                    # End-to-end tests with K8s
│   ├── js/
│   │   ├── jest.config.js
│   │   ├── setup.js        # K8s setup
│   │   └── package.json
│   └── python/
│       ├── pytest.ini
│       ├── conftest.py
│       └── requirements.txt
├── fixtures/               # Test data and templates
│   ├── api/               # API test templates
│   ├── database/          # Database test templates
│   ├── redis/             # Redis test templates
│   └── test-data.json     # Sample test data
├── mocks/                  # Mock services
│   ├── github-api.js
│   └── llm-api.js
├── k8s/                    # Kubernetes test resources
│   ├── test-namespace.yaml
│   ├── test-resources/
│   │   ├── redis.yaml
│   │   ├── postgres.yaml
│   │   └── mock-services.yaml
│   └── test-runner-job.yaml
├── ci/                     # CI/CD pipeline templates
│   ├── github-actions-test.yaml
│   └── gitlab-ci-test.yaml
├── coverage/               # Coverage reports
│   ├── generate-report.sh
│   └── reports/
├── examples/               # Example tests for services
│   ├── issue-parser/
│   ├── repo-context/
│   └── code-generator/
└── README.md              # This file
```

## Test Types

### Unit Tests

Fast, isolated tests with mocked dependencies.

**JavaScript (Jest):**
```bash
cd testing/unit/js
npm install
npm test
npm test -- --coverage
```

**Python (pytest):**
```bash
cd testing/unit/python
pip install -r requirements.txt
pytest
pytest --cov
```

### Integration Tests

Tests with real external dependencies using testcontainers.

**JavaScript:**
```bash
cd testing/integration/js
npm install
npm test
```

**Python:**
```bash
cd testing/integration/python
pip install -r requirements.txt
pytest
```

### E2E Tests

Full system tests in Kubernetes.

**Prerequisites:**
- K3s or K8s cluster running
- kubectl configured
- Test namespace created

**Run E2E tests:**
```bash
# Setup test environment
kubectl create namespace cortex-test
kubectl apply -f testing/k8s/test-resources/

# Run tests
cd testing/e2e/js
npm install
npm test
```

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (for integration tests)
- Kubernetes cluster (for E2E tests)

### Installation

```bash
# Install JavaScript dependencies
cd testing/unit/js && npm install
cd testing/integration/js && npm install
cd testing/e2e/js && npm install

# Install Python dependencies
cd testing/unit/python && pip install -r requirements.txt
cd testing/integration/python && pip install -r requirements.txt
cd testing/e2e/python && pip install -r requirements.txt
```

## Running Tests

### Run All Tests

```bash
# From project root
./testing/scripts/run-all-tests.sh
```

### Run Specific Test Suites

```bash
# Unit tests only
./testing/scripts/run-unit-tests.sh

# Integration tests only
./testing/scripts/run-integration-tests.sh

# E2E tests only
./testing/scripts/run-e2e-tests.sh
```

### Run Tests for Specific Services

```bash
# Issue Parser tests
cd testing/examples/issue-parser
npm test

# Repository Context tests
cd testing/examples/repo-context
pytest

# Code Generator tests
cd testing/examples/code-generator
npm test
```

## CI/CD Integration

### GitHub Actions

The GitHub Actions workflow runs automatically on push and pull requests:

- **Unit Tests**: Run in parallel for JS and Python
- **Integration Tests**: Run with Redis and PostgreSQL services
- **E2E Tests**: Run in K3s cluster
- **Coverage**: Upload to Codecov

**Configuration**: `/Users/ryandahlberg/Projects/cortex/testing/ci/github-actions-test.yaml`

### GitLab CI

The GitLab CI pipeline includes:

- Unit tests with caching
- Integration tests with service containers
- E2E tests
- Coverage reporting
- Scheduled daily test runs

**Configuration**: `/Users/ryandahlberg/Projects/cortex/testing/ci/gitlab-ci-test.yaml`

### Running Tests in K8s

Deploy test runners as Jobs:

```bash
# Deploy test jobs
kubectl apply -f testing/k8s/test-runner-job.yaml

# Check job status
kubectl get jobs -n cortex-test

# View logs
kubectl logs -n cortex-test job/cortex-unit-tests-js

# Clean up
kubectl delete jobs -n cortex-test --all
```

## Coverage Reports

### Generate Coverage Reports

```bash
# Run tests with coverage
cd testing/unit/js && npm test -- --coverage
cd testing/unit/python && pytest --cov

# Generate combined report
./testing/coverage/generate-report.sh
```

### View Coverage Reports

Open in browser:
```bash
# JavaScript coverage
open testing/coverage/unit/js/html/index.html

# Python coverage
open testing/coverage/unit/python/html/index.html

# Combined report
open testing/coverage/reports/index.html
```

### Coverage Requirements

- **Minimum**: 70% for all code
- **Target**: 80%+ for production services
- **Critical paths**: 90%+ coverage required

## Writing Tests

### Use Test Templates

Templates are available in `testing/fixtures/`:

- `api/test-api-endpoint.template.js` - API endpoint testing
- `api/test-api-endpoint.template.py` - Python API testing
- `database/test-database-operations.template.js` - Database tests
- `database/test-database-operations.template.py` - Python database tests
- `redis/test-redis-operations.template.js` - Redis tests
- `redis/test-redis-operations.template.py` - Python Redis tests

### Example: Writing an API Test

**JavaScript:**
```javascript
const request = require('supertest');

describe('My Service API', () => {
  it('should return 200 OK', async () => {
    const response = await request(app)
      .get('/api/endpoint')
      .expect(200);

    expect(response.body).toHaveProperty('data');
  });
});
```

**Python:**
```python
def test_api_endpoint(client):
    """Test API endpoint returns 200 OK"""
    response = client.get('/api/endpoint')
    assert response.status_code == 200
    assert 'data' in response.json()
```

### Use Mock Services

Mock GitHub and LLM APIs are available:

```javascript
const GitHubApiMock = require('@testing/mocks/github-api');
const LLMApiMock = require('@testing/mocks/llm-api');

describe('With mocks', () => {
  let githubMock;
  let llmMock;

  beforeEach(() => {
    githubMock = new GitHubApiMock();
    llmMock = new LLMApiMock();

    githubMock.mockGetRepository('owner', 'repo');
    llmMock.mockCompletion('prompt', { text: 'response' });
  });

  afterEach(() => {
    githubMock.cleanup();
    llmMock.cleanup();
  });

  // Your tests here
});
```

## Best Practices

### 1. Test Organization

- **One test file per source file**
- Use descriptive test names
- Group related tests with `describe` blocks
- Keep tests focused and atomic

### 2. Test Independence

- Each test should be independent
- Use `beforeEach` for setup
- Use `afterEach` for cleanup
- Don't rely on test execution order

### 3. Mocking

- Mock external dependencies in unit tests
- Use real dependencies in integration tests
- Keep mocks simple and maintainable
- Update mocks when APIs change

### 4. Assertions

- Use meaningful assertion messages
- Test both success and failure paths
- Verify side effects
- Check error messages

### 5. Performance

- Keep unit tests fast (< 1s each)
- Use fixtures for test data
- Clean up resources after tests
- Run expensive tests in CI only

### 6. Coverage

- Aim for high coverage but focus on quality
- Test edge cases and error conditions
- Don't test trivial code
- Use coverage to find untested code

## Troubleshooting

### Tests Failing Locally

```bash
# Clean install dependencies
rm -rf node_modules package-lock.json
npm install

# Clear Jest cache
npm test -- --clearCache

# Run tests with verbose output
npm test -- --verbose
```

### Integration Tests Failing

```bash
# Check Docker is running
docker ps

# Check containers are healthy
docker ps --filter "label=testcontainers"

# View container logs
docker logs <container-id>
```

### E2E Tests Failing

```bash
# Check K8s cluster
kubectl cluster-info

# Check test namespace
kubectl get all -n cortex-test

# View pod logs
kubectl logs -n cortex-test <pod-name>

# Describe pod for events
kubectl describe pod -n cortex-test <pod-name>
```

## Additional Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [Pytest Documentation](https://docs.pytest.org/)
- [Testcontainers](https://testcontainers.com/)
- [Kubernetes Testing Guide](https://kubernetes.io/docs/tasks/)

## Contributing

When adding new tests:

1. Follow existing patterns
2. Use test templates where possible
3. Include both happy and error paths
4. Update this README if needed
5. Ensure tests pass in CI

## Support

For issues or questions:

- Check existing test examples
- Review test templates
- Check CI logs for details
- Contact the Cortex team
