/**
 * Sandfly Security MCP Client
 * Connects to Sandfly MCP server via HTTP
 */

import axios from 'axios';

const SANDFLY_MCP_URL = process.env.SANDFLY_MCP_URL || 'http://sandfly-mcp-server.cortex-system.svc.cluster.local:8080';

/**
 * Execute a tool on the Sandfly MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeSandflyTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${SANDFLY_MCP_URL}/execute`, {
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
 * List available tools on Sandfly MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listSandflyTools() {
  try {
    const response = await axios.get(`${SANDFLY_MCP_URL}/tools`, {
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
 * Check Sandfly MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkSandflyHealth() {
  try {
    const response = await axios.get(`${SANDFLY_MCP_URL}/health`, {
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
 * Query Sandfly security system
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function querySandfly(query) {
  return executeSandflyTool('sandfly_query', { query });
}
