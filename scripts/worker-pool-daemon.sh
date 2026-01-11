#!/bin/bash

###############################################################################
# Worker Pool Daemon
# Launches and manages the Cortex worker pool manager process
###############################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FIFO_DIR="${FIFO_DIR:-/tmp/cortex/workers}"
POOL_SIZE="${POOL_SIZE:-20}"
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/logs}"
PID_FILE="${PID_FILE:-/tmp/cortex/worker-pool.pid}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up worker pool daemon..."

    # Remove FIFO directory
    if [ -d "$FIFO_DIR" ]; then
        log_info "Removing FIFO directory: $FIFO_DIR"
        rm -rf "$FIFO_DIR"
    fi

    # Remove PID file
    if [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
    fi

    log_info "Cleanup complete"
}

# Signal handlers
handle_sigterm() {
    log_info "Received SIGTERM, shutting down gracefully..."
    cleanup
    exit 0
}

handle_sigint() {
    log_info "Received SIGINT, shutting down..."
    cleanup
    exit 0
}

# Setup signal traps
trap handle_sigterm SIGTERM
trap handle_sigint SIGINT

# Main function
main() {
    log_info "Starting Cortex Worker Pool Daemon"
    log_info "Project root: $PROJECT_ROOT"
    log_info "FIFO directory: $FIFO_DIR"
    log_info "Pool size: $POOL_SIZE"
    log_info "Log directory: $LOG_DIR"

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            log_error "Worker pool daemon already running (PID: $OLD_PID)"
            exit 1
        else
            log_warning "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi

    # Create required directories
    log_info "Creating required directories..."
    mkdir -p "$FIFO_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$(dirname "$PID_FILE")"

    # Set permissions
    chmod 755 "$FIFO_DIR"

    # Check for Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js not found. Please install Node.js to run the worker pool."
        exit 1
    fi

    NODE_VERSION=$(node --version)
    log_info "Using Node.js version: $NODE_VERSION"

    # Create daemon script if it doesn't exist
    DAEMON_SCRIPT="$PROJECT_ROOT/lib/worker-pool/daemon.js"
    if [ ! -f "$DAEMON_SCRIPT" ]; then
        log_info "Creating daemon script..."
        cat > "$DAEMON_SCRIPT" << 'EOF'
#!/usr/bin/env node

/**
 * Worker Pool Daemon Process
 */

const { createWorkerPool } = require('./index');
const fs = require('fs');
const path = require('path');

// Configuration from environment
const config = {
  poolSize: parseInt(process.env.POOL_SIZE || '20', 10),
  minWorkers: parseInt(process.env.MIN_WORKERS || '5', 10),
  maxWorkers: parseInt(process.env.MAX_WORKERS || '50', 10),
  fifoDir: process.env.FIFO_DIR || '/tmp/cortex/workers',
  heartbeatInterval: parseInt(process.env.HEARTBEAT_INTERVAL || '5000', 10),
  taskTimeout: parseInt(process.env.TASK_TIMEOUT || '300000', 10),
  loadBalancing: process.env.LOAD_BALANCING || 'round-robin',
  autoRestart: process.env.AUTO_RESTART !== 'false',
  logWorkerErrors: true,
  logWorkerWarnings: true
};

let pool = null;

async function start() {
  console.log('[Daemon] Starting worker pool with config:', config);

  try {
    // Create and initialize pool
    pool = await createWorkerPool(config);

    console.log('[Daemon] Worker pool initialized successfully');

    // Log metrics periodically
    setInterval(() => {
      const metrics = pool.getPoolMetrics();
      console.log('[Daemon] Pool metrics:', JSON.stringify(metrics, null, 2));
    }, 30000); // Every 30 seconds

    // Handle shutdown signals
    process.on('SIGTERM', async () => {
      console.log('[Daemon] Received SIGTERM, shutting down...');
      await shutdown();
    });

    process.on('SIGINT', async () => {
      console.log('[Daemon] Received SIGINT, shutting down...');
      await shutdown();
    });

  } catch (error) {
    console.error('[Daemon] Failed to start worker pool:', error);
    process.exit(1);
  }
}

async function shutdown() {
  if (pool) {
    console.log('[Daemon] Shutting down worker pool...');
    await pool.shutdown(true);
    console.log('[Daemon] Worker pool shut down complete');
  }
  process.exit(0);
}

// Start the daemon
start().catch(error => {
  console.error('[Daemon] Fatal error:', error);
  process.exit(1);
});
EOF
        chmod +x "$DAEMON_SCRIPT"
    fi

    # Write PID file
    echo $$ > "$PID_FILE"
    log_info "Daemon PID: $$"

    # Start the worker pool
    log_info "Launching worker pool manager..."

    export POOL_SIZE
    export FIFO_DIR

    # Run the daemon script
    node "$DAEMON_SCRIPT" 2>&1 | tee "$LOG_DIR/worker-pool.log"

    # If we get here, the daemon exited
    DAEMON_EXIT_CODE=$?

    if [ $DAEMON_EXIT_CODE -ne 0 ]; then
        log_error "Worker pool daemon exited with code: $DAEMON_EXIT_CODE"
    else
        log_info "Worker pool daemon exited normally"
    fi

    cleanup
    exit $DAEMON_EXIT_CODE
}

# Command handling
case "${1:-start}" in
    start)
        main
        ;;

    stop)
        log_info "Stopping worker pool daemon..."
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                log_info "Sending SIGTERM to PID: $PID"
                kill -TERM "$PID"

                # Wait for process to exit
                for i in {1..30}; do
                    if ! kill -0 "$PID" 2>/dev/null; then
                        log_info "Daemon stopped"
                        cleanup
                        exit 0
                    fi
                    sleep 1
                done

                # Force kill if still running
                log_warning "Daemon did not stop gracefully, force killing..."
                kill -KILL "$PID" 2>/dev/null || true
                cleanup
            else
                log_warning "PID file exists but process not running"
                cleanup
            fi
        else
            log_warning "No PID file found, daemon may not be running"
        fi
        ;;

    restart)
        log_info "Restarting worker pool daemon..."
        "$0" stop
        sleep 2
        "$0" start
        ;;

    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                log_info "Worker pool daemon is running (PID: $PID)"
                exit 0
            else
                log_warning "PID file exists but process not running"
                exit 1
            fi
        else
            log_warning "Worker pool daemon is not running"
            exit 1
        fi
        ;;

    cleanup)
        cleanup
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|status|cleanup}"
        echo ""
        echo "Environment variables:"
        echo "  POOL_SIZE         - Number of workers (default: 20)"
        echo "  FIFO_DIR          - FIFO directory path (default: /tmp/cortex/workers)"
        echo "  LOG_DIR           - Log directory path (default: PROJECT_ROOT/logs)"
        echo "  PID_FILE          - PID file path (default: /tmp/cortex/worker-pool.pid)"
        exit 1
        ;;
esac
