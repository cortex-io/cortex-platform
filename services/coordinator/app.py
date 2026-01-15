#!/usr/bin/env python3
"""
Cortex School Coordinator
Main orchestration service for the autonomous learning pipeline
"""
import os
import json
import time
import logging
import requests
from flask import Flask, jsonify
from redis import Redis
from datetime import datetime

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.cortex.svc.cluster.local')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
AUTO_APPROVE_THRESHOLD = float(os.getenv('AUTO_APPROVE_THRESHOLD', '0.90'))
HIGH_RISK_THRESHOLD = float(os.getenv('HIGH_RISK_THRESHOLD', '0.95'))
MOE_ROUTER_URL = os.getenv('MOE_ROUTER_URL', 'http://moe-router.cortex-school.svc.cluster.local:8080')
RAG_VALIDATOR_URL = os.getenv('RAG_VALIDATOR_URL', 'http://rag-validator.cortex-school.svc.cluster.local:8080')

# Redis connection
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Auto-approval override flags
def get_override_flags():
    """Check Redis for emergency override flags"""
    return {
        'auto_approve_all': redis_client.get('auto_approve_all') == 'true',
        'auto_approve_none': redis_client.get('auto_approve_none') == 'true',
        'auto_approve_integrations': redis_client.get('auto_approve_integrations') == 'true'
    }

def should_auto_approve(improvement, rag_result):
    """Determine if improvement should be auto-approved"""
    overrides = get_override_flags()

    # Emergency stop
    if overrides['auto_approve_none']:
        logger.info("Auto-approval disabled by override flag")
        return False

    # Emergency approve all
    if overrides['auto_approve_all']:
        logger.warning("Auto-approving due to emergency override")
        return True

    relevance = improvement.get('relevance', 0.0)
    category = improvement.get('category', '')
    imp_type = improvement.get('type', '')

    # Never auto-approve if RAG found conflicts
    if not rag_result.get('rag_check_passed', False):
        logger.info(f"RAG check failed for improvement: {improvement.get('title')}")
        return False

    # Never auto-approve integrations unless override
    if category == 'integration' or imp_type == 'integration':
        if overrides['auto_approve_integrations']:
            return relevance >= AUTO_APPROVE_THRESHOLD
        return False

    # High-risk categories need 95% relevance
    high_risk_categories = ['security', 'database']
    if category in high_risk_categories:
        return relevance >= HIGH_RISK_THRESHOLD

    # Standard categories auto-approve at 90%
    safe_categories = ['architecture', 'capability', 'monitoring']
    if category in safe_categories:
        return relevance >= AUTO_APPROVE_THRESHOLD

    # Default: require review
    return False

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return jsonify({'status': 'healthy', 'redis': 'connected'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

@app.route('/status')
def status():
    """Return pipeline status and queue sizes"""
    try:
        queues = {
            'raw': redis_client.zcard('improvements:raw'),
            'categorized': redis_client.zcard('improvements:categorized'),
            'validated': redis_client.zcard('improvements:validated'),
            'approved': redis_client.zcard('improvements:approved'),
            'pending_review': redis_client.zcard('improvements:pending_review'),
            'deployed': redis_client.zcard('improvements:deployed'),
            'verified': redis_client.zcard('improvements:verified'),
            'failed': redis_client.zcard('improvements:failed')
        }
        overrides = get_override_flags()

        return jsonify({
            'status': 'running',
            'queues': queues,
            'overrides': overrides,
            'thresholds': {
                'auto_approve': AUTO_APPROVE_THRESHOLD,
                'high_risk': HIGH_RISK_THRESHOLD
            }
        }), 200
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({'error': str(e)}), 500

def process_raw_improvements():
    """Process improvements from raw queue through MoE router"""
    try:
        # Get oldest improvement from raw queue (FIFO using sorted set with timestamp scores)
        improvements = redis_client.zrange('improvements:raw', 0, 0, withscores=True)
        if not improvements:
            return

        improvement_key, timestamp = improvements[0]
        improvement = json.loads(redis_client.get(improvement_key))

        logger.info(f"Processing raw improvement: {improvement.get('title')}")

        # Route to MoE for expert evaluation
        response = requests.post(
            f"{MOE_ROUTER_URL}/route",
            json=improvement,
            timeout=30
        )

        if response.status_code == 200:
            expert_evaluation = response.json()
            improvement['expert_evaluation'] = expert_evaluation

            # Update improvement with expert evaluation
            redis_client.set(improvement_key, json.dumps(improvement))

            # Move to categorized queue
            redis_client.zadd('improvements:categorized', {improvement_key: time.time()})
            redis_client.zrem('improvements:raw', improvement_key)

            logger.info(f"Moved to categorized: {improvement.get('title')}")
        else:
            logger.error(f"MoE routing failed: {response.status_code}")

    except Exception as e:
        logger.error(f"Error processing raw improvement: {e}")

def process_categorized_improvements():
    """Process categorized improvements through RAG validation"""
    try:
        improvements = redis_client.zrange('improvements:categorized', 0, 0, withscores=True)
        if not improvements:
            return

        improvement_key, timestamp = improvements[0]
        improvement = json.loads(redis_client.get(improvement_key))

        logger.info(f"Validating improvement: {improvement.get('title')}")

        # Send to RAG validator
        response = requests.post(
            f"{RAG_VALIDATOR_URL}/validate",
            json=improvement,
            timeout=30
        )

        if response.status_code == 200:
            rag_result = response.json()
            improvement['rag_validation'] = rag_result

            # Update improvement
            redis_client.set(improvement_key, json.dumps(improvement))

            # Move to validated queue
            redis_client.zadd('improvements:validated', {improvement_key: time.time()})
            redis_client.zrem('improvements:categorized', improvement_key)

            logger.info(f"Moved to validated: {improvement.get('title')}")
        else:
            logger.error(f"RAG validation failed: {response.status_code}")

    except Exception as e:
        logger.error(f"Error validating improvement: {e}")

def process_validated_improvements():
    """Apply auto-approval logic to validated improvements"""
    try:
        improvements = redis_client.zrange('improvements:validated', 0, 0, withscores=True)
        if not improvements:
            return

        improvement_key, timestamp = improvements[0]
        improvement = json.loads(redis_client.get(improvement_key))

        logger.info(f"Evaluating for auto-approval: {improvement.get('title')}")

        rag_result = improvement.get('rag_validation', {})

        if should_auto_approve(improvement, rag_result):
            # Auto-approve
            improvement['approved_at'] = datetime.utcnow().isoformat()
            improvement['approval_type'] = 'automatic'
            redis_client.set(improvement_key, json.dumps(improvement))

            redis_client.zadd('improvements:approved', {improvement_key: time.time()})
            redis_client.zrem('improvements:validated', improvement_key)

            logger.info(f"Auto-approved: {improvement.get('title')} (relevance: {improvement.get('relevance')})")
        else:
            # Requires human review
            improvement['requires_review'] = True
            improvement['review_reason'] = 'Below auto-approval threshold or high-risk category'
            redis_client.set(improvement_key, json.dumps(improvement))

            redis_client.zadd('improvements:pending_review', {improvement_key: time.time()})
            redis_client.zrem('improvements:validated', improvement_key)

            logger.info(f"Pending review: {improvement.get('title')}")

    except Exception as e:
        logger.error(f"Error processing validated improvement: {e}")

def run_coordinator_loop():
    """Main coordinator loop"""
    logger.info("Starting coordinator loop")

    while True:
        try:
            # Process each stage
            process_raw_improvements()
            process_categorized_improvements()
            process_validated_improvements()

            # Sleep between cycles
            time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Coordinator shutting down")
            break
        except Exception as e:
            logger.error(f"Coordinator loop error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    import threading

    # Start coordinator loop in background thread
    coordinator_thread = threading.Thread(target=run_coordinator_loop, daemon=True)
    coordinator_thread.start()

    # Start Flask API
    app.run(host='0.0.0.0', port=8080)
