/**
 * Training Data Management
 *
 * Collects and manages execution outcomes for ML model training.
 * - Stores outcomes in JSONL format for incremental processing
 * - Feature engineering helpers
 * - Data validation and cleaning
 * - Efficient retrieval for model training
 */

const fs = require('fs');
const path = require('path');

/**
 * Task type encoding for one-hot vectors
 */
const TASK_TYPES = [
  'implementation',
  'security',
  'documentation',
  'review',
  'test',
  'fix',
  'scan',
  'pr-creation',
  'unknown'
];

/**
 * Training Data Manager
 */
class TrainingDataManager {
  constructor(options = {}) {
    this.dataDir = options.dataDir || path.join(process.cwd(), 'coordination', 'scheduler-data');
    this.outcomesFile = path.join(this.dataDir, 'task-outcomes.jsonl');
    this.maxRecords = options.maxRecords || 10000;
    this.featureCache = new Map();

    this._ensureDataDir();
  }

  /**
   * Ensure data directory exists
   */
  _ensureDataDir() {
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
    }
  }

  /**
   * Extract features from task metadata
   *
   * Features include:
   * - Task type (one-hot encoded)
   * - Description complexity metrics
   * - File count estimates
   * - Historical averages for similar tasks
   */
  extractFeatures(task, historicalData = null) {
    const features = {
      // Task type encoding (one-hot)
      taskType: this._normalizeTaskType(task.type || task.taskType || 'unknown'),
      taskTypeEncoded: this._encodeTaskType(task.type || task.taskType || 'unknown'),

      // Text-based features
      descriptionLength: (task.description || task.task || '').length,
      descriptionWordCount: (task.description || task.task || '').split(/\s+/).length,
      descriptionComplexity: this._calculateTextComplexity(task.description || task.task || ''),

      // Structural features
      fileCount: this._estimateFileCount(task),
      hasDeadline: !!(task.deadline || task.sla),
      priority: this._normalizePriority(task.priority),

      // Historical features
      historicalMean: null,
      historicalStd: null
    };

    // Add historical statistics if available
    if (historicalData && historicalData[features.taskType]) {
      features.historicalMean = historicalData[features.taskType].meanMemory || 0;
      features.historicalStd = historicalData[features.taskType].stdMemory || 0;
    }

    return features;
  }

  /**
   * Normalize task type to standard categories
   */
  _normalizeTaskType(type) {
    const typeStr = String(type).toLowerCase();

    if (typeStr.includes('implement') || typeStr.includes('feature')) return 'implementation';
    if (typeStr.includes('secur') || typeStr.includes('audit')) return 'security';
    if (typeStr.includes('doc')) return 'documentation';
    if (typeStr.includes('review')) return 'review';
    if (typeStr.includes('test')) return 'test';
    if (typeStr.includes('fix') || typeStr.includes('bug')) return 'fix';
    if (typeStr.includes('scan')) return 'scan';
    if (typeStr.includes('pr')) return 'pr-creation';

    return 'unknown';
  }

  /**
   * One-hot encode task type
   */
  _encodeTaskType(type) {
    const normalizedType = this._normalizeTaskType(type);
    const index = TASK_TYPES.indexOf(normalizedType);

    const encoded = new Array(TASK_TYPES.length).fill(0);
    if (index >= 0) {
      encoded[index] = 1;
    }

    return encoded;
  }

  /**
   * Calculate text complexity score
   * Based on: length, unique words, average word length, punctuation
   */
  _calculateTextComplexity(text) {
    if (!text || text.length === 0) return 0;

    const words = text.split(/\s+/).filter(w => w.length > 0);
    const uniqueWords = new Set(words.map(w => w.toLowerCase()));
    const avgWordLength = words.reduce((sum, w) => sum + w.length, 0) / (words.length || 1);
    const punctuationCount = (text.match(/[.,;:!?]/g) || []).length;

    // Complexity score is a weighted combination
    const complexity =
      (uniqueWords.size / (words.length || 1)) * 0.3 + // Vocabulary diversity
      (avgWordLength / 10) * 0.3 + // Word complexity
      (punctuationCount / text.length) * 100 * 0.2 + // Structure complexity
      Math.min(text.length / 1000, 1) * 0.2; // Length factor (capped at 1)

    return complexity;
  }

  /**
   * Estimate file count from task description
   */
  _estimateFileCount(task) {
    let fileCount = task.fileCount || task.files?.length || 0;

    if (fileCount === 0) {
      // Estimate from description
      const description = (task.description || task.task || '').toLowerCase();

      // Look for explicit file mentions
      const fileMatches = description.match(/(\d+)\s*files?/i);
      if (fileMatches) {
        fileCount = parseInt(fileMatches[1], 10);
      } else {
        // Heuristic based on task type
        const taskType = this._normalizeTaskType(task.type);
        const estimates = {
          implementation: 3,
          security: 5,
          documentation: 1,
          review: 2,
          test: 2,
          fix: 1,
          scan: 10,
          'pr-creation': 1,
          unknown: 2
        };
        fileCount = estimates[taskType] || 2;
      }
    }

    return fileCount;
  }

  /**
   * Normalize priority to numeric value
   */
  _normalizePriority(priority) {
    if (typeof priority === 'number') return priority;

    const priorityMap = {
      P0: 4,
      P1: 3,
      P2: 2,
      P3: 1,
      critical: 4,
      high: 3,
      medium: 2,
      low: 1
    };

    return priorityMap[priority] || 2;
  }

  /**
   * Convert features to flat numeric array for ML model
   */
  featuresToArray(features) {
    return [
      ...features.taskTypeEncoded, // One-hot encoded task type (9 values)
      features.descriptionLength / 1000, // Normalized to ~[0, 1]
      features.descriptionWordCount / 100, // Normalized
      features.descriptionComplexity, // Already [0, 1]
      features.fileCount / 10, // Normalized
      features.hasDeadline ? 1 : 0,
      features.priority / 4, // Normalized to [0, 1]
      features.historicalMean || 0,
      features.historicalStd || 0
    ];
  }

  /**
   * Record task outcome for training
   */
  recordOutcome(taskId, task, actualResources) {
    const features = this.extractFeatures(task);

    const record = {
      taskId,
      timestamp: new Date().toISOString(),
      features,
      actualResources: {
        memoryMB: actualResources.actualMemoryMB || actualResources.memoryMB || 0,
        cpuSeconds: actualResources.actualCpuSeconds || actualResources.cpuSeconds || 0,
        tokens: actualResources.actualTokens || actualResources.tokens || 0,
        durationMs: actualResources.actualDurationMs || actualResources.durationMs || 0
      },
      task: {
        type: task.type || task.taskType,
        description: (task.description || task.task || '').substring(0, 200) // Truncate for storage
      }
    };

    // Append to JSONL file
    const line = JSON.stringify(record) + '\n';
    fs.appendFileSync(this.outcomesFile, line, 'utf8');

    // Manage file size
    this._rotateIfNeeded();

    return record;
  }

  /**
   * Get training data
   */
  getTrainingData(limit = null) {
    if (!fs.existsSync(this.outcomesFile)) {
      return [];
    }

    const content = fs.readFileSync(this.outcomesFile, 'utf8');
    const lines = content.trim().split('\n').filter(line => line.length > 0);

    // Take most recent records if limit specified
    const records = limit ? lines.slice(-limit) : lines;

    return records.map(line => {
      try {
        return JSON.parse(line);
      } catch (error) {
        console.error('Error parsing training record:', error);
        return null;
      }
    }).filter(record => record !== null);
  }

  /**
   * Get training data formatted for ML model
   */
  getTrainingDataForModel(resourceType = 'memoryMB', limit = null) {
    const records = this.getTrainingData(limit);

    const X = [];
    const y = [];

    for (const record of records) {
      const features = this.featuresToArray(record.features);
      const target = record.actualResources[resourceType] || 0;

      // Filter out invalid data
      if (target > 0 && features.every(f => isFinite(f))) {
        X.push(features);
        y.push(target);
      }
    }

    return { X, y };
  }

  /**
   * Get historical statistics by task type
   */
  getHistoricalStatsByType() {
    const records = this.getTrainingData();
    const statsByType = {};

    for (const record of records) {
      const taskType = record.features.taskType;

      if (!statsByType[taskType]) {
        statsByType[taskType] = {
          samples: [],
          memory: [],
          cpu: [],
          tokens: [],
          duration: []
        };
      }

      statsByType[taskType].samples.push(record);
      statsByType[taskType].memory.push(record.actualResources.memoryMB);
      statsByType[taskType].cpu.push(record.actualResources.cpuSeconds);
      statsByType[taskType].tokens.push(record.actualResources.tokens);
      statsByType[taskType].duration.push(record.actualResources.durationMs);
    }

    // Calculate statistics
    const result = {};
    for (const [taskType, data] of Object.entries(statsByType)) {
      result[taskType] = {
        count: data.samples.length,
        meanMemory: this._mean(data.memory),
        stdMemory: this._stdDev(data.memory),
        meanCpu: this._mean(data.cpu),
        stdCpu: this._stdDev(data.cpu),
        meanTokens: this._mean(data.tokens),
        stdTokens: this._stdDev(data.tokens),
        meanDuration: this._mean(data.duration),
        stdDuration: this._stdDev(data.duration)
      };
    }

    return result;
  }

  /**
   * Calculate mean
   */
  _mean(arr) {
    if (arr.length === 0) return 0;
    return arr.reduce((sum, val) => sum + val, 0) / arr.length;
  }

  /**
   * Calculate standard deviation
   */
  _stdDev(arr) {
    if (arr.length < 2) return 0;
    const mean = this._mean(arr);
    const variance = arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / arr.length;
    return Math.sqrt(variance);
  }

  /**
   * Rotate log file if it gets too large
   */
  _rotateIfNeeded() {
    if (!fs.existsSync(this.outcomesFile)) return;

    const stats = fs.statSync(this.outcomesFile);
    const lines = fs.readFileSync(this.outcomesFile, 'utf8').split('\n').length;

    if (lines > this.maxRecords) {
      // Keep only the most recent records
      const content = fs.readFileSync(this.outcomesFile, 'utf8');
      const allLines = content.trim().split('\n');
      const recentLines = allLines.slice(-this.maxRecords);

      // Backup old file
      const backupFile = this.outcomesFile.replace('.jsonl', `.backup-${Date.now()}.jsonl`);
      fs.renameSync(this.outcomesFile, backupFile);

      // Write recent lines
      fs.writeFileSync(this.outcomesFile, recentLines.join('\n') + '\n', 'utf8');
    }
  }

  /**
   * Export data for external analysis
   */
  exportForTraining(outputPath = null) {
    const records = this.getTrainingData();
    const outputFile = outputPath || path.join(this.dataDir, `export-${Date.now()}.json`);

    const exportData = {
      exportedAt: new Date().toISOString(),
      recordCount: records.length,
      statistics: this.getHistoricalStatsByType(),
      records
    };

    fs.writeFileSync(outputFile, JSON.stringify(exportData, null, 2), 'utf8');
    return outputFile;
  }

  /**
   * Clear all training data
   */
  clear() {
    if (fs.existsSync(this.outcomesFile)) {
      fs.unlinkSync(this.outcomesFile);
    }
    this.featureCache.clear();
  }

  /**
   * Get summary statistics
   */
  getSummary() {
    const records = this.getTrainingData();
    const byType = this.getHistoricalStatsByType();

    return {
      totalRecords: records.length,
      taskTypes: Object.keys(byType).length,
      byType,
      dataFile: this.outcomesFile,
      dataExists: fs.existsSync(this.outcomesFile)
    };
  }
}

module.exports = {
  TrainingDataManager,
  TASK_TYPES
};
