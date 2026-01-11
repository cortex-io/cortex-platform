/**
 * Intelligent Scheduler Module
 *
 * ML-powered task scheduling with resource prediction and SLA-aware prioritization.
 *
 * @module lib/scheduler
 */

const { IntelligentScheduler, createIntelligentScheduler } = require('./intelligent-scheduler');
const { ResourcePredictor, HEURISTIC_ESTIMATES } = require('./resource-predictor');
const { FeasibilityChecker, SystemResourceMonitor, TokenBudgetTracker } = require('./feasibility-checker');
const { PriorityEngine, DEFAULT_PRIORITY_WEIGHTS, PRIORITY_LEVEL_MULTIPLIERS } = require('./priority-engine');
const { LinearRegressor, DecisionTree, MovingAverage } = require('./ml-model');
const { TrainingDataManager, TASK_TYPES } = require('./training-data');

module.exports = {
  // Main scheduler
  IntelligentScheduler,
  createIntelligentScheduler,

  // Components
  ResourcePredictor,
  FeasibilityChecker,
  PriorityEngine,
  TrainingDataManager,

  // ML Models
  LinearRegressor,
  DecisionTree,
  MovingAverage,

  // Utilities
  SystemResourceMonitor,
  TokenBudgetTracker,

  // Constants
  HEURISTIC_ESTIMATES,
  DEFAULT_PRIORITY_WEIGHTS,
  PRIORITY_LEVEL_MULTIPLIERS,
  TASK_TYPES
};
