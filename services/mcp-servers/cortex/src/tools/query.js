/**
 * Cortex Query Tool
 * Routes queries to appropriate subsystem using MoE routing
 */

import { routeQuery, getRoutingSuggestion } from '../moe-router.js';
import { queryUniFi } from '../clients/unifi.js';
import { queryProxmox } from '../clients/proxmox.js';
import { querySandfly } from '../clients/sandfly.js';
import { queryCheckMK } from '../clients/checkmk.js';
import { queryKubernetes } from '../clients/kubernetes.js';
import { queryN8n } from '../clients/n8n.js';
import { querySchool } from '../clients/school.js';
import { queryYoutube } from '../clients/youtube.js';

/**
 * Tool definition for MCP
 */
export const cortexQueryTool = {
  name: 'cortex_query',
  description: 'Query any Cortex subsystem (UniFi, Proxmox, Sandfly, CheckMK, Kubernetes, n8n, School, YouTube). Use auto routing for intelligent system selection based on query content.',
  inputSchema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Natural language query about infrastructure, security, network, monitoring, automation, content/knowledge, or video ingestion'
      },
      system: {
        type: 'string',
        enum: ['auto', 'unifi', 'proxmox', 'sandfly', 'checkmk', 'k8s', 'n8n', 'school', 'youtube'],
        description: 'Target system (auto = MoE intelligent routing)',
        default: 'auto'
      }
    },
    required: ['query']
  }
};

/**
 * Execute the cortex_query tool
 * @param {Object} args - Tool arguments
 * @returns {Promise<Object>} Query result
 */
export async function executeCortexQuery(args) {
  const { query, system = 'auto' } = args;

  let targetSystem = system;
  let routingInfo = null;

  // If auto mode, use MoE routing
  if (system === 'auto') {
    const suggestion = getRoutingSuggestion(query);
    routingInfo = suggestion;

    if (suggestion.system) {
      targetSystem = suggestion.system;
      console.log(`[Cortex Query] MoE Router: ${suggestion.action} routing to ${targetSystem} (confidence: ${suggestion.confidence})`);
      console.log(`[Cortex Query] Reason: ${suggestion.reason}`);
    } else {
      return {
        success: false,
        error: 'Could not determine target system from query',
        suggestion: 'Please specify system explicitly: unifi, proxmox, sandfly, checkmk, k8s, or n8n',
        routing_info: routingInfo
      };
    }
  }

  // Route to appropriate subsystem
  let result;
  try {
    switch (targetSystem) {
      case 'unifi':
        result = await queryUniFi(query);
        break;
      case 'proxmox':
        result = await queryProxmox(query);
        break;
      case 'sandfly':
        result = await querySandfly(query);
        break;
      case 'checkmk':
        result = await queryCheckMK(query);
        break;
      case 'k8s':
        result = await queryKubernetes(query);
        break;
      case 'n8n':
        result = await queryN8n(query);
        break;
      case 'school':
        result = await querySchool(query);
        break;
      case 'youtube':
        result = await queryYoutube(query);
        break;
      default:
        return {
          success: false,
          error: `Unknown system: ${targetSystem}`,
          valid_systems: ['unifi', 'proxmox', 'sandfly', 'checkmk', 'k8s', 'n8n', 'school', 'youtube']
        };
    }

    // Add routing metadata
    return {
      ...result,
      routing: {
        target_system: targetSystem,
        routing_mode: system === 'auto' ? 'automatic' : 'manual',
        routing_info: routingInfo
      }
    };
  } catch (error) {
    return {
      success: false,
      error: `Failed to query ${targetSystem}: ${error.message}`,
      target_system: targetSystem
    };
  }
}
