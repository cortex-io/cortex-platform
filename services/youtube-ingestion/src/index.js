#!/usr/bin/env node
/**
 * YouTube Ingestion Service
 * HTTP API for YouTube transcript ingestion and knowledge management
 */

import http from 'http';
import Redis from 'ioredis';
import IngestionService from './ingestion-service.js';
import { config } from './config.js';

const PORT = config.port;

// Initialize Redis
let redisClient = null;
if (config.redis.enabled) {
  redisClient = new Redis({
    host: config.redis.host,
    port: config.redis.port,
    maxRetriesPerRequest: 3,
    retryStrategy(times) {
      const delay = Math.min(times * 50, 2000);
      return delay;
    },
    lazyConnect: true
  });

  redisClient.on('error', (error) => {
    console.error('[Redis] Connection error:', error.message);
  });

  redisClient.on('connect', () => {
    console.log('[Redis] Connected successfully');
  });

  // Connect to Redis
  await redisClient.connect().catch(err => {
    console.error('[Redis] Failed to connect:', err.message);
    console.log('[Redis] Continuing without Redis');
    redisClient = null;
  });
}

// Initialize ingestion service
const ingestionService = new IngestionService(redisClient);
await ingestionService.initialize();

/**
 * Parse request body
 */
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(new Error('Invalid JSON'));
      }
    });
    req.on('error', reject);
  });
}

/**
 * Send JSON response
 */
function sendJSON(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data, null, 2));
}

/**
 * Handle requests
 */
async function handleRequest(req, res) {
  const { method, url } = req;

  console.log(`[API] ${method} ${url}`);

  // Health check
  if (method === 'GET' && url === '/health') {
    return sendJSON(res, 200, {
      status: 'healthy',
      service: 'youtube-ingestion',
      redis_connected: redisClient !== null
    });
  }

  // Stats endpoint
  if (method === 'GET' && url === '/stats') {
    try {
      const stats = await ingestionService.getStats();
      return sendJSON(res, 200, stats);
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // List all videos
  if (method === 'GET' && url.startsWith('/videos')) {
    try {
      const urlParams = new URL(url, `http://localhost:${PORT}`);
      const limit = parseInt(urlParams.searchParams.get('limit') || '100');

      const videos = await ingestionService.listAll(limit);
      return sendJSON(res, 200, {
        count: videos.length,
        videos
      });
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // Get specific video
  if (method === 'GET' && url.startsWith('/video/')) {
    try {
      const videoId = url.split('/video/')[1];
      const knowledge = await ingestionService.knowledgeStore.retrieve(videoId);

      if (!knowledge) {
        return sendJSON(res, 404, { error: 'Video not found' });
      }

      return sendJSON(res, 200, knowledge);
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // Search videos
  if (method === 'POST' && url === '/search') {
    try {
      const query = await parseBody(req);
      const results = await ingestionService.search(query);

      return sendJSON(res, 200, {
        count: results.length,
        results
      });
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // Process message (detect and ingest)
  if (method === 'POST' && url === '/process') {
    try {
      const { message } = await parseBody(req);

      if (!message) {
        return sendJSON(res, 400, { error: 'Missing message field' });
      }

      const result = await ingestionService.processMessage(message);

      return sendJSON(res, 200, result);
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // Manually ingest a video
  if (method === 'POST' && url === '/ingest') {
    try {
      const { url: videoUrl, videoId } = await parseBody(req);

      let id = videoId;
      if (videoUrl && !id) {
        id = ingestionService.urlDetector.extractVideoId(videoUrl);
      }

      if (!id) {
        return sendJSON(res, 400, { error: 'Missing videoId or url' });
      }

      const knowledge = await ingestionService.ingestVideo(id);

      return sendJSON(res, 200, {
        status: 'success',
        videoId: id,
        knowledge
      });
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // Meta-review endpoint
  if (method === 'POST' && url === '/meta-review') {
    try {
      const options = await parseBody(req);
      const review = await ingestionService.performMetaReview(options);

      return sendJSON(res, 200, review);
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // Get pending improvements
  if (method === 'GET' && url === '/improvements') {
    try {
      const improvements = await ingestionService.getPendingImprovements();

      return sendJSON(res, 200, {
        count: improvements.length,
        improvements
      });
    } catch (error) {
      return sendJSON(res, 500, { error: error.message });
    }
  }

  // 404
  return sendJSON(res, 404, {
    error: 'Not found',
    available_endpoints: [
      'GET /health',
      'GET /stats',
      'GET /videos?limit=100',
      'GET /video/:videoId',
      'POST /search',
      'POST /process',
      'POST /ingest',
      'POST /meta-review',
      'GET /improvements'
    ]
  });
}

// Create HTTP server
const server = http.createServer(handleRequest);

server.listen(PORT, () => {
  console.log(`[Server] YouTube Ingestion Service listening on port ${PORT}`);
  console.log(`[Server] Health check: http://localhost:${PORT}/health`);
  console.log(`[Server] Redis: ${redisClient ? 'Connected' : 'Disabled'}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[Server] SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('[Server] HTTP server closed');
  });

  if (redisClient) {
    await redisClient.quit();
    console.log('[Redis] Connection closed');
  }

  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('[Server] SIGINT received, shutting down gracefully');
  server.close(() => {
    console.log('[Server] HTTP server closed');
  });

  if (redisClient) {
    await redisClient.quit();
    console.log('[Redis] Connection closed');
  }

  process.exit(0);
});
