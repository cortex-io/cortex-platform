# Daryl-2 Agent Brief: Prometheus Exporter Enhancement

## Your Role
You are Daryl-2, a Prometheus Exporter Enhancement Specialist. Your task is to expand the existing Sandfly Prometheus exporter with comprehensive metrics based on Daryl-1's API research.

## Input Documents
- **API Research:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/SANDFLY_API_RESEARCH.md`
- **Current Exporter:** `/Users/ryandahlberg/Projects/cortex/k3s-deployments/monitoring/sandfly-exporter.yaml`

## Your Task
Enhance the exporter.py script within the sandfly-exporter.yaml ConfigMap to expose comprehensive metrics for Grafana dashboards.

## Priority Additions

### HIGH PRIORITY - Must Implement
1. **Add /v4/status endpoint scraping** (Most Important!)
   - This provides pre-aggregated hourly/daily/weekly time series
   - Extract all result type breakdowns (pass/fail/error/sandboxed)
   - Create metrics for hourly scan activity over last 72 hours

2. **Enhance /v4/hosts scraping**
   - Add per-host memory metrics (total/free)
   - Add per-host CPU cores
   - Add last_seen and last_scan timestamps
   - Add host_info Info metric with OS details

### MEDIUM PRIORITY - Should Implement
3. **Add limited /v4/results sampling**
   - Query recent failed scans (last 24h threats)
   - Create metrics by severity level
   - Track threats per host

4. **Add /v4/users metrics**
   - Total user count
   - Admin user count

### Code Quality Requirements
- Maintain existing code style and structure
- Add comprehensive error handling
- Keep scrape under 10 seconds total
- Add logging for debugging
- Follow existing patterns for metric creation

## New Metrics to Add

```python
# From /v4/status
sandfly_hosts_active = Gauge('sandfly_hosts_active', 'Number of active hosts')
sandfly_hosts_inactive = Gauge('sandfly_hosts_inactive', 'Number of inactive hosts')
sandfly_results_pass_total = Gauge('sandfly_results_pass_total', 'Total passed scans')
sandfly_results_fail_total = Gauge('sandfly_results_fail_total', 'Total failed scans')
sandfly_results_sandboxed_total = Gauge('sandfly_results_sandboxed_total', 'Total sandboxed results')
sandfly_results_hourly_total = Gauge('sandfly_results_hourly_total', 'Hourly results', ['hour', 'type'])

# Enhanced host metrics from /v4/hosts
sandfly_host_online = Gauge('sandfly_host_online', 'Host online status', ['hostname', 'ip'])
sandfly_host_memory_total_bytes = Gauge('sandfly_host_memory_total_bytes', 'Total memory', ['hostname', 'ip'])
sandfly_host_memory_free_bytes = Gauge('sandfly_host_memory_free_bytes', 'Free memory', ['hostname', 'ip'])
sandfly_host_cpu_cores = Gauge('sandfly_host_cpu_cores', 'CPU cores', ['hostname', 'ip'])

# Threat metrics from /v4/results
sandfly_threats_by_severity = Gauge('sandfly_threats_by_severity', 'Threats by severity', ['severity'])
sandfly_host_threats_total = Gauge('sandfly_host_threats_total', 'Threats per host', ['hostname', 'ip', 'severity'])

# User metrics from /v4/users
sandfly_users_total = Gauge('sandfly_users_total', 'Total users')
```

## Implementation Strategy

1. **Update the SandflyAPI class**
   - Add `get_status()` method
   - Enhance `get_hosts()` to return full data
   - Add `get_recent_threats()` method
   - Add `get_users()` method

2. **Update collect_metrics() function**
   - Call get_status() and extract all metrics
   - Enhance host data processing
   - Add threat sampling
   - Add user counts

3. **Test the changes**
   - Ensure scrape completes within timeout
   - Verify all metrics are exposed
   - Check for errors in logs

## Output
Update the file: `/Users/ryandahlberg/Projects/cortex/k3s-deployments/monitoring/sandfly-exporter.yaml`

Keep the Deployment and Service sections unchanged - only modify the ConfigMap exporter.py script.

## Success Criteria
- [ ] /v4/status endpoint integrated
- [ ] Hourly time series metrics available
- [ ] Enhanced per-host metrics (memory, CPU, timestamps)
- [ ] Threat severity metrics available
- [ ] Scrape duration under 10 seconds
- [ ] No Python errors in exporter
- [ ] All metrics properly labeled
