# MCP Server Scaling Documentation

## Overview

This document provides comprehensive scaling strategies for Model Context Protocol (MCP) servers in the cortex automation system. MCP servers benefit from dynamic scaling due to their event-driven nature and variable workloads.

## Table of Contents

1. [KEDA ScaledObject Configurations](#keda-scaledobject-configurations)
2. [Scale-to-Zero Patterns](#scale-to-zero-patterns)
3. [Warm Standby Configuration](#warm-standby-configuration)
4. [Cold Start Optimization](#cold-start-optimization)
5. [Scaling Triggers](#scaling-triggers)
6. [Resource Limits and Requests](#resource-limits-and-requests)
7. [HPA vs KEDA Comparison](#hpa-vs-keda-comparison)
8. [Knative Serving Alternative](#knative-serving-alternative)
9. [Cost Optimization](#cost-optimization)
10. [Scaling Metrics and Monitoring](#scaling-metrics-and-monitoring)

---

## 1. KEDA ScaledObject Configurations

### 1.1 Basic KEDA ScaledObject for MCP Server

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-filesystem-scaler
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-filesystem-server
  pollingInterval: 30  # Seconds between checks
  cooldownPeriod: 300  # Seconds before scaling down
  minReplicaCount: 0   # Scale to zero when idle
  maxReplicaCount: 10  # Maximum pods
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: mcp_request_rate
        threshold: '10'
        query: |
          sum(rate(mcp_requests_total{server="filesystem"}[1m]))
```

### 1.2 HTTP-Based Scaling for MCP Servers

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-http-scaler
  namespace: cortex-mcp
  annotations:
    autoscaling.keda.sh/paused: "false"
spec:
  scaleTargetRef:
    name: mcp-http-server
  pollingInterval: 15
  cooldownPeriod: 180
  minReplicaCount: 0
  maxReplicaCount: 20
  fallback:
    failureThreshold: 3
    replicas: 2
  advanced:
    restoreToOriginalReplicaCount: false
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
          - type: Percent
            value: 50
            periodSeconds: 60
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
          - type: Percent
            value: 100
            periodSeconds: 15
          - type: Pods
            value: 4
            periodSeconds: 15
          selectPolicy: Max
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: http_requests_per_second
        threshold: '100'
        query: |
          sum(rate(http_requests_total{
            namespace="cortex-mcp",
            service="mcp-http-server"
          }[1m]))
```

### 1.3 Queue-Based Scaling for MCP Servers

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-queue-scaler
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-queue-processor
  pollingInterval: 10
  cooldownPeriod: 60
  minReplicaCount: 1  # Keep 1 warm for queue processing
  maxReplicaCount: 50
  triggers:
    # Redis Queue Depth
    - type: redis
      metadata:
        address: redis-master.cortex-mcp:6379
        password: ""
        databaseIndex: "0"
        listName: mcp_task_queue
        listLength: "5"
        activationListLength: "1"

    # RabbitMQ Alternative
    - type: rabbitmq
      metadata:
        host: amqp://guest:guest@rabbitmq.cortex-mcp:5672
        queueName: mcp-tasks
        mode: QueueLength
        value: "10"

    # AWS SQS Alternative
    - type: aws-sqs-queue
      metadata:
        queueURL: https://sqs.us-west-2.amazonaws.com/123456789/mcp-tasks
        queueLength: "5"
        awsRegion: us-west-2
        identityOwner: operator
```

### 1.4 CPU/Memory-Based Scaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-cpu-memory-scaler
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-compute-server
  pollingInterval: 30
  cooldownPeriod: 300
  minReplicaCount: 2
  maxReplicaCount: 15
  triggers:
    - type: cpu
      metricType: Utilization
      metadata:
        value: "70"

    - type: memory
      metricType: Utilization
      metadata:
        value: "80"
```

### 1.5 Custom Metrics Scaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-custom-metrics-scaler
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-ai-inference-server
  pollingInterval: 20
  cooldownPeriod: 240
  minReplicaCount: 0
  maxReplicaCount: 25
  triggers:
    # Active WebSocket Connections
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: active_websocket_connections
        threshold: '50'
        query: |
          sum(websocket_connections_active{
            server="mcp-ai-inference"
          })

    # Pending AI Tasks
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: pending_ai_tasks
        threshold: '20'
        query: |
          sum(ai_tasks_pending{
            server="mcp-ai-inference"
          })

    # Average Response Time (scale up if slow)
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: avg_response_time_seconds
        threshold: '2'
        query: |
          sum(rate(http_request_duration_seconds_sum{
            server="mcp-ai-inference"
          }[5m])) / sum(rate(http_request_duration_seconds_count{
            server="mcp-ai-inference"
          }[5m]))
```

---

## 2. Scale-to-Zero Patterns

### 2.1 Scale-to-Zero Configuration

Scale-to-zero is ideal for MCP servers with intermittent workloads, significantly reducing costs during idle periods.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-scale-to-zero
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-ephemeral-server
  pollingInterval: 30
  cooldownPeriod: 600  # 10 minutes idle before scaling to zero
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: mcp_active_requests
        threshold: '1'
        activationThreshold: '0.1'  # Wake up on any activity
        query: |
          sum(mcp_requests_in_flight{
            server="ephemeral"
          })
```

### 2.2 Idle Timeout Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-idle-config
  namespace: cortex-mcp
data:
  IDLE_TIMEOUT: "600"  # 10 minutes
  IDLE_CHECK_INTERVAL: "60"  # Check every minute
  GRACEFUL_SHUTDOWN_TIMEOUT: "30"  # 30 seconds to finish requests

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-idle-aware-server
  namespace: cortex-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcp-idle-aware-server
  template:
    metadata:
      labels:
        app: mcp-idle-aware-server
    spec:
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        env:
        - name: IDLE_TIMEOUT
          valueFrom:
            configMapKeyRef:
              name: mcp-idle-config
              key: IDLE_TIMEOUT
        - name: IDLE_CHECK_INTERVAL
          valueFrom:
            configMapKeyRef:
              name: mcp-idle-config
              key: IDLE_CHECK_INTERVAL
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 30"]  # Drain connections
```

### 2.3 HTTP Addon for Scale-from-Zero

KEDA HTTP Add-on enables true scale-from-zero with request buffering:

```yaml
apiVersion: http.keda.sh/v1alpha1
kind: HTTPScaledObject
metadata:
  name: mcp-http-scaled
  namespace: cortex-mcp
spec:
  hosts:
  - mcp.cortex.local
  pathPrefixes:
  - /api/mcp
  scaleTargetRef:
    name: mcp-http-server
    service: mcp-http-service
    port: 8080
  replicas:
    min: 0
    max: 20
  targetPendingRequests: 100
  scaledownPeriod: 300
  cooldownPeriod: 120

---
apiVersion: v1
kind: Service
metadata:
  name: mcp-http-service
  namespace: cortex-mcp
spec:
  selector:
    app: mcp-http-server
  ports:
  - port: 8080
    targetPort: 8080
```

---

## 3. Warm Standby Configuration

Warm standby keeps a minimum number of pods ready to handle immediate requests, avoiding cold start latency.

### 3.1 Warm Standby with Minimum Replicas

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-warm-standby
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-critical-server
  pollingInterval: 15
  cooldownPeriod: 180
  minReplicaCount: 3  # Always keep 3 warm pods
  maxReplicaCount: 30
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: mcp_request_rate
        threshold: '50'
        query: |
          sum(rate(mcp_requests_total{
            server="critical"
          }[1m]))
```

### 3.2 Pod Disruption Budget for Warm Standby

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: mcp-warm-standby-pdb
  namespace: cortex-mcp
spec:
  minAvailable: 2  # Always keep at least 2 pods during disruptions
  selector:
    matchLabels:
      app: mcp-critical-server
      tier: warm-standby
```

### 3.3 Warm Standby with Readiness Gates

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-warm-standby-server
  namespace: cortex-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-warm-standby-server
  template:
    metadata:
      labels:
        app: mcp-warm-standby-server
    spec:
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          successThreshold: 2  # Must pass twice before ready
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        startupProbe:
          httpGet:
            path: /health/startup
            port: 8080
          initialDelaySeconds: 0
          periodSeconds: 5
          failureThreshold: 30  # 150 seconds to start
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

---

## 4. Cold Start Optimization

### 4.1 Fast Container Startup

```dockerfile
# Optimized MCP Server Dockerfile
FROM node:20-alpine AS base

# Install dependencies separately for layer caching
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy application code
COPY . .

# Pre-compile TypeScript
RUN npm run build

# Use non-root user
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
USER nodejs

# Warm up the application (pre-load modules)
RUN node --no-warnings --experimental-modules ./dist/warmup.js

EXPOSE 8080
CMD ["node", "--max-old-space-size=512", "./dist/index.js"]
```

### 4.2 Init Container for Warm-up

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-fast-start
  namespace: cortex-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcp-fast-start
  template:
    metadata:
      labels:
        app: mcp-fast-start
    spec:
      # Init container to pre-warm cache
      initContainers:
      - name: cache-warmer
        image: cortex/mcp-server:latest
        command: ["/bin/sh", "-c"]
        args:
          - |
            echo "Pre-warming cache..."
            node /app/scripts/warm-cache.js
            echo "Cache warmed successfully"
        volumeMounts:
        - name: cache
          mountPath: /cache

      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        env:
        - name: CACHE_PATH
          value: /cache
        - name: PRELOAD_MODULES
          value: "true"
        volumeMounts:
        - name: cache
          mountPath: /cache
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"

      volumes:
      - name: cache
        emptyDir: {}
```

### 4.3 Lazy Loading Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-lazy-loading-config
  namespace: cortex-mcp
data:
  config.json: |
    {
      "lazyLoading": {
        "enabled": true,
        "modules": {
          "filesystem": {
            "loadOnDemand": true,
            "cacheTimeout": 3600
          },
          "git": {
            "loadOnDemand": true,
            "cacheTimeout": 1800
          },
          "database": {
            "loadOnDemand": false,
            "preload": true
          }
        }
      },
      "coldStart": {
        "optimizations": {
          "precompileTemplates": true,
          "preconnectDatabases": false,
          "preloadStaticAssets": true
        }
      }
    }
```

### 4.4 Topology-Aware Scheduling

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-topology-aware
  namespace: cortex-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-topology-aware
  template:
    metadata:
      labels:
        app: mcp-topology-aware
    spec:
      # Spread pods across zones for availability
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: mcp-topology-aware

      # Prefer nodes with cached images
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            preference:
              matchExpressions:
              - key: node.kubernetes.io/image-cached
                operator: In
                values:
                - "true"

      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        imagePullPolicy: IfNotPresent  # Use cached images when available
```

---

## 5. Scaling Triggers

### 5.1 HTTP Request-Based Triggers

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-http-triggers
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-http-server
  pollingInterval: 10
  cooldownPeriod: 120
  minReplicaCount: 1
  maxReplicaCount: 30
  triggers:
    # Total requests per second
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: http_requests_per_second
        threshold: '100'
        query: |
          sum(rate(http_requests_total{
            namespace="cortex-mcp",
            service="mcp-http-server"
          }[1m]))

    # Request latency (p95)
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: http_request_duration_p95
        threshold: '1'  # Scale if p95 > 1 second
        query: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{
              namespace="cortex-mcp",
              service="mcp-http-server"
            }[5m])) by (le)
          )

    # Concurrent connections
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: concurrent_connections
        threshold: '200'
        query: |
          sum(http_connections_active{
            namespace="cortex-mcp",
            service="mcp-http-server"
          })
```

### 5.2 Queue Depth Triggers

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-queue-triggers
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-queue-processor
  pollingInterval: 5
  cooldownPeriod: 60
  minReplicaCount: 0
  maxReplicaCount: 100
  triggers:
    # Redis Queue
    - type: redis
      metadata:
        address: redis-master.cortex-mcp:6379
        listName: mcp_high_priority_queue
        listLength: "10"
        activationListLength: "1"

    # Kafka Consumer Lag
    - type: kafka
      metadata:
        bootstrapServers: kafka.cortex-mcp:9092
        consumerGroup: mcp-processors
        topic: mcp-tasks
        lagThreshold: "50"
        activationLagThreshold: "10"

    # NATS JetStream
    - type: nats-jetstream
      metadata:
        natsServerMonitoringEndpoint: nats-monitor.cortex-mcp:8222
        stream: MCP_TASKS
        consumer: mcp-consumer
        lagThreshold: "20"
```

### 5.3 Custom Metrics Triggers

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-custom-triggers
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-ai-server
  pollingInterval: 20
  cooldownPeriod: 180
  minReplicaCount: 2
  maxReplicaCount: 50
  triggers:
    # GPU Utilization
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: gpu_utilization
        threshold: '75'
        query: |
          avg(nvidia_gpu_duty_cycle{
            namespace="cortex-mcp",
            pod=~"mcp-ai-server-.*"
          })

    # Token Processing Rate
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: tokens_per_second
        threshold: '10000'
        query: |
          sum(rate(ai_tokens_processed_total{
            namespace="cortex-mcp",
            service="mcp-ai-server"
          }[1m]))

    # Active AI Sessions
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: active_ai_sessions
        threshold: '25'
        query: |
          sum(ai_sessions_active{
            namespace="cortex-mcp",
            service="mcp-ai-server"
          })
```

### 5.4 Time-Based Scaling (Cron)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-cron-scaling
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-batch-processor
  pollingInterval: 30
  cooldownPeriod: 300
  minReplicaCount: 0
  maxReplicaCount: 20
  triggers:
    # Scale up during business hours (8 AM - 6 PM PST)
    - type: cron
      metadata:
        timezone: America/Los_Angeles
        start: 0 8 * * *
        end: 0 18 * * *
        desiredReplicas: "5"

    # Scale down during off-hours
    - type: cron
      metadata:
        timezone: America/Los_Angeles
        start: 0 18 * * *
        end: 0 8 * * *
        desiredReplicas: "1"

    # Weekend scaling
    - type: cron
      metadata:
        timezone: America/Los_Angeles
        start: 0 0 * * 6  # Saturday
        end: 0 0 * * 1    # Monday
        desiredReplicas: "0"
```

---

## 6. Resource Limits and Requests

### 6.1 Standard MCP Server Resources

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-standard-server
  namespace: cortex-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-standard-server
  template:
    metadata:
      labels:
        app: mcp-standard-server
    spec:
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
            ephemeral-storage: "1Gi"
          limits:
            memory: "512Mi"
            cpu: "500m"
            ephemeral-storage: "2Gi"
        env:
        - name: NODE_OPTIONS
          value: "--max-old-space-size=384"  # 75% of memory limit
```

### 6.2 High-Performance MCP Server Resources

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-high-perf-server
  namespace: cortex-mcp
spec:
  replicas: 5
  selector:
    matchLabels:
      app: mcp-high-perf-server
  template:
    metadata:
      labels:
        app: mcp-high-perf-server
    spec:
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
            ephemeral-storage: "5Gi"
          limits:
            memory: "2Gi"
            cpu: "2000m"
            ephemeral-storage: "10Gi"
        env:
        - name: NODE_OPTIONS
          value: "--max-old-space-size=1536"
```

### 6.3 GPU-Enabled MCP Server Resources

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-gpu-server
  namespace: cortex-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-gpu-server
  template:
    metadata:
      labels:
        app: mcp-gpu-server
    spec:
      nodeSelector:
        nvidia.com/gpu: "true"
      containers:
      - name: mcp-ai-server
        image: cortex/mcp-ai-server:gpu
        resources:
          requests:
            memory: "4Gi"
            cpu: "2000m"
            nvidia.com/gpu: 1
          limits:
            memory: "8Gi"
            cpu: "4000m"
            nvidia.com/gpu: 1
```

### 6.4 Resource Quotas for MCP Namespace

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: mcp-resource-quota
  namespace: cortex-mcp
spec:
  hard:
    requests.cpu: "50"
    requests.memory: "100Gi"
    requests.storage: "500Gi"
    limits.cpu: "100"
    limits.memory: "200Gi"
    persistentvolumeclaims: "20"
    pods: "100"

---
apiVersion: v1
kind: LimitRange
metadata:
  name: mcp-limit-range
  namespace: cortex-mcp
spec:
  limits:
  - max:
      cpu: "4"
      memory: "8Gi"
    min:
      cpu: "100m"
      memory: "128Mi"
    default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "250m"
      memory: "256Mi"
    type: Container
```

---

## 7. HPA vs KEDA Comparison

### 7.1 Comparison Table

| Feature | HPA (Horizontal Pod Autoscaler) | KEDA (Kubernetes Event-Driven Autoscaling) |
|---------|----------------------------------|---------------------------------------------|
| **Metrics Sources** | CPU, Memory, Custom Metrics API | 50+ scalers (Prometheus, Queue, HTTP, Cron, etc.) |
| **Scale to Zero** | No (min 1 replica) | Yes (min 0 replicas) |
| **External Metrics** | Via Custom Metrics API | Built-in support for external systems |
| **Configuration** | Simple, basic | Advanced, feature-rich |
| **Event-Driven** | No | Yes |
| **Multi-Trigger** | No | Yes (combine multiple triggers) |
| **Activation Threshold** | No | Yes (separate from scaling threshold) |
| **Use Case** | General workloads | Event-driven, serverless, cost-sensitive |
| **Complexity** | Low | Medium |
| **Performance** | Good | Excellent for event-driven |

### 7.2 HPA Example

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mcp-hpa
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mcp-server
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
```

### 7.3 KEDA Example (Equivalent)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-keda
  namespace: cortex-mcp
spec:
  scaleTargetRef:
    name: mcp-server
  pollingInterval: 30
  cooldownPeriod: 300
  minReplicaCount: 2
  maxReplicaCount: 10
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
          - type: Percent
            value: 50
            periodSeconds: 60
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
          - type: Percent
            value: 100
            periodSeconds: 15
          - type: Pods
            value: 4
            periodSeconds: 15
          selectPolicy: Max
  triggers:
  - type: cpu
    metricType: Utilization
    metadata:
      value: "70"
  - type: memory
    metricType: Utilization
    metadata:
      value: "80"
```

### 7.4 When to Use HPA vs KEDA

**Use HPA when:**
- Simple CPU/Memory scaling is sufficient
- Minimum 1 replica is acceptable
- Standard Kubernetes metrics are enough
- Low configuration complexity desired
- No external event sources needed

**Use KEDA when:**
- Scale-to-zero is required (cost optimization)
- Event-driven architecture (queues, message brokers)
- Multiple scaling triggers needed
- External metrics from Prometheus, Datadog, etc.
- Serverless-style scaling desired
- Advanced scaling behaviors required

**Use Both (KEDA manages HPA):**
- KEDA creates and manages HPA under the hood
- Combine KEDA's rich triggers with HPA's proven scaling
- Best of both worlds for complex scenarios

---

## 8. Knative Serving Alternative

### 8.1 Knative Service for MCP Server

Knative Serving provides built-in scale-to-zero, traffic splitting, and gradual rollouts.

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: mcp-knative-server
  namespace: cortex-mcp
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/class: "kpa.autoscaling.knative.dev"
        autoscaling.knative.dev/metric: "concurrency"
        autoscaling.knative.dev/target: "100"
        autoscaling.knative.dev/min-scale: "0"
        autoscaling.knative.dev/max-scale: "20"
        autoscaling.knative.dev/scale-down-delay: "5m"
        autoscaling.knative.dev/window: "60s"
        autoscaling.knative.dev/panic-window-percentage: "10"
        autoscaling.knative.dev/panic-threshold-percentage: "200"
    spec:
      containerConcurrency: 100
      timeoutSeconds: 300
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        ports:
        - containerPort: 8080
          protocol: TCP
        env:
        - name: PORT
          value: "8080"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 0
          periodSeconds: 1
          successThreshold: 1
```

### 8.2 Knative with RPS (Requests Per Second) Scaling

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: mcp-rps-scaling
  namespace: cortex-mcp
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/class: "kpa.autoscaling.knative.dev"
        autoscaling.knative.dev/metric: "rps"
        autoscaling.knative.dev/target: "150"
        autoscaling.knative.dev/min-scale: "1"
        autoscaling.knative.dev/max-scale: "50"
    spec:
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        ports:
        - containerPort: 8080
```

### 8.3 Knative with HPA (CPU-based)

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: mcp-hpa-knative
  namespace: cortex-mcp
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/class: "hpa.autoscaling.knative.dev"
        autoscaling.knative.dev/metric: "cpu"
        autoscaling.knative.dev/target: "70"
        autoscaling.knative.dev/min-scale: "2"
        autoscaling.knative.dev/max-scale: "30"
    spec:
      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        resources:
          requests:
            cpu: "500m"
          limits:
            cpu: "1000m"
```

### 8.4 Traffic Splitting with Knative

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: mcp-traffic-split
  namespace: cortex-mcp
spec:
  traffic:
  - revisionName: mcp-server-v1
    percent: 80
  - revisionName: mcp-server-v2
    percent: 20
    tag: canary
  - latestRevision: true
    percent: 0
    tag: latest
```

---

## 9. Cost Optimization Through Scaling

### 9.1 Cost-Optimized Scaling Strategy

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: mcp-cost-optimized
  namespace: cortex-mcp
  annotations:
    cost-optimization.cortex/enabled: "true"
    cost-optimization.cortex/strategy: "aggressive-scale-down"
spec:
  scaleTargetRef:
    name: mcp-cost-optimized-server
  pollingInterval: 60  # Less frequent checks = lower costs
  cooldownPeriod: 600  # Longer cooldown = fewer scaling events
  minReplicaCount: 0   # Scale to zero when idle
  maxReplicaCount: 10  # Cap maximum resources
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-server.monitoring:9090
        metricName: mcp_request_rate
        threshold: '20'  # Higher threshold before scaling
        activationThreshold: '5'
        query: |
          sum(rate(mcp_requests_total[5m]))  # Longer time window
```

### 9.2 Spot/Preemptible Instance Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-spot-instances
  namespace: cortex-mcp
spec:
  replicas: 5
  selector:
    matchLabels:
      app: mcp-spot-instances
  template:
    metadata:
      labels:
        app: mcp-spot-instances
    spec:
      # Tolerate spot instance taints
      tolerations:
      - key: "node.kubernetes.io/spot"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"

      # Prefer spot instances for cost savings
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            preference:
              matchExpressions:
              - key: "node.kubernetes.io/instance-type"
                operator: In
                values:
                - "spot"
                - "preemptible"

      containers:
      - name: mcp-server
        image: cortex/mcp-server:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### 9.3 Vertical Pod Autoscaler (VPA) for Right-Sizing

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: mcp-vpa
  namespace: cortex-mcp
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mcp-server
  updatePolicy:
    updateMode: "Auto"  # Automatically adjust resources
  resourcePolicy:
    containerPolicies:
    - containerName: mcp-server
      minAllowed:
        cpu: "100m"
        memory: "128Mi"
      maxAllowed:
        cpu: "2000m"
        memory: "4Gi"
      controlledResources:
      - cpu
      - memory
      mode: Auto
```

### 9.4 Cost Monitoring Dashboard

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-cost-monitoring
  namespace: cortex-mcp
data:
  prometheus-rules.yaml: |
    groups:
    - name: mcp_cost_optimization
      interval: 60s
      rules:
      - record: mcp:cost:hourly_pod_cost
        expr: |
          sum(
            kube_pod_container_resource_requests{namespace="cortex-mcp"} *
            on(node) group_left() node_cost_hourly
          ) by (pod)

      - record: mcp:cost:total_hourly
        expr: |
          sum(mcp:cost:hourly_pod_cost)

      - record: mcp:cost:waste_potential
        expr: |
          sum(
            kube_pod_container_resource_requests{namespace="cortex-mcp"} -
            kube_pod_container_resource_limits{namespace="cortex-mcp"}
          )

      - alert: HighMCPCost
        expr: mcp:cost:total_hourly > 100
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "MCP server costs exceeding budget"
          description: "Hourly cost is ${{ $value }}, consider scaling down"
```

---

## 10. Scaling Metrics and Monitoring

### 10.1 Prometheus Metrics for MCP Scaling

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-metrics-config
  namespace: cortex-mcp
data:
  prometheus-rules.yaml: |
    groups:
    - name: mcp_scaling_metrics
      interval: 30s
      rules:
      # Request Rate
      - record: mcp:requests:rate1m
        expr: |
          sum(rate(mcp_requests_total{namespace="cortex-mcp"}[1m])) by (server, method)

      # Request Duration (p50, p95, p99)
      - record: mcp:request_duration:p50
        expr: |
          histogram_quantile(0.50,
            sum(rate(mcp_request_duration_seconds_bucket{namespace="cortex-mcp"}[5m])) by (le, server)
          )

      - record: mcp:request_duration:p95
        expr: |
          histogram_quantile(0.95,
            sum(rate(mcp_request_duration_seconds_bucket{namespace="cortex-mcp"}[5m])) by (le, server)
          )

      - record: mcp:request_duration:p99
        expr: |
          histogram_quantile(0.99,
            sum(rate(mcp_request_duration_seconds_bucket{namespace="cortex-mcp"}[5m])) by (le, server)
          )

      # Active Connections
      - record: mcp:connections:active
        expr: |
          sum(mcp_connections_active{namespace="cortex-mcp"}) by (server)

      # Error Rate
      - record: mcp:errors:rate1m
        expr: |
          sum(rate(mcp_requests_total{namespace="cortex-mcp",status=~"5.."}[1m])) by (server)

      # Saturation (CPU/Memory)
      - record: mcp:cpu:utilization
        expr: |
          sum(rate(container_cpu_usage_seconds_total{namespace="cortex-mcp"}[5m])) by (pod) /
          sum(kube_pod_container_resource_limits{namespace="cortex-mcp",resource="cpu"}) by (pod)

      - record: mcp:memory:utilization
        expr: |
          sum(container_memory_working_set_bytes{namespace="cortex-mcp"}) by (pod) /
          sum(kube_pod_container_resource_limits{namespace="cortex-mcp",resource="memory"}) by (pod)

      # Queue Depth
      - record: mcp:queue:depth
        expr: |
          sum(redis_list_length{namespace="cortex-mcp",list=~"mcp_.*_queue"}) by (list)

      # Scaling Events
      - record: mcp:scaling:events_rate
        expr: |
          sum(rate(keda_scaler_activity{namespace="cortex-mcp"}[5m])) by (scaler)
```

### 10.2 Grafana Dashboard for MCP Scaling

```json
{
  "dashboard": {
    "title": "MCP Server Scaling Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "sum(rate(mcp_requests_total{namespace='cortex-mcp'}[1m])) by (server)"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Pod Replicas Over Time",
        "targets": [
          {
            "expr": "kube_deployment_status_replicas{namespace='cortex-mcp'}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(mcp_request_duration_seconds_bucket{namespace='cortex-mcp'}[5m])) by (le, server))"
          }
        ],
        "type": "graph"
      },
      {
        "title": "CPU Utilization",
        "targets": [
          {
            "expr": "sum(rate(container_cpu_usage_seconds_total{namespace='cortex-mcp'}[5m])) by (pod)"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Memory Utilization",
        "targets": [
          {
            "expr": "sum(container_memory_working_set_bytes{namespace='cortex-mcp'}) by (pod)"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Scaling Events",
        "targets": [
          {
            "expr": "sum(rate(keda_scaler_activity{namespace='cortex-mcp'}[5m])) by (scaler)"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

### 10.3 Scaling Alerts

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-scaling-alerts
  namespace: cortex-mcp
data:
  alerts.yaml: |
    groups:
    - name: mcp_scaling_alerts
      rules:
      # High latency despite scaling
      - alert: MCPHighLatencyDespiteScaling
        expr: |
          mcp:request_duration:p95 > 2 and
          kube_deployment_status_replicas{namespace="cortex-mcp"} >=
          kube_deployment_spec_replicas{namespace="cortex-mcp"} * 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MCP server latency high despite scaling"
          description: "P95 latency is {{ $value }}s with {{ $labels.replicas }} replicas"

      # Scaling at maximum capacity
      - alert: MCPAtMaximumScale
        expr: |
          kube_deployment_status_replicas{namespace="cortex-mcp"} >=
          kube_horizontalpodautoscaler_spec_max_replicas{namespace="cortex-mcp"}
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "MCP server at maximum scale"
          description: "{{ $labels.deployment }} has reached max replicas"

      # Frequent scaling events
      - alert: MCPFrequentScaling
        expr: |
          rate(keda_scaler_activity{namespace="cortex-mcp"}[15m]) > 0.5
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "MCP server experiencing frequent scaling"
          description: "Scaling events rate: {{ $value }} per second"

      # Scale-to-zero failing to activate
      - alert: MCPScaleToZeroStuck
        expr: |
          kube_deployment_status_replicas{namespace="cortex-mcp"} > 0 and
          rate(mcp_requests_total{namespace="cortex-mcp"}[10m]) == 0
        for: 30m
        labels:
          severity: info
        annotations:
          summary: "MCP server not scaling to zero despite no traffic"
          description: "{{ $labels.deployment }} has {{ $value }} replicas with no requests"

      # Cold start taking too long
      - alert: MCPColdStartSlow
        expr: |
          avg(mcp_pod_startup_duration_seconds{namespace="cortex-mcp"}) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MCP server cold start slow"
          description: "Average startup time: {{ $value }}s"
```

### 10.4 Custom Metrics Exporter

```javascript
// mcp-metrics-exporter.js
const express = require('express');
const promClient = require('prom-client');

const app = express();
const register = new promClient.Registry();

// Default metrics
promClient.collectDefaultMetrics({ register });

// Custom MCP metrics
const requestCounter = new promClient.Counter({
  name: 'mcp_requests_total',
  help: 'Total number of MCP requests',
  labelNames: ['server', 'method', 'status'],
  registers: [register]
});

const requestDuration = new promClient.Histogram({
  name: 'mcp_request_duration_seconds',
  help: 'MCP request duration in seconds',
  labelNames: ['server', 'method'],
  buckets: [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10],
  registers: [register]
});

const activeConnections = new promClient.Gauge({
  name: 'mcp_connections_active',
  help: 'Number of active MCP connections',
  labelNames: ['server'],
  registers: [register]
});

const queueDepth = new promClient.Gauge({
  name: 'mcp_queue_depth',
  help: 'Current queue depth',
  labelNames: ['queue'],
  registers: [register]
});

const podStartupDuration = new promClient.Histogram({
  name: 'mcp_pod_startup_duration_seconds',
  help: 'Time taken for pod to become ready',
  buckets: [1, 5, 10, 30, 60, 120],
  registers: [register]
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

const PORT = process.env.METRICS_PORT || 9090;
app.listen(PORT, () => {
  console.log(`Metrics server listening on port ${PORT}`);
});

module.exports = {
  requestCounter,
  requestDuration,
  activeConnections,
  queueDepth,
  podStartupDuration
};
```

### 10.5 ServiceMonitor for Prometheus Operator

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: mcp-server-metrics
  namespace: cortex-mcp
  labels:
    app: mcp-server
spec:
  selector:
    matchLabels:
      app: mcp-server
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
    relabelings:
    - sourceLabels: [__meta_kubernetes_pod_name]
      targetLabel: pod
    - sourceLabels: [__meta_kubernetes_namespace]
      targetLabel: namespace
```

---

## Summary

This documentation provides comprehensive scaling strategies for MCP servers:

1. **KEDA ScaledObjects** - Event-driven autoscaling with 50+ triggers
2. **Scale-to-Zero** - Cost optimization through idle scaling
3. **Warm Standby** - Balance cost and performance with minimum replicas
4. **Cold Start Optimization** - Fast startup through image caching and pre-warming
5. **Scaling Triggers** - HTTP, queue, custom metrics, and time-based scaling
6. **Resource Management** - Right-sized requests and limits
7. **HPA vs KEDA** - Choose the right autoscaler for your workload
8. **Knative Serving** - Serverless alternative with traffic splitting
9. **Cost Optimization** - Spot instances, VPA, and aggressive scale-down
10. **Monitoring** - Comprehensive metrics, dashboards, and alerts

**Key Takeaways:**
- Use KEDA for event-driven workloads requiring scale-to-zero
- Use HPA for simple CPU/Memory scaling with minimum 1 replica
- Use Knative for full serverless experience with traffic management
- Optimize cold starts with image caching and lazy loading
- Monitor scaling metrics to tune thresholds and prevent flapping
- Implement cost controls with spot instances and aggressive scale-down

**Next Steps:**
1. Review `/Users/ryandahlberg/Projects/cortex/coordination/resource-manager/mcp-scaling.json` for templates
2. Deploy KEDA operator: `kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.12.0/keda-2.12.0.yaml`
3. Implement metrics exporter in MCP servers
4. Configure Prometheus ServiceMonitors
5. Set up Grafana dashboards for visualization
6. Test scale-to-zero behavior in staging environment

For questions or additional scaling patterns, consult the cortex development team.
