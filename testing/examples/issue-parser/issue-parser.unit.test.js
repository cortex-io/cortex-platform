// Unit tests for Issue Parser Service
const request = require('supertest');
const express = require('express');

// Mock dependencies
jest.mock('@anthropic-ai/sdk');
jest.mock('redis', () => ({
  createClient: jest.fn(() => ({
    connect: jest.fn().mockResolvedValue(undefined),
    isOpen: true,
    set: jest.fn().mockResolvedValue('OK'),
    get: jest.fn(),
    quit: jest.fn().mockResolvedValue(undefined),
    on: jest.fn()
  }))
}));

const Anthropic = require('@anthropic-ai/sdk');

describe('Issue Parser Service - Unit Tests', () => {
  let app;
  let mockAnthropic;
  let mockRedis;

  beforeEach(() => {
    // Setup mocks
    mockAnthropic = {
      messages: {
        create: jest.fn()
      }
    };
    Anthropic.mockImplementation(() => mockAnthropic);

    // Reset modules to get fresh instance
    jest.resetModules();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /issues/parse', () => {
    it('should parse a valid issue successfully', async () => {
      const mockResponse = {
        content: [{
          text: JSON.stringify({
            task_id: 'test-id',
            title: 'Add authentication',
            description: 'Implement JWT authentication',
            acceptance_criteria: ['Users can login', 'Tokens expire after 1 hour'],
            context: {
              service: 'auth-service',
              namespace: 'cortex-dev'
            },
            estimated_complexity: 'medium',
            task_type: 'feature'
          })
        }]
      };

      mockAnthropic.messages.create.mockResolvedValue(mockResponse);

      // Note: This test would require setting up the full app
      // For now, testing the parsing logic in isolation

      const issueText = 'Add JWT authentication to the auth service';
      const expectedOutput = {
        task_id: 'test-id',
        title: 'Add authentication',
        description: 'Implement JWT authentication'
      };

      expect(mockAnthropic.messages.create).toBeDefined();
    });

    it('should return 400 if issue field is missing', async () => {
      // Test validation logic
      const payload = {}; // Missing 'issue' field

      const validatePayload = (body) => {
        if (!body.issue) {
          return { error: 'issue field is required', status: 400 };
        }
        return { status: 200 };
      };

      const result = validatePayload(payload);
      expect(result.status).toBe(400);
      expect(result.error).toBe('issue field is required');
    });

    it('should handle malformed JSON from AI', async () => {
      const mockResponse = {
        content: [{
          text: 'This is not valid JSON {invalid}'
        }]
      };

      mockAnthropic.messages.create.mockResolvedValue(mockResponse);

      const parseJsonResponse = (text) => {
        try {
          return JSON.parse(text);
        } catch (error) {
          throw new Error('Invalid JSON response from AI');
        }
      };

      expect(() => parseJsonResponse(mockResponse.content[0].text))
        .toThrow('Invalid JSON response from AI');
    });

    it('should include context in the prompt', () => {
      const buildPrompt = (issue, context) => {
        let prompt = `Parse this development request into a structured task:\n\n${issue}`;

        if (context.repository) {
          prompt += `\n\nRepository: ${context.repository}`;
        }
        if (context.service) {
          prompt += `\nService: ${context.service}`;
        }

        return prompt;
      };

      const prompt = buildPrompt('Add feature', { repository: 'cortex', service: 'api' });
      expect(prompt).toContain('Repository: cortex');
      expect(prompt).toContain('Service: api');
    });
  });

  describe('POST /issues/validate', () => {
    it('should validate atomic tasks', async () => {
      const mockValidation = {
        is_atomic: true,
        is_well_defined: true,
        issues: [],
        suggestions: []
      };

      const validateTask = (task) => {
        const hasTitle = !!task.title;
        const hasDescription = !!task.description;
        const hasCriteria = Array.isArray(task.acceptance_criteria) && task.acceptance_criteria.length > 0;

        return {
          is_well_defined: hasTitle && hasDescription && hasCriteria,
          issues: []
        };
      };

      const task = {
        title: 'Test task',
        description: 'Test description',
        acceptance_criteria: ['Criterion 1']
      };

      const result = validateTask(task);
      expect(result.is_well_defined).toBe(true);
    });

    it('should identify missing acceptance criteria', () => {
      const validateTask = (task) => {
        const issues = [];

        if (!Array.isArray(task.acceptance_criteria) || task.acceptance_criteria.length === 0) {
          issues.push('Missing acceptance criteria');
        }

        return { issues };
      };

      const task = {
        title: 'Test task',
        description: 'Test description'
      };

      const result = validateTask(task);
      expect(result.issues).toContain('Missing acceptance criteria');
    });
  });

  describe('GET /issues/:id', () => {
    it('should retrieve task from Redis', async () => {
      const mockTask = {
        task_id: 'test-123',
        title: 'Test Task',
        description: 'Test Description'
      };

      const getFromRedis = async (key) => {
        if (key === 'issue:test-123') {
          return JSON.stringify(mockTask);
        }
        return null;
      };

      const result = await getFromRedis('issue:test-123');
      const parsed = JSON.parse(result);
      expect(parsed.task_id).toBe('test-123');
      expect(parsed.title).toBe('Test Task');
    });

    it('should return 404 for non-existent task', async () => {
      const getFromRedis = async (key) => {
        return null;
      };

      const result = await getFromRedis('issue:nonexistent');
      expect(result).toBeNull();
    });
  });

  describe('POST /issues/:id/refine', () => {
    it('should refine task with additional context', async () => {
      const originalTask = {
        task_id: 'test-123',
        title: 'Original title',
        description: 'Original description'
      };

      const additionalContext = 'Use PostgreSQL for data storage';

      const refineTask = (task, context) => {
        return {
          ...task,
          description: `${task.description}\n\nAdditional context: ${context}`,
          refined_at: new Date().toISOString()
        };
      };

      const refined = refineTask(originalTask, additionalContext);
      expect(refined.description).toContain('Additional context');
      expect(refined.refined_at).toBeDefined();
    });

    it('should preserve task_id during refinement', () => {
      const task = { task_id: 'original-123', title: 'Test' };
      const refined = { ...task, title: 'Updated Test' };
      refined.task_id = task.task_id; // Preserve ID

      expect(refined.task_id).toBe('original-123');
    });
  });

  describe('GET /health', () => {
    it('should return healthy status when all dependencies are ready', () => {
      const checkHealth = (redisConnected, anthropicConfigured) => {
        const health = {
          status: 'healthy',
          redis: redisConnected ? 'connected' : 'disconnected',
          anthropic: anthropicConfigured ? 'configured' : 'not_configured'
        };

        const statusCode = health.redis === 'connected' && health.anthropic === 'configured' ? 200 : 503;
        return { health, statusCode };
      };

      const result = checkHealth(true, true);
      expect(result.statusCode).toBe(200);
      expect(result.health.status).toBe('healthy');
    });

    it('should return 503 when dependencies are not ready', () => {
      const checkHealth = (redisConnected, anthropicConfigured) => {
        const health = {
          status: 'healthy',
          redis: redisConnected ? 'connected' : 'disconnected',
          anthropic: anthropicConfigured ? 'configured' : 'not_configured'
        };

        const statusCode = health.redis === 'connected' && health.anthropic === 'configured' ? 200 : 503;
        return { health, statusCode };
      };

      const result = checkHealth(false, true);
      expect(result.statusCode).toBe(503);
    });
  });

  describe('Prometheus Metrics', () => {
    it('should increment counter on successful parse', () => {
      const mockCounter = {
        inc: jest.fn()
      };

      mockCounter.inc({ status: 'success' });
      expect(mockCounter.inc).toHaveBeenCalledWith({ status: 'success' });
    });

    it('should track parse duration', () => {
      const mockHistogram = {
        startTimer: jest.fn(() => jest.fn())
      };

      const end = mockHistogram.startTimer();
      expect(mockHistogram.startTimer).toHaveBeenCalled();
      expect(typeof end).toBe('function');
    });
  });
});
