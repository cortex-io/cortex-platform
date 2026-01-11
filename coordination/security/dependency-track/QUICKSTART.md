# Dependency-Track Quick Start Guide

Get up and running with Dependency-Track in 5 minutes.

## 1. Start Dependency-Track

```bash
cd /Users/ryandahlberg/Projects/cortex
./scripts/security/dependency-track-setup.sh
```

**What happens**:
- Starts Docker containers (API, Frontend, Database)
- Waits for initialization (~2-5 min)
- Creates initial projects

## 2. Complete Setup

Open browser to: **http://localhost:8082**

1. Login: `admin` / `admin`
2. Change password when prompted
3. Navigate to: **Administration → Access Management → Teams**
4. Click **Administrators** → **API Keys** tab
5. Click **Create API Key**
6. Copy the key and run:

```bash
mkdir -p ~/.cortex
echo "YOUR-API-KEY-HERE" > ~/.cortex/dtrack-api-key
chmod 600 ~/.cortex/dtrack-api-key
```

## 3. Upload SBOMs

```bash
./scripts/security/dependency-track-upload-sboms.sh
```

Wait 2-5 minutes for analysis to complete.

## 4. View Results

**Web UI**: http://localhost:8082
- Click on each project to see vulnerabilities
- Check **Audit Vulnerabilities** tab
- Review risk scores and metrics

**CLI Report**:
```bash
./scripts/security/dependency-track-report.sh
```

## 5. Enable Enhanced Features

### CISA KEV (Known Exploited Vulnerabilities)

1. **Administration → Analyzers**
2. Find **Known Exploited Vulnerabilities**
3. Click **Enable**

### EPSS (Exploit Prediction Scoring)

1. **Administration → Analyzers**
2. Find **EPSS**
3. Click **Enable**

## Common Commands

```bash
# Full scan workflow (scan → upload → report)
./scripts/security/integrated-vulnerability-scan.sh

# Just upload existing SBOMs
./scripts/security/dependency-track-upload-sboms.sh

# Generate report
./scripts/security/dependency-track-report.sh

# Check if running
curl http://localhost:8081/api/version

# View logs
cd coordination/security/dependency-track
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart
```

## Automation

### Daily Scans (Cron)

```bash
# Add to crontab
0 2 * * * cd /Users/ryandahlberg/Projects/cortex && ./scripts/security/integrated-vulnerability-scan.sh
```

### Real-time Alerts

Start webhook server:
```bash
./scripts/security/dependency-track-webhook-server.sh &
```

Configure in UI:
1. **Administration → Notifications → Alerts**
2. **Create Notification**
3. **Publisher**: Webhook
4. **URL**: http://host.docker.internal:8888/webhook

## Troubleshooting

**Not starting?**
```bash
# Check Docker
docker ps

# Check logs
cd coordination/security/dependency-track
docker-compose logs apiserver | tail -50

# Restart
docker-compose restart
```

**Upload failing?**
```bash
# Verify API key
cat ~/.cortex/dtrack-api-key

# Test connection
curl -H "X-Api-Key: $(cat ~/.cortex/dtrack-api-key)" http://localhost:8081/api/version
```

## Key URLs

- Frontend: http://localhost:8082
- API: http://localhost:8081
- Prometheus: http://localhost:9090 (if monitoring enabled)
- Grafana: http://localhost:3000 (if monitoring enabled)

## Next Steps

1. Review vulnerability findings in web UI
2. Set up notification webhooks
3. Configure security policies
4. Schedule automated scans
5. Integrate with CI/CD pipeline

---

**Need help?** See full README: `coordination/security/dependency-track/README.md`
