// Global test setup for Jest unit tests

// Extend Jest matchers if needed
// require('jest-extended');

// Set test environment variables
process.env.NODE_ENV = 'test';
process.env.LOG_LEVEL = 'error';

// Mock common external services by default
jest.mock('redis', () => ({
  createClient: jest.fn(() => ({
    connect: jest.fn().mockResolvedValue(undefined),
    disconnect: jest.fn().mockResolvedValue(undefined),
    get: jest.fn(),
    set: jest.fn(),
    del: jest.fn(),
    exists: jest.fn(),
    expire: jest.fn(),
    on: jest.fn(),
    quit: jest.fn()
  }))
}));

// Global test utilities
global.sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

global.mockRedisClient = () => ({
  connect: jest.fn().mockResolvedValue(undefined),
  disconnect: jest.fn().mockResolvedValue(undefined),
  get: jest.fn(),
  set: jest.fn(),
  del: jest.fn(),
  exists: jest.fn(),
  expire: jest.fn(),
  on: jest.fn(),
  quit: jest.fn()
});

global.mockHttpResponse = () => {
  const res = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json = jest.fn().mockReturnValue(res);
  res.send = jest.fn().mockReturnValue(res);
  res.set = jest.fn().mockReturnValue(res);
  return res;
};

global.mockHttpRequest = (overrides = {}) => ({
  body: {},
  params: {},
  query: {},
  headers: {},
  ...overrides
});

// Cleanup after each test
afterEach(() => {
  jest.clearAllMocks();
});

// Setup before all tests
beforeAll(() => {
  // Suppress console output during tests unless explicitly needed
  if (process.env.VERBOSE !== 'true') {
    global.console = {
      ...console,
      log: jest.fn(),
      debug: jest.fn(),
      info: jest.fn(),
      warn: jest.fn(),
      // Keep error for debugging
      error: console.error
    };
  }
});
