# Cortex K8s CLI - Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     cortex-k8s CLI                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Command    │  │   Global     │  │   Utility    │     │
│  │   Router     │  │   Flags      │  │  Functions   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
│         └─────────────────┴─────────────────┘              │
│                           ▼                                │
│         ┌─────────────────────────────────┐                │
│         │     Command Implementations     │                │
│         │                                 │                │
│         │  • deploy    • scale           │                │
│         │  • build     • exec            │                │
│         │  • logs      • list            │                │
│         │  • status    • help            │                │
│         │  • test      • version         │                │
│         │  • restart                     │                │
│         └─────────────────┬───────────────┘                │
│                           │                                │
└───────────────────────────┼────────────────────────────────┘
                            ▼
         ┌──────────────────────────────────┐
         │         kubectl API              │
         │  (with namespace/context flags)  │
         └──────────────────┬───────────────┘
                            ▼
         ┌──────────────────────────────────┐
         │      Kubernetes/K3s Cluster      │
         │                                  │
         │  ┌────────┐  ┌────────┐         │
         │  │  Pods  │  │Service │         │
         │  └────────┘  └────────┘         │
         │  ┌────────┐  ┌────────┐         │
         │  │Deployment│ │ Logs  │         │
         │  └────────┘  └────────┘         │
         └──────────────────────────────────┘
```

## Command Flow

### Deploy Command Flow

```
User Input
    │
    ▼
cortex-k8s deploy cortex-api --namespace=prod
    │
    ├─► Parse arguments (service="cortex-api")
    ├─► Parse global flags (namespace="prod")
    ├─► Validate inputs
    │
    ├─► Find service manifest
    │   │
    │   ├─► Check k8s/deployments/cortex-api.yaml
    │   ├─► Check k8s/deployments/cortex-api-deployment.yaml
    │   └─► Check k8s/cortex-api.yaml
    │
    ├─► Create namespace if missing
    │   └─► kubectl create namespace prod
    │
    ├─► Apply manifest
    │   └─► kubectl apply -f manifest.yaml --namespace=prod
    │
    ├─► Wait for rollout
    │   └─► kubectl rollout status deployment/cortex-api --namespace=prod
    │
    ├─► Show status
    │   ├─► kubectl get deployment cortex-api --namespace=prod
    │   └─► kubectl get pods -l app=cortex-api --namespace=prod
    │
    └─► Return success/failure
```

### Build Command Flow

```
User Input
    │
    ▼
cortex-k8s build cortex-chat v1.2.0 --push
    │
    ├─► Parse arguments (service="cortex-chat", tag="v1.2.0")
    ├─► Parse flags (push=true)
    │
    ├─► Find Dockerfile
    │   │
    │   ├─► Check cortex-chat/Dockerfile
    │   ├─► Check services/cortex-chat/Dockerfile
    │   └─► Check ./Dockerfile
    │
    ├─► Build image
    │   └─► docker build -t cortex/cortex-chat:v1.2.0 .
    │
    ├─► If --push flag
    │   └─► docker push cortex/cortex-chat:v1.2.0
    │
    └─► Return success/failure
```

### Logs Command Flow

```
User Input
    │
    ▼
cortex-k8s logs cortex-worker -f --tail=100
    │
    ├─► Parse arguments (service="cortex-worker")
    ├─► Parse kubectl flags (-f, --tail=100)
    │
    ├─► Find pods for service
    │   └─► kubectl get pods -l app=cortex-worker --namespace=cortex
    │
    ├─► If single pod
    │   └─► kubectl logs pod-name -f --tail=100
    │
    ├─► If multiple pods
    │   └─► kubectl logs -l app=cortex-worker -f --tail=100
    │
    └─► Stream logs (blocking)
```

## Component Interaction

```
┌────────────────────────────────────────────────────────────┐
│                         User                               │
└───────────┬────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────┐
│                   Shell / Terminal                        │
│                                                           │
│  ┌─────────────────────────────────────────────────┐     │
│  │         Auto-completion Engine                  │     │
│  │                                                 │     │
│  │  • Bash: _cortex_k8s_completions()            │     │
│  │  • Zsh:  _cortex-k8s()                        │     │
│  │                                                 │     │
│  │  Provides:                                     │     │
│  │  - Command completion                          │     │
│  │  - Service name suggestions                    │     │
│  │  - Flag completion                             │     │
│  └─────────────────────────────────────────────────┘     │
└───────────┬───────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────┐
│                    cortex-k8s                             │
│                                                           │
│  ┌─────────────────────────────────────────────────┐     │
│  │              Main Entry Point                   │     │
│  │  • Parse global flags                          │     │
│  │  • Check prerequisites                         │     │
│  │  • Route to command function                   │     │
│  └─────────────┬───────────────────────────────────┘     │
│                │                                          │
│  ┌─────────────▼───────────────────────────────────┐     │
│  │         Command Implementation                  │     │
│  │  • Validate inputs                             │     │
│  │  • Construct kubectl commands                  │     │
│  │  • Execute operations                          │     │
│  │  • Handle errors                               │     │
│  │  • Format output                               │     │
│  └─────────────┬───────────────────────────────────┘     │
└────────────────┼──────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│                      kubectl                               │
│  • Authenticates with cluster                            │
│  • Applies namespace and context                         │
│  • Executes Kubernetes operations                        │
└───────────┬────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────┐
│                  Kubernetes Cluster                        │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Deployment  │  │    Service   │  │  ConfigMap   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │     Pods     │  │    Volumes   │  │   Secrets    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────────────────────────────────────────────────────────┘
```

## Data Flow

### Configuration Discovery

```
cortex-k8s
    │
    ├─► CORTEX_ROOT environment variable
    │   └─► Default: ../../ (relative to script)
    │
    ├─► K8S_DIR = ${CORTEX_ROOT}/k8s
    │
    ├─► DEPLOY_DIR = ${K8S_DIR}/deployments
    │
    └─► Service Manifest Discovery
        │
        ├─► ${DEPLOY_DIR}/${service}.yaml
        ├─► ${DEPLOY_DIR}/${service}-deployment.yaml
        └─► ${K8S_DIR}/${service}.yaml
```

### kubectl Command Construction

```
User Command: cortex-k8s deploy cortex-api --namespace=prod --context=k3s

Parsed:
├─► command = "deploy"
├─► service = "cortex-api"
├─► namespace = "prod"
└─► context = "k3s"

kubectl Command:
└─► kubectl apply -f manifest.yaml --namespace=prod --context=k3s
```

## Error Handling Flow

```
Command Execution
    │
    ├─► Prerequisites Check
    │   ├─► kubectl installed? ─► No ─► Exit with error
    │   └─► jq installed? ─► No ─► Exit with error
    │
    ├─► Input Validation
    │   ├─► Required arguments? ─► No ─► Show usage, exit
    │   └─► Valid values? ─► No ─► Show error, exit
    │
    ├─► Resource Discovery
    │   ├─► Manifest found? ─► No ─► Show search locations, exit
    │   └─► Service exists? ─► No ─► Show available services, exit
    │
    ├─► kubectl Execution
    │   ├─► Success ─► Show success message
    │   └─► Failure ─► Show error, suggest troubleshooting
    │
    └─► Return Exit Code
        ├─► 0 = Success
        └─► 1 = Failure
```

## State Management

The CLI is **stateless** - no persistent state between invocations:

```
Each Invocation:
├─► Parse arguments
├─► Query cluster state (via kubectl)
├─► Execute operation
├─► Show results
└─► Exit

No state files
No caching
No background processes
```

## Integration Architecture

### CI/CD Integration

```
┌────────────────────────────────────────────────────────┐
│                   CI/CD Platform                       │
│              (Jenkins/GitLab/GitHub)                   │
│                                                        │
│  ┌──────────────────────────────────────────────┐     │
│  │          Pipeline Definition                 │     │
│  │                                              │     │
│  │  stages:                                     │     │
│  │    - build                                   │     │
│  │    - test                                    │     │
│  │    - deploy                                  │     │
│  └──────────────┬───────────────────────────────┘     │
│                 │                                      │
│  ┌──────────────▼───────────────────────────────┐     │
│  │         Shell Executor                       │     │
│  │                                              │     │
│  │  $ cortex-k8s build $SERVICE $TAG --push    │     │
│  │  $ cortex-k8s deploy $SERVICE --namespace=$ENV   │
│  │  $ cortex-k8s test $SERVICE --namespace=$ENV     │
│  └──────────────┬───────────────────────────────┘     │
└─────────────────┼────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │   cortex-k8s   │
         └────────────────┘
```

### Monitoring Integration

```
┌────────────────────────────────────────────────────────┐
│                    Cron / Scheduler                    │
│                                                        │
│  */5 * * * * /path/to/health-check.sh                 │
│                                                        │
│  ┌──────────────────────────────────────────────┐     │
│  │         health-check.sh                      │     │
│  │                                              │     │
│  │  for service in services; do                │     │
│  │    cortex-k8s status $service               │     │
│  │    if [ $? -ne 0 ]; then                    │     │
│  │      alert_team                             │     │
│  │    fi                                       │     │
│  │  done                                       │     │
│  └──────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────┘
```

## Security Model

```
┌────────────────────────────────────────────────────────┐
│                    cortex-k8s CLI                      │
│                                                        │
│  Security Features:                                    │
│  ├─► No credential storage                            │
│  ├─► Delegates to kubectl                             │
│  ├─► Respects KUBECONFIG                              │
│  ├─► No privilege escalation                          │
│  └─► Clear error messages (no credential leaks)       │
│                                                        │
└───────────┬────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────┐
│                      kubectl                           │
│                                                        │
│  Authentication:                                       │
│  ├─► Uses KUBECONFIG                                  │
│  ├─► Supports multiple contexts                       │
│  └─► Certificate-based or token-based                 │
│                                                        │
└───────────┬────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────┐
│              Kubernetes API Server                     │
│                                                        │
│  Authorization:                                        │
│  ├─► RBAC policies                                    │
│  ├─► Namespace restrictions                           │
│  └─► Service account permissions                      │
│                                                        │
└────────────────────────────────────────────────────────┘
```

## Performance Characteristics

```
Operation         │ Time      │ Network Calls │ Notes
──────────────────┼───────────┼───────────────┼─────────────────
help/version      │ <10ms     │ 0             │ Local only
list              │ <100ms    │ 1-2           │ List deployments
status (single)   │ <500ms    │ 2-3           │ Get deployment + pods
status (all)      │ <1s       │ 3-5           │ List all resources
deploy            │ 10-60s    │ 5-10          │ Apply + rollout
build             │ 1-10min   │ 0             │ Local Docker build
build --push      │ 2-15min   │ 1             │ Build + push
logs -f           │ ∞         │ 1 (stream)    │ Continuous stream
restart           │ 10-60s    │ 3-5           │ Rollout restart
scale             │ <5s       │ 2-3           │ Scale + verify
exec              │ ∞         │ 1 (stream)    │ Interactive session
test              │ 1-60s     │ 2-5           │ Depends on tests
```

## Extension Points

The CLI is designed to be extensible:

```
Extension Areas:
├─► New Commands
│   └─► Add cmd_* function + router entry
│
├─► New Flags
│   └─► Parse in main() + pass to commands
│
├─► Custom Output Formats
│   └─► Add format functions (JSON, YAML, table)
│
├─► Additional Integrations
│   └─► Helm, Kustomize, ArgoCD, etc.
│
└─► Plugin System (future)
    └─► Load external command modules
```

## Deployment Strategies Support

```
Current:
└─► Rolling Update (default Kubernetes behavior)

Planned:
├─► Blue-Green Deployment
├─► Canary Deployment
├─► A/B Testing
└─► Progressive Delivery
```

---

For implementation details, see [cortex-k8s](cortex-k8s) source code.
For usage examples, see [examples/](examples/) directory.
