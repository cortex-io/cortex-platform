module.exports = {
  displayName: 'Cortex Integration Tests',
  testEnvironment: 'node',
  testMatch: [
    '**/__tests__/**/*.integration.test.js',
    '**/?(*.)+(integration).test.js'
  ],
  collectCoverageFrom: [
    '**/*.js',
    '!**/node_modules/**',
    '!**/coverage/**',
    '!**/__tests__/**',
    '!**/dist/**'
  ],
  coverageDirectory: '../../coverage/integration/js',
  coverageReporters: ['text', 'lcov', 'html', 'json'],
  verbose: true,
  testTimeout: 60000, // 60 seconds for integration tests
  setupFilesAfterEnv: ['./setup.js'],
  maxWorkers: 2, // Limit parallel tests for container resources
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/../../../$1',
    '^@testing/(.*)$': '<rootDir>/../../$1'
  }
};
