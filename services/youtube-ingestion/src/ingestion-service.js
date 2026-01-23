/**
 * YouTube Ingestion Service
 * Main orchestrator for the ingestion pipeline
 */

import URLDetector from './utils/url-detector.js';
import TranscriptExtractor from './extractors/transcript-extractor.js';
import MetadataExtractor from './extractors/metadata-extractor.js';
import ContentClassifier from './processors/classifier.js';
import KnowledgeStore from './storage/knowledge-store.js';
import ImprovementAgent from './agents/improvement-agent.js';
import { config } from './config.js';

export class IngestionService {
  constructor(redisClient = null) {
    this.urlDetector = new URLDetector();
    this.transcriptExtractor = new TranscriptExtractor();
    this.metadataExtractor = new MetadataExtractor();
    this.classifier = new ContentClassifier();
    this.knowledgeStore = new KnowledgeStore(redisClient);
    this.improvementAgent = new ImprovementAgent(this.knowledgeStore);
    this.redis = redisClient;
  }

  /**
   * Initialize the service
   */
  async initialize() {
    console.log('[IngestionService] Initializing...');
    await this.knowledgeStore.initialize();
    console.log('[IngestionService] Ready');
  }

  /**
   * Process a message and detect YouTube URLs
   * @param {string} message
   * @returns {Promise<Array>}
   */
  async processMessage(message) {
    console.log('[IngestionService] Processing message for YouTube URLs');

    const detectedURLs = this.urlDetector.detect(message);

    if (detectedURLs.length === 0) {
      return {
        detected: false,
        videos: []
      };
    }

    console.log(`[IngestionService] Detected ${detectedURLs.length} YouTube URL(s)`);

    const results = [];

    for (const { url, videoId } of detectedURLs) {
      try {
        // Always re-process videos (no caching)
        console.log(`[IngestionService] Processing video: ${videoId}`);

        // Ingest the video
        const knowledge = await this.ingestVideo(videoId);

        results.push({
          videoId,
          url,
          status: 'ingested',
          knowledge
        });
      } catch (error) {
        console.error(`[IngestionService] Failed to ingest ${videoId}: ${error.message}`);
        results.push({
          videoId,
          url,
          status: 'failed',
          error: error.message
        });
      }
    }

    return {
      detected: true,
      count: detectedURLs.length,
      videos: results
    };
  }

  /**
   * Ingest a single YouTube video
   * @param {string} videoId
   * @returns {Promise<Object>}
   */
  async ingestVideo(videoId) {
    console.log(`[IngestionService] Starting ingestion for video: ${videoId}`);

    const startTime = Date.now();

    // Step 1: Extract metadata
    console.log('[IngestionService] STEP 1/4: Extracting metadata...');
    const metadata = await this.metadataExtractor.extract(videoId);

    // Step 2: Extract transcript
    console.log('[IngestionService] STEP 2/4: Extracting transcript...');
    const transcript = await this.transcriptExtractor.extract(videoId);

    // Step 3: Classify content
    console.log('[IngestionService] STEP 3/4: Classifying content...');
    const classification = await this.classifier.classify({
      title: metadata.title,
      description: metadata.description,
      rawText: transcript.rawText,
      channelName: metadata.channelName
    });

    // Step 4: Synthesize knowledge
    console.log('[IngestionService] STEP 4/4: Synthesizing knowledge...');
    const knowledge = this.synthesizeKnowledge(
      videoId,
      metadata,
      transcript,
      classification
    );

    // Store knowledge
    await this.knowledgeStore.store(knowledge);

    // Analyze for improvements (async, don't wait)
    this.analyzeForImprovements(knowledge).catch(error => {
      console.error(`[IngestionService] Improvement analysis failed: ${error.message}`);
    });

    const duration = Date.now() - startTime;
    console.log(`[IngestionService] Ingestion complete in ${duration}ms`);

    return knowledge;
  }

  /**
   * Synthesize knowledge from extracted data
   * @private
   */
  synthesizeKnowledge(videoId, metadata, transcript, classification) {
    return {
      video_id: videoId,
      url: `https://www.youtube.com/watch?v=${videoId}`,
      title: metadata.title,
      channel_name: metadata.channelName,
      description: metadata.description,
      duration: metadata.duration,
      upload_date: metadata.uploadDate,
      thumbnail_url: metadata.thumbnailUrl,

      category: classification.category,
      relevance_to_cortex: classification.relevance_to_cortex,
      summary: classification.summary,
      key_concepts: classification.key_concepts || [],
      actionable_items: classification.actionable_items || [],
      tools_mentioned: classification.tools_mentioned || [],
      tags: classification.tags || [],

      transcript: {
        language: transcript.language,
        word_count: transcript.wordCount,
        has_timestamps: transcript.hasTimestamps,
        segments: transcript.segments
      },

      raw_transcript: transcript.rawText,

      ingested_at: new Date().toISOString(),
      metadata_extracted_at: metadata.extractedAt,
      transcript_extracted_at: transcript.extractedAt
    };
  }

  /**
   * Analyze knowledge for improvement opportunities
   * @private
   */
  async analyzeForImprovements(knowledge) {
    console.log('[IngestionService] Analyzing for improvements...');

    const analysis = await this.improvementAgent.analyzeVideo(knowledge);

    // Store improvement proposals in Redis
    if (this.redis && (analysis.improvements.passive.length > 0 || analysis.improvements.active.length > 0)) {
      await this.redis.lpush(
        'youtube:improvements',
        JSON.stringify(analysis)
      );

      console.log(`[IngestionService] Stored ${analysis.improvements.passive.length} passive and ${analysis.improvements.active.length} active improvements`);
    }
  }

  /**
   * Get ingestion statistics
   * @returns {Promise<Object>}
   */
  async getStats() {
    return await this.knowledgeStore.getStats();
  }

  /**
   * Search the knowledge base
   * @param {Object} query
   * @returns {Promise<Array>}
   */
  async search(query) {
    return await this.knowledgeStore.search(query);
  }

  /**
   * List all ingested videos
   * @param {number} limit
   * @returns {Promise<Array>}
   */
  async listAll(limit = 100) {
    return await this.knowledgeStore.listAll(limit);
  }

  /**
   * Perform meta-review
   * @param {Object} options
   * @returns {Promise<Object>}
   */
  async performMetaReview(options = {}) {
    return await this.improvementAgent.performMetaReview(options);
  }

  /**
   * Get pending improvements
   * @returns {Promise<Array>}
   */
  async getPendingImprovements() {
    if (!this.redis) {
      return [];
    }

    const improvements = await this.redis.lrange('youtube:improvements', 0, -1);
    return improvements.map(item => JSON.parse(item));
  }
}

export default IngestionService;
