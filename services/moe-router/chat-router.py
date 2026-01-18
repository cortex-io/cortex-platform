#!/usr/bin/env python3
"""
MoE Chat Router for Cortex Chat
Routes chat requests to specialized experts based on intent classification
"""
import os
import json
import yaml
import logging
import redis
from datetime import datetime
from flask import Flask, request, jsonify
from anthropic import Anthropic
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration
config = {
    'router': {
        'experts': [
            {
                'name': 'general',
                'endpoint': os.getenv('EXPERT_GENERAL', 'http://cortex-orchestrator.cortex.svc.cluster.local:8000'),
                'weight': 1.0,
                'specialization': 'general conversation and task routing'
            },
            {
                'name': 'infrastructure',
                'endpoint': os.getenv('EXPERT_INFRA', 'http://cortex-orchestrator.cortex.svc.cluster.local:8000'),
                'weight': 2.0,
                'specialization': 'kubernetes, deployment, infrastructure management'
            },
            {
                'name': 'security',
                'endpoint': os.getenv('EXPERT_SECURITY', 'http://cortex-orchestrator.cortex.svc.cluster.local:8000'),
                'weight': 2.0,
                'specialization': 'security scanning, vulnerability analysis, compliance'
            },
            {
                'name': 'automation',
                'endpoint': os.getenv('EXPERT_AUTO', 'http://cortex-orchestrator.cortex.svc.cluster.local:8000'),
                'weight': 1.5,
                'specialization': 'workflow automation, n8n, langflow'
            }
        ]
    },
    'qdrant': {
        'host': os.getenv('QDRANT_HOST', 'qdrant.cortex-chat.svc.cluster.local'),
        'port': int(os.getenv('QDRANT_PORT', '6333')),
        'collection': 'chat_memory'
    },
    'telemetry': {
        'enabled': os.getenv('TELEMETRY_ENABLED', 'true').lower() == 'true',
        'redis_host': os.getenv('REDIS_HOST', 'redis.cortex-system.svc.cluster.local'),
        'redis_port': int(os.getenv('REDIS_PORT', '6379')),
        'redis_key_prefix': 'moe:telemetry:'
    }
}

# Initialize clients
anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

qdrant_client = QdrantClient(
    host=config['qdrant']['host'],
    port=config['qdrant']['port']
)

if config['telemetry']['enabled']:
    redis_client = redis.Redis(
        host=config['telemetry']['redis_host'],
        port=config['telemetry']['redis_port'],
        decode_responses=True
    )
else:
    redis_client = None

COLLECTION_NAME = config['qdrant']['collection']

def ensure_collection():
    """Ensure Qdrant collection exists"""
    try:
        collections = qdrant_client.get_collections().collections
        if not any(c.name == COLLECTION_NAME for c in collections):
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
            logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
    except Exception as e:
        logger.error(f"Error ensuring collection: {e}")

ensure_collection()

def classify_intent(message: str) -> dict:
    """Classify user intent using Claude"""
    experts_desc = "\n".join([
        f"- {e['name']}: {e['specialization']}"
        for e in config['router']['experts']
    ])

    prompt = f"""Classify the user's intent and select the best expert.

Available experts:
{experts_desc}

User message: {message}

Respond with JSON only:
{{"expert": "expert_name", "confidence": 0.95, "reasoning": "brief explanation"}}"""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.content[0].text)
        return result
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        return {"expert": "general", "confidence": 0.5, "reasoning": "fallback"}

def store_in_qdrant(message: str, response: str, conversation_id: str, metadata: dict):
    """Store conversation in Qdrant"""
    try:
        vector = [float(ord(c) % 256) / 256.0 for c in hashlib.sha512(message.encode()).hexdigest()[:1536]]

        point = PointStruct(
            id=hashlib.md5(f"{conversation_id}-{datetime.utcnow().isoformat()}".encode()).hexdigest(),
            vector=vector,
            payload={
                "conversation_id": conversation_id,
                "message": message,
                "response": response,
                "timestamp": datetime.utcnow().isoformat(),
                **metadata
            }
        )

        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=[point])
        logger.info(f"Stored in Qdrant: {conversation_id}")
    except Exception as e:
        logger.error(f"Qdrant storage error: {e}")

def capture_telemetry(intent: dict, expert: str, latency: float, success: bool):
    """Capture routing telemetry to Redis"""
    if not redis_client:
        return

    try:
        key_prefix = config['telemetry']['redis_key_prefix']
        telemetry = {
            "timestamp": datetime.utcnow().isoformat(),
            "intent": intent,
            "expert": expert,
            "latency_ms": latency,
            "success": success
        }

        redis_client.zadd(
            f"{key_prefix}routing_decisions",
            {json.dumps(telemetry): datetime.utcnow().timestamp()}
        )

        redis_client.hincrby(f"{key_prefix}expert_usage", expert, 1)
        logger.info(f"Captured telemetry for expert: {expert}")
    except Exception as e:
        logger.error(f"Telemetry capture error: {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "moe-router"}), 200

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        message = data.get('message', '')
        conversation_id = data.get('conversation_id', 'default')

        start_time = datetime.utcnow()

        # Classify intent
        intent = classify_intent(message)
        expert_name = intent['expert']

        # Find expert endpoint
        expert = next((e for e in config['router']['experts'] if e['name'] == expert_name), None)
        if not expert:
            expert = config['router']['experts'][0]

        # Route to expert
        expert_request = {
            "message": message,
            "conversation_id": conversation_id,
            "intent": intent
        }

        try:
            response = requests.post(
                f"{expert['endpoint']}/chat",
                json=expert_request,
                timeout=30
            )

            if response.status_code == 200:
                expert_response = response.json()

                # Store in Qdrant
                store_in_qdrant(
                    message,
                    expert_response.get('response', ''),
                    conversation_id,
                    {"expert": expert_name, "intent": intent}
                )

                # Capture telemetry
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                capture_telemetry(intent, expert_name, latency, True)

                return jsonify({
                    "response": expert_response.get('response', ''),
                    "expert": expert_name,
                    "confidence": intent['confidence'],
                    "latency_ms": latency
                }), 200
            else:
                raise Exception(f"Expert returned {response.status_code}")

        except Exception as e:
            logger.error(f"Expert routing error: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            capture_telemetry(intent, expert_name, latency, False)

            return jsonify({"error": "Expert routing failed", "message": str(e)}), 500

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
