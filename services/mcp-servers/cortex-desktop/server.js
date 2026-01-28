/**
 * Cortex Desktop MCP Server v2.3
 * Provides MCP protocol access to Cortex orchestrator for desktop Claude
 * Transport: SSE (Server-Sent Events)
 * Auth: Anthropic API key validation
 *
 * Learning Integration:
 * - Tracks tool executions with success/failure outcomes
 * - Stores execution data in Qdrant for analysis
 * - Enables learning which tools work for which query types
 */

const express = require('express');
const axios = require('axios');
const Redis = require('ioredis');
const cors = require('cors');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

// Learning integration
let learningClient = null;
let LEARNING_ENABLED = false;

try {
  const learning = require('./qdrant-learning');
  learningClient = learning.learningClient;
  LEARNING_ENABLED = learning.LEARNING_ENABLED;
  console.log('[Learning] Module loaded');
} catch (error) {
  console.log('[Learning] Module not available:', error.message);
}

const app = express();
const PORT = process.env.PORT || 8765;

// Configuration
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const REDIS_HOST = process.env.REDIS_HOST || 'redis.cortex-system.svc.cluster.local';
const REDIS_PORT = process.env.REDIS_PORT || 6379;

// MCP Server URLs (via Traefik ingress for proper routing)
const PROXMOX_MCP_URL = process.env.PROXMOX_MCP_URL || 'https://proxmox-mcp.ry-ops.dev';
const UNIFI_MCP_URL = process.env.UNIFI_MCP_URL || 'https://unifi-mcp.ry-ops.dev';
const SANDFLY_MCP_URL = process.env.SANDFLY_MCP_URL || 'https://sandfly-mcp.ry-ops.dev';
const CLOUDFLARE_MCP_URL = process.env.CLOUDFLARE_MCP_URL || 'https://cloudflare-mcp.ry-ops.dev';

// Token throttle configuration (separate from web chat)
const DESKTOP_RATE_LIMIT_ITPM = 50000; // 50K tokens/min for desktop
const WINDOW_MS = 60000; // 1 minute window
const REDIS_KEY = 'anthropic:desktop:token-usage'; // Separate key from web chat

// Initialize Redis for token throttling
let redisClient = null;
try {
  redisClient = new Redis({
    host: REDIS_HOST,
    port: REDIS_PORT,
    maxRetriesPerRequest: 3,
    lazyConnect: true
  });

  redisClient.on('error', (error) => {
    console.error('[Redis] Connection error:', error.message);
  });

  redisClient.on('connect', () => {
    console.log('[Redis] Connected successfully');
  });

  redisClient.on('ready', () => {
    console.log('[Redis] Ready for operations');
  });

  redisClient.connect().catch(err => {
    console.error('[Redis] Failed to connect:', err.message);
  });
} catch (error) {
  console.error('[Redis] Initialization error:', error.message);
}

// Token Throttle Class (Desktop-specific)
class DesktopTokenThrottle {
  constructor(redis) {
    this.redis = redis;
    this.enabled = !!redis;
    console.log(`[DesktopThrottle] Initialized with limit ${DESKTOP_RATE_LIMIT_ITPM} tokens/minute (Redis: ${this.enabled ? 'enabled' : 'disabled'})`);
  }

  estimateTokens(messages, tools = [], systemPrompt = null) {
    const text = JSON.stringify({ messages, tools, system: systemPrompt });
    return Math.ceil(text.length / 4);
  }

  async checkAndWait(estimatedTokens) {
    if (!this.enabled) {
      return { allowed: true, waitMs: 0, currentUsage: 0 };
    }

    const now = Date.now();
    const windowStart = now - WINDOW_MS;

    try {
      const recentEntries = await this.redis.zrangebyscore(
        REDIS_KEY,
        windowStart,
        now,
        'WITHSCORES'
      );

      let currentUsage = 0;
      for (let i = 0; i < recentEntries.length; i += 2) {
        currentUsage += parseInt(recentEntries[i], 10);
      }

      if (currentUsage + estimatedTokens > DESKTOP_RATE_LIMIT_ITPM) {
        const oldestTimestamp = recentEntries.length > 0 ? parseInt(recentEntries[1], 10) : now;
        const waitMs = Math.max(0, oldestTimestamp + WINDOW_MS - now);

        console.log(`[DesktopThrottle] Rate limit would be exceeded (${currentUsage + estimatedTokens}/${DESKTOP_RATE_LIMIT_ITPM}), waiting ${waitMs}ms`);

        return {
          allowed: false,
          waitMs,
          currentUsage,
          estimatedTokens
        };
      }

      await this.redis.zadd(REDIS_KEY, now, `${estimatedTokens}:${now}`);
      await this.redis.zremrangebyscore(REDIS_KEY, '-inf', windowStart);

      console.log(`[DesktopThrottle] Request allowed (${currentUsage + estimatedTokens}/${DESKTOP_RATE_LIMIT_ITPM} tokens used)`);

      return {
        allowed: true,
        waitMs: 0,
        currentUsage: currentUsage + estimatedTokens,
        estimatedTokens
      };

    } catch (error) {
      console.error(`[DesktopThrottle] Redis error:`, error.message);
      return { allowed: true, waitMs: 0, currentUsage: 0 };
    }
  }

  async throttle(messages, tools = [], systemPrompt = null) {
    const estimatedTokens = this.estimateTokens(messages, tools, systemPrompt);

    while (true) {
      const check = await this.checkAndWait(estimatedTokens);

      if (check.allowed) {
        return check;
      }

      await new Promise(resolve => setTimeout(resolve, check.waitMs));
    }
  }
}

const tokenThrottle = new DesktopTokenThrottle(redisClient);

// Middleware
app.use(cors());
app.use(express.json());

// Auth middleware
function validateApiKey(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid authorization header' });
  }

  const apiKey = authHeader.substring(7);

  if (apiKey !== ANTHROPIC_API_KEY) {
    return res.status(401).json({ error: 'Invalid API key' });
  }

  next();
}

// Health check (no auth required)
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'cortex-desktop-mcp',
    version: '2.1.0',
    transport: 'sse',
    capabilities: {
      kubectl: 'direct',
      proxmox: 'traefik-ingress',
      unifi: 'traefik-ingress',
      sandfly: 'traefik-ingress',
      cloudflare: 'traefik-ingress'
    },
    throttle: {
      enabled: tokenThrottle.enabled,
      limit: DESKTOP_RATE_LIMIT_ITPM
    }
  });
});

// MCP Protocol: List available tools
// Return Cortex orchestrator tools in MCP format
app.get('/mcp/tools', validateApiKey, async (req, res) => {
  try {
    // Define tools that match Cortex orchestrator's capabilities
    const tools = {
      tools: [
        {
          name: 'kubectl',
          description: 'Execute kubectl commands to query the Kubernetes cluster. Use this for pod status, deployments, services, namespaces, logs, and any k8s resources.',
          inputSchema: {
            type: 'object',
            properties: {
              command: {
                type: 'string',
                description: 'The kubectl command to run (e.g., "get pods -n cortex", "describe pod <name> -n cortex")'
              }
            },
            required: ['command']
          }
        },
        {
          name: 'get_infrastructure_summary',
          description: 'Get a comprehensive summary of the infrastructure including k8s cluster, Proxmox VMs, and network status.',
          inputSchema: {
            type: 'object',
            properties: {},
            required: []
          }
        },
        {
          name: 'proxmox_list_vms',
          description: 'List all Proxmox virtual machines and containers',
          inputSchema: {
            type: 'object',
            properties: {},
            required: []
          }
        },
        {
          name: 'proxmox_vm_status',
          description: 'Get status of a specific Proxmox VM or container',
          inputSchema: {
            type: 'object',
            properties: {
              vmid: {
                type: 'string',
                description: 'The VM ID to query'
              }
            },
            required: ['vmid']
          }
        },
        {
          name: 'unifi_devices',
          description: 'List all UniFi network devices',
          inputSchema: {
            type: 'object',
            properties: {},
            required: []
          }
        },
        {
          name: 'unifi_clients',
          description: 'List all UniFi network clients',
          inputSchema: {
            type: 'object',
            properties: {},
            required: []
          }
        },
        {
          name: 'sandfly_scan',
          description: 'Run a Sandfly security scan',
          inputSchema: {
            type: 'object',
            properties: {
              target: {
                type: 'string',
                description: 'Target host or network to scan'
              }
            },
            required: ['target']
          }
        },
        {
          name: 'cloudflare_list_zones',
          description: 'List all Cloudflare DNS zones',
          inputSchema: {
            type: 'object',
            properties: {},
            required: []
          }
        },
        {
          name: 'cloudflare_get_dns_records',
          description: 'Get DNS records for a Cloudflare zone',
          inputSchema: {
            type: 'object',
            properties: {
              zone_id: {
                type: 'string',
                description: 'The Cloudflare zone ID'
              }
            },
            required: ['zone_id']
          }
        }
      ]
    };

    res.json(tools);
  } catch (error) {
    console.error('[Tools] Error:', error.message);
    res.status(500).json({ error: 'Failed to fetch tools' });
  }
});

// Helper: Call MCP server via HTTP/HTTPS
async function callMCPServer(url, toolName, toolArgs) {
  const requestPayload = {
    jsonrpc: '2.0',
    id: Date.now(),
    method: 'tools/call',
    params: {
      name: toolName,
      arguments: toolArgs
    }
  };

  const response = await axios.post(url, requestPayload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000,
    httpsAgent: new (require('https').Agent)({ rejectUnauthorized: false }) // Accept self-signed certs
  });

  return response.data.result;
}

// MCP Protocol: Execute tool
app.post('/mcp/execute', validateApiKey, async (req, res) => {
  const { tool, parameters } = req.body;

  if (!tool) {
    return res.status(400).json({ error: 'Missing tool name' });
  }

  try {
    console.log(`[Execute] Tool: ${tool}`, JSON.stringify(parameters || {}));

    let result;

    // Handle kubectl directly
    if (tool === 'kubectl') {
      if (!parameters || !parameters.command) {
        return res.status(400).json({ error: 'kubectl requires a command parameter' });
      }

      try {
        const { stdout, stderr } = await execPromise(`kubectl ${parameters.command}`);
        result = {
          output: stdout || stderr,
          success: true
        };
      } catch (error) {
        result = {
          output: error.stdout || error.stderr || error.message,
          success: false,
          error: error.message
        };
      }
    }
    // Handle get_infrastructure_summary
    else if (tool === 'get_infrastructure_summary') {
      const [k8sResult, proxmoxResult] = await Promise.allSettled([
        execPromise('kubectl get nodes,pods --all-namespaces'),
        callMCPServer(PROXMOX_MCP_URL, 'list_vms', {})
      ]);

      result = {
        kubernetes: k8sResult.status === 'fulfilled' ? k8sResult.value.stdout : k8sResult.reason.message,
        proxmox: proxmoxResult.status === 'fulfilled' ? proxmoxResult.value : proxmoxResult.reason.message
      };
    }
    // Route to Proxmox MCP server
    else if (tool.startsWith('proxmox_')) {
      const mcpTool = tool.replace('proxmox_', '');
      result = await callMCPServer(PROXMOX_MCP_URL, mcpTool, parameters || {});
    }
    // Route to UniFi MCP server
    else if (tool.startsWith('unifi_')) {
      const mcpTool = tool.replace('unifi_', '');
      result = await callMCPServer(UNIFI_MCP_URL, mcpTool, parameters || {});
    }
    // Route to Sandfly MCP server
    else if (tool.startsWith('sandfly_')) {
      const mcpTool = tool.replace('sandfly_', '');
      result = await callMCPServer(SANDFLY_MCP_URL, mcpTool, parameters || {});
    }
    // Route to Cloudflare MCP server
    else if (tool.startsWith('cloudflare_')) {
      const mcpTool = tool.replace('cloudflare_', '');
      result = await callMCPServer(CLOUDFLARE_MCP_URL, mcpTool, parameters || {});
    }
    else {
      return res.status(400).json({ error: `Unknown tool: ${tool}` });
    }

    console.log(`[Execute] Success: ${tool}`);
    res.json(result);
  } catch (error) {
    console.error('[Execute] Error:', error.message);
    console.error('[Execute] Stack:', error.stack);
    res.status(500).json({
      error: 'Tool execution failed',
      details: error.response?.data || error.message
    });
  }
});

// MCP Protocol: Chat not supported (tools only)
app.post('/mcp/chat', validateApiKey, (req, res) => {
  res.status(501).json({
    error: 'Chat not implemented',
    message: 'This MCP server provides tools only. Use the tools/call endpoint instead.'
  });
});

// MCP Protocol: List available prompts (empty for now)
app.get('/mcp/prompts', validateApiKey, (req, res) => {
  res.json({ prompts: [] });
});

// MCP Protocol: List available resources
app.get('/mcp/resources', validateApiKey, async (req, res) => {
  res.json({ resources: [] });
});

// MCP Protocol: Initialize connection
app.post('/mcp/initialize', validateApiKey, (req, res) => {
  res.json({
    protocolVersion: '2024-11-05',
    serverInfo: {
      name: 'cortex-desktop-mcp',
      version: '2.0.0'
    },
    capabilities: {
      tools: {
        listChanged: false
      },
      prompts: {
        listChanged: false
      },
      resources: {
        listChanged: false
      }
    }
  });
});

// Store active SSE connections by session ID
const sseConnections = new Map();

// MCP Protocol: SSE Transport Endpoint (GET for server-to-client events)
app.get('/sse', (req, res) => {
  const sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  console.log(`[SSE] New SSE connection established: ${sessionId}`);

  // Set SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'X-Accel-Buffering': 'no'
  });

  // Store this connection
  sseConnections.set(sessionId, res);

  // Send initial comment (keep-alive)
  res.write(': SSE connection established\n\n');

  // Send endpoint event telling client where to POST messages
  // The client will POST to /message with the session ID
  const endpointEvent = `/message?sessionId=${sessionId}`;
  res.write(`event: endpoint\ndata: ${endpointEvent}\n\n`);

  // Handle client disconnect
  req.on('close', () => {
    console.log(`[SSE] Client disconnected: ${sessionId}`);
    sseConnections.delete(sessionId);
  });

  // Send periodic heartbeat to keep connection alive
  const heartbeat = setInterval(() => {
    if (sseConnections.has(sessionId)) {
      res.write(': heartbeat\n\n');
    } else {
      clearInterval(heartbeat);
    }
  }, 30000);

  req.on('close', () => {
    clearInterval(heartbeat);
  });
});

// MCP Protocol: Message endpoint (POST for client-to-server messages)
app.post('/message', async (req, res) => {
  const sessionId = req.query.sessionId;
  const sseRes = sseConnections.get(sessionId);

  if (!sseRes) {
    console.error(`[Message] No SSE connection found for session: ${sessionId}`);
    return res.status(400).json({
      jsonrpc: '2.0',
      id: null,
      error: {
        code: -32600,
        message: 'Invalid session - SSE connection not found'
      }
    });
  }

  const request = req.body;
  console.log(`[Message] Received MCP request: ${request.method} (session: ${sessionId})`);

  let response;

  try {
    // Handle MCP methods
    switch (request.method) {
      case 'initialize':
        response = {
          jsonrpc: '2.0',
          id: request.id,
          result: {
            protocolVersion: '2024-11-05',
            serverInfo: {
              name: 'cortex-desktop-mcp',
              version: '2.2.0'
            },
            capabilities: {
              tools: {},
              prompts: {},
              resources: {}
            }
          }
        };
        break;

      case 'notifications/initialized':
        // Client notification that initialization is complete - no response needed
        console.log(`[Message] Client initialized (session: ${sessionId})`);
        return res.status(202).send();

      case 'tools/list':
        try {
          const tools = getLocalTools();
          response = {
            jsonrpc: '2.0',
            id: request.id,
            result: { tools }
          };
        } catch (error) {
          response = {
            jsonrpc: '2.0',
            id: request.id,
            error: {
              code: -32603,
              message: `Failed to fetch tools: ${error.message}`
            }
          };
        }
        break;

      case 'tools/call':
        try {
          const { name, arguments: args } = request.params;
          const result = await executeToolLocal(name, args || {});
          response = {
            jsonrpc: '2.0',
            id: request.id,
            result: {
              content: [
                {
                  type: 'text',
                  text: typeof result === 'string' ? result : JSON.stringify(result, null, 2)
                }
              ]
            }
          };
        } catch (error) {
          response = {
            jsonrpc: '2.0',
            id: request.id,
            error: {
              code: -32603,
              message: `Tool execution failed: ${error.message}`
            }
          };
        }
        break;

      case 'ping':
        response = {
          jsonrpc: '2.0',
          id: request.id,
          result: {}
        };
        break;

      case 'prompts/list':
        response = {
          jsonrpc: '2.0',
          id: request.id,
          result: { prompts: [] }
        };
        break;

      case 'resources/list':
        response = {
          jsonrpc: '2.0',
          id: request.id,
          result: { resources: [] }
        };
        break;

      default:
        response = {
          jsonrpc: '2.0',
          id: request.id,
          error: {
            code: -32601,
            message: `Method not found: ${request.method}`
          }
        };
    }
  } catch (error) {
    console.error(`[Message] Error processing request: ${error.message}`);
    response = {
      jsonrpc: '2.0',
      id: request.id,
      error: {
        code: -32603,
        message: `Internal error: ${error.message}`
      }
    };
  }

  // Send response via SSE stream
  if (response) {
    sseRes.write(`data: ${JSON.stringify(response)}\n\n`);
  }

  // Acknowledge receipt
  res.status(202).send();
});

// Get local tools (not fetching from remote MCP servers)
function getLocalTools() {
  return [
    {
      name: 'kubectl',
      description: 'Execute kubectl commands to query the Kubernetes cluster. Use this for pod status, deployments, services, namespaces, logs, and any k8s resources.',
      inputSchema: {
        type: 'object',
        properties: {
          command: {
            type: 'string',
            description: 'The kubectl command to run (e.g., "get pods -n cortex", "describe pod <name> -n cortex")'
          }
        },
        required: ['command']
      }
    },
    {
      name: 'get_infrastructure_summary',
      description: 'Get a comprehensive summary of the infrastructure including k8s cluster status.',
      inputSchema: {
        type: 'object',
        properties: {},
        required: []
      }
    }
  ];
}

// Execute tool locally with learning tracking
async function executeToolLocal(toolName, args, sessionId = null) {
  console.log(`[Execute] Tool: ${toolName}`, JSON.stringify(args));

  const startTime = Date.now();
  let result;
  let success = false;
  let errorType = null;

  try {
    if (toolName === 'kubectl') {
      if (!args.command) {
        throw new Error('kubectl requires a command parameter');
      }

      try {
        const { stdout, stderr } = await execPromise(`kubectl ${args.command}`);
        result = {
          output: stdout || stderr,
          success: true
        };
        success = true;
      } catch (error) {
        result = {
          output: error.stdout || error.stderr || error.message,
          success: false,
          error: error.message
        };
        errorType = 'command_failed';
      }
    } else if (toolName === 'get_infrastructure_summary') {
      try {
        const { stdout } = await execPromise('kubectl get nodes,pods --all-namespaces -o wide');
        result = {
          kubernetes: stdout,
          timestamp: new Date().toISOString()
        };
        success = true;
      } catch (error) {
        result = {
          error: error.message,
          timestamp: new Date().toISOString()
        };
        errorType = 'command_failed';
      }
    } else {
      throw new Error(`Unknown tool: ${toolName}`);
    }
  } catch (error) {
    result = { error: error.message };
    errorType = 'execution_error';
  }

  // Track execution for learning (async, don't wait)
  const latencyMs = Date.now() - startTime;
  trackExecution(toolName, args, success, latencyMs, errorType, sessionId);

  return result;
}

/**
 * Track tool execution for learning (fire and forget)
 */
async function trackExecution(toolName, args, success, latencyMs, errorType, sessionId) {
  if (!learningClient || !learningClient.initialized) {
    return;
  }

  try {
    await learningClient.storeExecution({
      tool: toolName,
      parameters: args,
      success,
      latencyMs,
      errorType,
      sessionId
    });
  } catch (error) {
    // Don't let learning failures affect tool execution
    console.error('[Learning] Track execution failed:', error.message);
  }
}

// Learning statistics endpoint
app.get('/learning/stats', async (req, res) => {
  if (!learningClient || !learningClient.initialized) {
    return res.json({
      enabled: false,
      message: 'Learning not initialized'
    });
  }

  try {
    const kubectlStats = await learningClient.getToolStats('kubectl');
    const summaryStats = await learningClient.getToolStats('get_infrastructure_summary');

    res.json({
      enabled: true,
      tools: {
        kubectl: kubectlStats,
        get_infrastructure_summary: summaryStats
      }
    });
  } catch (error) {
    res.status(500).json({
      error: error.message
    });
  }
});

// Initialize learning and start server
async function startServer() {
  // Initialize learning client
  if (learningClient && LEARNING_ENABLED) {
    try {
      await learningClient.initialize();
    } catch (error) {
      console.error('[Learning] Initialization error:', error.message);
    }
  }

  // Start server
  app.listen(PORT, '0.0.0.0', () => {
    console.log('='.repeat(60));
    console.log('Cortex Desktop MCP Server v2.3 - SSE Transport');
    console.log('='.repeat(60));
    console.log(`Port: ${PORT}`);
    console.log(`Transport: SSE (MCP 2024-11-05 compliant)`);
    console.log(`Learning: ${learningClient?.initialized ? 'ENABLED' : 'disabled'}`);
    console.log('');
    console.log('MCP Transport Endpoints:');
    console.log('  GET  /sse     - SSE stream (server-to-client)');
    console.log('  POST /message - Message endpoint (client-to-server)');
    console.log('');
    console.log('Legacy Endpoints:');
    console.log('  GET  /health - Health check');
    console.log('  GET  /mcp/tools - List available tools');
    console.log('  POST /mcp/execute - Execute a tool');
    console.log('  GET  /learning/stats - Tool execution statistics');
    console.log('='.repeat(60));
    console.log('');
    console.log('Tools available:');
    console.log('  - kubectl (direct execution)');
    console.log('  - get_infrastructure_summary');
    console.log('='.repeat(60));
  });
}

startServer();
