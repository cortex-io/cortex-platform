// Mock GitHub API for testing
// Use with nock or similar HTTP mocking library

const nock = require('nock');

const GITHUB_API_BASE = 'https://api.github.com';

class GitHubApiMock {
  constructor() {
    this.scope = nock(GITHUB_API_BASE);
  }

  /**
   * Mock repository information
   */
  mockGetRepository(owner, repo, data = {}) {
    const defaultData = {
      id: 123456789,
      name: repo,
      full_name: `${owner}/${repo}`,
      private: false,
      description: 'Test repository',
      language: 'JavaScript',
      default_branch: 'main',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-09T00:00:00Z',
      ...data
    };

    return this.scope
      .get(`/repos/${owner}/${repo}`)
      .reply(200, defaultData);
  }

  /**
   * Mock list issues
   */
  mockListIssues(owner, repo, issues = []) {
    const defaultIssues = issues.length > 0 ? issues : [
      {
        id: 1,
        number: 42,
        title: 'Test Issue',
        state: 'open',
        body: 'This is a test issue description',
        user: {
          login: 'testuser',
          id: 1
        },
        labels: [{ name: 'bug' }],
        created_at: '2025-01-09T00:00:00Z',
        updated_at: '2025-01-09T00:00:00Z'
      }
    ];

    return this.scope
      .get(`/repos/${owner}/${repo}/issues`)
      .reply(200, defaultIssues);
  }

  /**
   * Mock get single issue
   */
  mockGetIssue(owner, repo, issueNumber, data = {}) {
    const defaultData = {
      id: 1,
      number: issueNumber,
      title: 'Test Issue',
      state: 'open',
      body: 'This is a test issue description',
      user: {
        login: 'testuser',
        id: 1
      },
      labels: [{ name: 'bug' }],
      created_at: '2025-01-09T00:00:00Z',
      updated_at: '2025-01-09T00:00:00Z',
      ...data
    };

    return this.scope
      .get(`/repos/${owner}/${repo}/issues/${issueNumber}`)
      .reply(200, defaultData);
  }

  /**
   * Mock create issue comment
   */
  mockCreateComment(owner, repo, issueNumber, commentBody) {
    return this.scope
      .post(`/repos/${owner}/${repo}/issues/${issueNumber}/comments`, {
        body: commentBody
      })
      .reply(201, {
        id: 123,
        body: commentBody,
        user: { login: 'cortex-bot' },
        created_at: new Date().toISOString()
      });
  }

  /**
   * Mock repository contents
   */
  mockGetContents(owner, repo, path, content = {}) {
    const defaultContent = {
      name: path.split('/').pop(),
      path: path,
      type: 'file',
      size: 1024,
      content: Buffer.from('test content').toString('base64'),
      encoding: 'base64',
      ...content
    };

    return this.scope
      .get(`/repos/${owner}/${repo}/contents/${path}`)
      .reply(200, defaultContent);
  }

  /**
   * Mock directory contents
   */
  mockGetDirectory(owner, repo, path, files = []) {
    const defaultFiles = files.length > 0 ? files : [
      {
        name: 'README.md',
        path: `${path}/README.md`,
        type: 'file',
        size: 1024
      },
      {
        name: 'src',
        path: `${path}/src`,
        type: 'dir'
      }
    ];

    return this.scope
      .get(`/repos/${owner}/${repo}/contents/${path}`)
      .reply(200, defaultFiles);
  }

  /**
   * Mock authentication check
   */
  mockAuthCheck(authenticated = true) {
    if (authenticated) {
      return this.scope
        .get('/user')
        .reply(200, {
          login: 'testuser',
          id: 1,
          type: 'User'
        });
    } else {
      return this.scope
        .get('/user')
        .reply(401, {
          message: 'Bad credentials'
        });
    }
  }

  /**
   * Clean up all mocks
   */
  cleanup() {
    nock.cleanAll();
  }
}

module.exports = GitHubApiMock;
