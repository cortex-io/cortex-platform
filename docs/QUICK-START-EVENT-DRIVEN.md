# Quick Start: Event-Driven Architecture

Get up and running with Cortex's new event-driven architecture in 5 minutes.

---

## Prerequisites

- Bash 4.0+
- jq (JSON processor)
- Python 3.11+ (for AI notebooks)
- Quarto (optional, for reports)

---

## Installation

### 1. Verify Setup

```bash
cd /path/to/cortex

# Check that event infrastructure exists
ls scripts/events/event-dispatcher.sh
ls scripts/events/handlers/

# Make sure scripts are executable
chmod +x scripts/events/*.sh
chmod +x scripts/events/lib/*.sh
chmod +x scripts/events/handlers/*.sh
```

### 2. Test Event System

```bash
# Run test suite
./scripts/events/test-event-flow.sh
```

You should see:
```
✓ Event ID Generation
✓ Event Validation
✓ Event Creation
✓ Event Logging
✓ Event Dispatcher
✓ Worker Complete Handler
✓ Task Failure Handler

Passed: 7
Failed: 0

✓ All tests passed!
```

---

## Basic Usage

### Create Your First Event

```bash
# Create a worker completion event
./scripts/events/lib/event-logger.sh --create \
    "worker.completed" \
    "my-worker-001" \
    '{"worker_id": "my-worker-001", "status": "completed", "tokens_used": 1234}' \
    "my-task-001" \
    "medium"
```

This will:
1. Generate a unique event ID
2. Validate the event structure
3. Log to `coordination/events/worker-events.jsonl`
4. Queue for processing in `coordination/events/queue/`

### Process Events

```bash
# Process all queued events
./scripts/events/event-dispatcher.sh
```

The dispatcher will:
1. Read events from the queue
2. Route to appropriate handlers
3. Archive processed events
4. Exit when queue is empty

### View Event Logs

```bash
# View all worker events
cat coordination/events/worker-events.jsonl | jq '.'

# Watch events in real-time
tail -f coordination/events/*.jsonl | jq '.'

# Count events by type
jq -r '.event_type' coordination/events/*.jsonl | sort | uniq -c
```

---

## Automated Event Processing

### Option 1: Cron Job (Simple)

Add to your crontab:

```bash
# Edit crontab
crontab -e

# Add this line (process events every minute)
* * * * * cd /path/to/cortex && ./scripts/events/event-dispatcher.sh >> /var/log/cortex-events.log 2>&1
```

### Option 2: Filesystem Watch (Immediate)

Using `fswatch` (macOS/Linux):

```bash
# Install fswatch
brew install fswatch  # macOS
# or: apt-get install fswatch  # Linux

# Watch queue directory and process immediately
fswatch -0 coordination/events/queue | while read -d "" event; do
    ./scripts/events/event-dispatcher.sh
done
```

---

## Migrate from Daemons

### Stop Running Daemons

```bash
# Find running daemons
ps aux | grep daemon.sh

# Stop specific daemon
pkill -f heartbeat-monitor-daemon.sh

# Or stop all
pkill -f "daemon.sh"
```

### Enable Event Processing

```bash
# Set up cron for automated event processing (see above)
crontab -e

# Or run dispatcher manually when needed
./scripts/events/event-dispatcher.sh
```

### Update Your Scripts

Replace daemon calls with event creation:

**Before (daemon-based):**
```bash
# Worker completed - daemon would poll for this
echo "completed" > /tmp/worker-status
```

**After (event-driven):**
```bash
# Worker completed - emit event
./scripts/events/lib/event-logger.sh --create \
    "worker.completed" \
    "$WORKER_ID" \
    "{\"worker_id\": \"$WORKER_ID\", \"status\": \"completed\"}" \
    "$TASK_ID" \
    "medium" | ./scripts/events/lib/event-logger.sh
```

---

## AI-Powered Analysis

### Install Python Dependencies

```bash
cd analysis
pip install -r requirements.txt
```

### Run Marimo Notebooks

```bash
# Interactive routing optimization
marimo edit analysis/routing-optimization.py

# Or run as web app
marimo run analysis/routing-optimization.py --port 8080

# Then open: http://localhost:8080
```

### Available Notebooks

1. **routing-optimization.py** - Analyze MoE routing decisions
2. **security-dashboard.py** - Security scan analysis
3. **worker-performance.py** - Worker metrics and optimization

Each notebook includes:
- Real-time data visualization
- AI-powered insights (requires `ANTHROPIC_API_KEY`)
- Interactive filtering and exploration

---

## Generate Reports

### Install Quarto

```bash
# macOS
brew install quarto

# Linux
# Download from https://quarto.org/docs/get-started/
```

### Render Reports

```bash
cd reports

# Set API key for AI insights (optional)
export ANTHROPIC_API_KEY="your-key-here"

# Render weekly summary
quarto render weekly-summary.qmd

# View output
open weekly-summary.html

# Or render all reports
quarto render
```

### Automated Reports via GitHub Actions

Reports are automatically generated weekly via GitHub Actions:

1. Push to GitHub
2. Reports generate every Monday at 9 AM
3. Published to GitHub Pages
4. View at: `https://your-username.github.io/cortex/reports/`

---

## Common Event Types

### Worker Events

```bash
# Worker started
./scripts/events/lib/event-logger.sh --create "worker.started" "$WORKER_ID" \
    "{\"worker_id\": \"$WORKER_ID\"}" "$TASK_ID" "low"

# Worker completed
./scripts/events/lib/event-logger.sh --create "worker.completed" "$WORKER_ID" \
    "{\"worker_id\": \"$WORKER_ID\", \"status\": \"completed\", \"tokens_used\": $TOKENS}" \
    "$TASK_ID" "medium"

# Worker heartbeat
./scripts/events/lib/event-logger.sh --create "worker.heartbeat" "$WORKER_ID" \
    "{\"worker_id\": \"$WORKER_ID\", \"heartbeat_time\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}" \
    "$WORKER_ID" "low"
```

### Task Events

```bash
# Task failed
./scripts/events/lib/event-logger.sh --create "task.failed" "task-processor" \
    "{\"task_id\": \"$TASK_ID\", \"error_type\": \"timeout\", \"error_message\": \"Task exceeded limit\"}" \
    "$TASK_ID" "high"
```

### System Events

```bash
# Cleanup needed
./scripts/events/lib/event-logger.sh --create "system.cleanup_needed" "cleanup-scheduler" \
    "{\"cleanup_type\": \"old_events\"}" "system" "low"

# Health alert
./scripts/events/lib/event-logger.sh --create "system.health_alert" "health-monitor" \
    "{\"alert_type\": \"high_latency\", \"value\": 5000}" "system" "critical"
```

---

## Monitoring

### Queue Depth

```bash
# Check how many events are waiting
ls coordination/events/queue/*.json 2>/dev/null | wc -l

# Alert if queue > 100
QUEUE_DEPTH=$(ls coordination/events/queue/*.json 2>/dev/null | wc -l)
if [ $QUEUE_DEPTH -gt 100 ]; then
    echo "WARNING: Event queue depth is $QUEUE_DEPTH"
fi
```

### Event Processing Rate

```bash
# Count events processed in last hour
find coordination/events/archive/$(date +%Y-%m-%d)/ -name "*.json" -mmin -60 | wc -l
```

### Handler Health

```bash
# Check for handler errors
grep "ERROR" /var/log/cortex-events.log | tail -20

# Check handler performance
grep "Handler completed" /var/log/cortex-events.log | \
    awk '{print $NF}' | sort | uniq -c
```

---

## Troubleshooting

### Events Not Processing

```bash
# 1. Check queue has events
ls coordination/events/queue/

# 2. Run dispatcher manually with verbose output
./scripts/events/event-dispatcher.sh 2>&1

# 3. Check handler permissions
ls -l scripts/events/handlers/

# 4. Test specific handler
./scripts/events/handlers/on-worker-complete.sh \
    coordination/events/queue/some-event.json
```

### Invalid Events

```bash
# Validate an event
./scripts/events/lib/event-validator.sh "$(cat my-event.json)"

# Check event schema
cat scripts/events/event-schema.json | jq '.'
```

### Performance Issues

```bash
# Check system resources
top -p $(pgrep -f event-dispatcher)

# Check queue depth (should be near 0)
watch -n 1 'ls coordination/events/queue/*.json 2>/dev/null | wc -l'

# Monitor event processing
tail -f /var/log/cortex-events.log
```

---

## Next Steps

1. **Integrate with Existing Scripts**
   - Replace daemon calls with event emissions
   - Update worker completion hooks
   - Add event logging to critical operations

2. **Set Up Monitoring**
   - Configure cron for automated processing
   - Set up alerts for queue depth
   - Monitor handler performance

3. **Explore AI Analysis**
   - Install Python dependencies
   - Run Marimo notebooks
   - Generate weekly reports

4. **Customize Handlers**
   - Review handler logic in `scripts/events/handlers/`
   - Add custom handlers for specific events
   - Adjust thresholds and alerts

---

## Resources

- **Full Documentation**: `docs/EVENT-DRIVEN-ARCHITECTURE.md`
- **Architecture Plan**: `ARCHITECTURE-EVOLUTION.md`
- **Event Schema**: `scripts/events/event-schema.json`
- **Test Suite**: `scripts/events/test-event-flow.sh`

---

## Getting Help

```bash
# Run tests
./scripts/events/test-event-flow.sh

# Check event validator
./scripts/events/lib/event-validator.sh --help

# Review handler code
cat scripts/events/handlers/on-worker-complete.sh
```

**Questions?** Review the full documentation in `docs/EVENT-DRIVEN-ARCHITECTURE.md`
