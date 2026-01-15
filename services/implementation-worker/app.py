#!/usr/bin/env python3
"""
Cortex Implementation Worker
Generates Kubernetes manifests and commits to Git
"""
import os
import json
import time
import logging
import subprocess
import tempfile
from flask import Flask, jsonify
from redis import Redis
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.cortex.svc.cluster.local')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
GITHUB_REPO = os.getenv('GITHUB_REPO', 'ry-ops/cortex-gitops')
GITHUB_BRANCH = os.getenv('GITHUB_BRANCH', 'main')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
COMMIT_AUTHOR_NAME = os.getenv('COMMIT_AUTHOR_NAME', 'Cortex Online School')
COMMIT_AUTHOR_EMAIL = os.getenv('COMMIT_AUTHOR_EMAIL', 'school@cortex.ai')
WORKER_TYPE = os.getenv('WORKER_TYPE', 'all')

# Redis connection
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def git_command(cmd, cwd):
    """Execute git command"""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    return result.stdout

def clone_repository(clone_dir):
    """Clone the cortex-gitops repository"""
    github_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git" if GITHUB_TOKEN else f"https://github.com/{GITHUB_REPO}.git"

    git_command(['git', 'clone', '-b', GITHUB_BRANCH, github_url, clone_dir], cwd='/')
    git_command(['git', 'config', 'user.name', COMMIT_AUTHOR_NAME], cwd=clone_dir)
    git_command(['git', 'config', 'user.email', COMMIT_AUTHOR_EMAIL], cwd=clone_dir)

def generate_manifest_from_improvement(improvement):
    """Generate Kubernetes manifest based on improvement type"""
    category = improvement.get('category', '')
    title = improvement.get('title', '')
    description = improvement.get('description', '')

    # Simple manifest generation - in production this would be much more sophisticated
    # For now, create a ConfigMap as a placeholder

    safe_name = title.lower().replace(' ', '-')[:50]

    manifest = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: improvement-{safe_name}
  namespace: cortex
  labels:
    managed-by: cortex-online-school
    category: {category}
    auto-implemented: "true"
  annotations:
    cortex.ai/source: youtube-learning
    cortex.ai/relevance: "{improvement.get('relevance', 0.0)}"
    cortex.ai/implemented-at: "{datetime.utcnow().isoformat()}"
data:
  title: {json.dumps(title)}
  description: {json.dumps(description)}
  implementation-notes: {json.dumps(improvement.get('implementation_notes', ''))}
  category: {category}
"""

    return manifest, f"improvement-{safe_name}.yaml"

def commit_and_push_improvement(improvement):
    """Generate manifest, commit, and push to GitHub"""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"Cloning repository to {tmpdir}")
            clone_repository(tmpdir)

            # Generate manifest
            manifest_content, filename = generate_manifest_from_improvement(improvement)

            # Write manifest to appropriate directory
            category = improvement.get('category', 'misc')
            target_dir = Path(tmpdir) / 'apps' / 'cortex' / 'improvements'
            target_dir.mkdir(parents=True, exist_ok=True)

            manifest_path = target_dir / filename
            manifest_path.write_text(manifest_content)

            logger.info(f"Generated manifest: {manifest_path}")

            # Git add
            git_command(['git', 'add', '.'], cwd=tmpdir)

            # Check if there are changes
            status = git_command(['git', 'status', '--porcelain'], cwd=tmpdir)
            if not status.strip():
                logger.info("No changes to commit")
                return {'status': 'no_changes'}

            # Create commit message
            commit_message = f"""Implement: {improvement.get('title')}

Source: YouTube video {improvement.get('video_id', 'unknown')} - {improvement.get('video_title', '')}
Relevance: {improvement.get('relevance', 0.0)}
Category: {improvement.get('category', '')}
Auto-approved: Yes (relevance ≥ 90%)

Changes:
- Added ConfigMap {filename}

Implementation notes:
{improvement.get('implementation_notes', 'None provided')}

Co-Authored-By: Cortex Online School <school@cortex.ai>
"""

            # Commit
            git_command(['git', 'commit', '-m', commit_message], cwd=tmpdir)

            # Push
            if GITHUB_TOKEN:
                git_command(['git', 'push', 'origin', GITHUB_BRANCH], cwd=tmpdir)
                logger.info("Pushed to GitHub successfully")

                # Get commit hash
                commit_hash = git_command(['git', 'rev-parse', 'HEAD'], cwd=tmpdir).strip()

                return {
                    'status': 'success',
                    'commit_hash': commit_hash,
                    'manifest_path': str(manifest_path.relative_to(tmpdir))
                }
            else:
                logger.warning("No GitHub token - commit created but not pushed")
                return {'status': 'no_token', 'message': 'Commit created locally but not pushed'}

    except Exception as e:
        logger.error(f"Error committing improvement: {e}")
        return {'status': 'error', 'error': str(e)}

def process_approved_improvements():
    """Process improvements from approved queue"""
    try:
        improvements = redis_client.zrange('improvements:approved', 0, 0, withscores=True)
        if not improvements:
            return

        improvement_key, timestamp = improvements[0]
        improvement = json.loads(redis_client.get(improvement_key))

        logger.info(f"Implementing improvement: {improvement.get('title')}")

        # Generate and commit manifest
        result = commit_and_push_improvement(improvement)

        if result['status'] == 'success':
            # Update improvement with implementation details
            improvement['implementation'] = result
            improvement['implemented_at'] = datetime.utcnow().isoformat()
            redis_client.set(improvement_key, json.dumps(improvement))

            # Move to deployed queue
            redis_client.zadd('improvements:deployed', {improvement_key: time.time()})
            redis_client.zrem('improvements:approved', improvement_key)

            logger.info(f"Successfully implemented: {improvement.get('title')}")
        else:
            logger.error(f"Implementation failed: {result}")

    except Exception as e:
        logger.error(f"Error processing approved improvement: {e}")

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return jsonify({
            'status': 'healthy',
            'redis': 'connected',
            'github_configured': bool(GITHUB_TOKEN),
            'worker_type': WORKER_TYPE
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

def run_worker_loop():
    """Main worker loop"""
    logger.info(f"Starting implementation worker (type: {WORKER_TYPE})")

    while True:
        try:
            process_approved_improvements()
            time.sleep(10)

        except KeyboardInterrupt:
            logger.info("Worker shutting down")
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    import threading

    # Start worker loop in background thread
    worker_thread = threading.Thread(target=run_worker_loop, daemon=True)
    worker_thread.start()

    # Start Flask API
    app.run(host='0.0.0.0', port=8080)
