# Cortex Observability Pipeline

## Overview

The Observability Pipeline is a data processing layer inspired by Datadog Observability Pipelines. It provides a scalable, flexible architecture for collecting, processing, and routing observability data across the Cortex AI Agent System.

**Architecture**: `Sources → Processors → Destinations`

## Key Features

- **Multiple Sources**: Collect events from files, event streams, masters, and workers
- **Flexible Processing**: Transform, filter, enrich, and redact data in-flight
- **Multi-Destination Routing**: Send processed events to multiple destinations simultaneously
- **Backward Compatible**: Works with existing Cortex JSONL logging
- **Extensible**: Easy to add new sources, processors, and destinations

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Sources   │ --> │  Processors  │ --> │ Destinations │
└─────────────┘     └──────────────┘     └──────────────┘
     │                     │                     │
     ├─ FileWatcher       ├─ Enricher           ├─ JSONL
     ├─ EventStream       ├─ Sampler            ├─ Console
     └─ (Future)          ├─ Filter             └─ (Future: PostgreSQL, S3, Webhook)
                          └─ PIIRedactor
```

## Components

### Sources

Sources emit events into the pipeline:

- **FileWatcherSource**: Watches JSONL files for new events (tail-like behavior)
- **EventStreamSource**: Collects events from Cortex event system

### Processors

Processors transform, filter, or enrich events:

- **PassthroughProcessor**: Passes events unchanged (testing/baseline)
- **EnricherProcessor**: Adds metadata (timestamp, hostname, etc.) [Weeks 3-4]
- **SamplerProcessor**: Intelligent sampling (100% errors, 10% success) [Weeks 3-4]
- **FilterProcessor**: Drops low-value events [Weeks 3-4]
- **PIIRedactorProcessor**: Redacts sensitive data [Weeks 3-4]

### Destinations

Destinations receive and store/forward processed events:

- **JSONLDestination**: Writes to JSONL files (backward compatible)
- **ConsoleDestination**: Outputs to console (debugging)
- *Future (Weeks 5-6)*: PostgreSQL, S3, Webhook

## Usage

### Quick Start

```javascript
const { PipelineConfigBuilder } = require('./lib/observability/pipeline/config');

// Create default Cortex pipeline
const pipeline = PipelineConfigBuilder.createDefaultPipeline();

await pipeline.initialize();
await pipeline.start();

// Pipeline is now collecting and processing events
```

### Custom Pipeline

```javascript
const { PipelineConfigBuilder } = require('./lib/observability/pipeline/config');

const pipeline = new PipelineConfigBuilder()
  // Source: Watch specific event files
  .addSource('event-stream', {
    name: 'WorkerEvents',
    eventsDir: 'coordination/events',
    eventTypes: ['worker', 'heartbeat']
  })

  // Processor: Enrich events
  .addProcessor('enricher', {
    name: 'EventEnricher',
    enrichments: ['timestamp', 'hostname']
  })

  // Destination: Write to JSONL
  .addDestination('jsonl', {
    name: 'ProcessedEvents',
    outputPath: 'coordination/observability/processed.jsonl',
    rotateDaily: true
  })

  // Destination: Also write to console
  .addDestination('console', {
    name: 'ConsoleMonitor',
    pretty: true
  })

  .build();

await pipeline.initialize();
await pipeline.start();
```

### JSON Configuration

```javascript
const config = {
  sources: [
    {
      type: 'event-stream',
      config: {
        name: 'CortexEvents',
        eventsDir: 'coordination/events',
        eventTypes: ['all']
      }
    }
  ],
  processors: [
    {
      type: 'enricher',
      config: { enrichments: ['timestamp'] }
    }
  ],
  destinations: [
    {
      type: 'jsonl',
      config: {
        outputPath: 'coordination/observability/pipeline.jsonl',
        rotateDaily: true
      }
    }
  ]
};

const pipeline = PipelineConfigBuilder.fromJSON(config);
await pipeline.initialize();
await pipeline.start();
```

## Examples

Run the included examples:

```bash
# Default Cortex pipeline
node lib/observability/pipeline/example.js default

# Basic file watcher example
node lib/observability/pipeline/example.js basic

# Multi-destination example
node lib/observability/pipeline/example.js multi

# JSON configuration example
node lib/observability/pipeline/example.js json
```

## Monitoring

### Pipeline Health

```javascript
const health = pipeline.getHealth();
console.log(health);

// Output:
// {
//   name: 'ObservabilityPipeline',
//   running: true,
//   metrics: {
//     events_received: 1234,
//     events_processed: 1230,
//     events_dropped: 4,
//     events_delivered: 1230,
//     errors: 0
//   },
//   components: {
//     sources: [...],
//     processors: [...],
//     destinations: [...]
//   }
// }
```

### Metrics

```javascript
const metrics = pipeline.getMetrics();
console.log(metrics);

// Output:
// {
//   events_received: 1234,
//   events_processed: 1230,
//   events_dropped: 4,
//   events_delivered: 1230,
//   errors: 0,
//   uptime: 3600000  // milliseconds
// }
```

## Backward Compatibility

The pipeline is designed to be backward compatible with existing Cortex JSONL logging:

- Existing event files continue to work as-is
- Default pipeline configuration mirrors current behavior
- JSONL destination maintains exact file format
- No breaking changes to existing systems

## Implementation Timeline

### Weeks 1-2: Foundation (Current)
- ✅ Base classes (Source, Processor, Destination)
- ✅ Pipeline orchestrator
- ✅ File watcher and event stream sources
- ✅ JSONL and console destinations
- ✅ Basic processor stubs
- ✅ Configuration builder

### Weeks 3-4: Processors (Next)
- [ ] Implement PII Redactor (integrate with existing PII scanner)
- [ ] Implement Sampler (100% errors, 10% success)
- [ ] Implement Enricher (hostname, master type, metadata)
- [ ] Implement Filter (drop low-value events)
- [ ] Add processor tests

### Weeks 5-6: Destinations
- [ ] PostgreSQL destination (for querying)
- [ ] S3 destination (for archival)
- [ ] Webhook destination (for integrations)
- [ ] Add destination tests

### Weeks 7-8: Search & Query
- [ ] Build search API over processed data
- [ ] Add filtering and aggregation
- [ ] Performance optimization

### Weeks 9-10: Dashboard
- [ ] Simple observability dashboard
- [ ] Metrics visualization
- [ ] Error tracking UI

## Performance

Designed for high throughput:

- **Buffered I/O**: Destinations buffer events for batch writes
- **Async Processing**: Non-blocking event processing
- **Parallel Destinations**: Events sent to multiple destinations concurrently
- **Configurable Buffer Sizes**: Tune for your workload

Target: **1 TB/vCPU/day** (inspired by Datadog's benchmarks)

## Testing

Run tests:

```bash
# Unit tests (coming in Weeks 1-2)
npm test -- lib/observability/pipeline

# Integration tests (coming in Weeks 3-4)
npm test -- lib/observability/pipeline/integration
```

## Contributing

When adding new components:

1. **Sources**: Extend `Source` base class, implement `start()` and `stop()`
2. **Processors**: Extend `Processor` base class, implement `process(event)`
3. **Destinations**: Extend `Destination` base class, implement `send(event)` and `sendBatch(events)`
4. Update the respective `index.js` exports
5. Add to configuration builder type maps
6. Write tests

## Related Documentation

- `/docs/observability-pipeline-design.md` - Detailed architecture design
- `/docs/datadog-comparison.md` - Comparison with Datadog features
- `/lib/observability/tracing/tracer.js` - OpenTelemetry tracing
- `/lib/governance/governance-metrics.js` - Governance metrics

## License

Part of the Cortex AI Agent System. See LICENSE file in repository root.
