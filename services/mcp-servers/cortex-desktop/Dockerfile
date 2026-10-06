FROM node:20-alpine

WORKDIR /app

# Install kubectl and dependencies
RUN apk add --no-cache curl && \
    curl -LO "https://dl.k8s.io/release/v1.33.1/bin/linux/amd64/kubectl" && \
    echo "5de4e9f2266738fd112b721265a0c1cd7f4e5208b670f811861f699474a100a3  kubectl" | sha256sum -c - && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    apk del curl

# Install Node.js dependencies
COPY package*.json ./
RUN npm install --only=production

# Copy application
COPY server.js ./

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:8765/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Run server
CMD ["node", "server.js"]


