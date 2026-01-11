# Sandfly Grafana Dashboard - Coordination Plan

**Coordinator:** Larry (Coordination Agent)
**Date:** 2025-12-26
**Project:** Comprehensive Sandfly Security Grafana Dashboard

## Objective
Create a comprehensive Grafana dashboard for Sandfly Security monitoring with full API metric coverage.

## Current State
- **Sandfly Instance:** 10.88.140.176
- **Exporter Location:** `/Users/ryandahlberg/Projects/cortex/k3s-deployments/monitoring/sandfly-exporter.yaml`
- **Dashboard Target:** `/Users/ryandahlberg/Projects/cortex/k3s-deployments/monitoring/grafana-dashboards/sandfly-security.json`
- **Exporter Service:** sandfly-exporter.monitoring.svc.cluster.local:9131

### Current Metrics
- sandfly_results_total: 101
- sandfly_info{version="5.5.4"}
- sandfly_hosts_total, sandfly_hosts_online, sandfly_hosts_offline
- sandfly_results_pass, sandfly_results_fail, sandfly_results_error
- sandfly_host_results{hostname, ip}
- sandfly_scrape_duration_seconds

### Authentication
- Username: admin
- Password: emphasize-art-nibble-arguable-paradox-flick-unpack
- Host: 10.88.140.176
- SSL Verify: false

## Agent Assignments

### Daryl-1: API Research Specialist
**Task:** Research Sandfly API and document all available endpoints and metrics
**Deliverable:** Comprehensive API documentation including:
- All available API endpoints at https://10.88.140.176/v4
- Data structures and fields for each endpoint
- Metrics that should be exposed to Prometheus
- Rate limits and pagination details
**Output File:** `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/SANDFLY_API_RESEARCH.md`

### Daryl-2: Exporter Enhancement Specialist
**Task:** Expand the Prometheus exporter with all useful metrics from Sandfly API
**Dependencies:** Requires Daryl-1's API research
**Deliverable:** Enhanced exporter.py script including:
- All host metrics (status, last scan, vulnerabilities)
- All scan results and findings
- Alert/threat detection metrics
- Policy and sandbox metrics
- System health and performance metrics
**Target File:** `/Users/ryandahlberg/Projects/cortex/k3s-deployments/monitoring/sandfly-exporter.yaml`

### Daryl-3: Dashboard Creation Specialist
**Task:** Create comprehensive Grafana dashboard JSON
**Dependencies:** Requires Daryl-2's metrics expansion
**Deliverable:** Production-ready Grafana dashboard with:
- Overview panel (total hosts, online/offline, scan status)
- Alerts panel (failed scans, errors, threat detections)
- Host breakdown (per-host metrics and scan results)
- Scan activity timeline
- Security findings over time
- System health metrics
**Target File:** `/Users/ryandahlberg/Projects/cortex/k3s-deployments/monitoring/grafana-dashboards/sandfly-security.json`

## Dashboard Requirements

### Must-Have Panels
1. **Overview Stats**
   - Total monitored hosts
   - Online/Offline hosts
   - Active scans
   - Total threats detected

2. **Alert Panel**
   - Failed scans (red threshold)
   - Scan errors (yellow threshold)
   - Critical threats (red)
   - Warning-level findings (yellow)

3. **Host Breakdown Table**
   - Hostname
   - IP address
   - Status (online/offline)
   - Last scan time
   - Threats detected
   - Scan results

4. **Timeline Visualizations**
   - Scan activity over time (line/bar chart)
   - Threats detected over time
   - Host status changes

5. **Security Findings**
   - Breakdown by severity
   - Breakdown by category
   - Top affected hosts

6. **System Health**
   - Exporter scrape duration
   - Scrape errors
   - API response times
   - Data freshness

### Design Guidelines
- Use Grafana 10.0+ panel types
- Follow Cloudflare dashboard style (reference: cloudflare-analytics.json)
- Use color coding: green (good), yellow (warning), red (critical)
- Include proper thresholds for alerts
- Use time range variables for flexibility
- Include helpful descriptions in panel titles

## Coordination Notes
- Work must proceed sequentially: Research -> Exporter -> Dashboard
- Each agent should validate their output before marking complete
- Larry will verify integration between components
- Final deployment will be validated with live metrics

## Success Criteria
- [ ] All Sandfly API endpoints researched and documented
- [ ] Exporter collecting comprehensive metrics
- [ ] Dashboard displays all critical security metrics
- [ ] Dashboard is visually appealing and easy to understand
- [ ] Metrics update in real-time (60s interval)
- [ ] No scrape errors in Prometheus
