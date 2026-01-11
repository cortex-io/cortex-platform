// Global setup for integration tests with testcontainers

const { GenericContainer, Wait } = require('testcontainers');

// Set test environment
process.env.NODE_ENV = 'test';
process.env.LOG_LEVEL = 'info';

// Global test containers
global.testContainers = {
  redis: null,
  postgres: null,
  redisPort: null,
  postgresPort: null
};

// Setup containers before all tests
beforeAll(async () => {
  console.log('Starting test containers...');

  try {
    // Start Redis container
    const redisContainer = await new GenericContainer('redis:7-alpine')
      .withExposedPorts(6379)
      .withWaitStrategy(Wait.forLogMessage('Ready to accept connections'))
      .start();

    global.testContainers.redis = redisContainer;
    global.testContainers.redisPort = redisContainer.getMappedPort(6379);
    process.env.REDIS_HOST = 'localhost';
    process.env.REDIS_PORT = global.testContainers.redisPort.toString();

    console.log(`Redis container started on port ${global.testContainers.redisPort}`);

    // Start PostgreSQL container
    const postgresContainer = await new GenericContainer('postgres:16-alpine')
      .withEnvironment({
        POSTGRES_DB: 'cortex_test',
        POSTGRES_USER: 'cortex_test',
        POSTGRES_PASSWORD: 'cortex_test_password'
      })
      .withExposedPorts(5432)
      .withWaitStrategy(Wait.forLogMessage('database system is ready to accept connections'))
      .start();

    global.testContainers.postgres = postgresContainer;
    global.testContainers.postgresPort = postgresContainer.getMappedPort(5432);
    process.env.POSTGRES_HOST = 'localhost';
    process.env.POSTGRES_PORT = global.testContainers.postgresPort.toString();
    process.env.POSTGRES_DB = 'cortex_test';
    process.env.POSTGRES_USER = 'cortex_test';
    process.env.POSTGRES_PASSWORD = 'cortex_test_password';

    console.log(`PostgreSQL container started on port ${global.testContainers.postgresPort}`);

  } catch (error) {
    console.error('Failed to start test containers:', error);
    throw error;
  }
}, 120000); // 2 minutes timeout for container startup

// Cleanup containers after all tests
afterAll(async () => {
  console.log('Stopping test containers...');

  try {
    if (global.testContainers.redis) {
      await global.testContainers.redis.stop();
      console.log('Redis container stopped');
    }

    if (global.testContainers.postgres) {
      await global.testContainers.postgres.stop();
      console.log('PostgreSQL container stopped');
    }
  } catch (error) {
    console.error('Error stopping containers:', error);
  }
}, 30000);

// Cleanup after each test
afterEach(() => {
  jest.clearAllMocks();
});

// Utility functions
global.sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

global.waitForCondition = async (condition, timeout = 5000, interval = 100) => {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    if (await condition()) {
      return true;
    }
    await global.sleep(interval);
  }
  throw new Error('Condition not met within timeout');
};
