// lib/observability/pipeline/destinations/index.js
// Destination exports

const JSONLDestination = require('./jsonl');
const ConsoleDestination = require('./console');
const PostgreSQLDestination = require('./postgresql');
const S3Destination = require('./s3');
const WebhookDestination = require('./webhook');

module.exports = {
  JSONLDestination,
  ConsoleDestination,
  PostgreSQLDestination,
  S3Destination,
  WebhookDestination
};
