/**
 * Kubernetes MCP Client
 * Connects to Kubernetes MCP server via HTTP
 */

import axios from 'axios';

const K8S_MCP_URL = process.env.K8S_MCP_URL || 'http://kubernetes-mcp-server.cortex-system.svc.cluster.local:3001';

/**
 * Execute a tool on the Kubernetes MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeK8sTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${K8S_MCP_URL}/execute`, {
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
 * List available tools on Kubernetes MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listK8sTools() {
  try {
    const response = await axios.get(`${K8S_MCP_URL}/tools`, {
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
