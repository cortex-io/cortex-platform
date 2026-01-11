#!/usr/bin/env node
/**
 * Cortex MCP Server
 * Main entry point - implements MCP protocol over stdio
 * Routes to UniFi, Proxmox, Wazuh, and Kubernetes subsystems
 */

import { cortexQueryTool, executeCortexQuery } from './tools/query.js';
import { cortexGetStatusTool, executeCortexGetStatus } from './tools/status.js';

// MCP Protocol Version
const MCP_VERSION = '2024-11-05';

// Available tools
const TOOLS = [cortexQueryTool, cortexGetStatusTool];

/**
 * Handle MCP initialize request
 */
function handleInitialize(request) {
  return {
    jsonrpc: '2.0',
    id: request.id,
    result: {
      protocolVersion: MCP_VERSION,
      serverInfo: {
        name: 'cortex-mcp-server',
        version: '1.0.0'
      },
      capabilities: {
        tools: {}
      }
    }
  };
}

/**
 * Handle MCP tools/list request
 */
function handleToolsList(request) {
  return {
    jsonrpc: '2.0',
    id: request.id,
    result: {
      tools: TOOLS
    }
  };
}

/**
 * Handle MCP tools/call request
 */
async function handleToolsCall(request) {
  const { name, arguments: args } = request.params;

  try {
    let result;

    switch (name) {
      case 'cortex_query':
        result = await executeCortexQuery(args);
        break;

      case 'cortex_get_status':
        result = await executeCortexGetStatus();
        break;

      default:
        return {
          jsonrpc: '2.0',
          id: request.id,
          error: {
            code: -32601,
            message: `Unknown tool: ${name}`,
            data: {
              available_tools: TOOLS.map(t => t.name)
            }
          }
        };
    }

    return {
      jsonrpc: '2.0',
      id: request.id,
      result: {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }
        ]
      }
    };
  } catch (error) {
    return {
      jsonrpc: '2.0',
      id: request.id,
      error: {
        code: -32603,
        message: `Tool execution failed: ${error.message}`,
        data: {
          tool: name,
          error: error.stack
        }
      }
    };
  }
}

/**
 * Handle incoming MCP request
 */
async function handleRequest(request) {
  console.error(`[MCP Server] Received: ${request.method}`);

  switch (request.method) {
    case 'initialize':
      return handleInitialize(request);

    case 'tools/list':
      return handleToolsList(request);

    case 'tools/call':
      return await handleToolsCall(request);

    case 'ping':
      return {
        jsonrpc: '2.0',
        id: request.id,
        result: {}
      };

    default:
      return {
        jsonrpc: '2.0',
        id: request.id,
        error: {
          code: -32601,
          message: `Method not found: ${request.method}`
        }
      };
  }
}

/**
 * Main stdio loop
 */
async function main() {
  console.error('[MCP Server] Cortex MCP Server v1.0.0 starting...');
  console.error('[MCP Server] Mode: stdio');
  console.error('[MCP Server] Tools: cortex_query, cortex_get_status');
  console.error('[MCP Server] Subsystems: UniFi, Proxmox, Wazuh, Kubernetes');

  let buffer = '';

  process.stdin.on('data', async (chunk) => {
    buffer += chunk.toString();

    // Process complete JSON-RPC messages (newline delimited)
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const request = JSON.parse(line);
        const response = await handleRequest(request);

        // Write response to stdout
        process.stdout.write(JSON.stringify(response) + '\n');
      } catch (error) {
        console.error(`[MCP Server] Error processing request: ${error.message}`);

        // Send error response
        const errorResponse = {
          jsonrpc: '2.0',
          id: null,
          error: {
            code: -32700,
            message: 'Parse error',
            data: { error: error.message }
          }
        };
        process.stdout.write(JSON.stringify(errorResponse) + '\n');
      }
    }
  });

  process.stdin.on('end', () => {
    console.error('[MCP Server] Input stream ended, shutting down...');
    process.exit(0);
  });

  process.on('SIGINT', () => {
    console.error('[MCP Server] Received SIGINT, shutting down...');
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    console.error('[MCP Server] Received SIGTERM, shutting down...');
    process.exit(0);
  });

  console.error('[MCP Server] Ready to accept requests');
}

// Start the server
main().catch((error) => {
  console.error(`[MCP Server] Fatal error: ${error.message}`);
  process.exit(1);
});
