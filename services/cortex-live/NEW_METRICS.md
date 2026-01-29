# Cortex Live v2.2 - Complete Metrics Suite

## All Requested Metrics Implemented ✅

### 1. Network I/O (bytes in/out per second) ✅
**Location**: Cluster Pulse panel
**Display**: `↓ 1.2MB/s  ↑ 856.3KB/s`

**Implementation**:
- Queries Prometheus for network receive/transmit rates
- Excludes virtual interfaces (lo, veth, docker, flannel, cali)
- Auto-formats: B → KB → MB → GB → TB
- Green for download (↓), Magenta for upload (↑)
- Updates every 2 seconds

**Prometheus Queries**:
```promql
# Download rate
sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|flannel.*|cali.*"}[1m]))

# Upload rate
sum(rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|flannel.*|cali.*"}[1m]))
```

---

### 2. Disk Usage (per node) ✅
**Location**: Nodes panel
**Display**: Each node shows CPU | MEM | DISK with color-coded bars

**Example**:
```
◆ master01    ██████ 67%  ██████ 54%  ███░░░ 45%
              └─CPU   └─MEM    └─DISK
```

**Implementation**:
- Queries root filesystem usage per node
- Excludes tmpfs filesystems
- Color-coded: Green (<50%), Yellow (50-75%), Red (>75%)
- 6-character progress bars for each metric
- Updates every 2 seconds

**Prometheus Query**:
```promql
(1 - (node_filesystem_avail_bytes{instance=~"{node}.*",mountpoint="/",fstype!="tmpfs"} /
      node_filesystem_size_bytes{instance=~"{node}.*",mountpoint="/",fstype!="tmpfs"})) * 100
```

---

### 3. Pod Distribution (pods per namespace) ✅
**Location**: New panel between Events and Agents
**Display**: Top 5 namespaces with horizontal bar chart

**Example**:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📦 POD DISTRIBUTION                                              ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ cortex-system     ████████████████░░░░░░░░░░░░░░  52% (120 pods) ┃
┃ kube-system       ████████░░░░░░░░░░░░░░░░░░░░░░  28% (65 pods)  ┃
┃ cortex-chat       ████░░░░░░░░░░░░░░░░░░░░░░░░░░  12% (28 pods)  ┃
┃ monitoring        ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░   5% (12 pods)  ┃
┃ default           █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3% (7 pods)   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Implementation**:
- Counts pods per namespace
- Sorts by count (descending)
- Shows top 5 namespaces
- Displays percentage of total pods
- 30-character horizontal bar chart
- Updates every 2 seconds

**Data Source**: Kubernetes API `list_pod_for_all_namespaces()`

---

### 4. API Latency (Kubernetes API response times) ✅
**Location**: Status bar (top right)
**Display**: `⚡ 45ms` (color-coded)

**Implementation**:
- Shows p95 API server request duration
- Excludes WATCH requests (long-running)
- Color-coded:
  - Green: < 100ms
  - Yellow: 100-500ms
  - Red: > 500ms
- Updates every 2 seconds

**Prometheus Query**:
```promql
histogram_quantile(0.95,
  sum(rate(apiserver_request_duration_seconds_bucket{verb!="WATCH"}[5m])) by (le)
) * 1000  # Convert to milliseconds
```

---

## Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ ⬢ CORTEX LIVE                   ⚡ 45ms │ ▲ 7 nodes │ k3s     │ ← API Latency
├──────────────────────────────────────────────────────────────────┤
│ ◉ CLUSTER PULSE                                                  │
│ ████████████████████ CPU 68%    Pods 186/235 ready              │
│ ████████████░░░░░░░░ MEM 41%    Events 60/min                   │
│ ↓ 1.2MB/s  ↑ 856.3KB/s                                          │ ← Network I/O
├──────────────────────────────────────────────────────────────────┤
│ ⚡ LIVE EVENTS                                                   │
│ 13:16:27 │ ! cortex-chat         │ OperationComplete           │
│ ...                                                              │
├──────────────────────────────────────────────────────────────────┤
│ 📦 POD DISTRIBUTION                                              │ ← NEW!
│ cortex-system     ████████████████░░░░░░  52% (120 pods)       │
│ kube-system       ████████░░░░░░░░░░░░░░  28% (65 pods)        │
│ ...                                                              │
├─────────────────────────────┬────────────────────────────────────┤
│ ⚙ AGENTS                    │ ⬢ NODES                           │
│ Active:       10            │ ◆ master01  ██ 67% ██ 54% █ 45%  │ ← Disk Usage
│ ...                         │ ◆ master02  ██ 67% ██ 54% █ 42%  │
│                             │ ◆ master03  ██ 67% ██ 54% █ 38%  │
│                             │ ◆ worker01  ██ 67% ██ 54% █ 51%  │
└─────────────────────────────┴────────────────────────────────────┘
```

---

## Files Modified

### api.py
- ✅ Added `get_network_io()` - Network I/O metrics
- ✅ Added `get_node_disk_usage()` - Per-node disk usage
- ✅ Added `get_api_latency()` - API response time
- ✅ Added `get_pod_distribution()` - Pods per namespace
- ✅ Added `get_namespaces()` - List all namespaces

### widgets.py
- ✅ Updated `StatusBar` - Added API latency display
- ✅ Updated `ClusterPulse` - Added network I/O row
- ✅ Updated `NodesPanel` - Added disk usage column (widened to 56 chars)
- ✅ Added `PodDistribution` - New widget for pod distribution

### app.py
- ✅ Added `PodDistribution` to compose()
- ✅ Updated CSS for new panel
- ✅ Updated `update_all()` to fetch all new metrics
- ✅ Wired up API latency to status bar
- ✅ Wired up network I/O to cluster pulse
- ✅ Wired up disk usage to nodes panel
- ✅ Wired up pod distribution to new panel

---

## Prometheus Requirements

For all metrics to work, ensure these Prometheus metrics are available:

### Node Exporter (required for most metrics)
```bash
# Usually deployed with kube-prometheus-stack
kubectl get pods -n monitoring | grep node-exporter
```

**Metrics needed**:
- `node_network_receive_bytes_total`
- `node_network_transmit_bytes_total`
- `node_filesystem_avail_bytes`
- `node_filesystem_size_bytes`

### API Server Metrics (for latency)
```bash
# Built into kube-apiserver
```

**Metrics needed**:
- `apiserver_request_duration_seconds_bucket`

### Fallback Behavior

If Prometheus is unavailable or metrics are missing:
- Network I/O: Shows `0.0B/s`
- Disk usage: Shows `0%`
- API latency: Not displayed
- All other metrics: Use hardcoded fallback values

---

## Testing

### Verify Prometheus Connection
```bash
# Check if Prometheus is accessible
kubectl port-forward -n cortex-system svc/prometheus-server 9090:80

# Open browser: http://localhost:9090
# Test query: node_network_receive_bytes_total
```

### Test Each Metric

1. **Network I/O**:
   - Look for `↓ X.XMB/s  ↑ X.XKB/s` in Cluster Pulse
   - Should show real-time network traffic

2. **Disk Usage**:
   - Look for third bar in each node row
   - Should show percentage (color-coded)

3. **Pod Distribution**:
   - New panel between Events and Agents
   - Should show top 5 namespaces with bar charts

4. **API Latency**:
   - Look for `⚡ XXms` in status bar (top right)
   - Should be green if cluster is healthy

---

## Performance Impact

- **API Calls per Update** (2 second interval):
  - 1x get_nodes()
  - 1x get_pods()
  - 1x get_jobs()
  - 1x get_events()
  - 4x get_node_metrics() (per node)
  - 4x get_node_disk_usage() (per node)
  - 1x get_network_io()
  - 1x get_api_latency()
  - 1x get_pod_distribution()

**Total**: ~13 Prometheus queries + 4 Kubernetes API calls per refresh

**Optimization**: All metrics use cached data from the same 2-second update cycle.

---

## Version History

- **v2.0** - Initial release with basic metrics
- **v2.1** - Connected borders, color scheme
- **v2.2** - **Complete metrics suite** ← Current
  - Network I/O
  - Disk usage per node
  - Pod distribution by namespace
  - API latency indicator

---

## What's Next?

Potential future enhancements:
- Historical graphs (CPU/Memory over time)
- Alert thresholds (configurable red/yellow/green)
- Custom metric queries
- Export to Grafana
- Log streaming from multiple pods
- Resource quotas per namespace

---

**Status**: All requested metrics implemented and ready to test! 🎉
