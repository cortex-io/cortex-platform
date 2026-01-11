/**
 * Unix FIFO Communication Layer
 * Provides reliable message passing between pool manager and worker processes
 */

const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

class FIFOChannel extends EventEmitter {
  constructor(workerId, fifoDir) {
    super();
    this.workerId = workerId;
    this.fifoDir = fifoDir;
    this.inPipe = path.join(fifoDir, `worker-${workerId}-in.fifo`);
    this.outPipe = path.join(fifoDir, `worker-${workerId}-out.fifo`);
    this.writeStream = null;
    this.readStream = null;
    this.readBuffer = Buffer.alloc(0);
    this.connected = false;
    this.reconnecting = false;
  }

  /**
   * Create FIFO pipes for this worker
   */
  async createChannel() {
    try {
      // Ensure directory exists
      await fs.mkdir(this.fifoDir, { recursive: true });

      // Remove old pipes if they exist
      await this._cleanupPipes();

      // Create new FIFO pipes
      const { execSync } = require('child_process');
      execSync(`mkfifo "${this.inPipe}"`);
      execSync(`mkfifo "${this.outPipe}"`);

      this.emit('channel-created', { workerId: this.workerId });
      return true;
    } catch (error) {
      this.emit('error', {
        workerId: this.workerId,
        operation: 'createChannel',
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Connect to FIFO pipes (non-blocking)
   */
  async connect() {
    try {
      // Open write stream to worker's input pipe
      // O_WRONLY | O_NONBLOCK to avoid blocking
      this.writeStream = fsSync.createWriteStream(this.inPipe, {
        flags: 'w',
        encoding: 'utf8'
      });

      // Open read stream from worker's output pipe
      // O_RDONLY | O_NONBLOCK to avoid blocking
      this.readStream = fsSync.createReadStream(this.outPipe, {
        flags: 'r',
        encoding: 'utf8',
        highWaterMark: 64 * 1024 // 64KB buffer
      });

      this._setupStreamHandlers();
      this.connected = true;
      this.emit('connected', { workerId: this.workerId });

      return true;
    } catch (error) {
      this.emit('error', {
        workerId: this.workerId,
        operation: 'connect',
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Send message to worker (length-prefixed framing)
   */
  async sendToWorker(message) {
    if (!this.connected || !this.writeStream) {
      throw new Error(`Worker ${this.workerId} not connected`);
    }

    try {
      const msgStr = JSON.stringify(message);
      const msgBuffer = Buffer.from(msgStr, 'utf8');
      const lengthPrefix = Buffer.alloc(4);
      lengthPrefix.writeUInt32BE(msgBuffer.length, 0);

      // Write length prefix followed by message
      const written = this.writeStream.write(Buffer.concat([lengthPrefix, msgBuffer]));

      if (!written) {
        // Wait for drain event
        await new Promise((resolve) => this.writeStream.once('drain', resolve));
      }

      this.emit('message-sent', {
        workerId: this.workerId,
        messageType: message.type,
        size: msgBuffer.length
      });

      return true;
    } catch (error) {
      this.emit('error', {
        workerId: this.workerId,
        operation: 'sendToWorker',
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Async generator to receive messages from worker
   */
  async *receiveFromWorker() {
    if (!this.connected || !this.readStream) {
      throw new Error(`Worker ${this.workerId} not connected`);
    }

    const messageQueue = [];
    let resolveNext = null;

    // Set up data handler
    const dataHandler = (chunk) => {
      this.readBuffer = Buffer.concat([this.readBuffer, Buffer.from(chunk, 'utf8')]);
      this._processBuffer(messageQueue, resolveNext);
    };

    this.readStream.on('data', dataHandler);

    try {
      while (this.connected) {
        if (messageQueue.length > 0) {
          yield messageQueue.shift();
        } else {
          // Wait for next message
          await new Promise((resolve) => {
            resolveNext = resolve;
          });
          resolveNext = null;
        }
      }
    } finally {
      this.readStream.off('data', dataHandler);
    }
  }

  /**
   * Process read buffer and extract complete messages
   */
  _processBuffer(messageQueue, resolveNext) {
    while (this.readBuffer.length >= 4) {
      // Read length prefix
      const msgLength = this.readBuffer.readUInt32BE(0);

      // Check if we have the complete message
      if (this.readBuffer.length >= 4 + msgLength) {
        // Extract message
        const msgBuffer = this.readBuffer.slice(4, 4 + msgLength);
        const msgStr = msgBuffer.toString('utf8');

        try {
          const message = JSON.parse(msgStr);
          messageQueue.push(message);

          this.emit('message-received', {
            workerId: this.workerId,
            messageType: message.type,
            size: msgLength
          });

          // Notify waiting receiver
          if (resolveNext) {
            resolveNext();
          }
        } catch (error) {
          this.emit('error', {
            workerId: this.workerId,
            operation: 'parseMessage',
            error: error.message
          });
        }

        // Remove processed message from buffer
        this.readBuffer = this.readBuffer.slice(4 + msgLength);
      } else {
        // Wait for more data
        break;
      }
    }
  }

  /**
   * Setup stream event handlers
   */
  _setupStreamHandlers() {
    if (this.writeStream) {
      this.writeStream.on('error', (error) => {
        this.emit('error', {
          workerId: this.workerId,
          stream: 'write',
          error: error.message
        });
        this._handleDisconnection();
      });

      this.writeStream.on('close', () => {
        this.emit('write-stream-closed', { workerId: this.workerId });
      });
    }

    if (this.readStream) {
      this.readStream.on('error', (error) => {
        this.emit('error', {
          workerId: this.workerId,
          stream: 'read',
          error: error.message
        });
        this._handleDisconnection();
      });

      this.readStream.on('end', () => {
        this.emit('read-stream-ended', { workerId: this.workerId });
        this._handleDisconnection();
      });

      this.readStream.on('close', () => {
        this.emit('read-stream-closed', { workerId: this.workerId });
      });
    }
  }

  /**
   * Handle disconnection and attempt reconnection
   */
  async _handleDisconnection() {
    if (this.reconnecting) return;

    this.connected = false;
    this.reconnecting = true;
    this.emit('disconnected', { workerId: this.workerId });

    // Clean up streams
    if (this.writeStream) {
      this.writeStream.destroy();
      this.writeStream = null;
    }
    if (this.readStream) {
      this.readStream.destroy();
      this.readStream = null;
    }

    this.reconnecting = false;
  }

  /**
   * Close the channel and cleanup
   */
  async close() {
    this.connected = false;

    if (this.writeStream) {
      this.writeStream.end();
      this.writeStream.destroy();
      this.writeStream = null;
    }

    if (this.readStream) {
      this.readStream.destroy();
      this.readStream = null;
    }

    await this._cleanupPipes();
    this.emit('channel-closed', { workerId: this.workerId });
  }

  /**
   * Cleanup FIFO pipes
   */
  async _cleanupPipes() {
    try {
      if (fsSync.existsSync(this.inPipe)) {
        await fs.unlink(this.inPipe);
      }
      if (fsSync.existsSync(this.outPipe)) {
        await fs.unlink(this.outPipe);
      }
    } catch (error) {
      // Ignore cleanup errors
    }
  }

  /**
   * Check if channel is connected
   */
  isConnected() {
    return this.connected;
  }
}

module.exports = FIFOChannel;
