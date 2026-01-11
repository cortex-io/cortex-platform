module.exports = {
  displayName: 'Cortex E2E Tests',
  testEnvironment: 'node',
  testMatch: [
    '**/__tests__/**/*.e2e.test.js',
    '**/?(*.)+(e2e).test.js'
  ],
  collectCoverageFrom: [
    '**/*.js',
    '!**/node_modules/**',
    '!**/coverage/**',
    '!**/__tests__/**',
    '!**/dist/**'
  ],
  coverageDirectory: '../../coverage/e2e/js',
  coverageReporters: ['text', 'lcov', 'html', 'json'],
  verbose: true,
  testTimeout: 120000, // 2 minutes for E2E tests
  setupFilesAfterEnv: ['./setup.js'],
  maxWorkers: 1, // Run E2E tests sequentially
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/../../../$1',
    '^@testing/(.*)$': '<rootDir>/../../$1'
  }
};
