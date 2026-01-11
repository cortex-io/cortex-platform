/**
 * High-performance message bus for inter-process communication
 * Supports priority queuing, broadcast, and point-to-point messaging
 */

const EventEmitter = require('events');

/**
 * Message priority levels
 */
const Priority = {
  CRITICAL: 0,
  HIGH: 1,
  NORMAL: 2,
  LOW: 3
};

/**
 * Delivery guarantee strategies
 */
const DeliveryGuarantee = {
  AT_MOST_ONCE: 'at-most-once',    // Fire and forget
  AT_LEAST_ONCE: 'at-least-once',  // Retry until ack
  EXACTLY_ONCE: 'exactly-once'      // Deduplicate + ack
};

/**
 * Message structure
 */
class Message {
  constructor(data) {
    this.id = data.id || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    this.type = data.type;
    this.payload = data.payload;
    this.priority = data.priority || Priority.NORMAL;
    this.sender = data.sender;
    this.recipient = data.recipient; // null for broadcast
    this.timestamp = data.timestamp || Date.now();
    this.deliveryGuarantee = data.deliveryGuarantee || DeliveryGuarantee.AT_MOST_ONCE;
    this.ttl = data.ttl || 60000; // 60 seconds default
    this.retries = data.retries || 0;
    this.maxRetries = data.maxRetries || 3;
  }

  isExpired() {
    return Date.now() - this.timestamp > this.ttl;
  }

  canRetry() {
    return this.retries < this.maxRetries;
  }
}

/**
 * Priority queue for message handling
 */
class PriorityQueue {
  constructor() {
    // Separate queues for each priority level
    this.queues = {
      [Priority.CRITICAL]: [],
      [Priority.HIGH]: [],
      [Priority.NORMAL]: [],
      [Priority.LOW]: []
    };
    this.size = 0;
  }

  enqueue(message) {
    this.queues[message.priority].push(message);
    this.size++;
  }

  dequeue() {
    // Process in priority order
    for (const priority of [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]) {
      const queue = this.queues[priority];
      if (queue.length > 0) {
        this.size--;
        return queue.shift();
      }
    }
    return null;
  }

  peek() {
    for (const priority of [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]) {
      const queue = this.queues[priority];
      if (queue.length > 0) {
        return queue[0];
      }
    }
    return null;
  }

  isEmpty() {
    return this.size === 0;
  }

  clear() {
    for (const priority in this.queues) {
      this.queues[priority] = [];
    }
    this.size = 0;
  }

  getStats() {
    return {
      total: this.size,
      critical: this.queues[Priority.CRITICAL].length,
      high: this.queues[Priority.HIGH].length,
      normal: this.queues[Priority.NORMAL].length,
      low: this.queues[Priority.LOW].length
    };
  }
}

/**
 * Message bus for inter-process communication
 */
class MessageBus extends EventEmitter {
  /**
   * @param {Object} config Configuration options
   * @param {number} config.processingInterval - Message processing interval (ms)
   * @param {number} config.maxQueueSize - Maximum queue size
   * @param {boolean} config.enableMetrics - Enable metrics collection
   */
  constructor(config = {}) {
    super();

    this.config = {
      processingInterval: config.processingInterval || 10, // 10ms for high throughput
      maxQueueSize: config.maxQueueSize || 100000,
      enableMetrics: config.enableMetrics !== false,
      ...config
    };

    // Message queue
    this.queue = new PriorityQueue();

    // Active subscribers
    this.subscribers = new Map(); // topic -> Set of callbacks
    this.workerSubscribers = new Map(); // workerId -> Set of topics

    // Pending acknowledgments for at-least-once delivery
    this.pendingAcks = new Map(); // messageId -> { message, timeout }

    // Message deduplication for exactly-once delivery
    this.processedMessages = new Set(); // messageId
    this.deduplicationWindow = 60000; // 1 minute

    // Metrics
    this.metrics = {
      messagesSent: 0,
      messagesReceived: 0,
      messagesDelivered: 0,
      messagesDropped: 0,
      messagesRetried: 0,
      averageLatency: 0,
      queueDepth: 0,
      subscriberCount: 0
    };

    // Latency tracking
    this.latencies = [];
    this.maxLatencySamples = 1000;

    // Processing
    this.processing = false;
    this.processingTimer = null;
  }

  /**
   * Start the message bus
   */
  start() {
    if (this.processing) {
      return;
    }

    this.processing = true;
    this._startProcessing();

    // Cleanup expired messages periodically
    this.cleanupTimer = setInterval(() => {
      this._cleanupExpiredMessages();
    }, 5000);

    this.emit('started');
  }

  /**
   * Stop the message bus
   */
  stop() {
    this.processing = false;

    if (this.processingTimer) {
      clearInterval(this.processingTimer);
    }

    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }

    this.emit('stopped');
  }

  /**
   * Start message processing loop
   */
  _startProcessing() {
    this.processingTimer = setInterval(() => {
      this._processMessages();
    }, this.config.processingInterval);
  }

  /**
   * Process messages from queue
   */
  _processMessages() {
    const startTime = Date.now();
    let processed = 0;
    const maxBatchSize = 100; // Process up to 100 messages per cycle

    while (!this.queue.isEmpty() && processed < maxBatchSize) {
      const message = this.queue.dequeue();

      if (message.isExpired()) {
        this.metrics.messagesDropped++;
        this.emit('message-expired', { messageId: message.id });
        processed++;
        continue;
      }

      this._deliverMessage(message);
      processed++;
    }

    if (processed > 0) {
      const latency = Date.now() - startTime;
      this._recordLatency(latency / processed); // Average per message
    }

    this.metrics.queueDepth = this.queue.size;
  }

  /**
   * Deliver a message to subscribers
   */
  _deliverMessage(message) {
    const deliveryStart = Date.now();

    try {
      // Check for deduplication (exactly-once)
      if (message.deliveryGuarantee === DeliveryGuarantee.EXACTLY_ONCE) {
        if (this.processedMessages.has(message.id)) {
          // Already processed, acknowledge and skip
          this._acknowledgeMessage(message.id);
          return;
        }
        this.processedMessages.add(message.id);
      }

      // Determine recipients
      const recipients = this._getRecipients(message);

      if (recipients.length === 0) {
        this.metrics.messagesDropped++;
        this.emit('no-subscribers', { message });
        return;
      }

      // Deliver to all recipients
      let delivered = false;
      for (const callback of recipients) {
        try {
          callback(message);
          delivered = true;
          this.metrics.messagesDelivered++;
        } catch (error) {
          this.emit('delivery-error', { message, error: error.message });
        }
      }

      // Handle acknowledgment for at-least-once delivery
      if (message.deliveryGuarantee === DeliveryGuarantee.AT_LEAST_ONCE) {
        this._setupAcknowledgment(message);
      } else if (delivered) {
        // Fire and forget - consider delivered
        this.emit('message-delivered', {
          messageId: message.id,
          latency: Date.now() - deliveryStart
        });
      }

    } catch (error) {
      this.emit('error', { operation: 'deliver-message', error: error.message });
      this._handleDeliveryFailure(message);
    }
  }

  /**
   * Get recipients for a message
   */
  _getRecipients(message) {
    const recipients = new Set();

    if (message.recipient) {
      // Point-to-point
      const topics = this.workerSubscribers.get(message.recipient);
      if (topics && topics.has(message.type)) {
        const callbacks = this.subscribers.get(message.type);
        if (callbacks) {
          callbacks.forEach(cb => recipients.add(cb));
        }
      }
    } else {
      // Broadcast
      const callbacks = this.subscribers.get(message.type);
      if (callbacks) {
        callbacks.forEach(cb => recipients.add(cb));
      }
    }

    return Array.from(recipients);
  }

  /**
   * Setup acknowledgment timeout for at-least-once delivery
   */
  _setupAcknowledgment(message) {
    const timeout = setTimeout(() => {
      // Retry if not acknowledged
      if (this.pendingAcks.has(message.id)) {
        this._handleDeliveryFailure(message);
      }
    }, 5000); // 5 second timeout

    this.pendingAcks.set(message.id, { message, timeout });
  }

  /**
   * Acknowledge message delivery
   */
  _acknowledgeMessage(messageId) {
    const pending = this.pendingAcks.get(messageId);
    if (pending) {
      clearTimeout(pending.timeout);
      this.pendingAcks.delete(messageId);
      this.emit('message-acknowledged', { messageId });
    }
  }

  /**
   * Handle delivery failure
   */
  _handleDeliveryFailure(message) {
    message.retries++;

    if (message.canRetry()) {
      this.metrics.messagesRetried++;
      this.queue.enqueue(message);
      this.emit('message-retry', { messageId: message.id, retries: message.retries });
    } else {
      this.metrics.messagesDropped++;
      this.emit('message-failed', { messageId: message.id, retries: message.retries });
    }
  }

  /**
   * Cleanup expired messages and deduplication cache
   */
  _cleanupExpiredMessages() {
    // Cleanup deduplication cache
    if (this.processedMessages.size > 10000) {
      this.processedMessages.clear();
    }

    // Cleanup expired pending acks
    const now = Date.now();
    for (const [messageId, pending] of this.pendingAcks.entries()) {
      if (now - pending.message.timestamp > pending.message.ttl) {
        clearTimeout(pending.timeout);
        this.pendingAcks.delete(messageId);
      }
    }
  }

  /**
   * Publish a message
   */
  publish(type, payload, options = {}) {
    if (this.queue.size >= this.config.maxQueueSize) {
      this.emit('queue-full', { queueSize: this.queue.size });
      return null;
    }

    const message = new Message({
      type,
      payload,
      priority: options.priority || Priority.NORMAL,
      sender: options.sender,
      recipient: options.recipient,
      deliveryGuarantee: options.deliveryGuarantee || DeliveryGuarantee.AT_MOST_ONCE,
      ttl: options.ttl,
      maxRetries: options.maxRetries
    });

    this.queue.enqueue(message);
    this.metrics.messagesSent++;

    this.emit('message-published', { messageId: message.id, type, priority: message.priority });

    return message.id;
  }

  /**
   * Subscribe to messages
   */
  subscribe(topic, callback, workerId = null) {
    if (!this.subscribers.has(topic)) {
      this.subscribers.set(topic, new Set());
    }

    this.subscribers.get(topic).add(callback);

    if (workerId) {
      if (!this.workerSubscribers.has(workerId)) {
        this.workerSubscribers.set(workerId, new Set());
      }
      this.workerSubscribers.get(workerId).add(topic);
    }

    this.metrics.subscriberCount = this._countSubscribers();

    this.emit('subscribed', { topic, workerId });

    // Return unsubscribe function
    return () => this.unsubscribe(topic, callback, workerId);
  }

  /**
   * Unsubscribe from messages
   */
  unsubscribe(topic, callback, workerId = null) {
    const callbacks = this.subscribers.get(topic);
    if (callbacks) {
      callbacks.delete(callback);
      if (callbacks.size === 0) {
        this.subscribers.delete(topic);
      }
    }

    if (workerId) {
      const topics = this.workerSubscribers.get(workerId);
      if (topics) {
        topics.delete(topic);
        if (topics.size === 0) {
          this.workerSubscribers.delete(workerId);
        }
      }
    }

    this.metrics.subscriberCount = this._countSubscribers();

    this.emit('unsubscribed', { topic, workerId });
  }

  /**
   * Acknowledge message (for at-least-once delivery)
   */
  acknowledge(messageId) {
    this._acknowledgeMessage(messageId);
  }

  /**
   * Count total subscribers
   */
  _countSubscribers() {
    let count = 0;
    for (const callbacks of this.subscribers.values()) {
      count += callbacks.size;
    }
    return count;
  }

  /**
   * Record latency for metrics
   */
  _recordLatency(latency) {
    this.latencies.push(latency);

    if (this.latencies.length > this.maxLatencySamples) {
      this.latencies.shift();
    }

    // Calculate average
    const sum = this.latencies.reduce((a, b) => a + b, 0);
    this.metrics.averageLatency = sum / this.latencies.length;
  }

  /**
   * Get queue statistics
   */
  getQueueStats() {
    return this.queue.getStats();
  }

  /**
   * Get metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      queue: this.queue.getStats(),
      pendingAcks: this.pendingAcks.size,
      topics: this.subscribers.size,
      workers: this.workerSubscribers.size
    };
  }

  /**
   * Clear all messages and subscriptions
   */
  clear() {
    this.queue.clear();
    this.subscribers.clear();
    this.workerSubscribers.clear();
    this.pendingAcks.clear();
    this.processedMessages.clear();
    this.emit('cleared');
  }
}

module.exports = { MessageBus, Priority, DeliveryGuarantee };
