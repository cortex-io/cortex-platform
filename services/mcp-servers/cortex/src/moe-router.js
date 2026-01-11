/**
 * MoE (Mixture of Experts) Router for Cortex
 * Intelligently routes queries to the correct subsystem based on keywords/intent
 */

const MOE_ROUTES = {
  unifi: {
    keywords: [
      'unifi', 'network', 'wifi', 'wireless', 'ssid', 'access point', 'ap',
      'client', 'device connected', 'bandwidth', 'switch', 'port', 'vlan'
    ],
    system: 'unifi',
    priority: 100
  },
  proxmox: {
    keywords: [
      'proxmox', 'vm', 'virtual machine', 'container', 'lxc', 'pve',
      'hypervisor', 'node resource', 'vcpu', 'memory', 'disk', 'snapshot'
    ],
    system: 'proxmox',
    priority: 100
  },
  sandfly: {
    keywords: [
      'sandfly', 'security', 'alert', 'vulnerability', 'threat', 'compliance',
      'cve', 'intrusion', 'siem', 'log', 'agent', 'malware'
    ],
    system: 'sandfly',
    priority: 100
  },
  checkmk: {
    keywords: [
      'checkmk', 'monitoring', 'host', 'service', 'alert', 'problem',
      'status', 'health', 'metric', 'check', 'cmk', 'up', 'down'
    ],
    system: 'checkmk',
    priority: 100
  },
  kubernetes: {
    keywords: [
      'k8s', 'kubernetes', 'pod', 'deployment', 'service', 'namespace',
      'kubectl', 'container', 'cluster', 'helm', 'ingress', 'configmap',
      'node', 'replica', 'logs'
    ],
    system: 'k8s',
    priority: 50
  },
  n8n: {
    keywords: [
      'n8n', 'workflow', 'automation', 'trigger', 'execute', 'integration',
      'automate', 'orchestration', 'webhook', 'flow'
    ],
    system: 'n8n',
    priority: 100
  }
};

/**
 * Analyze query and route to best subsystem
 * @param {string} query - The user's query
 * @returns {Object} Routing decision with confidence score
 */
export function routeQuery(query) {
  const lowerQuery = query.toLowerCase();
  const scores = {};

  // Score each route
  for (const [name, route] of Object.entries(MOE_ROUTES)) {
    let score = 0;
    const matchedKeywords = [];

    for (const keyword of route.keywords) {
      if (lowerQuery.includes(keyword)) {
        score += route.priority;
        matchedKeywords.push(keyword);
      }
    }

    if (score > 0) {
      scores[name] = {
        system: route.system,
        score,
        confidence: Math.min(score / 100, 1.0),
        matchedKeywords
      };
    }
  }

  // Find highest scoring route
  const routes = Object.entries(scores).sort((a, b) => b[1].score - a[1].score);

  if (routes.length === 0) {
    return {
      system: null,
      confidence: 0,
      reason: 'No matching routes found - will require manual system selection'
    };
  }

  const [topName, topRoute] = routes[0];

  return {
    system: topRoute.system,
    confidence: topRoute.confidence,
    reason: `Matched keywords: ${topRoute.matchedKeywords.join(', ')}`,
    allMatches: routes.map(([name, r]) => ({
      name,
      system: r.system,
      confidence: r.confidence,
      keywords: r.matchedKeywords
    }))
  };
}

/**
 * Get routing suggestion with confidence level
 * @param {string} query - The user's query
 * @returns {Object} Routing suggestion
 */
export function getRoutingSuggestion(query) {
  const routing = routeQuery(query);

  // High confidence (>=1.0) - Force route
  if (routing.confidence >= 1.0 && routing.system) {
    return {
      action: 'force',
      system: routing.system,
      confidence: routing.confidence,
      reason: routing.reason
    };
  }

  // Moderate confidence (0.5-0.99) - Suggest route
  if (routing.confidence >= 0.5 && routing.system) {
    return {
      action: 'suggest',
      system: routing.system,
      confidence: routing.confidence,
      reason: routing.reason
    };
  }

  // Low confidence - No suggestion
  return {
    action: 'none',
    system: null,
    confidence: routing.confidence,
    reason: routing.reason
  };
}

export { MOE_ROUTES };
