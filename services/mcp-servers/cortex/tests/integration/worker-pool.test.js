/**
 * Integration tests for Worker Pool
 * Tests worker spawning, task assignment, and completion tracking
 */

const assert = require('assert');
const crypto = require('crypto');

// Mock Worker Pool
class WorkerPool {
  constructor(maxSize = 10000) {
    this.maxSize = maxSize;
    this.workers = new Map();
    this.tasks = new Map();
    this.activeWorkers = 0;
    this.completedTasks = 0;
    this.failedTasks = 0;
  }

  async spawnWorker(workerType, taskDescription, options = {}) {
    if (this.activeWorkers >= this.maxSize) {
      throw new Error(`Worker pool at capacity (${this.maxSize})`);
    }

    const workerId = `worker-${crypto.randomUUID()}`;
    const taskId = `task-${crypto.randomUUID()}`;

    const worker = {
      id: workerId,
      type: workerType,
      taskId: taskId,
      status: 'spawning',
      createdAt: new Date(),
      tokenAllocation: options.tokenAllocation || 15000,
      timeLimit: options.timeLimitMinutes || 60
    };

    const task = {
      id: taskId,
      workerId: workerId,
      description: taskDescription,
      status: 'pending',
      createdAt: new Date()
    };

    this.workers.set(workerId, worker);
    this.tasks.set(taskId, task);
    this.activeWorkers++;

    // Simulate worker initialization
    await this.delay(100);
    worker.status = 'active';
    task.status = 'in_progress';

    return { workerId, taskId, worker };
  }

  async executeTask(taskId) {
    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    const worker = this.workers.get(task.workerId);
    if (!worker) {
      throw new Error(`Worker ${task.workerId} not found`);
    }

    // Simulate task execution
    await this.delay(200);

    // 90% success rate
    const success = Math.random() > 0.1;

    if (success) {
      task.status = 'completed';
      task.completedAt = new Date();
      task.result = {
        success: true,
        output: `Task ${taskId} completed successfully`,
        tokensUsed: Math.floor(Math.random() * worker.tokenAllocation)
      };
      this.completedTasks++;
    } else {
      task.status = 'failed';
      task.completedAt = new Date();
      task.result = {
        success: false,
        error: 'Task execution failed',
        tokensUsed: Math.floor(Math.random() * 1000)
      };
      this.failedTasks++;
    }

    worker.status = 'completed';
    this.activeWorkers--;

    return task.result;
  }

  async spawnAndExecute(workerType, taskDescription, options = {}) {
    const { taskId } = await this.spawnWorker(workerType, taskDescription, options);
    return await this.executeTask(taskId);
  }

  getWorkerStatus(workerId) {
    return this.workers.get(workerId);
  }

  getTaskStatus(taskId) {
    return this.tasks.get(taskId);
  }

  getPoolStats() {
    return {
      maxSize: this.maxSize,
      activeWorkers: this.activeWorkers,
      totalSpawned: this.workers.size,
      completedTasks: this.completedTasks,
      failedTasks: this.failedTasks,
      successRate: this.completedTasks / (this.completedTasks + this.failedTasks) || 0
    };
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Test Suite
async function runTests() {
  console.log('Running Worker Pool Integration Tests...\n');

  // Test 1: Single worker spawn
  console.log('Single Worker Spawn Test');
  const pool1 = new WorkerPool(10);

  const { workerId, taskId } = await pool1.spawnWorker(
    'feature-implementer',
    'Implement authentication feature',
    { tokenAllocation: 15000, timeLimitMinutes: 60 }
  );

  assert.ok(workerId);
  assert.ok(taskId);
  console.log('  ✓ Worker spawned successfully');

  const workerStatus = pool1.getWorkerStatus(workerId);
  assert.strictEqual(workerStatus.status, 'active');
  console.log('  ✓ Worker status is active');

  const taskStatus = pool1.getTaskStatus(taskId);
  assert.strictEqual(taskStatus.status, 'in_progress');
  console.log('  ✓ Task status is in_progress');

  // Test 2: Task execution
  console.log('\nTask Execution Test');
  const result = await pool1.executeTask(taskId);
  assert.ok(result);
  console.log('  ✓ Task executed');

  const completedTask = pool1.getTaskStatus(taskId);
  assert.ok(['completed', 'failed'].includes(completedTask.status));
  console.log(`  ✓ Task status updated to ${completedTask.status}`);

  // Test 3: Multiple workers
  console.log('\nMultiple Workers Test (5 workers)');
  const pool2 = new WorkerPool(100);
  const workerTypes = ['feature-implementer', 'bug-fixer', 'refactorer', 'optimizer', 'feature-implementer'];
  const tasks = [
    'Implement user registration',
    'Fix memory leak in worker pool',
    'Refactor MoE router',
    'Optimize database queries',
    'Implement password reset'
  ];

  const spawnPromises = tasks.map((task, index) =>
    pool2.spawnWorker(workerTypes[index], task)
  );

  const workers = await Promise.all(spawnPromises);
  assert.strictEqual(workers.length, 5);
  console.log('  ✓ 5 workers spawned successfully');

  const stats1 = pool2.getPoolStats();
  assert.strictEqual(stats1.activeWorkers, 5);
  console.log('  ✓ Pool has 5 active workers');

  // Test 4: Concurrent task execution
  console.log('\nConcurrent Task Execution Test');
  const executePromises = workers.map(({ taskId }) =>
    pool2.executeTask(taskId)
  );

  const results = await Promise.all(executePromises);
  assert.strictEqual(results.length, 5);
  console.log('  ✓ All 5 tasks executed');

  const stats2 = pool2.getPoolStats();
  assert.strictEqual(stats2.activeWorkers, 0);
  assert.strictEqual(stats2.completedTasks + stats2.failedTasks, 5);
  console.log(`  ✓ Tasks completed: ${stats2.completedTasks}, failed: ${stats2.failedTasks}`);
  console.log(`  ✓ Success rate: ${(stats2.successRate * 100).toFixed(1)}%`);

  // Test 5: Worker pool capacity
  console.log('\nWorker Pool Capacity Test');
  const pool3 = new WorkerPool(10);

  const capacityPromises = [];
  for (let i = 0; i < 10; i++) {
    capacityPromises.push(
      pool3.spawnWorker('feature-implementer', `Task ${i}`)
    );
  }

  const capacityWorkers = await Promise.all(capacityPromises);
  assert.strictEqual(capacityWorkers.length, 10);
  console.log('  ✓ Pool filled to capacity (10/10)');

  const stats3 = pool3.getPoolStats();
  assert.strictEqual(stats3.activeWorkers, 10);
  console.log('  ✓ Pool at maximum capacity');

  // Test 6: Pool overflow protection
  console.log('\nPool Overflow Protection Test');
  try {
    await pool3.spawnWorker('feature-implementer', 'Overflow task');
    assert.fail('Should have thrown capacity error');
  } catch (error) {
    assert.ok(error.message.includes('capacity'));
    console.log('  ✓ Pool correctly rejects overflow');
  }

  // Test 7: Scaling test (10 workers)
  console.log('\nScaling Test (10 workers)');
  const pool4 = new WorkerPool(100);

  const scalingTasks = [];
  for (let i = 0; i < 10; i++) {
    scalingTasks.push({
      type: workerTypes[i % workerTypes.length],
      description: `Scaling test task ${i}`
    });
  }

  const scalingPromises = scalingTasks.map(task =>
    pool4.spawnAndExecute(task.type, task.description)
  );

  const scalingResults = await Promise.all(scalingPromises);
  assert.strictEqual(scalingResults.length, 10);
  console.log('  ✓ 10 workers spawned and executed successfully');

  const stats4 = pool4.getPoolStats();
  console.log(`  ✓ Completed: ${stats4.completedTasks}, Failed: ${stats4.failedTasks}`);
  console.log(`  ✓ Success rate: ${(stats4.successRate * 100).toFixed(1)}%`);

  // Test 8: Worker type distribution
  console.log('\nWorker Type Distribution Test');
  const pool5 = new WorkerPool(1000);
  const typeCounts = {
    'feature-implementer': 0,
    'bug-fixer': 0,
    'refactorer': 0,
    'optimizer': 0
  };

  const distributionTasks = [];
  for (let i = 0; i < 20; i++) {
    const type = workerTypes[i % workerTypes.length];
    typeCounts[type]++;
    distributionTasks.push(
      pool5.spawnWorker(type, `Distribution test ${i}`)
    );
  }

  await Promise.all(distributionTasks);
  console.log('  ✓ 20 workers spawned with distribution:');
  console.log(`    - feature-implementer: ${typeCounts['feature-implementer']}`);
  console.log(`    - bug-fixer: ${typeCounts['bug-fixer']}`);
  console.log(`    - refactorer: ${typeCounts['refactorer']}`);
  console.log(`    - optimizer: ${typeCounts['optimizer']}`);

  console.log('\nAll worker pool tests completed!');
}

// Run tests if executed directly
if (require.main === module) {
  runTests().catch(error => {
    console.error('Test suite failed:', error);
    process.exit(1);
  });
}

module.exports = { WorkerPool, runTests };
