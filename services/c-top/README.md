# Cortex Live

**Real-time k3s cluster monitoring TUI**

Cortex Live is a Terminal User Interface (TUI) for monitoring your Kubernetes cluster in real-time. It provides a beautiful, interactive dashboard with live metrics, events, and drill-down views.

## Features

### Dashboard (Main Screen)
- **Cluster Pulse**: Real-time CPU and memory metrics from Prometheus
- **Live Events**: Streaming cluster events
- **Agents Panel**: Kubernetes Jobs status and metrics
- **Nodes Panel**: Node health and resource usage

### Drill-Down Views
- **Pods View** (`p`): Scrollable table of all pods with namespace, name, status, restarts, age, and node
- **Nodes View** (`n`): Detailed node information with CPU/memory from Prometheus
- **Agents View** (`a`): All Kubernetes Jobs with filtering (active/completed/failed)
- **Logs View** (`l`): Select pods and stream logs in real-time
- **Search** (`/`): Search across pods, nodes, namespaces, and events

## Installation

### Local Development

```bash
# Install in development mode
pip install -e .

# Run the TUI
cortex-live
```

### Docker

```bash
# Build the image
docker build -t cortex-live:latest .

# Run in cluster (with kubeconfig mounted)
docker run -it --rm \
  -v ~/.kube:/root/.kube \
  cortex-live:latest
```

### Kubernetes Deployment

```bash
# Deploy to cluster
kubectl apply -f k8s/deployment.yaml

# Access via exec
kubectl exec -it -n cortex-system deployment/cortex-live -- cortex-live
```

## Configuration

### Prometheus Integration

By default, Cortex Live connects to Prometheus at:
```
http://prometheus-server.cortex-system:80
```

To override, set the `PROMETHEUS_URL` environment variable:
```bash
export PROMETHEUS_URL=http://custom-prometheus:9090
cortex-live
```

### Kubernetes Authentication

Cortex Live uses the standard Kubernetes client authentication:
1. In-cluster config (when running in a pod)
2. ~/.kube/config (when running locally)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit application or return to dashboard |
| `p` | Open Pods view |
| `n` | Open Nodes view |
| `a` | Open Agents (Jobs) view |
| `l` | Open Logs view |
| `/` | Open Search |
| `r` | Force refresh |
| `ESC` | Return to dashboard (from any view) |

### Agents View Filters
| Key | Action |
|-----|--------|
| `a` | Show only active jobs |
| `c` | Show only completed jobs |
| `f` | Show only failed jobs |
| `x` | Show all jobs |

## Architecture

```
cortex-live/
├── src/
│   └── cortex_live/
│       ├── __init__.py       # Package metadata
│       ├── __main__.py       # Module entry point
│       ├── app.py            # Main application
│       ├── screens.py        # All screen classes
│       ├── widgets.py        # Custom widgets
│       └── api.py            # Prometheus/K8s clients
├── pyproject.toml            # Project dependencies
├── Dockerfile                # Container image
└── README.md                 # This file
```

## Dependencies

- **textual**: TUI framework
- **kubernetes**: Kubernetes Python client
- **prometheus-api-client**: Prometheus query client

## Error Handling

Cortex Live includes graceful fallback behavior:
- **Prometheus unavailable**: Falls back to hardcoded metrics
- **Kubernetes API errors**: Shows error notifications
- **Missing permissions**: Displays helpful error messages

## Auto-Refresh

All views auto-refresh every 2 seconds:
- Dashboard metrics
- Pods table
- Nodes table
- Agents table
- Log streaming

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (TODO)
pytest
```

### Code Formatting

```bash
# Format with black
black src/

# Type checking
mypy src/
```

## Troubleshooting

### "Config error" on startup
- Ensure you have a valid kubeconfig at ~/.kube/config
- Or run inside a Kubernetes pod with appropriate ServiceAccount

### "Failed to connect to Prometheus"
- Check Prometheus is running: `kubectl get pods -n cortex-system`
- Verify the URL is correct
- Metrics will fall back to hardcoded values

### Blank screens or no data
- Check RBAC permissions for the ServiceAccount
- Verify cluster resources exist (pods, nodes, jobs)

## License

Internal Cortex project - not for external distribution

## Version History

- **2.0.0**: Complete rewrite with modular architecture
  - Added Prometheus integration
  - Implemented all drill-down views (pods, nodes, agents, logs, search)
  - Added real-time log streaming
  - Added search functionality
  - Improved error handling

- **1.0.0**: Initial release
  - Basic dashboard with hardcoded metrics
  - Stub views for drill-downs
