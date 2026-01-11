/**
 * Worker Pool - Main Entry Point
 * High-performance persistent worker pool with automatic zombie detection and cleanup
 */

const WorkerPoolManager = require('./pool-manager');
const TaskQueue = require('./task-queue');
const HealthMonitor = require('./health-monitor');
const FIFOChannel = require('./fifo-channel');

/**
 * Create and initialize a worker pool
 * @param {Object} config - Pool configuration
 * @returns {Promise<WorkerPoolManager>} Initialized pool manager
 */
async function createWorkerPool(config = {}) {
  const pool = new WorkerPoolManager(config);
  await pool.initialize(config.poolSize);
  return pool;
}

/**
 * Create a worker pool (without initialization)
 * @param {Object} config - Pool configuration
 * @returns {WorkerPoolManager} Pool manager instance
 */
function createPool(config = {}) {
  return new WorkerPoolManager(config);
}

module.exports = {
  // Factory functions
  createWorkerPool,
  createPool,

  // Classes
  WorkerPoolManager,
  TaskQueue,
  HealthMonitor,
  FIFOChannel,

  // Default export
  default: createWorkerPool
};
