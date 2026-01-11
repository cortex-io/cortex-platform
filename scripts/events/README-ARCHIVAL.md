# Event Archival Quick Reference

## Quick Start

```bash
# 1. Test (recommended first step)
./event-archiver.sh --dry-run --verbose

# 2. Run manually
./event-archiver.sh

# 3. Setup automated daily run
./setup-archiver-cron.sh
```

## Common Commands

### Archiver Operations

```bash
# Full archival process
./event-archiver.sh

# Preview without changes
./event-archiver.sh --dry-run

# Only compress old archives
./event-archiver.sh --compress-only

# Only cleanup archives > 90 days
./event-archiver.sh --cleanup-only

# Verbose output
./event-archiver.sh --verbose
```

### Archive Utilities

```bash
# Show statistics
./archive-utils.sh stats

# Search for pattern
./archive-utils.sh search "worker_failure"

# List all archives
./archive-utils.sh list

# List specific date
./archive-utils.sh list 2025-11-20

# Size by event type
./archive-utils.sh size

# Decompress date
./archive-utils.sh decompress 2025-11-20

# Restore events
./archive-utils.sh restore 2025-11-20 heartbeat

# Verify integrity
./archive-utils.sh verify

# Cleanup temp files
./archive-utils.sh cleanup-temp
```

## Monitoring

```bash
# Check last run
tail -50 ../../coordination/events/.archiver.log

# View cron logs
tail -f /var/log/cortex/archiver.log

# Check disk usage
du -sh ../../coordination/events

# Archive statistics
./archive-utils.sh stats
```

## Troubleshooting

```bash
# Test with dry-run
./event-archiver.sh --dry-run --verbose

# Check for errors
grep "ERROR" /var/log/cortex/archiver.log

# Verify cron job
crontab -l | grep event-archiver

# Emergency cleanup
./event-archiver.sh --cleanup-only
```

## Configuration

Default thresholds (edit `event-archiver.sh`):

```bash
ARCHIVE_AGE_HOURS=24       # Archive after 24 hours
COMPRESS_AGE_DAYS=7        # Compress after 7 days
DELETE_AGE_DAYS=90         # Delete after 90 days
ROTATION_SIZE_MB=10        # Rotate at 10MB
```

## Archive Lifecycle

```
New Event (active JSONL)
    ↓ 24 hours
Archived (archive/YYYY-MM-DD/*.jsonl)
    ↓ 7 days
Compressed (archive/YYYY-MM-DD/*.jsonl.gz)
    ↓ 90 days
Deleted
```

## Files

- `event-archiver.sh` - Main archival script
- `setup-archiver-cron.sh` - Cron setup utility
- `archive-utils.sh` - Archive management tools
- `../../docs/EVENT-ARCHIVAL.md` - Full documentation

## Cron Schedule

Recommended (daily at 2 AM):
```cron
0 2 * * * cd /path/to/cortex && ./scripts/events/event-archiver.sh >> /var/log/cortex/archiver.log 2>&1
```

High-volume (every 6 hours):
```cron
0 */6 * * * cd /path/to/cortex && ./scripts/events/event-archiver.sh >> /var/log/cortex/archiver.log 2>&1
```

## Help

```bash
./event-archiver.sh --help
./archive-utils.sh help
cat ../../docs/EVENT-ARCHIVAL.md
```
