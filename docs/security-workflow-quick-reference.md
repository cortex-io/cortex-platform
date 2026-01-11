# Security Workflow Quick Reference

## Files Created

```
cortex/
  .github/workflows/security-scan.yml    (7.2 KB)
  README.md                              (updated with badge)

blog/
  .github/workflows/security-scan.yml    (6.1 KB)
  README.md                              (updated with badge)

DriveIQ/
  .github/workflows/security-scan.yml    (8.5 KB)
  README.md                              (updated with badge)
```

## Workflow Triggers

| Event | Description | Frequency |
|-------|-------------|-----------|
| Push to main | Automatic scan on merge | Per commit |
| Pull Request | Scan before merge approval | Per PR |
| Daily Schedule | Proactive CVE detection | 2 AM UTC |

## Security Tools

| Tool | Purpose | Fails On |
|------|---------|----------|
| npm audit | NPM vulnerabilities | HIGH/CRITICAL |
| pip-audit | Python vulnerabilities | ANY |
| Trivy | Filesystem scanning | HIGH/CRITICAL |
| Syft | SBOM generation | N/A |
| Grype | SBOM vulnerability scan | HIGH |

## Job Workflows

### Cortex (Multi-ecosystem)
1. npm-audit → Scan package.json
2. python-audit → Scan python-sdk + evaluation (matrix)
3. trivy-scan → Full filesystem scan
4. sbom-generation → SBOM + Grype
5. security-summary → Aggregate results

### Blog (NPM only)
1. npm-audit → Scan Astro dependencies
2. trivy-scan → Filesystem scan
3. sbom-generation → SBOM + Grype
4. security-summary → Aggregate results

### DriveIQ (Full-stack)
1. npm-audit-frontend → Scan React dependencies
2. python-audit-backend → Scan FastAPI dependencies
3. trivy-scan → Full filesystem scan
4. sbom-generation → Dual SBOM (frontend + backend) + Grype
5. security-summary → Aggregate results

## Artifacts Generated

| Artifact | Retention | Format |
|----------|-----------|--------|
| NPM audit results | 30 days | JSON |
| pip-audit results | 30 days | JSON |
| Trivy scan results | 30 days | SARIF + JSON |
| SBOM files | 90 days | SPDX + CycloneDX |
| Grype scan results | 30 days | JSON |

## Quick Commands

```bash
# View workflow status
gh workflow view security-scan.yml

# List workflow runs
gh run list --workflow=security-scan.yml

# View latest run
gh run view

# Download artifacts
gh run download <run-id>

# Trigger manual run
gh workflow run security-scan.yml

# Watch live run
gh run watch
```

## GitHub Security Tab

All SARIF results automatically uploaded to:
- https://github.com/ry-ops/cortex/security
- https://github.com/ry-ops/blog/security
- https://github.com/ry-ops/DriveIQ/security

## Status Badges

All README files now display live security scan status:

![Security Scan Badge](https://img.shields.io/badge/Security-Scan-green)

## Common Issues

### Workflow fails on false positive
1. Review Trivy/Grype output in artifacts
2. Add ignore rules if needed
3. Update workflow with suppressions

### SBOM generation fails
1. Check Syft installation step
2. Verify filesystem permissions
3. Review scan directory paths

### SARIF upload fails
1. Verify `security-events: write` permission
2. Check SARIF file format validity
3. Ensure GitHub Advanced Security enabled

## Next Actions

1. Push workflows to GitHub:
   ```bash
   git add .github/workflows/security-scan.yml README.md
   git commit -m "feat: Add automated security scanning"
   git push origin main
   ```

2. Monitor first run in Actions tab

3. Review Security tab for SARIF results

4. Configure notification preferences

## Integration Points

- **Local Cortex Scans**: Complements GitHub Actions
- **Security Dashboard**: Aggregates CI + local results
- **Portfolio Health**: 100% coverage across all repos
- **Auto-remediation**: Triggers security-fix workers

---

**Status**: Ready to deploy
**Coverage**: 3/3 repositories
**Next Step**: git push to activate
