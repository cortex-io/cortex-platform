FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy shared modules from capacity-forecaster
RUN mkdir -p /app/shared
COPY ../capacity-forecaster/app/prometheus_client.py /app/shared/ || echo "Warning: shared module not found"
COPY ../capacity-forecaster/app/cache.py /app/shared/ || echo "Warning: shared module not found"

# Create model storage directory
RUN mkdir -p /app/models

# Expose ports
EXPOSE 8001 9101

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
