/**
 * Qdrant Learning Layer for Cortex Desktop MCP Server
 *
 * This module provides the learning foundation for tool execution tracking.
 * It stores tool executions with outcomes to learn which tools succeed
 * for which types of queries.
 *
 * Collections:
 *   - tool_executions: Tool call records with success/failure outcomes
 *
 * Since this is a stateless MCP server, learning happens passively:
 *   1. Record all tool executions with outcomes
 *   2. Future: Use similarity to predict tool success (not implemented yet)
 */

const axios = require('axios');
const crypto = require('crypto');

// Configuration
const QDRANT_URL = process.env.QDRANT_URL || 'http://cortex-qdrant.cortex-system:6333';
const COLLECTION_EXECUTIONS = process.env.QDRANT_COLLECTION_EXECUTIONS || 'tool_executions';
const LEARNING_ENABLED = (process.env.LEARNING_ENABLED || 'true').toLowerCase() === 'true';

// Vector dimension (using simple hash-based pseudo-embeddings for now)
const VECTOR_SIZE = 384;

/**
 * Generate a simple pseudo-embedding from text.
 * This is not semantically meaningful but allows storage in Qdrant.
 * For real similarity search, use sentence-transformers or external embedding service.
 */
function generatePseudoEmbedding(text) {
  const hash = crypto.createHash('sha384').update(text.toLowerCase()).digest();
  const embedding = [];
  for (let i = 0; i < hash.length; i++) {
    embedding.push((hash[i] - 128) / 128.0);
  }
  return embedding;
}

/**
 * Generate a UUID v4
 */
function generateId() {
  return crypto.randomUUID();
}

/**
 * Qdrant Learning Client for tool execution tracking
 */
class QdrantLearningClient {
  constructor() {
    this.url = QDRANT_URL;
    this.collection = COLLECTION_EXECUTIONS;
    this.initialized = false;
  }

  /**
   * Initialize the learning client
   */
  async initialize() {
    if (!LEARNING_ENABLED) {
      console.log('[Learning] Disabled via LEARNING_ENABLED=false');
      return false;
    }

    try {
      // Check Qdrant connectivity
      const response = await axios.get(`${this.url}/readyz`, { timeout: 5000 });
      if (response.status !== 200) {
        console.log('[Learning] Qdrant not ready');
        return false;
      }

      // Ensure collection exists
      await this.ensureCollection();

      this.initialized = true;
      console.log(`[Learning] Qdrant initialized at ${this.url}`);
      return true;

    } catch (error) {
      console.error(`[Learning] Init failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Create collection if it doesn't exist
   */
  async ensureCollection() {
    try {
      const response = await axios.get(`${this.url}/collections/${this.collection}`);
      if (response.status === 200) {
        return; // Collection exists
      }
    } catch (error) {
      if (error.response?.status !== 404) {
        throw error;
      }
    }

    // Create collection
    await axios.put(`${this.url}/collections/${this.collection}`, {
      vectors: { size: VECTOR_SIZE, distance: 'Cosine' },
      on_disk_payload: true
    });
    console.log(`[Learning] Created collection: ${this.collection}`);
  }

  /**
   * Store a tool execution record
   */
  async storeExecution(execution) {
    if (!this.initialized) {
      return false;
    }

    try {
      const id = execution.executionId || generateId();
      const text = `${execution.tool} ${JSON.stringify(execution.parameters || {})}`;
      const embedding = generatePseudoEmbedding(text);

      const point = {
        id,
        vector: embedding,
        payload: {
          execution_id: id,
          tool: execution.tool,
          parameters_preview: JSON.stringify(execution.parameters || {}).slice(0, 200),
          success: execution.success,
          latency_ms: execution.latencyMs || 0,
          error_type: execution.errorType || null,
          timestamp: new Date().toISOString(),
          session_id: execution.sessionId || null
        }
      };

      const response = await axios.put(
        `${this.url}/collections/${this.collection}/points`,
        { points: [point] },
        { params: { wait: 'true' } }
      );

      return response.status === 200 || response.status === 201;

    } catch (error) {
      console.error(`[Learning] Store execution failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Get execution statistics for a tool
   */
  async getToolStats(toolName) {
    if (!this.initialized) {
      return null;
    }

    try {
      const response = await axios.post(
        `${this.url}/collections/${this.collection}/points/scroll`,
        {
          filter: {
            must: [
              { key: 'tool', match: { value: toolName } }
            ]
          },
          limit: 100,
          with_payload: true
        }
      );

      const points = response.data.result?.points || [];
      if (points.length === 0) {
        return null;
      }

      let successes = 0;
      let failures = 0;
      let totalLatency = 0;

      for (const point of points) {
        const payload = point.payload || {};
        if (payload.success) {
          successes++;
        } else {
          failures++;
        }
        totalLatency += payload.latency_ms || 0;
      }

      return {
        tool: toolName,
        total: points.length,
        successes,
        failures,
        success_rate: points.length > 0 ? successes / points.length : 0,
        avg_latency_ms: points.length > 0 ? totalLatency / points.length : 0
      };

    } catch (error) {
      console.error(`[Learning] Get stats failed: ${error.message}`);
      return null;
    }
  }
}

// Export singleton instance
const learningClient = new QdrantLearningClient();

module.exports = {
  learningClient,
  QdrantLearningClient,
  generateId,
  LEARNING_ENABLED
};
