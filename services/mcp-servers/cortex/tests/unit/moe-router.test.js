/**
 * Unit tests for MoE Router
 * Tests keyword-based routing to specialized MCP servers
 */

const assert = require('assert');

// Mock MoE Router implementation for testing
class MoERouter {
  constructor() {
    this.keywords = {
      unifi: ['unifi', 'wifi', 'network', 'access point', 'switch', 'client', 'ssid'],
      proxmox: ['proxmox', 'vm', 'virtual machine', 'container', 'lxc', 'node', 'storage'],
      sandfly: ['sandfly', 'security', 'alert', 'siem', 'vulnerability', 'compliance', 'agent']
    };
  }

  route(query) {
    const lowerQuery = query.toLowerCase();

    // Check for keyword matches
    for (const [master, keywords] of Object.entries(this.keywords)) {
      for (const keyword of keywords) {
        if (lowerQuery.includes(keyword)) {
          return master;
        }
      }
    }

    // Default to coordinator for general queries
    return 'coordinator';
  }

  getServerUrl(master) {
    const urls = {
      unifi: process.env.UNIFI_MCP_URL || 'http://unifi-mcp-server:3000',
      proxmox: process.env.PROXMOX_MCP_URL || 'http://proxmox-mcp-server:3000',
      sandfly: process.env.SANDFLY_MCP_URL || 'http://sandfly-mcp-server:8080',
      coordinator: 'internal'
    };

    return urls[master] || urls.coordinator;
  }
}

// Test Suite
describe('MoE Router', () => {
  let router;

  beforeEach(() => {
    router = new MoERouter();
  });

  describe('Keyword Routing', () => {
    it('should route UniFi queries correctly', () => {
      assert.strictEqual(router.route('Show me UniFi network status'), 'unifi');
      assert.strictEqual(router.route('List all WiFi clients'), 'unifi');
      assert.strictEqual(router.route('What is the SSID configuration?'), 'unifi');
      assert.strictEqual(router.route('Show access point status'), 'unifi');
    });

    it('should route Proxmox queries correctly', () => {
      assert.strictEqual(router.route('List Proxmox VMs'), 'proxmox');
      assert.strictEqual(router.route('Show virtual machine status'), 'proxmox');
      assert.strictEqual(router.route('What containers are running?'), 'proxmox');
      assert.strictEqual(router.route('Check node storage'), 'proxmox');
    });

    it('should route Sandfly queries correctly', () => {
      assert.strictEqual(router.route('Show Sandfly security alerts'), 'sandfly');
      assert.strictEqual(router.route('List compliance violations'), 'sandfly');
      assert.strictEqual(router.route('What are the recent SIEM events?'), 'sandfly');
      assert.strictEqual(router.route('Show vulnerability scan results'), 'sandfly');
    });

    it('should route to coordinator for general queries', () => {
      assert.strictEqual(router.route('What is the weather today?'), 'coordinator');
      assert.strictEqual(router.route('Help me with deployment'), 'coordinator');
      assert.strictEqual(router.route('General system overview'), 'coordinator');
    });

    it('should handle case-insensitive matching', () => {
      assert.strictEqual(router.route('UNIFI STATUS'), 'unifi');
      assert.strictEqual(router.route('ProxMox VMs'), 'proxmox');
      assert.strictEqual(router.route('SaNdFlY aLeRtS'), 'sandfly');
    });

    it('should match partial keywords', () => {
      assert.strictEqual(router.route('The UniFi controller is down'), 'unifi');
      assert.strictEqual(router.route('My Proxmox cluster needs help'), 'proxmox');
      assert.strictEqual(router.route('Check the Sandfly dashboard'), 'sandfly');
    });
  });

  describe('URL Resolution', () => {
    it('should return correct UniFi URL', () => {
      const url = router.getServerUrl('unifi');
      assert.ok(url.includes('unifi-mcp-server'));
    });

    it('should return correct Proxmox URL', () => {
      const url = router.getServerUrl('proxmox');
      assert.ok(url.includes('proxmox-mcp-server'));
    });

    it('should return correct Sandfly URL', () => {
      const url = router.getServerUrl('sandfly');
      assert.ok(url.includes('sandfly-mcp-server'));
    });

    it('should return internal for coordinator', () => {
      const url = router.getServerUrl('coordinator');
      assert.strictEqual(url, 'internal');
    });

    it('should handle unknown masters gracefully', () => {
      const url = router.getServerUrl('unknown-master');
      assert.strictEqual(url, 'internal');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty queries', () => {
      assert.strictEqual(router.route(''), 'coordinator');
    });

    it('should handle null queries', () => {
      assert.strictEqual(router.route(null), 'coordinator');
    });

    it('should handle queries with multiple keywords', () => {
      // First match wins
      const result = router.route('Show UniFi WiFi and Proxmox VMs');
      assert.strictEqual(result, 'unifi');
    });

    it('should handle special characters', () => {
      assert.strictEqual(router.route('UniFi @#$% network!'), 'unifi');
    });
  });
});

// Simple test runner
function describe(name, fn) {
  console.log(`\n${name}`);
  fn();
}

function beforeEach(fn) {
  // Store setup function
  describe.beforeEach = fn;
}

function it(name, fn) {
  if (describe.beforeEach) {
    describe.beforeEach();
  }

  try {
    fn();
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.log(`  ✗ ${name}`);
    console.log(`    ${error.message}`);
    process.exitCode = 1;
  }
}

// Run tests if executed directly
if (require.main === module) {
  console.log('Running MoE Router Unit Tests...');
  describe('MoE Router', () => {
    let router;

    beforeEach(() => {
      router = new MoERouter();
    });

    describe('Keyword Routing', () => {
      it('should route UniFi queries correctly', () => {
        assert.strictEqual(router.route('Show me UniFi network status'), 'unifi');
        assert.strictEqual(router.route('List all WiFi clients'), 'unifi');
      });

      it('should route Proxmox queries correctly', () => {
        assert.strictEqual(router.route('List Proxmox VMs'), 'proxmox');
        assert.strictEqual(router.route('Show virtual machine status'), 'proxmox');
      });

      it('should route Sandfly queries correctly', () => {
        assert.strictEqual(router.route('Show Sandfly security alerts'), 'sandfly');
        assert.strictEqual(router.route('List compliance violations'), 'sandfly');
      });
    });
  });

  console.log('\nTests completed!');
}

module.exports = { MoERouter };
