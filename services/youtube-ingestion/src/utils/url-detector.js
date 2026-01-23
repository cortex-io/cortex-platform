/**
 * URL Detection Utility
 * Detects YouTube URLs in messages and extracts video IDs
 */

import { config } from '../config.js';

export class URLDetector {
  constructor() {
    this.patterns = config.urlPatterns;
  }

  /**
   * Detect YouTube URLs in a message
   * @param {string} message - The message to scan
   * @returns {Array<{url: string, videoId: string, position: number}>}
   */
  detect(message) {
    const results = [];

    for (const pattern of this.patterns) {
      const matches = [...message.matchAll(new RegExp(pattern, 'g'))];

      for (const match of matches) {
        const videoId = match[1];
        const url = match[0];
        const position = match.index;

        // Avoid duplicates
        if (!results.find(r => r.videoId === videoId)) {
          results.push({
            url,
            videoId,
            position,
            pattern: pattern.toString()
          });
        }
      }
    }

    return results;
  }

  /**
   * Check if message contains any YouTube URLs
   * @param {string} message
   * @returns {boolean}
   */
  hasYouTubeURL(message) {
    return this.patterns.some(pattern => pattern.test(message));
  }

  /**
   * Extract video ID from a URL
   * @param {string} url
   * @returns {string|null}
   */
  extractVideoId(url) {
    for (const pattern of this.patterns) {
      const match = url.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }
    return null;
  }

  /**
   * Normalize URL to standard watch format
   * @param {string} videoId
   * @returns {string}
   */
  normalizeURL(videoId) {
    return `https://www.youtube.com/watch?v=${videoId}`;
  }

  /**
   * Validate video ID format
   * @param {string} videoId
   * @returns {boolean}
   */
  isValidVideoId(videoId) {
    return /^[a-zA-Z0-9_-]{11}$/.test(videoId);
  }
}

export default URLDetector;
