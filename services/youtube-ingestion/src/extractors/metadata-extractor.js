/**
 * Metadata Extractor
 * Extracts video metadata from YouTube
 */

import axios from 'axios';
import * as cheerio from 'cheerio';

export class MetadataExtractor {
  /**
   * Extract metadata for a YouTube video
   * @param {string} videoId
   * @returns {Promise<Object>}
   */
  async extract(videoId) {
    console.log(`[MetadataExtractor] Extracting metadata for video: ${videoId}`);

    try {
      const url = `https://www.youtube.com/watch?v=${videoId}`;
      const response = await axios.get(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      });

      const $ = cheerio.load(response.data);

      // Extract from meta tags
      const title = this.extractMetaContent($, 'name', 'title') ||
                    this.extractMetaContent($, 'property', 'og:title') ||
                    $('title').text().replace(' - YouTube', '');

      const description = this.extractMetaContent($, 'name', 'description') ||
                         this.extractMetaContent($, 'property', 'og:description') ||
                         '';

      const duration = this.extractMetaContent($, 'itemprop', 'duration') || '';
      const uploadDate = this.extractMetaContent($, 'itemprop', 'uploadDate') || '';
      const channelName = this.extractMetaContent($, 'itemprop', 'author') || '';

      // Try to extract from JSON-LD
      let jsonLdData = null;
      $('script[type="application/ld+json"]').each((i, elem) => {
        try {
          const data = JSON.parse($(elem).html());
          if (data['@type'] === 'VideoObject') {
            jsonLdData = data;
            return false; // break
          }
        } catch (e) {
          // Ignore parse errors
        }
      });

      return {
        videoId,
        url: `https://www.youtube.com/watch?v=${videoId}`,
        title: title || 'Unknown Title',
        description: description || '',
        channelName: channelName || (jsonLdData?.author?.name) || 'Unknown Channel',
        duration: duration || (jsonLdData?.duration) || '',
        uploadDate: uploadDate || (jsonLdData?.uploadDate) || '',
        thumbnailUrl: this.extractMetaContent($, 'property', 'og:image') ||
                      `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
        extractedAt: new Date().toISOString()
      };
    } catch (error) {
      console.error(`[MetadataExtractor] Failed to extract metadata: ${error.message}`);

      // Return minimal metadata
      return {
        videoId,
        url: `https://www.youtube.com/watch?v=${videoId}`,
        title: 'Unknown Title',
        description: '',
        channelName: 'Unknown Channel',
        duration: '',
        uploadDate: '',
        thumbnailUrl: `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
        extractedAt: new Date().toISOString(),
        error: error.message
      };
    }
  }

  /**
   * Extract content from meta tags
   * @private
   */
  extractMetaContent($, attr, value) {
    const element = $(`meta[${attr}="${value}"]`);
    return element.attr('content') || '';
  }

  /**
   * Parse ISO 8601 duration to seconds
   * @param {string} duration - ISO 8601 duration (e.g., PT1H2M3S)
   * @returns {number}
   */
  parseDuration(duration) {
    if (!duration) return 0;

    const match = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (!match) return 0;

    const hours = parseInt(match[1] || 0);
    const minutes = parseInt(match[2] || 0);
    const seconds = parseInt(match[3] || 0);

    return hours * 3600 + minutes * 60 + seconds;
  }

  /**
   * Format duration in seconds to human-readable string
   * @param {number} seconds
   * @returns {string}
   */
  formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
  }
}

export default MetadataExtractor;
