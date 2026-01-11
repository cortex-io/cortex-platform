# Cortex K8s CLI - Project Overview

## Summary

The **cortex-k8s CLI** is a comprehensive, developer-friendly command-line tool for deploying and managing Cortex services on Kubernetes/K3s clusters. It provides an intuitive interface for common operations while maintaining the power and flexibility of kubectl.

## Project Structure

```
cortex-cli/
├── cortex-k8s                      # Main CLI executable (bash)
├── cortex-k8s-completion.bash      # Bash auto-completion
├── cortex-k8s-completion.zsh       # Zsh auto-completion
├── install.sh                      # Installation script
├── test.sh                         # Test suite
├── Makefile                        # Build automation
│
├── README.md                       # Comprehensive documentation
├── QUICKSTART.md                   # 5-minute getting started guide
├── CHANGELOG.md                    # Version history
├── CONTRIBUTING.md                 # Contribution guidelines
├── PROJECT-OVERVIEW.md            # This file
│
└── examples/                       # Practical examples
    ├── deploy-all.sh               # Deploy all services
    ├── rolling-update.sh           # Rolling update workflow
    ├── health-check.sh             # Health monitoring
    ├── ci-cd-pipeline.sh           # CI/CD integration
    └── README.md                   # Examples documentation
```

## Core Features

### 1. Service Management
- **Deploy**: Deploy services to K3s with automatic manifest discovery
- **Restart**: Rolling restart of services with zero downtime
- **Scale**: Dynamically adjust replica counts
- **Status**: View detailed service and pod status

### 2. Development Workflow
- **Build**: Build Docker images with optional registry push
- **Logs**: Stream logs from one or all pods
- **Exec**: Interactive shell access to running containers
- **Test**: Run tests or verify pod health

### 3. Developer Experience
- **Auto-completion**: Full bash and zsh completion support
- **Color Output**: Clear, color-coded messages
- **Error Handling**: Helpful error messages with troubleshooting tips
- **Verbose Mode**: Debug mode for detailed operation logs

### 4. Flexibility
- **Namespace Support**: Work across multiple environments
- **Context Support**: Manage multiple clusters
- **Global Flags**: Consistent flags across all commands
- **Environment Variables**: Configuration via env vars

## Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `deploy <service>` | Deploy service to K3s | `cortex-k8s deploy cortex-api` |
| `build <service> [tag]` | Build Docker image | `cortex-k8s build cortex-chat v1.0.0` |
| `logs <service> [-f]` | Tail service logs | `cortex-k8s logs cortex-api -f` |
| `status [service]` | Show status | `cortex-k8s status` |
| `test <service>` | Run tests | `cortex-k8s test cortex-worker` |
| `restart <service>` | Restart service | `cortex-k8s restart cortex-api` |
| `scale <service> <N>` | Scale replicas | `cortex-k8s scale cortex-worker 5` |
| `exec <service> [cmd]` | Execute in pod | `cortex-k8s exec cortex-api` |
| `list` | List services | `cortex-k8s list` |
| `help` | Show help | `cortex-k8s help` |
| `version` | Show version | `cortex-k8s version` |

## Architecture

### Design Principles

1. **Simplicity**: Common tasks should be simple, complex tasks should be possible
2. **Discoverability**: Help text and auto-completion make features discoverable
3. **Safety**: Validate inputs, provide clear errors, avoid destructive operations
4. **Portability**: Pure bash, minimal dependencies, works on macOS and Linux
5. **Extensibility**: Easy to add new commands and features

### Technical Stack

- **Language**: Bash 4.0+
- **Dependencies**: kubectl, jq
- **Platform**: macOS, Linux (any Unix-like system)
- **Integration**: Works with any Kubernetes/K3s cluster

### Code Organization

```bash
# Main script structure
cortex-k8s
├── Global configuration
├── Utility functions (logging, colors, kubectl wrapper)
├── Command implementations (cmd_deploy, cmd_build, etc.)
├── Command router (main function)
└── Error handling

# Each command follows this pattern:
cmd_commandname() {
    # 1. Parse arguments
    # 2. Validate inputs
    # 3. Get kubectl command with namespace/context
    # 4. Execute operations
    # 5. Show results
    # 6. Return exit code
}
```

## Installation Methods

### 1. Quick Install (Recommended)
```bash
cd /Users/ryandahlberg/Projects/cortex/scripts/cortex-cli
./install.sh
```

### 2. Manual Install
```bash
sudo cp cortex-k8s /usr/local/bin/
sudo chmod +x /usr/local/bin/cortex-k8s
```

### 3. Development Install
```bash
make dev-install  # Creates symlink for development
```

## Usage Patterns

### Basic Operations
```bash
# Check what's running
cortex-k8s status

# Deploy a service
cortex-k8s deploy cortex-mcp-server

# Watch logs
cortex-k8s logs cortex-mcp-server -f
```

### Development Workflow
```bash
# Build and deploy
cortex-k8s build cortex-api v1.2.0 --push
cortex-k8s deploy cortex-api

# Debug
cortex-k8s logs cortex-api --tail=100
cortex-k8s exec cortex-api -- env
```

### Multi-Environment
```bash
# Staging
cortex-k8s deploy cortex-worker --namespace=staging

# Production
cortex-k8s deploy cortex-worker --namespace=production

# Different cluster
cortex-k8s deploy cortex-worker --context=prod-cluster --namespace=production
```

## Example Scripts

### 1. deploy-all.sh
Deploy all Cortex services in one command. Useful for:
- Initial cluster setup
- Complete system updates
- Disaster recovery

### 2. rolling-update.sh
Complete update workflow with staging verification. Demonstrates:
- Build process
- Multi-environment deployment
- Testing before production

### 3. health-check.sh
Comprehensive health monitoring. Can be used for:
- Scheduled monitoring (cron)
- CI/CD verification
- Troubleshooting

### 4. ci-cd-pipeline.sh
Full CI/CD integration example. Shows:
- Test execution
- Build and push
- Deployment
- Health verification
- Notifications

## Testing

### Test Coverage

The test suite (`test.sh`) verifies:
- Bash syntax
- File permissions
- Required files
- Help output
- Prerequisites
- Shellcheck (if available)
- Documentation completeness
- Completion scripts
- Example scripts

Run tests:
```bash
./test.sh
make test
make lint  # Requires shellcheck
```

## Configuration

### Environment Variables
- `CORTEX_ROOT` - Path to Cortex repository
- `KUBECONFIG` - Kubectl configuration
- `NAMESPACE` - Default namespace (in scripts)
- `REGISTRY` - Docker registry (in scripts)

### Default Values
- Namespace: `cortex`
- Context: (current kubectl context)
- K8s manifests: `k8s/deployments/` and `k8s/`

## Integration Points

### CI/CD Platforms
- Jenkins
- GitLab CI
- GitHub Actions
- CircleCI
- Any bash-compatible platform

### Development Tools
- Make
- Docker
- Git hooks
- Shell aliases

### Monitoring
- Cron jobs
- Alerting systems
- Health dashboards

## Extension Guide

### Adding a New Command

1. **Implement function** in `cortex-k8s`:
   ```bash
   cmd_mycommand() {
       # Your implementation
   }
   ```

2. **Add to router**:
   ```bash
   case "${command}" in
       mycommand) cmd_mycommand "$@" ;;
   ```

3. **Update help text** in `cmd_help()`

4. **Add completion** in both completion scripts

5. **Document** in README.md

6. **Add tests** in test.sh

### Adding a New Example

1. Create `examples/my-example.sh`
2. Add usage documentation
3. Make it executable
4. Document in `examples/README.md`
5. Add test in `test.sh`

## Performance

### Speed
- Instant command execution (no compilation)
- Direct kubectl integration (no additional overhead)
- Efficient manifest discovery
- Minimal dependencies

### Resource Usage
- Minimal memory footprint
- No background processes
- Clean execution model

## Security

### Best Practices
- No hardcoded credentials
- Uses kubectl authentication
- Respects RBAC permissions
- No privilege escalation
- Clear error messages (no credential leakage)

### Recommendations
- Use namespaces for isolation
- Implement RBAC policies
- Regular security updates
- Audit logs for production

## Future Enhancements

### Planned Features (v1.1)
- `rollback` command for quick reverts
- `port-forward` for local access
- `describe` for detailed resource info
- Enhanced error messages
- Performance optimizations

### Long-term Vision
- Helm chart support
- Kustomize integration
- Multi-cluster management
- Service mesh integration
- GitOps workflows
- Resource visualization
- Cost tracking

## Support & Resources

### Documentation
- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - Getting started
- [examples/README.md](examples/README.md) - Example usage

### Contributing
- [CONTRIBUTING.md](CONTRIBUTING.md) - How to contribute
- [CHANGELOG.md](CHANGELOG.md) - Version history

### Getting Help
- Check existing documentation
- Review examples
- Use `--verbose` flag for debugging
- Check kubectl logs

## License

Part of the Cortex automation system.

## Version

Current version: **1.0.0** (2026-01-09)

## Credits

Built for the Cortex automation platform to provide developers with a streamlined, intuitive interface for Kubernetes operations.

---

**Quick Links:**
- Installation: [README.md#installation](README.md#installation)
- Quick Start: [QUICKSTART.md](QUICKSTART.md)
- Examples: [examples/README.md](examples/README.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
