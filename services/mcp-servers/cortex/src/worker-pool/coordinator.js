#!/usr/bin/env node

/**
 * Worker Pool Coordinator
 *
 * Coordinates task distribution across worker pools and aggregates results.
 * Implements multiple coordination strategies for parallel execution.
 */

const { EventEmitter } = require('events');
const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');

class WorkerCoordinator extends EventEmitter {
  constructor(spawner, config = {}) {
    super();

    this.spawner = spawner;
    this.config = {
      cortexRoot: config.cortexRoot || process.env.CORTEX_ROOT || '/Users/ryandahlberg/Projects/cortex',
      aggregationStrategy: config.aggregationStrategy || 'consensus', // consensus, voting, merge, reduce
      taskTimeout: config.taskTimeout || 300000, // 5 minutes
      retryAttempts: config.retryAttempts || 2,
      ...config
    };

    // Active coordinations
    this.coordinations = new Map(); // coordinationId -> coordination state
    this.taskQueue = []; // Pending tasks

    // Task assignments
    this.taskAssignments = new Map(); // taskId -> workerId

    // Results cache
    this.results = new Map(); // taskId -> result
  }

  /**
   * Coordinate a parallel task execution across multiple workers
   * @param {Object} options - Coordination options
   * @returns {Promise<Object>} Aggregated results
   */
  async coordinate(options) {
    const {
      taskSpec,
      workerCount = 1,
      workerType = 'feature-implementer',
      strategy = this.config.aggregationStrategy,
      taskDistribution = 'split', // split, replicate, map-reduce
      resources = {}
    } = options;

    const coordinationId = this._generateCoordinationId();

    const coordination = {
      id: coordinationId,
      taskSpec,
      workerCount,
      workerType,
      strategy,
      taskDistribution,
      status: 'initializing',
      workers: [],
      tasks: [],
      results: [],
      startedAt: new Date(),
      completedAt: null
    };

    this.coordinations.set(coordinationId, coordination);
    this.emit('coordination_started', { coordinationId, coordination });

    try {
      // 1. Spawn workers
      coordination.status = 'spawning_workers';
      const workerIds = await this.spawner.spawnWorkers({
        count: workerCount,
        workerType,
        taskSpec,
        resources
      });

      coordination.workers = workerIds;
      this.emit('workers_spawned', { coordinationId, workerIds });

      // 2. Distribute tasks
      coordination.status = 'distributing_tasks';
      const tasks = await this._distributeTasks(
        coordinationId,
        taskSpec,
        workerIds,
        taskDistribution
      );

      coordination.tasks = tasks;
      this.emit('tasks_distributed', { coordinationId, taskCount: tasks.length });

      // 3. Execute tasks
      coordination.status = 'executing';
      const taskResults = await this._executeTasks(coordinationId, tasks);

      coordination.results = taskResults;
      this.emit('tasks_executed', { coordinationId, resultCount: taskResults.length });

      // 4. Aggregate results
      coordination.status = 'aggregating';
      const aggregatedResult = await this._aggregateResults(
        coordinationId,
        taskResults,
        strategy
      );

      coordination.status = 'completed';
      coordination.completedAt = new Date();
      coordination.finalResult = aggregatedResult;

      this.emit('coordination_completed', {
        coordinationId,
        result: aggregatedResult,
        duration: coordination.completedAt - coordination.startedAt
      });

      return {
        coordinationId,
        result: aggregatedResult,
        workers: workerIds,
        taskCount: tasks.length,
        duration: coordination.completedAt - coordination.startedAt
      };

    } catch (error) {
      coordination.status = 'failed';
      coordination.error = error.message;
      coordination.completedAt = new Date();

      this.emit('coordination_failed', {
        coordinationId,
        error: error.message
      });

      throw error;
    }
  }

  /**
   * Distribute tasks among workers based on distribution strategy
   * @private
   */
  async _distributeTasks(coordinationId, taskSpec, workerIds, distribution) {
    const tasks = [];

    switch (distribution) {
      case 'split':
        // Split task into subtasks for parallel execution
        tasks.push(...this._splitTask(taskSpec, workerIds));
        break;

      case 'replicate':
        // Replicate same task to all workers (for consensus)
        for (const workerId of workerIds) {
          tasks.push({
            taskId: this._generateTaskId(),
            workerId,
            taskSpec,
            type: 'replicated'
          });
        }
        break;

      case 'map-reduce':
        // Map-reduce pattern
        tasks.push(...this._mapReduceTasks(taskSpec, workerIds));
        break;

      default:
        throw new Error(`Unknown distribution strategy: ${distribution}`);
    }

    // Assign tasks to workers
    for (const task of tasks) {
      this.taskAssignments.set(task.taskId, task.workerId);
    }

    return tasks;
  }

  /**
   * Split a task into subtasks
   * @private
   */
  _splitTask(taskSpec, workerIds) {
    const tasks = [];

    // Example: If taskSpec has an array of items, split them
    if (taskSpec.items && Array.isArray(taskSpec.items)) {
      const itemsPerWorker = Math.ceil(taskSpec.items.length / workerIds.length);

      workerIds.forEach((workerId, index) => {
        const start = index * itemsPerWorker;
        const end = Math.min(start + itemsPerWorker, taskSpec.items.length);
        const items = taskSpec.items.slice(start, end);

        if (items.length > 0) {
          tasks.push({
            taskId: this._generateTaskId(),
            workerId,
            taskSpec: {
              ...taskSpec,
              items,
              partition: { index, total: workerIds.length }
            },
            type: 'split'
          });
        }
      });
    } else {
      // Default: assign one task per worker with partitioning info
      workerIds.forEach((workerId, index) => {
        tasks.push({
          taskId: this._generateTaskId(),
          workerId,
          taskSpec: {
            ...taskSpec,
            partition: { index, total: workerIds.length }
          },
          type: 'split'
        });
      });
    }

    return tasks;
  }

  /**
   * Create map-reduce tasks
   * @private
   */
  _mapReduceTasks(taskSpec, workerIds) {
    const tasks = [];

    // Map phase: split work
    const mapTasks = this._splitTask(taskSpec, workerIds);
    tasks.push(...mapTasks.map(t => ({ ...t, phase: 'map' })));

    // Reduce phase will be handled after map completes
    // For now, we'll add a placeholder
    tasks.push({
      taskId: this._generateTaskId(),
      workerId: workerIds[0], // Use first worker for reduce
      taskSpec: {
        ...taskSpec,
        phase: 'reduce',
        dependsOn: mapTasks.map(t => t.taskId)
      },
      type: 'map-reduce',
      phase: 'reduce'
    });

    return tasks;
  }

  /**
   * Execute tasks and collect results
   * @private
   */
  async _executeTasks(coordinationId, tasks) {
    const results = [];
    const executePromises = [];

    for (const task of tasks) {
      // Skip reduce tasks initially (they depend on map tasks)
      if (task.phase === 'reduce') {
        continue;
      }

      executePromises.push(
        this._executeTask(task).then(result => {
          results.push(result);
          this.emit('task_completed', {
            coordinationId,
            taskId: task.taskId,
            workerId: task.workerId
          });
          return result;
        }).catch(error => {
          this.emit('task_failed', {
            coordinationId,
            taskId: task.taskId,
            error: error.message
          });
          return {
            taskId: task.taskId,
            status: 'failed',
            error: error.message
          };
        })
      );
    }

    // Wait for all tasks to complete
    const mapResults = await Promise.allSettled(executePromises);

    // Handle reduce tasks if present
    const reduceTasks = tasks.filter(t => t.phase === 'reduce');
    for (const reduceTask of reduceTasks) {
      const reduceResult = await this._executeTask({
        ...reduceTask,
        mapResults: results
      });
      results.push(reduceResult);
    }

    return results;
  }

  /**
   * Execute a single task
   * @private
   */
  async _executeTask(task) {
    const { taskId, workerId, taskSpec } = task;

    // Store task assignment
    this.taskAssignments.set(taskId, workerId);

    // In real implementation, this would communicate with the worker
    // For now, simulate task execution
    return new Promise((resolve) => {
      setTimeout(() => {
        const result = {
          taskId,
          workerId,
          status: 'completed',
          output: {
            message: `Task ${taskId} completed by worker ${workerId}`,
            taskSpec,
            simulatedResult: true
          },
          completedAt: new Date().toISOString()
        };

        this.results.set(taskId, result);
        resolve(result);
      }, Math.random() * 1000 + 500); // Simulate 0.5-1.5s execution
    });
  }

  /**
   * Aggregate results using specified strategy
   * @private
   */
  async _aggregateResults(coordinationId, results, strategy) {
    this.emit('aggregation_started', { coordinationId, strategy, resultCount: results.length });

    let aggregated;

    switch (strategy) {
      case 'consensus':
        aggregated = this._consensusAggregation(results);
        break;

      case 'voting':
        aggregated = this._votingAggregation(results);
        break;

      case 'merge':
        aggregated = this._mergeAggregation(results);
        break;

      case 'reduce':
        aggregated = this._reduceAggregation(results);
        break;

      case 'first':
        aggregated = results[0]?.output || null;
        break;

      case 'all':
        aggregated = results.map(r => r.output);
        break;

      default:
        aggregated = this._mergeAggregation(results);
    }

    this.emit('aggregation_completed', {
      coordinationId,
      strategy,
      resultCount: results.length
    });

    return aggregated;
  }

  /**
   * Consensus aggregation - choose most common result
   * @private
   */
  _consensusAggregation(results) {
    const outputs = results.map(r => JSON.stringify(r.output));
    const frequency = {};

    for (const output of outputs) {
      frequency[output] = (frequency[output] || 0) + 1;
    }

    const mostCommon = Object.entries(frequency)
      .sort((a, b) => b[1] - a[1])[0];

    return mostCommon ? JSON.parse(mostCommon[0]) : null;
  }

  /**
   * Voting aggregation - majority wins
   * @private
   */
  _votingAggregation(results) {
    // Similar to consensus but with explicit voting
    return this._consensusAggregation(results);
  }

  /**
   * Merge aggregation - combine all results
   * @private
   */
  _mergeAggregation(results) {
    const merged = {
      results: results.map(r => r.output),
      count: results.length,
      successful: results.filter(r => r.status === 'completed').length,
      failed: results.filter(r => r.status === 'failed').length
    };

    return merged;
  }

  /**
   * Reduce aggregation - reduce results to single value
   * @private
   */
  _reduceAggregation(results) {
    // Example reduce: combine arrays, sum numbers, etc.
    const outputs = results.map(r => r.output);

    if (outputs.length === 0) return null;
    if (outputs.length === 1) return outputs[0];

    // If all outputs are arrays, concatenate them
    if (outputs.every(o => Array.isArray(o))) {
      return outputs.flat();
    }

    // If all outputs are objects, deep merge them
    if (outputs.every(o => typeof o === 'object' && !Array.isArray(o))) {
      return Object.assign({}, ...outputs);
    }

    // Otherwise, return as array
    return outputs;
  }

  /**
   * Get coordination status
   */
  getCoordinationStatus(coordinationId) {
    return this.coordinations.get(coordinationId);
  }

  /**
   * Get all active coordinations
   */
  getActiveCoordinations() {
    return Array.from(this.coordinations.values())
      .filter(c => c.status !== 'completed' && c.status !== 'failed');
  }

  /**
   * Cancel a coordination
   */
  async cancelCoordination(coordinationId, reason = 'manual') {
    const coordination = this.coordinations.get(coordinationId);
    if (!coordination) {
      throw new Error(`Coordination ${coordinationId} not found`);
    }

    coordination.status = 'cancelled';
    coordination.cancellationReason = reason;
    coordination.completedAt = new Date();

    // Terminate associated workers
    for (const workerId of coordination.workers) {
      try {
        await this.spawner.terminateWorker(workerId, 'coordination_cancelled');
      } catch (error) {
        this.emit('worker_termination_error', {
          coordinationId,
          workerId,
          error: error.message
        });
      }
    }

    this.emit('coordination_cancelled', { coordinationId, reason });

    return true;
  }

  /**
   * Generate unique coordination ID
   * @private
   */
  _generateCoordinationId() {
    return `coord-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
  }

  /**
   * Generate unique task ID
   * @private
   */
  _generateTaskId() {
    return `task-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
  }

  /**
   * Get metrics
   */
  getMetrics() {
    return {
      totalCoordinations: this.coordinations.size,
      activeCoordinations: this.getActiveCoordinations().length,
      totalTasks: this.taskAssignments.size,
      cachedResults: this.results.size
    };
  }

  /**
   * Shutdown coordinator
   */
  async shutdown() {
    const activeCoordinations = this.getActiveCoordinations();

    for (const coordination of activeCoordinations) {
      await this.cancelCoordination(coordination.id, 'shutdown');
    }

    this.coordinations.clear();
    this.taskAssignments.clear();
    this.results.clear();

    this.emit('shutdown_complete');
  }
}

module.exports = { WorkerCoordinator };
