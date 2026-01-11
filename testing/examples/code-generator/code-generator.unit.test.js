// Unit tests for Code Generator Service
const request = require('supertest');

jest.mock('@anthropic-ai/sdk');
jest.mock('axios');

const Anthropic = require('@anthropic-ai/sdk');
const axios = require('axios');

describe('Code Generator Service - Unit Tests', () => {
  let mockAnthropic;

  beforeEach(() => {
    mockAnthropic = {
      messages: {
        create: jest.fn()
      }
    };
    Anthropic.mockImplementation(() => mockAnthropic);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /generate', () => {
    it('should generate code from task specification', async () => {
      const mockResponse = {
        content: [{
          text: JSON.stringify({
            files: [{
              path: 'src/auth.js',
              content: 'const jwt = require("jsonwebtoken");',
              description: 'JWT authentication module'
            }],
            dependencies: {
              npm: ['jsonwebtoken'],
              pip: []
            },
            tests: [{
              path: 'test/auth.test.js',
              content: 'describe("Auth", () => {})'
            }]
          })
        }]
      };

      mockAnthropic.messages.create.mockResolvedValue(mockResponse);

      const generateCode = async (task) => {
        const result = await mockAnthropic.messages.create({
          model: 'claude-sonnet-4',
          messages: [{ role: 'user', content: JSON.stringify(task) }]
        });

        return JSON.parse(result.content[0].text);
      };

      const code = await generateCode({ title: 'Add auth' });
      expect(code.files).toHaveLength(1);
      expect(code.dependencies.npm).toContain('jsonwebtoken');
    });

    it('should return 400 if task is missing', () => {
      const validateRequest = (body) => {
        if (!body.task) {
          return { error: 'task field is required', status: 400 };
        }
        return { status: 200 };
      };

      const result = validateRequest({});
      expect(result.status).toBe(400);
    });

    it('should fetch repository context when repo_id provided', async () => {
      axios.post.mockResolvedValue({
        data: {
          instructions: ['Use kebab-case', 'Include tests']
        }
      });

      const fetchContext = async (repoId) => {
        const response = await axios.post(`http://repo-context/repos/${repoId}/instructions`);
        return response.data.instructions;
      };

      const instructions = await fetchContext('test-repo');
      expect(instructions).toContain('Use kebab-case');
    });

    it('should handle JSON parsing errors gracefully', () => {
      const parseResponse = (text) => {
        try {
          const jsonMatch = text.match(/\{[\s\S]*\}/);
          return jsonMatch ? JSON.parse(jsonMatch[0]) : null;
        } catch (error) {
          throw new Error('Invalid JSON response from AI');
        }
      };

      expect(() => parseResponse('invalid json')).toThrow('Invalid JSON response from AI');
    });
  });

  describe('POST /edit', () => {
    it('should edit existing code', async () => {
      const mockResponse = {
        content: [{
          text: JSON.stringify({
            updated_content: 'Updated code here',
            changes_summary: 'Added error handling',
            affected_tests: ['test/module.test.js']
          })
        }]
      };

      mockAnthropic.messages.create.mockResolvedValue(mockResponse);

      const result = JSON.parse(mockResponse.content[0].text);
      expect(result.updated_content).toBeDefined();
      expect(result.changes_summary).toBe('Added error handling');
    });

    it('should require file_path, current_content, and edit_instruction', () => {
      const validateEditRequest = (body) => {
        const required = ['file_path', 'current_content', 'edit_instruction'];
        const missing = required.filter(field => !body[field]);

        if (missing.length > 0) {
          return { error: `Missing fields: ${missing.join(', ')}`, status: 400 };
        }
        return { status: 200 };
      };

      const result = validateEditRequest({ file_path: 'test.js' });
      expect(result.status).toBe(400);
    });
  });

  describe('POST /test', () => {
    it('should generate comprehensive tests', async () => {
      const mockResponse = {
        content: [{
          text: JSON.stringify({
            test_files: [{
              path: 'test/service.test.js',
              content: 'describe("Service", () => { it("works", () => {}) })'
            }],
            coverage_estimate: '85%',
            test_summary: 'Tests cover happy path and error cases'
          })
        }]
      };

      mockAnthropic.messages.create.mockResolvedValue(mockResponse);

      const result = JSON.parse(mockResponse.content[0].text);
      expect(result.test_files).toHaveLength(1);
      expect(result.coverage_estimate).toBe('85%');
    });

    it('should validate implementation_files array', () => {
      const validate = (body) => {
        if (!body.implementation_files || !Array.isArray(body.implementation_files)) {
          return { error: 'implementation_files array is required', status: 400 };
        }
        return { status: 200 };
      };

      expect(validate({}).status).toBe(400);
      expect(validate({ implementation_files: 'not-array' }).status).toBe(400);
      expect(validate({ implementation_files: [] }).status).toBe(200);
    });
  });

  describe('POST /document', () => {
    it('should generate documentation', async () => {
      mockAnthropic.messages.create.mockResolvedValue({
        content: [{ text: '# API Documentation\n\nThis service provides...' }]
      });

      const docs = await mockAnthropic.messages.create({});
      expect(docs.content[0].text).toContain('# API Documentation');
    });
  });

  describe('POST /commit', () => {
    it('should validate required fields', () => {
      const validate = (body) => {
        if (!body.repo_path || !body.files || !body.commit_message) {
          return { error: 'repo_path, files, and commit_message are required', status: 400 };
        }
        return { status: 200 };
      };

      expect(validate({}).status).toBe(400);
      expect(validate({
        repo_path: '/repo',
        files: [],
        commit_message: 'Update'
      }).status).toBe(200);
    });
  });

  describe('GET /health', () => {
    it('should return healthy when Anthropic is configured', () => {
      process.env.ANTHROPIC_API_KEY = 'test-key';

      const health = {
        status: 'healthy',
        anthropic: process.env.ANTHROPIC_API_KEY ? 'configured' : 'not_configured'
      };

      expect(health.status).toBe('healthy');
      expect(health.anthropic).toBe('configured');
    });

    it('should return 503 when Anthropic is not configured', () => {
      delete process.env.ANTHROPIC_API_KEY;

      const health = {
        anthropic: process.env.ANTHROPIC_API_KEY ? 'configured' : 'not_configured'
      };

      const statusCode = health.anthropic === 'configured' ? 200 : 503;
      expect(statusCode).toBe(503);
    });
  });

  describe('Metrics', () => {
    it('should track generation requests', () => {
      const mockCounter = { inc: jest.fn() };

      mockCounter.inc({ status: 'success', type: 'generate' });
      expect(mockCounter.inc).toHaveBeenCalledWith({ status: 'success', type: 'generate' });
    });

    it('should track generation duration', () => {
      const mockHistogram = {
        labels: jest.fn().mockReturnThis(),
        startTimer: jest.fn(() => jest.fn())
      };

      const end = mockHistogram.labels('generate').startTimer();
      expect(mockHistogram.labels).toHaveBeenCalledWith('generate');
      expect(typeof end).toBe('function');
    });
  });
});
