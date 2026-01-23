/**
 * Cortex Fabric Client
 * JavaScript/TypeScript client for connecting to the Cortex Fabric Gateway
 *
 * Usage (browser):
 *   const fabric = new FabricClient('wss://fabric.ry-ops.dev/ws/fabric');
 *   await fabric.connect();
 *   const result = await fabric.callMcpTool('kubernetes', 'list_pods', { namespace: 'cortex-system' });
 *
 * Usage (Node.js):
 *   const { FabricClient } = require('./fabric-client');
 *   const fabric = new FabricClient('wss://fabric.ry-ops.dev/ws/fabric');
 */

class FabricClient {
  constructor(url, options = {}) {
    this.url = url;
    this.clientType = options.clientType || 'chat';
    this.reconnect = options.reconnect !== false;
    this.reconnectDelay = options.reconnectDelay || 5000;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
    this.heartbeatInterval = options.heartbeatInterval || 25000;

    this.ws = null;
    this.clientId = null;
    this.sessionId = null;
    this.connected = false;
    this.reconnectAttempts = 0;

    this._pendingRequests = new Map();
    this._eventHandlers = new Map();
    this._heartbeatTimer = null;
    this._reconnectTimer = null;
  }

  /**
   * Connect to the Fabric Gateway
   */
  async connect() {
    return new Promise((resolve, reject) => {
      const wsUrl = `${this.url}?client_type=${this.clientType}`;

      // Use native WebSocket in browser, or ws package in Node.js
      if (typeof WebSocket !== 'undefined') {
        this.ws = new WebSocket(wsUrl);
      } else {
        // Node.js environment
        const WebSocketNode = require('ws');
        this.ws = new WebSocketNode(wsUrl);
      }

      this.ws.onopen = () => {
        console.log('[Fabric] WebSocket connected');
      };

      this.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.type === 'connected') {
          this.clientId = message.client_id;
          this.connected = true;
          this.reconnectAttempts = 0;
          this._startHeartbeat();
          console.log(`[Fabric] Connected as ${this.clientId}`);
          console.log(`[Fabric] Available MCP servers: ${message.mcp_servers?.join(', ')}`);
          resolve(message);
        } else {
          this._handleMessage(message);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[Fabric] WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = (event) => {
        console.log(`[Fabric] WebSocket closed: ${event.code} ${event.reason}`);
        this.connected = false;
        this._stopHeartbeat();

        if (this.reconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this._scheduleReconnect();
        }
      };
    });
  }

  /**
   * Disconnect from the Fabric Gateway
   */
  async disconnect() {
    this.reconnect = false;
    this._stopHeartbeat();

    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
    }

    if (this.sessionId) {
      await this.endSession();
    }

    if (this.ws) {
      this.ws.close();
    }
  }

  /**
   * Start a new session or resume existing one
   */
  async startSession(options = {}) {
    const response = await this._request({
      type: 'session_start',
      data: {
        session_id: options.sessionId || this.sessionId,
        working_directory: options.workingDirectory || '/',
      }
    });

    if (response.type === 'session_started') {
      this.sessionId = response.session_id;
      return this.sessionId;
    }

    throw new Error(`Failed to start session: ${JSON.stringify(response)}`);
  }

  /**
   * End the current session
   */
  async endSession(summary = '') {
    if (!this.sessionId) return;

    await this._request({
      type: 'session_end',
      data: { summary }
    });

    this.sessionId = null;
  }

  /**
   * Call an MCP tool
   */
  async callMcpTool(server, tool, args = {}) {
    const response = await this._request({
      type: 'mcp_call',
      data: { server, tool, args }
    }, 120000); // 2 minute timeout for MCP calls

    if (response.type === 'mcp_result') {
      return response.result;
    } else if (response.type === 'mcp_error') {
      throw new Error(response.error);
    }

    throw new Error(`Unexpected response: ${JSON.stringify(response)}`);
  }

  /**
   * Publish an event to all fabric clients
   */
  async publishEvent(eventName, data) {
    await this._send({
      type: 'event',
      data: { name: eventName, data }
    });
  }

  /**
   * Subscribe to additional channels
   */
  async subscribe(channels) {
    await this._send({
      type: 'subscribe',
      data: { channels }
    });
  }

  /**
   * Unsubscribe from channels
   */
  async unsubscribe(channels) {
    await this._send({
      type: 'unsubscribe',
      data: { channels }
    });
  }

  /**
   * Query shared state
   */
  async queryState(key, params = {}) {
    const response = await this._request({
      type: 'state_query',
      data: { key, params }
    });

    if (response.type === 'state_update') {
      return response.data;
    }

    throw new Error(`State query failed: ${JSON.stringify(response)}`);
  }

  /**
   * Get current infrastructure state
   */
  async getInfrastructure() {
    return this.queryState('infrastructure');
  }

  /**
   * Get connected clients
   */
  async getClients() {
    return this.queryState('clients');
  }

  /**
   * Get timeline events
   */
  async getTimeline(params = {}) {
    return this.queryState('timeline', params);
  }

  /**
   * Register event handler
   */
  on(eventName, handler) {
    if (!this._eventHandlers.has(eventName)) {
      this._eventHandlers.set(eventName, []);
    }
    this._eventHandlers.get(eventName).push(handler);
    return () => this.off(eventName, handler);
  }

  /**
   * Remove event handler
   */
  off(eventName, handler) {
    const handlers = this._eventHandlers.get(eventName);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
      }
    }
  }

  // Private methods

  _send(message) {
    if (!this.ws || this.ws.readyState !== 1) {
      throw new Error('Not connected to Fabric Gateway');
    }
    this.ws.send(JSON.stringify(message));
  }

  async _request(message, timeout = 60000) {
    const requestId = this._generateId();
    message.request_id = requestId;

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._pendingRequests.delete(requestId);
        reject(new Error('Request timeout'));
      }, timeout);

      this._pendingRequests.set(requestId, { resolve, reject, timer });
      this._send(message);
    });
  }

  _handleMessage(message) {
    // Handle request responses
    if (message.request_id && this._pendingRequests.has(message.request_id)) {
      const { resolve, timer } = this._pendingRequests.get(message.request_id);
      clearTimeout(timer);
      this._pendingRequests.delete(message.request_id);
      resolve(message);
      return;
    }

    // Handle events
    if (message.type === 'event_broadcast') {
      this._dispatchEvent(message.event, message.data);
      return;
    }

    // Handle state updates
    if (message.type === 'state_update') {
      this._dispatchEvent('state_update', message);
      return;
    }

    // Handle session messages
    if (message.type === 'session_started') {
      this.sessionId = message.session_id;
      this._dispatchEvent('session_started', message);
      return;
    }

    if (message.type === 'session_ended') {
      this.sessionId = null;
      this._dispatchEvent('session_ended', message);
      return;
    }

    // Handle pong
    if (message.type === 'pong') {
      return;
    }

    // Dispatch unknown messages as events
    this._dispatchEvent(message.type, message);
  }

  _dispatchEvent(eventName, data) {
    // Call specific handlers
    const handlers = this._eventHandlers.get(eventName) || [];
    handlers.forEach(handler => {
      try {
        handler(data);
      } catch (e) {
        console.error('[Fabric] Event handler error:', e);
      }
    });

    // Call wildcard handlers
    const wildcardHandlers = this._eventHandlers.get('*') || [];
    wildcardHandlers.forEach(handler => {
      try {
        handler(eventName, data);
      } catch (e) {
        console.error('[Fabric] Wildcard handler error:', e);
      }
    });
  }

  _startHeartbeat() {
    this._heartbeatTimer = setInterval(() => {
      if (this.connected) {
        this._send({ type: 'heartbeat', timestamp: new Date().toISOString() });
      }
    }, this.heartbeatInterval);
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  _scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 60000);

    console.log(`[Fabric] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this._reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
        if (this.sessionId) {
          await this.startSession({ sessionId: this.sessionId });
        }
      } catch (e) {
        console.error('[Fabric] Reconnect failed:', e);
      }
    }, delay);
  }

  _generateId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// Export for different environments
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { FabricClient };
} else if (typeof window !== 'undefined') {
  window.FabricClient = FabricClient;
}
