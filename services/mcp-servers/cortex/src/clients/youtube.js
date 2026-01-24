/**
 * Cortex YouTube MCP Client
 * Connects to YouTube ingestion/processing services
 */

import axios from 'axios';

const YOUTUBE_MCP_URL = process.env.YOUTUBE_MCP_URL || 'http://youtube-ingestion.cortex-youtube.svc.cluster.local:8080';

/**
 * Execute a tool on the YouTube service
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeYoutubeTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${YOUTUBE_MCP_URL}/execute`, {
      tool: toolName,
      arguments: args
    }, {
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      details: error.response?.data
    };
  }
}

/**
 * List available tools on YouTube service
 * @returns {Promise<Array>} List of available tools
 */
export async function listYoutubeTools() {
  try {
    const response = await axios.get(`${YOUTUBE_MCP_URL}/tools`, {
      timeout: 5000
    });

    return {
      success: true,
      tools: response.data.tools || []
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Check YouTube service health
 * @returns {Promise<Object>} Health status
 */
export async function checkYoutubeHealth() {
  try {
    const response = await axios.get(`${YOUTUBE_MCP_URL}/health`, {
      timeout: 5000
    });

    return {
      healthy: true,
      status: response.data
    };
  } catch (error) {
    return {
      healthy: false,
      error: error.message
    };
  }
}

/**
 * Query YouTube ingestion system
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryYoutube(query) {
  return executeYoutubeTool('youtube_query', { query });
}
