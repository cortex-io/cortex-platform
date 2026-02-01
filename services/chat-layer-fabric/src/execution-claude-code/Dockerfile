FROM python:3.11-slim

WORKDIR /app

# Install Node.js for Claude Code CLI
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Create non-root user with access to npm global
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /home/appuser/.npm-global \
    && chown -R appuser:appuser /home/appuser

USER appuser
ENV PATH="/home/appuser/.npm-global/bin:$PATH"
ENV NPM_CONFIG_PREFIX="/home/appuser/.npm-global"

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
