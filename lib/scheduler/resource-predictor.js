/**
 * ML-Based Resource Predictor
 *
 * Predicts resource requirements for tasks using machine learning:
 * - CPU seconds
 * - Peak memory (MB)
 * - Token usage
 * - Duration
 *
 * Features:
 * - Online learning from actual outcomes
 * - Graceful fallback to heuristics when ML data is insufficient
 * - Conservative estimates to prevent OOM
 * - Per-resource type models
 */

const fs = require('fs');
const path = require('path');
const { LinearRegressor, MovingAverage } = require('./ml-model');
const { TrainingDataManager } = require('./training-data');

/**
 * Heuristic-based fallback predictions
 * Used when insufficient training data for ML
 */
const HEURISTIC_ESTIMATES = {
  implementation: {
    memoryMB: 800,
    cpuSeconds: 180,
    tokens: 50000,
    durationMs: 300000
  },
  security: {
    memoryMB: 600,
    cpuSeconds: 120,
    tokens: 25000,
    durationMs: 180000
  },
  documentation: {
    memoryMB: 400,
    cpuSeconds: 60,
    tokens: 15000,
    durationMs: 120000
  },
  review: {
    memoryMB: 500,
    cpuSeconds: 90,
    tokens: 30000,
    durationMs: 150000
  },
  test: {
    memoryMB: 600,
    cpuSeconds: 120,
    tokens: 20000,
    durationMs: 180000
  },
  fix: {
    memoryMB: 700,
    cpuSeconds: 150,
    tokens: 40000,
    durationMs: 240000
  },
  scan: {
    memoryMB: 500,
    cpuSeconds: 100,
    tokens: 20000,
    durationMs: 160000
  },
  'pr-creation': {
    memoryMB: 400,
    cpuSeconds: 60,
    tokens: 15000,
    durationMs: 100000
  },
  unknown: {
    memoryMB: 600,
    cpuSeconds: 120,
    tokens: 30000,
    durationMs: 180000
  }
};

/**
 * Resource Predictor with ML
 */
class ResourcePredictor {
  constructor(options = {}) {
    this.modelDir = options.modelDir || path.join(process.cwd(), 'coordination', 'scheduler-data', 'models');
    this.minSamplesForML = options.minSamplesForML || 50;
    this.fallbackToHeuristics = options.fallbackToHeuristics !== false;
    this.modelUpdateInterval = options.modelUpdateInterval || 100;
    this.conservativeMultiplier = options.conservativeMultiplier || 1.2; // 20% safety margin

    // Initialize models for each resource type
    this.models = {
      memoryMB: new LinearRegressor({ learningRate: 0.01 }),
      cpuSeconds: new LinearRegressor({ learningRate: 0.01 }),
      tokens: new LinearRegressor({ learningRate: 0.01 }),
      durationMs: new LinearRegressor({ learningRate: 0.01 })
    };

    // Moving averages for baseline
    this.movingAverages = {
      memoryMB: new MovingAverage(20),
      cpuSeconds: new MovingAverage(20),
      tokens: new MovingAverage(20),
      durationMs: new MovingAverage(20)
    };

    // Training data manager
    this.trainingData = new TrainingDataManager(options);

    // Load existing models
    this._ensureModelDir();
    this._loadModels();

    // Statistics
    this.stats = {
      totalPredictions: 0,
      mlPredictions: 0,
      heuristicPredictions: 0,
      updatesSinceLastSave: 0
    };
  }

  /**
   * Ensure model directory exists
   */
  _ensureModelDir() {
    if (!fs.existsSync(this.modelDir)) {
      fs.mkdirSync(this.modelDir, { recursive: true });
    }
  }

  /**
   * Load saved models from disk
   */
  _loadModels() {
    for (const resourceType of Object.keys(this.models)) {
      const modelPath = path.join(this.modelDir, `${resourceType}-model.json`);
      if (fs.existsSync(modelPath)) {
        try {
          this.models[resourceType].load(modelPath);
        } catch (error) {
          console.error(`Error loading model for ${resourceType}:`, error.message);
        }
      }
    }
  }

  /**
   * Save models to disk
   */
  _saveModels() {
    for (const [resourceType, model] of Object.entries(this.models)) {
      const modelPath = path.join(this.modelDir, `${resourceType}-model.json`);
      try {
        model.save(modelPath);
      } catch (error) {
        console.error(`Error saving model for ${resourceType}:`, error.message);
      }
    }
    this.stats.updatesSinceLastSave = 0;
  }

  /**
   * Predict resources required for a task
   */
  predict(task) {
    this.stats.totalPredictions++;

    // Extract features
    const historicalStats = this.trainingData.getHistoricalStatsByType();
    const features = this.trainingData.extractFeatures(task, historicalStats);
    const featureArray = this.trainingData.featuresToArray(features);

    // Check if we have enough data for ML
    const trainingSummary = this.trainingData.getSummary();
    const useML = trainingSummary.totalRecords >= this.minSamplesForML;

    const predictions = {};
    const confidence = {};

    for (const resourceType of Object.keys(this.models)) {
      if (useML && this.models[resourceType].initialized) {
        // Use ML model
        const mlPrediction = this.models[resourceType].predict(featureArray);

        if (mlPrediction !== null && mlPrediction > 0) {
          // Apply conservative multiplier for safety
          predictions[resourceType] = mlPrediction * this.conservativeMultiplier;
          confidence[resourceType] = 'ml';
          this.stats.mlPredictions++;
        } else {
          // Fall back to heuristic
          predictions[resourceType] = this._getHeuristicPrediction(features.taskType, resourceType);
          confidence[resourceType] = 'heuristic-fallback';
          this.stats.heuristicPredictions++;
        }
      } else {
        // Use heuristic baseline
        predictions[resourceType] = this._getHeuristicPrediction(features.taskType, resourceType);
        confidence[resourceType] = 'heuristic';
        this.stats.heuristicPredictions++;
      }

      // Ensure predictions are reasonable
      predictions[resourceType] = this._clampPrediction(resourceType, predictions[resourceType]);
    }

    return {
      estimatedMemoryMB: Math.ceil(predictions.memoryMB),
      estimatedCpuSeconds: Math.ceil(predictions.cpuSeconds),
      estimatedTokens: Math.ceil(predictions.tokens),
      estimatedDurationMs: Math.ceil(predictions.durationMs),
      confidence,
      method: useML ? 'ml' : 'heuristic',
      features,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get heuristic prediction for a resource type
   */
  _getHeuristicPrediction(taskType, resourceType) {
    const baseEstimate = HEURISTIC_ESTIMATES[taskType]?.[resourceType] || HEURISTIC_ESTIMATES.unknown[resourceType];

    // Check if we have historical data for this task type
    const historicalStats = this.trainingData.getHistoricalStatsByType();
    if (historicalStats[taskType] && historicalStats[taskType].count > 5) {
      // Use historical mean if available
      const meanField = `mean${resourceType.charAt(0).toUpperCase() + resourceType.slice(1)}`;
      const historicalMean = historicalStats[taskType][meanField];

      if (historicalMean > 0) {
        // Blend heuristic with historical data
        return (baseEstimate * 0.3 + historicalMean * 0.7) * this.conservativeMultiplier;
      }
    }

    return baseEstimate * this.conservativeMultiplier;
  }

  /**
   * Clamp predictions to reasonable ranges
   */
  _clampPrediction(resourceType, value) {
    const ranges = {
      memoryMB: { min: 100, max: 8192 },
      cpuSeconds: { min: 10, max: 3600 },
      tokens: { min: 1000, max: 200000 },
      durationMs: { min: 30000, max: 7200000 }
    };

    const range = ranges[resourceType];
    return Math.max(range.min, Math.min(range.max, value));
  }

  /**
   * Report actual outcome for online learning
   */
  reportOutcome(taskId, task, actualResources) {
    // Record in training data
    this.trainingData.recordOutcome(taskId, task, actualResources);

    // Extract features
    const historicalStats = this.trainingData.getHistoricalStatsByType();
    const features = this.trainingData.extractFeatures(task, historicalStats);
    const featureArray = this.trainingData.featuresToArray(features);

    // Update models with online learning
    for (const [resourceType, model] of Object.entries(this.models)) {
      const actualValue = actualResources[resourceType] || actualResources[`actual${resourceType.charAt(0).toUpperCase() + resourceType.slice(1)}`] || 0;

      if (actualValue > 0) {
        model.update(featureArray, actualValue);

        // Update moving average
        this.movingAverages[resourceType].add(actualValue);
      }
    }

    this.stats.updatesSinceLastSave++;

    // Periodically save models
    if (this.stats.updatesSinceLastSave >= this.modelUpdateInterval) {
      this._saveModels();
    }

    return {
      taskId,
      recorded: true,
      modelUpdated: true
    };
  }

  /**
   * Batch train models on historical data
   */
  batchTrain(epochs = 10) {
    const resourceTypes = Object.keys(this.models);
    const results = {};

    for (const resourceType of resourceTypes) {
      const { X, y } = this.trainingData.getTrainingDataForModel(resourceType);

      if (X.length < this.minSamplesForML) {
        results[resourceType] = {
          trained: false,
          reason: 'insufficient-data',
          samples: X.length,
          required: this.minSamplesForML
        };
        continue;
      }

      try {
        this.models[resourceType].fit(X, y, epochs);
        results[resourceType] = {
          trained: true,
          samples: X.length,
          epochs,
          modelStats: this.models[resourceType].getStats()
        };
      } catch (error) {
        results[resourceType] = {
          trained: false,
          reason: 'training-error',
          error: error.message
        };
      }
    }

    // Save models after batch training
    this._saveModels();

    return results;
  }

  /**
   * Get predictor statistics
   */
  getStats() {
    const trainingSummary = this.trainingData.getSummary();

    return {
      predictions: this.stats,
      training: trainingSummary,
      models: Object.fromEntries(
        Object.entries(this.models).map(([type, model]) => [type, model.getStats()])
      ),
      configuration: {
        minSamplesForML: this.minSamplesForML,
        fallbackToHeuristics: this.fallbackToHeuristics,
        conservativeMultiplier: this.conservativeMultiplier,
        modelUpdateInterval: this.modelUpdateInterval
      }
    };
  }

  /**
   * Get prediction accuracy metrics
   */
  getAccuracyMetrics() {
    const records = this.trainingData.getTrainingData(1000); // Last 1000 records

    if (records.length === 0) {
      return null;
    }

    const metrics = {
      memoryMB: { errors: [], meanError: 0, mape: 0 },
      cpuSeconds: { errors: [], meanError: 0, mape: 0 },
      tokens: { errors: [], meanError: 0, mape: 0 },
      durationMs: { errors: [], meanError: 0, mape: 0 }
    };

    for (const record of records) {
      const featureArray = this.trainingData.featuresToArray(record.features);

      for (const resourceType of Object.keys(metrics)) {
        const prediction = this.models[resourceType].predict(featureArray);
        const actual = record.actualResources[resourceType];

        if (prediction !== null && actual > 0) {
          const error = Math.abs(prediction - actual);
          const percentError = (error / actual) * 100;

          metrics[resourceType].errors.push(error);
          metrics[resourceType].percentErrors = metrics[resourceType].percentErrors || [];
          metrics[resourceType].percentErrors.push(percentError);
        }
      }
    }

    // Calculate statistics
    for (const [resourceType, data] of Object.entries(metrics)) {
      if (data.errors.length > 0) {
        data.meanError = data.errors.reduce((sum, e) => sum + e, 0) / data.errors.length;
        data.mape = data.percentErrors.reduce((sum, e) => sum + e, 0) / data.percentErrors.length;
        data.samples = data.errors.length;
      }
    }

    return metrics;
  }

  /**
   * Reset all models
   */
  reset() {
    for (const resourceType of Object.keys(this.models)) {
      this.models[resourceType] = new LinearRegressor({ learningRate: 0.01 });
      this.movingAverages[resourceType].clear();
    }

    this.stats = {
      totalPredictions: 0,
      mlPredictions: 0,
      heuristicPredictions: 0,
      updatesSinceLastSave: 0
    };
  }
}

module.exports = {
  ResourcePredictor,
  HEURISTIC_ESTIMATES
};
