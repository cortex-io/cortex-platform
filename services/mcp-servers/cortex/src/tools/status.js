/**
 * Cortex Status Tool
 * Get real-time operational status of all Cortex systems
 */

import { checkUniFiHealth } from '../clients/unifi.js';
import { checkProxmoxHealth } from '../clients/proxmox.js';
import { checkSandflyHealth } from '../clients/sandfly.js';
import { checkK8sHealth } from '../clients/kubernetes.js';
import { checkN8nHealth } from '../clients/n8n.js';
import { checkSchoolHealth } from '../clients/school.js';
import { checkYoutubeHealth } from '../clients/youtube.js';
import { readFile } from 'fs/promises';
import { existsSync } from 'fs';

/**
 * Tool definition for MCP
 */
export const cortexGetStatusTool = {
  name: 'cortex_get_status',
  description: 'Get real-time status of all Cortex operations including MCP servers, active workers, masters, and running tasks',
  inputSchema: {
    type: 'object',
    properties: {},
    required: []
  }
};

/**
 * Get active workers from coordination directory
 * @returns {Promise<Array>} List of active workers
 */
async function getActiveWorkers() {
  try {
    const coordPath = '/Users/ryandahlberg/cortex/coordination';

    // Check development master state
    const devStatePath = `${coordPath}/masters/development/context/master-state.json`;
    if (existsSync(devStatePath)) {
      const devState = JSON.parse(await readFile(devStatePath, 'utf-8'));
      return devState.active_workers || [];
    }

    return [];
  } catch (error) {
    return [];
  }
}

/**
 * Get active masters
 * @returns {Promise<Array>} List of active masters
 */
async function getActiveMasters() {
  const masters = [];
  const coordPath = '/Users/ryandahlberg/cortex/coordination';

  try {
    const masterTypes = ['development', 'security', 'inventory', 'cicd'];

    for (const type of masterTypes) {
      const statePath = `${coordPath}/masters/${type}/context/master-state.json`;
      if (existsSync(statePath)) {
        const state = JSON.parse(await readFile(statePath, 'utf-8'));
        if (state.session_id) {
          masters.push({
            type,
            session_id: state.session_id,
            started_at: state.started_at
          });
        }
      }
    }

    return masters;
  } catch (error) {
    return [];
  }
}

/**
 * Get running tasks
 * @returns {Promise<Array>} List of running tasks
 */
async function getRunningTasks() {
  try {
    const coordPath = '/Users/ryandahlberg/cortex/coordination';
    const tasksPath = `${coordPath}/tasks`;

    if (!existsSync(tasksPath)) {
      return [];
    }

    // This is a simplified version - in production, would scan task files
    return [];
  } catch (error) {
    return [];
  }
}

/**
 * Execute the cortex_get_status tool
 * @returns {Promise<Object>} System status
 */
export async function executeCortexGetStatus() {
  console.log('[Cortex Status] Checking all subsystems...');

  // Check all MCP servers in parallel
  const [unifiHealth, proxmoxHealth, sandflyHealth, k8sHealth, n8nHealth, schoolHealth, youtubeHealth, activeWorkers, activeMasters, runningTasks] = await Promise.all([
    checkUniFiHealth(),
    checkProxmoxHealth(),
    checkSandflyHealth(),
    checkK8sHealth(),
    checkN8nHealth(),
    checkSchoolHealth(),
    checkYoutubeHealth(),
    getActiveWorkers(),
    getActiveMasters(),
    getRunningTasks()
  ]);

  const status = {
    timestamp: new Date().toISOString(),
    mcp_servers: {
      unifi: unifiHealth.healthy ? 'healthy' : 'unhealthy',
      proxmox: proxmoxHealth.healthy ? 'healthy' : 'unhealthy',
      sandfly: sandflyHealth.healthy ? 'healthy' : 'unhealthy',
      k8s: k8sHealth.healthy ? 'healthy' : 'unhealthy',
      n8n: n8nHealth.healthy ? 'healthy' : 'unhealthy',
      school: schoolHealth.healthy ? 'healthy' : 'unhealthy',
      youtube: youtubeHealth.healthy ? 'healthy' : 'unhealthy'
    },
    mcp_server_details: {
      unifi: unifiHealth,
      proxmox: proxmoxHealth,
      sandfly: sandflyHealth,
      k8s: k8sHealth,
      n8n: n8nHealth,
      school: schoolHealth,
      youtube: youtubeHealth
    },
    cortex_operations: {
      active_workers: activeWorkers.length,
      active_masters: activeMasters.length,
      running_tasks: runningTasks.length
    },
    details: {
      active_workers: activeWorkers,
      active_masters: activeMasters,
      running_tasks: runningTasks
    },
    overall_health: determineOverallHealth({
      unifiHealth,
      proxmoxHealth,
      sandflyHealth,
      k8sHealth,
      n8nHealth,
      schoolHealth,
      youtubeHealth
    })
  };

  console.log('[Cortex Status] Status check complete');
  console.log(`  - MCP Servers: UniFi=${status.mcp_servers.unifi}, Proxmox=${status.mcp_servers.proxmox}, Sandfly=${status.mcp_servers.sandfly}, K8s=${status.mcp_servers.k8s}, n8n=${status.mcp_servers.n8n}, School=${status.mcp_servers.school}, YouTube=${status.mcp_servers.youtube}`);
  console.log(`  - Operations: ${activeWorkers.length} workers, ${activeMasters.length} masters, ${runningTasks.length} tasks`);

  return {
    success: true,
    status
  };
}

/**
 * Determine overall system health
 * @param {Object} healthChecks - Individual health check results
 * @returns {string} Overall health status
 */
function determineOverallHealth(healthChecks) {
  const { unifiHealth, proxmoxHealth, sandflyHealth, k8sHealth, n8nHealth, schoolHealth, youtubeHealth } = healthChecks;

  const healthyCount = [unifiHealth, proxmoxHealth, sandflyHealth, k8sHealth, n8nHealth, schoolHealth, youtubeHealth]
    .filter(h => h.healthy).length;

  if (healthyCount === 7) return 'healthy';
  if (healthyCount >= 4) return 'degraded';
  return 'unhealthy';
}
