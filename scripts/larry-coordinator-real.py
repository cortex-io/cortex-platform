#!/usr/bin/env python3
"""
Real Larry Coordinator - Production Implementation
Connects to Redis for coordination and spawns K8s workers
"""

import os
import sys
import time
import json
import redis
import psycopg2
from datetime import datetime
from kubernetes import client, config
from typing import Dict, List, Any

class LarryCoordinator:
    def __init__(self):
        self.larry_id = os.getenv('LARRY_ID', 'larry-01')
        self.phase = os.getenv('PHASE', 'infrastructure')
        self.redis_host = os.getenv('REDIS_HOST', 'redis-master.cortex-system.svc.cluster.local')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_password = os.getenv('REDIS_PASSWORD', 'cortex123')
        self.postgres_host = os.getenv('POSTGRES_HOST', 'postgres.cortex-system.svc.cluster.local')
        self.postgres_port = int(os.getenv('POSTGRES_PORT', '5432'))
        self.postgres_db = os.getenv('POSTGRES_DB', 'cortex')
        self.postgres_user = os.getenv('POSTGRES_USER', 'cortex')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD', 'cortex')
        self.coordination_path = os.getenv('COORDINATION_PATH', '/coordination')
        self.worker_count = int(os.getenv('WORKER_COUNT', '4'))
        self.token_budget_personal = int(os.getenv('TOKEN_BUDGET_PERSONAL', '50000'))
        self.token_budget_workers = int(os.getenv('TOKEN_BUDGET_WORKERS', '36000'))

        # Initialize connections
        self.redis_client = None
        self.postgres_conn = None
        self.k8s_batch_api = None
        self.k8s_core_api = None

        # State
        self.workers_spawned = []
        self.start_time = None

    def connect(self):
        """Initialize all connections"""
        print(f"[{self.larry_id}] Initializing connections...")

        # Redis connection
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                decode_responses=True
            )
            self.redis_client.ping()
            print(f"[{self.larry_id}] Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"[{self.larry_id}] ERROR: Failed to connect to Redis: {e}")
            sys.exit(1)

        # PostgreSQL connection
        try:
            self.postgres_conn = psycopg2.connect(
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
                user=self.postgres_user,
                password=self.postgres_password
            )
            print(f"[{self.larry_id}] Connected to PostgreSQL at {self.postgres_host}:{self.postgres_port}")
        except Exception as e:
            print(f"[{self.larry_id}] WARNING: Failed to connect to PostgreSQL: {e}")
            print(f"[{self.larry_id}] Continuing with Redis-only coordination")

        # Kubernetes connection
        try:
            config.load_incluster_config()
            self.k8s_batch_api = client.BatchV1Api()
            self.k8s_core_api = client.CoreV1Api()
            print(f"[{self.larry_id}] Connected to Kubernetes API")
        except Exception as e:
            print(f"[{self.larry_id}] ERROR: Failed to connect to Kubernetes: {e}")
            sys.exit(1)

    def publish_event(self, event_type: str, data: Dict[str, Any] = None):
        """Publish coordination event to Redis"""
        event = {
            "from": self.larry_id,
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        if data:
            event.update(data)

        try:
            self.redis_client.publish('larry:coordination', json.dumps(event))
        except Exception as e:
            print(f"[{self.larry_id}] WARNING: Failed to publish event: {e}")

    def update_redis_state(self, status: str, progress: int = 0, metadata: Dict[str, Any] = None):
        """Update Larry state in Redis"""
        try:
            key_prefix = f"phase:{self.larry_id}"
            self.redis_client.set(f"{key_prefix}:status", status)
            self.redis_client.set(f"{key_prefix}:progress", progress)

            if status == "in_progress" and not self.start_time:
                self.start_time = datetime.utcnow().isoformat() + "Z"
                self.redis_client.set(f"{key_prefix}:started_at", self.start_time)
            elif status == "completed":
                self.redis_client.set(f"{key_prefix}:completed_at", datetime.utcnow().isoformat() + "Z")

            if metadata:
                for key, value in metadata.items():
                    self.redis_client.set(f"{key_prefix}:{key}", str(value))
        except Exception as e:
            print(f"[{self.larry_id}] WARNING: Failed to update Redis state: {e}")

    def spawn_worker(self, worker_spec: Dict[str, Any]) -> bool:
        """Spawn a Kubernetes Job for a worker"""
        try:
            namespace = f"larry-{self.larry_id.split('-')[1]}"
            job_name = worker_spec['name']

            # Create Job manifest
            job = client.V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=client.V1ObjectMeta(
                    name=job_name,
                    namespace=namespace,
                    labels={
                        "app": "larry-worker",
                        "larry-instance": self.larry_id,
                        "worker-type": worker_spec['type']
                    }
                ),
                spec=client.V1JobSpec(
                    backoff_limit=3,
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={
                                "app": "larry-worker",
                                "larry-instance": self.larry_id,
                                "worker-type": worker_spec['type']
                            }
                        ),
                        spec=client.V1PodSpec(
                            restart_policy="OnFailure",
                            containers=[
                                client.V1Container(
                                    name=worker_spec['type'],
                                    image=worker_spec.get('image', 'alpine:3.18'),
                                    command=["/bin/sh", "-c"],
                                    args=[worker_spec.get('command', 'echo "Worker running"; sleep 5')],
                                    env=[
                                        client.V1EnvVar(name="WORKER_TYPE", value=worker_spec['type']),
                                        client.V1EnvVar(name="LARRY_ID", value=self.larry_id),
                                        client.V1EnvVar(name="TASK_ID", value=worker_spec.get('task_id', 'unknown')),
                                        client.V1EnvVar(name="TOKEN_BUDGET", value=str(worker_spec.get('token_budget', 8000))),
                                        client.V1EnvVar(name="REDIS_HOST", value=self.redis_host),
                                        client.V1EnvVar(name="REDIS_PORT", value=str(self.redis_port)),
                                        client.V1EnvVar(name="REDIS_PASSWORD", value=self.redis_password),
                                    ],
                                    resources=client.V1ResourceRequirements(
                                        requests={"memory": "1Gi", "cpu": "500m"},
                                        limits={"memory": "2Gi", "cpu": "1000m"}
                                    )
                                )
                            ]
                        )
                    )
                )
            )

            # Create the Job
            self.k8s_batch_api.create_namespaced_job(namespace=namespace, body=job)
            print(f"[{self.larry_id}] Spawned worker: {job_name} (type: {worker_spec['type']})")
            self.workers_spawned.append(job_name)
            return True

        except Exception as e:
            print(f"[{self.larry_id}] ERROR: Failed to spawn worker {worker_spec['name']}: {e}")
            return False

    def monitor_workers(self) -> Dict[str, int]:
        """Monitor worker job status"""
        namespace = f"larry-{self.larry_id.split('-')[1]}"

        try:
            jobs = self.k8s_batch_api.list_namespaced_job(
                namespace=namespace,
                label_selector=f"larry-instance={self.larry_id}"
            )

            status = {
                'total': len(jobs.items),
                'active': 0,
                'succeeded': 0,
                'failed': 0
            }

            for job in jobs.items:
                if job.status.active:
                    status['active'] += job.status.active
                if job.status.succeeded:
                    status['succeeded'] += job.status.succeeded
                if job.status.failed:
                    status['failed'] += job.status.failed

            return status

        except Exception as e:
            print(f"[{self.larry_id}] WARNING: Failed to monitor workers: {e}")
            return {'total': 0, 'active': 0, 'succeeded': 0, 'failed': 0}

    def get_worker_specs(self) -> List[Dict[str, Any]]:
        """Get worker specifications based on Larry ID and phase"""
        # This will be customized per Larry instance
        # For now, return generic demo workers
        specs = []

        if self.larry_id == "larry-01":
            specs = [
                {"name": "cleanup-worker", "type": "cleanup", "task_id": "fix-pgadmin", "token_budget": 8000},
                {"name": "consolidation-worker", "type": "consolidation", "task_id": "consolidate-pg", "token_budget": 10000},
                {"name": "optimization-worker", "type": "optimization", "task_id": "optimize-db", "token_budget": 8000},
                {"name": "monitoring-worker", "type": "monitoring", "task_id": "setup-monitoring", "token_budget": 10000},
            ]
        elif self.larry_id == "larry-02":
            specs = [
                {"name": "scan-worker-01", "type": "scan", "task_id": "scan-group-01", "token_budget": 8000},
                {"name": "scan-worker-02", "type": "scan", "task_id": "scan-group-02", "token_budget": 8000},
                {"name": "audit-worker", "type": "audit", "task_id": "dependency-audit", "token_budget": 10000},
                {"name": "remediation-worker", "type": "remediation", "task_id": "auto-remediation", "token_budget": 10000},
            ]
        elif self.larry_id == "larry-03":
            specs = [
                {"name": "catalog-worker-01", "type": "catalog", "task_id": "catalog-deployments", "token_budget": 8000},
                {"name": "catalog-worker-02", "type": "catalog", "task_id": "catalog-helm", "token_budget": 8000},
                {"name": "classification-worker", "type": "classification", "task_id": "classify-assets", "token_budget": 10000},
                {"name": "code-quality-worker", "type": "code-quality", "task_id": "analyze-quality", "token_budget": 10000},
                {"name": "test-coverage-worker", "type": "test-coverage", "task_id": "improve-coverage", "token_budget": 10000},
                {"name": "documentation-worker", "type": "documentation", "task_id": "generate-docs", "token_budget": 10000},
                {"name": "feature-worker", "type": "feature", "task_id": "implement-feature", "token_budget": 12000},
                {"name": "review-worker", "type": "review", "task_id": "review-prs", "token_budget": 8000},
            ]

        # Add full names with larry prefix
        for spec in specs:
            spec['name'] = f"{self.larry_id}-{spec['name']}"

        return specs

    def run(self):
        """Main coordinator loop"""
        print(f"========================================")
        print(f"   {self.larry_id.upper()} COORDINATOR")
        print(f"========================================")
        print(f"")
        print(f"Larry ID: {self.larry_id}")
        print(f"Phase: {self.phase}")
        print(f"Worker Count: {self.worker_count}")
        print(f"Token Budget (Personal): {self.token_budget_personal}")
        print(f"Token Budget (Workers): {self.token_budget_workers}")
        print(f"Started: {datetime.utcnow().isoformat()}Z")
        print(f"")

        # Connect to services
        self.connect()

        # Initialize state
        self.update_redis_state("in_progress", 0)
        self.publish_event("phase_started")

        # Get worker specifications
        worker_specs = self.get_worker_specs()
        print(f"[{self.larry_id}] Planning to spawn {len(worker_specs)} workers")

        # Spawn workers
        print(f"[{self.larry_id}] Spawning workers...")
        spawned_count = 0
        for spec in worker_specs:
            if self.spawn_worker(spec):
                spawned_count += 1
                time.sleep(2)  # Stagger worker creation

        print(f"[{self.larry_id}] Successfully spawned {spawned_count}/{len(worker_specs)} workers")

        # Monitor workers
        print(f"[{self.larry_id}] Monitoring worker progress...")
        last_update = time.time()

        while True:
            status = self.monitor_workers()

            if status['total'] == 0:
                print(f"[{self.larry_id}] No workers found, waiting...")
                time.sleep(10)
                continue

            progress = int((status['succeeded'] / status['total']) * 100) if status['total'] > 0 else 0

            # Update every 30 seconds
            if time.time() - last_update >= 30:
                print(f"[{self.larry_id}] Progress: {status['succeeded']}/{status['total']} workers completed ({progress}%)")
                print(f"[{self.larry_id}]   Active: {status['active']}, Succeeded: {status['succeeded']}, Failed: {status['failed']}")

                self.update_redis_state("in_progress", progress)
                self.publish_event("progress_update", {
                    "progress": progress,
                    "message": f"{status['succeeded']}/{status['total']} workers completed",
                    "active": status['active'],
                    "succeeded": status['succeeded'],
                    "failed": status['failed']
                })

                last_update = time.time()

            # Check completion
            if status['succeeded'] == status['total']:
                print(f"[{self.larry_id}] All workers completed successfully!")
                self.update_redis_state("completed", 100)
                self.publish_event("phase_complete")
                break

            # Check for failures
            if status['failed'] > 0 and (status['succeeded'] + status['failed']) == status['total']:
                print(f"[{self.larry_id}] WARNING: Some workers failed ({status['failed']} failures)")
                self.update_redis_state("completed_with_errors", progress, {"failures": status['failed']})
                self.publish_event("phase_complete_with_errors", {"failures": status['failed']})
                break

            time.sleep(10)

        # Final summary
        print(f"")
        print(f"[{self.larry_id}] ========================================")
        print(f"[{self.larry_id}]   PHASE COMPLETE")
        print(f"[{self.larry_id}] ========================================")
        print(f"[{self.larry_id}] Workers spawned: {spawned_count}")
        print(f"[{self.larry_id}] Workers succeeded: {status['succeeded']}")
        print(f"[{self.larry_id}] Workers failed: {status['failed']}")
        print(f"[{self.larry_id}] Duration: {(datetime.utcnow() - datetime.fromisoformat(self.start_time.replace('Z', ''))).total_seconds():.2f}s")
        print(f"[{self.larry_id}] ========================================")

        # Keep running for observation
        print(f"[{self.larry_id}] Standing by for additional tasks...")
        while True:
            time.sleep(60)

if __name__ == "__main__":
    coordinator = LarryCoordinator()
    coordinator.run()
