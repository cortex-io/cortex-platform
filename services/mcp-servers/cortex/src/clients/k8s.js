/**
 * Kubernetes Client
 * Wrapper for kubectl commands
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

/**
 * Execute kubectl command
 * @param {string} command - kubectl command (without 'kubectl' prefix)
 * @param {Object} options - Execution options
 * @returns {Promise<Object>} Command result
 */
export async function executeKubectl(command, options = {}) {
  try {
    const { stdout, stderr } = await execAsync(`kubectl ${command}`, {
      timeout: options.timeout || 30000,
      maxBuffer: 1024 * 1024 * 10 // 10MB buffer
    });

    return {
      success: true,
      stdout: stdout.trim(),
      stderr: stderr.trim()
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      stdout: error.stdout?.trim() || '',
      stderr: error.stderr?.trim() || '',
      code: error.code
    };
  }
}

/**
 * Get cluster status
 * @returns {Promise<Object>} Cluster status
 */
export async function getClusterStatus() {
  const result = await executeKubectl('cluster-info');

  if (result.success) {
    return {
      healthy: true,
      info: result.stdout
    };
  }

  return {
    healthy: false,
    error: result.error
  };
}

/**
 * List pods in namespace
 * @param {string} namespace - Kubernetes namespace (default: all)
 * @returns {Promise<Object>} Pod list
 */
export async function listPods(namespace = 'all-namespaces') {
  const nsFlag = namespace === 'all-namespaces' ? '-A' : `-n ${namespace}`;
  const result = await executeKubectl(`get pods ${nsFlag} -o json`);

  if (result.success) {
    try {
      const data = JSON.parse(result.stdout);
      return {
        success: true,
        pods: data.items || []
      };
    } catch (error) {
      return {
        success: false,
        error: 'Failed to parse kubectl output'
      };
    }
  }

  return result;
}

/**
 * Get resource details
 * @param {string} resourceType - Type of resource (pod, deployment, service, etc.)
 * @param {string} name - Resource name
 * @param {string} namespace - Namespace
 * @returns {Promise<Object>} Resource details
 */
export async function getResource(resourceType, name, namespace = 'default') {
  const result = await executeKubectl(`get ${resourceType} ${name} -n ${namespace} -o json`);

  if (result.success) {
    try {
      const data = JSON.parse(result.stdout);
      return {
        success: true,
        resource: data
      };
    } catch (error) {
      return {
        success: false,
        error: 'Failed to parse kubectl output'
      };
    }
  }

  return result;
}

/**
 * Query Kubernetes with natural language (basic implementation)
 * @param {string} query - Natural language query
 * @returns {Promise<Object>} Query result
 */
export async function queryKubernetes(query) {
  const lowerQuery = query.toLowerCase();

  // Simple keyword-based command routing
  if (lowerQuery.includes('pod')) {
    return listPods();
  } else if (lowerQuery.includes('cluster') || lowerQuery.includes('status')) {
    return getClusterStatus();
  } else {
    // Default: get cluster info
    return executeKubectl('get all -A');
  }
}

/**
 * Check Kubernetes cluster health
 * @returns {Promise<Object>} Health status
 */
export async function checkK8sHealth() {
  const result = await getClusterStatus();
  return {
    healthy: result.healthy,
    status: result.info || result.error
  };
}
