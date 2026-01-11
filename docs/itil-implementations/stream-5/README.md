# ITIL Stream 5: Service Desk & Request Management

## Overview

Stream 5 implements AI-powered Service Desk and Intelligent Request Fulfillment capabilities for Cortex, providing conversational AI assistance and automated request processing.

## Components Implemented

### 1. Conversational AI Service Desk (Recommendation #15)

An intelligent service desk powered by NLP and machine learning that provides:

- **Natural Language Processing**: Intent detection and entity extraction using spaCy and Transformers
- **Multi-Channel Support**: Web portal, API, WebSocket chat, and future integrations (email, Slack)
- **Sentiment Analysis**: Understands user sentiment to prioritize urgent requests
- **Contextual Conversations**: Maintains session context for multi-turn dialogues
- **Service Catalog Integration**: Automatically routes to appropriate services

**Key Features:**
- Intent confidence scoring (threshold: 0.75)
- Entity extraction (persons, orgs, dates, products)
- Multi-language support (en, es, fr, de, ja)
- Real-time chat with WebSocket
- Session management with Redis

### 2. Intelligent Request Fulfillment System (Recommendation #16)

An automated workflow engine that processes service requests with:

- **Automated Workflows**: Pre-defined workflows for common requests
- **Smart Approval Routing**: Dynamic approval based on risk and priority
- **Parallel Execution**: Multiple workflow steps in parallel
- **Retry Logic**: Automatic retry on transient failures
- **Service Catalog**: 6 pre-configured services

**Workflows Implemented:**
1. Access Provisioning
2. Password Reset (Auto)
3. Software Approval & Install
4. Hardware Procurement
5. Network Access Provisioning
6. Security Review & Approval

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Self-Service Portal                      │
│                  (Web UI + Multi-Channel)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┴──────────┐
           │                      │
           ▼                      ▼
┌──────────────────┐   ┌──────────────────────┐
│  AI Service Desk │   │  Fulfillment Engine  │
│   (NLP Engine)   │──▶│  (Workflow Executor) │
└──────────────────┘   └──────────────────────┘
           │                      │
           └──────────┬───────────┘
                      ▼
              ┌──────────────┐
              │    Redis     │
              │ (Queue/State)│
              └──────────────┘
```

## Deployment

### Namespace
- `cortex-service-desk`

### Services Deployed

| Service | Replicas | Resources | Purpose |
|---------|----------|-----------|---------|
| ai-service-desk | 2 | 1Gi RAM, 500m CPU | NLP processing and chat |
| fulfillment-engine | 2 | 512Mi RAM, 250m CPU | Workflow execution |
| self-service-portal | 2 | 128Mi RAM, 100m CPU | Web UI |

### Endpoints

- **Self-Service Portal**: http://service-desk.cortex.local
- **API**: http://api.service-desk.cortex.local
- **Fulfillment**: http://fulfillment.service-desk.cortex.local

### Resource Quotas

- Total CPU: 4 cores (requests), 8 cores (limits)
- Total Memory: 8Gi (requests), 16Gi (limits)
- PVCs: 10

## Service Catalog

| ID | Service | Category | SLA | Auto-Fulfill | Workflow |
|----|---------|----------|-----|--------------|----------|
| srv-001 | Account Access Request | access | 4h | Yes | access-provisioning |
| srv-002 | Password Reset | access | 15m | Yes | password-reset-auto |
| srv-003 | Software Installation | software | 8h | No | software-approval-install |
| srv-004 | Hardware Request | hardware | 24h | No | hardware-procurement |
| srv-005 | Network Access | network | 2h | Yes | network-access-provisioning |
| srv-006 | Security Exception | security | 4h | No | security-review-approval |

## NLP Intents

The AI service desk recognizes these intents with confidence scoring:

1. **password_reset** (0.8 threshold)
   - "reset password", "forgot password", "can't login", "locked out"

2. **access_request** (0.75 threshold)
   - "need access to", "request permission", "get access"

3. **software_install** (0.8 threshold)
   - "install software", "need application", "install program"

4. **hardware_request** (0.75 threshold)
   - "need new laptop", "request hardware", "get equipment"

5. **network_access** (0.8 threshold)
   - "vpn access", "remote access", "connect to network"

## Workflow Engine

### Workflow Steps

Each workflow consists of configurable steps:

1. **Validation**: Verify required fields and prerequisites
2. **Approval**: Route for approval (auto or manual)
3. **Execution**: Perform the requested action
4. **Verification**: Confirm successful completion
5. **Notification**: Notify user of status

### Auto-Approval Logic

Requests are auto-approved when:
- Service has `auto_fulfill: true`
- Workflow has `auto_approve: true`
- Priority is low or medium (with threshold setting)
- Risk assessment is low

### Example Workflows

**Password Reset (Automated)**
```yaml
1. Validate user identity
2. Auto-approve
3. Reset password
4. Send secure notification with temp password
```

**Software Installation (Approval Required)**
```yaml
1. Validate software request
2. Check license availability
3. Security scan
4. Manager approval
5. IT admin approval
6. Install software
7. Verify installation
8. Notify user
```

## API Reference

### Create Session
```bash
POST /api/v1/session
{
  "user_id": "string",
  "channel": "api|web|chat|email|slack"
}

Response:
{
  "session_id": "string",
  "message": "Welcome message"
}
```

### Send Message
```bash
POST /api/v1/message
{
  "session_id": "string",
  "message": "string"
}

Response:
{
  "message": "string",
  "service": {...},
  "request_id": "string",
  "suggestions": [...]
}
```

### Get Service Catalog
```bash
GET /api/v1/catalog

Response:
{
  "version": "1.0",
  "services": [...]
}
```

### Get Request Status
```bash
GET /api/v1/request/{request_id}

Response:
{
  "request_id": "string",
  "status": "pending|in_progress|completed|failed",
  "service_id": "string",
  "created_at": "ISO8601",
  "completed_at": "ISO8601"
}
```

### Approve Request
```bash
POST /api/v1/approve/{request_id}
{
  "approver": "string"
}
```

## Metrics & Monitoring

### Prometheus Metrics

**Service Desk Metrics:**
- `service_desk_requests_total{intent, channel}` - Total requests by intent and channel
- `service_desk_intent_confidence` - Intent detection confidence scores
- `service_desk_response_time_seconds` - Response time histogram
- `service_desk_active_sessions` - Active chat sessions

**Fulfillment Metrics:**
- `fulfillment_requests_total{workflow, status}` - Total fulfillment requests
- `fulfillment_duration_seconds{workflow}` - Fulfillment duration by workflow
- `fulfillment_active_workflows` - Currently executing workflows
- `fulfillment_approval_pending` - Requests pending approval
- `fulfillment_auto_fulfilled_total{service}` - Auto-fulfilled requests

### Service Monitor

A ServiceMonitor is configured for Prometheus scraping:
```yaml
selector:
  app: ai-service-desk
endpoints:
  - port: metrics
    interval: 30s
```

## Configuration

### Environment Variables

**AI Service Desk:**
- `NLP_MODEL`: distilbert-base-uncased-finetuned-sst-2-english
- `CONFIDENCE_THRESHOLD`: 0.75
- `REDIS_HOST`: redis.cortex-system.svc.cluster.local
- `REDIS_PORT`: 6379

**Fulfillment Engine:**
- `AUTO_APPROVE_THRESHOLD`: low|medium|high
- `WORKFLOW_TIMEOUT`: 3600 seconds
- `RETRY_ATTEMPTS`: 3

### ConfigMap Settings

Key configuration options in `service-desk-config`:
- NLP settings (confidence, entity extraction, sentiment analysis)
- Service catalog configuration
- Fulfillment automation rules
- Multi-channel settings
- Metrics and analytics options

## Testing

### Run Test Suite

```bash
/Users/ryandahlberg/Projects/cortex/k8s/itil/service-desk/test-service-desk.sh
```

The test suite validates:
1. Health checks
2. Service catalog retrieval
3. Session creation
4. NLP intent detection (password reset, access request, VPN)
5. Fulfillment engine workflows
6. Redis queue processing
7. Metrics collection

### Manual Testing

**Create a session:**
```bash
kubectl exec -n cortex-service-desk deployment/ai-service-desk -- \
  curl -X POST http://localhost:5000/api/v1/session \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "channel": "cli"}'
```

**Send a message:**
```bash
kubectl exec -n cortex-service-desk deployment/ai-service-desk -- \
  curl -X POST http://localhost:5000/api/v1/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "message": "I need to reset my password"}'
```

## Self-Service Portal

The web-based self-service portal provides:

### Features

1. **AI Chat Interface**
   - Real-time conversational AI
   - Message history
   - Typing indicators
   - Suggestion chips

2. **Service Catalog Browser**
   - Categorized services
   - SLA information
   - One-click service requests

3. **Request Tracking**
   - View request status
   - Request history
   - Progress tracking

4. **Quick Actions**
   - Password reset
   - Access requests
   - VPN access

### Access

Access via ingress at: `http://service-desk.cortex.local`

## Security Considerations

1. **Authentication**: Sessions are tracked but not authenticated (add SSO/OAuth)
2. **Authorization**: No RBAC implemented (add role-based access)
3. **Encryption**: TLS should be enabled for production
4. **Audit Logging**: All requests are logged to Redis
5. **Approval Workflows**: Manual approval required for high-risk requests

## Future Enhancements

1. **Additional Channels**
   - Email integration
   - Slack/Teams bot
   - Mobile app

2. **Advanced NLP**
   - Multi-language conversations
   - Sentiment-based prioritization
   - Intent chaining for complex requests

3. **ML Improvements**
   - Fine-tuned models on historical data
   - Predictive request routing
   - Automated categorization

4. **Workflow Extensions**
   - Custom workflow builder
   - Conditional branching
   - External system integrations (AD, HR systems, etc.)

5. **Analytics**
   - Resolution time tracking
   - Customer satisfaction surveys
   - Trending issue detection

## Troubleshooting

### AI Service Desk not responding

Check pod logs:
```bash
kubectl logs -n cortex-service-desk deployment/ai-service-desk
```

Common issues:
- NLP models still downloading (wait 3-5 minutes)
- Redis connection failure
- Memory limits exceeded

### Fulfillment not processing

Check queue length:
```bash
kubectl exec -n cortex-system deployment/redis -- redis-cli llen fulfillment:queue
```

Check fulfillment logs:
```bash
kubectl logs -n cortex-service-desk deployment/fulfillment-engine
```

### Portal not loading

Check nginx logs:
```bash
kubectl logs -n cortex-service-desk deployment/self-service-portal
```

Verify service endpoints:
```bash
kubectl get svc -n cortex-service-desk
kubectl get ingress -n cortex-service-desk
```

## Support

For issues or questions:
- Check logs: `kubectl logs -n cortex-service-desk <pod>`
- View metrics: Access Prometheus/Grafana
- Review documentation: This file and API docs

## References

- [ITIL Service Desk Best Practices](https://www.axelos.com/certifications/itil-service-management)
- [NLP with spaCy](https://spacy.io/)
- [Transformers Documentation](https://huggingface.co/docs/transformers)
- [Workflow Automation Patterns](https://www.enterpriseintegrationpatterns.com/)
