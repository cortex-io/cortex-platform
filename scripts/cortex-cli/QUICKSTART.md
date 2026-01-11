# Cortex K8s CLI - Quick Start Guide

Get up and running with the Cortex K8s CLI in 5 minutes.

## 1. Install

```bash
cd /Users/ryandahlberg/Projects/cortex/scripts/cortex-cli
./install.sh
```

Or using make:
```bash
make install
```

## 2. Verify Installation

```bash
cortex-k8s version
cortex-k8s help
```

## 3. Check Your Cluster

```bash
# Make sure kubectl is working
kubectl cluster-info

# List namespaces
kubectl get namespaces
```

## 4. Deploy Your First Service

```bash
# List available services
cortex-k8s list

# Check current status
cortex-k8s status

# Deploy a service
cortex-k8s deploy cortex-mcp-server

# Watch the deployment
watch -n 2 cortex-k8s status cortex-mcp-server
```

## 5. Common Tasks

### View Logs
```bash
# Recent logs
cortex-k8s logs cortex-mcp-server

# Follow logs (tail -f)
cortex-k8s logs cortex-mcp-server -f
```

### Restart a Service
```bash
cortex-k8s restart cortex-mcp-server
```

### Scale a Service
```bash
# Scale to 3 replicas
cortex-k8s scale cortex-mcp-server 3

# Scale to 1 replica
cortex-k8s scale cortex-mcp-server 1
```

### Shell into a Pod
```bash
# Interactive shell
cortex-k8s exec cortex-mcp-server

# Run a command
cortex-k8s exec cortex-mcp-server -- node --version
```

## 6. Build and Deploy Workflow

```bash
# Build a new image
cortex-k8s build cortex-chat v1.0.0

# Push to registry
cortex-k8s build cortex-chat v1.0.0 --push

# Deploy the new version
cortex-k8s deploy cortex-chat

# Check it's running
cortex-k8s status cortex-chat

# View logs
cortex-k8s logs cortex-chat -f
```

## 7. Working with Multiple Namespaces

```bash
# Deploy to staging
cortex-k8s deploy cortex-api --namespace=staging

# Check staging status
cortex-k8s status --namespace=staging

# Deploy to production
cortex-k8s deploy cortex-api --namespace=production
```

## 8. Debugging

```bash
# Full service status
cortex-k8s status cortex-api

# Last 100 log lines
cortex-k8s logs cortex-api --tail=100

# Shell into pod
cortex-k8s exec cortex-api

# In the pod:
ps aux                     # Check processes
curl localhost:3000/health # Test endpoint
env | grep -i database     # Check env vars
```

## 9. Auto-completion

If auto-completion isn't working:

```bash
# Bash
source /etc/bash_completion.d/cortex-k8s

# Zsh
compinit
```

Then test it:
```bash
cortex-k8s de<TAB>         # Should complete to 'deploy'
cortex-k8s deploy c<TAB>   # Should show cortex services
```

## 10. Get Help

```bash
# General help
cortex-k8s help

# Command-specific help
cortex-k8s deploy --help

# Read full documentation
cat README.md
```

## Common Patterns

### Deploy and Monitor
```bash
cortex-k8s deploy cortex-worker && \
  cortex-k8s logs cortex-worker -f
```

### Restart and Watch
```bash
cortex-k8s restart cortex-api && \
  watch -n 2 cortex-k8s status cortex-api
```

### Scale with Monitoring
```bash
cortex-k8s scale cortex-worker 5 && \
  cortex-k8s logs cortex-worker -f
```

## Troubleshooting

### "command not found"
```bash
# Check installation
which cortex-k8s

# Reinstall
./install.sh
```

### "No pods found"
```bash
# Check namespace
cortex-k8s status --namespace=cortex

# List all namespaces
kubectl get namespaces

# List all deployments
kubectl get deployments --all-namespaces
```

### "Cannot connect to cluster"
```bash
# Check kubectl config
kubectl config current-context

# List contexts
kubectl config get-contexts

# Use specific context
cortex-k8s status --context=my-cluster
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore all commands with `cortex-k8s help`
- Set up auto-completion for your shell
- Integrate into your CI/CD pipeline

## Useful Aliases

Add these to your `.bashrc` or `.zshrc`:

```bash
# Short aliases
alias ck='cortex-k8s'
alias ck-status='cortex-k8s status'
alias ck-logs='cortex-k8s logs'
alias ck-deploy='cortex-k8s deploy'

# Namespace-specific
alias ck-prod='cortex-k8s --namespace=production'
alias ck-staging='cortex-k8s --namespace=staging'

# Common tasks
alias ck-all='cortex-k8s status'
alias ck-restart='cortex-k8s restart'
```

Then use them:
```bash
ck status
ck-logs cortex-api -f
ck-prod deploy cortex-worker
```

Happy deploying!
