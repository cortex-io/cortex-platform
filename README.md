# Cortex Platform

**The monorepo for all Cortex application code, libraries, and services.**

## Structure

```
cortex-platform/
├── services/           # Microservices and applications
│   ├── mcp-servers/   # MCP server implementations
│   ├── api/           # API services
│   └── workers/       # Worker processes
├── lib/               # Shared libraries
│   ├── cortex-core/   # Core platform libraries
│   ├── orchestration/ # Orchestration logic
│   ├── coordination/  # Agent coordination
│   └── tools/         # Utilities and helpers
├── coordination/      # Agent coordination system
│   ├── masters/       # Master agent configurations
│   ├── workers/       # Worker agent specs
│   └── policies/      # Coordination policies
├── docs/              # Documentation
├── examples/          # Usage examples
├── testing/           # Test suites
└── scripts/           # Build and deployment scripts
```

## Philosophy

This is application code only. Infrastructure manifests live in `cortex-gitops`.

- **Code here** → Build containers → Push to registry
- **Manifests in cortex-gitops** → ArgoCD pulls → Deploys to k3s

The control plane whispers; the cluster thunders.

---

**Repository**: https://github.com/ry-ops/cortex-platform
**GitOps Repo**: https://github.com/ry-ops/cortex-gitops
**Project**: Cortex - AI Infrastructure Orchestration
