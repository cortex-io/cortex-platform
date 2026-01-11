// lib/observability/pipeline/processors/index.js
// Processor exports

const PassthroughProcessor = require('./passthrough');
const EnricherProcessor = require('./enricher');
const SamplerProcessor = require('./sampler');
const FilterProcessor = require('./filter');
const PIIRedactorProcessor = require('./pii-redactor');

module.exports = {
  PassthroughProcessor,
  EnricherProcessor,
  SamplerProcessor,
  FilterProcessor,
  PIIRedactorProcessor
};
