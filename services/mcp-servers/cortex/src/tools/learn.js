/**
 * Cortex Learn Today Tool
 * Get what Cortex learned from YouTube videos in the last N hours
 */

import axios from 'axios';

const COORDINATOR_URL = process.env.COORDINATOR_URL || 'http://school-coordinator.cortex-school.svc.cluster.local:8080';

/**
 * Tool definition for MCP
 */
export const cortexLearnTodayTool = {
  name: 'cortex_learn_today',
  description: 'Get what Cortex learned today from YouTube videos. Returns videos watched, improvements identified, what was auto-approved vs pending review, and what was implemented.',
  inputSchema: {
    type: 'object',
    properties: {
      hours: {
        type: 'number',
        description: 'Number of hours to look back (default: 24)',
        default: 24
      }
    },
    required: []
  }
};

/**
 * Execute the cortex_learn_today tool
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Learning summary
 */
export async function executeCortexLearnToday(args = {}) {
  const hours = args.hours || 24;

  console.log(`[Cortex Learn] Fetching learning summary for last ${hours} hours...`);

  try {
    const response = await axios.get(`${COORDINATOR_URL}/learn/today`, {
      params: { hours },
      timeout: 30000
    });

    const data = response.data;

    // Format a human-readable summary
    const summary = formatLearningSummary(data, hours);

    console.log('[Cortex Learn] Summary retrieved successfully');

    return {
      success: true,
      summary,
      raw_data: data
    };
  } catch (error) {
    console.error(`[Cortex Learn] Error: ${error.message}`);

    // If coordinator is unavailable, try to get data directly from Redis
    return await getLearningSummaryFromRedis(hours);
  }
}

/**
 * Format learning data into a human-readable summary
 */
function formatLearningSummary(data, hours) {
  const { summary, sources, recent_improvements } = data;

  let output = `## What Cortex Learned (Last ${hours} Hours)\n\n`;

  // Summary stats
  output += `### Summary\n`;
  output += `- **Total Improvements Identified**: ${summary.total_improvements}\n`;
  output += `- **Auto-Approved**: ${summary.auto_approved}\n`;
  output += `- **Pending Human Review**: ${summary.pending_review}\n`;
  output += `- **Average Relevance Score**: ${(summary.average_relevance * 100).toFixed(1)}%\n\n`;

  // Categories breakdown
  if (summary.categories && Object.keys(summary.categories).length > 0) {
    output += `### Categories\n`;
    for (const [category, count] of Object.entries(summary.categories)) {
      output += `- ${category}: ${count}\n`;
    }
    output += '\n';
  }

  // Video sources
  if (sources && Object.keys(sources).length > 0) {
    output += `### Videos Watched\n`;
    for (const [title, info] of Object.entries(sources)) {
      output += `- **${title}**\n`;
      output += `  - Improvements: ${info.improvements}\n`;
      output += `  - Relevance: ${(info.relevance * 100).toFixed(1)}%\n`;
    }
    output += '\n';
  }

  // Recent approved improvements
  if (recent_improvements?.approved?.length > 0) {
    output += `### Recently Implemented\n`;
    for (const imp of recent_improvements.approved.slice(0, 5)) {
      output += `- **${imp.title}** (${imp.category}) - ${(imp.relevance * 100).toFixed(1)}% relevance\n`;
    }
    output += '\n';
  }

  // Pending review
  if (recent_improvements?.pending_review?.length > 0) {
    output += `### Pending Your Review\n`;
    for (const imp of recent_improvements.pending_review.slice(0, 5)) {
      output += `- **${imp.title}** (${imp.category}) - ${(imp.relevance * 100).toFixed(1)}% relevance\n`;
    }
    output += '\n';
  }

  return output;
}

/**
 * Fallback: Get learning summary directly from Redis if coordinator is unavailable
 */
async function getLearningSummaryFromRedis(hours) {
  try {
    // This is a simplified fallback - would need Redis client
    return {
      success: false,
      error: 'Coordinator service unavailable',
      suggestion: 'Check if school-coordinator is running: kubectl get pods -n cortex-school'
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}
