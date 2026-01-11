# GitHub Actions Automated Reports

This document describes the automated reporting workflows configured for Cortex.

## Overview

Cortex uses GitHub Actions to automatically generate and publish reports on a scheduled basis. All reports are generated using Quarto and deployed to GitHub Pages.

## Workflows

### 1. Weekly Report (`weekly-report.yml`)

**Schedule**: Every Monday at 9 AM UTC

**Purpose**: Generate comprehensive weekly performance and health reports.

**Reports Generated**:
- Weekly Summary (`weekly-summary.html`)
- Security Audit (`security-audit.html`)
- Cost Report (`cost-report.html`)

**Features**:
- AI-powered insights using Claude API
- Performance metrics visualization
- Worker activity tracking
- Task completion trends
- Automated deployment to GitHub Pages
- 90-day artifact retention

**Manual Trigger**:
```bash
# Via GitHub UI: Actions > Generate Weekly Report > Run workflow
# Via gh CLI:
gh workflow run weekly-report.yml
```

---

### 2. Monthly Security Audit (`monthly-security-audit.yml`)

**Schedule**: First day of each month at 10 AM UTC

**Purpose**: Comprehensive security posture assessment.

**Features**:
- Automated security scanning
- Vulnerability trend analysis
- AI-powered security assessment
- Critical findings detection
- 365-day artifact retention
- Automatic warnings for critical vulnerabilities

**Reports Generated**:
- Security Audit Report (`security-audit.html`)
- Security Audit PDF (`security-audit.pdf`)

**Manual Trigger**:
```bash
gh workflow run monthly-security-audit.yml
```

---

### 3. Monthly Cost Report (`monthly-cost-report.yml`)

**Schedule**: Last day of each month at 11 AM UTC

**Purpose**: Track and analyze operational costs.

**Features**:
- Token usage analysis
- Cost trend tracking
- Budget forecasting
- 365-day artifact retention

**Reports Generated**:
- Cost Report (`cost-report.html`)
- Cost Report PDF (`cost-report.pdf`)

**Manual Trigger**:
```bash
gh workflow run monthly-cost-report.yml
```

---

## Configuration

### Required Secrets

Set up these secrets in your GitHub repository:

1. **ANTHROPIC_API_KEY** (Optional but recommended)
   - Used for AI-powered insights and summaries
   - Navigate to: Settings > Secrets and variables > Actions > New repository secret
   - Name: `ANTHROPIC_API_KEY`
   - Value: Your Anthropic API key

### Permissions

All workflows require these permissions (already configured):
```yaml
permissions:
  contents: write      # For committing reports
  pages: write        # For GitHub Pages deployment
  id-token: write     # For GitHub Pages
  security-events: read  # For security scanning (security audit only)
```

### GitHub Pages Setup

1. Go to: Settings > Pages
2. Source: Deploy from a branch
3. Branch: `gh-pages` / `root`
4. Save

After the first workflow run, reports will be available at:
```
https://<username>.github.io/<repo-name>/reports/
```

---

## Local Testing

### Prerequisites

```bash
# Install Quarto
brew install quarto  # macOS
# OR download from https://quarto.org/docs/get-started/

# Install Python dependencies
cd reports
pip install polars anthropic plotly pandas
```

### Test Report Generation

```bash
# Set API key (optional)
export ANTHROPIC_API_KEY="your-key-here"

# Generate weekly summary
cd reports
quarto render weekly-summary.qmd

# Generate security audit
quarto render security-audit.qmd

# Generate cost report
quarto render cost-report.qmd

# View reports
open _site/index.html
```

### Test All Reports

```bash
# Use the provided test script
bash scripts/test-reports.sh
```

---

## Report Access

### Public URLs (after GitHub Pages setup)

- **All Reports**: `https://<username>.github.io/<repo-name>/reports/`
- **Weekly Summary**: `https://<username>.github.io/<repo-name>/reports/weekly-summary.html`
- **Security Audit**: `https://<username>.github.io/<repo-name>/reports/security-audit.html`
- **Cost Report**: `https://<username>.github.io/<repo-name>/reports/cost-report.html`

### Artifacts

Reports are also saved as workflow artifacts:

1. Go to: Actions > [Workflow Name] > [Run]
2. Scroll to "Artifacts" section
3. Download the report archive

**Retention**:
- Weekly reports: 90 days
- Monthly reports: 365 days

---

## Customization

### Modify Schedule

Edit the `cron` expression in the workflow file:

```yaml
on:
  schedule:
    - cron: '0 9 * * MON'  # Every Monday at 9 AM UTC
```

Cron format: `minute hour day month day-of-week`

**Examples**:
- Daily at 8 AM: `'0 8 * * *'`
- Every 6 hours: `'0 */6 * * *'`
- First and 15th of month: `'0 10 1,15 * *'`

### Add New Reports

1. Create new `.qmd` file in `reports/` directory
2. Add to `reports/_quarto.yml` navigation
3. Add render step to appropriate workflow:

```yaml
- name: Render custom report
  run: |
    cd reports
    quarto render custom-report.qmd
```

### Disable AI Insights

If you don't want to use AI insights (saves API costs):

1. Remove or comment out the `ANTHROPIC_API_KEY` environment variable
2. Reports will still generate with static analysis
3. AI-generated sections will show fallback content

---

## Monitoring

### Check Workflow Status

```bash
# List recent workflow runs
gh run list --workflow=weekly-report.yml

# View specific run
gh run view <run-id>

# View run logs
gh run view <run-id> --log
```

### GitHub UI

1. Navigate to: Actions tab
2. Select workflow from left sidebar
3. View run history and details

### Notifications

Configure workflow notifications:
1. Settings > Notifications
2. Enable "Actions" notifications
3. Choose notification preferences

---

## Troubleshooting

### Common Issues

**Issue**: Reports not deploying to GitHub Pages
- **Solution**: Check GitHub Pages settings, ensure `gh-pages` branch exists

**Issue**: AI insights not generating
- **Solution**: Verify `ANTHROPIC_API_KEY` secret is set correctly

**Issue**: Permission denied errors
- **Solution**: Check workflow permissions in `.github/workflows/*.yml`

**Issue**: Missing dependencies
- **Solution**: Verify all Python packages are listed in `pip install` step

### Debug Mode

Enable debug logging:

1. Settings > Secrets and variables > Actions > Variables
2. New variable: `ACTIONS_STEP_DEBUG` = `true`
3. Re-run workflow

---

## Best Practices

1. **Schedule Optimization**: Avoid scheduling multiple heavy workflows at the same time
2. **Cost Management**: Monitor API usage if using AI features extensively
3. **Artifact Cleanup**: Adjust retention days based on compliance requirements
4. **Security**: Never commit API keys; always use GitHub Secrets
5. **Testing**: Test reports locally before modifying workflows

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         GitHub Actions Workflows                │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐│
│  │   Weekly     │  │   Monthly    │  │Monthly ││
│  │   Report     │  │   Security   │  │  Cost  ││
│  │  (Mon 9AM)   │  │   (1st 10AM) │  │(Last)  ││
│  └──────┬───────┘  └──────┬───────┘  └───┬────┘│
│         │                 │               │     │
│         └─────────┬───────┴───────────────┘     │
│                   │                             │
│         ┌─────────▼─────────┐                   │
│         │  Quarto Renderer  │                   │
│         │  + Python + AI    │                   │
│         └─────────┬─────────┘                   │
│                   │                             │
│         ┌─────────▼─────────┐                   │
│         │   HTML Reports    │                   │
│         └─────────┬─────────┘                   │
│                   │                             │
│         ┌─────────▼─────────┐                   │
│         │  GitHub Pages     │                   │
│         │  + Artifacts      │                   │
│         └───────────────────┘                   │
└─────────────────────────────────────────────────┘
```

---

## Future Enhancements

Potential improvements:

- [ ] Slack/Discord notifications for critical security findings
- [ ] Email summaries for weekly reports
- [ ] Trend analysis across multiple weeks/months
- [ ] Integration with external monitoring tools
- [ ] Custom dashboards for executive summaries
- [ ] Automated PR creation for security fixes
- [ ] Budget alerts for cost overruns

---

## Support

For issues or questions:

1. Check workflow run logs in GitHub Actions
2. Review this documentation
3. Test reports locally to isolate issues
4. Check GitHub Actions status: https://www.githubstatus.com/

---

**Last Updated**: 2025-12-01
**Version**: 1.0
**Maintainer**: Cortex Development Team
