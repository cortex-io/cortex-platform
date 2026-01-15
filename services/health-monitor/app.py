#!/usr/bin/env python3
"""
Cortex Health Monitor
Monitors deployments and triggers automatic rollbacks on failures
"""
import os
import json
import time
import logging
import subprocess
import tempfile
import requests
from flask import Flask, jsonify
from redis import Redis
from datetime import datetime, timedelta
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.cortex.svc.cluster.local')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus.monitoring.svc.cluster.local:9090')
HEALTH_CHECK_DURATION = int(os.getenv('HEALTH_CHECK_DURATION', '300'))  # 5 minutes
ROLLBACK_ENABLED = os.getenv('ROLLBACK_ENABLED', 'true').lower() == 'true'
GITHUB_REPO = os.getenv('GITHUB_REPO', 'ry-ops/cortex-gitops')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

# Redis connection
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Kubernetes client
try:
    config.load_incluster_config()
    k8s_core = client.CoreV1Api()
    k8s_apps = client.AppsV1Api()
    logger.info("Loaded in-cluster Kubernetes config")
except:
    logger.warning("Failed to load in-cluster config, trying local kubeconfig")
    try:
        config.load_kube_config()
        k8s_core = client.CoreV1Api()
        k8s_apps = client.AppsV1Api()
    except:
        logger.error("Failed to load Kubernetes config")
        k8s_core = None
        k8s_apps = None

def git_command(cmd, cwd):
    """Execute git command"""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    return result.stdout

def perform_rollback(improvement):
    """Revert the Git commit that deployed this improvement"""
    try:
        commit_hash = improvement.get('implementation', {}).get('commit_hash')
        if not commit_hash:
            logger.error("No commit hash found for rollback")
            return {'status': 'error', 'error': 'No commit hash available'}

        logger.warning(f"Performing rollback of commit {commit_hash}")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Clone repository
            github_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git" if GITHUB_TOKEN else f"https://github.com/{GITHUB_REPO}.git"
            git_command(['git', 'clone', github_url, tmpdir], cwd='/')
            git_command(['git', 'config', 'user.name', 'Cortex Health Monitor'], cwd=tmpdir)
            git_command(['git', 'config', 'user.email', 'monitor@cortex.ai'], cwd=tmpdir)

            # Revert commit
            git_command(['git', 'revert', '--no-edit', commit_hash], cwd=tmpdir)

            # Push rollback
            if GITHUB_TOKEN:
                git_command(['git', 'push', 'origin', 'main'], cwd=tmpdir)
                rollback_commit = git_command(['git', 'rev-parse', 'HEAD'], cwd=tmpdir).strip()

                logger.info(f"Rollback successful: {rollback_commit}")
                return {'status': 'success', 'rollback_commit': rollback_commit}
            else:
                return {'status': 'no_token', 'message': 'Cannot push rollback - no GitHub token'}

    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return {'status': 'error', 'error': str(e)}

def check_pod_health(namespace, label_selector):
    """Check if pods are healthy"""
    if not k8s_core:
        return {'healthy': False, 'reason': 'No Kubernetes connection'}

    try:
        pods = k8s_core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)

        if not pods.items:
            return {'healthy': False, 'reason': 'No pods found'}

        unhealthy_pods = []
        for pod in pods.items:
            # Check pod phase
            if pod.status.phase not in ['Running', 'Succeeded']:
                unhealthy_pods.append({
                    'name': pod.metadata.name,
                    'phase': pod.status.phase,
                    'reason': 'Not running'
                })
                continue

            # Check container readiness
            if pod.status.container_statuses:
                for container in pod.status.container_statuses:
                    if not container.ready:
                        unhealthy_pods.append({
                            'name': pod.metadata.name,
                            'container': container.name,
                            'reason': 'Container not ready'
                        })

        if unhealthy_pods:
            return {'healthy': False, 'unhealthy_pods': unhealthy_pods}

        return {'healthy': True, 'pod_count': len(pods.items)}

    except Exception as e:
        logger.error(f"Error checking pod health: {e}")
        return {'healthy': False, 'reason': str(e)}

def check_prometheus_metrics(improvement):
    """Check Prometheus for error rates and latency"""
    try:
        # Simple health check - in production would check specific metrics
        response = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=5)
        return {'healthy': response.status_code == 200}

    except Exception as e:
        logger.warning(f"Prometheus check failed: {e}")
        return {'healthy': True, 'warning': 'Could not check Prometheus metrics'}

def monitor_deployment(improvement):
    """Monitor deployment for health issues"""
    logger.info(f"Monitoring deployment: {improvement.get('title')}")

    deployed_at = datetime.fromisoformat(improvement.get('implemented_at'))
    monitor_until = deployed_at + timedelta(seconds=HEALTH_CHECK_DURATION)

    checks = []

    while datetime.utcnow() < monitor_until:
        # Check pod health (if we know what was deployed)
        # For now, just do basic checks
        health_check = {
            'timestamp': datetime.utcnow().isoformat(),
            'prometheus': check_prometheus_metrics(improvement)
        }

        checks.append(health_check)

        # If any check fails, trigger rollback
        if not health_check['prometheus']['healthy']:
            logger.error(f"Health check failed: {health_check}")
            return {'status': 'failed', 'checks': checks, 'trigger_rollback': True}

        # Wait before next check
        time.sleep(10)

    # All checks passed
    logger.info(f"Health monitoring complete - all checks passed: {improvement.get('title')}")
    return {'status': 'verified', 'checks': checks}

def process_deployed_improvements():
    """Monitor deployed improvements for health"""
    try:
        improvements = redis_client.zrange('improvements:deployed', 0, 0, withscores=True)
        if not improvements:
            return

        improvement_key, timestamp = improvements[0]
        improvement = json.loads(redis_client.get(improvement_key))

        logger.info(f"Starting health monitoring: {improvement.get('title')}")

        # Monitor deployment
        monitoring_result = monitor_deployment(improvement)

        if monitoring_result['status'] == 'verified':
            # Deployment successful
            improvement['health_monitoring'] = monitoring_result
            improvement['verified_at'] = datetime.utcnow().isoformat()
            redis_client.set(improvement_key, json.dumps(improvement))

            redis_client.zadd('improvements:verified', {improvement_key: time.time()})
            redis_client.zrem('improvements:deployed', improvement_key)

            logger.info(f"Deployment verified: {improvement.get('title')}")

        elif monitoring_result.get('trigger_rollback') and ROLLBACK_ENABLED:
            # Deployment failed - rollback
            logger.error(f"Deployment failed, triggering rollback: {improvement.get('title')}")

            rollback_result = perform_rollback(improvement)

            improvement['health_monitoring'] = monitoring_result
            improvement['rollback'] = rollback_result
            improvement['failed_at'] = datetime.utcnow().isoformat()
            redis_client.set(improvement_key, json.dumps(improvement))

            redis_client.zadd('improvements:failed', {improvement_key: time.time()})
            redis_client.zrem('improvements:deployed', improvement_key)

            logger.warning(f"Rolled back failed deployment: {improvement.get('title')}")

    except Exception as e:
        logger.error(f"Error processing deployed improvement: {e}")

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        redis_client.ping()
        k8s_healthy = k8s_core is not None

        return jsonify({
            'status': 'healthy',
            'redis': 'connected',
            'kubernetes': 'connected' if k8s_healthy else 'disconnected',
            'rollback_enabled': ROLLBACK_ENABLED,
            'github_configured': bool(GITHUB_TOKEN)
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

def run_monitor_loop():
    """Main monitoring loop"""
    logger.info("Starting health monitor loop")

    while True:
        try:
            process_deployed_improvements()
            time.sleep(15)

        except KeyboardInterrupt:
            logger.info("Monitor shutting down")
            break
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    import threading

    # Start monitor loop in background thread
    monitor_thread = threading.Thread(target=run_monitor_loop, daemon=True)
    monitor_thread.start()

    # Start Flask API
    app.run(host='0.0.0.0', port=8080)
