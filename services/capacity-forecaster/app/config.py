"""Configuration management for Capacity Forecaster"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Prometheus Settings
    prometheus_url: str = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
    prometheus_timeout: int = 30

    # Redis Settings
    redis_host: str = "redis.cortex-system.svc.cluster.local"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # Model Settings
    model_storage_path: str = "/app/models"
    model_retrain_interval_days: int = 7
    historical_data_days: int = 30

    # Forecasting Settings
    forecast_short_term_days: int = 7
    forecast_medium_term_days: int = 30
    forecast_long_term_days: int = 90

    # Thresholds
    cpu_warning_threshold: float = 0.75
    cpu_critical_threshold: float = 0.90
    memory_warning_threshold: float = 0.80
    memory_critical_threshold: float = 0.95
    disk_warning_threshold: float = 0.75
    disk_critical_threshold: float = 0.90

    # Metrics
    metrics_port: int = 9100

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
