# Cortex K8s CLI

A developer-friendly command-line tool for deploying and managing Cortex services on Kubernetes/K3s.

## Features

- **Easy Deployment**: Deploy services with a single command
- **Log Streaming**: Tail logs from running pods
- **Service Management**: Restart, scale, and monitor services
- **Docker Build Integration**: Build and push images
- **Interactive Exec**: Shell into running containers
- **Auto-completion**: Bash and Zsh completion support
- **Namespace Support**: Work across multiple Kubernetes namespaces

## Installation

### Quick Install

```bash
cd /Users/ryandahlberg/Projects/cortex/scripts/cortex-cli
./install.sh
```

This will:
1. Install `cortex-k8s` to `/usr/local/bin`
2. Set up auto-completion for your shell
3. Verify prerequisites

### Manual Installation

```bash
# Copy the binary
sudo cp cortex-k8s /usr/local/bin/
sudo chmod +x /usr/local/bin/cortex-k8s

# Install bash completion
sudo cp cortex-k8s-completion.bash /etc/bash_completion.d/cortex-k8s

# Or for zsh
sudo cp cortex-k8s-completion.zsh /usr/local/share/zsh/site-functions/_cortex-k8s
```

### Custom Installation Directory

```bash
# Install to custom directory
INSTALL_DIR=$HOME/bin ./install.sh
```

### Uninstall

```bash
./install.sh --uninstall
```

## Prerequisites

Required tools:
- `kubectl` - Kubernetes CLI
- `jq` - JSON processor

Install on macOS:
```bash
brew install kubectl jq
```

Install on Linux:
```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# jq
sudo apt-get install jq  # Debian/Ubuntu
sudo yum install jq      # RHEL/CentOS
```

## Usage

### Basic Commands

```bash
# Show help
cortex-k8s help

# List available services
cortex-k8s list

# Show status of all services
cortex-k8s status

# Show status of specific service
cortex-k8s status cortex-api
```

### Deployment

```bash
# Deploy a service
cortex-k8s deploy cortex-mcp-server

# Deploy to different namespace
cortex-k8s deploy cortex-api --namespace=production

# Deploy with specific kubectl context
cortex-k8s deploy cortex-worker --context=prod-cluster
```

The deploy command will:
1. Find the service manifest (checks `k8s/deployments/` and `k8s/`)
2. Create namespace if it doesn't exist
3. Apply the manifest
4. Wait for rollout to complete
5. Show deployment and pod status

### Building Images

```bash
# Build Docker image
cortex-k8s build cortex-chat

# Build with specific tag
cortex-k8s build cortex-chat v1.2.0

# Build and push to registry
cortex-k8s build cortex-chat v1.2.0 --push

# Build latest and push
cortex-k8s build cortex-api latest --push
```

### Log Management

```bash
# Show recent logs
cortex-k8s logs cortex-api

# Follow logs (tail -f style)
cortex-k8s logs cortex-api -f

# Show last 100 lines
cortex-k8s logs cortex-api --tail=100

# Follow with tail
cortex-k8s logs cortex-worker -f --tail=50

# Show logs from specific time
cortex-k8s logs cortex-api --since=1h
```

### Service Operations

```bash
# Restart a service (rolling restart)
cortex-k8s restart cortex-coordinator

# Scale a service
cortex-k8s scale cortex-worker 5

# Scale down to 1 replica
cortex-k8s scale cortex-api 1

# Scale up to 10 replicas
cortex-k8s scale cortex-worker 10
```

### Testing

```bash
# Run tests for a service
cortex-k8s test cortex-chat

# If no test script found, verifies pod health
cortex-k8s test cortex-api
```

The test command will:
1. Look for `package.json` with test script
2. Look for `test.sh` script
3. Fall back to health check of running pods

### Shell Access

```bash
# Open interactive shell in pod
cortex-k8s exec cortex-api

# Run specific command
cortex-k8s exec cortex-api -- node --version

# Run npm command
cortex-k8s exec cortex-chat -- npm run migrate

# Check environment variables
cortex-k8s exec cortex-worker -- env

# Inspect filesystem
cortex-k8s exec cortex-coordinator -- ls -la /app
```

## Global Flags

All commands support these global flags:

```bash
--namespace=<name>    # Kubernetes namespace (default: cortex)
--context=<name>      # Kubectl context to use
--verbose, -v         # Verbose output
```

### Examples with Global Flags

```bash
# Deploy to production namespace
cortex-k8s deploy cortex-api --namespace=production

# Check logs in staging
cortex-k8s logs cortex-worker --namespace=staging -f

# Use different cluster context
cortex-k8s status --context=prod-k3s --namespace=cortex

# Verbose deployment
cortex-k8s deploy cortex-mcp-server --verbose
```

## Configuration

### Environment Variables

- `CORTEX_ROOT` - Path to Cortex repository (auto-detected)
- `KUBECONFIG` - Path to kubeconfig file (standard kubectl variable)

### Directory Structure

The CLI expects this directory structure:

```
cortex/
├── k8s/
│   ├── deployments/          # Service deployments
│   │   ├── cortex-api.yaml
│   │   ├── cortex-chat.yaml
│   │   └── ...
│   └── *.yaml                # Other K8s resources
├── services/                 # Service source code
│   ├── cortex-api/
│   │   ├── Dockerfile
│   │   └── package.json
│   └── ...
└── scripts/
    └── cortex-cli/           # This CLI tool
```

## Auto-completion

### Bash

Auto-completion provides:
- Command completion
- Service name completion (from kubectl)
- Flag completion
- Context-aware suggestions

Test it:
```bash
cortex-k8s de<TAB>           # Completes to 'deploy'
cortex-k8s deploy co<TAB>    # Shows cortex services
cortex-k8s logs cortex-api -<TAB>  # Shows available flags
```

### Zsh

Zsh completion includes:
- Command descriptions
- Service suggestions
- Flag completion with descriptions
- Smart context-aware completion

## Examples

### Complete Workflow: Deploy New Service

```bash
# 1. Build the image
cortex-k8s build cortex-new-service v1.0.0 --push

# 2. Deploy to staging
cortex-k8s deploy cortex-new-service --namespace=staging

# 3. Check status
cortex-k8s status cortex-new-service --namespace=staging

# 4. Watch logs
cortex-k8s logs cortex-new-service --namespace=staging -f

# 5. Test the service
cortex-k8s test cortex-new-service --namespace=staging

# 6. If tests pass, deploy to production
cortex-k8s deploy cortex-new-service --namespace=production
```

### Debugging a Service

```bash
# 1. Check service status
cortex-k8s status cortex-api

# 2. View recent logs
cortex-k8s logs cortex-api --tail=100

# 3. Shell into pod
cortex-k8s exec cortex-api

# Inside pod:
ps aux                    # Check processes
curl localhost:3000/health # Test endpoint
cat /app/config.json      # Check config
env | grep DATABASE       # Check env vars
exit

# 4. Restart if needed
cortex-k8s restart cortex-api

# 5. Watch new logs
cortex-k8s logs cortex-api -f --since=1m
```

### Scaling for Load

```bash
# Current status
cortex-k8s status cortex-worker

# Scale up for high load
cortex-k8s scale cortex-worker 10

# Monitor deployment
watch -n 2 cortex-k8s status cortex-worker

# Check logs from all pods
cortex-k8s logs cortex-worker -f

# Scale back down
cortex-k8s scale cortex-worker 3
```

### Multi-Environment Management

```bash
# Development
cortex-k8s deploy cortex-api --namespace=dev
cortex-k8s logs cortex-api --namespace=dev -f

# Staging
cortex-k8s deploy cortex-api --namespace=staging
cortex-k8s test cortex-api --namespace=staging

# Production (with different context)
cortex-k8s deploy cortex-api \
  --namespace=production \
  --context=prod-cluster

cortex-k8s status --namespace=production --context=prod-cluster
```

## Service Manifest Discovery

The CLI automatically finds service manifests in these locations (in order):

1. `k8s/deployments/<service>.yaml`
2. `k8s/deployments/<service>-deployment.yaml`
3. `k8s/<service>.yaml`

Example manifest (`k8s/deployments/cortex-api.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cortex-api
  labels:
    app: cortex-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cortex-api
  template:
    metadata:
      labels:
        app: cortex-api
    spec:
      containers:
      - name: cortex-api
        image: cortex/cortex-api:latest
        ports:
        - containerPort: 3000
---
apiVersion: v1
kind: Service
metadata:
  name: cortex-api
spec:
  selector:
    app: cortex-api
  ports:
  - port: 80
    targetPort: 3000
```

## Troubleshooting

### Command not found

```bash
# Check if installed
which cortex-k8s

# If not in PATH, use full path
/usr/local/bin/cortex-k8s status

# Or add to PATH
export PATH="/usr/local/bin:$PATH"
```

### Permission denied

```bash
# Make sure it's executable
chmod +x /usr/local/bin/cortex-k8s

# Or reinstall
./install.sh
```

### Auto-completion not working

```bash
# Bash: Source the completion file
source /etc/bash_completion.d/cortex-k8s

# Or add to ~/.bashrc
echo "source /etc/bash_completion.d/cortex-k8s" >> ~/.bashrc

# Zsh: Rebuild completion cache
rm -f ~/.zcompdump
compinit
```

### Cannot connect to cluster

```bash
# Check kubectl is configured
kubectl cluster-info

# List available contexts
kubectl config get-contexts

# Use specific context
cortex-k8s status --context=my-cluster

# Check namespace exists
kubectl get namespace cortex
```

### Service not found

```bash
# List all available services
cortex-k8s list

# Check running deployments
kubectl get deployments -n cortex

# Verbose mode for debugging
cortex-k8s deploy my-service --verbose
```

## Advanced Usage

### Custom Namespace for All Commands

```bash
# Set default namespace in kubectl config
kubectl config set-context --current --namespace=cortex

# Or use environment variable
export KUBECTL_NAMESPACE=cortex
```

### Integration with CI/CD

```bash
# In your CI/CD pipeline
#!/bin/bash
set -euo pipefail

# Build and tag
cortex-k8s build cortex-api "${CI_COMMIT_SHA}" --push

# Deploy to staging
cortex-k8s deploy cortex-api --namespace=staging

# Run tests
cortex-k8s test cortex-api --namespace=staging

# If tests pass, deploy to production
if [ "$?" -eq 0 ]; then
  cortex-k8s deploy cortex-api --namespace=production
fi
```

### Scripting with cortex-k8s

```bash
#!/bin/bash
# Deploy all services

services=(
  cortex-api
  cortex-chat
  cortex-coordinator
  cortex-mcp-server
  cortex-worker
)

for service in "${services[@]}"; do
  echo "Deploying $service..."
  cortex-k8s deploy "$service" --namespace=production
done

# Wait for all to be ready
for service in "${services[@]}"; do
  echo "Checking $service..."
  cortex-k8s status "$service" --namespace=production
done
```

## Contributing

To add new commands:

1. Edit `cortex-k8s` script
2. Add command function: `cmd_mycommand()`
3. Add to help text
4. Add to completion scripts
5. Update README

## License

Part of the Cortex automation system.

## Version

1.0.0

## Support

For issues or questions, please refer to the main Cortex documentation or create an issue in the repository.
