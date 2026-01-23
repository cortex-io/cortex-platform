/**
 * Content Classifier
 * Uses Claude to classify video content and determine relevance
 */

import axios from 'axios';
import { config } from '../config.js';

export class ContentClassifier {
  constructor() {
    this.apiKey = config.anthropic.apiKey;
    this.model = config.anthropic.model;
  }

  /**
   * Classify video content
   * @param {Object} videoData - Video metadata and transcript
   * @returns {Promise<Object>}
   */
  async classify(videoData) {
    const { title, description, rawText, channelName } = videoData;

    console.log(`[ContentClassifier] Classifying video: ${title}`);

    const prompt = this.buildClassificationPrompt(title, description, rawText, channelName);

    try {
      const response = await axios.post(
        'https://api.anthropic.com/v1/messages',
        {
          model: this.model,
          max_tokens: 2048,
          messages: [
            {
              role: 'user',
              content: prompt
            }
          ]
        },
        {
          headers: {
            'x-api-key': this.apiKey,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
          }
        }
      );

      const result = response.data.content[0].text;

      // Strip markdown code fences if present (more robust version)
      let cleanedResult = result.trim();
      if (cleanedResult.startsWith('```json')) {
        cleanedResult = cleanedResult.replace(/^```json\s*/, '').replace(/\s*```\s*$/, '');
      } else if (cleanedResult.startsWith('```')) {
        cleanedResult = cleanedResult.replace(/^```\s*/, '').replace(/\s*```\s*$/, '');
      }
      cleanedResult = cleanedResult.trim();

      // Parse JSON response
      const classification = JSON.parse(cleanedResult);

      console.log(`[ContentClassifier] Classification complete: ${classification.category} (relevance: ${classification.relevance_to_cortex})`);

      return classification;
    } catch (error) {
      console.error(`[ContentClassifier] Classification failed: ${error.message}`);

      // Return default classification
      return {
        category: 'other',
        relevance_to_cortex: 0.0,
        summary: 'Failed to classify content',
        key_concepts: [],
        actionable_items: [],
        tools_mentioned: [],
        tags: [],
        error: error.message
      };
    }
  }

  /**
   * Build classification prompt
   * @private
   */
  buildClassificationPrompt(title, description, transcript, channelName) {
    // Truncate transcript if too long (keep first 8000 words)
    const truncatedTranscript = this.truncateText(transcript, 8000);

    return `You are a content classifier for Cortex, an AI-powered infrastructure management system.

Analyze this YouTube video and provide a structured classification.

VIDEO INFORMATION:
Title: ${title}
Channel: ${channelName}
Description: ${description}

TRANSCRIPT:
${truncatedTranscript}

TASK:
Classify this video according to these criteria:

1. CATEGORY: Choose one from: tutorial, architecture, concept, tool-demo, discussion, code-walkthrough, conference-talk, lecture, review, other

2. RELEVANCE TO CORTEX (0.0-1.0):
   - 1.0: Directly applicable (AI agents, infrastructure automation, MCP, Claude, DevOps tools)
   - 0.7-0.9: Highly relevant (software architecture, system design, observability)
   - 0.4-0.6: Moderately relevant (programming techniques, cloud platforms)
   - 0.1-0.3: Tangentially relevant (general tech topics)
   - 0.0: Not relevant

3. SUMMARY: 2-3 sentence overview of the content

4. KEY CONCEPTS: List of main concepts/topics covered

5. ACTIONABLE ITEMS: Things Cortex could learn or implement
   Each item should have:
   - type: technique|tool|pattern|integration
   - description: What it is
   - implementation_notes: How it could be used

6. TOOLS MENTIONED: List of specific tools, libraries, or technologies mentioned

7. TAGS: Relevant tags for searchability

Return ONLY valid JSON in this exact format:
{
  "category": "string",
  "relevance_to_cortex": 0.0,
  "summary": "string",
  "key_concepts": ["string"],
  "actionable_items": [
    {
      "type": "technique|tool|pattern|integration",
      "description": "string",
      "implementation_notes": "string"
    }
  ],
  "tools_mentioned": ["string"],
  "tags": ["string"]
}`;
  }

  /**
   * Truncate text to max words
   * @private
   */
  truncateText(text, maxWords) {
    const words = text.split(/\s+/);
    if (words.length <= maxWords) {
      return text;
    }
    return words.slice(0, maxWords).join(' ') + '... [truncated]';
  }
}

export default ContentClassifier;
