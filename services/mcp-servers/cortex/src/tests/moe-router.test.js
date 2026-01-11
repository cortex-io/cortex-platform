/**
 * Unit tests for MoE Router
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import { routeQuery, getRoutingSuggestion, MOE_ROUTES } from '../moe-router.js';

describe('MoE Router', () => {
  describe('routeQuery', () => {
    it('should route UniFi queries correctly', () => {
      const queries = [
        'Show me all WiFi networks',
        'What clients are connected to the network?',
        'List all access points',
        'What is the bandwidth usage on UniFi?'
      ];

      for (const query of queries) {
        const result = routeQuery(query);
        assert.strictEqual(result.system, 'unifi', `Query "${query}" should route to unifi`);
        assert.ok(result.confidence > 0, 'Confidence should be > 0');
      }
    });

    it('should route Proxmox queries correctly', () => {
      const queries = [
        'List all VMs on Proxmox',
        'What containers are running?',
        'Show me node resources',
        'Create a new virtual machine'
      ];

      for (const query of queries) {
        const result = routeQuery(query);
        assert.strictEqual(result.system, 'proxmox', `Query "${query}" should route to proxmox`);
        assert.ok(result.confidence > 0, 'Confidence should be > 0');
      }
    });

    it('should route Sandfly queries correctly', () => {
      const queries = [
        'Show me security alerts',
        'What vulnerability was detected?',
        'List compliance violations',
        'Show me threat intelligence'
      ];

      for (const query of queries) {
        const result = routeQuery(query);
        assert.strictEqual(result.system, 'sandfly', `Query "${query}" should route to sandfly`);
        assert.ok(result.confidence > 0, 'Confidence should be > 0');
      }
    });

    it('should route Kubernetes queries correctly', () => {
      const queries = [
        'List all pods in the cluster',
        'What deployments are running?',
        'Show me k8s services',
        'Get namespace details'
      ];

      for (const query of queries) {
        const result = routeQuery(query);
        assert.strictEqual(result.system, 'k8s', `Query "${query}" should route to k8s`);
        assert.ok(result.confidence > 0, 'Confidence should be > 0');
      }
    });

    it('should return null for ambiguous queries', () => {
      const result = routeQuery('What is the weather today?');
      assert.strictEqual(result.system, null);
      assert.strictEqual(result.confidence, 0);
    });

    it('should handle multiple keyword matches', () => {
      const result = routeQuery('Show me UniFi network and security alerts');
      assert.ok(result.allMatches.length >= 2, 'Should match multiple systems');
      assert.ok(result.confidence > 0, 'Should have confidence > 0');
    });

    it('should calculate confidence correctly', () => {
      const highConfQuery = 'unifi network wifi';
      const lowConfQuery = 'wifi';

      const high = routeQuery(highConfQuery);
      const low = routeQuery(lowConfQuery);

      assert.ok(high.confidence >= low.confidence, 'More keywords should increase or maintain confidence');
    });
  });

  describe('getRoutingSuggestion', () => {
    it('should force route on high confidence', () => {
      const result = getRoutingSuggestion('Show me all UniFi access points');
      assert.strictEqual(result.action, 'force');
      assert.strictEqual(result.system, 'unifi');
      assert.ok(result.confidence >= 1.0);
    });

    it('should suggest route on moderate confidence', () => {
      const result = getRoutingSuggestion('Show me network information');
      if (result.confidence >= 0.5 && result.confidence < 1.0) {
        assert.strictEqual(result.action, 'suggest');
        assert.ok(result.system !== null);
      }
    });

    it('should not suggest on low confidence', () => {
      const result = getRoutingSuggestion('What is the status?');
      assert.strictEqual(result.action, 'none');
    });

    it('should include reasoning', () => {
      const result = getRoutingSuggestion('Proxmox VM status');
      assert.ok(result.reason, 'Should include reason');
      assert.ok(typeof result.reason === 'string');
    });
  });

  describe('MOE_ROUTES configuration', () => {
    it('should have all required systems', () => {
      const requiredSystems = ['unifi', 'proxmox', 'sandfly', 'kubernetes'];
      for (const system of requiredSystems) {
        assert.ok(MOE_ROUTES[system], `Should have ${system} route`);
      }
    });

    it('should have keywords for each system', () => {
      for (const [name, route] of Object.entries(MOE_ROUTES)) {
        assert.ok(Array.isArray(route.keywords), `${name} should have keywords array`);
        assert.ok(route.keywords.length > 0, `${name} should have at least one keyword`);
      }
    });

    it('should have valid priorities', () => {
      for (const [name, route] of Object.entries(MOE_ROUTES)) {
        assert.ok(typeof route.priority === 'number', `${name} should have numeric priority`);
        assert.ok(route.priority > 0, `${name} priority should be > 0`);
      }
    });
  });

  describe('Edge cases', () => {
    it('should handle empty query', () => {
      const result = routeQuery('');
      assert.strictEqual(result.system, null);
      assert.strictEqual(result.confidence, 0);
    });

    it('should handle special characters', () => {
      const result = routeQuery('Show me UniFi @#$% networks!!!');
      assert.strictEqual(result.system, 'unifi');
    });

    it('should be case insensitive', () => {
      const lower = routeQuery('unifi network');
      const upper = routeQuery('UNIFI NETWORK');
      const mixed = routeQuery('UniFi NeTwOrK');

      assert.strictEqual(lower.system, upper.system);
      assert.strictEqual(lower.system, mixed.system);
    });

    it('should handle partial keyword matches', () => {
      const result = routeQuery('kubernetes cluster');
      assert.strictEqual(result.system, 'k8s');
    });
  });
});
