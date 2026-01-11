"""Main FastAPI application for Anomaly Detector"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import uvicorn
import pandas as pd

from app.config import settings
from app.detectors import EnsembleDetector, BaselineCalculator

# Import from capacity forecaster (shared)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'capacity-forecaster'))
from app.prometheus_client import PrometheusClient
from app.cache import CacheManager

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('anomaly_detector_requests_total', 'Total requests', ['endpoint', 'method'])
REQUEST_DURATION = Histogram('anomaly_detector_request_duration_seconds', 'Request duration', ['endpoint'])
ANOMALIES_DETECTED = Counter('anomaly_detector_anomalies_total', 'Anomalies detected', ['metric', 'severity'])
BASELINE_CALCULATIONS = Counter('anomaly_detector_baselines_calculated_total', 'Baselines calculated')
MODEL_TRAINING = Counter('anomaly_detector_model_training_total', 'Model training runs')
DETECTION_RUNS = Counter('anomaly_detector_detection_runs_total', 'Detection runs', ['method'])

# Global instances
prom_client: Optional[PrometheusClient] = None
detector: Optional[EnsembleDetector] = None
cache: Optional[CacheManager] = None


class DetectionRequest(BaseModel):
    metric_type: str
    resource_type: str
    resource_name: Optional[str] = None
    namespace: Optional[str] = None
    lookback_hours: int = 24
    detection_method: str = "ensemble"  # ensemble, zscore, isolation_forest, autoencoder, dbscan


class AnomalyResponse(BaseModel):
    metric_type: str
    resource_type: str
    resource_name: Optional[str]
    anomalies: List[Dict]
    baseline: Dict
    total_anomalies: int
    anomaly_rate: float
    generated_at: str


class BaselineRequest(BaseModel):
    metric_type: str
    resource_type: str
    resource_name: Optional[str] = None
    namespace: Optional[str] = None
    window_days: int = 7


class HealthResponse(BaseModel):
    status: str
    prometheus_connected: bool
    redis_connected: bool
    timestamp: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global prom_client, detector, cache

    logger.info("Starting Anomaly Detector service...")

    # Initialize components
    prom_client = PrometheusClient()
    detector = EnsembleDetector()
    cache = CacheManager()

    # Verify connections
    if not prom_client.health_check():
        logger.error("Failed to connect to Prometheus")
    else:
        logger.info("Connected to Prometheus")

    if not cache.health_check():
        logger.error("Failed to connect to Redis")
    else:
        logger.info("Connected to Redis")

    logger.info("Anomaly Detector service started successfully")

    yield

    logger.info("Shutting down Anomaly Detector service...")


app = FastAPI(
    title="Anomaly Detector",
    description="Performance baselining and anomaly detection for Kubernetes clusters",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    REQUEST_COUNT.labels(endpoint='/health', method='GET').inc()

    prom_healthy = prom_client.health_check() if prom_client else False
    redis_healthy = cache.health_check() if cache else False

    status = "healthy" if (prom_healthy and redis_healthy) else "degraded"

    return HealthResponse(
        status=status,
        prometheus_connected=prom_healthy,
        redis_connected=redis_healthy,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/baseline/calculate", response_model=Dict)
async def calculate_baseline(request: BaselineRequest):
    """Calculate performance baseline"""
    REQUEST_COUNT.labels(endpoint='/baseline/calculate', method='POST').inc()

    with REQUEST_DURATION.labels(endpoint='/baseline/calculate').time():
        try:
            logger.info(f"Calculating baseline for {request.metric_type} on {request.resource_type}")

            # Fetch historical data
            if request.resource_type == "node" and request.metric_type == "cpu":
                df = prom_client.get_node_cpu_usage(days=request.window_days)
            elif request.resource_type == "node" and request.metric_type == "memory":
                df = prom_client.get_node_memory_usage(days=request.window_days)
            elif request.resource_type == "node" and request.metric_type == "disk":
                df = prom_client.get_node_disk_usage(days=request.window_days)
            elif request.resource_type == "pod" and request.metric_type == "cpu":
                df = prom_client.get_pod_cpu_usage(namespace=request.namespace, days=request.window_days)
            elif request.resource_type == "pod" and request.metric_type == "memory":
                df = prom_client.get_pod_memory_usage(namespace=request.namespace, days=request.window_days)
            else:
                raise HTTPException(status_code=400, detail="Invalid metric/resource combination")

            if df.empty:
                raise HTTPException(status_code=404, detail="No historical data found")

            # Filter by resource name if specified
            if request.resource_name:
                if 'instance' in df.columns:
                    df = df[df['instance'] == request.resource_name]
                elif 'pod' in df.columns:
                    df = df[df['pod'] == request.resource_name]

            # Calculate baseline
            metric_name = f"{request.resource_type}_{request.metric_type}"
            baseline = detector.baseline_calc.calculate_baseline(df, metric_name)

            BASELINE_CALCULATIONS.inc()

            # Cache baseline
            cache_key = f"baseline:{metric_name}"
            cache.set(cache_key, baseline, ttl=86400)  # 24 hours

            return JSONResponse(content=baseline)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error calculating baseline: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect", response_model=AnomalyResponse)
async def detect_anomalies(request: DetectionRequest):
    """Detect anomalies in metrics"""
    REQUEST_COUNT.labels(endpoint='/detect', method='POST').inc()

    with REQUEST_DURATION.labels(endpoint='/detect').time():
        try:
            logger.info(f"Detecting anomalies for {request.metric_type} on {request.resource_type}")

            # Fetch recent data
            lookback_days = max(1, request.lookback_hours // 24)

            if request.resource_type == "node" and request.metric_type == "cpu":
                df = prom_client.get_node_cpu_usage(days=lookback_days)
            elif request.resource_type == "node" and request.metric_type == "memory":
                df = prom_client.get_node_memory_usage(days=lookback_days)
            elif request.resource_type == "node" and request.metric_type == "disk":
                df = prom_client.get_node_disk_usage(days=lookback_days)
            elif request.resource_type == "pod" and request.metric_type == "cpu":
                df = prom_client.get_pod_cpu_usage(namespace=request.namespace, days=lookback_days)
            elif request.resource_type == "pod" and request.metric_type == "memory":
                df = prom_client.get_pod_memory_usage(namespace=request.namespace, days=lookback_days)
            else:
                raise HTTPException(status_code=400, detail="Invalid metric/resource combination")

            if df.empty:
                raise HTTPException(status_code=404, detail="No data found")

            # Filter by resource name if specified
            if request.resource_name:
                if 'instance' in df.columns:
                    df = df[df['instance'] == request.resource_name]
                elif 'pod' in df.columns:
                    df = df[df['pod'] == request.resource_name]

            # Load or get baseline
            metric_name = f"{request.resource_type}_{request.metric_type}"
            baseline = detector.baseline_calc.get_baseline(metric_name)

            if not baseline:
                # Try to load from cache
                cache_key = f"baseline:{metric_name}"
                baseline = cache.get(cache_key)

                if not baseline:
                    # Calculate new baseline
                    baseline = detector.baseline_calc.calculate_baseline(df, metric_name)
                    cache.set(cache_key, baseline, ttl=86400)

            # Detect anomalies
            if request.detection_method == "ensemble":
                result_df = detector.detect(df, metric_name, voting_threshold=2)
            elif request.detection_method == "zscore":
                result_df = detector.zscore_detector.detect(df, baseline)
            elif request.detection_method == "isolation_forest":
                detector.isolation_forest.fit(df)
                result_df = detector.isolation_forest.detect(df)
            elif request.detection_method == "autoencoder":
                detector.autoencoder.fit(df)
                result_df = detector.autoencoder.detect(df)
            elif request.detection_method == "dbscan":
                result_df = detector.dbscan.detect(df)
            else:
                raise HTTPException(status_code=400, detail="Invalid detection method")

            DETECTION_RUNS.labels(method=request.detection_method).inc()

            # Extract anomalies
            anomalies_df = result_df[result_df['is_anomaly'] == True]
            total_anomalies = len(anomalies_df)
            anomaly_rate = total_anomalies / len(result_df) if len(result_df) > 0 else 0.0

            # Prepare anomaly records
            anomaly_records = []
            for _, row in anomalies_df.iterrows():
                severity = "critical" if row.get('anomaly_score', 0) > 2.0 else "warning"

                anomaly = {
                    'timestamp': row['timestamp'].isoformat() if isinstance(row['timestamp'], pd.Timestamp) else str(row['timestamp']),
                    'value': float(row['value']),
                    'anomaly_score': float(row.get('anomaly_score', 0)),
                    'severity': severity,
                    'detection_method': row.get('detection_method', request.detection_method)
                }

                if 'zscore' in row:
                    anomaly['zscore'] = float(row['zscore'])

                anomaly_records.append(anomaly)

                ANOMALIES_DETECTED.labels(metric=metric_name, severity=severity).inc()

            response = {
                'metric_type': request.metric_type,
                'resource_type': request.resource_type,
                'resource_name': request.resource_name,
                'anomalies': anomaly_records,
                'baseline': baseline,
                'total_anomalies': total_anomalies,
                'anomaly_rate': anomaly_rate,
                'generated_at': datetime.utcnow().isoformat()
            }

            return JSONResponse(content=response)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/train")
async def train_models():
    """Train anomaly detection models"""
    REQUEST_COUNT.labels(endpoint='/train', method='POST').inc()

    try:
        logger.info("Starting model training...")

        metrics_to_train = [
            ('node', 'cpu'),
            ('node', 'memory'),
            ('node', 'disk'),
        ]

        results = []

        for resource_type, metric_type in metrics_to_train:
            try:
                if resource_type == "node" and metric_type == "cpu":
                    df = prom_client.get_node_cpu_usage(days=settings.baseline_window_days)
                elif resource_type == "node" and metric_type == "memory":
                    df = prom_client.get_node_memory_usage(days=settings.baseline_window_days)
                elif resource_type == "node" and metric_type == "disk":
                    df = prom_client.get_node_disk_usage(days=settings.baseline_window_days)
                else:
                    continue

                if not df.empty:
                    metric_name = f"{resource_type}_{metric_type}"
                    detector.train(df, metric_name)
                    detector.save_models(settings.model_storage_path, metric_name)

                    MODEL_TRAINING.inc()

                    results.append({
                        'metric': metric_name,
                        'status': 'success',
                        'data_points': len(df)
                    })
                    logger.info(f"Trained models for {metric_name}")

            except Exception as e:
                logger.error(f"Error training {resource_type}_{metric_type}: {e}")
                results.append({
                    'metric': f"{resource_type}_{metric_type}",
                    'status': 'failed',
                    'error': str(e)
                })

        return JSONResponse(content={
            'status': 'completed',
            'timestamp': datetime.utcnow().isoformat(),
            'results': results
        })

    except Exception as e:
        logger.error(f"Error in model training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower()
    )
