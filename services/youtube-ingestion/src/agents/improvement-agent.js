/**
 * Self-Improvement Agent
 * Analyzes ingested knowledge and proposes improvements to Cortex
 */

import axios from 'axios';
import { config } from '../config.js';

export class ImprovementAgent {
  constructor(knowledgeStore) {
    this.knowledgeStore = knowledgeStore;
    this.apiKey = config.anthropic.apiKey;
    this.model = config.anthropic.model;
  }

  /**
   * Analyze a single video for improvement opportunities
   * @param {Object} knowledge - Processed video knowledge
   * @returns {Promise<Object>}
   */
  async analyzeVideo(knowledge) {
    const { relevance_to_cortex, actionable_items } = knowledge;

    // Skip if relevance is too low
    if (relevance_to_cortex < config.improvement.minRelevanceScore) {
      return {
        video_id: knowledge.video_id,
        skip_reason: 'low_relevance',
        improvements: []
      };
    }

    console.log(`[ImprovementAgent] Analyzing video: ${knowledge.title}`);

    const improvements = {
      passive: [],
      active: []
    };

    // Process actionable items
    for (const item of actionable_items) {
      const improvement = await this.evaluateActionableItem(item, knowledge);

      if (improvement.auto_approve || relevance_to_cortex >= config.improvement.autoApproveThreshold) {
        improvements.passive.push(improvement);
      } else {
        improvements.active.push(improvement);
      }
    }

    return {
      video_id: knowledge.video_id,
      title: knowledge.title,
      relevance: relevance_to_cortex,
      improvements
    };
  }

  /**
   * Evaluate an actionable item
   * @private
   */
  async evaluateActionableItem(item, knowledge) {
    const { type, description, implementation_notes } = item;

    // Determine improvement category
    let category;
    let auto_approve = false;

    switch (type) {
      case 'tool':
        category = 'integration';
        auto_approve = false; // Tools require review
        break;

      case 'technique':
        category = 'capability';
        auto_approve = true; // Techniques can be auto-added to knowledge
        break;

      case 'pattern':
        category = 'architecture';
        auto_approve = true;
        break;

      case 'integration':
        category = 'integration';
        auto_approve = false;
        break;

      default:
        category = 'knowledge';
        auto_approve = true;
    }

    return {
      category,
      type,
      description,
      implementation_notes,
      source_video: knowledge.video_id,
      source_title: knowledge.title,
      auto_approve,
      proposed_at: new Date().toISOString(),
      status: auto_approve ? 'approved' : 'pending'
    };
  }

  /**
   * Perform meta-review of accumulated knowledge
   * @param {Object} options - Review options
   * @returns {Promise<Object>}
   */
  async performMetaReview(options = {}) {
    const {
      minVideos = config.improvement.minVideosForPattern,
      lookbackDays = 30
    } = options;

    console.log('[ImprovementAgent] Performing meta-review of accumulated knowledge...');

    // Get recent videos
    const allKnowledge = await this.knowledgeStore.listAll(100);

    // Filter to recent and relevant
    const cutoffDate = new Date(Date.now() - (lookbackDays * 24 * 60 * 60 * 1000));
    const recentKnowledge = allKnowledge.filter(k => {
      const ingestedDate = new Date(k.ingested_at);
      return ingestedDate >= cutoffDate && k.relevance_to_cortex >= config.improvement.minRelevanceScore;
    });

    if (recentKnowledge.length < minVideos) {
      return {
        status: 'insufficient_data',
        videos_analyzed: recentKnowledge.length,
        min_required: minVideos,
        recommendations: []
      };
    }

    // Analyze patterns
    const analysis = await this.analyzePatterns(recentKnowledge);

    return {
      status: 'complete',
      videos_analyzed: recentKnowledge.length,
      period_days: lookbackDays,
      analysis,
      generated_at: new Date().toISOString()
    };
  }

  /**
   * Analyze patterns across multiple videos
   * @private
   */
  async analyzePatterns(knowledgeSet) {
    console.log(`[ImprovementAgent] Analyzing patterns across ${knowledgeSet.length} videos`);

    // Aggregate data
    const toolMentions = {};
    const conceptFrequency = {};
    const categories = {};

    for (const knowledge of knowledgeSet) {
      // Count tool mentions
      for (const tool of knowledge.tools_mentioned || []) {
        toolMentions[tool] = (toolMentions[tool] || 0) + 1;
      }

      // Count concept frequency
      for (const concept of knowledge.key_concepts || []) {
        conceptFrequency[concept] = (conceptFrequency[concept] || 0) + 1;
      }

      // Count categories
      categories[knowledge.category] = (categories[knowledge.category] || 0) + 1;
    }

    // Use Claude to generate insights
    const insights = await this.generateInsights({
      toolMentions,
      conceptFrequency,
      categories,
      videoCount: knowledgeSet.length
    });

    return {
      recurring_tools: this.getTopItems(toolMentions, 10),
      recurring_concepts: this.getTopItems(conceptFrequency, 10),
      category_distribution: categories,
      insights
    };
  }

  /**
   * Generate insights using Claude
   * @private
   */
  async generateInsights(data) {
    const prompt = `You are analyzing patterns in YouTube videos ingested by Cortex, an AI infrastructure management system.

DATA SUMMARY:
- Videos analyzed: ${data.videoCount}
- Top tools mentioned: ${JSON.stringify(this.getTopItems(data.toolMentions, 5))}
- Top concepts: ${JSON.stringify(this.getTopItems(data.conceptFrequency, 5))}
- Category distribution: ${JSON.stringify(data.categories)}

TASK:
Based on this data, provide actionable insights for improving Cortex:

1. RECURRING THEMES: What themes appear most often? Are they being prioritized correctly?

2. NEW INTEGRATIONS: What tools/services are mentioned frequently that Cortex should integrate with?

3. CAPABILITY GAPS: What techniques or patterns are discussed that Cortex should implement?

4. CONTRADICTIONS: Are there any conflicting recommendations or approaches?

5. PRIORITY RECOMMENDATIONS: What should be implemented first?

Return ONLY valid JSON in this format:
{
  "recurring_themes": [
    {
      "theme": "string",
      "frequency": "high|medium|low",
      "priority": "critical|high|medium|low"
    }
  ],
  "recommended_integrations": [
    {
      "tool": "string",
      "reason": "string",
      "effort": "low|medium|high",
      "priority": "critical|high|medium|low"
    }
  ],
  "capability_improvements": [
    {
      "capability": "string",
      "description": "string",
      "impact": "high|medium|low"
    }
  ],
  "contradictions": [
    {
      "issue": "string",
      "recommendation": "string"
    }
  ],
  "next_actions": [
    {
      "action": "string",
      "priority": "1|2|3|4|5"
    }
  ]
}`;

    try {
      const response = await axios.post(
        'https://api.anthropic.com/v1/messages',
        {
          model: this.model,
          max_tokens: 3072,
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

      return JSON.parse(response.data.content[0].text);
    } catch (error) {
      console.error(`[ImprovementAgent] Failed to generate insights: ${error.message}`);
      return {
        error: error.message,
        recurring_themes: [],
        recommended_integrations: [],
        capability_improvements: [],
        contradictions: [],
        next_actions: []
      };
    }
  }

  /**
   * Get top N items from frequency map
   * @private
   */
  getTopItems(frequencyMap, limit) {
    return Object.entries(frequencyMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([item, count]) => ({ item, count }));
  }

  /**
   * Generate improvement proposals
   * @param {Array} knowledgeSet
   * @returns {Promise<Array>}
   */
  async generateProposals(knowledgeSet) {
    const proposals = [];

    for (const knowledge of knowledgeSet) {
      const analysis = await this.analyzeVideo(knowledge);

      if (analysis.improvements.passive.length > 0 || analysis.improvements.active.length > 0) {
        proposals.push(analysis);
      }
    }

    return proposals;
  }
}

export default ImprovementAgent;
