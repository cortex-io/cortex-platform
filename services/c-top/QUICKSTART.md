# Cortex Live - Quick Start Guide

## Installation (5 minutes)

### Option 1: Local Installation
```bash
cd /Users/ryandahlberg/Projects/cortex-platform/services/cortex-live
pip3 install -e .
cortex-live
```

### Option 2: Docker
```bash
cd /Users/ryandahlberg/Projects/cortex-platform/services/cortex-live
docker build -t cortex-live:latest .
docker run -it --rm -v ~/.kube:/root/.kube cortex-live:latest
```

### Option 3: Python Module
```bash
cd /Users/ryandahlberg/Projects/cortex-platform/services/cortex-live
python3 -m cortex_live
```

## First Run

1. **Ensure kubeconfig is configured**:
   ```bash
   kubectl get nodes  # Should work
   ```

2. **Launch Cortex Live**:
   ```bash
   cortex-live
   ```

3. **You should see**:
   - Cluster pulse with CPU/Memory metrics
   - Live event stream
   - Agents panel (Kubernetes Jobs)
   - Nodes panel with metrics

## Navigation Cheat Sheet

### Main Dashboard
- **View**: Cluster overview with real-time metrics
- **Refresh**: Auto-updates every 2 seconds
- **Quit**: Press `q`

### Drill-Down Views
| Key | View | What You See |
|-----|------|-------------|
| `p` | Pods | All pods: namespace, name, status, restarts, age, node |
| `n` | Nodes | All nodes: name, status, roles, CPU, memory, pods, age |
| `a` | Agents | All jobs: namespace, name, status, completions, duration |
| `l` | Logs | Select pod → stream logs (tail 100 lines) |
| `/` | Search | Search pods, nodes, events |

### In Any View
- **Return to Dashboard**: Press `ESC` or `q`
- **Navigate Table**: Arrow keys, Page Up/Down

### In Agents View (Special)
- `a` - Filter: Active jobs only
- `c` - Filter: Completed jobs only
- `f` - Filter: Failed jobs only
- `x` - Filter: All jobs

## Quick Tests

### Test 1: View All Pods
```
1. Press 'p'
2. See all pods in a table
3. Press ESC to return
```

### Test 2: Check Node Metrics
```
1. Press 'n'
2. See CPU/Memory from Prometheus
3. Press ESC to return
```

### Test 3: Stream Pod Logs
```
1. Press 'l'
2. Arrow down to select a pod
3. Press Enter
4. See logs streaming
5. Press ESC to return
```

### Test 4: Search
```
1. Press '/'
2. Type 'cortex'
3. Press Enter
4. See filtered results
5. Press ESC to return
```

## Troubleshooting

### "Config error" on startup
**Fix**: Ensure kubeconfig is valid
```bash
export KUBECONFIG=~/.kube/config
kubectl cluster-info
```

### "Failed to connect to Prometheus"
**Expected**: Metrics will fall back to hardcoded values
**Fix** (optional): Deploy Prometheus or set custom URL
```bash
export PROMETHEUS_URL=http://your-prometheus:9090
cortex-live
```

### No data in tables
**Fix**: Check RBAC permissions
```bash
kubectl auth can-i list pods --all-namespaces
kubectl auth can-i list nodes
```

### Blank screen
**Fix**: Terminal size too small
```bash
# Resize terminal to at least 80x24
# Or use full screen
```

## Configuration

### Environment Variables
```bash
# Prometheus URL (default: http://prometheus-server.cortex-system:80)
export PROMETHEUS_URL=http://custom-prometheus:9090

# Kubernetes config (default: auto-detect)
export KUBECONFIG=/path/to/kubeconfig

# Python unbuffered output (recommended)
export PYTHONUNBUFFERED=1

# Terminal type (for best display)
export TERM=xterm-256color
```

### Run with custom Prometheus
```bash
PROMETHEUS_URL=http://10.43.0.1:9090 cortex-live
```

## Performance Tips

1. **Large Clusters (100+ nodes)**:
   - Initial load may take 2-5 seconds
   - Tables will populate after first refresh

2. **Slow Log Streaming**:
   - Normal for pods with high log volume
   - Switch to a different pod if needed

3. **High CPU Usage**:
   - Expected: TUI renders every 2 seconds
   - Use `top` to monitor

## What to Expect

### Dashboard Metrics (Every 2 Seconds)
- ✅ CPU/Memory from Prometheus (or fallback)
- ✅ Pod counts (ready/total)
- ✅ Events per minute
- ✅ Active/completed/failed agents
- ✅ Node count and metrics

### Drill-Down Views (Every 2 Seconds)
- ✅ Pods table refreshes
- ✅ Nodes table refreshes
- ✅ Agents table refreshes
- ✅ Logs stream updates

## Next Steps

1. **Explore all views**: Press each key (p, n, a, l, /)
2. **Check Prometheus metrics**: Verify CPU/Memory values
3. **Stream logs**: Select a busy pod and watch logs
4. **Search functionality**: Try searching for namespaces
5. **Filter agents**: Use a, c, f, x keys in agents view

## Common Questions

**Q: Why do metrics show 68% CPU and 41% memory?**
A: These are fallback values when Prometheus is unavailable. Deploy Prometheus for real metrics.

**Q: Can I run this remotely?**
A: Yes! SSH with terminal forwarding: `ssh -t user@host cortex-live`

**Q: How do I exit?**
A: Press `q` from any screen

**Q: Can I customize the refresh rate?**
A: Yes, edit `app.py` line 174: `self.set_interval(2, self.update_all)` (change `2` to desired seconds)

**Q: Does this work with other Kubernetes clusters?**
A: Yes! Works with any cluster where kubectl is configured.

## Development Mode

### Make Changes
```bash
cd /Users/ryandahlberg/Projects/cortex-platform/services/cortex-live
vim src/cortex_live/app.py  # Edit files
cortex-live  # Changes are live (pip install -e .)
```

### Enable Debug Logging
```python
# In src/cortex_live/app.py, line 18:
logging.basicConfig(level=logging.DEBUG)  # Change INFO to DEBUG
```

### Test Installation
```bash
./test_install.sh
```

## Support

- Check `README.md` for full documentation
- Check `FEATURES.md` for feature details
- View logs: `cortex-live 2>&1 | tee cortex-live.log`

---

**Quick Start Complete!**
You're ready to monitor your k3s cluster in real-time with Cortex Live.

Press `q` to quit anytime.
