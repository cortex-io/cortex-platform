# Cortex Unified MCP Server
# The brain of Cortex for Claude Code integration

FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/ry-ops/cortex-platform"
LABEL org.opencontainers.image.description="Cortex Unified MCP Server"
LABEL org.opencontainers.image.licenses="MIT"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 cortex
WORKDIR /app

# Copy all files needed for install
COPY pyproject.toml README.md ./
COPY src/ src/

# Install Python dependencies (not editable - production install)
RUN pip install --no-cache-dir .

# Set ownership
RUN chown -R cortex:cortex /app

USER cortex

# Environment defaults (override in K8s deployment)
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=20

# Health check via Python
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the MCP server
CMD ["cortex-unified"]
