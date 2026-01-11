#!/usr/bin/env node

/**
 * Coordination Daemon CLI
 * Start the coordination daemon with command-line configuration
 */

const path = require('path');
const { createCoordinationDaemon, getConfigPreset, PersistenceStrategy } = require('../lib/coordination');

// Parse command line arguments
const args = process.argv.slice(2);

const config = {
  port: 9500,
  wsPort: 9501,
  host: '0.0.0.0',
  persistence: PersistenceStrategy.PERIODIC_SNAPSHOT,
  snapshotInterval: 30000,
  snapshotPath: './coordination/state-snapshot.json',
  walPath: './coordination/wal.log'
};

// Parse command line arguments
for (let i = 0; i < args.length; i++) {
  const arg = args[i];

  switch (arg) {
    case '--port':
    case '-p':
      config.port = parseInt(args[++i], 10);
      break;

    case '--ws-port':
    case '-w':
      config.wsPort = parseInt(args[++i], 10);
      break;

    case '--host':
    case '-h':
      config.host = args[++i];
      break;

    case '--persistence':
      config.persistence = args[++i];
      break;

    case '--snapshot-interval':
      config.snapshotInterval = parseInt(args[++i], 10);
      break;

    case '--snapshot-path':
      config.snapshotPath = args[++i];
      break;

    case '--wal-path':
      config.walPath = args[++i];
      break;

    case '--preset':
      const preset = args[++i];
      const presetConfig = getConfigPreset(preset);
      Object.assign(config, presetConfig);
      break;

    case '--max-tasks-per-worker':
      config.maxTasksPerWorker = parseInt(args[++i], 10);
      break;

    case '--heartbeat-interval':
      config.heartbeatInterval = parseInt(args[++i], 10);
      break;

    case '--heartbeat-timeout':
      config.heartbeatTimeout = parseInt(args[++i], 10);
      break;

    case '--help':
      printHelp();
      process.exit(0);
      break;

    default:
      console.error(`Unknown argument: ${arg}`);
      printHelp();
      process.exit(1);
  }
}

/**
 * Print help message
 */
function printHelp() {
  console.log(`
Coordination Daemon CLI

Usage: node coordination-daemon.js [options]

Options:
  --port, -p <port>              HTTP API port (default: 9500)
  --ws-port, -w <port>           WebSocket port (default: 9501)
  --host, -h <host>              Bind host (default: 0.0.0.0)
  --persistence <mode>           Persistence mode (memory-only, periodic-snapshot, write-ahead-log)
  --snapshot-interval <ms>       Snapshot interval in milliseconds (default: 30000)
  --snapshot-path <path>         Path for snapshot files (default: ./coordination/state-snapshot.json)
  --wal-path <path>              Path for write-ahead-log (default: ./coordination/wal.log)
  --preset <name>                Use configuration preset (development, production, highAvailability, testing)
  --max-tasks-per-worker <n>     Maximum tasks per worker (default: 10)
  --heartbeat-interval <ms>      Heartbeat check interval (default: 5000)
  --heartbeat-timeout <ms>       Heartbeat timeout (default: 15000)
  --help                         Show this help message

Examples:
  # Start with default configuration
  node coordination-daemon.js

  # Start with production preset
  node coordination-daemon.js --preset production

  # Start with custom configuration
  node coordination-daemon.js --port 8080 --persistence memory-only

  # Start with write-ahead-log persistence
  node coordination-daemon.js --persistence write-ahead-log --wal-path ./coordination/wal.log

Environment Variables:
  COORDINATION_PORT              HTTP API port (overrides --port)
  COORDINATION_WS_PORT           WebSocket port (overrides --ws-port)
  COORDINATION_PERSISTENCE       Persistence mode (overrides --persistence)
  COORDINATION_SNAPSHOT_PATH     Snapshot path (overrides --snapshot-path)
  COORDINATION_WAL_PATH          WAL path (overrides --wal-path)
  `);
}

/**
 * Apply environment variable overrides
 */
if (process.env.COORDINATION_PORT) {
  config.port = parseInt(process.env.COORDINATION_PORT, 10);
}

if (process.env.COORDINATION_WS_PORT) {
  config.wsPort = parseInt(process.env.COORDINATION_WS_PORT, 10);
}

if (process.env.COORDINATION_PERSISTENCE) {
  config.persistence = process.env.COORDINATION_PERSISTENCE;
}

if (process.env.COORDINATION_SNAPSHOT_PATH) {
  config.snapshotPath = process.env.COORDINATION_SNAPSHOT_PATH;
}

if (process.env.COORDINATION_WAL_PATH) {
  config.walPath = process.env.COORDINATION_WAL_PATH;
}

/**
 * Create and start the daemon
 */
async function main() {
  console.log('Starting Coordination Daemon...');
  console.log('Configuration:', JSON.stringify(config, null, 2));

  const daemon = createCoordinationDaemon(config);

  // Setup event handlers
  daemon.on('started', (data) => {
    console.log(`\nCoordination Daemon started successfully!`);
    console.log(`  HTTP API: http://${config.host}:${data.httpPort}`);
    console.log(`  WebSocket: ws://${config.host}:${data.wsPort}`);
    console.log(`  Health check: http://${config.host}:${data.httpPort}/health`);
    console.log(`  Metrics: http://${config.host}:${data.httpPort}/api/metrics`);
    console.log(`\nPress Ctrl+C to stop\n`);
  });

  daemon.on('worker-registered', (data) => {
    console.log(`[WORKER] Registered: ${data.workerId} (capabilities: ${data.capabilities.join(', ') || 'none'})`);
  });

  daemon.on('worker-unregistered', (data) => {
    console.log(`[WORKER] Unregistered: ${data.workerId}`);
  });

  daemon.on('worker-timeout', (data) => {
    console.log(`[WORKER] Timeout: ${data.workerId} - marking as offline`);
  });

  daemon.on('task-assigned', (data) => {
    console.log(`[TASK] Assigned: ${data.taskId} -> ${data.workerId}`);
  });

  daemon.on('task-completed', (data) => {
    console.log(`[TASK] Completed: ${data.taskId} by ${data.workerId}`);
  });

  daemon.on('task-failed', (data) => {
    console.log(`[TASK] Failed: ${data.taskId} by ${data.workerId}`);
  });

  daemon.on('task-reassigned', (data) => {
    console.log(`[TASK] Reassigned: ${data.taskId} from ${data.fromWorker}`);
  });

  daemon.on('snapshot-created', (data) => {
    console.log(`[STATE] Snapshot created: ${data.path} at ${data.timestamp}`);
  });

  daemon.on('error', (data) => {
    console.error(`[ERROR] ${data.source || 'daemon'}:`, data.error || data);
  });

  // Graceful shutdown
  let shuttingDown = false;

  const shutdown = async (signal) => {
    if (shuttingDown) {
      return;
    }

    shuttingDown = true;
    console.log(`\n\nReceived ${signal}, shutting down gracefully...`);

    try {
      // Display final metrics
      const metrics = daemon.getMetrics();
      console.log('\nFinal Metrics:');
      console.log(`  Total operations: ${metrics.daemon.operations}`);
      console.log(`  Operations/sec: ${metrics.daemon.operationsPerSecond}`);
      console.log(`  Average latency: ${metrics.daemon.averageLatency.toFixed(2)}ms`);
      console.log(`  Active workers: ${metrics.daemon.activeWorkers}`);
      console.log(`  Tasks processed: ${metrics.daemon.totalTasksProcessed}`);
      console.log(`  Tasks failed: ${metrics.daemon.totalTasksFailed}`);
      console.log(`  Uptime: ${Math.round(metrics.daemon.uptime / 1000)}s`);

      await daemon.stop();
      console.log('\nDaemon stopped successfully');
      process.exit(0);
    } catch (error) {
      console.error('Error during shutdown:', error);
      process.exit(1);
    }
  };

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));

  // Handle uncaught errors
  process.on('uncaughtException', (error) => {
    console.error('Uncaught exception:', error);
    shutdown('uncaughtException');
  });

  process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled rejection at:', promise, 'reason:', reason);
    shutdown('unhandledRejection');
  });

  // Start the daemon
  try {
    await daemon.start();

    // Display periodic metrics
    setInterval(() => {
      const metrics = daemon.getMetrics();
      console.log(`[METRICS] Ops/sec: ${metrics.daemon.operationsPerSecond} | ` +
                  `Latency: ${metrics.daemon.averageLatency.toFixed(2)}ms | ` +
                  `Workers: ${metrics.daemon.activeWorkers} | ` +
                  `Active tasks: ${metrics.daemon.activeTasks} | ` +
                  `Queue: ${metrics.messageBus.queueDepth}`);
    }, 10000); // Every 10 seconds

  } catch (error) {
    console.error('Failed to start daemon:', error);
    process.exit(1);
  }
}

// Run main
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
