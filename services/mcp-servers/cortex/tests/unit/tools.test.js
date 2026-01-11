/**
 * Unit tests for Tool Input Validation
 * Tests parameter validation for MCP tools
 */

const assert = require('assert');

// Mock tool validator
class ToolValidator {
  validateSpawnWorkerInput(input) {
    const errors = [];

    if (!input) {
      errors.push('Input is required');
      return { valid: false, errors };
    }

    // Validate worker_type
    const validTypes = ['feature-implementer', 'bug-fixer', 'refactorer', 'optimizer'];
    if (!input.worker_type) {
      errors.push('worker_type is required');
    } else if (!validTypes.includes(input.worker_type)) {
      errors.push(`worker_type must be one of: ${validTypes.join(', ')}`);
    }

    // Validate task_description
    if (!input.task_description) {
      errors.push('task_description is required');
    } else if (typeof input.task_description !== 'string') {
      errors.push('task_description must be a string');
    } else if (input.task_description.length < 10) {
      errors.push('task_description must be at least 10 characters');
    }

    // Validate optional fields
    if (input.token_allocation !== undefined) {
      if (typeof input.token_allocation !== 'number') {
        errors.push('token_allocation must be a number');
      } else if (input.token_allocation < 1000 || input.token_allocation > 100000) {
        errors.push('token_allocation must be between 1000 and 100000');
      }
    }

    if (input.time_limit_minutes !== undefined) {
      if (typeof input.time_limit_minutes !== 'number') {
        errors.push('time_limit_minutes must be a number');
      } else if (input.time_limit_minutes < 1 || input.time_limit_minutes > 240) {
        errors.push('time_limit_minutes must be between 1 and 240');
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  validateQueryMasterInput(input) {
    const errors = [];

    if (!input) {
      errors.push('Input is required');
      return { valid: false, errors };
    }

    // Validate master
    const validMasters = ['unifi', 'proxmox', 'wazuh', 'coordinator'];
    if (!input.master) {
      errors.push('master is required');
    } else if (!validMasters.includes(input.master)) {
      errors.push(`master must be one of: ${validMasters.join(', ')}`);
    }

    // Validate query
    if (!input.query) {
      errors.push('query is required');
    } else if (typeof input.query !== 'string') {
      errors.push('query must be a string');
    } else if (input.query.length < 3) {
      errors.push('query must be at least 3 characters');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  validateGetSystemStatusInput(input) {
    const errors = [];

    if (input && input.detail_level) {
      const validLevels = ['basic', 'detailed', 'full'];
      if (!validLevels.includes(input.detail_level)) {
        errors.push(`detail_level must be one of: ${validLevels.join(', ')}`);
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// Test Suite
console.log('Running Tool Validation Unit Tests...\n');

const validator = new ToolValidator();

// Test spawn_worker validation
console.log('spawn_worker Tool Validation');

// Valid input
let result = validator.validateSpawnWorkerInput({
  worker_type: 'feature-implementer',
  task_description: 'Implement authentication feature',
  token_allocation: 15000,
  time_limit_minutes: 60
});
assert.strictEqual(result.valid, true);
console.log('  ✓ Valid input accepted');

// Missing worker_type
result = validator.validateSpawnWorkerInput({
  task_description: 'Some task'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('worker_type')));
console.log('  ✓ Missing worker_type rejected');

// Invalid worker_type
result = validator.validateSpawnWorkerInput({
  worker_type: 'invalid-type',
  task_description: 'Some task'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('worker_type must be one of')));
console.log('  ✓ Invalid worker_type rejected');

// Missing task_description
result = validator.validateSpawnWorkerInput({
  worker_type: 'bug-fixer'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('task_description')));
console.log('  ✓ Missing task_description rejected');

// Short task_description
result = validator.validateSpawnWorkerInput({
  worker_type: 'bug-fixer',
  task_description: 'Short'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('at least 10 characters')));
console.log('  ✓ Short task_description rejected');

// Invalid token_allocation (too low)
result = validator.validateSpawnWorkerInput({
  worker_type: 'optimizer',
  task_description: 'Optimize database queries',
  token_allocation: 500
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('between 1000 and 100000')));
console.log('  ✓ Invalid token_allocation (too low) rejected');

// Invalid token_allocation (too high)
result = validator.validateSpawnWorkerInput({
  worker_type: 'optimizer',
  task_description: 'Optimize database queries',
  token_allocation: 150000
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('between 1000 and 100000')));
console.log('  ✓ Invalid token_allocation (too high) rejected');

// Invalid time_limit_minutes
result = validator.validateSpawnWorkerInput({
  worker_type: 'refactorer',
  task_description: 'Refactor authentication module',
  time_limit_minutes: 300
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('between 1 and 240')));
console.log('  ✓ Invalid time_limit_minutes rejected');

// Test query_master validation
console.log('\nquery_master Tool Validation');

// Valid input
result = validator.validateQueryMasterInput({
  master: 'unifi',
  query: 'Show network status'
});
assert.strictEqual(result.valid, true);
console.log('  ✓ Valid input accepted');

// Missing master
result = validator.validateQueryMasterInput({
  query: 'Some query'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('master is required')));
console.log('  ✓ Missing master rejected');

// Invalid master
result = validator.validateQueryMasterInput({
  master: 'invalid-master',
  query: 'Some query'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('master must be one of')));
console.log('  ✓ Invalid master rejected');

// Missing query
result = validator.validateQueryMasterInput({
  master: 'proxmox'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('query is required')));
console.log('  ✓ Missing query rejected');

// Short query
result = validator.validateQueryMasterInput({
  master: 'wazuh',
  query: 'Hi'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('at least 3 characters')));
console.log('  ✓ Short query rejected');

// Test get_system_status validation
console.log('\nget_system_status Tool Validation');

// Valid input
result = validator.validateGetSystemStatusInput({
  detail_level: 'detailed'
});
assert.strictEqual(result.valid, true);
console.log('  ✓ Valid input accepted');

// No input (optional parameters)
result = validator.validateGetSystemStatusInput({});
assert.strictEqual(result.valid, true);
console.log('  ✓ Empty input accepted (optional parameters)');

// Invalid detail_level
result = validator.validateGetSystemStatusInput({
  detail_level: 'invalid'
});
assert.strictEqual(result.valid, false);
assert.ok(result.errors.some(e => e.includes('detail_level must be one of')));
console.log('  ✓ Invalid detail_level rejected');

console.log('\nAll tool validation tests passed!');

module.exports = { ToolValidator };
