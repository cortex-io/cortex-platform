/**
 * Tailscale MCP Client
 * Connects to Tailscale MCP server via HTTP JSON-RPC
 */

import axios from 'axios';

const TAILSCALE_MCP_URL = process.env.TAILSCALE_MCP_URL || 'http://tailscale-mcp-server.cortex-system.svc.cluster.local:3000';

/**
 * Execute a tool on the Tailscale MCP server using JSON-RPC
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeTailscaleTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${TAILSCALE_MCP_URL}/`, {
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/call',
      params: {
        name: toolName,
        arguments: args
      }
    }, {
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Handle JSON-RPC response
    if (response.data.error) {
      return {
        success: false,
        error: response.data.error.message || 'Unknown error',
        details: response.data.error
      };
    }

    return {
      success: true,
      data: response.data.result
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
 * List available tools on Tailscale MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listTailscaleTools() {
  try {
    const response = await axios.post(`${TAILSCALE_MCP_URL}/`, {
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/list',
      params: {}
    }, {
      timeout: 5000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.data.result) {
      return {
        success: true,
        tools: response.data.result.tools || []
      };
    }

    return {
      success: false,
      error: 'No tools found'
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Check Tailscale MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkTailscaleHealth() {
  try {
    const response = await axios.get(`${TAILSCALE_MCP_URL}/health`, {
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
 * Query Tailscale with intelligent routing
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryTailscale(query) {
  // Analyze query to determine best tool
  const lowerQuery = query.toLowerCase();

  if (lowerQuery.includes('device') && (lowerQuery.includes('list') || lowerQuery.includes('all') || lowerQuery.includes('show'))) {
    return executeTailscaleTool('tailscale_list_devices', {});
  }

  if (lowerQuery.includes('health') || lowerQuery.includes('status') || lowerQuery.includes('overview')) {
    return executeTailscaleTool('tailscale_health', {});
  }

  if (lowerQuery.includes('dns')) {
    return executeTailscaleTool('tailscale_get_dns', {});
  }

  if (lowerQuery.includes('acl') || lowerQuery.includes('access') || lowerQuery.includes('policy')) {
    return executeTailscaleTool('tailscale_get_acl', {});
  }

  if (lowerQuery.includes('key') || lowerQuery.includes('auth key')) {
    return executeTailscaleTool('tailscale_list_keys', {});
  }

  if (lowerQuery.includes('exit node') || lowerQuery.includes('route')) {
    return executeTailscaleTool('tailscale_health', {});  // Health includes exit node info
  }

  // Default to health check for general queries
  return executeTailscaleTool('tailscale_health', {});
}
