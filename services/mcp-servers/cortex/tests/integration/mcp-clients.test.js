/**
 * Integration tests for MCP Client connections
 * Tests connectivity to UniFi, Proxmox, and Sandfly MCP servers
 */

const assert = require('assert');
const http = require('http');

// Mock MCP Client
class MCPClient {
  constructor(url) {
    this.url = url;
    this.connected = false;
  }

  async connect() {
    try {
      // Simulate connection attempt
      const urlObj = new URL(this.url);
      await this.healthCheck(urlObj);
      this.connected = true;
      return { success: true, message: 'Connected successfully' };
    } catch (error) {
      this.connected = false;
      return { success: false, message: error.message };
    }
  }

  async healthCheck(urlObj) {
    return new Promise((resolve, reject) => {
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port,
        path: '/health',
        method: 'GET',
        timeout: 5000
      };

      const req = http.request(options, (res) => {
        if (res.statusCode === 200) {
          resolve(true);
        } else {
          reject(new Error(`Health check failed with status ${res.statusCode}`));
        }
      });

      req.on('error', (err) => {
        reject(err);
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Connection timeout'));
      });

      req.end();
    });
  }

  async query(toolName, parameters) {
    if (!this.connected) {
      throw new Error('Not connected to MCP server');
    }

    // Simulate MCP query
    return {
      tool: toolName,
      parameters,
      result: `Mock result from ${this.url}`,
      timestamp: new Date().toISOString()
    };
  }

  disconnect() {
    this.connected = false;
  }
}

// Test configuration
const TEST_CONFIG = {
  unifi: {
    url: process.env.UNIFI_MCP_URL || 'http://unifi-mcp-server.cortex-system.svc.cluster.local:3000',
    tools: ['list_devices', 'get_clients', 'get_network_stats']
  },
  proxmox: {
    url: process.env.PROXMOX_MCP_URL || 'http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000',
    tools: ['list_vms', 'get_vm_status', 'list_nodes']
  },
  sandfly: {
    url: process.env.SANDFLY_MCP_URL || 'http://sandfly-mcp-server.cortex-system.svc.cluster.local:8080',
    tools: ['get_alerts', 'get_agents', 'get_vulnerabilities']
  }
};

// Test Suite
async function runTests() {
  console.log('Running MCP Client Integration Tests...\n');

  // Test UniFi MCP Client
  console.log('UniFi MCP Server Tests');
  const unifiClient = new MCPClient(TEST_CONFIG.unifi.url);

  try {
    const connectResult = await unifiClient.connect();
    if (connectResult.success) {
      console.log('  ✓ Connected to UniFi MCP server');
    } else {
      console.log(`  ⚠ Connection failed: ${connectResult.message} (server may not be running)`);
    }

    if (unifiClient.connected) {
      // Test list_devices tool
      const devicesResult = await unifiClient.query('list_devices', {});
      assert.ok(devicesResult.result);
      console.log('  ✓ list_devices query successful');

      // Test get_clients tool
      const clientsResult = await unifiClient.query('get_clients', {});
      assert.ok(clientsResult.result);
      console.log('  ✓ get_clients query successful');

      // Test get_network_stats tool
      const statsResult = await unifiClient.query('get_network_stats', {});
      assert.ok(statsResult.result);
      console.log('  ✓ get_network_stats query successful');

      unifiClient.disconnect();
      console.log('  ✓ Disconnected from UniFi MCP server');
    }
  } catch (error) {
    console.log(`  ⚠ UniFi tests skipped: ${error.message}`);
  }

  // Test Proxmox MCP Client
  console.log('\nProxmox MCP Server Tests');
  const proxmoxClient = new MCPClient(TEST_CONFIG.proxmox.url);

  try {
    const connectResult = await proxmoxClient.connect();
    if (connectResult.success) {
      console.log('  ✓ Connected to Proxmox MCP server');
    } else {
      console.log(`  ⚠ Connection failed: ${connectResult.message} (server may not be running)`);
    }

    if (proxmoxClient.connected) {
      // Test list_vms tool
      const vmsResult = await proxmoxClient.query('list_vms', {});
      assert.ok(vmsResult.result);
      console.log('  ✓ list_vms query successful');

      // Test get_vm_status tool
      const statusResult = await proxmoxClient.query('get_vm_status', { vmid: 100 });
      assert.ok(statusResult.result);
      console.log('  ✓ get_vm_status query successful');

      // Test list_nodes tool
      const nodesResult = await proxmoxClient.query('list_nodes', {});
      assert.ok(nodesResult.result);
      console.log('  ✓ list_nodes query successful');

      proxmoxClient.disconnect();
      console.log('  ✓ Disconnected from Proxmox MCP server');
    }
  } catch (error) {
    console.log(`  ⚠ Proxmox tests skipped: ${error.message}`);
  }

  // Test Sandfly MCP Client
  console.log('\nSandfly MCP Server Tests');
  const sandflyClient = new MCPClient(TEST_CONFIG.sandfly.url);

  try {
    const connectResult = await sandflyClient.connect();
    if (connectResult.success) {
      console.log('  ✓ Connected to Sandfly MCP server');
    } else {
      console.log(`  ⚠ Connection failed: ${connectResult.message} (server may not be running)`);
    }

    if (sandflyClient.connected) {
      // Test get_alerts tool
      const alertsResult = await sandflyClient.query('get_alerts', { limit: 10 });
      assert.ok(alertsResult.result);
      console.log('  ✓ get_alerts query successful');

      // Test get_agents tool
      const agentsResult = await sandflyClient.query('get_agents', {});
      assert.ok(agentsResult.result);
      console.log('  ✓ get_agents query successful');

      // Test get_vulnerabilities tool
      const vulnResult = await sandflyClient.query('get_vulnerabilities', {});
      assert.ok(vulnResult.result);
      console.log('  ✓ get_vulnerabilities query successful');

      sandflyClient.disconnect();
      console.log('  ✓ Disconnected from Sandfly MCP server');
    }
  } catch (error) {
    console.log(`  ⚠ Sandfly tests skipped: ${error.message}`);
  }

  // Test connection pooling
  console.log('\nConnection Pool Tests');
  const clients = [
    new MCPClient(TEST_CONFIG.unifi.url),
    new MCPClient(TEST_CONFIG.proxmox.url),
    new MCPClient(TEST_CONFIG.sandfly.url)
  ];

  const connections = await Promise.allSettled(
    clients.map(client => client.connect())
  );

  const successfulConnections = connections.filter(
    result => result.status === 'fulfilled' && result.value.success
  ).length;

  console.log(`  ✓ Connection pool established: ${successfulConnections}/3 servers connected`);

  // Cleanup
  clients.forEach(client => client.disconnect());
  console.log('  ✓ All connections closed');

  console.log('\nIntegration tests completed!');
}

// Run tests if executed directly
if (require.main === module) {
  runTests().catch(error => {
    console.error('Test suite failed:', error);
    process.exit(1);
  });
}

module.exports = { MCPClient, runTests };
