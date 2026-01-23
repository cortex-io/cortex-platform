FROM python:3.12-alpine

LABEL maintainer="Cortex Team"
LABEL description="Cortex Intelligent Orchestrator - Adaptive pod lifecycle management"

# Install system dependencies
RUN apk add --no-cache curl ca-certificates

# Create non-root user (Alpine uses adduser)
RUN adduser -D -u 1000 -s /bin/sh orchestrator

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server/ ./server/
COPY __init__.py .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R orchestrator:orchestrator /app

# Switch to non-root user
USER orchestrator

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
EXPOSE 8080 9090

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO

# Run the orchestrator
CMD ["python", "-m", "server.main"]
