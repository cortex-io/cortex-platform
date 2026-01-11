# Cortex K8s CLI - Examples

This directory contains practical examples of using the cortex-k8s CLI in real-world scenarios.

## Available Examples

### 1. deploy-all.sh

Deploy all Cortex services to a namespace.

**Usage:**
```bash
# Deploy to default namespace (cortex)
./deploy-all.sh

# Deploy to specific namespace
NAMESPACE=production ./deploy-all.sh
```

**What it does:**
- Deploys all core Cortex services
- Verifies each deployment
- Shows final status

**Customize:**
Edit the `SERVICES` array to add/remove services.

---

### 2. rolling-update.sh

Complete rolling update workflow from build to production.

**Usage:**
```bash
# Update cortex-api to current git commit
./rolling-update.sh cortex-api

# Update with specific version
./rolling-update.sh cortex-chat v1.2.0
```

**What it does:**
1. Builds Docker image
2. Pushes to registry
3. Deploys to staging
4. Runs tests in staging
5. Prompts for production deployment
6. Tails production logs

**Perfect for:** Manual releases with verification steps

---

### 3. health-check.sh

Comprehensive health check for all services.

**Usage:**
```bash
# Check default namespace
./health-check.sh

# Check specific namespace
NAMESPACE=production ./health-check.sh
```

**What it does:**
- Checks all deployments in namespace
- Verifies replica counts
- Shows pod status for unhealthy services
- Displays recent events
- Returns exit code 0 if all healthy, 1 if any issues

**Use cases:**
- Monitoring scripts
- Post-deployment verification
- Troubleshooting

---

### 4. ci-cd-pipeline.sh

Full CI/CD pipeline integration example.

**Usage:**
```bash
# Basic usage
./ci-cd-pipeline.sh

# With environment variables
SERVICE=cortex-worker \
ENVIRONMENT=production \
IMAGE_TAG=v1.2.0 \
./ci-cd-pipeline.sh
```

**Environment Variables:**
- `SERVICE` - Service to deploy (default: cortex-api)
- `ENVIRONMENT` - Target environment (default: staging)
- `IMAGE_TAG` - Image tag (default: git commit SHA)
- `REGISTRY` - Docker registry (default: cortex)
- `NAMESPACE` - K8s namespace (default: same as ENVIRONMENT)
- `SLACK_WEBHOOK_URL` - Optional: Slack notification webhook

**What it does:**
1. Verifies prerequisites
2. Runs tests
3. Builds Docker image
4. Pushes to registry
5. Deploys to environment
6. Health check with retries
7. Verifies deployment
8. Optional Slack notification

**Pipeline Integration:**

**GitLab CI (.gitlab-ci.yml):**
```yaml
deploy:staging:
  stage: deploy
  script:
    - export SERVICE=cortex-api
    - export ENVIRONMENT=staging
    - export IMAGE_TAG=$CI_COMMIT_SHA
    - ./scripts/cortex-cli/examples/ci-cd-pipeline.sh
  only:
    - develop
```

**GitHub Actions (.github/workflows/deploy.yml):**
```yaml
- name: Deploy to staging
  env:
    SERVICE: cortex-api
    ENVIRONMENT: staging
    IMAGE_TAG: ${{ github.sha }}
  run: ./scripts/cortex-cli/examples/ci-cd-pipeline.sh
```

**Jenkins (Jenkinsfile):**
```groovy
stage('Deploy') {
    steps {
        sh '''
            export SERVICE=cortex-api
            export ENVIRONMENT=staging
            export IMAGE_TAG=$GIT_COMMIT
            ./scripts/cortex-cli/examples/ci-cd-pipeline.sh
        '''
    }
}
```

---

## Creating Custom Scripts

### Template Structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# Configuration
SERVICE="${1:-cortex-api}"
NAMESPACE="${NAMESPACE:-cortex}"

# Your logic here
echo "Deploying ${SERVICE} to ${NAMESPACE}..."

if cortex-k8s deploy "${SERVICE}" --namespace="${NAMESPACE}"; then
    echo "✓ Success"
else
    echo "✗ Failed"
    exit 1
fi
```

### Best Practices

1. **Use `set -euo pipefail`** - Exit on errors
2. **Accept environment variables** - Make scripts flexible
3. **Provide defaults** - `${VAR:-default}`
4. **Check prerequisites** - Verify tools exist
5. **Use proper exit codes** - 0 for success, non-zero for failure
6. **Add logging** - Clear status messages
7. **Handle errors gracefully** - Provide troubleshooting tips

### Common Patterns

**Retry logic:**
```bash
MAX_RETRIES=5
RETRY_COUNT=0

while [[ ${RETRY_COUNT} -lt ${MAX_RETRIES} ]]; do
    if cortex-k8s test "${SERVICE}"; then
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 10
done
```

**Multiple services:**
```bash
SERVICES=("api" "worker" "chat")

for service in "${SERVICES[@]}"; do
    cortex-k8s deploy "cortex-${service}" || exit 1
done
```

**Conditional deployment:**
```bash
if [[ "${ENVIRONMENT}" == "production" ]]; then
    read -p "Deploy to production? [y/N] " -n 1 -r
    [[ $REPLY =~ ^[Yy]$ ]] || exit 0
fi

cortex-k8s deploy "${SERVICE}" --namespace="${ENVIRONMENT}"
```

---

## Integration Examples

### Makefile Integration

```makefile
.PHONY: deploy-staging deploy-prod health-check

deploy-staging:
	NAMESPACE=staging ./examples/deploy-all.sh

deploy-prod:
	NAMESPACE=production ./examples/deploy-all.sh

health-check:
	./examples/health-check.sh
```

### Cron Job Monitoring

```bash
# Add to crontab: crontab -e
# Check health every 5 minutes
*/5 * * * * /path/to/health-check.sh || mail -s "Cortex health check failed" admin@example.com
```

### Pre-commit Hook

```bash
# .git/hooks/pre-push
#!/bin/bash
if [[ "$(git branch --show-current)" == "main" ]]; then
    echo "Running health check before push..."
    ./scripts/cortex-cli/examples/health-check.sh || {
        echo "Health check failed, aborting push"
        exit 1
    }
fi
```

---

## Troubleshooting Examples

### Debug Mode

Add to any script:
```bash
# Enable debug output
set -x

# Or for cortex-k8s
cortex-k8s deploy "${SERVICE}" --verbose
```

### Capture Logs on Failure

```bash
deploy_with_logs() {
    local service="$1"
    local namespace="$2"

    if ! cortex-k8s deploy "${service}" --namespace="${namespace}"; then
        echo "Deployment failed, capturing logs..."
        cortex-k8s logs "${service}" --namespace="${namespace}" --tail=100 \
            > "deploy-failure-${service}-$(date +%s).log"
        exit 1
    fi
}
```

### Rollback on Failure

```bash
# Save current deployment
kubectl get deployment "${SERVICE}" -n "${NAMESPACE}" -o yaml > backup.yaml

# Deploy new version
if ! cortex-k8s deploy "${SERVICE}" --namespace="${NAMESPACE}"; then
    echo "Deployment failed, rolling back..."
    kubectl apply -f backup.yaml
    exit 1
fi
```

---

## Contributing

To add new examples:

1. Create a new script in this directory
2. Make it executable: `chmod +x example.sh`
3. Add documentation to this README
4. Test with different scenarios
5. Include error handling
6. Add usage examples

---

## Support

For questions or issues with these examples, please refer to the main [README.md](../README.md) or create an issue in the repository.
