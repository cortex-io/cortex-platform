// lib/observability/api/index.js
// Observability API exports

const ObservabilityAPIServer = require('./server');
const PostgreSQLDataSource = require('./datasources/postgresql');

module.exports = {
  ObservabilityAPIServer,
  PostgreSQLDataSource
};
