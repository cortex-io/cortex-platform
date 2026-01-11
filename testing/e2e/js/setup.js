// Global setup for E2E tests with K3s

const { execSync } = require('child_process');
const axios = require('axios');

// Set test environment
process.env.NODE_ENV = 'test';
process.env.LOG_LEVEL = 'info';
process.env.K8S_NAMESPACE = 'cortex-test';

// Global test state
global.testNamespace = 'cortex-test';
global.testServices = {};

// Utility to execute kubectl commands
global.kubectl = (command, options = {}) => {
  const namespace = options.namespace || global.testNamespace;
  const fullCommand = `kubectl ${command} -n ${namespace}`;
  try {
    const result = execSync(fullCommand, {
      encoding: 'utf8',
      stdio: options.silent ? 'pipe' : 'inherit',
      ...options
    });
    return result;
  } catch (error) {
    console.error(`kubectl command failed: ${fullCommand}`, error.message);
    throw error;
  }
};

// Wait for a service to be ready
global.waitForService = async (serviceName, timeout = 120000) => {
  const startTime = Date.now();
  const interval = 2000;

  console.log(`Waiting for service ${serviceName} to be ready...`);

  while (Date.now() - startTime < timeout) {
    try {
      // Check if deployment is ready
      const result = global.kubectl(
        `get deployment ${serviceName} -o jsonpath='{.status.readyReplicas}'`,
        { silent: true }
      );

      const readyReplicas = parseInt(result.trim().replace(/'/g, ''));
      if (readyReplicas > 0) {
        console.log(`Service ${serviceName} is ready`);
        return true;
      }
    } catch (error) {
      // Service might not exist yet
    }

    await global.sleep(interval);
  }

  throw new Error(`Service ${serviceName} did not become ready within ${timeout}ms`);
};

// Get service endpoint
global.getServiceEndpoint = (serviceName, port = 80) => {
  const namespace = global.testNamespace;
  return `http://${serviceName}.${namespace}.svc.cluster.local:${port}`;
};

// Health check for a service
global.healthCheck = async (serviceUrl, retries = 10, delay = 2000) => {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await axios.get(`${serviceUrl}/health`, { timeout: 5000 });
      if (response.status === 200) {
        console.log(`Health check passed for ${serviceUrl}`);
        return true;
      }
    } catch (error) {
      console.log(`Health check attempt ${i + 1}/${retries} failed for ${serviceUrl}`);
      if (i < retries - 1) {
        await global.sleep(delay);
      }
    }
  }
  throw new Error(`Health check failed for ${serviceUrl} after ${retries} retries`);
};

// Setup test namespace and resources
beforeAll(async () => {
  console.log('Setting up E2E test environment...');

  try {
    // Create test namespace if it doesn't exist
    try {
      global.kubectl('get namespace', { silent: true });
    } catch {
      console.log(`Creating namespace ${global.testNamespace}...`);
      execSync(`kubectl create namespace ${global.testNamespace}`, { stdio: 'inherit' });
    }

    // Apply test resources
    console.log('Applying test resources...');
    global.kubectl('apply -f ../../k8s/test-resources/', { silent: false });

    // Wait for core services to be ready
    console.log('Waiting for test services to be ready...');
    await global.waitForService('test-redis');
    await global.waitForService('test-postgres');

    console.log('E2E test environment ready');
  } catch (error) {
    console.error('Failed to setup E2E test environment:', error);
    throw error;
  }
}, 180000); // 3 minutes timeout

// Cleanup after each test
afterEach(async () => {
  jest.clearAllMocks();
});

// Cleanup test namespace after all tests (optional - comment out to debug)
afterAll(async () => {
  if (process.env.CLEANUP_TESTS !== 'false') {
    console.log('Cleaning up E2E test resources...');
    try {
      // Delete test namespace (this will delete all resources in it)
      // Uncomment if you want full cleanup
      // execSync(`kubectl delete namespace ${global.testNamespace} --wait=false`, { stdio: 'inherit' });
      console.log('E2E test cleanup complete');
    } catch (error) {
      console.error('Error cleaning up test resources:', error);
    }
  }
}, 30000);

// Utility functions
global.sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

global.waitForCondition = async (condition, timeout = 30000, interval = 1000) => {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    if (await condition()) {
      return true;
    }
    await global.sleep(interval);
  }
  throw new Error('Condition not met within timeout');
};
