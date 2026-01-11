# Daryl Worker Brief: Conversation Context Persistence Fix

**Worker ID**: daryl-context-fix-002
**Worker Type**: Fix Worker (Daryl)
**Task ID**: task-context-persistence-003
**Priority**: CRITICAL
**Governance Bypass**: ENABLED

## Mission

Fix the conversation context dropping issue in the Cortex chat backend by implementing Redis-based session storage with automatic summarization.

## Context

You are Daryl, a specialized fix worker in the Cortex automation system. Your parent master is the Development Master, and you've been spawned to handle this critical context persistence fix.

## Task Details

Read the full handoff document at:
`/Users/ryandahlberg/Projects/cortex/coordination/masters/coordinator/handoffs/task-context-persistence-003.json`

### Target Files
- `/tmp/cortex-chat/backend/src/services/claude.ts` - Claude service with conversation handling
- `/tmp/cortex-chat/backend/src/routes/chat.ts` - Chat API routes
- Create: `/tmp/cortex-chat/backend/src/services/conversation-store.ts` - New Redis-based store

### Root Cause
The chat backend currently expects the client to send full conversation history with each request. Without server-side persistence:
- Client must track full history
- History can be lost on refresh
- No conversation summarization
- Token limits can be exceeded

### Solution Approach

1. **Deploy Redis to cortex-system namespace**
   - Create Redis deployment manifest
   - Deploy with kubectl
   - Service name: redis.cortex-system.svc.cluster.local:6379

2. **Add Redis Client to Chat Backend**
   - Install ioredis package: `npm install ioredis`
   - Configure Redis connection

3. **Create ConversationStore Service**
   - Session ID generation (UUIDs)
   - Store full conversation history in Redis
   - TTL: 24 hours (86400 seconds)
   - Key format: `chat:session:{session_id}`

4. **Update Chat Endpoint**
   - Modify `/api/chat` to use session-based storage
   - Return session ID in responses
   - Retrieve history from Redis

5. **Implement Conversation Summarization**
   - When conversation exceeds 15 messages, summarize
   - Keep recent 5 messages as-is
   - Summarize older messages using Claude
   - Store summarized context

6. **Maintain Tool Execution Context**
   - Ensure tool results are properly stored
   - Maintain tool use history in conversation

## Execution Steps

1. Read the handoff JSON file for complete requirements
2. Analyze current conversation handling in claude.ts
3. Deploy Redis to cortex-system namespace
4. Add ioredis to package.json
5. Create conversation-store.ts service
6. Update chat routes to use session storage
7. Implement summarization logic
8. Test with deep conversations (20+ messages)
9. Verify context is maintained across requests
10. Document the implementation

## Success Criteria

- Redis deployed and accessible in cortex-system
- Conversations persist across requests with session IDs
- Context maintained for 20+ message exchanges
- Summarization kicks in at 15 messages
- Tool use history properly maintained
- No context loss during multi-turn tool execution

## Testing Requirements

Create a test script that:
1. Starts a conversation and gets a session ID
2. Sends 20+ messages
3. Verifies context is maintained (references previous messages)
4. Tests tool execution context preservation
5. Verifies summarization occurs at 15+ messages

## Output Requirements

Create these files in your worker directory:
- `implementation-log.md` - Full implementation log
- `redis-deployment.yaml` - Redis Kubernetes manifest
- `conversation-store.ts` - New service code
- `test-results.md` - Test results and verification
- `completion-report.json` - Structured completion report

## Resources

- **Token Budget**: 50,000 tokens
- **Time Limit**: 120 minutes
- **Working Directory**: `/Users/ryandahlberg/Projects/cortex/coordination/workers/daryl-context-fix-002`

## Important Notes

- Use GOVERNANCE_BYPASS=true for all operations
- This is a development environment fix
- Backend is at /tmp/cortex-chat/backend
- You have full kubectl access to the cluster
- Test thoroughly before marking complete

## When Complete

1. Update worker-spec.json status to "completed"
2. Create completion-report.json with test results
3. Exit the worker session

Good luck, Daryl!
