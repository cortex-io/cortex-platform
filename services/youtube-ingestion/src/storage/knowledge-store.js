/**
 * Knowledge Store
 * Manages storage and retrieval of processed video knowledge
 */

import fs from 'fs/promises';
import path from 'path';
import { config } from '../config.js';

export class KnowledgeStore {
  constructor(redisClient = null) {
    this.redis = redisClient;
    this.transcriptsDir = config.storage.transcriptsDir;
    this.knowledgeDir = config.storage.knowledgeDir;
    this.cacheDir = config.storage.cacheDir;
  }

  /**
   * Initialize storage directories
   */
  async initialize() {
    console.log('[KnowledgeStore] Initializing storage directories...');

    await fs.mkdir(this.transcriptsDir, { recursive: true });
    await fs.mkdir(this.knowledgeDir, { recursive: true });
    await fs.mkdir(this.cacheDir, { recursive: true });

    console.log('[KnowledgeStore] Storage initialized');
  }

  /**
   * Store processed video knowledge
   * @param {Object} knowledge - Complete processed video data
   */
  async store(knowledge) {
    const { video_id, title, category, relevance_to_cortex } = knowledge;

    console.log(`[KnowledgeStore] Storing knowledge for: ${video_id}`);

    // Store to filesystem
    const knowledgePath = path.join(this.knowledgeDir, `${video_id}.json`);
    await fs.writeFile(knowledgePath, JSON.stringify(knowledge, null, 2));

    // Store to Redis if available
    if (this.redis) {
      try {
        // Store full knowledge
        await this.redis.set(
          `youtube:knowledge:${video_id}`,
          JSON.stringify(knowledge),
          'EX',
          config.cache.transcriptTTL
        );

        // Add to category index
        await this.redis.sadd(`youtube:category:${category}`, video_id);

        // Add to relevance-sorted set
        await this.redis.zadd('youtube:by-relevance', relevance_to_cortex, video_id);

        // Add to chronological index
        await this.redis.zadd('youtube:by-date', Date.now(), video_id);

        // Store searchable metadata
        await this.redis.hset(`youtube:meta:${video_id}`, {
          title,
          category,
          relevance: relevance_to_cortex.toString(),
          ingested_at: knowledge.ingested_at
        });

        console.log(`[KnowledgeStore] Stored to Redis: ${video_id}`);
      } catch (error) {
        console.error(`[KnowledgeStore] Redis storage failed: ${error.message}`);
      }
    }

    console.log(`[KnowledgeStore] Knowledge stored: ${knowledgePath}`);
  }

  /**
   * Retrieve knowledge by video ID
   * @param {string} videoId
   * @returns {Promise<Object|null>}
   */
  async retrieve(videoId) {
    // Try Redis first
    if (this.redis) {
      try {
        const cached = await this.redis.get(`youtube:knowledge:${videoId}`);
        if (cached) {
          return JSON.parse(cached);
        }
      } catch (error) {
        console.error(`[KnowledgeStore] Redis retrieval failed: ${error.message}`);
      }
    }

    // Fallback to filesystem
    const knowledgePath = path.join(this.knowledgeDir, `${videoId}.json`);

    try {
      const data = await fs.readFile(knowledgePath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      if (error.code === 'ENOENT') {
        return null;
      }
      throw error;
    }
  }

  /**
   * Search knowledge base
   * @param {Object} query - Search criteria
   * @returns {Promise<Array>}
   */
  async search(query) {
    const { category, minRelevance, tags, limit = 50 } = query;

    console.log(`[KnowledgeStore] Searching with criteria:`, query);

    // If Redis available, use it for efficient search
    if (this.redis) {
      return await this.searchRedis(query);
    }

    // Fallback to filesystem search
    return await this.searchFilesystem(query);
  }

  /**
   * Search using Redis
   * @private
   */
  async searchRedis(query) {
    const { category, minRelevance = 0.0, tags = [], limit = 50 } = query;

    let videoIds = [];

    // Get by category
    if (category) {
      videoIds = await this.redis.smembers(`youtube:category:${category}`);
    } else {
      // Get all by relevance score
      videoIds = await this.redis.zrevrange('youtube:by-relevance', 0, -1);
    }

    // Filter by relevance
    if (minRelevance > 0.0) {
      const filtered = [];
      for (const videoId of videoIds) {
        const score = await this.redis.zscore('youtube:by-relevance', videoId);
        if (parseFloat(score) >= minRelevance) {
          filtered.push(videoId);
        }
      }
      videoIds = filtered;
    }

    // Limit results
    videoIds = videoIds.slice(0, limit);

    // Retrieve full knowledge for each
    const results = [];
    for (const videoId of videoIds) {
      const knowledge = await this.retrieve(videoId);
      if (knowledge) {
        results.push(knowledge);
      }
    }

    return results;
  }

  /**
   * Search using filesystem
   * @private
   */
  async searchFilesystem(query) {
    const { category, minRelevance = 0.0, tags = [], limit = 50 } = query;

    const files = await fs.readdir(this.knowledgeDir);
    const results = [];

    for (const file of files) {
      if (!file.endsWith('.json')) continue;

      const filePath = path.join(this.knowledgeDir, file);
      const data = await fs.readFile(filePath, 'utf8');
      const knowledge = JSON.parse(data);

      // Apply filters
      if (category && knowledge.category !== category) continue;
      if (knowledge.relevance_to_cortex < minRelevance) continue;

      if (tags.length > 0) {
        const hasTag = tags.some(tag => knowledge.tags.includes(tag));
        if (!hasTag) continue;
      }

      results.push(knowledge);

      if (results.length >= limit) break;
    }

    // Sort by relevance
    results.sort((a, b) => b.relevance_to_cortex - a.relevance_to_cortex);

    return results;
  }

  /**
   * Get statistics about stored knowledge
   * @returns {Promise<Object>}
   */
  async getStats() {
    const stats = {
      total: 0,
      by_category: {},
      avg_relevance: 0.0,
      recent_count: 0
    };

    if (this.redis) {
      try {
        stats.total = await this.redis.zcard('youtube:by-relevance');

        // Get category counts
        for (const category of config.categories) {
          const count = await this.redis.scard(`youtube:category:${category}`);
          if (count > 0) {
            stats.by_category[category] = count;
          }
        }

        // Calculate average relevance
        const allScores = await this.redis.zrange('youtube:by-relevance', 0, -1, 'WITHSCORES');
        if (allScores.length > 0) {
          const scores = allScores.filter((_, i) => i % 2 === 1).map(parseFloat);
          stats.avg_relevance = scores.reduce((a, b) => a + b, 0) / scores.length;
        }

        // Count recent (last 7 days)
        const weekAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
        stats.recent_count = await this.redis.zcount('youtube:by-date', weekAgo, Date.now());
      } catch (error) {
        console.error(`[KnowledgeStore] Stats retrieval failed: ${error.message}`);
      }
    } else {
      // Filesystem stats
      const files = await fs.readdir(this.knowledgeDir);
      stats.total = files.filter(f => f.endsWith('.json')).length;
    }

    return stats;
  }

  /**
   * List all ingested videos
   * @param {number} limit
   * @returns {Promise<Array>}
   */
  async listAll(limit = 100) {
    if (this.redis) {
      // Get most recent
      const videoIds = await this.redis.zrevrange('youtube:by-date', 0, limit - 1);
      const results = [];

      for (const videoId of videoIds) {
        const knowledge = await this.retrieve(videoId);
        if (knowledge) {
          results.push(knowledge);
        }
      }

      return results;
    }

    // Filesystem fallback
    const files = await fs.readdir(this.knowledgeDir);
    const results = [];

    for (const file of files.slice(0, limit)) {
      if (!file.endsWith('.json')) continue;

      const filePath = path.join(this.knowledgeDir, file);
      const data = await fs.readFile(filePath, 'utf8');
      results.push(JSON.parse(data));
    }

    // Sort by ingested date
    results.sort((a, b) => new Date(b.ingested_at) - new Date(a.ingested_at));

    return results;
  }
}

export default KnowledgeStore;
