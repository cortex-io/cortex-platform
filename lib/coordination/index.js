/**
 * Coordination module exports
 * Factory functions for creating coordination components
 */

const { CoordinationDaemon, WorkerStatus, TaskStatus } = require('./daemon');
const { StateStore, PersistenceStrategy } = require('./state-store');
const { MessageBus, Priority, DeliveryGuarantee } = require('./message-bus');

/**
 * Create a coordination daemon with configuration
 * @param {Object} config Configuration options
 * @returns {CoordinationDaemon}
 */
function createCoordinationDaemon(config = {}) {
  return new CoordinationDaemon(config);
}

/**
 * Create a state store with configuration
 * @param {Object} config Configuration options
 * @returns {StateStore}
 */
function createStateStore(config = {}) {
  return new StateStore(config);
}

/**
 * Create a message bus with configuration
 * @param {Object} config Configuration options
 * @returns {MessageBus}
 */
function createMessageBus(config = {}) {
  return new MessageBus(config);
}

/**
 * Default configuration presets
 */
const ConfigPresets = {
  /**
   * Development preset - memory only, verbose logging
   */
  development: {
    port: 9500,
    wsPort: 9501,
    persistence: PersistenceStrategy.MEMORY_ONLY,
    heartbeatInterval: 5000,
    heartbeatTimeout: 15000
  },

  /**
   * Production preset - periodic snapshots, optimized performance
   */
  production: {
    port: 9500,
    wsPort: 9501,
    persistence: PersistenceStrategy.PERIODIC_SNAPSHOT,
    snapshotInterval: 30000,
    snapshotPath: './coordination/state-snapshot.json',
    heartbeatInterval: 5000,
    heartbeatTimeout: 15000,
    maxTasksPerWorker: 10
  },

  /**
   * High availability preset - WAL for durability
   */
  highAvailability: {
    port: 9500,
    wsPort: 9501,
    persistence: PersistenceStrategy.WAL,
    walPath: './coordination/wal.log',
    walSyncInterval: 1000,
    snapshotInterval: 60000,
    snapshotPath: './coordination/state-snapshot.json',
    heartbeatInterval: 3000,
    heartbeatTimeout: 10000,
    maxTasksPerWorker: 5
  },

  /**
   * Testing preset - memory only, fast heartbeats
   */
  testing: {
    port: 9500,
    wsPort: 9501,
    persistence: PersistenceStrategy.MEMORY_ONLY,
    heartbeatInterval: 1000,
    heartbeatTimeout: 3000,
    maxTasksPerWorker: 5
  }
};

/**
 * Get configuration preset
 * @param {string} preset Preset name (development, production, highAvailability, testing)
 * @param {Object} overrides Optional configuration overrides
 * @returns {Object} Configuration object
 */
function getConfigPreset(preset, overrides = {}) {
  const baseConfig = ConfigPresets[preset];
  if (!baseConfig) {
    throw new Error(`Unknown preset: ${preset}. Available: ${Object.keys(ConfigPresets).join(', ')}`);
  }
  return { ...baseConfig, ...overrides };
}

module.exports = {
  // Factory functions
  createCoordinationDaemon,
  createStateStore,
  createMessageBus,

  // Classes (for advanced usage)
  CoordinationDaemon,
  StateStore,
  MessageBus,

  // Constants
  WorkerStatus,
  TaskStatus,
  PersistenceStrategy,
  Priority,
  DeliveryGuarantee,

  // Configuration
  ConfigPresets,
  getConfigPreset
};
