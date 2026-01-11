/**
 * UniFi MCP Client
 * Connects to UniFi MCP server via HTTP
 */

import axios from 'axios';

const UNIFI_MCP_URL = process.env.UNIFI_MCP_URL || 'http://unifi-mcp-server.cortex-system.svc.cluster.local:3000';

/**
 * Execute a tool on the UniFi MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeUniFiTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${UNIFI_MCP_URL}/execute`, {
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
 * List available tools on UniFi MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listUniFiTools() {
  try {
    const response = await axios.get(`${UNIFI_MCP_URL}/tools`, {
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
 * Check UniFi MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkUniFiHealth() {
  try {
    const response = await axios.get(`${UNIFI_MCP_URL}/health`, {
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
 * Query UniFi system with intelligent routing
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryUniFi(query) {
  // For now, use a generic query tool
  // Future: Implement smarter tool selection based on query
  return executeUniFiTool('unifi_query', { query });
}
