# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install .

# Runtime stage
FROM python:3.12-slim

LABEL org.opencontainers.image.title="mcp-sandfly"
LABEL org.opencontainers.image.description="MCP Server for Sandfly Security"
LABEL org.opencontainers.image.source="https://github.com/ry-ops/mcp-sandfly"
LABEL org.opencontainers.image.licenses="MIT"

# Create non-root user
RUN useradd --create-home --shell /bin/bash mcp

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source
COPY --from=builder /app/src ./src

USER mcp

# Environment variables (override at runtime)
ENV SANDFLY_HOST=""
ENV SANDFLY_USERNAME=""
ENV SANDFLY_PASSWORD=""
ENV SANDFLY_VERIFY_SSL="true"

ENTRYPOINT ["python", "-m", "mcp_sandfly.server"]
