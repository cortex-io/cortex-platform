"""Main FastAPI application for Capacity Forecaster"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import uvicorn

from app.config import settings
from app.prometheus_client import PrometheusClient
from app.models import CapacityForecaster
from app.cache import CacheManager

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('capacity_forecaster_requests_total', 'Total requests', ['endpoint', 'method'])
REQUEST_DURATION = Histogram('capacity_forecaster_request_duration_seconds', 'Request duration', ['endpoint'])
FORECAST_GENERATION = Counter('capacity_forecaster_forecasts_generated_total', 'Forecasts generated', ['metric'])
ALERTS_GENERATED = Counter('capacity_forecaster_alerts_generated_total', 'Alerts generated', ['severity'])
MODEL_TRAINING = Counter('capacity_forecaster_model_training_total', 'Model training runs', ['model_type'])
CACHE_HITS = Counter('capacity_forecaster_cache_hits_total', 'Cache hits')
CACHE_MISSES = Counter('capacity_forecaster_cache_misses_total', 'Cache misses')

# Global instances
prom_client: Optional[PrometheusClient] = None
forecaster: Optional[CapacityForecaster] = None
cache: Optional[CacheManager] = None


class ForecastRequest(BaseModel):
    metric_type: str  # cpu, memory, disk, network
    resource_type: str  # node, pod, pvc
    resource_name: Optional[str] = None
    namespace: Optional[str] = None
    horizon_days: int = 7


class ForecastResponse(BaseModel):
    metric_type: str
    resource_type: str
    resource_name: Optional[str]
    forecast: List[Dict]
    alerts: List[Dict]
    generated_at: str
    horizon_days: int


class HealthResponse(BaseModel):
    status: str
    prometheus_connected: bool
    redis_connected: bool
    timestamp: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global prom_client, forecaster, cache

    logger.info("Starting Capacity Forecaster service...")

    # Initialize components
    prom_client = PrometheusClient()
    forecaster = CapacityForecaster()
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

    logger.info("Capacity Forecaster service started successfully")

    yield

    logger.info("Shutting down Capacity Forecaster service...")


app = FastAPI(
    title="Capacity Forecaster",
    description="AI-driven capacity forecasting for Kubernetes clusters",
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


@app.post("/forecast", response_model=ForecastResponse)
async def generate_forecast(request: ForecastRequest):
    """Generate capacity forecast"""
    REQUEST_COUNT.labels(endpoint='/forecast', method='POST').inc()

    with REQUEST_DURATION.labels(endpoint='/forecast').time():
        try:
            # Check cache
            cache_key = f"forecast:{request.metric_type}:{request.resource_type}:{request.resource_name}:{request.horizon_days}"
            cached_result = cache.get(cache_key)

            if cached_result:
                CACHE_HITS.inc()
                logger.info(f"Cache hit for {cache_key}")
                return JSONResponse(content=cached_result)

            CACHE_MISSES.inc()

            # Fetch historical data
            logger.info(f"Generating forecast for {request.metric_type} on {request.resource_type}")

            if request.resource_type == "node" and request.metric_type == "cpu":
                df = prom_client.get_node_cpu_usage(days=settings.historical_data_days)
            elif request.resource_type == "node" and request.metric_type == "memory":
                df = prom_client.get_node_memory_usage(days=settings.historical_data_days)
            elif request.resource_type == "node" and request.metric_type == "disk":
                df = prom_client.get_node_disk_usage(days=settings.historical_data_days)
            elif request.resource_type == "pod" and request.metric_type == "cpu":
                df = prom_client.get_pod_cpu_usage(namespace=request.namespace, days=settings.historical_data_days)
            elif request.resource_type == "pod" and request.metric_type == "memory":
                df = prom_client.get_pod_memory_usage(namespace=request.namespace, days=settings.historical_data_days)
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

            # Generate forecast
            periods = request.horizon_days * 288  # 5-min intervals
            forecast_df = forecaster.forecast(df, f"{request.resource_type}_{request.metric_type}", periods=periods)

            if forecast_df.empty:
                raise HTTPException(status_code=500, detail="Failed to generate forecast")

            # Detect capacity issues
            if request.metric_type == "cpu":
                alerts = forecaster.detect_capacity_issues(
                    forecast_df,
                    settings.cpu_warning_threshold,
                    settings.cpu_critical_threshold
                )
            elif request.metric_type == "memory":
                alerts = forecaster.detect_capacity_issues(
                    forecast_df,
                    settings.memory_warning_threshold,
                    settings.memory_critical_threshold
                )
            elif request.metric_type == "disk":
                alerts = forecaster.detect_capacity_issues(
                    forecast_df,
                    settings.disk_warning_threshold,
                    settings.disk_critical_threshold
                )
            else:
                alerts = []

            # Update metrics
            FORECAST_GENERATION.labels(metric=f"{request.resource_type}_{request.metric_type}").inc()
            for alert in alerts:
                ALERTS_GENERATED.labels(severity=alert['severity']).inc()

            # Prepare response
            forecast_data = forecast_df.to_dict('records')
            for record in forecast_data:
                if isinstance(record.get('timestamp'), pd.Timestamp):
                    record['timestamp'] = record['timestamp'].isoformat()

            response = {
                'metric_type': request.metric_type,
                'resource_type': request.resource_type,
                'resource_name': request.resource_name,
                'forecast': forecast_data,
                'alerts': alerts,
                'generated_at': datetime.utcnow().isoformat(),
                'horizon_days': request.horizon_days
            }

            # Cache result for 1 hour
            cache.set(cache_key, response, ttl=3600)

            return JSONResponse(content=response)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating forecast: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecasts/recent")
async def get_recent_forecasts():
    """Get recently generated forecasts from cache"""
    REQUEST_COUNT.labels(endpoint='/forecasts/recent', method='GET').inc()

    try:
        # Get all forecast keys from cache
        forecast_keys = cache.get_keys("forecast:*")
        forecasts = []

        for key in forecast_keys[:10]:  # Limit to 10 most recent
            forecast = cache.get(key)
            if forecast:
                forecasts.append(forecast)

        return JSONResponse(content={'forecasts': forecasts, 'count': len(forecasts)})

    except Exception as e:
        logger.error(f"Error fetching recent forecasts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/train")
async def trigger_model_training():
    """Manually trigger model training"""
    REQUEST_COUNT.labels(endpoint='/train', method='POST').inc()

    try:
        logger.info("Starting manual model training...")

        # Train models for each metric type
        metrics_to_train = [
            ('node', 'cpu'),
            ('node', 'memory'),
            ('node', 'disk'),
        ]

        results = []

        for resource_type, metric_type in metrics_to_train:
            try:
                if resource_type == "node" and metric_type == "cpu":
                    df = prom_client.get_node_cpu_usage(days=settings.historical_data_days)
                elif resource_type == "node" and metric_type == "memory":
                    df = prom_client.get_node_memory_usage(days=settings.historical_data_days)
                elif resource_type == "node" and metric_type == "disk":
                    df = prom_client.get_node_disk_usage(days=settings.historical_data_days)
                else:
                    continue

                if not df.empty:
                    model_name = f"{resource_type}_{metric_type}"
                    prophet_model = forecaster.train_prophet_model(df, model_name)
                    forecaster.save_model(prophet_model, f"{model_name}_prophet")

                    MODEL_TRAINING.labels(model_type='prophet').inc()

                    results.append({
                        'metric': model_name,
                        'status': 'success',
                        'data_points': len(df)
                    })
                    logger.info(f"Trained model for {model_name}")

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
