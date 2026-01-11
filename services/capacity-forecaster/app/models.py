"""ML models for capacity forecasting"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
import joblib
from app.config import settings

logger = logging.getLogger(__name__)


class CapacityForecaster:
    """Main forecasting engine using ensemble of models"""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.model_path = settings.model_storage_path
        os.makedirs(self.model_path, exist_ok=True)

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer features from raw time series data"""
        if df.empty:
            return df

        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        # Time-based features
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek
        df['day_of_month'] = df.index.day
        df['month'] = df.index.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_business_hours'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)

        # Lag features
        for lag in [1, 6, 12, 24]:  # 5min, 30min, 1hr, 2hr lags
            df[f'lag_{lag}'] = df['value'].shift(lag)

        # Rolling statistics
        for window in [12, 24, 288]:  # 1hr, 2hr, 24hr windows
            df[f'rolling_mean_{window}'] = df['value'].rolling(window=window).mean()
            df[f'rolling_std_{window}'] = df['value'].rolling(window=window).std()
            df[f'rolling_min_{window}'] = df['value'].rolling(window=window).min()
            df[f'rolling_max_{window}'] = df['value'].rolling(window=window).max()

        # Drop NaN rows created by lag/rolling
        df = df.dropna()

        return df

    def train_prophet_model(self, df: pd.DataFrame, metric_name: str) -> Prophet:
        """Train Facebook Prophet model"""
        logger.info(f"Training Prophet model for {metric_name}")

        # Prepare data for Prophet
        prophet_df = df.reset_index()[['timestamp', 'value']]
        prophet_df.columns = ['ds', 'y']

        # Initialize and train model
        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
        )

        model.fit(prophet_df)
        return model

    def train_arima_model(self, df: pd.DataFrame, metric_name: str) -> ARIMA:
        """Train ARIMA model"""
        logger.info(f"Training ARIMA model for {metric_name}")

        # Use auto ARIMA for parameter selection (simplified here)
        # In production, use pmdarima.auto_arima
        model = ARIMA(df['value'], order=(5, 1, 2))
        fitted_model = model.fit()

        return fitted_model

    def train_ml_model(self, df: pd.DataFrame, metric_name: str) -> Tuple[RandomForestRegressor, StandardScaler]:
        """Train Random Forest model"""
        logger.info(f"Training ML model for {metric_name}")

        # Prepare features
        feature_cols = [col for col in df.columns if col not in ['value']]
        X = df[feature_cols]
        y = df['value']

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train model
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )

        model.fit(X_scaled, y)

        return model, scaler

    def forecast(
        self,
        df: pd.DataFrame,
        metric_name: str,
        periods: int = 2016,  # 7 days at 5-min intervals
        use_ensemble: bool = True
    ) -> pd.DataFrame:
        """Generate forecast using ensemble of models"""

        if df.empty:
            logger.warning(f"Empty dataframe for {metric_name}")
            return pd.DataFrame()

        forecasts = {}

        try:
            # Prophet forecast
            prophet_model = self.train_prophet_model(df, metric_name)
            future = prophet_model.make_future_dataframe(periods=periods, freq='5min')
            prophet_forecast = prophet_model.predict(future)
            forecasts['prophet'] = prophet_forecast[['ds', 'yhat']].tail(periods)
            forecasts['prophet'].columns = ['timestamp', 'value']

        except Exception as e:
            logger.error(f"Prophet forecast failed: {e}")

        try:
            # ARIMA forecast
            arima_model = self.train_arima_model(df, metric_name)
            arima_forecast = arima_model.forecast(steps=periods)
            last_timestamp = df.index[-1]
            forecast_timestamps = pd.date_range(
                start=last_timestamp + timedelta(minutes=5),
                periods=periods,
                freq='5min'
            )
            forecasts['arima'] = pd.DataFrame({
                'timestamp': forecast_timestamps,
                'value': arima_forecast
            })

        except Exception as e:
            logger.error(f"ARIMA forecast failed: {e}")

        # Ensemble: average predictions
        if use_ensemble and len(forecasts) > 1:
            ensemble_df = pd.DataFrame()
            ensemble_df['timestamp'] = forecasts[list(forecasts.keys())[0]]['timestamp']

            values = []
            for model_name, forecast_df in forecasts.items():
                values.append(forecast_df['value'].values)

            ensemble_df['value'] = np.mean(values, axis=0)
            ensemble_df['lower_bound'] = np.min(values, axis=0)
            ensemble_df['upper_bound'] = np.max(values, axis=0)
            ensemble_df['metric_name'] = metric_name

            return ensemble_df
        elif forecasts:
            # Return first available forecast
            key = list(forecasts.keys())[0]
            result = forecasts[key].copy()
            result['metric_name'] = metric_name
            return result
        else:
            return pd.DataFrame()

    def detect_capacity_issues(
        self,
        forecast_df: pd.DataFrame,
        threshold_warning: float = 0.75,
        threshold_critical: float = 0.90
    ) -> List[Dict]:
        """Detect when capacity thresholds will be exceeded"""

        if forecast_df.empty:
            return []

        alerts = []

        # Check for threshold violations
        warnings = forecast_df[forecast_df['value'] >= threshold_warning * 100]
        critical = forecast_df[forecast_df['value'] >= threshold_critical * 100]

        if not critical.empty:
            first_critical = critical.iloc[0]
            alerts.append({
                'severity': 'critical',
                'metric': forecast_df['metric_name'].iloc[0],
                'predicted_time': str(first_critical['timestamp']),
                'predicted_value': float(first_critical['value']),
                'threshold': threshold_critical * 100,
                'message': f"Critical threshold ({threshold_critical*100}%) predicted to be exceeded"
            })

        elif not warnings.empty:
            first_warning = warnings.iloc[0]
            alerts.append({
                'severity': 'warning',
                'metric': forecast_df['metric_name'].iloc[0],
                'predicted_time': str(first_warning['timestamp']),
                'predicted_value': float(first_warning['value']),
                'threshold': threshold_warning * 100,
                'message': f"Warning threshold ({threshold_warning*100}%) predicted to be exceeded"
            })

        return alerts

    def save_model(self, model, model_name: str):
        """Save trained model to disk"""
        path = os.path.join(self.model_path, f"{model_name}.pkl")
        joblib.dump(model, path)
        logger.info(f"Saved model to {path}")

    def load_model(self, model_name: str):
        """Load trained model from disk"""
        path = os.path.join(self.model_path, f"{model_name}.pkl")
        if os.path.exists(path):
            model = joblib.load(path)
            logger.info(f"Loaded model from {path}")
            return model
        return None
