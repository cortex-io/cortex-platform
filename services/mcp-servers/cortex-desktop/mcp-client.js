#!/usr/bin/env node
/**
 * Cortex MCP Client for Desktop Claude
 * Connects to Cortex Desktop MCP Server via HTTP
 */

const http = require('http');

const BASE_URL = 'http://10.88.145.216:8765';
const API_KEY = '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';

// Make HTTP request helper
function request(method, path, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(BASE_URL + path);

    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: method,
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json'
      }
    };

    const req = http.request(options, (res) => {
      let data = '';

      res.on('data', chunk => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          if (res.statusCode === 200) {
            resolve(JSON.parse(data));
          } else {
            resolve({ error: data, statusCode: res.statusCode });
          }
        } catch(e) {
          resolve({ error: data });
        }
      });
    });

    req.on('error', reject);

    if (body) {
      req.write(JSON.stringify(body));
    }

    req.end();
  });
}

// Send response to Claude
function sendResponse(id, result) {
  const response = {
    jsonrpc: '2.0',
    id: id,
    result: result
  };
  process.stdout.write(JSON.stringify(response) + '\n');
}

// Send error to Claude
function sendError(id, error) {
  const response = {
    jsonrpc: '2.0',
    id: id,
    error: {
      code: -32603,
      message: error.message || String(error)
    }
  };
  process.stdout.write(JSON.stringify(response) + '\n');
}

// Handle incoming messages from Claude Desktop
process.stdin.on('data', async (chunk) => {
  try {
    const lines = chunk.toString().split('\n').filter(line => line.trim());

    for (const line of lines) {
      if (!line.trim()) continue;

      const msg = JSON.parse(line);

      if (msg.method === 'initialize') {
        // Initialize MCP connection
        const result = await request('POST', '/mcp/initialize', {
          protocolVersion: msg.params?.protocolVersion || '2024-11-05',
          clientInfo: msg.params?.clientInfo || { name: 'claude-desktop', version: '1.0.0' }
        });
        sendResponse(msg.id, result);

      } else if (msg.method === 'tools/list') {
        // List available tools
        const result = await request('GET', '/mcp/tools');
        sendResponse(msg.id, result);

      } else if (msg.method === 'tools/call') {
        // Execute a tool
        const result = await request('POST', '/mcp/execute', {
          tool: msg.params.name,
          parameters: msg.params.arguments || {}
        });

        // Format response for Claude
        sendResponse(msg.id, {
          content: [
            {
              type: 'text',
              text: typeof result === 'string' ? result : JSON.stringify(result, null, 2)
            }
          ]
        });

      } else if (msg.method === 'prompts/list') {
        // List prompts
        const result = await request('GET', '/mcp/prompts');
        sendResponse(msg.id, result);

      } else if (msg.method === 'resources/list') {
        // List resources
        const result = await request('GET', '/mcp/resources');
        sendResponse(msg.id, result);

      } else {
        // Unknown method
        sendError(msg.id, { message: `Unknown method: ${msg.method}` });
      }
    }

  } catch (err) {
    process.stderr.write(`Error: ${err.message}\n`);
  }
});

// Handle errors
process.on('uncaughtException', (err) => {
  process.stderr.write(`Uncaught exception: ${err.message}\n`);
});

process.on('unhandledRejection', (err) => {
  process.stderr.write(`Unhandled rejection: ${err.message}\n`);
});

// Keep process alive
process.stdin.resume();
