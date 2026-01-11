# Cortex Environment Separation

## Overview

Cortex now supports three isolated environments for safe development, testing, and production deployment:

- **dev**: Development environment for feature development and testing
- **staging**: Pre-production environment for validation before deployment
- **prod**: Production environment for live operations

Each environment maintains its own coordination data (tasks, metrics, lineage, etc.) while sharing common resources (prompts, schemas, master configurations).

## Directory Structure

```
coordination/
├── dev/                      # Development environment
│   ├── tasks/
│   ├── routing/
│   ├── metrics/
│   ├── lineage/
│   ├── events/
│   ├── traces/
│   └── logs/
├── staging/                  # Staging environment
│   ├── tasks/
│   ├── routing/
│   ├── metrics/
│   ├── lineage/
│   ├── events/
│   ├── traces/
│   └── logs/
├── prod/                     # Production environment
│   ├── tasks/
│   ├── routing/
│   ├── metrics/
│   ├── lineage/
│   ├── events/
│   ├── traces/
│   └── logs/
└── [shared resources]
    ├── prompts/              # Shared across all environments
    ├── schemas/              # Shared across all environments
    ├── masters/              # Shared across all environments
    ├── config/               # Shared across all environments
    └── catalog/              # Shared across all environments
```

## Environment Selection

Set the `CORTEX_ENV` environment variable to specify which environment to use:

```bash
# Use development environment
export CORTEX_ENV=dev

# Use staging environment
export CORTEX_ENV=staging

# Use production environment (default)
export CORTEX_ENV=prod
```

If `CORTEX_ENV` is not set, the system defaults to `prod` for safety.

## Cross-Environment Access Rules

### Read Access

Different environments have different read access permissions:

| Current Env | Can Read From Dev | Can Read From Staging | Can Read From Prod |
|-------------|-------------------|----------------------|-------------------|
| dev         | Yes (own)         | Yes                  | Yes               |
| staging     | No                | Yes (own)            | Yes               |
| prod        | No                | No                   | Yes (own)         |

**Use Cases:**
- Dev can read from staging/prod to test against real data
- Staging can read from prod for pre-deployment validation
- Prod is isolated and only reads its own data

### Write Access

**All environments have write isolation enforced:**
- Each environment can ONLY write to its own directories
- No cross-environment writes are permitted
- This prevents accidental data corruption across environments

## Usage Examples

### Basic Environment Usage

```bash
# Development workflow
export CORTEX_ENV=dev

# All operations now use dev environment
./scripts/run-coordinator-master.sh

# Tasks, metrics, lineage saved to coordination/dev/
```

### Cross-Environment Reading

```bash
# In dev environment, read production metrics for comparison
export CORTEX_ENV=dev

# Get dev metrics
dev_metrics=$(cat "$(get_metrics_dir)/metrics.jsonl")

# Get prod metrics for comparison (read-only)
prod_metrics=$(cat "$(get_env_path prod metrics)/metrics.jsonl")

# Compare and analyze
```

### Testing Against Production Data

```bash
# Test new feature against production data without affecting prod
export CORTEX_ENV=dev

# Read prod tasks for testing
prod_tasks=$(ls "$(get_env_path prod tasks)")

# Process in dev environment
# All outputs go to coordination/dev/
```

## Library Integration

### Using Environment Library

```bash
#!/bin/bash
source "$(dirname "$0")/lib/environment.sh"

# Get current environment
current_env=$(get_env)
echo "Running in: $current_env"

# Get environment-specific paths
tasks_dir=$(get_tasks_dir)
metrics_dir=$(get_metrics_dir)
lineage_dir=$(get_lineage_dir)

# Get shared resource paths
prompts_dir=$(get_prompts_dir)
schemas_dir=$(get_schemas_dir)

# Check cross-environment access
if can_read_from_env "prod"; then
    echo "Can read from production"
    prod_tasks=$(get_env_path "prod" "tasks")
fi

# Verify write permissions
if can_write_to_env "staging"; then
    echo "Can write to staging"
else
    echo "Cannot write to staging (not current environment)"
fi
```

### Updated Libraries

The following libraries are now environment-aware:

- **scripts/lib/environment.sh**: Core environment library (new)
- **scripts/lib/lineage.sh**: Task lineage tracking
- **scripts/lib/metrics.sh**: Metrics collection
- **scripts/lib/read-alias.sh**: Master version management

These libraries automatically use the correct environment paths based on `CORTEX_ENV`.

## API Reference

### Core Functions

#### `get_env()`
Returns the current environment name (dev/staging/prod).

```bash
env=$(get_env)
# Returns: "dev", "staging", or "prod"
```

#### `get_coordination_path(subdir)`
Returns the environment-specific path for a subdirectory.

```bash
tasks_path=$(get_coordination_path "tasks")
# Returns: /path/to/cortex/coordination/dev/tasks (if CORTEX_ENV=dev)
```

#### `get_env_path(target_env, subdir)`
Returns the path for a specific environment (for cross-env reads).

```bash
prod_metrics=$(get_env_path "prod" "metrics")
# Returns: /path/to/cortex/coordination/prod/metrics
```

#### `can_read_from_env(target_env)`
Checks if current environment can read from target environment.

```bash
if can_read_from_env "prod"; then
    # Read from prod
fi
```

#### `can_write_to_env(target_env)`
Checks if current environment can write to target environment.

```bash
if can_write_to_env "staging"; then
    # Write to staging
fi
```

### Convenience Functions

```bash
# Environment-specific directories
get_tasks_dir()
get_routing_dir()
get_metrics_dir()
get_lineage_dir()
get_events_dir()
get_traces_dir()
get_logs_dir()

# Shared resource directories
get_prompts_dir()
get_schemas_dir()
get_masters_dir()
get_workers_dir()
get_config_dir()
get_catalog_dir()
```

### Environment Information

```bash
# Get environment status as JSON
get_env_status()

# Display environment info (human-readable)
display_env_info()

# Initialize environment directories
init_env_directories()
```

## Migration Guide

### Migrating Existing Deployments

If you have an existing Cortex deployment with data in `coordination/tasks`, `coordination/metrics`, etc., follow these steps:

#### 1. Backup Existing Data

```bash
# Create backup
tar -czf cortex-coordination-backup-$(date +%Y%m%d).tar.gz coordination/
```

#### 2. Run Migration (Optional)

The system includes a migration helper that copies existing data to the prod environment:

```bash
# Source environment library
source scripts/lib/environment.sh

# Run migration
migrate_to_env_structure

# This copies data from coordination/{tasks,metrics,etc} to coordination/prod/
```

#### 3. Verify Migration

```bash
# Check that prod environment has your data
export CORTEX_ENV=prod
ls -la $(get_tasks_dir)
ls -la $(get_metrics_dir)
```

#### 4. Test Environment Isolation

```bash
# Run test suite
./scripts/test-environment-isolation.sh
```

#### 5. Update Custom Scripts

If you have custom scripts that hardcode paths like `coordination/tasks`, update them:

```bash
# Before
tasks_dir="coordination/tasks"

# After
source scripts/lib/environment.sh
tasks_dir=$(get_tasks_dir)
```

### Backwards Compatibility

The updated libraries include backwards compatibility fallbacks:

- If environment.sh is not found, libraries use legacy paths
- If `CORTEX_ENV` is not set, defaults to `prod`
- Existing scripts continue to work without modification

However, for new development, always use the environment library.

## Testing

### Running Tests

```bash
# Run comprehensive test suite
./scripts/test-environment-isolation.sh

# Expected output:
# Total Tests: 21
# Passed: 21
# Failed: 0
```

### Test Coverage

The test suite verifies:
- Environment detection and defaults
- Path resolution for all environments
- Cross-environment read access rules
- Write isolation enforcement
- Shared resource access
- Library integration
- Directory structure

### Manual Testing

```bash
# Test dev environment
export CORTEX_ENV=dev
./scripts/run-coordinator-master.sh

# Verify data goes to coordination/dev/
ls -la coordination/dev/tasks/

# Test staging environment
export CORTEX_ENV=staging
./scripts/run-security-master.sh

# Verify data goes to coordination/staging/
ls -la coordination/staging/metrics/
```

## Best Practices

### Development Workflow

1. **Always use dev environment for development:**
   ```bash
   export CORTEX_ENV=dev
   ```

2. **Test against production data (read-only):**
   ```bash
   # In dev, read from prod for testing
   prod_data=$(cat "$(get_env_path prod tasks)/task-123.json")
   ```

3. **Validate in staging before prod:**
   ```bash
   export CORTEX_ENV=staging
   # Run validation tests
   ```

4. **Production deployments use prod environment:**
   ```bash
   export CORTEX_ENV=prod
   # Or omit CORTEX_ENV (defaults to prod)
   ```

### Script Development

1. **Always source environment library:**
   ```bash
   source "$(dirname "$0")/lib/environment.sh"
   ```

2. **Use helper functions instead of hardcoded paths:**
   ```bash
   # Good
   tasks=$(get_tasks_dir)

   # Bad
   tasks="coordination/tasks"
   ```

3. **Check environment before sensitive operations:**
   ```bash
   current_env=$(get_env)
   if [ "$current_env" != "prod" ]; then
       echo "Warning: Not running in production"
   fi
   ```

4. **Validate cross-environment access:**
   ```bash
   if ! can_read_from_env "prod"; then
       echo "Cannot access production data from this environment"
       exit 1
   fi
   ```

### Security Considerations

1. **Prod is isolated** - Production data is protected from dev/staging writes
2. **Read-only prod access** - Dev/staging can read prod but never write
3. **Environment verification** - Always verify current environment for sensitive operations
4. **Separate credentials** - Use different credentials for each environment

## Troubleshooting

### Environment Not Detected

```bash
# Check current environment
source scripts/lib/environment.sh
get_env

# Display environment info
display_env_info
```

### Wrong Environment Being Used

```bash
# Verify CORTEX_ENV is set
echo $CORTEX_ENV

# Unset to use default (prod)
unset CORTEX_ENV

# Set explicitly
export CORTEX_ENV=dev
```

### Cross-Environment Access Denied

```bash
# Check if access is allowed
source scripts/lib/environment.sh
export CORTEX_ENV=staging

if can_read_from_env "dev"; then
    echo "Can read from dev"
else
    echo "Cannot read from dev (expected for staging)"
fi
```

### Missing Directories

```bash
# Initialize environment directories
source scripts/lib/environment.sh
init_env_directories
```

## Performance Considerations

### Environment Overhead

- Minimal overhead from environment detection
- Path resolution cached during script execution
- No performance impact on existing operations

### Storage Requirements

- Each environment maintains separate data
- Shared resources (prompts, schemas) stored once
- Typical storage: ~3x for environment-specific data

### Optimization Tips

1. **Clean up old data:**
   ```bash
   # Remove old dev data periodically
   find coordination/dev/tasks -mtime +30 -delete
   ```

2. **Use staging for final validation only:**
   - Most testing in dev
   - Staging only for pre-prod validation

3. **Monitor prod environment size:**
   ```bash
   du -sh coordination/prod/
   ```

## Future Enhancements

Planned improvements to environment separation:

- [ ] Environment-specific configuration files
- [ ] Automated promotion from dev -> staging -> prod
- [ ] Environment comparison tools
- [ ] Cross-environment data sync utilities
- [ ] Environment-specific access controls
- [ ] Audit logging for cross-environment access

## Support

For issues or questions about environment separation:

1. Run test suite: `./scripts/test-environment-isolation.sh`
2. Check environment status: `display_env_info()`
3. Review this documentation
4. Check library source: `scripts/lib/environment.sh`

## Summary

Environment separation provides:
- Safe development and testing workflows
- Production data protection
- Flexible cross-environment access for dev/staging
- Easy environment switching via `CORTEX_ENV`
- Backwards compatibility with existing deployments

Always use `CORTEX_ENV` to control which environment you're working in!
