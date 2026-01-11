/**
 * Cortex Desktop MCP Server
 * Provides MCP protocol access to Cortex orchestrator for desktop Claude
 * Transport: SSE (Server-Sent Events)
 * Auth: Anthropic API key validation
 */

const express = require('express');
const axios = require('axios');
const Redis = require('ioredis');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 8765;

// Configuration
const CORTEX_ORCHESTRATOR_URL = process.env.CORTEX_URL || 'http://cortex-orchestrator.cortex.svc.cluster.local:8000';
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const REDIS_HOST = process.env.REDIS_HOST || 'redis.cortex-system.svc.cluster.local';
const REDIS_PORT = process.env.REDIS_PORT || 6379;

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
    version: '1.0.0',
    transport: 'sse',
    throttle: {
      enabled: tokenThrottle.enabled,
      limit: DESKTOP_RATE_LIMIT_ITPM
    }
  });
});

// MCP Protocol: List available tools
app.get('/mcp/tools', validateApiKey, async (req, res) => {
  try {
    const response = await axios.get(`${CORTEX_ORCHESTRATOR_URL}/api/tools`);
    res.json(response.data);
  } catch (error) {
    console.error('[Tools] Error fetching tools:', error.message);
    res.status(500).json({ error: 'Failed to fetch tools' });
  }
});

// MCP Protocol: Execute tool
app.post('/mcp/execute', validateApiKey, async (req, res) => {
  const { tool, parameters } = req.body;

  if (!tool || !parameters) {
    return res.status(400).json({ error: 'Missing tool or parameters' });
  }

  try {
    console.log(`[Execute] Tool: ${tool}`, parameters);

    const response = await axios.post(
      `${CORTEX_ORCHESTRATOR_URL}/execute-tool`,
      { tool, parameters },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    res.json(response.data);
  } catch (error) {
    console.error('[Execute] Error:', error.message);
    res.status(500).json({
      error: 'Tool execution failed',
      details: error.response?.data || error.message
    });
  }
});

// MCP Protocol: Send message to Cortex (streaming)
app.post('/mcp/chat', validateApiKey, async (req, res) => {
  const { message, sessionId, history = [] } = req.body;

  if (!message) {
    return res.status(400).json({ error: 'Missing message' });
  }

  // Apply token throttle
  const throttleResult = await tokenThrottle.throttle(
    [...history, { role: 'user', content: message }],
    [],
    null
  );

  if (throttleResult.waitMs > 0) {
    console.log(`[Chat] Throttled for ${throttleResult.waitMs}ms`);
  }

  // Set up SSE
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  try {
    const response = await axios.post(
      `${CORTEX_ORCHESTRATOR_URL}/api/chat`,
      { message, sessionId: sessionId || `desktop-${Date.now()}`, history },
      {
        responseType: 'stream',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        }
      }
    );

    // Forward SSE stream to client
    response.data.on('data', (chunk) => {
      res.write(chunk);
    });

    response.data.on('end', () => {
      res.end();
    });

    response.data.on('error', (error) => {
      console.error('[Chat] Stream error:', error.message);
      res.write(`data: ${JSON.stringify({ type: 'error', error: error.message })}\n\n`);
      res.end();
    });

  } catch (error) {
    console.error('[Chat] Error:', error.message);
    res.write(`data: ${JSON.stringify({ type: 'error', error: error.message })}\n\n`);
    res.end();
  }
});

// MCP Protocol: List available prompts (empty for now)
app.get('/mcp/prompts', validateApiKey, (req, res) => {
  res.json({ prompts: [] });
});

// MCP Protocol: List available resources
app.get('/mcp/resources', validateApiKey, async (req, res) => {
  try {
    // Return cluster resources
    const response = await axios.get(`${CORTEX_ORCHESTRATOR_URL}/api/resources`);
    res.json(response.data);
  } catch (error) {
    console.error('[Resources] Error:', error.message);
    res.json({ resources: [] });
  }
});

// MCP Protocol: Initialize connection
app.post('/mcp/initialize', validateApiKey, (req, res) => {
  res.json({
    protocolVersion: '2024-11-05',
    serverInfo: {
      name: 'cortex-desktop-mcp',
      version: '1.0.0'
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

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log('='.repeat(60));
  console.log('Cortex Desktop MCP Server');
  console.log('='.repeat(60));
  console.log(`Port: ${PORT}`);
  console.log(`Transport: SSE (Server-Sent Events)`);
  console.log(`Cortex URL: ${CORTEX_ORCHESTRATOR_URL}`);
  console.log(`Token Throttle: ${DESKTOP_RATE_LIMIT_ITPM} tokens/min`);
  console.log(`Redis: ${redisClient ? 'Enabled' : 'Disabled'}`);
  console.log('='.repeat(60));
  console.log('');
  console.log('Available endpoints:');
  console.log('  GET  /health - Health check');
  console.log('  POST /mcp/initialize - Initialize MCP connection');
  console.log('  GET  /mcp/tools - List available tools');
  console.log('  POST /mcp/execute - Execute a tool');
  console.log('  POST /mcp/chat - Send message to Cortex');
  console.log('  GET  /mcp/prompts - List available prompts');
  console.log('  GET  /mcp/resources - List available resources');
  console.log('='.repeat(60));
});
