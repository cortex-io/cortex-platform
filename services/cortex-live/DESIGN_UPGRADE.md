# Cortex Live Design Upgrade v2.1

## Changes Applied

### ✅ Fixed Border Connectivity
- **Problem**: Borders weren't connecting properly because content width was dynamic
- **Solution**: Added `BORDER_WIDTH` constants to each widget for fixed-width rendering
- All borders now use consistent box-drawing characters:
  - `┏━━┓` (top)
  - `┃  ┃` (sides)
  - `┗━━┛` (bottom)
  - `┣━━┫` (section separators)

### ✅ Enhanced Color Scheme
- **Cyan (`#00d9ff`)**: Primary accent, borders, branding
- **Magenta**: Node markers, k3s badge
- **Dark background (`#0a0e14`)**: Deep space aesthetic
- **Smart coloring**: Metrics change color based on thresholds
  - Green: < 50%
  - Yellow: 50-75%
  - Red: > 75%

### ✅ New Metrics Added

#### Cluster Pulse Panel
- ✅ **Network I/O**: ↓ Download / ↑ Upload (bytes/sec)
  - Formatted in KB/MB/GB
  - Green for download, Magenta for upload
  - Currently placeholder (0 B/s), ready for Prometheus integration

#### Agents Panel
- ✅ **Namespaces**: Count of unique namespaces containing jobs
  - Shows job distribution across namespaces

#### Nodes Panel
- ✅ **Disk Usage**: Ready to display per-node disk utilization
  - Currently in data structure, awaiting Prometheus metrics

### ✅ Fixed Widget Dimensions

| Widget | Border Width | Max Rows | Height |
|--------|--------------|----------|--------|
| ClusterPulse | 64 chars | 4 lines | 8 |
| LiveEvents | 64 chars | 5 events | 10 |
| AgentsPanel | 32 chars | 8 lines | 12 |
| NodesPanel | 46 chars | 4 nodes | 12 |

### ✅ Improved Icons
- `⬢` - Cortex logo (hexagon)
- `◉` - Cluster pulse
- `⚡` - Live events
- `⚙` - Agents
- `⬢` - Nodes header
- `◆` - Individual nodes
- `↓` - Network download
- `↑` - Network upload

## Technical Implementation

### Border Rendering Pattern
```python
BORDER_WIDTH = 64  # Fixed width

def render(self):
    text = Text()

    # Top border
    text.append("┏", style="bold cyan")
    text.append("━" * self.BORDER_WIDTH, style="bold cyan")
    text.append("┓\n", style="bold cyan")

    # Content with padding
    text.append("┃", style="bold cyan")
    text.append(content, style="...")
    padding = self.BORDER_WIDTH - len(content)
    text.append(" " * padding, style="")
    text.append("┃\n", style="bold cyan")

    # Bottom border
    text.append("┗", style="bold cyan")
    text.append("━" * self.BORDER_WIDTH, style="bold cyan")
    text.append("┛", style="bold cyan")
```

### Fixed-Row Rendering
All panels now render a **fixed number of rows** to maintain border alignment:
- Empty rows are filled with spaces
- Content is truncated if it exceeds max rows
- Borders remain stable regardless of data

## Future Enhancements

### Network I/O (Ready for Integration)
Add to `api.py`:
```python
def get_network_io(self) -> dict:
    """Get cluster network I/O from Prometheus"""
    query_in = 'sum(rate(node_network_receive_bytes_total[1m]))'
    query_out = 'sum(rate(node_network_transmit_bytes_total[1m]))'
    # Return bytes/sec
```

### Disk Usage (Ready for Integration)
Add to `api.py`:
```python
def get_node_disk(self, node_name: str) -> int:
    """Get node disk usage percentage"""
    query = f'(1 - (node_filesystem_avail_bytes{{instance=~"{node_name}.*"}} / node_filesystem_size_bytes{{instance=~"{node_name}.*"}})) * 100'
    # Return percentage
```

### API Latency (Future)
Could add to status bar:
- Kubernetes API response time
- Prometheus query latency
- Shows system health at a glance

### Pod Distribution (Future)
New panel showing:
- Pods per namespace (horizontal bar chart)
- Top 5 busiest namespaces
- Color-coded by resource usage

## Testing

Launch cortex-live and verify:
1. ✅ All borders connect fully around each panel
2. ✅ Borders remain stable when metrics update
3. ✅ Colors change based on metric thresholds
4. ✅ Network I/O shows "0.0B/s" (placeholder)
5. ✅ Namespaces count appears in Agents panel
6. ✅ Panel sizes are consistent and aligned

## Files Modified

- `src/cortex_live/widgets.py` - All widget rendering with fixed borders
- `src/cortex_live/app.py` - CSS heights, network/namespace metrics
- `DESIGN_UPGRADE.md` - This documentation

## Version

**Cortex Live v2.1** - "Connected Borders" Edition

---

**Design Philosophy**: Minimalist meets Cortex
- Neural network aesthetic
- Data-driven color changes
- Clean, readable layout
- Professional monitoring tool
