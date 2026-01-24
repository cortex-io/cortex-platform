#!/usr/bin/env python3
"""
Simple Chat API for local development
Minimal MoE router without Qdrant/Redis dependencies
"""
import os
import json
import logging
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from anthropic import Anthropic

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Initialize Anthropic client
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    logger.warning("ANTHROPIC_API_KEY not set - chat will return mock responses")
    anthropic_client = None
else:
    anthropic_client = Anthropic(api_key=api_key)

# Simple in-memory conversation storage
# Each conversation: {messages: [], status: str, created_at: str, updated_at: str, title: str}
# Status: 'active' (current), 'in_progress' (has messages), 'completed' (ended)
conversations = {}
archived_conversations = {}


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
        "anthropic_configured": anthropic_client is not None
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

    conv_list = []
    for conv_id, conv in conversations.items():
        # Handle legacy format (list of messages)
        if isinstance(conv, list):
            conv = {
                "id": conv_id,
                "title": f"Conversation {conv_id}",
                "messages": conv,
                "status": "in_progress" if conv else "active",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            conversations[conv_id] = conv

        if status_filter and conv.get("status") != status_filter:
            continue

        last_msg = conv.get("messages", [])[-1] if conv.get("messages") else None
        conv_list.append({
            "id": conv_id,
            "title": conv.get("title", f"Conversation {conv_id}"),
            "status": conv.get("status", "active"),
            "lastMessage": last_msg.get("content", "No messages")[:100] if last_msg else "No messages",
            "messageCount": len(conv.get("messages", [])),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at")
        })

    # Include archived if requested
    if include_archived:
        for conv_id, conv in archived_conversations.items():
            last_msg = conv.get("messages", [])[-1] if conv.get("messages") else None
            conv_list.append({
                "id": conv_id,
                "title": conv.get("title", f"Conversation {conv_id}"),
                "status": "archived",
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
    conversations[conv["id"]] = conv
    return jsonify(conv), 201


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get a single conversation"""
    conv = conversations.get(conversation_id)
    if not conv:
        conv = archived_conversations.get(conversation_id)
        if conv:
            conv = {**conv, "status": "archived"}
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify(conv), 200


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation permanently"""
    if conversation_id in conversations:
        del conversations[conversation_id]
        logger.info(f"Deleted conversation: {conversation_id}")
        return jsonify({"success": True, "message": f"Conversation {conversation_id} deleted"}), 200
    if conversation_id in archived_conversations:
        del archived_conversations[conversation_id]
        logger.info(f"Deleted archived conversation: {conversation_id}")
        return jsonify({"success": True, "message": f"Archived conversation {conversation_id} deleted"}), 200
    return jsonify({"error": "Conversation not found"}), 404


@app.route('/api/conversations/<conversation_id>/archive', methods=['POST'])
def archive_conversation(conversation_id):
    """Archive a conversation (move to archived storage)"""
    if conversation_id not in conversations:
        return jsonify({"error": "Conversation not found"}), 404

    conv = conversations.pop(conversation_id)
    conv["status"] = "archived"
    conv["archived_at"] = datetime.utcnow().isoformat() + "Z"
    archived_conversations[conversation_id] = conv
    logger.info(f"Archived conversation: {conversation_id}")
    return jsonify({"success": True, "message": f"Conversation {conversation_id} archived"}), 200


@app.route('/api/conversations/<conversation_id>/restore', methods=['POST'])
def restore_conversation(conversation_id):
    """Restore an archived conversation"""
    if conversation_id not in archived_conversations:
        return jsonify({"error": "Archived conversation not found"}), 404

    conv = archived_conversations.pop(conversation_id)
    conv["status"] = "completed"  # Restored as completed
    conv.pop("archived_at", None)
    conv["updated_at"] = datetime.utcnow().isoformat() + "Z"
    conversations[conversation_id] = conv
    logger.info(f"Restored conversation: {conversation_id}")
    return jsonify({"success": True, "message": f"Conversation {conversation_id} restored"}), 200


@app.route('/api/conversations/<conversation_id>/status', methods=['PUT'])
def update_conversation_status(conversation_id):
    """Update conversation status (active, in_progress, completed)"""
    if conversation_id not in conversations:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.json or {}
    new_status = data.get('status')
    if new_status not in ['active', 'in_progress', 'completed']:
        return jsonify({"error": "Invalid status. Must be: active, in_progress, or completed"}), 400

    conv = conversations[conversation_id]
    # Handle legacy format
    if isinstance(conv, list):
        conv = create_new_conversation(conv_id=conversation_id)
        conv["messages"] = conversations[conversation_id]
        conversations[conversation_id] = conv

    conv["status"] = new_status
    conv["updated_at"] = datetime.utcnow().isoformat() + "Z"
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

        # Get or create conversation
        if conversation_id not in conversations:
            conv = create_new_conversation(conv_id=conversation_id)
            conversations[conversation_id] = conv
        else:
            conv = conversations[conversation_id]
            # Handle legacy format (list of messages)
            if isinstance(conv, list):
                new_conv = create_new_conversation(conv_id=conversation_id)
                new_conv["messages"] = conv
                conversations[conversation_id] = new_conv
                conv = new_conv

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
    conv = conversations.get(conversation_id)
    if not conv:
        conv = archived_conversations.get(conversation_id)
    if not conv:
        return jsonify([]), 200

    # Handle legacy format
    if isinstance(conv, list):
        messages = conv
    else:
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

if __name__ == '__main__':
    logger.info("Starting Simple Chat API on http://localhost:8080")
    logger.info(f"Anthropic API configured: {anthropic_client is not None}")
    app.run(host='0.0.0.0', port=8080, debug=True)
