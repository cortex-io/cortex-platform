#!/usr/bin/env python3
"""
YouTube-to-School Bridge Service
Transforms youtube-ingestion improvements into school-coordinator format
"""
import os
import json
import time
import logging
import hashlib
from flask import Flask, jsonify
from redis import Redis
from datetime import datetime

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment
REDIS_HOST = os.getenv('REDIS_HOST', 'redis-queue.cortex.svc.cluster.local')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '5'))

# Redis connection
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def generate_improvement_id(improvement, video_id):
    """Generate unique ID for an improvement"""
    # Create hash from key fields
    hash_input = f"{video_id}:{improvement.get('category')}:{improvement.get('description')}"
    hash_obj = hashlib.sha256(hash_input.encode())
    return f"improvement:{hash_obj.hexdigest()[:12]}"

def transform_improvement(video_analysis, improvement, is_passive=True):
    """Transform youtube-ingestion improvement to school-coordinator format"""
    return {
        # Core fields expected by school-coordinator
        'title': f"{improvement.get('type', 'improvement').title()}: {improvement.get('description', 'No description')[:80]}",
        'relevance': video_analysis.get('relevance', 0.0),
        'category': improvement.get('category', 'knowledge'),
        'type': improvement.get('type', 'unknown'),
        'description': improvement.get('description', ''),

        # Implementation details
        'implementation_notes': improvement.get('implementation_notes', ''),
        'auto_approve': improvement.get('auto_approve', False),
        'status': improvement.get('status', 'pending'),

        # Source tracking
        'source_video': video_analysis.get('video_id', ''),
        'source_title': video_analysis.get('title', ''),
        'source_type': 'youtube',

        # Metadata
        'proposed_at': improvement.get('proposed_at', datetime.utcnow().isoformat()),
        'improvement_type': 'passive' if is_passive else 'active',
        'created_by': 'youtube-school-bridge'
    }

def process_youtube_improvements():
    """Process improvements from youtube:improvements LIST"""
    try:
        # Pop oldest improvement from list (FIFO)
        raw_data = redis_client.rpop('youtube:improvements')

        if not raw_data:
            return 0  # No items to process

        # Parse the youtube-ingestion analysis
        video_analysis = json.loads(raw_data)
        video_id = video_analysis.get('video_id', 'unknown')

        logger.info(f"Processing improvements from video: {video_analysis.get('title', video_id)}")

        improvements_data = video_analysis.get('improvements', {})
        passive = improvements_data.get('passive', [])
        active = improvements_data.get('active', [])

        count = 0

        # Process passive improvements
        for improvement in passive:
            try:
                # Transform to school format
                school_improvement = transform_improvement(video_analysis, improvement, is_passive=True)

                # Generate unique key
                improvement_id = generate_improvement_id(improvement, video_id)

                # Store improvement data
                redis_client.set(improvement_id, json.dumps(school_improvement))

                # Add to raw queue with current timestamp as score
                redis_client.zadd('improvements:raw', {improvement_id: time.time()})

                count += 1
                logger.info(f"Added passive improvement: {school_improvement['title'][:60]}...")

            except Exception as e:
                logger.error(f"Failed to process passive improvement: {e}")

        # Process active improvements
        for improvement in active:
            try:
                # Transform to school format
                school_improvement = transform_improvement(video_analysis, improvement, is_passive=False)

                # Generate unique key
                improvement_id = generate_improvement_id(improvement, video_id)

                # Store improvement data
                redis_client.set(improvement_id, json.dumps(school_improvement))

                # Add to raw queue with current timestamp as score
                redis_client.zadd('improvements:raw', {improvement_id: time.time()})

                count += 1
                logger.info(f"Added active improvement: {school_improvement['title'][:60]}...")

            except Exception as e:
                logger.error(f"Failed to process active improvement: {e}")

        logger.info(f"Processed {count} improvements from video {video_id}")
        return count

    except Exception as e:
        logger.error(f"Error processing youtube improvements: {e}")
        return 0

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
    """Return bridge status"""
    try:
        youtube_queue = redis_client.llen('youtube:improvements')
        school_queue = redis_client.zcard('improvements:raw')

        return jsonify({
            'status': 'running',
            'youtube_queue_size': youtube_queue,
            'school_raw_queue_size': school_queue
        }), 200
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({'error': str(e)}), 500

def run_bridge_loop():
    """Main bridge loop"""
    logger.info("Starting youtube-to-school bridge loop")

    while True:
        try:
            # Process available improvements
            count = process_youtube_improvements()

            # Sleep if no items processed
            if count == 0:
                time.sleep(POLL_INTERVAL)
            else:
                # Process next immediately if there were items
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Bridge shutting down")
            break
        except Exception as e:
            logger.error(f"Bridge loop error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    import threading

    # Start bridge loop in background thread
    bridge_thread = threading.Thread(target=run_bridge_loop, daemon=True)
    bridge_thread.start()

    # Start Flask API
    app.run(host='0.0.0.0', port=8080)
