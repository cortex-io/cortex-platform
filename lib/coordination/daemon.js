/**
 * Main Coordination Daemon
 * High-performance coordination server with EventEmitter-based pub/sub
 * Target: 1,000 ops/second with <100ms latency
 */

const EventEmitter = require('events');
const http = require('http');
const express = require('express');
const WebSocket = require('ws');
const { StateStore, PersistenceStrategy } = require('./state-store');
const { MessageBus, Priority, DeliveryGuarantee } = require('./message-bus');

/**
 * Worker status constants
 */
const WorkerStatus = {
  IDLE: 'idle',
  BUSY: 'busy',
  OFFLINE: 'offline',
  ERROR: 'error'
};

/**
 * Task status constants
 */
const TaskStatus = {
  PENDING: 'pending',
  ASSIGNED: 'assigned',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
};

/**
 * Main coordination daemon
 */
class CoordinationDaemon extends EventEmitter {
  /**
   * @param {Object} config Configuration options
   */
  constructor(config = {}) {
    super();

    this.config = {
      port: config.port || 9500,
      wsPort: config.wsPort || 9501,
      host: config.host || '0.0.0.0',
      persistence: config.persistence || PersistenceStrategy.PERIODIC_SNAPSHOT,
      snapshotInterval: config.snapshotInterval || 30000,
      snapshotPath: config.snapshotPath || './coordination/state-snapshot.json',
      walPath: config.walPath || './coordination/wal.log',
      heartbeatInterval: config.heartbeatInterval || 5000,
      heartbeatTimeout: config.heartbeatTimeout || 15000,
      enableCors: config.enableCors !== false,
      maxTasksPerWorker: config.maxTasksPerWorker || 10,
      ...config
    };

    // Initialize components
    this.stateStore = new StateStore({
      persistence: this.config.persistence,
      snapshotPath: this.config.snapshotPath,
      snapshotInterval: this.config.snapshotInterval,
      walPath: this.config.walPath
    });

    this.messageBus = new MessageBus({
      processingInterval: 10,
      maxQueueSize: 100000
    });

    // HTTP/WebSocket servers
    this.httpServer = null;
    this.wsServer = null;
    this.app = null;

    // WebSocket connections
    this.wsConnections = new Map(); // workerId -> WebSocket

    // Performance metrics
    this.metrics = {
      startTime: null,
      operations: 0,
      operationsPerSecond: 0,
      averageLatency: 0,
      activeWorkers: 0,
      activeTasks: 0,
      totalTasksProcessed: 0,
      totalTasksFailed: 0
    };

    // Latency tracking
    this.latencies = [];
    this.maxLatencySamples = 1000;

    // Heartbeat monitoring
    this.heartbeatTimer = null;

    this._initialized = false;
  }

  /**
   * Initialize the daemon
   */
  async initialize() {
    if (this._initialized) {
      return;
    }

    // Initialize state store
    await this.stateStore.initialize();

    // Setup message bus event handlers
    this._setupMessageBusHandlers();

    // Setup state store event handlers
    this._setupStateStoreHandlers();

    // Initialize HTTP server
    this._initializeHttpServer();

    // Initialize WebSocket server
    this._initializeWebSocketServer();

    this._initialized = true;
    this.emit('initialized');
  }

  /**
   * Setup message bus event handlers
   */
  _setupMessageBusHandlers() {
    this.messageBus.on('message-delivered', (data) => {
      this.emit('message-delivered', data);
    });

    this.messageBus.on('message-failed', (data) => {
      this.emit('message-failed', data);
    });

    this.messageBus.on('error', (data) => {
      this.emit('error', { source: 'message-bus', ...data });
    });
  }

  /**
   * Setup state store event handlers
   */
  _setupStateStoreHandlers() {
    this.stateStore.on('state-changed', (data) => {
      // Broadcast state changes to WebSocket clients
      this._broadcastStateChange(data);
      this.emit('state-changed', data);
    });

    this.stateStore.on('snapshot-created', (data) => {
      this.emit('snapshot-created', data);
    });

    this.stateStore.on('error', (data) => {
      this.emit('error', { source: 'state-store', ...data });
    });
  }

  /**
   * Initialize HTTP server for REST API
   */
  _initializeHttpServer() {
    this.app = express();

    // Middleware
    this.app.use(express.json());

    if (this.config.enableCors) {
      this.app.use((req, res, next) => {
        res.header('Access-Control-Allow-Origin', '*');
        res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
        next();
      });
    }

    // Health check
    this.app.get('/health', (req, res) => {
      res.json({
        status: 'healthy',
        uptime: Date.now() - this.metrics.startTime,
        version: '1.0.0'
      });
    });

    // Get full state
    this.app.get('/api/state', (req, res) => {
      const startTime = Date.now();
      const state = this.getState();
      this._recordLatency(Date.now() - startTime);
      res.json(state);
    });

    // Get metrics
    this.app.get('/api/metrics', (req, res) => {
      res.json(this.getMetrics());
    });

    // Register worker
    this.app.post('/api/workers/register', async (req, res) => {
      const startTime = Date.now();
      try {
        const { workerId, capabilities, metadata } = req.body;

        if (!workerId) {
          return res.status(400).json({ error: 'workerId is required' });
        }

        const result = await this.registerWorker(workerId, capabilities, metadata);
        this._recordLatency(Date.now() - startTime);

        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    // Unregister worker
    this.app.post('/api/workers/unregister', async (req, res) => {
      const startTime = Date.now();
      try {
        const { workerId } = req.body;

        if (!workerId) {
          return res.status(400).json({ error: 'workerId is required' });
        }

        const result = await this.unregisterWorker(workerId);
        this._recordLatency(Date.now() - startTime);

        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    // Get all workers
    this.app.get('/api/workers', (req, res) => {
      const workers = this.stateStore.getAll('workers');
      res.json({ workers });
    });

    // Get worker by ID
    this.app.get('/api/workers/:workerId', (req, res) => {
      const worker = this.stateStore.get('workers', req.params.workerId);
      if (!worker) {
        return res.status(404).json({ error: 'Worker not found' });
      }
      res.json(worker);
    });

    // Assign task
    this.app.post('/api/tasks/assign', async (req, res) => {
      const startTime = Date.now();
      try {
        const { taskId, workerId, taskData } = req.body;

        if (!taskId) {
          return res.status(400).json({ error: 'taskId is required' });
        }

        const result = await this.assignTask(taskId, workerId, taskData);
        this._recordLatency(Date.now() - startTime);

        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    // Complete task
    this.app.post('/api/tasks/complete', async (req, res) => {
      const startTime = Date.now();
      try {
        const { taskId, result } = req.body;

        if (!taskId) {
          return res.status(400).json({ error: 'taskId is required' });
        }

        const response = await this.completeTask(taskId, result);
        this._recordLatency(Date.now() - startTime);

        res.json(response);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    // Fail task
    this.app.post('/api/tasks/fail', async (req, res) => {
      const startTime = Date.now();
      try {
        const { taskId, error } = req.body;

        if (!taskId) {
          return res.status(400).json({ error: 'taskId is required' });
        }

        const response = await this.failTask(taskId, error);
        this._recordLatency(Date.now() - startTime);

        res.json(response);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    // Get all tasks
    this.app.get('/api/tasks', (req, res) => {
      const tasks = this.stateStore.getAll('tasks');
      res.json({ tasks });
    });

    // Get task by ID
    this.app.get('/api/tasks/:taskId', (req, res) => {
      const task = this.stateStore.get('tasks', req.params.taskId);
      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }
      res.json(task);
    });

    // Trigger snapshot
    this.app.post('/api/snapshot', async (req, res) => {
      try {
        await this.stateStore.snapshot();
        res.json({ success: true, message: 'Snapshot created' });
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    this.httpServer = http.createServer(this.app);
  }

  /**
   * Initialize WebSocket server for real-time communication
   */
  _initializeWebSocketServer() {
    this.wsServer = new WebSocket.Server({
      port: this.config.wsPort,
      perMessageDeflate: false // Disable compression for lower latency
    });

    this.wsServer.on('connection', (ws, req) => {
      let workerId = null;

      ws.on('message', async (data) => {
        try {
          const message = JSON.parse(data);

          switch (message.type) {
            case 'register':
              workerId = message.workerId;
              this.wsConnections.set(workerId, ws);
              await this.registerWorker(workerId, message.capabilities, message.metadata);
              ws.send(JSON.stringify({
                type: 'registered',
                workerId,
                timestamp: Date.now()
              }));
              break;

            case 'heartbeat':
              this._handleHeartbeat(message.workerId);
              ws.send(JSON.stringify({
                type: 'heartbeat_ack',
                timestamp: Date.now()
              }));
              break;

            case 'task_update':
              await this._handleTaskUpdate(message);
              break;

            case 'subscribe':
              // Subscribe to specific state changes
              this._handleSubscribe(ws, workerId, message.topics);
              break;

            default:
              ws.send(JSON.stringify({
                type: 'error',
                message: `Unknown message type: ${message.type}`
              }));
          }
        } catch (error) {
          ws.send(JSON.stringify({
            type: 'error',
            message: error.message
          }));
        }
      });

      ws.on('close', () => {
        if (workerId) {
          this.wsConnections.delete(workerId);
          // Mark worker as offline
          const worker = this.stateStore.get('workers', workerId);
          if (worker) {
            this.stateStore.update('workers', workerId, {
              status: WorkerStatus.OFFLINE,
              lastSeen: Date.now()
            });
          }
        }
      });

      ws.on('error', (error) => {
        this.emit('ws-error', { workerId, error: error.message });
      });
    });
  }

  /**
   * Handle heartbeat from worker
   */
  _handleHeartbeat(workerId) {
    const worker = this.stateStore.get('workers', workerId);
    if (worker) {
      this.stateStore.update('workers', workerId, {
        lastHeartbeat: Date.now(),
        status: worker.activeTasks > 0 ? WorkerStatus.BUSY : WorkerStatus.IDLE
      });
    }
  }

  /**
   * Handle task update from worker
   */
  async _handleTaskUpdate(message) {
    const { taskId, status, progress, result, error } = message;

    const task = this.stateStore.get('tasks', taskId);
    if (!task) {
      return;
    }

    const updates = {
      status,
      lastUpdate: Date.now()
    };

    if (progress !== undefined) {
      updates.progress = progress;
    }

    if (status === TaskStatus.COMPLETED && result) {
      updates.result = result;
      updates.completedAt = Date.now();
      await this.completeTask(taskId, result);
    } else if (status === TaskStatus.FAILED && error) {
      updates.error = error;
      updates.failedAt = Date.now();
      await this.failTask(taskId, error);
    } else {
      this.stateStore.update('tasks', taskId, updates);
    }
  }

  /**
   * Handle WebSocket subscription
   */
  _handleSubscribe(ws, workerId, topics) {
    // Store subscription information
    const worker = this.stateStore.get('workers', workerId);
    if (worker) {
      this.stateStore.update('workers', workerId, {
        subscriptions: topics
      });
    }
  }

  /**
   * Broadcast state change to WebSocket clients
   */
  _broadcastStateChange(change) {
    const message = JSON.stringify({
      type: 'state_change',
      change,
      timestamp: Date.now()
    });

    for (const [workerId, ws] of this.wsConnections) {
      if (ws.readyState === WebSocket.OPEN) {
        const worker = this.stateStore.get('workers', workerId);
        if (worker && worker.subscriptions) {
          // Only send if worker is subscribed to this type of change
          const topic = `${change.collection}:${change.operation}`;
          if (worker.subscriptions.includes(topic) || worker.subscriptions.includes('*')) {
            ws.send(message);
          }
        }
      }
    }
  }

  /**
   * Send message to specific worker via WebSocket
   */
  _sendToWorker(workerId, message) {
    const ws = this.wsConnections.get(workerId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
      return true;
    }
    return false;
  }

  /**
   * Start heartbeat monitoring
   */
  _startHeartbeatMonitoring() {
    this.heartbeatTimer = setInterval(() => {
      const now = Date.now();
      const workers = this.stateStore.getAll('workers');

      for (const worker of workers) {
        if (worker.status === WorkerStatus.OFFLINE) {
          continue;
        }

        const timeSinceHeartbeat = now - worker.lastHeartbeat;

        if (timeSinceHeartbeat > this.config.heartbeatTimeout) {
          // Worker is unresponsive
          this.stateStore.update('workers', worker.id, {
            status: WorkerStatus.OFFLINE,
            lastSeen: now
          });

          // Reassign tasks if any
          this._reassignWorkerTasks(worker.id);

          this.emit('worker-timeout', { workerId: worker.id });
        }
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * Reassign tasks from an offline worker
   */
  async _reassignWorkerTasks(workerId) {
    const workerTasks = this.stateStore.get('workerTasks', workerId);
    if (!workerTasks || workerTasks.size === 0) {
      return;
    }

    for (const taskId of workerTasks) {
      const task = this.stateStore.get('tasks', taskId);
      if (task && task.status !== TaskStatus.COMPLETED) {
        // Reset task for reassignment
        this.stateStore.update('tasks', taskId, {
          status: TaskStatus.PENDING,
          assignedTo: null,
          reassignedFrom: workerId,
          reassignedAt: Date.now()
        });

        this.stateStore.delete('assignments', taskId);

        this.emit('task-reassigned', { taskId, fromWorker: workerId });
      }
    }

    // Clear worker tasks
    this.stateStore.set('workerTasks', workerId, new Set());
  }

  /**
   * Register a worker
   */
  async registerWorker(workerId, capabilities = [], metadata = {}) {
    const worker = {
      id: workerId,
      capabilities,
      metadata,
      status: WorkerStatus.IDLE,
      activeTasks: 0,
      completedTasks: 0,
      failedTasks: 0,
      registeredAt: Date.now(),
      lastHeartbeat: Date.now(),
      lastSeen: Date.now(),
      subscriptions: metadata.subscriptions || ['*']
    };

    this.stateStore.set('workers', workerId, worker);
    this.stateStore.set('workerTasks', workerId, new Set());

    this.metrics.activeWorkers++;

    this.emit('worker-registered', { workerId, capabilities });

    return { success: true, worker };
  }

  /**
   * Unregister a worker
   */
  async unregisterWorker(workerId) {
    const worker = this.stateStore.get('workers', workerId);
    if (!worker) {
      return { success: false, error: 'Worker not found' };
    }

    // Reassign tasks
    await this._reassignWorkerTasks(workerId);

    // Remove worker
    this.stateStore.delete('workers', workerId);
    this.stateStore.delete('workerTasks', workerId);
    this.wsConnections.delete(workerId);

    this.metrics.activeWorkers--;

    this.emit('worker-unregistered', { workerId });

    return { success: true };
  }

  /**
   * Assign a task to a worker
   */
  async assignTask(taskId, workerId = null, taskData = {}) {
    // If no worker specified, find best available worker
    if (!workerId) {
      workerId = this._findBestWorker(taskData.capabilities);
      if (!workerId) {
        return { success: false, error: 'No available workers' };
      }
    }

    const worker = this.stateStore.get('workers', workerId);
    if (!worker) {
      return { success: false, error: 'Worker not found' };
    }

    if (worker.status === WorkerStatus.OFFLINE) {
      return { success: false, error: 'Worker is offline' };
    }

    // Check worker capacity
    if (worker.activeTasks >= this.config.maxTasksPerWorker) {
      return { success: false, error: 'Worker at capacity' };
    }

    // Create or update task
    const task = {
      id: taskId,
      ...taskData,
      status: TaskStatus.ASSIGNED,
      assignedTo: workerId,
      assignedAt: Date.now(),
      lastUpdate: Date.now()
    };

    this.stateStore.set('tasks', taskId, task);
    this.stateStore.set('assignments', taskId, workerId);

    // Update worker task list
    const workerTasks = this.stateStore.get('workerTasks', workerId) || new Set();
    workerTasks.add(taskId);
    this.stateStore.set('workerTasks', workerId, workerTasks);

    // Update worker
    this.stateStore.update('workers', workerId, {
      activeTasks: workerTasks.size,
      status: WorkerStatus.BUSY
    });

    this.metrics.activeTasks++;

    // Notify worker via WebSocket
    this._sendToWorker(workerId, {
      type: 'task_assigned',
      task,
      timestamp: Date.now()
    });

    this.emit('task-assigned', { taskId, workerId });

    return { success: true, task, workerId };
  }

  /**
   * Find best available worker for task
   */
  _findBestWorker(requiredCapabilities = []) {
    const workers = this.stateStore.getAll('workers');

    // Filter available workers
    const available = workers.filter(w =>
      w.status === WorkerStatus.IDLE ||
      (w.status === WorkerStatus.BUSY && w.activeTasks < this.config.maxTasksPerWorker)
    );

    if (available.length === 0) {
      return null;
    }

    // Filter by capabilities if specified
    let candidates = available;
    if (requiredCapabilities.length > 0) {
      candidates = available.filter(w =>
        requiredCapabilities.every(cap => w.capabilities.includes(cap))
      );
    }

    if (candidates.length === 0) {
      return null;
    }

    // Find worker with least active tasks
    candidates.sort((a, b) => a.activeTasks - b.activeTasks);

    return candidates[0].id;
  }

  /**
   * Complete a task
   */
  async completeTask(taskId, result = {}) {
    const task = this.stateStore.get('tasks', taskId);
    if (!task) {
      return { success: false, error: 'Task not found' };
    }

    const workerId = task.assignedTo;

    // Update task
    this.stateStore.update('tasks', taskId, {
      status: TaskStatus.COMPLETED,
      result,
      completedAt: Date.now()
    });

    // Update worker
    if (workerId) {
      const worker = this.stateStore.get('workers', workerId);
      if (worker) {
        const workerTasks = this.stateStore.get('workerTasks', workerId);
        if (workerTasks) {
          workerTasks.delete(taskId);
          this.stateStore.set('workerTasks', workerId, workerTasks);
        }

        this.stateStore.update('workers', workerId, {
          activeTasks: workerTasks ? workerTasks.size : 0,
          completedTasks: worker.completedTasks + 1,
          status: workerTasks && workerTasks.size > 0 ? WorkerStatus.BUSY : WorkerStatus.IDLE
        });
      }
    }

    this.stateStore.delete('assignments', taskId);

    this.metrics.activeTasks--;
    this.metrics.totalTasksProcessed++;

    this.emit('task-completed', { taskId, workerId, result });

    return { success: true, task };
  }

  /**
   * Fail a task
   */
  async failTask(taskId, error = {}) {
    const task = this.stateStore.get('tasks', taskId);
    if (!task) {
      return { success: false, error: 'Task not found' };
    }

    const workerId = task.assignedTo;

    // Update task
    this.stateStore.update('tasks', taskId, {
      status: TaskStatus.FAILED,
      error,
      failedAt: Date.now()
    });

    // Update worker
    if (workerId) {
      const worker = this.stateStore.get('workers', workerId);
      if (worker) {
        const workerTasks = this.stateStore.get('workerTasks', workerId);
        if (workerTasks) {
          workerTasks.delete(taskId);
          this.stateStore.set('workerTasks', workerId, workerTasks);
        }

        this.stateStore.update('workers', workerId, {
          activeTasks: workerTasks ? workerTasks.size : 0,
          failedTasks: worker.failedTasks + 1,
          status: workerTasks && workerTasks.size > 0 ? WorkerStatus.BUSY : WorkerStatus.IDLE
        });
      }
    }

    this.stateStore.delete('assignments', taskId);

    this.metrics.activeTasks--;
    this.metrics.totalTasksFailed++;

    this.emit('task-failed', { taskId, workerId, error });

    return { success: true, task };
  }

  /**
   * Get full coordination state
   */
  getState() {
    return {
      workers: this.stateStore.getAll('workers'),
      tasks: this.stateStore.getAll('tasks'),
      assignments: this.stateStore.getAllEntries('assignments'),
      metadata: {
        totalWorkers: this.stateStore.size('workers'),
        totalTasks: this.stateStore.size('tasks'),
        activeAssignments: this.stateStore.size('assignments')
      }
    };
  }

  /**
   * Subscribe to state changes
   */
  subscribeToChanges(callback) {
    this.on('state-changed', callback);
    return () => this.off('state-changed', callback);
  }

  /**
   * Record operation latency
   */
  _recordLatency(latency) {
    this.latencies.push(latency);

    if (this.latencies.length > this.maxLatencySamples) {
      this.latencies.shift();
    }

    const sum = this.latencies.reduce((a, b) => a + b, 0);
    this.metrics.averageLatency = sum / this.latencies.length;
    this.metrics.operations++;
  }

  /**
   * Calculate operations per second
   */
  _calculateOpsPerSecond() {
    if (!this.metrics.startTime) {
      return 0;
    }

    const elapsed = (Date.now() - this.metrics.startTime) / 1000;
    return elapsed > 0 ? Math.round(this.metrics.operations / elapsed) : 0;
  }

  /**
   * Get metrics
   */
  getMetrics() {
    const stateMetrics = this.stateStore.getMetrics();
    const messageBusMetrics = this.messageBus.getMetrics();

    return {
      daemon: {
        ...this.metrics,
        operationsPerSecond: this._calculateOpsPerSecond(),
        uptime: this.metrics.startTime ? Date.now() - this.metrics.startTime : 0
      },
      stateStore: stateMetrics,
      messageBus: messageBusMetrics,
      websockets: {
        connections: this.wsConnections.size
      }
    };
  }

  /**
   * Start the daemon
   */
  async start() {
    if (!this._initialized) {
      await this.initialize();
    }

    // Start message bus
    this.messageBus.start();

    // Start HTTP server
    await new Promise((resolve, reject) => {
      this.httpServer.listen(this.config.port, this.config.host, (err) => {
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });

    // Start heartbeat monitoring
    this._startHeartbeatMonitoring();

    this.metrics.startTime = Date.now();

    this.emit('started', {
      httpPort: this.config.port,
      wsPort: this.config.wsPort
    });

    console.log(`Coordination Daemon started`);
    console.log(`  HTTP API: http://${this.config.host}:${this.config.port}`);
    console.log(`  WebSocket: ws://${this.config.host}:${this.config.wsPort}`);
    console.log(`  Persistence: ${this.config.persistence}`);
  }

  /**
   * Stop the daemon
   */
  async stop() {
    // Stop heartbeat monitoring
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }

    // Close WebSocket connections
    for (const ws of this.wsConnections.values()) {
      ws.close();
    }

    // Close WebSocket server
    if (this.wsServer) {
      await new Promise((resolve) => {
        this.wsServer.close(resolve);
      });
    }

    // Close HTTP server
    if (this.httpServer) {
      await new Promise((resolve) => {
        this.httpServer.close(resolve);
      });
    }

    // Stop message bus
    this.messageBus.stop();

    // Shutdown state store
    await this.stateStore.shutdown();

    this.emit('stopped');

    console.log('Coordination Daemon stopped');
  }
}

module.exports = { CoordinationDaemon, WorkerStatus, TaskStatus };
