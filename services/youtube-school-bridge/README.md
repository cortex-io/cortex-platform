# YouTube-to-School Bridge Service

## Purpose
Transforms youtube-ingestion improvement proposals into the format expected by school-coordinator.

## Data Flow
1. Reads from `youtube:improvements` Redis LIST
2. Unpacks `passive` and `active` improvement arrays
3. Transforms each improvement to school-coordinator format
4. Stores as individual Redis keys (`improvement:{id}`)
5. Adds to `improvements:raw` sorted set (ZSET)

## Input Format (from youtube-ingestion)
```json
{
  "video_id": "xxx",
  "title": "Video Title",
  "relevance": 0.8,
  "improvements": {
    "passive": [...],
    "active": [...]
  }
}
```

## Output Format (to school-coordinator)
```json
{
  "title": "Improvement title",
  "relevance": 0.8,
  "category": "capability",
  "type": "technique",
  "description": "...",
  "implementation_notes": "...",
  "source_video": "xxx",
  "source_title": "Video Title"
}
```

## Environment Variables
- `REDIS_HOST`: Redis server hostname (default: redis-queue.cortex.svc.cluster.local)
- `REDIS_PORT`: Redis server port (default: 6379)
- `POLL_INTERVAL`: Seconds between polls when idle (default: 5)
- `LOG_LEVEL`: Logging level (default: INFO)

## Endpoints
- `GET /health`: Health check
- `GET /status`: Queue sizes and bridge status
