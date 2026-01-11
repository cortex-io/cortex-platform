# Asset Catalog

**Version:** 1.0
**Last Updated:** 2025-11-27

## Overview

The Asset Catalog provides comprehensive documentation of all Cortex coordination files, schemas, prompts, scripts, and configurations. It enables impact analysis, schema validation, and dependency tracking.

## Quick Start

### Generate Catalog

```bash
./scripts/catalog-assets.sh
```

### View Catalog

```bash
# Summary
jq '.summary' coordination/catalog/asset-catalog.json

# All assets
jq '.assets' coordination/catalog/asset-catalog.json

# Assets by category
jq '.assets | group_by(.category)' coordination/catalog/asset-catalog.json

# Critical assets
jq '.assets | map(select(.critical == true))' coordination/catalog/asset-catalog.json
```

### Validation Report

```bash
# View assets requiring validation
jq '.validation_checklist' coordination/catalog/validation-report.json

# Critical assets count
jq '.critical_assets' coordination/catalog/validation-report.json
```

## Catalog Structure

```json
{
  "generated_at": "2025-11-27T19:50:00-0600",
  "cortex_version": "1.0",
  "summary": {
    "total_assets": 42,
    "by_category": {
      "schema": 23,
      "prompt": 13,
      "scripts": 3,
      "library": 1,
      "configuration": 1,
      "documentation": 1
    },
    "by_owner": {
      "platform": 41,
      "coordinator-master": 1
    }
  },
  "assets": [...]
}
```

## Asset Categories

### 1. Schemas (23 assets)

JSON schemas that define coordination file formats:

```bash
# View all schemas
jq '.assets | map(select(.category == "schema"))' \
    coordination/catalog/asset-catalog.json
```

**Key Schemas**:
- `task-spec.json` - Task definition schema
- `worker-spec.json` - Worker specification
- `routing-decision.json` - MoE routing decisions
- `task-lineage.schema.json` - Lineage event schema
- `security-vulnerability.schema.json` - Vulnerability reports

**Validation Required**: All 23 schemas marked for validation

### 2. Prompts (13 assets)

System prompts for masters and workers:

**Master Prompts** (5):
- coordinator-master.md
- security-master.md
- development-master.md
- inventory-master.md
- cicd-master.md

**Worker Prompts** (7):
- implementation-worker.md
- scan-worker.md
- fix-worker.md
- test-worker.md
- review-worker.md
- pr-worker.md
- documentation-worker.md
- analysis-worker.md
- catalog-worker.md

**Properties**:
- `versioned: true` - Tracked in git
- `ab_test_eligible: true` - Can be A/B tested

### 3. Scripts (3 categories)

Bash scripts organized by directory:

- **scripts/lib**: 13 library scripts
- **scripts/daemons**: Daemon scripts
- **scripts**: Top-level orchestration scripts

### 4. Libraries (1 category)

Reusable bash libraries in `scripts/lib/`:

- environment.sh
- ab-testing.sh
- medallion.sh
- lineage.sh
- metrics.sh
- correlation.sh
- traced-logging.sh
- rag.sh
- And more...

### 5. Configuration (1 asset)

**Critical Configuration**:
- `routing-config` - 5-layer MoE routing configuration
- Owner: coordinator-master
- Requires validation: true
- Schema: routing-config.schema.json

### 6. Documentation (counted)

Documentation files in `docs/` directory.

## Asset Properties

### Common Properties

All assets have:
- `asset_id` - Unique identifier
- `category` - Asset category
- `name` - Display name
- `file_path` - Absolute path (if file-based)
- `description` - Human-readable description
- `owner` - Owning component/master

### Optional Properties

- `critical` - Requires special attention
- `requires_validation` - Must pass validation
- `schema` - Associated JSON schema
- `versioned` - Tracked in version control
- `ab_test_eligible` - Can be used in A/B tests
- `count` - Number of items (for aggregated assets)
- `public` - Public-facing documentation

## Use Cases

### 1. Impact Analysis

Find all assets owned by a master:

```bash
jq '.assets | map(select(.owner == "security-master"))' \
    coordination/catalog/asset-catalog.json
```

### 2. Schema Validation

Validate all files against their schemas:

```bash
# Get assets with schemas
jq -r '.assets | map(select(.schema != null)) |
    .[] | "\(.file_path) → \(.schema)"' \
    coordination/catalog/asset-catalog.json

# Validate each
for file in $(jq -r '.assets | map(select(.schema != null)) | .[].file_path' \
    coordination/catalog/asset-catalog.json); do
    echo "Validating $file"
    jq empty "$file"  # Basic JSON validation
done
```

### 3. Dependency Tracking

Find what depends on a schema:

```bash
schema_name="task-spec.json"

jq --arg schema "$schema_name" \
    '.assets | map(select(.schema == $schema))' \
    coordination/catalog/asset-catalog.json
```

### 4. Onboarding Documentation

Generate asset overview for new developers:

```bash
./scripts/catalog-assets.sh > /dev/null

echo "=== Cortex Asset Overview ==="
jq -r '.summary | to_entries | .[] | "\(.key): \(.value)"' \
    coordination/catalog/asset-catalog.json
```

### 5. Pre-Deployment Validation

Ensure all critical assets are valid:

```bash
# Check critical assets
critical_count=$(jq '.critical_assets' \
    coordination/catalog/validation-report.json)

if [[ $critical_count -gt 0 ]]; then
    echo "Critical assets requiring validation: $critical_count"
    jq -r '.validation_checklist[] | "  - \(.asset_id)"' \
        coordination/catalog/validation-report.json
fi
```

### 6. Version Tracking

Track changes to versioned assets:

```bash
# Find versioned assets
jq '.assets | map(select(.versioned == true))' \
    coordination/catalog/asset-catalog.json

# Check git history
for file in $(jq -r '.assets | map(select(.versioned == true)) | .[].file_path' \
    coordination/catalog/asset-catalog.json); do
    echo "=== $file ==="
    git log --oneline -n 5 "$file"
done
```

## Integration with Other Systems

### With Pre-Deployment Testing

```bash
# Validate all schemas before deployment
./scripts/catalog-assets.sh

# Get validation checklist
validation_items=$(jq '.validation_checklist | length' \
    coordination/catalog/validation-report.json)

if [[ $validation_items -gt 0 ]]; then
    echo "ERROR: $validation_items assets require validation"
    exit 1
fi
```

### With A/B Testing

```bash
# Find A/B testable prompts
jq '.assets | map(select(.ab_test_eligible == true))' \
    coordination/catalog/asset-catalog.json
```

### With Documentation Generation

```bash
# Generate documentation index
jq -r '.assets | map(select(.category == "documentation")) |
    .[] | "- [\(.name)](\(.file_path))"' \
    coordination/catalog/asset-catalog.json > docs/INDEX.md
```

## Catalog Maintenance

### Regular Updates

Run catalog generation:
- **Daily**: Automated via cron
- **Before deployment**: Part of pre-deployment checks
- **After major changes**: Manual run

### Validation Schedule

- **Schema validation**: Every commit (CI/CD)
- **Critical assets**: Before every deployment
- **Full catalog**: Weekly

## Catalog Schema

### Asset Object

```typescript
{
  asset_id: string,           // Unique identifier
  category: string,           // Category (schema, prompt, etc.)
  subcategory?: string,       // Optional subcategory
  name: string,               // Display name
  file_path?: string,         // File path (if applicable)
  count?: number,             // Count (for aggregated assets)
  description: string,        // Human-readable description
  owner: string,              // Owning component
  critical?: boolean,         // Critical asset flag
  requires_validation?: boolean,
  validation_required?: boolean,
  schema?: string,            // Associated schema file
  versioned?: boolean,        // Version controlled
  ab_test_eligible?: boolean, // Can be A/B tested
  reusable?: boolean,         // Reusable library
  public?: boolean,           // Public documentation
  last_modified?: string      // Last modification date
}
```

### Validation Report

```typescript
{
  generated_at: string,
  total_assets: number,
  critical_assets: number,
  assets_requiring_validation: number,
  assets_with_schemas: number,
  validation_checklist: Array<{
    asset_id: string,
    file_path: string,
    schema: string,
    owner: string
  }>
}
```

## Best Practices

1. **Regular Generation**: Generate catalog daily or after major changes
2. **Schema First**: Create schema before implementing new file types
3. **Documentation**: Document all assets with clear descriptions
4. **Ownership**: Assign clear ownership for each asset
5. **Validation**: Validate critical assets before deployment
6. **Version Control**: Track all versioned assets in git

## Future Enhancements

- Automated dependency graph generation
- Asset usage tracking (which assets are actively used)
- Schema evolution tracking
- Automated documentation generation
- Integration with IDE (asset autocomplete)
- Real-time catalog updates (on file changes)
- Asset deprecation warnings
