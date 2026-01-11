/**
 * CheckMK MCP Client
 * Connects to CheckMK MCP server via HTTP
 */

import axios from 'axios';

const CHECKMK_MCP_URL = process.env.CHECKMK_MCP_URL || 'http://checkmk-mcp-server.cortex-system.svc.cluster.local:3000';

/**
 * Execute a tool on the CheckMK MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeCheckMKTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${CHECKMK_MCP_URL}/execute`, {
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
 * List available tools on CheckMK MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listCheckMKTools() {
  try {
    const response = await axios.get(`${CHECKMK_MCP_URL}/tools`, {
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
 * Check CheckMK MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkCheckMKHealth() {
  try {
    const response = await axios.get(`${CHECKMK_MCP_URL}/health`, {
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
 * Query CheckMK system with intelligent routing
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryCheckMK(query) {
  // For now, use a generic query tool
  // Future: Implement smarter tool selection based on query
  return executeCheckMKTool('checkmk_query', { query });
}
