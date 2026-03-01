FROM node:20-alpine

WORKDIR /app

# Install yt-dlp for transcript extraction fallback
RUN apk add --no-cache python3 py3-pip && \
    pip3 install --break-system-packages --no-cache-dir yt-dlp youtube-transcript-api

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --omit=dev

# Copy application code
COPY src/ ./src/
COPY extract_transcript.py ./extract_transcript.py
RUN chmod +x ./extract_transcript.py

# Create data directories and fix permissions
RUN mkdir -p /data/transcripts /data/knowledge /data/cache && \
    chown -R node:node /data /app

# Switch to non-root user
USER node

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:8080/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start the service
CMD ["node", "src/index.js"]


