# Cleanup Master

**Version:** 1.0.0
**Last Updated:** 2025-11-27

## Overview

The Cleanup Master is an automated system that detects and removes unused code, dead references, and legacy patterns after implementations and removals. It helps maintain a clean, efficient codebase through continuous housekeeping.

**Key Benefits:**
- 🔍 **Automated Detection** - Finds dead code, broken references, and legacy patterns
- 🤖 **Safe Auto-Fix** - Automatically fixes safe issues (permissions, empty dirs, duplicates)
- 📊 **Actionable Reports** - Prioritized recommendations with confidence scores
- 🎯 **Post-Implementation Hygiene** - Runs after major changes to clean up artifacts

---

## Architecture

```
Cleanup Master
    ↓
Scanner (Dead Code Detection)
    ↓
Analyzer (Pattern Detection)
    ↓
Auto-Fix (Safe Fixes)
    ↓
Report Generator
```

### Components

1. **Scanner** (`lib/scanner.sh`)
   - Unreferenced file detection
   - Dead function detection
   - Empty directory detection
   - File permission validation
   - Duplicate file detection

2. **Analyzer** (`lib/analyzer.sh`)
   - Broken reference detection
   - Legacy API call detection
   - Legacy pattern detection
   - .gitignore consistency checks

3. **Auto-Fix** (`lib/auto-fix.sh`)
   - Safe automated fixes
   - Dry-run support
   - Confidence-based removal
   - Backup creation

4. **Report Generator** (`report.sh`)
   - Markdown report generation
   - Priority-based sorting
   - Actionable recommendations

---

## Usage

### Quick Scan (After Changes)

```bash
# Run after implementations/removals
./coordination/masters/cleanup/scan.sh
```

**Output:**
```
=== Cleanup Master - Quick Scan ===

Scanning for unreferenced files...
Scanning for dead functions...
Scanning for empty directories...
Checking file permissions...
Scanning for duplicate files...
Scanning for broken references...
Scanning for legacy API calls...

=== Scan Complete ===
Results: coordination/masters/cleanup/scans/scan-20251127_143022

Total Issues: 47
  - Unreferenced files: 12
  - Dead functions: 8
  - Empty directories: 5
  - Permission issues: 3
  - Duplicate files: 6
  - Broken references: 2
  - Legacy API calls: 11
```

### Full Cleanup with Auto-Fix

```bash
# Dry run (preview changes)
./coordination/masters/cleanup/run.sh --auto-fix

# Live run (apply changes)
./coordination/masters/cleanup/run.sh --auto-fix --live
```

**What gets auto-fixed:**
- ✅ Empty directories (safe to remove)
- ✅ File permissions (make scripts executable, configs non-executable)
- ✅ Duplicate files (keeps newest)
- ✅ .gitignore violations (untrack files that should be ignored)

**What requires manual review:**
- ⚠️ Unreferenced files (may be new/planned)
- ⚠️ Broken references (need to understand context)
- ⚠️ Legacy API calls (need to remove from code)
- ⚠️ Dead functions (may be library functions)

### Generate Report

```bash
./coordination/masters/cleanup/report.sh
```

**Output:** `coordination/masters/cleanup/scans/scan-YYYYMMDD_HHMMSS/CLEANUP-REPORT.md`

---

## Integration Points

### 1. Post-Worker Task Hook

Run cleanup after worker completes task:

```bash
# In worker completion handler
source coordination/masters/cleanup/lib/scanner.sh

# Quick scan for new issues
find_unreferenced_files "$PWD" "/tmp/cleanup-check.json"
```

### 2. Coordinator Integration

Trigger cleanup after major changes:

```bash
# After removing files/features
./coordination/masters/cleanup/scan.sh

# Review and apply fixes
./coordination/masters/cleanup/run.sh --auto-fix --live
```

### 3. Weekly Daemon

Proactive cleanup via daemon:

```bash
# Start weekly cleanup daemon
./scripts/daemons/cleanup-daemon.sh &

# Runs every Sunday at 2 AM
# - Full scan
# - Generate report
# - Auto-fix safe issues
# - Notify of manual review items
```

### 4. Pre-Commit Hook

Optional git hook to check before commits:

```bash
# .git/hooks/pre-commit
#!/bin/bash
./coordination/masters/cleanup/scan.sh --quick || {
    echo "⚠️  Cleanup scan found issues. Review before committing."
    exit 1
}
```

---

## Configuration

### Cleanup Rules (`config/cleanup-rules.json`)

```json
{
  "safe_to_remove": {
    "exclude_patterns": [
      "README", "LICENSE", "/lib/", "/config/", "/docs/"
    ],
    "confidence_threshold": 0.95
  },
  "auto_fix": {
    "enable_empty_directory_removal": true,
    "enable_permission_fixes": true,
    "enable_duplicate_removal": true,
    "enable_gitignore_cleanup": true,
    "enable_unreferenced_file_removal": false
  },
  "legacy_patterns": {
    "api_endpoints": ["localhost:3000", "api/achievements"],
    "old_project_names": ["commit-relay", "api-server"],
    "deprecated_systems": ["worker-pool.json", "dashboard-events"]
  },
  "priority_weights": {
    "broken_references": 10,
    "permission_issues": 9,
    "legacy_api_calls": 8,
    "unreferenced_files": 5
  }
}
```

---

## Scan Results

### Directory Structure

```
coordination/masters/cleanup/scans/
└── scan-20251127_143022/
    ├── summary.json                 # Overall summary
    ├── unreferenced-files.json      # Files not referenced anywhere
    ├── dead-functions.json          # Functions never called
    ├── empty-directories.json       # Empty directories
    ├── permission-issues.json       # Wrong file permissions
    ├── duplicate-files.json         # Duplicate content
    ├── broken-references.json       # Missing files/imports
    ├── legacy-api-calls.json        # Old API patterns
    ├── legacy-patterns.json         # Deprecated code patterns
    ├── gitignore-issues.json        # .gitignore inconsistencies
    ├── auto-fix-summary.json        # Auto-fix results
    └── CLEANUP-REPORT.md            # Human-readable report
```

### Example: Unreferenced Files

```json
{
  "scan_type": "unreferenced_files",
  "timestamp": "2025-11-27T20:30:22Z",
  "count": 12,
  "files": [
    "scripts/old-helper.sh",
    "coordination/legacy-config.json",
    "lib/deprecated-util.js"
  ]
}
```

### Example: Broken References

```json
{
  "scan_type": "broken_references",
  "timestamp": "2025-11-27T20:30:22Z",
  "count": 2,
  "references": [
    {
      "file": "scripts/main.sh",
      "missing_reference": "../lib/removed-module.sh",
      "type": "source"
    }
  ]
}
```

---

## Examples

### Example 1: After Removing API Server

```bash
# 1. Remove API server
rm -rf api-server/

# 2. Run cleanup scan
./coordination/masters/cleanup/scan.sh

# Output shows:
# - 10 unreferenced scripts calling APIs
# - 25 legacy API call patterns
# - 3 broken references to api-server

# 3. Review report
./coordination/masters/cleanup/report.sh

# 4. Auto-fix safe issues
./coordination/masters/cleanup/run.sh --auto-fix --live

# 5. Manually remove API-calling scripts
# (identified in report)
```

### Example 2: After Feature Implementation

```bash
# 1. Implement new feature
# Created 10 new files, modified 20 existing

# 2. Quick scan for cleanup
./coordination/masters/cleanup/scan.sh

# Output shows:
# - 3 empty test directories
# - 2 new scripts not executable
# - 1 duplicate utility function

# 3. Auto-fix
./coordination/masters/cleanup/run.sh --auto-fix --live

# Fixed:
# - Removed empty directories
# - Made scripts executable
# - Removed duplicate function
```

### Example 3: Weekly Proactive Cleanup

```bash
# Daemon runs weekly
# Sunday 2 AM:

# 1. Full scan
# 2. Auto-fix safe issues
# 3. Generate report
# 4. Email/notify of manual review items

# No action needed if clean
# Manual review email if issues found
```

---

## Best Practices

### When to Run Cleanup

1. **After removing features/infrastructure**
   - API servers, daemons, systems
   - Ensures all references are removed

2. **After major implementations**
   - Check for duplicates, orphaned files
   - Fix permissions on new scripts

3. **Weekly proactive scans**
   - Catch issues early
   - Maintain clean codebase

4. **Before major releases**
   - Clean up technical debt
   - Remove deprecated code

### Safety Guidelines

1. **Always dry-run first**
   ```bash
   ./coordination/masters/cleanup/run.sh --auto-fix
   # Review before:
   ./coordination/masters/cleanup/run.sh --auto-fix --live
   ```

2. **Review high-priority issues manually**
   - Broken references
   - Legacy API calls
   - Unreferenced files in /lib/ or /config/

3. **Use git for recovery**
   ```bash
   # Cleanup creates stash before changes
   git stash list
   git stash pop  # If needed
   ```

4. **Exclude critical patterns**
   - Edit `config/cleanup-rules.json`
   - Add to `exclude_patterns`

---

## Troubleshooting

### False Positives

**Issue:** Scanner marks file as unreferenced but it's imported dynamically

**Solution:** Add to exclude patterns in config:
```json
{
  "safe_to_remove": {
    "exclude_patterns": ["scripts/dynamic-loader/"]
  }
}
```

### Permission Denied

**Issue:** Auto-fix can't change permissions

**Solution:** Check file ownership:
```bash
ls -la <file>
sudo chown $USER <file>
```

### Scan Too Slow

**Issue:** Full scan takes too long

**Solution:** Exclude large directories:
```bash
# Edit scanner.sh, add to exclusions:
if echo "$relative_path" | grep -qE '(node_modules|\.git|large_data_dir)'; then
    continue
fi
```

---

## Future Enhancements

1. **Dependency Graph Analysis**
   - Build full dependency graph
   - Identify circular dependencies
   - Suggest refactoring opportunities

2. **Code Complexity Metrics**
   - Cyclomatic complexity
   - Lines of code per function
   - Suggest simplification

3. **Performance Hotspot Detection**
   - Profile script execution
   - Identify slow operations
   - Suggest optimizations

4. **Semantic Analysis**
   - Understand code intent
   - Better unreferenced detection
   - Context-aware recommendations

5. **Integration with CI/CD**
   - Block PRs with critical issues
   - Auto-comment on PRs
   - Track cleanup metrics over time

---

**The Cleanup Master keeps your codebase tidy! 🧹**
