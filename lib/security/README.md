# Cortex Security Module

Comprehensive security features to protect Cortex against prompt injection attacks and unauthorized operations.

## Overview

This security module implements a 5-layer defense strategy inspired by security research from Bugcrowd's "The Promptfather" guide:

1. **Input Validation** - Detect and block prompt injection attempts
2. **Access Control** - Restrict file, network, and command operations
3. **Audit Logging** - Track all security events
4. **Anomaly Detection** - Identify suspicious patterns
5. **Human Review** - Flag high-risk operations

## Modules

### Prompt Injection Detector

Analyzes task descriptions for malicious injection attempts.

```javascript
const { PromptInjectionDetector } = require('./prompt-injection-detector');

const detector = new PromptInjectionDetector();

// Analyze a task description
const result = detector.analyze("Fix authentication bug");

console.log(result);
// {
//   safe: true,
//   riskScore: 0,
//   severity: 'none',
//   threats: [],
//   recommendation: 'ALLOW - No threats detected'
// }
```

**Detected Threats:**
- Instruction override attempts (`ignore previous instructions`)
- System mode manipulation (`system override`)
- Context boundary manipulation (`---END OF USER INPUT---`)
- Privilege escalation (`admin mode`)
- Data exfiltration (external URLs in markdown images)
- Encoding attempts (`base64`, `atob`)
- Credential access (`.env`, `secrets`)
- Destructive operations (`rm -rf`, `delete all`)

### Access Control

Restricts operations to whitelisted resources.

```javascript
const { AccessControl } = require('./access-control');

const acl = new AccessControl();

// Check file read permission
const canRead = acl.canReadFile('src/index.js');
console.log(canRead);
// { allowed: true }

// Check blocked file
const canReadEnv = acl.canReadFile('.env');
console.log(canReadEnv);
// { allowed: false, reason: 'File matches blocked pattern' }

// Check git remote
const canPush = acl.canAccessGitRemote('github.com/ry-ops/cortex');
console.log(canPush);
// { allowed: true }
```

**Access Restrictions:**
- **File Read**: Limited to `src/`, `lib/`, `docs/`, `coordination/`
- **File Write**: More restrictive, excludes config files
- **Blocked Files**: `.env`, credentials, secrets, keys
- **Git Remotes**: Only `github.com/ry-ops/*`
- **Network**: Only localhost and github.com
- **Commands**: Blocks `rm -rf`, `dd`, fork bombs, etc.

## Integration Example

### In Coordinator

```javascript
const { PromptInjectionDetector } = require('./lib/security/prompt-injection-detector');
const { AccessControl } = require('./lib/security/access-control');

class Coordinator {
  constructor() {
    this.securityDetector = new PromptInjectionDetector();
    this.accessControl = new AccessControl();
  }

  async submitTask(taskData) {
    // Step 1: Validate input for prompt injection
    const validation = this.securityDetector.validate(taskData.description);

    if (!validation.valid) {
      throw new SecurityError(
        `Task blocked: ${validation.analysis.recommendation}`,
        { threats: validation.analysis.threats }
      );
    }

    // Step 2: Continue with normal task processing
    // ...
  }
}
```

### In Worker

```javascript
class Worker {
  constructor(config) {
    this.accessControl = new AccessControl();
  }

  async readFile(filepath) {
    // Check permission before reading
    const permission = this.accessControl.canReadFile(filepath);

    if (!permission.allowed) {
      throw new AccessDeniedError(permission.reason);
    }

    // Read file
    return fs.readFileSync(filepath, 'utf8');
  }
}
```

## Security Audit Log

All security events are logged to `coordination/governance/access-log.jsonl`:

```jsonl
{"timestamp":"2025-11-26T10:00:00Z","event":"prompt_injection_blocked","task_id":"task-001","severity":"high","threats":[...]}
{"timestamp":"2025-11-26T10:01:00Z","event":"access_denied","worker_id":"worker-001","operation":"file_read","target":".env","reason":"blocked pattern"}
{"timestamp":"2025-11-26T10:02:00Z","event":"external_network_blocked","worker_id":"worker-002","target":"attacker.com"}
```

## Configuration

### Custom Access Control Rules

```javascript
const acl = new AccessControl({
  allowedReadPaths: [
    'src/**',
    'custom-dir/**'
  ],
  allowedWritePaths: [
    'output/**'
  ],
  blockedPatterns: [
    '.env',
    'credentials*',
    'my-secrets/**'
  ],
  allowedGitRemotes: [
    'github.com/my-org/*'
  ]
});
```

### Detection Sensitivity

```javascript
const detector = new PromptInjectionDetector();

// Validate with custom options
const result = detector.validate(taskDescription, {
  blockOnHigh: true,       // Block high-severity threats
  blockOnCritical: true,   // Block critical threats
  requireReviewOnMedium: true  // Flag medium threats for review
});
```

## Testing

Run security tests:

```bash
npm test lib/security/
```

## References

- [The Promptfather: An Offer AI Can't Refuse](https://www.bugcrowd.com/resources/levelup/the-promptfather-an-offer-ai-cant-refuse/)
- OWASP LLM Top 10
- Prompt Injection Handbook
- AI Security Best Practices

## License

MIT
