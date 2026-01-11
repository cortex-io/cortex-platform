// Mock LLM API for testing
// Use with nock or similar HTTP mocking library

const nock = require('nock');

class LLMApiMock {
  constructor(baseUrl = 'http://localhost:11434') {
    this.baseUrl = baseUrl;
    this.scope = nock(baseUrl);
  }

  /**
   * Mock text completion
   */
  mockCompletion(prompt, response = {}) {
    const defaultResponse = {
      model: 'llama2',
      created_at: new Date().toISOString(),
      response: response.text || 'Generated code output',
      done: true,
      context: [1, 2, 3],
      total_duration: 1000000000,
      load_duration: 500000000,
      prompt_eval_duration: 200000000,
      eval_duration: 300000000,
      ...response
    };

    return this.scope
      .post('/api/generate', {
        model: 'llama2',
        prompt: prompt,
        stream: false
      })
      .reply(200, defaultResponse);
  }

  /**
   * Mock streaming completion
   */
  mockStreamingCompletion(prompt, chunks = []) {
    const defaultChunks = chunks.length > 0 ? chunks : [
      { response: 'Generated ', done: false },
      { response: 'code ', done: false },
      { response: 'output', done: true }
    ];

    return this.scope
      .post('/api/generate', {
        model: 'llama2',
        prompt: prompt,
        stream: true
      })
      .reply(200, () => {
        return defaultChunks.map(chunk => JSON.stringify(chunk)).join('\n');
      });
  }

  /**
   * Mock chat completion
   */
  mockChatCompletion(messages, response = {}) {
    const defaultResponse = {
      model: 'llama2',
      created_at: new Date().toISOString(),
      message: {
        role: 'assistant',
        content: response.content || 'This is a generated response'
      },
      done: true,
      ...response
    };

    return this.scope
      .post('/api/chat', {
        model: 'llama2',
        messages: messages
      })
      .reply(200, defaultResponse);
  }

  /**
   * Mock embeddings generation
   */
  mockEmbeddings(text, embedding = []) {
    const defaultEmbedding = embedding.length > 0 ? embedding : Array(768).fill(0.1);

    return this.scope
      .post('/api/embeddings', {
        model: 'llama2',
        prompt: text
      })
      .reply(200, {
        embedding: defaultEmbedding
      });
  }

  /**
   * Mock model list
   */
  mockListModels(models = []) {
    const defaultModels = models.length > 0 ? models : [
      {
        name: 'llama2',
        modified_at: '2025-01-09T00:00:00Z',
        size: 3826793677,
        digest: 'abc123'
      }
    ];

    return this.scope
      .get('/api/tags')
      .reply(200, { models: defaultModels });
  }

  /**
   * Mock model info
   */
  mockModelInfo(modelName = 'llama2', info = {}) {
    const defaultInfo = {
      modelfile: 'FROM llama2',
      parameters: 'temperature 0.7',
      template: '{{ .Prompt }}',
      ...info
    };

    return this.scope
      .post('/api/show', { name: modelName })
      .reply(200, defaultInfo);
  }

  /**
   * Mock code generation specific response
   */
  mockCodeGeneration(prompt, code = '') {
    const defaultCode = code || `
function example() {
  // Generated code
  console.log('Hello, World!');
}
    `.trim();

    return this.mockCompletion(prompt, {
      text: defaultCode,
      response: defaultCode
    });
  }

  /**
   * Mock error response
   */
  mockError(statusCode = 500, message = 'Internal Server Error') {
    return this.scope
      .post(/\/api\/.*/)
      .reply(statusCode, {
        error: message
      });
  }

  /**
   * Clean up all mocks
   */
  cleanup() {
    nock.cleanAll();
  }
}

module.exports = LLMApiMock;
