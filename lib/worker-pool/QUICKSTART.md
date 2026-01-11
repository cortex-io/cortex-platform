# Worker Pool Quick Start Guide

Get up and running with the Cortex Worker Pool in 5 minutes.

## 1. Test the Installation

Run the test suite to verify everything works:

```bash
cd /Users/ryandahlberg/Projects/cortex
node lib/worker-pool/test-pool.js
```

You should see:
- Pool initializes with 5 workers
- Tasks complete successfully
- Worker reuse rate is 95%+
- All tests pass

## 2. Try the Examples

Run the example usage file:

```bash
# Edit example-usage.js and uncomment the examples you want to try
node lib/worker-pool/example-usage.js
```

## 3. Basic Usage in Your Code

```javascript
const { createWorkerPool } = require('./lib/worker-pool');

async function main() {
  // Create pool
  const pool = await createWorkerPool({
    poolSize: 20
  });

  // Submit task
  const result = await pool.submitTask({
    type: 'test',
    payload: { message: 'Hello' }
  });

  console.log('Result:', result);

  // Shutdown
  await pool.shutdown(true);
}

main();
```

## 4. Start the Daemon (Optional)

For long-running pools:

```bash
# Start
./scripts/worker-pool-daemon.sh start

# Check status
./scripts/worker-pool-daemon.sh status

# Stop
./scripts/worker-pool-daemon.sh stop
```

## 5. Monitor Performance

```javascript
const pool = await createWorkerPool({ poolSize: 20 });

// Get metrics
const metrics = pool.getPoolMetrics();
console.log('Worker Reuse Rate:', metrics.performance.workerReuseRate);
console.log('Tasks Completed:', metrics.tasks.completed);
console.log('Pool Status:', metrics.health.status);
```

## What You Get

- **20 persistent workers** (no per-task spawning)
- **95%+ worker reuse** (workers stay alive between tasks)
- **Automatic zombie cleanup** (unhealthy workers auto-restart)
- **Priority task queue** (with retry logic)
- **Load balancing** (round-robin or least-loaded)
- **Health monitoring** (real-time metrics and alerts)

## Key Metrics to Watch

1. **Worker Reuse Rate**: Should be 95%+
2. **Pool Capacity**: Should be 100% (all workers healthy)
3. **Queue Depth**: Should be low (workers processing tasks quickly)
4. **Zombie Workers**: Should be 0 (auto-detected and restarted)

## Common Commands

```bash
# Run tests
node lib/worker-pool/test-pool.js

# Run examples
node lib/worker-pool/example-usage.js

# Start daemon
./scripts/worker-pool-daemon.sh start

# Check status
./scripts/worker-pool-daemon.sh status

# View logs
tail -f logs/worker-pool.log

# Stop daemon
./scripts/worker-pool-daemon.sh stop
```

## Next Steps

1. Read the full README.md for detailed API documentation
2. Review INTEGRATION.md to integrate with your existing code
3. Check example-usage.js for comprehensive examples
4. Monitor pool metrics during development
5. Adjust pool size based on your workload

## Troubleshooting

**Pool won't start?**
```bash
# Check Node.js version
node --version  # Should be 14.0.0+

# Clear temp files
rm -rf /tmp/cortex/workers/*
```

**Workers becoming zombies?**
```javascript
// Increase monitoring frequency
const pool = await createWorkerPool({
  heartbeatInterval: 3000  // Check every 3 seconds
});
```

**Need more workers?**
```javascript
// Scale up dynamically
await pool.scaleUp(10);  // Add 10 more workers
```

## Help

- Full documentation: `lib/worker-pool/README.md`
- Integration guide: `lib/worker-pool/INTEGRATION.md`
- Example code: `lib/worker-pool/example-usage.js`
- Test suite: `lib/worker-pool/test-pool.js`

## Verification Checklist

After setup, verify:

- [ ] Test suite passes (`node test-pool.js`)
- [ ] Pool initializes successfully
- [ ] Tasks complete and return results
- [ ] Worker reuse rate is >95%
- [ ] No zombie workers detected
- [ ] Memory usage is stable
- [ ] Graceful shutdown works

If all checks pass, you're ready to integrate with your Cortex project!
