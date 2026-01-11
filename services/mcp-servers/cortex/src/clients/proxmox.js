/**
 * Proxmox MCP Client
 * Connects to Proxmox MCP server via HTTP
 */

import axios from 'axios';

const PROXMOX_MCP_URL = process.env.PROXMOX_MCP_URL || 'http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000';

/**
 * Execute a tool on the Proxmox MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeProxmoxTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${PROXMOX_MCP_URL}/execute`, {
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
 * List available tools on Proxmox MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listProxmoxTools() {
  try {
    const response = await axios.get(`${PROXMOX_MCP_URL}/tools`, {
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
 * Check Proxmox MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkProxmoxHealth() {
  try {
    const response = await axios.get(`${PROXMOX_MCP_URL}/health`, {
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
 * Query Proxmox system with intelligent routing
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryProxmox(query) {
  return executeProxmoxTool('proxmox_query', { query });
}
