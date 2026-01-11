# Event Archival and Compression

Automated archival system for Cortex event management with compression, rotation, and cleanup capabilities.

## Overview

The event archiver (`scripts/events/event-archiver.sh`) provides automated lifecycle management for event logs:

1. **Daily Archival** - Move processed events older than 24 hours to date-organized archives
2. **Compression** - Compress archives older than 7 days using gzip
3. **JSONL Rotation** - Rotate files exceeding 10MB to prevent performance degradation
4. **Cleanup** - Remove archives older than 90 days to manage disk space

## Quick Start

```bash
# Test with dry run (recommended first step)
./scripts/events/event-archiver.sh --dry-run --verbose

# Run full archival process
./scripts/events/event-archiver.sh

# Setup automated daily archival at 2 AM
./scripts/events/setup-archiver-cron.sh
```

## Usage

### Command Line Options

```bash
./scripts/events/event-archiver.sh [OPTIONS]

OPTIONS:
  --dry-run          Preview changes without executing
  --compress-only    Only compress archives older than 7 days
  --cleanup-only     Only delete archives older than 90 days
  --verbose, -v      Enable detailed logging
  --help, -h         Show help message
```

### Examples

```bash
# Preview what will be archived
./scripts/events/event-archiver.sh --dry-run

# Full archival with verbose output
./scripts/events/event-archiver.sh --verbose

# Only compress old archives
./scripts/events/event-archiver.sh --compress-only

# Only clean up archives older than 90 days
./scripts/events/event-archiver.sh --cleanup-only
```

## Archive Structure

```
coordination/events/
├── archive/
│   ├── 2025-12-01/                    # Daily archive directories
│   │   ├── heartbeat-events.jsonl
│   │   ├── daemon-supervisor-events.jsonl
│   │   └── zombie-cleanup-events.jsonl
│   ├── 2025-11-24/                    # Archives older than 7 days
│   │   ├── heartbeat-events.jsonl.gz  # Compressed
│   │   └── daemon-supervisor-events.jsonl.gz
│   ├── failed/                        # Failed event processing
│   └── invalid/                       # Invalid events
├── queue/                             # Pending events
├── heartbeat-events.jsonl             # Active event streams
├── daemon-supervisor-events.jsonl
└── .archiver.log                      # Archiver execution log
```

## Configuration

Default thresholds (configurable in script):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ARCHIVE_AGE_HOURS` | 24 | Archive events older than this |
| `COMPRESS_AGE_DAYS` | 7 | Compress archives older than this |
| `DELETE_AGE_DAYS` | 90 | Delete archives older than this |
| `ROTATION_SIZE_MB` | 10 | Rotate files larger than this |

### Customizing Thresholds

Edit `/Users/ryandahlberg/Projects/cortex/scripts/events/event-archiver.sh`:

```bash
# Change archival threshold to 48 hours
ARCHIVE_AGE_HOURS=48

# Compress after 14 days instead of 7
COMPRESS_AGE_DAYS=14

# Keep archives for 180 days instead of 90
DELETE_AGE_DAYS=180

# Rotate at 5MB instead of 10MB
ROTATION_SIZE_MB=5
```

## Automated Scheduling

### Setup with Cron

```bash
# Interactive setup (recommended)
./scripts/events/setup-archiver-cron.sh

# Or add to event processing setup
./scripts/setup-event-processing.sh
```

### Cron Schedule Options

1. **Daily at 2 AM** (recommended for most use cases)
   ```cron
   0 2 * * * cd /path/to/cortex && ./scripts/events/event-archiver.sh >> /var/log/cortex/archiver.log 2>&1
   ```

2. **Twice daily** (high-volume events)
   ```cron
   0 2,14 * * * cd /path/to/cortex && ./scripts/events/event-archiver.sh >> /var/log/cortex/archiver.log 2>&1
   ```

3. **Every 6 hours** (very high-volume events)
   ```cron
   0 */6 * * * cd /path/to/cortex && ./scripts/events/event-archiver.sh >> /var/log/cortex/archiver.log 2>&1
   ```

### Manual Cron Setup

```bash
# Edit crontab
crontab -e

# Add archiver job
0 2 * * * cd /Users/ryandahlberg/Projects/cortex && /Users/ryandahlberg/Projects/cortex/scripts/events/event-archiver.sh >> /var/log/cortex/archiver.log 2>&1
```

## Operations

### 1. Daily Archival

Moves events older than 24 hours from active JSONL files to date-organized archive directories.

**Process:**
- Read each active event file (`*.jsonl`)
- Parse event timestamps
- Split into current (keep) and archivable (move)
- Archive old events to `archive/YYYY-MM-DD/`
- Update active files with only recent events

**Example:**
```bash
# Events from 2025-11-30 in heartbeat-events.jsonl
# → Moved to archive/2025-11-30/heartbeat-events.jsonl
```

### 2. JSONL Rotation

Prevents active files from growing too large by rotating when they exceed 10MB.

**Process:**
- Check size of active JSONL files
- If > 10MB, rotate to archive with timestamp
- Create fresh active file
- Timestamp format: `{filename}-rotated-{timestamp}.jsonl`

**Example:**
```bash
# heartbeat-events.jsonl grows to 12MB
# → Rotated to archive/2025-12-01/heartbeat-events-rotated-20251201-140530.jsonl
# → New heartbeat-events.jsonl created
```

### 3. Compression

Compresses archives older than 7 days using gzip level 9 (maximum compression).

**Process:**
- Find archives in directories older than 7 days
- Compress uncompressed JSONL files with gzip -9
- Remove original uncompressed files
- Track space savings

**Compression ratios:**
- Heartbeat events: ~85% reduction (typical)
- JSON logs: ~75-90% reduction

**Example:**
```bash
# archive/2025-11-24/heartbeat-events.jsonl (2.5MB)
# → Compressed to heartbeat-events.jsonl.gz (350KB)
# → Saved 2.15MB
```

### 4. Cleanup

Removes archives older than 90 days to manage disk space.

**Process:**
- Find archive directories older than 90 days
- Calculate disk space to be freed
- Remove entire directory and contents
- Report deleted files and space freed

**Example:**
```bash
# archive/2025-09-01/ (older than 90 days)
# → Deleted entire directory (125MB freed)
```

### 5. Directory Cleanup

Removes empty archive directories to keep structure clean.

**Process:**
- Find all empty directories in archive
- Delete empty directories
- Preserve non-empty archives

## Monitoring

### Check Archiver Logs

```bash
# View recent archival activity
tail -f /var/log/cortex/archiver.log

# View archiver execution log
cat /Users/ryandahlberg/Projects/cortex/coordination/events/.archiver.log | tail -50

# Search for specific operations
grep "SUCCESS" /var/log/cortex/archiver.log
grep "ERROR" /var/log/cortex/archiver.log
```

### Disk Usage Monitoring

```bash
# Total events directory size
du -sh /Users/ryandahlberg/Projects/cortex/coordination/events

# Breakdown by subdirectory
du -sh /Users/ryandahlberg/Projects/cortex/coordination/events/*

# Archive size by date
du -sh /Users/ryandahlberg/Projects/cortex/coordination/events/archive/20??-??-??/

# Compressed vs uncompressed
find coordination/events/archive -name "*.gz" -exec du -ch {} + | tail -1
find coordination/events/archive -name "*.jsonl" ! -name "*.gz" -exec du -ch {} + | tail -1
```

### Archive Statistics

The archiver reports statistics after each run:

```
=======================================
  Event Archiver Summary
=======================================

Operations performed:
  Events archived:     11674
  Files compressed:    15
  Files deleted:       45
  Files rotated:       1
  Space freed:         234MB

Mode: LIVE (changes applied)
```

### Health Checks

```bash
# Check for archiver errors
grep "ERROR" /var/log/cortex/archiver.log | tail -20

# Verify cron job is scheduled
crontab -l | grep event-archiver

# Check last archival time
ls -lhtr /Users/ryandahlberg/Projects/cortex/coordination/events/archive/ | tail -5

# Verify compression is working
find /Users/ryandahlberg/Projects/cortex/coordination/events/archive -name "*.jsonl" ! -name "*.gz" -mtime +7
```

## Troubleshooting

### Issue: Events not being archived

**Check:**
```bash
# Verify events have timestamps
head -5 coordination/events/heartbeat-events.jsonl | jq -r '.timestamp'

# Check archiver is running
grep "Event Archiver Started" /var/log/cortex/archiver.log | tail -1

# Test with dry run
./scripts/events/event-archiver.sh --dry-run --verbose
```

### Issue: Compression not occurring

**Check:**
```bash
# Verify archives are old enough (>7 days)
find coordination/events/archive -name "*.jsonl" -mtime +7

# Check for compression errors
grep "compress" /var/log/cortex/archiver.log

# Test compression manually
gzip -9 -k coordination/events/archive/2025-11-20/heartbeat-events.jsonl
```

### Issue: Disk space still high

**Check:**
```bash
# Find large uncompressed archives
find coordination/events/archive -name "*.jsonl" ! -name "*.gz" -size +1M

# Check archive age distribution
find coordination/events/archive -name "20??-??-??" -type d | sort

# Run cleanup manually
./scripts/events/event-archiver.sh --cleanup-only
```

### Issue: Cron job not running

**Check:**
```bash
# Verify cron job exists
crontab -l | grep event-archiver

# Check cron is running
pgrep cron || pgrep crond

# Verify log file permissions
ls -l /var/log/cortex/archiver.log

# Test manual execution
/Users/ryandahlberg/Projects/cortex/scripts/events/event-archiver.sh --dry-run
```

## Performance

### Execution Time (typical)

| Operation | Time | Events Processed |
|-----------|------|------------------|
| Archival | 1-3 min | 10,000-50,000 events |
| Compression | 30-60 sec | 20-50 files |
| Cleanup | 5-10 sec | 10-30 directories |
| Rotation | 10-30 sec | 1-3 files |

### Disk Space Savings

| Period | Uncompressed | Compressed | Savings |
|--------|--------------|------------|---------|
| 1 week | 50MB | 50MB | 0% (not compressed yet) |
| 1 month | 200MB | 50MB + 30MB | 60% |
| 3 months | 600MB | 50MB + 90MB | 77% |

### Resource Usage

- CPU: Low (1-5% during execution)
- Memory: ~50MB typical
- I/O: Sequential reads/writes (efficient)
- Network: None

## Integration

### With Event Processing

The archiver works alongside the event dispatcher:

```bash
# Event flow
Event → Queue → Dispatcher → JSONL file → Archiver → Compressed archive → Deletion

# Timing
- Dispatcher runs every minute (processes new events)
- Archiver runs daily at 2 AM (manages old events)
```

### With Monitoring

Archive metrics feed into Cortex monitoring:

```bash
# Dashboard integration
- Track archive growth rate
- Monitor compression ratios
- Alert on disk usage thresholds
- Report archival failures
```

### With Backup

Archives should be included in backup strategy:

```bash
# Backup compressed archives
rsync -avz coordination/events/archive/*.gz backup-server:/cortex/archives/

# Exclude uncompressed (will be compressed soon)
# Exclude very old (will be deleted soon)
```

## Best Practices

1. **Run dry-run first** - Always test with `--dry-run` before first execution
2. **Monitor disk usage** - Set alerts at 80% capacity
3. **Schedule during off-hours** - Run at 2-3 AM when system is idle
4. **Verify compression** - Check compression ratios monthly
5. **Test restoration** - Periodically test decompressing and reading archives
6. **Adjust thresholds** - Tune based on event volume and disk space
7. **Log rotation** - Rotate archiver logs to prevent growth
8. **Backup strategy** - Include compressed archives in backups

## Recovery

### Restore archived events

```bash
# Decompress specific archive
gunzip -k coordination/events/archive/2025-11-20/heartbeat-events.jsonl.gz

# Read archived events
cat coordination/events/archive/2025-11-20/heartbeat-events.jsonl | jq -r '.event_type' | sort | uniq -c

# Restore to active file (if needed)
cat coordination/events/archive/2025-11-20/heartbeat-events.jsonl >> coordination/events/heartbeat-events.jsonl
```

### Emergency disk cleanup

```bash
# Immediate compression of all old archives
find coordination/events/archive -name "*.jsonl" ! -name "*.gz" -mtime +1 -exec gzip -9 {} \;

# Emergency deletion (use with caution)
find coordination/events/archive -name "20??-??-??" -mtime +30 -exec rm -rf {} \;
```

## See Also

- [Event-Driven Architecture](EVENT-DRIVEN-ARCHITECTURE.md)
- [Quick Start Guide](QUICK-START-EVENT-DRIVEN.md)
- [Event Processing Setup](../scripts/setup-event-processing.sh)
- [Event Dispatcher](../scripts/events/event-dispatcher.sh)
