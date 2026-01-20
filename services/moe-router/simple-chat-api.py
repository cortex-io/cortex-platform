#!/usr/bin/env python3
"""
Simple Chat API for local development
Minimal MoE router without Qdrant/Redis dependencies
"""
import os
import json
import logging
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
conversations = {}

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
    """Get all conversations"""
    conv_list = [
        {
            "id": conv_id,
            "title": f"Conversation {conv_id}",
            "lastMessage": msgs[-1] if msgs else "No messages",
            "timestamp": "2026-01-19T00:00:00Z"
        }
        for conv_id, msgs in conversations.items()
    ]
    return jsonify(conv_list), 200

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create new conversation"""
    conv_id = f"conv-{len(conversations) + 1}"
    conversations[conv_id] = []
    return jsonify({"id": conv_id, "title": f"New Conversation {conv_id}"}), 201

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        message = data.get('message', '')
        conversation_id = data.get('conversation_id', 'default')

        logger.info(f"Chat request: conversation={conversation_id}, message={message[:50]}...")

        # Store user message
        if conversation_id not in conversations:
            conversations[conversation_id] = []
        conversations[conversation_id].append({
            "role": "user",
            "content": message
        })

        # Generate response
        if anthropic_client:
            try:
                # Use Claude for response
                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=conversations[conversation_id]
                )

                assistant_message = response.content[0].text

            except Exception as e:
                logger.error(f"Anthropic API error: {e}")
                assistant_message = f"I'm having trouble connecting to Claude right now. Error: {str(e)}"
        else:
            # Mock response without API key
            assistant_message = f"Echo: {message} (Note: Set ANTHROPIC_API_KEY for real Claude responses)"

        # Store assistant response
        conversations[conversation_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        return jsonify({
            "response": assistant_message,
            "conversation_id": conversation_id,
            "expert": "general",
            "timestamp": "2026-01-19T00:00:00Z"
        }), 200

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """Get conversation history"""
    if conversation_id not in conversations:
        return jsonify([]), 200

    messages = [
        {
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": "2026-01-19T00:00:00Z"
        }
        for msg in conversations[conversation_id]
    ]
    return jsonify(messages), 200

if __name__ == '__main__':
    logger.info("Starting Simple Chat API on http://localhost:8080")
    logger.info(f"Anthropic API configured: {anthropic_client is not None}")
    app.run(host='0.0.0.0', port=8080, debug=True)
