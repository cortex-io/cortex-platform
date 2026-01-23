/**
 * Message Interceptor Middleware
 * To be integrated into cortex-chat backend
 * Automatically detects YouTube URLs in messages
 */

import axios from 'axios';

export class MessageInterceptor {
  constructor(ingestionServiceUrl) {
    this.serviceUrl = ingestionServiceUrl || 'http://youtube-ingestion.cortex.svc.cluster.local:8080';
  }

  /**
   * Intercept message and check for YouTube URLs
   * @param {string} message
   * @returns {Promise<Object>}
   */
  async intercept(message) {
    try {
      const response = await axios.post(
        `${this.serviceUrl}/process`,
        { message },
        { timeout: 5000 }
      );

      const { detected, count, videos } = response.data;

      if (detected) {
        return {
          detected: true,
          count,
          videos,
          userMessage: this.formatUserMessage(videos)
        };
      }

      return { detected: false };
    } catch (error) {
      console.error('[MessageInterceptor] Failed to process message:', error.message);
      return { detected: false, error: error.message };
    }
  }

  /**
   * Format user-facing message
   * @private
   */
  formatUserMessage(videos) {
    const messages = [];

    for (const video of videos) {
      if (video.status === 'ingested') {
        const { knowledge } = video;
        messages.push(
          `Detected YouTube video, extracting transcript...\n` +
          `Ingested: ${knowledge.title} - ${knowledge.category}\n` +
          `Relevance: ${(knowledge.relevance_to_cortex * 100).toFixed(0)}%`
        );
      } else if (video.status === 'already_exists') {
        messages.push(
          `YouTube video already in knowledge base: ${video.knowledge.title}`
        );
      } else if (video.status === 'failed') {
        messages.push(
          `Failed to ingest YouTube video: ${video.error}`
        );
      }
    }

    return messages.join('\n\n');
  }

  /**
   * Check if service is available
   * @returns {Promise<boolean>}
   */
  async isAvailable() {
    try {
      const response = await axios.get(`${this.serviceUrl}/health`, { timeout: 2000 });
      return response.data.status === 'healthy';
    } catch (error) {
      return false;
    }
  }
}

export default MessageInterceptor;

/**
 * Example integration for cortex-chat backend:
 *
 * import MessageInterceptor from './middleware/message-interceptor.js';
 *
 * const youtubeInterceptor = new MessageInterceptor();
 *
 * // In your message handler:
 * const interceptResult = await youtubeInterceptor.intercept(userMessage);
 * if (interceptResult.detected) {
 *   // Send notification to user
 *   sendToUser(interceptResult.userMessage);
 * }
 */
