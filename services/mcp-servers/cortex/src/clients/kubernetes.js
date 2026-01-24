/**
 * Kubernetes MCP Client
 * Connects to Kubernetes MCP server via HTTP JSON-RPC
 */

import axios from 'axios';

const K8S_MCP_URL = process.env.K8S_MCP_URL || 'http://kubernetes-mcp-server.cortex-system.svc.cluster.local:3001';

/**
 * Execute a tool on the Kubernetes MCP server using JSON-RPC
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeK8sTool(toolName, args = {}) {
  try {
    // Use JSON-RPC format for MCP HTTP wrapper
    const response = await axios.post(`${K8S_MCP_URL}/`, {
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
 * List available tools on Kubernetes MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listK8sTools() {
  try {
    // Use the dedicated list-tools endpoint
    const response = await axios.get(`${K8S_MCP_URL}/list-tools`, {
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
 * Check Kubernetes MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkK8sHealth() {
  try {
    const response = await axios.get(`${K8S_MCP_URL}/health`, {
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
 * Query Kubernetes system with intelligent routing
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryKubernetes(query) {
  // For now, use a generic query tool
  // Future: Implement smarter tool selection based on query
  return executeK8sTool('k8s_query', { query });
}
