/**
 * Priority Task Queue with Retry Logic
 * Heap-based priority queue for efficient task management
 */

const { EventEmitter } = require('events');

class TaskQueue extends EventEmitter {
  constructor(config = {}) {
    super();
    this.heap = []; // Min-heap based on priority (lower number = higher priority)
    this.taskMap = new Map(); // taskId -> task lookup
    this.deadLetterQueue = [];
    this.config = {
      maxRetries: config.maxRetries || 3,
      retryBackoffMs: config.retryBackoffMs || 1000,
      maxBackoffMs: config.maxBackoffMs || 30000,
      taskTimeoutMs: config.taskTimeoutMs || 300000, // 5 minutes
      ...config
    };
    this.taskCounter = 0;
  }

  /**
   * Enqueue a task with priority
   * @param {Object} task - Task object
   * @param {number} priority - Priority (0 = highest, lower is better)
   * @returns {string} taskId
   */
  enqueue(task, priority = 10) {
    const taskId = `task-${Date.now()}-${++this.taskCounter}`;
    const queuedTask = {
      id: taskId,
      task,
      priority,
      retries: 0,
      maxRetries: this.config.maxRetries,
      enqueuedAt: Date.now(),
      status: 'queued',
      timeoutMs: task.timeout || this.config.taskTimeoutMs,
      metadata: {
        attempts: [],
        ...task.metadata
      }
    };

    this.taskMap.set(taskId, queuedTask);
    this._heapPush(queuedTask);

    this.emit('task-enqueued', {
      taskId,
      priority,
      queueDepth: this.heap.length
    });

    return taskId;
  }

  /**
   * Dequeue highest priority task
   * @returns {Object|null} task or null if queue is empty
   */
  dequeue() {
    if (this.heap.length === 0) {
      return null;
    }

    const task = this._heapPop();
    task.status = 'dequeued';
    task.dequeuedAt = Date.now();

    this.emit('task-dequeued', {
      taskId: task.id,
      priority: task.priority,
      waitTimeMs: task.dequeuedAt - task.enqueuedAt,
      queueDepth: this.heap.length
    });

    return task;
  }

  /**
   * Peek at highest priority task without removing it
   * @returns {Object|null} task or null if queue is empty
   */
  peek() {
    return this.heap.length > 0 ? this.heap[0] : null;
  }

  /**
   * Get task by ID
   * @param {string} taskId
   * @returns {Object|null}
   */
  getTaskById(taskId) {
    return this.taskMap.get(taskId) || null;
  }

  /**
   * Mark task as completed
   * @param {string} taskId
   * @param {Object} result
   */
  completeTask(taskId, result) {
    const task = this.taskMap.get(taskId);
    if (!task) {
      this.emit('warning', {
        message: `Task ${taskId} not found in queue`,
        taskId
      });
      return;
    }

    task.status = 'completed';
    task.completedAt = Date.now();
    task.result = result;
    task.durationMs = task.completedAt - task.dequeuedAt;

    this.emit('task-completed', {
      taskId,
      durationMs: task.durationMs,
      retries: task.retries
    });

    // Remove from map after a delay (for metrics collection)
    setTimeout(() => {
      this.taskMap.delete(taskId);
    }, 60000); // Keep for 1 minute
  }

  /**
   * Mark task as failed and optionally retry
   * @param {string} taskId
   * @param {Error} error
   * @returns {boolean} true if task was retried, false if moved to DLQ
   */
  failTask(taskId, error) {
    const task = this.taskMap.get(taskId);
    if (!task) {
      this.emit('warning', {
        message: `Task ${taskId} not found in queue`,
        taskId
      });
      return false;
    }

    task.metadata.attempts.push({
      timestamp: Date.now(),
      error: error.message,
      stack: error.stack
    });

    task.retries++;

    if (task.retries <= task.maxRetries) {
      // Retry with exponential backoff
      const backoffMs = Math.min(
        this.config.retryBackoffMs * Math.pow(2, task.retries - 1),
        this.config.maxBackoffMs
      );

      task.status = 'retry-pending';
      task.nextRetryAt = Date.now() + backoffMs;

      this.emit('task-retry-scheduled', {
        taskId,
        retries: task.retries,
        maxRetries: task.maxRetries,
        backoffMs,
        error: error.message
      });

      // Re-enqueue after backoff
      setTimeout(() => {
        if (this.taskMap.has(taskId)) {
          task.status = 'queued';
          task.enqueuedAt = Date.now();
          this._heapPush(task);

          this.emit('task-retried', {
            taskId,
            retries: task.retries,
            queueDepth: this.heap.length
          });
        }
      }, backoffMs);

      return true;
    } else {
      // Move to dead letter queue
      task.status = 'failed';
      task.failedAt = Date.now();
      task.finalError = error;

      this.deadLetterQueue.push(task);
      this.taskMap.delete(taskId);

      this.emit('task-failed', {
        taskId,
        retries: task.retries,
        error: error.message,
        dlqSize: this.deadLetterQueue.length
      });

      return false;
    }
  }

  /**
   * Get current queue depth
   * @returns {number}
   */
  getQueueDepth() {
    return this.heap.length;
  }

  /**
   * Get dead letter queue
   * @returns {Array}
   */
  getDeadLetterQueue() {
    return [...this.deadLetterQueue];
  }

  /**
   * Clear dead letter queue
   */
  clearDeadLetterQueue() {
    const count = this.deadLetterQueue.length;
    this.deadLetterQueue = [];
    this.emit('dlq-cleared', { count });
    return count;
  }

  /**
   * Get queue statistics
   * @returns {Object}
   */
  getStats() {
    const tasks = Array.from(this.taskMap.values());
    const now = Date.now();

    const stats = {
      queueDepth: this.heap.length,
      totalTasks: this.taskMap.size,
      dlqSize: this.deadLetterQueue.length,
      byStatus: {},
      byPriority: {},
      avgWaitTimeMs: 0,
      avgDurationMs: 0,
      oldestTaskAge: 0
    };

    // Count by status
    tasks.forEach(task => {
      stats.byStatus[task.status] = (stats.byStatus[task.status] || 0) + 1;
      stats.byPriority[task.priority] = (stats.byPriority[task.priority] || 0) + 1;
    });

    // Calculate averages
    const dequeuedTasks = tasks.filter(t => t.dequeuedAt);
    if (dequeuedTasks.length > 0) {
      const totalWaitTime = dequeuedTasks.reduce((sum, t) => sum + (t.dequeuedAt - t.enqueuedAt), 0);
      stats.avgWaitTimeMs = Math.round(totalWaitTime / dequeuedTasks.length);
    }

    const completedTasks = tasks.filter(t => t.completedAt);
    if (completedTasks.length > 0) {
      const totalDuration = completedTasks.reduce((sum, t) => sum + (t.completedAt - t.dequeuedAt), 0);
      stats.avgDurationMs = Math.round(totalDuration / completedTasks.length);
    }

    // Find oldest task
    if (tasks.length > 0) {
      const oldestTask = tasks.reduce((oldest, task) =>
        task.enqueuedAt < oldest.enqueuedAt ? task : oldest
      );
      stats.oldestTaskAge = now - oldestTask.enqueuedAt;
    }

    return stats;
  }

  /**
   * Check for timed-out tasks
   * @returns {Array} Array of timed-out task IDs
   */
  checkTimeouts() {
    const now = Date.now();
    const timedOut = [];

    for (const [taskId, task] of this.taskMap.entries()) {
      if (task.status === 'dequeued' && task.dequeuedAt) {
        const elapsed = now - task.dequeuedAt;
        if (elapsed > task.timeoutMs) {
          timedOut.push(taskId);
          this.emit('task-timeout', {
            taskId,
            elapsedMs: elapsed,
            timeoutMs: task.timeoutMs
          });
        }
      }
    }

    return timedOut;
  }

  /**
   * Clear all tasks
   */
  clear() {
    const count = this.heap.length + this.taskMap.size;
    this.heap = [];
    this.taskMap.clear();
    this.emit('queue-cleared', { count });
  }

  // Heap operations

  _heapPush(task) {
    this.heap.push(task);
    this._heapifyUp(this.heap.length - 1);
  }

  _heapPop() {
    if (this.heap.length === 0) return null;
    if (this.heap.length === 1) return this.heap.pop();

    const top = this.heap[0];
    this.heap[0] = this.heap.pop();
    this._heapifyDown(0);
    return top;
  }

  _heapifyUp(index) {
    while (index > 0) {
      const parentIndex = Math.floor((index - 1) / 2);
      if (this._compare(this.heap[index], this.heap[parentIndex]) >= 0) {
        break;
      }
      this._swap(index, parentIndex);
      index = parentIndex;
    }
  }

  _heapifyDown(index) {
    while (true) {
      const leftChild = 2 * index + 1;
      const rightChild = 2 * index + 2;
      let smallest = index;

      if (leftChild < this.heap.length &&
          this._compare(this.heap[leftChild], this.heap[smallest]) < 0) {
        smallest = leftChild;
      }

      if (rightChild < this.heap.length &&
          this._compare(this.heap[rightChild], this.heap[smallest]) < 0) {
        smallest = rightChild;
      }

      if (smallest === index) break;

      this._swap(index, smallest);
      index = smallest;
    }
  }

  _compare(a, b) {
    // Lower priority number = higher priority
    if (a.priority !== b.priority) {
      return a.priority - b.priority;
    }
    // If same priority, FIFO (earlier enqueued first)
    return a.enqueuedAt - b.enqueuedAt;
  }

  _swap(i, j) {
    [this.heap[i], this.heap[j]] = [this.heap[j], this.heap[i]];
  }
}

module.exports = TaskQueue;
