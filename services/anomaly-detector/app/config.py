"""Configuration management for Anomaly Detector"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_workers: int = 4

    # Prometheus Settings
    prometheus_url: str = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
    prometheus_timeout: int = 30

    # Redis Settings
    redis_host: str = "redis-master.cortex-capacity.svc.cluster.local"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: Optional[str] = None

    # Model Settings
    model_storage_path: str = "/app/models"
    model_retrain_interval_hours: int = 24
    baseline_window_days: int = 7

    # Anomaly Detection Settings
    zscore_threshold: float = 3.0
    isolation_forest_contamination: float = 0.1
    autoencoder_threshold: float = 0.95
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5

    # Alerting
    alertmanager_url: str = "http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093"

    # Metrics
    metrics_port: int = 9101

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
