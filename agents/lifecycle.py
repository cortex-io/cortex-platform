"""
Agent lifecycle management: spawning, monitoring, and terminating agents.

Supports multiple spawn modes:
- subprocess: Local process (development)
- kubernetes: K8s Job (production)
"""

import asyncio
import logging
import os
import subprocess
from enum import Enum
from typing import Dict, List, Optional

import yaml


logger = logging.getLogger(__name__)


class SpawnMode(str, Enum):
    """Agent spawn mode."""

    SUBPROCESS = "subprocess"
    KUBERNETES = "kubernetes"


class AgentLifecycle:
    """
    Manages agent lifecycle: spawning, monitoring, and termination.

    Masters use this class to spawn worker agents.
    Supports both local subprocess (dev) and Kubernetes Job (prod) modes.
    """

    def __init__(
        self,
        spawn_mode: SpawnMode = SpawnMode.SUBPROCESS,
        namespace: str = "cortex-system",
    ):
        """
        Initialize lifecycle manager.

        Args:
            spawn_mode: How to spawn agents (subprocess or kubernetes)
            namespace: Kubernetes namespace for Job spawning
        """
        self.spawn_mode = spawn_mode
        self.namespace = namespace
        self._processes: Dict[str, subprocess.Popen] = {}
        self._kubernetes_jobs: Dict[str, str] = {}  # agent_id -> job_name

    async def spawn_worker(
        self,
        agent_id: str,
        worker_class: str,
        python_path: str = "python",
        env_vars: Optional[Dict[str, str]] = None,
        image: str = "cortex/worker:latest",
        cpu_request: str = "100m",
        memory_request: str = "256Mi",
    ) -> bool:
        """
        Spawn a worker agent.

        Args:
            agent_id: Unique agent ID
            worker_class: Python module path (e.g., "workers.sandfly_worker")
            python_path: Path to Python interpreter (subprocess mode)
            env_vars: Environment variables to pass
            image: Container image (kubernetes mode)
            cpu_request: CPU request (kubernetes mode)
            memory_request: Memory request (kubernetes mode)

        Returns:
            True if spawn succeeded

        Raises:
            ValueError: If spawn mode is invalid
        """
        env_vars = env_vars or {}
        env_vars["AGENT_ID"] = agent_id

        if self.spawn_mode == SpawnMode.SUBPROCESS:
            return await self._spawn_subprocess(agent_id, worker_class, python_path, env_vars)
        elif self.spawn_mode == SpawnMode.KUBERNETES:
            return await self._spawn_kubernetes(
                agent_id, worker_class, image, env_vars, cpu_request, memory_request
            )
        else:
            raise ValueError(f"Invalid spawn mode: {self.spawn_mode}")

    async def _spawn_subprocess(
        self,
        agent_id: str,
        worker_class: str,
        python_path: str,
        env_vars: Dict[str, str],
    ) -> bool:
        """Spawn worker as local subprocess."""
        try:
            # Build command
            cmd = [
                python_path,
                "-m",
                worker_class,
            ]

            # Merge environment variables
            env = os.environ.copy()
            env.update(env_vars)

            # Start process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self._processes[agent_id] = process
            logger.info(f"Spawned worker {agent_id} as subprocess (PID: {process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to spawn subprocess worker {agent_id}: {e}")
            return False

    async def _spawn_kubernetes(
        self,
        agent_id: str,
        worker_class: str,
        image: str,
        env_vars: Dict[str, str],
        cpu_request: str,
        memory_request: str,
    ) -> bool:
        """Spawn worker as Kubernetes Job."""
        try:
            job_name = f"worker-{agent_id.lower().replace('_', '-')}"

            # Build Job manifest
            job_manifest = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": job_name,
                    "namespace": self.namespace,
                    "labels": {
                        "app": "cortex-worker",
                        "agent-id": agent_id,
                        "worker-class": worker_class.replace(".", "-"),
                    },
                },
                "spec": {
                    "ttlSecondsAfterFinished": 3600,  # Cleanup after 1 hour
                    "template": {
                        "metadata": {
                            "labels": {
                                "app": "cortex-worker",
                                "agent-id": agent_id,
                            }
                        },
                        "spec": {
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "worker",
                                    "image": image,
                                    "command": ["python", "-m", worker_class],
                                    "env": [
                                        {"name": k, "value": v}
                                        for k, v in env_vars.items()
                                    ],
                                    "resources": {
                                        "requests": {
                                            "cpu": cpu_request,
                                            "memory": memory_request,
                                        }
                                    },
                                }
                            ],
                        },
                    },
                },
            }

            # Write manifest to temporary file
            manifest_path = f"/tmp/{job_name}.yaml"
            with open(manifest_path, "w") as f:
                yaml.dump(job_manifest, f)

            # Apply with kubectl
            result = subprocess.run(
                ["kubectl", "apply", "-f", manifest_path],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self._kubernetes_jobs[agent_id] = job_name
                logger.info(f"Spawned worker {agent_id} as Kubernetes Job: {job_name}")
                os.remove(manifest_path)
                return True
            else:
                logger.error(f"Failed to create Kubernetes Job: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to spawn Kubernetes worker {agent_id}: {e}")
            return False

    async def terminate_worker(self, agent_id: str, timeout: int = 30) -> bool:
        """
        Terminate a worker agent.

        Args:
            agent_id: Agent ID to terminate
            timeout: Grace period in seconds

        Returns:
            True if termination succeeded
        """
        if self.spawn_mode == SpawnMode.SUBPROCESS:
            return await self._terminate_subprocess(agent_id, timeout)
        elif self.spawn_mode == SpawnMode.KUBERNETES:
            return await self._terminate_kubernetes(agent_id)
        else:
            raise ValueError(f"Invalid spawn mode: {self.spawn_mode}")

    async def _terminate_subprocess(self, agent_id: str, timeout: int) -> bool:
        """Terminate subprocess worker."""
        process = self._processes.get(agent_id)
        if not process:
            logger.warning(f"No subprocess found for agent {agent_id}")
            return False

        try:
            # Try graceful termination
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Force kill if timeout
                logger.warning(f"Worker {agent_id} did not terminate gracefully, killing")
                process.kill()
                process.wait()

            del self._processes[agent_id]
            logger.info(f"Terminated subprocess worker {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Error terminating subprocess worker {agent_id}: {e}")
            return False

    async def _terminate_kubernetes(self, agent_id: str) -> bool:
        """Terminate Kubernetes Job worker."""
        job_name = self._kubernetes_jobs.get(agent_id)
        if not job_name:
            logger.warning(f"No Kubernetes Job found for agent {agent_id}")
            return False

        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "delete",
                    "job",
                    job_name,
                    "-n",
                    self.namespace,
                    "--grace-period=30",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                del self._kubernetes_jobs[agent_id]
                logger.info(f"Terminated Kubernetes Job worker: {job_name}")
                return True
            else:
                logger.error(f"Failed to delete Kubernetes Job: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error terminating Kubernetes worker {agent_id}: {e}")
            return False

    async def monitor_workers(self) -> Dict[str, bool]:
        """
        Check health of all spawned workers.

        Returns:
            Dictionary mapping agent_id -> is_alive
        """
        health_status = {}

        if self.spawn_mode == SpawnMode.SUBPROCESS:
            for agent_id, process in self._processes.items():
                health_status[agent_id] = process.poll() is None

        elif self.spawn_mode == SpawnMode.KUBERNETES:
            for agent_id, job_name in self._kubernetes_jobs.items():
                try:
                    result = subprocess.run(
                        [
                            "kubectl",
                            "get",
                            "job",
                            job_name,
                            "-n",
                            self.namespace,
                            "-o",
                            "jsonpath={.status.active}",
                        ],
                        capture_output=True,
                        text=True,
                    )
                    # Job is active if it has active pods
                    health_status[agent_id] = result.returncode == 0 and result.stdout.strip() == "1"
                except Exception as e:
                    logger.error(f"Error checking Job status for {agent_id}: {e}")
                    health_status[agent_id] = False

        return health_status

    async def cleanup_all(self) -> None:
        """Terminate all spawned workers."""
        agent_ids = list(self._processes.keys()) + list(self._kubernetes_jobs.keys())
        logger.info(f"Cleaning up {len(agent_ids)} workers")

        for agent_id in agent_ids:
            await self.terminate_worker(agent_id)

        logger.info("Cleanup complete")

    def get_active_workers(self) -> List[str]:
        """
        Get list of active worker agent IDs.

        Returns:
            List of agent IDs
        """
        if self.spawn_mode == SpawnMode.SUBPROCESS:
            return list(self._processes.keys())
        elif self.spawn_mode == SpawnMode.KUBERNETES:
            return list(self._kubernetes_jobs.keys())
        else:
            return []
