#!/usr/bin/env python3
"""
Simple Chat API with Redis persistence and Qdrant Learning
Stores conversations in Redis for persistence across restarts
Uses Qdrant for learning expert routing patterns

Learning Integration:
- Stores improvement evaluation queries with expert assignments
- Learns from successful evaluations to skip LLM for known patterns
- Routing cascade: Similarity → LLM evaluation
"""
import os
import json
import logging
import uuid
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify, make_response
from anthropic import Anthropic
import redis

# Learning imports
LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "true").lower() == "true"
qdrant_learning = None

try:
    from qdrant_learning import (
        QdrantConfig, QdrantLearningClient,
        ExpertRouting, EvaluationOutcome,
        generate_routing_id, generate_outcome_id
    )
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Manual CORS support (no flask_cors dependency)
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200

# Initialize Anthropic client
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    logger.warning("ANTHROPIC_API_KEY not set - chat will return mock responses")
    anthropic_client = None
else:
    anthropic_client = Anthropic(api_key=api_key)

# Redis connection for persistent storage
REDIS_HOST = os.getenv('CORTEX_REDIS_HOST', 'redis.cortex-chat.svc.cluster.local')
_redis_port = os.getenv('CORTEX_REDIS_PORT', '6379')
# Handle Kubernetes service discovery env vars that may contain URLs
if _redis_port.startswith('tcp://'):
    _redis_port = '6379'
REDIS_PORT = int(_redis_port)
REDIS_PASSWORD = os.getenv('CORTEX_REDIS_PASSWORD', 'cortex-redis-password')

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    redis_client.ping()
    logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    USE_REDIS = True
except Exception as e:
    logger.warning(f"Redis connection failed: {e} - falling back to in-memory storage")
    redis_client = None
    USE_REDIS = False

# Fallback in-memory storage (used if Redis unavailable)
conversations = {}
archived_conversations = {}

# Initialize Qdrant learning (async initialization in background)
def init_learning():
    """Initialize Qdrant learning client."""
    global qdrant_learning
    if not LEARNING_ENABLED or not LEARNING_AVAILABLE:
        logger.info("Learning disabled or not available")
        return

    try:
        config = QdrantConfig.from_env()
        qdrant_learning = QdrantLearningClient(config)

        # Run async initialization
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(qdrant_learning.initialize())
        loop.close()

        if success:
            logger.info(f"Qdrant learning initialized at {config.url}")
        else:
            logger.warning("Qdrant not available - using LLM evaluation only")
            qdrant_learning = None
    except Exception as e:
        logger.error(f"Failed to initialize learning: {e}")
        qdrant_learning = None

# Initialize learning on startup
init_learning()

# Redis key prefixes
CONV_PREFIX = "chat:conv:"
ARCHIVED_PREFIX = "chat:archived:"


def redis_get_conversation(conv_id):
    """Get conversation from Redis"""
    if not USE_REDIS:
        return conversations.get(conv_id)
    try:
        data = redis_client.get(f"{CONV_PREFIX}{conv_id}")
        if data:
            return json.loads(data)
        # Check archived
        data = redis_client.get(f"{ARCHIVED_PREFIX}{conv_id}")
        if data:
            conv = json.loads(data)
            conv["status"] = "archived"
            return conv
        return None
    except Exception as e:
        logger.error(f"Redis get error: {e}")
        return conversations.get(conv_id)


def redis_save_conversation(conv):
    """Save conversation to Redis"""
    conv_id = conv["id"]
    if not USE_REDIS:
        conversations[conv_id] = conv
        return
    try:
        redis_client.set(f"{CONV_PREFIX}{conv_id}", json.dumps(conv))
    except Exception as e:
        logger.error(f"Redis save error: {e}")
        conversations[conv_id] = conv


def redis_delete_conversation(conv_id):
    """Delete conversation from Redis"""
    if not USE_REDIS:
        conversations.pop(conv_id, None)
        archived_conversations.pop(conv_id, None)
        return
    try:
        redis_client.delete(f"{CONV_PREFIX}{conv_id}")
        redis_client.delete(f"{ARCHIVED_PREFIX}{conv_id}")
    except Exception as e:
        logger.error(f"Redis delete error: {e}")
        conversations.pop(conv_id, None)
        archived_conversations.pop(conv_id, None)


def redis_archive_conversation(conv_id):
    """Move conversation to archived storage"""
    if not USE_REDIS:
        if conv_id in conversations:
            conv = conversations.pop(conv_id)
            conv["status"] = "archived"
            conv["archived_at"] = datetime.utcnow().isoformat() + "Z"
            archived_conversations[conv_id] = conv
        return
    try:
        data = redis_client.get(f"{CONV_PREFIX}{conv_id}")
        if data:
            conv = json.loads(data)
            conv["status"] = "archived"
            conv["archived_at"] = datetime.utcnow().isoformat() + "Z"
            redis_client.delete(f"{CONV_PREFIX}{conv_id}")
            redis_client.set(f"{ARCHIVED_PREFIX}{conv_id}", json.dumps(conv))
    except Exception as e:
        logger.error(f"Redis archive error: {e}")


def redis_restore_conversation(conv_id):
    """Restore archived conversation"""
    if not USE_REDIS:
        if conv_id in archived_conversations:
            conv = archived_conversations.pop(conv_id)
            conv["status"] = "completed"
            conv.pop("archived_at", None)
            conv["updated_at"] = datetime.utcnow().isoformat() + "Z"
            conversations[conv_id] = conv
        return
    try:
        data = redis_client.get(f"{ARCHIVED_PREFIX}{conv_id}")
        if data:
            conv = json.loads(data)
            conv["status"] = "completed"
            conv.pop("archived_at", None)
            conv["updated_at"] = datetime.utcnow().isoformat() + "Z"
            redis_client.delete(f"{ARCHIVED_PREFIX}{conv_id}")
            redis_client.set(f"{CONV_PREFIX}{conv_id}", json.dumps(conv))
    except Exception as e:
        logger.error(f"Redis restore error: {e}")


def redis_list_conversations(include_archived=False):
    """List all conversations"""
    if not USE_REDIS:
        conv_list = list(conversations.values())
        if include_archived:
            conv_list.extend(archived_conversations.values())
        return conv_list
    try:
        conv_list = []
        # Get active conversations
        for key in redis_client.scan_iter(f"{CONV_PREFIX}*"):
            data = redis_client.get(key)
            if data:
                conv_list.append(json.loads(data))
        # Get archived if requested
        if include_archived:
            for key in redis_client.scan_iter(f"{ARCHIVED_PREFIX}*"):
                data = redis_client.get(key)
                if data:
                    conv = json.loads(data)
                    conv["status"] = "archived"
                    conv_list.append(conv)
        return conv_list
    except Exception as e:
        logger.error(f"Redis list error: {e}")
        conv_list = list(conversations.values())
        if include_archived:
            conv_list.extend(archived_conversations.values())
        return conv_list


def create_new_conversation(conv_id=None, title=None):
    """Create a new conversation with metadata"""
    if conv_id is None:
        conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "id": conv_id,
        "title": title or f"Conversation {conv_id}",
        "messages": [],
        "status": "active",
        "created_at": now,
        "updated_at": now
    }

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "simple-chat-api",
        "anthropic_configured": anthropic_client is not None,
        "redis_connected": USE_REDIS
    }), 200

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple auth endpoint for frontend"""
    data = request.json or {}
    username = data.get('username', 'user')

    # Mock authentication - always succeed
    return jsonify({
        "success": True,
        "token": "mock-token-123",
        "username": username,
        "user": {
            "username": username,
            "id": "user-1"
        }
    }), 200

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations, optionally filtered by status"""
    status_filter = request.args.get('status')  # active, in_progress, completed
    include_archived = request.args.get('include_archived', 'false').lower() == 'true'

    # Get all conversations from Redis or memory
    all_convs = redis_list_conversations(include_archived=include_archived)

    conv_list = []
    for conv in all_convs:
        # Handle legacy format (list of messages)
        if isinstance(conv, list):
            continue  # Skip invalid data

        if status_filter and conv.get("status") != status_filter:
            continue

        last_msg = conv.get("messages", [])[-1] if conv.get("messages") else None
        conv_list.append({
            "id": conv.get("id"),
            "title": conv.get("title", f"Conversation {conv.get('id')}"),
            "status": conv.get("status", "active"),
            "lastMessage": last_msg.get("content", "No messages")[:100] if last_msg else "No messages",
            "messageCount": len(conv.get("messages", [])),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at")
        })

    # Sort by updated_at descending
    conv_list.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return jsonify(conv_list), 200


@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create new conversation"""
    data = request.json or {}
    title = data.get('title')
    conv = create_new_conversation(title=title)
    redis_save_conversation(conv)
    return jsonify(conv), 201


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get a single conversation"""
    conv = redis_get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify(conv), 200


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation permanently"""
    conv = redis_get_conversation(conversation_id)
    if conv:
        redis_delete_conversation(conversation_id)
        logger.info(f"Deleted conversation: {conversation_id}")
        return jsonify({"success": True, "message": f"Conversation {conversation_id} deleted"}), 200
    return jsonify({"error": "Conversation not found"}), 404


@app.route('/api/conversations/<conversation_id>/archive', methods=['POST'])
def archive_conversation(conversation_id):
    """Archive a conversation (move to archived storage)"""
    conv = redis_get_conversation(conversation_id)
    if not conv or conv.get("status") == "archived":
        return jsonify({"error": "Conversation not found"}), 404

    redis_archive_conversation(conversation_id)
    logger.info(f"Archived conversation: {conversation_id}")
    return jsonify({"success": True, "message": f"Conversation {conversation_id} archived"}), 200


@app.route('/api/conversations/<conversation_id>/restore', methods=['POST'])
def restore_conversation(conversation_id):
    """Restore an archived conversation"""
    conv = redis_get_conversation(conversation_id)
    if not conv or conv.get("status") != "archived":
        return jsonify({"error": "Archived conversation not found"}), 404

    redis_restore_conversation(conversation_id)
    logger.info(f"Restored conversation: {conversation_id}")
    return jsonify({"success": True, "message": f"Conversation {conversation_id} restored"}), 200


@app.route('/api/conversations/<conversation_id>/status', methods=['PUT'])
def update_conversation_status(conversation_id):
    """Update conversation status (active, in_progress, completed)"""
    conv = redis_get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.json or {}
    new_status = data.get('status')
    if new_status not in ['active', 'in_progress', 'completed']:
        return jsonify({"error": "Invalid status. Must be: active, in_progress, or completed"}), 400

    conv["status"] = new_status
    conv["updated_at"] = datetime.utcnow().isoformat() + "Z"
    redis_save_conversation(conv)
    logger.info(f"Updated conversation {conversation_id} status to: {new_status}")
    return jsonify(conv), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        message = data.get('message', '')
        conversation_id = data.get('conversation_id', 'default')

        logger.info(f"Chat request: conversation={conversation_id}, message={message[:50]}...")

        now = datetime.utcnow().isoformat() + "Z"

        # Get or create conversation from Redis
        conv = redis_get_conversation(conversation_id)
        if not conv:
            conv = create_new_conversation(conv_id=conversation_id)

        # Store user message
        conv["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": now
        })
        conv["status"] = "in_progress"
        conv["updated_at"] = now

        # Get messages for API call
        api_messages = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]

        # Generate response
        if anthropic_client:
            try:
                # Use Claude for response
                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=api_messages
                )

                assistant_message = response.content[0].text

            except Exception as e:
                logger.error(f"Anthropic API error: {e}")
                assistant_message = f"I'm having trouble connecting to Claude right now. Error: {str(e)}"
        else:
            # Mock response without API key
            assistant_message = f"Echo: {message} (Note: Set ANTHROPIC_API_KEY for real Claude responses)"

        # Store assistant response
        now = datetime.utcnow().isoformat() + "Z"
        conv["messages"].append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": now
        })
        conv["updated_at"] = now

        # Save conversation to Redis
        redis_save_conversation(conv)

        return jsonify({
            "response": assistant_message,
            "conversation_id": conversation_id,
            "status": conv["status"],
            "expert": "general",
            "timestamp": now
        }), 200

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """Get conversation history"""
    conv = redis_get_conversation(conversation_id)
    if not conv:
        return jsonify([]), 200

    messages = conv.get("messages", [])

    result = [
        {
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg.get("timestamp", datetime.utcnow().isoformat() + "Z")
        }
        for msg in messages
    ]
    return jsonify(result), 200


def run_async(coro):
    """Helper to run async code from sync Flask handlers."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.route('/route', methods=['POST'])
def route_improvement():
    """
    MoE Router endpoint - evaluates improvements using Claude with learning

    Routing Cascade:
    1. Similarity lookup (Qdrant) - reuse proven evaluations
    2. LLM evaluation (Claude) - full evaluation for new patterns

    Stores successful evaluations for future similarity matching.
    """
    try:
        improvement = request.json
        if not improvement:
            return jsonify({"error": "No improvement data provided"}), 400

        title = improvement.get('title', 'Untitled')
        description = improvement.get('description', '')
        category = improvement.get('category', 'unknown')
        relevance = improvement.get('relevance', 0.0)
        source_title = improvement.get('source_title', 'Unknown')
        improvement_type = improvement.get('type', 'unknown')

        # Build query text for similarity search
        query_text = f"{title} {description} {category}"
        routing_id = generate_routing_id() if LEARNING_AVAILABLE else None
        routing_method = "llm"

        logger.info(f"Routing improvement: {title[:50]}...")

        # Path 1: Try similarity-based routing if learning is enabled
        if qdrant_learning:
            try:
                similar = run_async(qdrant_learning.find_similar_routing(query_text))
                if similar:
                    logger.info(f"Similar routing found: {similar.expert} (similarity: {similar.similarity:.2f})")
                    routing_method = "similarity"

                    # Store the new routing (linked to the similar pattern)
                    if routing_id:
                        embedding = run_async(qdrant_learning._embedding.embed(query_text[:2000]))
                        routing = ExpertRouting(
                            routing_id=routing_id,
                            query_text=query_text,
                            query_embedding=embedding,
                            expert=similar.expert,
                            routing_method="similarity",
                            confidence=similar.similarity,
                            metadata={"category": category, "improvement_type": improvement_type}
                        )
                        run_async(qdrant_learning.store_routing(routing))

                    return jsonify({
                        "expert": similar.expert,
                        "evaluation": {
                            "category": category,
                            "priority": "medium",  # Default for similarity matches
                            "implementation_complexity": "moderate",
                            "risk_level": "low",
                            "recommended_action": "review"
                        },
                        "reasoning": f"Similar improvement routed to {similar.expert} (similarity: {similar.similarity:.2f}, success rate: {similar.success_rate:.0%})",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "routing_id": routing_id,
                        "routing_method": "similarity"
                    }), 200
            except Exception as e:
                logger.warning(f"Similarity lookup failed: {e}")

        # Path 2: No Claude client - return basic evaluation
        if not anthropic_client:
            return jsonify({
                "expert": "general",
                "evaluation": {
                    "category": category,
                    "priority": "medium" if relevance >= 0.85 else "low",
                    "implementation_complexity": "unknown",
                    "risk_level": "low",
                    "recommended_action": "review" if relevance < 0.90 else "auto_approve"
                },
                "reasoning": "No Claude API configured - using default evaluation",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "routing_id": routing_id,
                "routing_method": "fallback"
            }), 200

        # Path 3: Use Claude to evaluate the improvement
        evaluation_prompt = f"""You are an expert evaluator for the Cortex autonomous learning system.
Evaluate this improvement proposal and provide a structured assessment.

IMPROVEMENT:
- Title: {title}
- Description: {description}
- Category: {category}
- Relevance Score: {relevance}
- Source: {source_title}
- Type: {improvement_type}

Provide a JSON response with:
1. "expert": Which expert domain this falls under (infrastructure, security, monitoring, architecture, knowledge, integration)
2. "priority": "high", "medium", or "low"
3. "implementation_complexity": "simple", "moderate", or "complex"
4. "risk_level": "low", "medium", or "high"
5. "recommended_action": "auto_approve", "review", or "reject"
6. "reasoning": Brief explanation of your evaluation

Return ONLY valid JSON, no other text."""

        try:
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": evaluation_prompt}]
            )

            response_text = response.content[0].text.strip()
            # Try to parse JSON from response
            if response_text.startswith('{'):
                evaluation = json.loads(response_text)
            else:
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    evaluation = json.loads(json_match.group())
                else:
                    evaluation = {
                        "expert": "general",
                        "priority": "medium",
                        "implementation_complexity": "moderate",
                        "risk_level": "low",
                        "recommended_action": "review",
                        "reasoning": response_text[:200]
                    }

            expert = evaluation.get("expert", "general")

            # Store for learning
            if qdrant_learning and routing_id:
                try:
                    embedding = run_async(qdrant_learning._embedding.embed(query_text[:2000]))
                    routing = ExpertRouting(
                        routing_id=routing_id,
                        query_text=query_text,
                        query_embedding=embedding,
                        expert=expert,
                        routing_method="llm",
                        confidence=0.9,  # High confidence for LLM evaluation
                        metadata={"category": category, "improvement_type": improvement_type}
                    )
                    run_async(qdrant_learning.store_routing(routing))
                except Exception as e:
                    logger.warning(f"Failed to store routing: {e}")

            return jsonify({
                "expert": expert,
                "evaluation": {
                    "category": category,
                    "priority": evaluation.get("priority", "medium"),
                    "implementation_complexity": evaluation.get("implementation_complexity", "moderate"),
                    "risk_level": evaluation.get("risk_level", "low"),
                    "recommended_action": evaluation.get("recommended_action", "review")
                },
                "reasoning": evaluation.get("reasoning", ""),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "routing_id": routing_id,
                "routing_method": "llm"
            }), 200

        except Exception as e:
            logger.error(f"Claude evaluation error: {e}")
            return jsonify({
                "expert": "general",
                "evaluation": {
                    "category": category,
                    "priority": "medium",
                    "implementation_complexity": "unknown",
                    "risk_level": "low",
                    "recommended_action": "review"
                },
                "reasoning": f"Evaluation error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "routing_id": routing_id,
                "routing_method": "error"
            }), 200

    except Exception as e:
        logger.error(f"Route error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/route/feedback', methods=['POST'])
def route_feedback():
    """
    Submit feedback on a routing evaluation to improve learning.

    Request body:
    {
        "routing_id": "uuid",
        "success": true/false,
        "recommended_action": "auto_approve" | "review" | "reject",
        "priority": "high" | "medium" | "low"
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No feedback data provided"}), 400

        routing_id = data.get('routing_id')
        success = data.get('success', True)
        recommended_action = data.get('recommended_action', 'review')
        priority = data.get('priority', 'medium')

        if not routing_id:
            return jsonify({"error": "routing_id is required"}), 400

        if qdrant_learning:
            try:
                outcome = EvaluationOutcome(
                    outcome_id=generate_outcome_id(),
                    routing_id=routing_id,
                    recommended_action=recommended_action,
                    priority=priority,
                    success=success,
                    timestamp=datetime.utcnow()
                )
                run_async(qdrant_learning.store_evaluation_outcome(outcome))
                logger.info(f"Feedback recorded for routing {routing_id}: success={success}")
            except Exception as e:
                logger.warning(f"Failed to store feedback: {e}")

        return jsonify({
            "status": "recorded",
            "routing_id": routing_id,
            "success": success
        }), 200

    except Exception as e:
        logger.error(f"Feedback error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/route/stats', methods=['GET'])
def route_stats():
    """Get routing statistics for learning."""
    stats = {
        "learning_enabled": qdrant_learning is not None,
        "learning_available": LEARNING_AVAILABLE
    }

    # Could add more stats from Qdrant here if needed

    return jsonify(stats), 200


if __name__ == '__main__':
    logger.info("Starting Simple Chat API on http://localhost:8080")
    logger.info(f"Anthropic API configured: {anthropic_client is not None}")
    logger.info(f"Qdrant learning: {qdrant_learning is not None}")
    app.run(host='0.0.0.0', port=8080, debug=True)
