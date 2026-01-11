/**
 * n8n MCP Client
 * Connects to n8n MCP server via HTTP
 */

import axios from 'axios';

const N8N_MCP_URL = process.env.N8N_MCP_URL || 'http://n8n-mcp-server.cortex-system.svc.cluster.local:3002';

/**
 * Execute a tool on the n8n MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeN8nTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${N8N_MCP_URL}/execute`, {
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
 * List available tools on n8n MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listN8nTools() {
  try {
    const response = await axios.get(`${N8N_MCP_URL}/tools`, {
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
 * Check n8n MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkN8nHealth() {
  try {
    const response = await axios.get(`${N8N_MCP_URL}/health`, {
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
 * Query n8n system with intelligent routing
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryN8n(query) {
  // For now, use a generic query tool
  // Future: Implement smarter tool selection based on query
  return executeN8nTool('n8n_query', { query });
}
