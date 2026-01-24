/**
 * Cortex School MCP Client
 * Connects to Cortex School MCP server for content/knowledge management
 */

import axios from 'axios';

const SCHOOL_MCP_URL = process.env.SCHOOL_MCP_URL || 'http://cortex-school-mcp.cortex-school.svc.cluster.local:3000';

/**
 * Execute a tool on the School MCP server
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Tool execution result
 */
export async function executeSchoolTool(toolName, args = {}) {
  try {
    const response = await axios.post(`${SCHOOL_MCP_URL}/execute`, {
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
 * List available tools on School MCP server
 * @returns {Promise<Array>} List of available tools
 */
export async function listSchoolTools() {
  try {
    const response = await axios.get(`${SCHOOL_MCP_URL}/tools`, {
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
 * Check School MCP server health
 * @returns {Promise<Object>} Health status
 */
export async function checkSchoolHealth() {
  try {
    const response = await axios.get(`${SCHOOL_MCP_URL}/health`, {
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
 * Query Cortex School system
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function querySchool(query) {
  return executeSchoolTool('school_query', { query });
}
