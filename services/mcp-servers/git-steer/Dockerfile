FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/cortex-io/cortex-platform"
LABEL org.opencontainers.image.description="git-steer MCP server — git/GitHub operations for Cortex"

# git is required by GitPython for subprocess fallback paths
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Configure git to trust the repo cache dir (used by GitPython)
RUN git config --global --add safe.directory '*'

RUN useradd -m -u 1000 cortex
WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Repo cache dir — will be mounted as a PVC in k3s
RUN mkdir -p /repos && chown cortex:cortex /repos

RUN chown -R cortex:cortex /app
USER cortex

ENV PYTHONUNBUFFERED=1
ENV GIT_STEER_CACHE_DIR=/repos

CMD ["git-steer"]
