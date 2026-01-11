// lib/observability/pipeline/sources/index.js
// Source exports

const FileWatcherSource = require('./file-watcher');
const EventStreamSource = require('./event-stream');

module.exports = {
  FileWatcherSource,
  EventStreamSource
};
