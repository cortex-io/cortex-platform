"""Anomaly detection models and algorithms"""
import logging
import os
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import EllipticEnvelope
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import joblib
from app.config import settings

logger = logging.getLogger(__name__)


class BaselineCalculator:
    """Calculate performance baselines using statistical methods"""

    def __init__(self):
        self.baselines = {}

    def calculate_baseline(self, df: pd.DataFrame, metric_name: str) -> Dict:
        """Calculate statistical baseline for a metric"""
        if df.empty:
            return {}

        values = df['value'].values

        baseline = {
            'metric_name': metric_name,
            'mean': float(np.mean(values)),
            'median': float(np.median(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'p50': float(np.percentile(values, 50)),
            'p90': float(np.percentile(values, 90)),
            'p95': float(np.percentile(values, 95)),
            'p99': float(np.percentile(values, 99)),
            'lower_bound': float(np.mean(values) - 3 * np.std(values)),
            'upper_bound': float(np.mean(values) + 3 * np.std(values)),
            'data_points': len(values),
            'calculated_at': pd.Timestamp.now().isoformat()
        }

        self.baselines[metric_name] = baseline
        logger.info(f"Calculated baseline for {metric_name}: mean={baseline['mean']:.2f}, std={baseline['std']:.2f}")

        return baseline

    def get_baseline(self, metric_name: str) -> Optional[Dict]:
        """Get baseline for a metric"""
        return self.baselines.get(metric_name)


class ZScoreDetector:
    """Statistical Z-score based anomaly detection"""

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold

    def detect(self, df: pd.DataFrame, baseline: Dict) -> pd.DataFrame:
        """Detect anomalies using Z-score"""
        if df.empty:
            return df

        df = df.copy()
        mean = baseline.get('mean', df['value'].mean())
        std = baseline.get('std', df['value'].std())

        if std == 0:
            df['zscore'] = 0
            df['is_anomaly'] = False
        else:
            df['zscore'] = (df['value'] - mean) / std
            df['is_anomaly'] = np.abs(df['zscore']) > self.threshold

        df['anomaly_score'] = np.abs(df['zscore']) / self.threshold
        df['detection_method'] = 'zscore'

        anomaly_count = df['is_anomaly'].sum()
        logger.info(f"Z-score detector found {anomaly_count} anomalies (threshold={self.threshold})")

        return df


class IsolationForestDetector:
    """Isolation Forest based anomaly detection"""

    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()

    def fit(self, df: pd.DataFrame):
        """Fit the model on training data"""
        if df.empty:
            return

        features = self._extract_features(df)
        if features.empty:
            return

        X = self.scaler.fit_transform(features)
        self.model.fit(X)
        logger.info(f"Isolation Forest fitted on {len(features)} samples")

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies using Isolation Forest"""
        if df.empty:
            return df

        df = df.copy()
        features = self._extract_features(df)

        if features.empty:
            df['is_anomaly'] = False
            df['anomaly_score'] = 0.0
            return df

        X = self.scaler.transform(features)
        predictions = self.model.predict(X)
        scores = self.model.score_samples(X)

        df['is_anomaly'] = predictions == -1
        df['anomaly_score'] = -scores  # Lower scores = more anomalous
        df['detection_method'] = 'isolation_forest'

        anomaly_count = df['is_anomaly'].sum()
        logger.info(f"Isolation Forest found {anomaly_count} anomalies")

        return df

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features for the model"""
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        features = pd.DataFrame()
        features['value'] = df['value']

        # Time-based features
        features['hour'] = df.index.hour
        features['day_of_week'] = df.index.dayofweek

        # Lag features
        for lag in [1, 6, 12]:
            features[f'lag_{lag}'] = df['value'].shift(lag)

        # Rolling statistics
        for window in [6, 12, 24]:
            features[f'rolling_mean_{window}'] = df['value'].rolling(window=window).mean()
            features[f'rolling_std_{window}'] = df['value'].rolling(window=window).std()

        features = features.dropna()
        return features


class AutoencoderDetector:
    """Autoencoder neural network for anomaly detection"""

    def __init__(self, encoding_dim: int = 8, threshold_percentile: float = 95):
        self.encoding_dim = encoding_dim
        self.threshold_percentile = threshold_percentile
        self.model = None
        self.scaler = StandardScaler()
        self.threshold = None

    def build_model(self, input_dim: int):
        """Build autoencoder model"""
        input_layer = layers.Input(shape=(input_dim,))

        # Encoder
        encoded = layers.Dense(32, activation='relu')(input_layer)
        encoded = layers.Dense(16, activation='relu')(encoded)
        encoded = layers.Dense(self.encoding_dim, activation='relu')(encoded)

        # Decoder
        decoded = layers.Dense(16, activation='relu')(encoded)
        decoded = layers.Dense(32, activation='relu')(decoded)
        decoded = layers.Dense(input_dim, activation='linear')(decoded)

        self.model = keras.Model(input_layer, decoded)
        self.model.compile(optimizer='adam', loss='mse')

    def fit(self, df: pd.DataFrame, epochs: int = 50):
        """Train the autoencoder"""
        if df.empty:
            return

        features = self._extract_features(df)
        if features.empty:
            return

        X = self.scaler.fit_transform(features)

        if self.model is None:
            self.build_model(X.shape[1])

        self.model.fit(
            X, X,
            epochs=epochs,
            batch_size=32,
            validation_split=0.1,
            verbose=0
        )

        # Calculate threshold
        reconstructions = self.model.predict(X, verbose=0)
        mse = np.mean(np.square(X - reconstructions), axis=1)
        self.threshold = np.percentile(mse, self.threshold_percentile)

        logger.info(f"Autoencoder trained, threshold={self.threshold:.4f}")

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies using reconstruction error"""
        if df.empty or self.model is None:
            df = df.copy()
            df['is_anomaly'] = False
            df['anomaly_score'] = 0.0
            return df

        df = df.copy()
        features = self._extract_features(df)

        if features.empty:
            df['is_anomaly'] = False
            df['anomaly_score'] = 0.0
            return df

        X = self.scaler.transform(features)
        reconstructions = self.model.predict(X, verbose=0)
        mse = np.mean(np.square(X - reconstructions), axis=1)

        df['is_anomaly'] = mse > self.threshold
        df['anomaly_score'] = mse / self.threshold if self.threshold > 0 else mse
        df['detection_method'] = 'autoencoder'

        anomaly_count = df['is_anomaly'].sum()
        logger.info(f"Autoencoder found {anomaly_count} anomalies")

        return df

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features for the model"""
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        features = pd.DataFrame()
        features['value'] = df['value']

        # Time-based features
        features['hour'] = df.index.hour
        features['day_of_week'] = df.index.dayofweek

        # Lag features
        for lag in [1, 6, 12]:
            features[f'lag_{lag}'] = df['value'].shift(lag)

        # Rolling statistics
        for window in [6, 12]:
            features[f'rolling_mean_{window}'] = df['value'].rolling(window=window).mean()
            features[f'rolling_std_{window}'] = df['value'].rolling(window=window).std()

        features = features.dropna()
        return features


class DBSCANDetector:
    """DBSCAN clustering for outlier detection"""

    def __init__(self, eps: float = 0.5, min_samples: int = 5):
        self.eps = eps
        self.min_samples = min_samples
        self.scaler = StandardScaler()

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies using DBSCAN"""
        if df.empty:
            return df

        df = df.copy()
        features = self._extract_features(df)

        if features.empty:
            df['is_anomaly'] = False
            df['anomaly_score'] = 0.0
            return df

        X = self.scaler.fit_transform(features)

        dbscan = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = dbscan.fit_predict(X)

        # Points labeled as -1 are outliers
        df['is_anomaly'] = labels == -1
        df['cluster_label'] = labels
        df['anomaly_score'] = (labels == -1).astype(float)
        df['detection_method'] = 'dbscan'

        anomaly_count = df['is_anomaly'].sum()
        logger.info(f"DBSCAN found {anomaly_count} anomalies")

        return df

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features for the model"""
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        features = pd.DataFrame()
        features['value'] = df['value']

        # Time-based features
        features['hour'] = df.index.hour
        features['day_of_week'] = df.index.dayofweek

        features = features.dropna()
        return features


class EnsembleDetector:
    """Ensemble of multiple anomaly detection methods"""

    def __init__(self):
        self.baseline_calc = BaselineCalculator()
        self.zscore_detector = ZScoreDetector(threshold=settings.zscore_threshold)
        self.isolation_forest = IsolationForestDetector(contamination=settings.isolation_forest_contamination)
        self.autoencoder = AutoencoderDetector(threshold_percentile=settings.autoencoder_threshold)
        self.dbscan = DBSCANDetector(eps=settings.dbscan_eps, min_samples=settings.dbscan_min_samples)

    def train(self, df: pd.DataFrame, metric_name: str):
        """Train all detectors"""
        logger.info(f"Training ensemble detectors for {metric_name}")

        # Calculate baseline
        self.baseline_calc.calculate_baseline(df, metric_name)

        # Train models
        self.isolation_forest.fit(df)
        self.autoencoder.fit(df)

    def detect(self, df: pd.DataFrame, metric_name: str, voting_threshold: int = 2) -> pd.DataFrame:
        """Detect anomalies using ensemble voting"""
        if df.empty:
            return df

        baseline = self.baseline_calc.get_baseline(metric_name)

        # Run all detectors
        results = []

        if baseline:
            zscore_result = self.zscore_detector.detect(df, baseline)
            results.append(zscore_result['is_anomaly'].values)

        iso_result = self.isolation_forest.detect(df)
        results.append(iso_result['is_anomaly'].values)

        ae_result = self.autoencoder.detect(df)
        results.append(ae_result['is_anomaly'].values)

        dbscan_result = self.dbscan.detect(df)
        results.append(dbscan_result['is_anomaly'].values)

        # Ensemble voting
        df = df.copy()
        votes = np.sum(results, axis=0)
        df['is_anomaly'] = votes >= voting_threshold
        df['anomaly_votes'] = votes
        df['anomaly_score'] = votes / len(results)
        df['detection_method'] = 'ensemble'

        anomaly_count = df['is_anomaly'].sum()
        logger.info(f"Ensemble detector found {anomaly_count} anomalies (threshold={voting_threshold})")

        return df

    def save_models(self, path: str, metric_name: str):
        """Save trained models"""
        os.makedirs(path, exist_ok=True)

        joblib.dump(self.baseline_calc.baselines, f"{path}/{metric_name}_baseline.pkl")
        joblib.dump(self.isolation_forest, f"{path}/{metric_name}_iso_forest.pkl")

        if self.autoencoder.model:
            self.autoencoder.model.save(f"{path}/{metric_name}_autoencoder.h5")
            joblib.dump(self.autoencoder.scaler, f"{path}/{metric_name}_ae_scaler.pkl")
            joblib.dump(self.autoencoder.threshold, f"{path}/{metric_name}_ae_threshold.pkl")

        logger.info(f"Saved models for {metric_name}")

    def load_models(self, path: str, metric_name: str):
        """Load trained models"""
        try:
            baseline_path = f"{path}/{metric_name}_baseline.pkl"
            if os.path.exists(baseline_path):
                self.baseline_calc.baselines = joblib.load(baseline_path)

            iso_path = f"{path}/{metric_name}_iso_forest.pkl"
            if os.path.exists(iso_path):
                self.isolation_forest = joblib.load(iso_path)

            ae_path = f"{path}/{metric_name}_autoencoder.h5"
            if os.path.exists(ae_path):
                self.autoencoder.model = keras.models.load_model(ae_path)
                self.autoencoder.scaler = joblib.load(f"{path}/{metric_name}_ae_scaler.pkl")
                self.autoencoder.threshold = joblib.load(f"{path}/{metric_name}_ae_threshold.pkl")

            logger.info(f"Loaded models for {metric_name}")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
