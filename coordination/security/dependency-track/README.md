# Dependency-Track Integration for Cortex Security

Complete centralized vulnerability management platform integrated with Cortex CVE scanning infrastructure.

## Overview

Dependency-Track is an open-source Component Analysis platform that provides:

- **Centralized Vulnerability Management**: Portfolio-wide visibility across all repositories
- **SBOM Analysis**: Automated analysis of CycloneDX SBOMs
- **Multiple Vulnerability Sources**: NVD, GitHub Advisories, OSS Index
- **CISA KEV Integration**: Known Exploited Vulnerabilities catalog
- **EPSS Integration**: Exploit Prediction Scoring System
- **Metrics & Reporting**: Risk scores, trending, and compliance reporting
- **Policy Engine**: Define security policies and track violations
- **REST API**: Full automation capabilities

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Cortex Security                         │
│                                                              │
│  ┌──────────────┐        ┌─────────────────┐               │
│  │ CVE Scanner  │───────>│  SBOM Files     │               │
│  │  (Parallel)  │        │ (CycloneDX 1.6) │               │
│  └──────────────┘        └────────┬────────┘               │
│                                    │                         │
│                                    v                         │
│                          ┌─────────────────┐                │
│                          │ Upload Script   │                │
│                          └────────┬────────┘                │
│                                   │                          │
│                                   v                          │
│         ┌─────────────────────────────────────────┐         │
│         │      Dependency-Track Platform          │         │
│         │  ┌──────────┐  ┌──────────┐             │         │
│         │  │ Frontend │  │   API    │             │         │
│         │  │  :8082   │  │  :8081   │             │         │
│         │  └──────────┘  └─────┬────┘             │         │
│         │                      │                   │         │
│         │  ┌──────────────────v────────────────┐  │         │
│         │  │     Vulnerability Analysis        │  │         │
│         │  │  • NVD  • GitHub  • OSS Index    │  │         │
│         │  │  • CISA KEV  • EPSS              │  │         │
│         │  └──────────────────┬────────────────┘  │         │
│         │                     │                    │         │
│         │  ┌──────────────────v────────────────┐  │         │
│         │  │      PostgreSQL Database          │  │         │
│         │  └───────────────────────────────────┘  │         │
│         └─────────────────────────────────────────┘         │
│                          │                                   │
│                          │ Webhooks                          │
│                          v                                   │
│                ┌─────────────────┐                          │
│                │ Webhook Handler │                          │
│                └────────┬────────┘                          │
│                         │                                    │
│                         v                                    │
│              ┌──────────────────┐                           │
│              │ Cortex Events    │                           │
│              │ Security Tasks   │                           │
│              └──────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- jq (JSON processor)
- 4GB+ RAM available for Docker

### 2. Deploy Dependency-Track

```bash
cd /Users/ryandahlberg/Projects/cortex
./scripts/security/dependency-track-setup.sh
```

This will:
1. Check prerequisites
2. Start Docker containers (API server, Frontend, PostgreSQL)
3. Wait for initialization (2-5 minutes)
4. Guide you through API key creation
5. Create projects for your repositories
6. Upload initial SBOMs

### 3. Access the Platform

- **Web UI**: http://localhost:8082
- **API**: http://localhost:8081
- **Default credentials**: admin / admin (you'll be prompted to change)

### 4. Configure API Key

After first login:

1. Navigate to: **Administration → Access Management → Teams**
2. Click on **Administrators** team
3. Go to **API Keys** tab
4. Click **Create API Key**
5. Save the key to: `~/.cortex/dtrack-api-key`

```bash
mkdir -p ~/.cortex
echo "your-api-key-here" > ~/.cortex/dtrack-api-key
chmod 600 ~/.cortex/dtrack-api-key
```

## Usage

### Automated Vulnerability Scanning

Run the integrated workflow that scans all repos and uploads to Dependency-Track:

```bash
./scripts/security/integrated-vulnerability-scan.sh
```

This executes:
1. Parallel CVE scanning across all repositories
2. SBOM generation (CycloneDX 1.6 format)
3. Automatic upload to Dependency-Track
4. Portfolio security report generation

**Options**:
- `--skip-scan`: Use existing SBOMs without re-scanning
- `--skip-upload`: Skip Dependency-Track upload
- `--skip-report`: Skip report generation

### Manual SBOM Upload

Upload SBOMs to Dependency-Track:

```bash
./scripts/security/dependency-track-upload-sboms.sh
```

Automatically discovers and uploads:
- `cortex-sbom-*.json` → cortex project
- `driveiq-backend-sbom-*.json` → driveiq-backend project
- `driveiq-frontend-sbom-*.json` → driveiq-frontend project
- `blog-sbom-*.json` → blog project

### Generate Portfolio Report

```bash
./scripts/security/dependency-track-report.sh
```

Generates:
- Text report: `coordination/security/dependency-track/reports/portfolio-report-*.txt`
- JSON report: `coordination/security/dependency-track/reports/portfolio-report-*.json`

Includes:
- Portfolio-wide vulnerability counts
- Per-project metrics and risk scores
- Severity breakdown (Critical, High, Medium, Low)
- Component counts

### Real-time Notifications

Start the webhook server to receive real-time alerts:

```bash
./scripts/security/dependency-track-webhook-server.sh
```

Then configure in Dependency-Track UI:
1. Go to **Administration → Notifications → Alerts**
2. Click **Create Notification**
3. Configure:
   - **Name**: Cortex Security Webhook
   - **Scope**: Portfolio
   - **Level**: All
   - **Publisher**: Webhook
   - **Destination**: http://host.docker.internal:8888/webhook
   - **Groups**: Select all relevant groups

Webhooks automatically:
- Create Cortex security events
- Generate tasks for critical/high vulnerabilities
- Log to `coordination/security/dependency-track/webhook-log.jsonl`
- Emit to `coordination/dashboard-events.jsonl`

## Configuration

### Project Structure

Projects are automatically created with these mappings:

| Repository | Project Name | Version | Ecosystems |
|------------|--------------|---------|------------|
| cortex | cortex | 1.0.0 | npm, python |
| driveiq-backend | driveiq-backend | 1.0.0 | npm |
| driveiq-frontend | driveiq-frontend | 1.0.0 | npm |
| blog | blog | 1.0.0 | npm |

### CISA KEV Integration

Enable Known Exploited Vulnerabilities:

1. Go to **Administration → Analyzers**
2. Find **Known Exploited Vulnerabilities**
3. Enable the analyzer
4. Set update frequency (default: daily)

KEV catalog URL: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

### EPSS Integration

Enable Exploit Prediction Scoring:

1. Go to **Administration → Analyzers**
2. Find **Exploit Prediction Scoring System (EPSS)**
3. Enable the analyzer
4. Set update frequency (default: daily)

EPSS data URL: https://api.first.org/data/v1/epss

### Vulnerability Sources

Configured sources (in docker-compose.yml):

- **NVD**: NIST National Vulnerability Database
- **GitHub Advisories**: GitHub Security Advisories
- **OSS Index**: Sonatype OSS Index
- **CISA KEV**: Known Exploited Vulnerabilities
- **EPSS**: Exploit Prediction Scoring

### Performance Tuning

Current settings in `docker-compose.yml`:

```yaml
# Java heap size
JAVA_OPTS: -Xmx4096m -Xms2048m

# Worker threads for parallel processing
ALPINE_WORKER_THREADS: 4

# Database connection pool
ALPINE_DATABASE_POOL_MAX_SIZE: 20
ALPINE_DATABASE_POOL_MIN_IDLE: 10

# Analysis frequency
PORTFOLIO_METRICS_UPDATE_CRON: 0 */6 * * *  # Every 6 hours
```

## API Integration

### Using the API Library

```bash
source scripts/security/dependency-track-api.sh

# Load API key
load_api_key

# Check health
check_health

# Get all projects
get_projects

# Get project metrics
get_project_metrics "project-uuid"

# Upload SBOM
upload_bom "path/to/sbom.json" "project-name" "version"

# Get portfolio metrics
get_portfolio_metrics
```

### API Examples

**Get vulnerability count for a project**:

```bash
source scripts/security/dependency-track-api.sh
load_api_key

project_uuid="your-project-uuid"
metrics=$(get_project_metrics "$project_uuid" | head -n -1)
critical=$(echo "$metrics" | jq -r '.critical')
high=$(echo "$metrics" | jq -r '.high')

echo "Critical: $critical, High: $high"
```

**List all projects with vulnerability counts**:

```bash
source scripts/security/dependency-track-api.sh
load_api_key

get_projects | head -n -1 | jq -r '.[] | "\(.name) v\(.version): \(.metrics.vulnerabilities) vulnerabilities"'
```

## Monitoring

### Optional: Prometheus & Grafana

Start monitoring stack:

```bash
cd coordination/security/dependency-track
docker-compose --profile monitoring up -d
```

Access:
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

Metrics available:
- API request rates and latency
- Vulnerability analysis queue depth
- Database performance
- Background task execution

### Log Files

**Docker logs**:
```bash
cd coordination/security/dependency-track
docker-compose logs -f apiserver
docker-compose logs -f postgres
```

**Cortex integration logs**:
- Upload log: `coordination/security/dependency-track/upload-log.json`
- Webhook log: `coordination/security/dependency-track/webhook-log.jsonl`
- Events: `coordination/dashboard-events.jsonl`

## Automation

### Scheduled Scans (Cron)

Add to crontab for daily scans:

```bash
crontab -e
```

Add line:
```
0 2 * * * cd /Users/ryandahlberg/Projects/cortex && ./scripts/security/integrated-vulnerability-scan.sh
```

### CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
- name: Generate SBOM and Upload to Dependency-Track
  run: |
    # Generate SBOM
    npx @cyclonedx/cyclonedx-npm --output-file sbom.json

    # Upload to Dependency-Track
    source scripts/security/dependency-track-api.sh
    load_api_key
    upload_bom "sbom.json" "${{ github.repository }}" "${{ github.sha }}"
```

## Security Policies

### Define Policies

1. Go to **Policy Management**
2. Click **Create Policy**
3. Configure conditions:
   - Severity thresholds
   - License compliance
   - Component age
   - Known exploited vulnerabilities

Example policy conditions:
- **Critical Vulnerabilities**: Fail if any critical severity
- **CISA KEV**: Fail if vulnerability is in KEV catalog
- **High EPSS**: Fail if EPSS score > 0.7
- **Outdated Components**: Warn if component > 2 years old

### Violation Notifications

Violations trigger webhooks that:
1. Create Cortex security tasks
2. Emit dashboard events
3. Log to webhook log

## Troubleshooting

### Dependency-Track won't start

**Check Docker resources**:
```bash
docker stats
```

Ensure at least 4GB RAM available.

**Check logs**:
```bash
cd coordination/security/dependency-track
docker-compose logs apiserver | tail -100
```

**Database connection issues**:
```bash
docker-compose logs postgres
docker-compose restart apiserver
```

### SBOMs not uploading

**Check API key**:
```bash
cat ~/.cortex/dtrack-api-key
```

**Test API connection**:
```bash
source scripts/security/dependency-track-api.sh
load_api_key
check_health
```

**Verify SBOM format**:
```bash
jq '.bomFormat, .specVersion' coordination/security/scans/cortex-sbom-20251130.json
```

Should output:
```
"CycloneDX"
"1.6"
```

### Analysis not completing

Vulnerability analysis can take time:
- Small projects: 2-5 minutes
- Large projects (1000+ components): 10-30 minutes

Check analysis queue:
1. Go to **Administration → Background Jobs**
2. View **Vulnerability Analysis** queue

### Webhook notifications not working

**Check webhook server**:
```bash
curl http://localhost:8888/health
```

**Test webhook manually**:
```bash
echo '{"notification":{"level":"INFO"},"project":{"name":"test"}}' | \
  bash scripts/security/dependency-track-webhook-handler.sh
```

**Check Dependency-Track can reach webhook**:
- Use `host.docker.internal` instead of `localhost` in webhook URL
- Ensure webhook server is running
- Check firewall rules

## Maintenance

### Backup Database

```bash
cd coordination/security/dependency-track
docker-compose exec postgres pg_dump -U dtrack dtrack > backup.sql
```

### Restore Database

```bash
docker-compose exec -T postgres psql -U dtrack dtrack < backup.sql
```

### Update Dependency-Track

```bash
cd coordination/security/dependency-track

# Pull latest images
docker-compose pull

# Restart with new images
docker-compose down
docker-compose up -d
```

### Clean Up Old Data

1. Go to **Administration → System**
2. Set **Retention Policy** for:
   - Metrics (default: 90 days)
   - Audit logs (default: 180 days)
   - Violation analysis (default: 365 days)

## File Structure

```
coordination/security/dependency-track/
├── docker-compose.yml              # Main deployment configuration
├── init-db/
│   └── 01-init.sql                # PostgreSQL initialization
├── prometheus/
│   └── prometheus.yml             # Prometheus configuration
├── reports/                       # Generated security reports
│   ├── portfolio-report-*.txt
│   └── portfolio-report-*.json
├── upload-log.json                # Upload tracking
├── webhook-log.jsonl              # Webhook events
└── README.md                      # This file

scripts/security/
├── dependency-track-setup.sh              # Initial setup and deployment
├── dependency-track-api.sh                # API library functions
├── dependency-track-upload-sboms.sh       # Automated SBOM upload
├── dependency-track-report.sh             # Portfolio report generator
├── dependency-track-webhook-handler.sh    # Webhook processing
├── dependency-track-webhook-server.sh     # Webhook HTTP server
└── integrated-vulnerability-scan.sh       # Complete workflow
```

## Additional Resources

- **Dependency-Track Documentation**: https://docs.dependencytrack.org/
- **CycloneDX Specification**: https://cyclonedx.org/specification/overview/
- **CISA KEV Catalog**: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- **EPSS Documentation**: https://www.first.org/epss/
- **NVD API**: https://nvd.nist.gov/developers

## Support

For issues with:
- **Dependency-Track**: See official documentation
- **Cortex integration**: Review Cortex security master logs
- **SBOM generation**: Check parallel-cve-scan.sh output

## Next Steps

1. **Configure notifications**: Set up webhook alerts for critical vulnerabilities
2. **Define policies**: Create security policies matching your risk tolerance
3. **Enable analyzers**: Activate CISA KEV and EPSS for enhanced risk scoring
4. **Schedule scans**: Add cron job for daily vulnerability scanning
5. **Integrate CI/CD**: Add SBOM upload to your deployment pipelines
6. **Monitor trends**: Review portfolio metrics weekly
7. **Remediate**: Prioritize critical and high-severity findings

---

**Generated by Cortex Security Master**
*Centralized vulnerability management for modern software portfolios*
