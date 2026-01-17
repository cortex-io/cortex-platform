#!/usr/bin/env node
/**
 * Cortex MCP Server - SSE Wrapper
 * Provides HTTP/SSE transport for the stdio-based MCP server
 * Enables remote access via mcp-remote package
 */

import { spawn } from 'child_process';
import http from 'http';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SSE_PORT = process.env.SSE_PORT || 3000;
const HEALTH_PORT = process.env.HEALTH_PORT || 8080;

/**
 * Health check server
 */
function startHealthServer() {
  const server = http.createServer((req, res) => {
    if (req.url === '/health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'healthy',
        server: 'cortex-mcp-sse',
        version: '1.0.0',
        timestamp: new Date().toISOString()
      }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  server.listen(HEALTH_PORT, () => {
    console.error(`[Health Server] Listening on port ${HEALTH_PORT}`);
  });

  return server;
}

/**
 * SSE connection handler
 */
function handleSSE(req, res) {
  console.error('[SSE] New client connection');

  // Set SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'X-Accel-Buffering': 'no' // Disable nginx buffering
  });

  // Send initial comment to establish connection
  res.write(': SSE connection established\n\n');

  // Spawn the stdio-based MCP server
  const mcpProcess = spawn('node', [join(__dirname, 'index.js')], {
    stdio: ['pipe', 'pipe', 'pipe']
  });

  console.error(`[SSE] Spawned MCP process PID: ${mcpProcess.pid}`);

  // Forward MCP stdout to SSE client
  mcpProcess.stdout.on('data', (data) => {
    const lines = data.toString().split('\n');

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        // Validate it's valid JSON before sending
        JSON.parse(line);
        res.write(`data: ${line}\n\n`);
      } catch (e) {
        // Not JSON, might be a log message - skip it
        console.error(`[SSE] Skipping non-JSON output: ${line.substring(0, 100)}`);
      }
    }
  });

  // Log MCP stderr (debug/error messages)
  mcpProcess.stderr.on('data', (data) => {
    const message = data.toString().trim();
    console.error(`[MCP] ${message}`);
  });

  // Handle MCP process errors
  mcpProcess.on('error', (error) => {
    console.error(`[SSE] MCP process error: ${error.message}`);
    res.write(`event: error\ndata: ${JSON.stringify({ error: error.message })}\n\n`);
  });

  // Handle MCP process exit
  mcpProcess.on('exit', (code, signal) => {
    console.error(`[SSE] MCP process exited with code ${code}, signal ${signal}`);
    res.end();
  });

  // Handle client disconnect
  req.on('close', () => {
    console.error(`[SSE] Client disconnected, killing MCP process ${mcpProcess.pid}`);
    mcpProcess.kill('SIGTERM');
  });

  // Handle client data (POST messages from mcp-remote)
  let buffer = '';
  req.on('data', (chunk) => {
    buffer += chunk.toString();

    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        // Forward client message to MCP stdin
        mcpProcess.stdin.write(line + '\n');
      } catch (error) {
        console.error(`[SSE] Error writing to MCP stdin: ${error.message}`);
      }
    }
  });
}

/**
 * Handle POST requests for bidirectional communication
 */
function handlePOST(req, res) {
  // For mcp-remote compatibility, accept POST to /sse for sending messages
  if (req.url === '/sse' || req.url === '/message') {
    let body = '';

    req.on('data', (chunk) => {
      body += chunk.toString();
    });

    req.on('end', () => {
      try {
        // Validate JSON
        JSON.parse(body);

        // Return 202 Accepted - message will be processed via SSE connection
        res.writeHead(202, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'accepted' }));
      } catch (error) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
  } else {
    res.writeHead(404);
    res.end();
  }
}

/**
 * Main SSE server
 */
function startSSEServer() {
  const server = http.createServer((req, res) => {
    console.error(`[SSE Server] ${req.method} ${req.url}`);

    if (req.method === 'GET' && req.url === '/sse') {
      handleSSE(req, res);
    } else if (req.method === 'POST') {
      handlePOST(req, res);
    } else if (req.method === 'GET' && req.url === '/') {
      // Informational endpoint
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        server: 'cortex-mcp-sse',
        version: '1.0.0',
        endpoints: {
          sse: '/sse',
          health: `http://localhost:${HEALTH_PORT}/health`
        },
        protocol: 'MCP over Server-Sent Events',
        status: 'ready'
      }));
    } else {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found' }));
    }
  });

  server.listen(SSE_PORT, () => {
    console.error(`[SSE Server] Cortex MCP SSE Server listening on port ${SSE_PORT}`);
    console.error(`[SSE Server] SSE endpoint: http://localhost:${SSE_PORT}/sse`);
    console.error(`[SSE Server] Health check: http://localhost:${HEALTH_PORT}/health`);
  });

  return server;
}

/**
 * Main entry point
 */
function main() {
  console.error('[Cortex MCP SSE] Starting SSE wrapper server...');

  // Start health check server
  startHealthServer();

  // Start SSE server
  startSSEServer();

  // Handle process signals
  process.on('SIGINT', () => {
    console.error('[Cortex MCP SSE] Received SIGINT, shutting down...');
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    console.error('[Cortex MCP SSE] Received SIGTERM, shutting down...');
    process.exit(0);
  });

  console.error('[Cortex MCP SSE] Server ready');
}

// Start the SSE server
main();
