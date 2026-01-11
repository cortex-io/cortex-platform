/**
 * High-performance state store for coordination daemon
 * Supports multiple persistence strategies and efficient in-memory operations
 */

const fs = require('fs').promises;
const path = require('path');
const EventEmitter = require('events');

/**
 * Persistence strategies
 */
const PersistenceStrategy = {
  MEMORY_ONLY: 'memory-only',
  WAL: 'write-ahead-log',
  PERIODIC_SNAPSHOT: 'periodic-snapshot'
};

/**
 * High-performance state store with configurable persistence
 */
class StateStore extends EventEmitter {
  /**
   * @param {Object} config Configuration options
   * @param {string} config.persistence - Persistence strategy (memory-only, write-ahead-log, periodic-snapshot)
   * @param {string} config.snapshotPath - Path for snapshot files
   * @param {number} config.snapshotInterval - Interval for periodic snapshots (ms)
   * @param {string} config.walPath - Path for write-ahead-log
   * @param {number} config.walSyncInterval - WAL sync interval (ms)
   */
  constructor(config = {}) {
    super();

    this.config = {
      persistence: config.persistence || PersistenceStrategy.MEMORY_ONLY,
      snapshotPath: config.snapshotPath || './coordination/state-snapshot.json',
      snapshotInterval: config.snapshotInterval || 30000,
      walPath: config.walPath || './coordination/wal.log',
      walSyncInterval: config.walSyncInterval || 1000,
      ...config
    };

    // Core state storage using Maps for O(1) operations
    this.state = {
      workers: new Map(),           // workerId -> worker metadata
      tasks: new Map(),              // taskId -> task data
      assignments: new Map(),        // taskId -> workerId
      workerTasks: new Map(),        // workerId -> Set of taskIds
      metadata: new Map(),           // general metadata storage
      timestamps: new Map()          // entity -> last modified timestamp
    };

    // Transaction support
    this.transactionLog = [];
    this.currentTransaction = null;

    // Performance metrics
    this.metrics = {
      operations: 0,
      transactions: 0,
      snapshots: 0,
      walWrites: 0,
      lastSnapshot: null,
      lastWalSync: null
    };

    // WAL buffer for batching
    this.walBuffer = [];

    // Timers
    this.snapshotTimer = null;
    this.walTimer = null;

    this._initialized = false;
  }

  /**
   * Initialize the state store
   */
  async initialize() {
    if (this._initialized) {
      return;
    }

    // Load existing state from disk if available
    await this._loadState();

    // Start periodic tasks based on persistence strategy
    if (this.config.persistence === PersistenceStrategy.PERIODIC_SNAPSHOT) {
      this._startSnapshotTimer();
    } else if (this.config.persistence === PersistenceStrategy.WAL) {
      this._startWalTimer();
    }

    this._initialized = true;
    this.emit('initialized');
  }

  /**
   * Load state from disk
   */
  async _loadState() {
    try {
      if (this.config.persistence === PersistenceStrategy.MEMORY_ONLY) {
        return;
      }

      // Try to load from snapshot first
      const snapshotExists = await this._fileExists(this.config.snapshotPath);
      if (snapshotExists) {
        const data = await fs.readFile(this.config.snapshotPath, 'utf8');
        const snapshot = JSON.parse(data);
        this._deserializeState(snapshot);
        this.emit('state-loaded', { source: 'snapshot', path: this.config.snapshotPath });
      }

      // Apply WAL entries if using WAL strategy
      if (this.config.persistence === PersistenceStrategy.WAL) {
        await this._replayWal();
      }
    } catch (error) {
      this.emit('error', { operation: 'load-state', error: error.message });
      // Continue with empty state on error
    }
  }

  /**
   * Check if file exists
   */
  async _fileExists(filePath) {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Deserialize state from snapshot
   */
  _deserializeState(snapshot) {
    if (snapshot.workers) {
      this.state.workers = new Map(Object.entries(snapshot.workers));
    }
    if (snapshot.tasks) {
      this.state.tasks = new Map(Object.entries(snapshot.tasks));
    }
    if (snapshot.assignments) {
      this.state.assignments = new Map(Object.entries(snapshot.assignments));
    }
    if (snapshot.workerTasks) {
      this.state.workerTasks = new Map(
        Object.entries(snapshot.workerTasks).map(([k, v]) => [k, new Set(v)])
      );
    }
    if (snapshot.metadata) {
      this.state.metadata = new Map(Object.entries(snapshot.metadata));
    }
    if (snapshot.timestamps) {
      this.state.timestamps = new Map(Object.entries(snapshot.timestamps));
    }
  }

  /**
   * Serialize state to snapshot format
   */
  _serializeState() {
    return {
      workers: Object.fromEntries(this.state.workers),
      tasks: Object.fromEntries(this.state.tasks),
      assignments: Object.fromEntries(this.state.assignments),
      workerTasks: Object.fromEntries(
        Array.from(this.state.workerTasks.entries()).map(([k, v]) => [k, Array.from(v)])
      ),
      metadata: Object.fromEntries(this.state.metadata),
      timestamps: Object.fromEntries(this.state.timestamps),
      snapshot_timestamp: new Date().toISOString(),
      metrics: this.metrics
    };
  }

  /**
   * Start periodic snapshot timer
   */
  _startSnapshotTimer() {
    this.snapshotTimer = setInterval(async () => {
      await this.snapshot();
    }, this.config.snapshotInterval);
  }

  /**
   * Start WAL sync timer
   */
  _startWalTimer() {
    this.walTimer = setInterval(async () => {
      await this._syncWal();
    }, this.config.walSyncInterval);
  }

  /**
   * Create a snapshot of current state
   */
  async snapshot() {
    try {
      const serialized = this._serializeState();
      const snapshotDir = path.dirname(this.config.snapshotPath);

      // Ensure directory exists
      await fs.mkdir(snapshotDir, { recursive: true });

      // Write snapshot atomically
      const tempPath = `${this.config.snapshotPath}.tmp`;
      await fs.writeFile(tempPath, JSON.stringify(serialized, null, 2));
      await fs.rename(tempPath, this.config.snapshotPath);

      this.metrics.snapshots++;
      this.metrics.lastSnapshot = new Date().toISOString();

      this.emit('snapshot-created', {
        path: this.config.snapshotPath,
        timestamp: this.metrics.lastSnapshot
      });

      return true;
    } catch (error) {
      this.emit('error', { operation: 'snapshot', error: error.message });
      return false;
    }
  }

  /**
   * Write operation to WAL
   */
  async _writeWal(operation) {
    if (this.config.persistence !== PersistenceStrategy.WAL) {
      return;
    }

    this.walBuffer.push({
      operation,
      timestamp: Date.now()
    });
  }

  /**
   * Sync WAL buffer to disk
   */
  async _syncWal() {
    if (this.walBuffer.length === 0) {
      return;
    }

    try {
      const walDir = path.dirname(this.config.walPath);
      await fs.mkdir(walDir, { recursive: true });

      const entries = this.walBuffer.splice(0);
      const walData = entries.map(e => JSON.stringify(e)).join('\n') + '\n';

      await fs.appendFile(this.config.walPath, walData);

      this.metrics.walWrites++;
      this.metrics.lastWalSync = new Date().toISOString();

      this.emit('wal-synced', { entries: entries.length });
    } catch (error) {
      this.emit('error', { operation: 'wal-sync', error: error.message });
      // Put entries back if sync failed
      this.walBuffer.unshift(...entries);
    }
  }

  /**
   * Replay WAL entries
   */
  async _replayWal() {
    try {
      const walExists = await this._fileExists(this.config.walPath);
      if (!walExists) {
        return;
      }

      const data = await fs.readFile(this.config.walPath, 'utf8');
      const lines = data.trim().split('\n');

      for (const line of lines) {
        if (!line) continue;
        const entry = JSON.parse(line);
        await this._applyOperation(entry.operation);
      }

      this.emit('wal-replayed', { entries: lines.length });
    } catch (error) {
      this.emit('error', { operation: 'wal-replay', error: error.message });
    }
  }

  /**
   * Apply an operation to state
   */
  async _applyOperation(operation) {
    const { type, key, value, collection } = operation;

    switch (type) {
      case 'set':
        this.state[collection].set(key, value);
        break;
      case 'delete':
        this.state[collection].delete(key);
        break;
      case 'update':
        const existing = this.state[collection].get(key);
        this.state[collection].set(key, { ...existing, ...value });
        break;
    }
  }

  /**
   * Begin a transaction
   */
  beginTransaction() {
    if (this.currentTransaction) {
      throw new Error('Transaction already in progress');
    }

    this.currentTransaction = {
      id: `txn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      operations: [],
      rollbackData: new Map()
    };

    return this.currentTransaction.id;
  }

  /**
   * Commit a transaction
   */
  async commitTransaction() {
    if (!this.currentTransaction) {
      throw new Error('No transaction in progress');
    }

    const txn = this.currentTransaction;

    try {
      // Write to WAL if enabled
      if (this.config.persistence === PersistenceStrategy.WAL) {
        for (const op of txn.operations) {
          await this._writeWal(op);
        }
      }

      this.metrics.transactions++;
      this.currentTransaction = null;

      this.emit('transaction-committed', {
        transactionId: txn.id,
        operations: txn.operations.length
      });

      return true;
    } catch (error) {
      await this.rollbackTransaction();
      throw error;
    }
  }

  /**
   * Rollback a transaction
   */
  async rollbackTransaction() {
    if (!this.currentTransaction) {
      throw new Error('No transaction in progress');
    }

    const txn = this.currentTransaction;

    // Restore previous values
    for (const [key, data] of txn.rollbackData) {
      const { collection, value } = data;
      if (value === undefined) {
        this.state[collection].delete(key);
      } else {
        this.state[collection].set(key, value);
      }
    }

    this.emit('transaction-rolled-back', { transactionId: txn.id });
    this.currentTransaction = null;
  }

  /**
   * Set a value in state
   */
  set(collection, key, value) {
    this._validateCollection(collection);

    const operation = { type: 'set', collection, key, value, timestamp: Date.now() };

    // Handle transactions
    if (this.currentTransaction) {
      const existing = this.state[collection].get(key);
      this.currentTransaction.rollbackData.set(key, { collection, value: existing });
      this.currentTransaction.operations.push(operation);
    } else if (this.config.persistence === PersistenceStrategy.WAL) {
      this._writeWal(operation);
    }

    this.state[collection].set(key, value);
    this.state.timestamps.set(`${collection}:${key}`, Date.now());
    this.metrics.operations++;

    this.emit('state-changed', { collection, key, operation: 'set' });

    return true;
  }

  /**
   * Get a value from state
   */
  get(collection, key) {
    this._validateCollection(collection);
    return this.state[collection].get(key);
  }

  /**
   * Delete a value from state
   */
  delete(collection, key) {
    this._validateCollection(collection);

    const operation = { type: 'delete', collection, key, timestamp: Date.now() };

    // Handle transactions
    if (this.currentTransaction) {
      const existing = this.state[collection].get(key);
      this.currentTransaction.rollbackData.set(key, { collection, value: existing });
      this.currentTransaction.operations.push(operation);
    } else if (this.config.persistence === PersistenceStrategy.WAL) {
      this._writeWal(operation);
    }

    const result = this.state[collection].delete(key);
    this.state.timestamps.delete(`${collection}:${key}`);
    this.metrics.operations++;

    this.emit('state-changed', { collection, key, operation: 'delete' });

    return result;
  }

  /**
   * Update a value (merge with existing)
   */
  update(collection, key, updates) {
    this._validateCollection(collection);

    const existing = this.state[collection].get(key) || {};
    const updated = { ...existing, ...updates };

    return this.set(collection, key, updated);
  }

  /**
   * Get all values from a collection
   */
  getAll(collection) {
    this._validateCollection(collection);
    return Array.from(this.state[collection].values());
  }

  /**
   * Get all entries from a collection
   */
  getAllEntries(collection) {
    this._validateCollection(collection);
    return Array.from(this.state[collection].entries());
  }

  /**
   * Check if key exists
   */
  has(collection, key) {
    this._validateCollection(collection);
    return this.state[collection].has(key);
  }

  /**
   * Get collection size
   */
  size(collection) {
    this._validateCollection(collection);
    const value = this.state[collection];
    return value instanceof Map ? value.size : 0;
  }

  /**
   * Clear a collection
   */
  clear(collection) {
    this._validateCollection(collection);
    this.state[collection].clear();
    this.emit('collection-cleared', { collection });
  }

  /**
   * Validate collection name
   */
  _validateCollection(collection) {
    if (!this.state.hasOwnProperty(collection)) {
      throw new Error(`Invalid collection: ${collection}`);
    }
  }

  /**
   * Get full state (for debugging/monitoring)
   */
  getState() {
    return {
      workers: Array.from(this.state.workers.entries()),
      tasks: Array.from(this.state.tasks.entries()),
      assignments: Array.from(this.state.assignments.entries()),
      workerTasks: Array.from(this.state.workerTasks.entries()).map(([k, v]) => [k, Array.from(v)]),
      metadata: Array.from(this.state.metadata.entries()),
      metrics: this.metrics
    };
  }

  /**
   * Get metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      collections: {
        workers: this.state.workers.size,
        tasks: this.state.tasks.size,
        assignments: this.state.assignments.size,
        workerTasks: this.state.workerTasks.size,
        metadata: this.state.metadata.size
      }
    };
  }

  /**
   * Graceful shutdown
   */
  async shutdown() {
    // Clear timers
    if (this.snapshotTimer) {
      clearInterval(this.snapshotTimer);
    }
    if (this.walTimer) {
      clearInterval(this.walTimer);
    }

    // Final snapshot/sync
    if (this.config.persistence === PersistenceStrategy.PERIODIC_SNAPSHOT) {
      await this.snapshot();
    } else if (this.config.persistence === PersistenceStrategy.WAL) {
      await this._syncWal();
    }

    this.emit('shutdown');
  }
}

module.exports = { StateStore, PersistenceStrategy };
