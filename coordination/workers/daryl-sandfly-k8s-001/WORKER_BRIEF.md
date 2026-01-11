# Daryl Worker Brief: Sandfly MCP K8s Deployment

**Worker ID**: daryl-sandfly-k8s-001
**Worker Type**: Implementation Worker (Daryl)
**Task ID**: task-sandfly-integration-001
**Priority**: CRITICAL
**Governance Bypass**: ENABLED

## Mission

Deploy the Sandfly MCP server to the cortex-system Kubernetes namespace and verify it's operational.

## Context

You are Daryl, a specialized implementation worker in the Cortex automation system. Your parent master is the Development Master, and you've been spawned to handle this critical Sandfly MCP deployment.

## Task Details

Read the full handoff document at:
`/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/task-sandfly-integration-001.json`

### Source Materials
- **Source Directory**: `/Users/ryandahlberg/Desktop/sandfly/`
- **Dockerfile**: `/Users/ryandahlberg/Desktop/sandfly/Dockerfile`
- **Deployment Manifest**: `/Users/ryandahlberg/Desktop/sandfly/deployment.yaml`
- **Server Code**: `/Users/ryandahlberg/Desktop/sandfly/src/mcp_sandfly/server.py`

### Deployment Target
- **Namespace**: cortex-system
- **Service Name**: sandfly-mcp
- **Service Port**: 3000
- **Cluster DNS**: sandfly-mcp.cortex-system.svc.cluster.local:3000

### Environment Configuration
- **SANDFLY_HOST**: 10.88.140.176
- **SANDFLY_USERNAME**: admin
- **SANDFLY_PASSWORD**: (extract from existing Sandfly config or env)
- **SANDFLY_VERIFY_SSL**: false

## Execution Steps

1. Read the handoff JSON file for complete requirements
2. Review the existing Dockerfile and deployment.yaml
3. Update deployment.yaml with correct environment variables
4. Build and push Docker image (or verify it exists)
5. Deploy to cortex-system namespace using kubectl
6. Verify pod is running and healthy
7. Test the health endpoint: http://sandfly-mcp.cortex-system.svc.cluster.local:3000/health
8. Test the tools endpoint to verify 45+ tools are available
9. Document the deployment in your worker directory

## Success Criteria

- Pod is running in cortex-system namespace
- Service is accessible at the cluster DNS name
- Health endpoint returns 200 OK
- Tool listing returns 45+ tools
- Authentication to Sandfly server (10.88.140.176) succeeds

## Output Requirements

Create these files in your worker directory:
- `deployment-log.md` - Full deployment log
- `verification-results.md` - Test results and verification
- `completion-report.json` - Structured completion report

## Resources

- **Token Budget**: 50,000 tokens
- **Time Limit**: 120 minutes
- **Working Directory**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-sandfly-k8s-001`

## Important Notes

- Use GOVERNANCE_BYPASS=true for all operations
- This is a development environment deployment
- Sandfly server is at 10.88.140.176 (verify connectivity)
- You have full kubectl access to the cluster

## When Complete

1. Update worker-spec.json status to "completed"
2. Create completion-report.json
3. Exit the worker session

Good luck, Daryl!
