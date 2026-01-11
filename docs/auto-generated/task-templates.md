# Task Templates Reference

Auto-generated documentation of all available task templates.

> **Note**: This documentation is auto-generated. Do not edit manually.

---

## bug-fix

**Description**: Fix reported bug

**Master**: `development-master`

**Default Priority**: high

**Estimated Duration**: 120 minutes

### Required Fields

- **bug_description**: Clear description of the bug
- **steps_to_reproduce**: Step-by-step instructions to reproduce the bug

### Optional Fields

- **affected_versions**: Versions where this bug exists
- **severity**: Bug severity: critical, high, medium, low
- **expected_behavior**: What should happen
- **actual_behavior**: What actually happens
- **error_logs**: Relevant error logs or stack traces

### Usage Examples

#### Example 1: Fix authentication timeout bug

```json
{
  "bug_description": "Users are logged out unexpectedly after 5 minutes",
  "steps_to_reproduce": "1. Login to app, 2. Wait 5 minutes, 3. Try to access protected resource",
  "severity": "high",
  "expected_behavior": "Session should last 30 minutes",
  "actual_behavior": "Session expires after 5 minutes"
}
```

---

## dependency-update

**Description**: Update dependencies or packages

**Master**: `inventory-master`

**Default Priority**: medium

**Estimated Duration**: 60 minutes

### Required Fields

- **package_manager**: Package manager: npm, yarn, pip, cargo, go, maven
- **update_type**: Update type: patch, minor, major, security-only

### Optional Fields

- **specific_packages**: Comma-separated list of specific packages to update
- **target_version**: Target version for specific package
- **include_dev_dependencies**: Update dev dependencies too (true/false)
- **run_tests_after**: Run tests after updates (true/false)

### Usage Examples

#### Example 1: Security updates for npm packages

```json
{
  "package_manager": "npm",
  "update_type": "security-only",
  "run_tests_after": "true"
}
```

#### Example 2: Update specific package

```json
{
  "package_manager": "npm",
  "update_type": "minor",
  "specific_packages": "express,lodash",
  "include_dev_dependencies": "false",
  "run_tests_after": "true"
}
```

---

## deployment

**Description**: Deploy application or service

**Master**: `coordinator-master`

**Default Priority**: high

**Estimated Duration**: 45 minutes

### Required Fields

- **application_name**: Name of the application to deploy
- **environment**: Target environment: development, staging, production
- **version**: Version or commit SHA to deploy

### Optional Fields

- **deployment_strategy**: Strategy: rolling, blue-green, canary
- **rollback_plan**: Rollback strategy if deployment fails
- **health_checks**: Health check endpoints to verify deployment
- **notification_channels**: Where to send deployment notifications (slack, email)

### Usage Examples

#### Example 1: Deploy API to production

```json
{
  "application_name": "cortex-api",
  "environment": "production",
  "version": "v2.1.0",
  "deployment_strategy": "blue-green",
  "health_checks": "/api/health,/api/ready"
}
```

#### Example 2: Canary deployment to staging

```json
{
  "application_name": "web-app",
  "environment": "staging",
  "version": "abc123def",
  "deployment_strategy": "canary",
  "notification_channels": "slack"
}
```

---

## documentation

**Description**: Create or update documentation

**Master**: `inventory-master`

**Default Priority**: medium

**Estimated Duration**: 90 minutes

### Required Fields

- **documentation_type**: Type: api, user-guide, developer-guide, architecture, changelog
- **target_component**: Component or module to document

### Optional Fields

- **output_format**: Output format: markdown, html, pdf, confluence
- **include_examples**: Include code examples (true/false)
- **audience**: Target audience: developers, end-users, operators
- **languages**: Programming languages to include in examples

### Usage Examples

#### Example 1: Document REST API endpoints

```json
{
  "documentation_type": "api",
  "target_component": "user-service",
  "output_format": "markdown",
  "include_examples": "true",
  "audience": "developers"
}
```

#### Example 2: Create user guide

```json
{
  "documentation_type": "user-guide",
  "target_component": "cortex-cli",
  "output_format": "markdown",
  "include_examples": "true",
  "audience": "end-users"
}
```

---

## feature-implementation

**Description**: Implement new feature

**Master**: `development-master`

**Default Priority**: medium

**Estimated Duration**: 240 minutes

### Required Fields

- **feature_description**: Detailed description of the feature to implement
- **acceptance_criteria**: List of criteria that define when the feature is complete

### Optional Fields

- **affected_components**: Components or modules that will be modified
- **breaking_changes**: Whether this introduces breaking changes (true/false)
- **target_version**: Target version for this feature (e.g., v2.1.0)
- **dependencies**: External dependencies required for this feature

### Usage Examples

#### Example 1: Implement user authentication

```json
{
  "feature_description": "Add JWT-based authentication with refresh tokens",
  "acceptance_criteria": "Users can login, logout, tokens refresh automatically, sessions persist",
  "affected_components": "auth-service, user-service, api-gateway",
  "breaking_changes": "false"
}
```

#### Example 2: Add GraphQL API endpoint

```json
{
  "feature_description": "Create GraphQL endpoint for querying user data",
  "acceptance_criteria": "GraphQL schema defined, queries work, mutations work, subscriptions enabled",
  "dependencies": "apollo-server, graphql",
  "target_version": "v2.0.0"
}
```

---

## security-scan

**Description**: Run security vulnerability scan

**Master**: `security-master`

**Default Priority**: high

**Estimated Duration**: 30 minutes

### Required Fields

- **target_repository**: Repository path or URL to scan
- **scan_type**: Type of scan: full, quick, dependencies, or code

### Optional Fields

- **severity_threshold**: Minimum severity to report (low, medium, high, critical)
- **exclude_paths**: Comma-separated paths to exclude from scan
- **output_format**: Output format: json, sarif, or markdown

### Usage Examples

#### Example 1: Full security scan of main repository

```json
{
  "target_repository": "/Users/ryandahlberg/Projects/cortex",
  "scan_type": "full",
  "severity_threshold": "medium"
}
```

#### Example 2: Quick dependency scan

```json
{
  "target_repository": "/Users/ryandahlberg/Projects/myapp",
  "scan_type": "dependencies",
  "output_format": "json"
}
```

---

