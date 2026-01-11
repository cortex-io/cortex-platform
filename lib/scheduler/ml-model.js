/**
 * Simple ML Models for Resource Prediction
 *
 * Implements lightweight machine learning without external dependencies:
 * - Linear Regression with online learning (Stochastic Gradient Descent)
 * - Feature normalization and standardization
 * - Model persistence (save/load from JSON)
 *
 * Uses pure JavaScript - no numpy, sklearn, or other heavy dependencies.
 */

const fs = require('fs');
const path = require('path');

/**
 * Linear Regression Model with Online Learning
 *
 * Algorithm: Stochastic Gradient Descent (SGD)
 * - Updates weights incrementally as new samples arrive
 * - Learning rate decay to stabilize convergence
 * - L2 regularization to prevent overfitting
 *
 * Mathematical formulation:
 *   y_pred = w0 + w1*x1 + w2*x2 + ... + wn*xn
 *   error = y_actual - y_pred
 *   w_i = w_i + learning_rate * error * x_i
 */
class LinearRegressor {
  constructor(options = {}) {
    this.learningRate = options.learningRate || 0.01;
    this.learningRateDecay = options.learningRateDecay || 0.999;
    this.regularization = options.regularization || 0.001; // L2 regularization
    this.weights = null;
    this.bias = 0;
    this.numSamples = 0;
    this.featureMeans = null;
    this.featureStds = null;
    this.initialized = false;
  }

  /**
   * Initialize model with first training sample
   */
  _initialize(features) {
    const numFeatures = features.length;
    this.weights = new Array(numFeatures).fill(0);
    this.featureMeans = new Array(numFeatures).fill(0);
    this.featureStds = new Array(numFeatures).fill(1);
    this.initialized = true;
  }

  /**
   * Normalize features using running statistics
   * Uses Welford's online algorithm for stable variance computation
   */
  _normalizeFeatures(features, update = false) {
    if (!this.initialized) {
      this._initialize(features);
    }

    const normalized = new Array(features.length);

    for (let i = 0; i < features.length; i++) {
      if (update) {
        // Update running mean and std using Welford's method
        this.numSamples++;
        const delta = features[i] - this.featureMeans[i];
        this.featureMeans[i] += delta / this.numSamples;
        const delta2 = features[i] - this.featureMeans[i];

        // Update running variance
        if (this.numSamples > 1) {
          const variance = (this.featureStds[i] * this.featureStds[i] * (this.numSamples - 1) + delta * delta2) / this.numSamples;
          this.featureStds[i] = Math.sqrt(variance);
        }
      }

      // Normalize using z-score normalization
      const std = this.featureStds[i] || 1;
      normalized[i] = std > 0 ? (features[i] - this.featureMeans[i]) / std : 0;
    }

    return normalized;
  }

  /**
   * Predict output for given features
   */
  predict(features) {
    if (!this.initialized || !this.weights) {
      // Return a conservative default if model not trained
      return null;
    }

    const normalizedFeatures = this._normalizeFeatures(features, false);

    // Linear combination: y = w0*x0 + w1*x1 + ... + wn*xn + bias
    let prediction = this.bias;
    for (let i = 0; i < normalizedFeatures.length; i++) {
      prediction += this.weights[i] * normalizedFeatures[i];
    }

    return Math.max(0, prediction); // Ensure non-negative predictions
  }

  /**
   * Batch training on multiple samples
   */
  fit(X, y, epochs = 10) {
    if (X.length === 0 || y.length === 0 || X.length !== y.length) {
      throw new Error('Invalid training data');
    }

    // Train for multiple epochs
    for (let epoch = 0; epoch < epochs; epoch++) {
      let totalLoss = 0;

      for (let i = 0; i < X.length; i++) {
        const loss = this.update(X[i], y[i]);
        totalLoss += loss;
      }

      // Decay learning rate
      this.learningRate *= this.learningRateDecay;
    }

    return this;
  }

  /**
   * Online learning - update model with single sample
   * Uses Stochastic Gradient Descent (SGD)
   */
  update(features, actualValue) {
    if (!this.initialized) {
      this._initialize(features);
    }

    // Normalize features and update statistics
    const normalizedFeatures = this._normalizeFeatures(features, true);

    // Compute prediction
    let prediction = this.bias;
    for (let i = 0; i < normalizedFeatures.length; i++) {
      prediction += this.weights[i] * normalizedFeatures[i];
    }

    // Compute error (gradient)
    const error = actualValue - prediction;

    // Update weights using SGD with L2 regularization
    // w_i = w_i + lr * (error * x_i - lambda * w_i)
    for (let i = 0; i < this.weights.length; i++) {
      const gradient = error * normalizedFeatures[i] - this.regularization * this.weights[i];
      this.weights[i] += this.learningRate * gradient;
    }

    // Update bias
    this.bias += this.learningRate * error;

    // Return squared error as loss
    return error * error;
  }

  /**
   * Save model to JSON file
   */
  save(filepath) {
    const modelData = {
      weights: this.weights,
      bias: this.bias,
      numSamples: this.numSamples,
      featureMeans: this.featureMeans,
      featureStds: this.featureStds,
      learningRate: this.learningRate,
      regularization: this.regularization,
      initialized: this.initialized,
      version: '1.0.0',
      savedAt: new Date().toISOString()
    };

    fs.writeFileSync(filepath, JSON.stringify(modelData, null, 2), 'utf8');
    return this;
  }

  /**
   * Load model from JSON file
   */
  load(filepath) {
    if (!fs.existsSync(filepath)) {
      return this; // Return uninitialized model if file doesn't exist
    }

    const modelData = JSON.parse(fs.readFileSync(filepath, 'utf8'));

    this.weights = modelData.weights;
    this.bias = modelData.bias;
    this.numSamples = modelData.numSamples;
    this.featureMeans = modelData.featureMeans;
    this.featureStds = modelData.featureStds;
    this.learningRate = modelData.learningRate;
    this.regularization = modelData.regularization;
    this.initialized = modelData.initialized;

    return this;
  }

  /**
   * Get model statistics
   */
  getStats() {
    return {
      initialized: this.initialized,
      numSamples: this.numSamples,
      numFeatures: this.weights ? this.weights.length : 0,
      learningRate: this.learningRate,
      weights: this.weights,
      bias: this.bias
    };
  }
}

/**
 * Simple Decision Tree for Classification
 * Used for task type classification and categorical predictions
 *
 * Implements ID3-like algorithm with information gain
 */
class DecisionTree {
  constructor(options = {}) {
    this.maxDepth = options.maxDepth || 5;
    this.minSamplesPerLeaf = options.minSamplesPerLeaf || 2;
    this.tree = null;
  }

  /**
   * Calculate entropy for a set of labels
   * H(S) = -Σ p_i * log2(p_i)
   */
  _entropy(labels) {
    const counts = {};
    for (const label of labels) {
      counts[label] = (counts[label] || 0) + 1;
    }

    let entropy = 0;
    const total = labels.length;

    for (const count of Object.values(counts)) {
      const p = count / total;
      if (p > 0) {
        entropy -= p * Math.log2(p);
      }
    }

    return entropy;
  }

  /**
   * Find best split point for a feature
   */
  _findBestSplit(X, y, featureIndex) {
    const values = X.map(row => row[featureIndex]);
    const uniqueValues = [...new Set(values)].sort((a, b) => a - b);

    let bestGain = -Infinity;
    let bestThreshold = null;

    // Try midpoints between unique values
    for (let i = 0; i < uniqueValues.length - 1; i++) {
      const threshold = (uniqueValues[i] + uniqueValues[i + 1]) / 2;

      const leftIndices = [];
      const rightIndices = [];

      for (let j = 0; j < X.length; j++) {
        if (X[j][featureIndex] <= threshold) {
          leftIndices.push(j);
        } else {
          rightIndices.push(j);
        }
      }

      if (leftIndices.length < this.minSamplesPerLeaf || rightIndices.length < this.minSamplesPerLeaf) {
        continue;
      }

      const leftLabels = leftIndices.map(i => y[i]);
      const rightLabels = rightIndices.map(i => y[i]);

      const parentEntropy = this._entropy(y);
      const leftEntropy = this._entropy(leftLabels);
      const rightEntropy = this._entropy(rightLabels);

      const leftWeight = leftLabels.length / y.length;
      const rightWeight = rightLabels.length / y.length;

      const informationGain = parentEntropy - (leftWeight * leftEntropy + rightWeight * rightEntropy);

      if (informationGain > bestGain) {
        bestGain = informationGain;
        bestThreshold = threshold;
      }
    }

    return { gain: bestGain, threshold: bestThreshold };
  }

  /**
   * Build decision tree recursively
   */
  _buildTree(X, y, depth = 0) {
    // Base cases
    if (depth >= this.maxDepth || y.length < this.minSamplesPerLeaf * 2) {
      return this._createLeaf(y);
    }

    // Check if all labels are the same
    if (new Set(y).size === 1) {
      return this._createLeaf(y);
    }

    // Find best split
    let bestFeature = null;
    let bestThreshold = null;
    let bestGain = -Infinity;

    for (let featureIndex = 0; featureIndex < X[0].length; featureIndex++) {
      const split = this._findBestSplit(X, y, featureIndex);

      if (split.gain > bestGain) {
        bestGain = split.gain;
        bestFeature = featureIndex;
        bestThreshold = split.threshold;
      }
    }

    // If no good split found, create leaf
    if (bestGain <= 0 || bestThreshold === null) {
      return this._createLeaf(y);
    }

    // Split data
    const leftX = [];
    const leftY = [];
    const rightX = [];
    const rightY = [];

    for (let i = 0; i < X.length; i++) {
      if (X[i][bestFeature] <= bestThreshold) {
        leftX.push(X[i]);
        leftY.push(y[i]);
      } else {
        rightX.push(X[i]);
        rightY.push(y[i]);
      }
    }

    return {
      feature: bestFeature,
      threshold: bestThreshold,
      left: this._buildTree(leftX, leftY, depth + 1),
      right: this._buildTree(rightX, rightY, depth + 1)
    };
  }

  /**
   * Create leaf node with most common class
   */
  _createLeaf(labels) {
    const counts = {};
    for (const label of labels) {
      counts[label] = (counts[label] || 0) + 1;
    }

    const mostCommon = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])[0][0];

    return {
      leaf: true,
      class: mostCommon,
      distribution: counts
    };
  }

  /**
   * Train the decision tree
   */
  fit(X, y) {
    this.tree = this._buildTree(X, y);
    return this;
  }

  /**
   * Predict class for a single sample
   */
  predict(features) {
    if (!this.tree) {
      return null;
    }

    let node = this.tree;

    while (!node.leaf) {
      if (features[node.feature] <= node.threshold) {
        node = node.left;
      } else {
        node = node.right;
      }
    }

    return node.class;
  }
}

/**
 * Moving Average Calculator
 * Used for baseline predictions and trend analysis
 */
class MovingAverage {
  constructor(windowSize = 10) {
    this.windowSize = windowSize;
    this.values = [];
  }

  /**
   * Add a new value and return current average
   */
  add(value) {
    this.values.push(value);

    if (this.values.length > this.windowSize) {
      this.values.shift();
    }

    return this.getAverage();
  }

  /**
   * Get current moving average
   */
  getAverage() {
    if (this.values.length === 0) {
      return null;
    }

    const sum = this.values.reduce((acc, val) => acc + val, 0);
    return sum / this.values.length;
  }

  /**
   * Get standard deviation
   */
  getStdDev() {
    const avg = this.getAverage();
    if (avg === null || this.values.length < 2) {
      return null;
    }

    const squaredDiffs = this.values.map(val => Math.pow(val - avg, 2));
    const variance = squaredDiffs.reduce((acc, val) => acc + val, 0) / this.values.length;
    return Math.sqrt(variance);
  }

  /**
   * Clear all values
   */
  clear() {
    this.values = [];
  }
}

module.exports = {
  LinearRegressor,
  DecisionTree,
  MovingAverage
};
