// lib/observability/pipeline/index.js
// Observability Pipeline - Main Orchestrator
// Architecture: Sources → Processors → Destinations
//
// Inspired by Datadog Observability Pipelines
// Built for Cortex AI Agent System

const EventEmitter = require('events');
const { PipelineComponent } = require('./base');

class ObservabilityPipeline extends EventEmitter {
  constructor(config = {}) {
    super();

    this.name = config.name || 'ObservabilityPipeline';
    this.sources = [];
    this.processors = [];
    this.destinations = [];
    this.metrics = {
      events_received: 0,
      events_processed: 0,
      events_dropped: 0,
      events_delivered: 0,
      errors: 0,
      started_at: null
    };
    this.running = false;
  }

  /**
   * Add a source to the pipeline
   * @param {Source} source
   */
  addSource(source) {
    if (!source || typeof source.start !== 'function') {
      throw new Error('Invalid source: must implement start() method');
    }

    // Listen for events from source
    source.on('event', async (event) => {
      await this.processEvent(event);
    });

    source.on('error', (error) => {
      this.metrics.errors++;
      this.emit('source_error', { source: source.name, error });
    });

    this.sources.push(source);
    this.emit('source_added', { name: source.name });

    return this;
  }

  /**
   * Add a processor to the pipeline
   * @param {Processor} processor
   */
  addProcessor(processor) {
    if (!processor || typeof processor.process !== 'function') {
      throw new Error('Invalid processor: must implement process() method');
    }

    processor.on('error', (error) => {
      this.metrics.errors++;
      this.emit('processor_error', { processor: processor.name, error });
    });

    this.processors.push(processor);
    this.emit('processor_added', { name: processor.name });

    return this;
  }

  /**
   * Add a destination to the pipeline
   * @param {Destination} destination
   */
  addDestination(destination) {
    if (!destination || typeof destination.write !== 'function') {
      throw new Error('Invalid destination: must implement write() method');
    }

    destination.on('error', (error) => {
      this.metrics.errors++;
      this.emit('destination_error', { destination: destination.name, error });
    });

    destination.on('flush', (info) => {
      this.emit('destination_flush', { destination: destination.name, ...info });
    });

    this.destinations.push(destination);
    this.emit('destination_added', { name: destination.name });

    return this;
  }

  /**
   * Initialize all pipeline components
   * @returns {Promise<void>}
   */
  async initialize() {
    // Initialize all sources
    for (const source of this.sources) {
      await source.initialize();
    }

    // Initialize all processors
    for (const processor of this.processors) {
      await processor.initialize();
    }

    // Initialize all destinations
    for (const destination of this.destinations) {
      await destination.initialize();
    }

    this.emit('initialized');
  }

  /**
   * Start the pipeline
   * @returns {Promise<void>}
   */
  async start() {
    if (this.running) {
      return;
    }

    this.running = true;
    this.metrics.started_at = new Date().toISOString();

    // Start all sources
    for (const source of this.sources) {
      await source.start();
    }

    this.emit('started', {
      sources: this.sources.length,
      processors: this.processors.length,
      destinations: this.destinations.length
    });
  }

  /**
   * Stop the pipeline
   * @returns {Promise<void>}
   */
  async stop() {
    if (!this.running) {
      return;
    }

    this.running = false;

    // Stop all sources
    for (const source of this.sources) {
      await source.stop();
    }

    // Shutdown all destinations (flushes buffers)
    for (const destination of this.destinations) {
      await destination.shutdown();
    }

    this.emit('stopped');
  }

  /**
   * Process a single event through the pipeline
   * @param {Object} event
   * @returns {Promise<void>}
   */
  async processEvent(event) {
    if (!this.running) {
      return;
    }

    this.metrics.events_received++;

    try {
      // Run event through processors
      let processedEvent = event;

      for (const processor of this.processors) {
        processedEvent = await processor.processWithMetrics(processedEvent);

        // If processor returns null, drop the event
        if (processedEvent === null) {
          this.metrics.events_dropped++;
          this.emit('event_dropped', { event, processor: processor.name });
          return;
        }
      }

      this.metrics.events_processed++;

      // Send to all destinations
      await this.deliverEvent(processedEvent);

    } catch (error) {
      this.metrics.errors++;
      this.emit('processing_error', { event, error });
    }
  }

  /**
   * Deliver processed event to all destinations
   * @param {Object} event
   * @returns {Promise<void>}
   */
  async deliverEvent(event) {
    const deliveryPromises = this.destinations.map(async (destination) => {
      try {
        await destination.write(event);
        this.metrics.events_delivered++;
      } catch (error) {
        this.emit('delivery_error', { destination: destination.name, event, error });
      }
    });

    await Promise.all(deliveryPromises);
  }

  /**
   * Get pipeline health status
   * @returns {Object}
   */
  getHealth() {
    return {
      name: this.name,
      running: this.running,
      metrics: this.metrics,
      components: {
        sources: this.sources.map(s => s.getHealth()),
        processors: this.processors.map(p => p.getHealth()),
        destinations: this.destinations.map(d => d.getHealth())
      },
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get pipeline metrics
   * @returns {Object}
   */
  getMetrics() {
    return {
      ...this.metrics,
      uptime: this.metrics.started_at
        ? Date.now() - new Date(this.metrics.started_at).getTime()
        : 0
    };
  }
}

// Export everything
module.exports = {
  ObservabilityPipeline,
  ...require('./base'),
  sources: require('./sources'),
  processors: require('./processors'),
  destinations: require('./destinations')
};
