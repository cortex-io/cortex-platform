# Changelog

All notable changes to the cortex-k8s CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-09

### Added
- Initial release of cortex-k8s CLI
- `deploy` command for deploying services to K3s
- `build` command for building Docker images
- `logs` command for tailing service logs
- `status` command for checking service status
- `test` command for running service tests
- `restart` command for rolling restarts
- `scale` command for scaling replicas
- `exec` command for shelling into pods
- `list` command for listing available services
- `help` command with comprehensive documentation
- `version` command for version info
- Global flags: `--namespace`, `--context`, `--verbose`
- Bash auto-completion support
- Zsh auto-completion support
- Installation script with auto-completion setup
- Comprehensive README with examples
- Quick start guide
- Example scripts:
  - deploy-all.sh
  - rolling-update.sh
  - health-check.sh
  - ci-cd-pipeline.sh
- Makefile for easy management
- Full documentation

### Features
- Automatic service manifest discovery
- Namespace creation if missing
- Rollout status monitoring
- Multi-pod log aggregation
- Interactive shell access
- Color-coded output
- Error handling and validation
- Verbose mode for debugging

### Documentation
- Main README with full usage guide
- Quick start guide for new users
- Examples directory with practical scripts
- Example integration patterns
- Troubleshooting guide
- Contributing guidelines

## [Unreleased]

### Planned Features
- `rollback` command for reverting deployments
- `port-forward` command for local access
- `describe` command for detailed resource info
- `events` command for K8s event stream
- `config` command for managing configuration
- `context` command for switching contexts
- Support for Helm charts
- Support for Kustomize
- Interactive service selection
- Service dependency checking
- Automated testing integration
- Metrics and monitoring integration
- Resource usage reporting
- Cost estimation
- Multi-cluster support
- Service mesh integration
- GitOps workflow support

### Future Improvements
- Performance optimizations
- Better error messages
- Tab completion for all flags
- Custom output formats (JSON, YAML)
- Parallel deployments
- Deployment strategies (blue-green, canary)
- Pre-deployment validation
- Post-deployment hooks
- Configuration templates
- Secret management integration

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## Version History

- **1.0.0** (2026-01-09) - Initial release
