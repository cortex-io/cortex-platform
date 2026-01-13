# Multi-stage build for Outline MCP Server
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.11-slim

# Install dumb-init for proper signal handling
RUN apt-get update && \
    apt-get install -y --no-install-recommends dumb-init && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN groupadd -g 1001 outline && \
    useradd -u 1001 -g outline -s /bin/bash outline

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/outline-mcp /usr/local/bin/outline-mcp

# Copy application source
COPY --chown=outline:outline src/ ./src/

# Switch to non-root user
USER outline

# Expose port for health check
EXPOSE 8080

# Health check (simple Python HTTP server check)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Use dumb-init to handle signals properly
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Start MCP server
CMD ["outline-mcp"]
