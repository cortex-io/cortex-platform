# Sandfly Security - K3s Deployment Summary

## Overview

Sandfly Security is an agentless intrusion detection and incident response platform for Linux that detects threats without requiring software agents on target systems. This document outlines the requirements and approach for deploying Sandfly in a K3s cluster.

## Important Notes

**Sandfly is NOT designed for native Kubernetes deployment.** As of 2025, there are no official Kubernetes manifests, Helm charts, or K3s-specific deployment guides from Sandfly Security. The platform is architected for Docker/Podman container deployment.

## Architecture

### Components

1. **Core Server**
   - Web UI
   - REST API (JWT bearer token authentication, 60-minute token validity)
   - PostgreSQL database
   - Multi-threaded scanning engines

2. **Scanning Nodes**
   - Perform remote system checks via SSH
   - Deploy "sandflies" (security agents) to remote hosts
   - Can be distributed across isolated networks
   - Communicate back to central server

3. **Optional Remote Database**
   - Supports distributed, fault-tolerant database clusters

### Deployment Models

- **Single Node**: One scanning node + central server
- **Multiple Nodes**: Distributed nodes across networks/clouds
- **Jump Host Support**: Nodes access isolated networks through SSH

## K3s Deployment Approach

Since Sandfly lacks native Kubernetes support, we have two options:

### Option 1: Docker-in-Docker (Quick Start)
Deploy Sandfly's official Docker containers as pods within K3s using Docker-in-Docker or Podman-in-Pod pattern.

**Pros:**
- Uses official Sandfly containers
- Faster deployment
- Official support from Sandfly

**Cons:**
- Not cloud-native
- Requires privileged containers
- Less efficient resource usage

### Option 2: Kubernetes-Native Conversion (Advanced)
Convert Sandfly's Docker Compose architecture to Kubernetes manifests.

**Pros:**
- True cloud-native deployment
- Better resource management
- K8s-native scaling and networking

**Cons:**
- Unsupported by Sandfly
- Requires reverse-engineering container architecture
- Maintenance burden on updates

## Recommended Deployment Strategy

**Use Option 1** for production deployments to maintain vendor support.

### Requirements

#### Infrastructure
- **Core Server**:
  - 2+ CPU cores
  - 4GB+ RAM
  - 20GB+ storage (database grows with scan results)
  - Ports: 8080 (UI/API), 5432 (PostgreSQL)

- **Scanning Nodes**:
  - 1+ CPU core per node
  - 2GB+ RAM per node
  - Network connectivity to target systems via SSH (port 22)

#### Network Requirements
- SSH access to all target Linux systems
- Outbound connectivity from scanning nodes
- Service mesh integration for internal cluster scanning

#### Credentials
- SSH keys or username/password for target systems
- API credentials stored in Kubernetes secrets

## API Capabilities

Sandfly provides a comprehensive REST API (v5.5.0+) with the following capabilities:

### Authentication
- JWT bearer tokens (60-minute validity)
- Token refresh endpoint
- Token revocation on logout

### Core Operations
- **Notifications**: Email alerts, syslog, notification management
- **Users & Access**: User management, SSO, password updates
- **Hosts**: Add/delete/update, bulk tagging, host rollup data
- **Scanning**: Initiate scans, view logs, manage schedules
- **Results**: Query findings, create timelines, manage profiles
- **Credentials**: Encrypted credential storage
- **Configuration**: Server settings, threat feeds, whitelists, SSH zones
- **Host Information**: Processes, users, services, network listeners, kernel modules
- **Reports**: Host snapshots, scan performance metrics

## Integration with Cortex

### MCP Server Integration
The Sandfly MCP server will expose:
- Host management and scanning operations
- Security findings and alerts
- Scan scheduling and execution
- Forensic data collection
- Integration with Cortex's security master

### Use Cases
1. **K3s Node Security**: Scan all K3s worker nodes for compromise
2. **Container Host Monitoring**: Monitor the infrastructure running containers
3. **Incident Response**: Rapid forensic data collection across fleet
4. **Compliance**: Continuous security posture assessment
5. **Threat Hunting**: Proactive search for indicators of compromise

## Deployment Steps

### 1. Obtain Sandfly License
- Contact Sandfly Security for licensing
- Obtain Docker registry credentials

### 2. Create Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: sandfly-credentials
  namespace: cortex-system
type: Opaque
data:
  api-token: <base64-encoded-jwt-token>
  postgres-password: <base64-encoded-password>
```

### 3. Deploy Core Server
- PostgreSQL StatefulSet
- Sandfly Server Deployment
- ClusterIP Services for internal access
- Ingress for external UI/API access

### 4. Deploy Scanning Nodes
- Deployment with configurable replicas
- ConfigMap for target system inventory
- SSH credential secrets

### 5. Configure Target Scanning
- Add K3s nodes as scan targets
- Configure scan schedules
- Set up alert notifications

### 6. Deploy MCP Server
- Sandfly MCP client Deployment
- Service exposure to Cortex ecosystem
- Integration with master coordination

## Monitoring & Maintenance

### Health Checks
- API endpoint availability
- Database connectivity
- Scanning node status
- Target system reachability

### Alerting
- Failed scans
- Detection of threats
- System errors
- License expiration

### Updates
- Follow Sandfly's release cadence
- Test updates in staging environment
- Rolling updates for zero-downtime

## Security Considerations

1. **Credential Management**: Store SSH keys and API tokens in Kubernetes secrets
2. **Network Policies**: Restrict scanning node egress to necessary targets
3. **RBAC**: Limit API access via Kubernetes service accounts
4. **Audit Logging**: Enable comprehensive audit trails
5. **TLS**: Use TLS for all API communications

## Cost Considerations

- Sandfly is a commercial product requiring licensing
- Costs scale with number of monitored hosts
- API usage may have rate limits
- Storage grows with scan results and forensic data

## References

- [Sandfly Security](https://sandflysecurity.com/)
- [Sandfly API Documentation](https://docs.sandflysecurity.com/reference/api-landing-page)
- [Sandfly GitHub](https://github.com/sandflysecurity/sandfly-setup)
- [Installation Overview](https://docs.sandflysecurity.com/docs/installation-overview)
- [REST API Announcement](https://sandflysecurity.com/blog/sandfly-rest-api-published)

## Next Steps

1. Contact Sandfly for licensing and trial access
2. Review target system inventory (K3s nodes, LXC containers, VMs)
3. Design network topology for scanning node placement
4. Create Kubernetes manifests for deployment
5. Implement MCP server integration
6. Test in staging environment
7. Deploy to production with monitoring
