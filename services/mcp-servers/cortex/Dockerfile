# Multi-stage build for Cortex MCP Server
# Stage 1: Build dependencies
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production && \
    npm cache clean --force

# Stage 2: Runtime
FROM node:18-alpine

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S cortex && \
    adduser -u 1001 -S cortex -G cortex

# Copy dependencies from builder
COPY --from=builder /app/node_modules ./node_modules

# Copy application source
COPY --chown=cortex:cortex . .

# Create required directories
RUN mkdir -p /app/coordination/{masters,workers,tasks} && \
    chown -R cortex:cortex /app/coordination

# Switch to non-root user
USER cortex

# Expose ports
# 3000: MCP stdio protocol (via HTTP wrapper)
# 8080: Health check and metrics
EXPOSE 3000 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:8080/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1) })"

# Use dumb-init to handle signals properly
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Start MCP SSE server (wraps stdio server)
CMD ["node", "src/sse-server.js"]
