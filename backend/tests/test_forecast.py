import pytest
from unittest.mock import patch, MagicMock
from app.sim.forecast import QueueForecaster

def test_queue_forecaster_missing_model():
    with patch("os.path.exists", return_value=False):
        forecaster = QueueForecaster()
        assert forecaster.model is None
        assert forecaster.predict({"queue_length_m": 10.0}) == -1.0

def test_queue_forecaster_predicts():
    with patch("os.path.exists", return_value=True):
        with patch("xgboost.XGBRegressor") as mock_xgb:
            mock_model = MagicMock()
            mock_model.predict.return_value = [42.5]
            mock_xgb.return_value = mock_model
            
            forecaster = QueueForecaster()
            assert forecaster.model is not None
            
            features = {
                "queue_length_m": 10.0,
                "vehicle_count": 5,
                "avg_speed_kmh": 20.0,
                "queue_minus_5": 10.0,
                "queue_minus_10": 10.0,
                "queue_minus_15": 10.0,
                "queue_minus_20": 10.0,
                "queue_slope": 0.0
            }
            pred = forecaster.predict(features)
            assert pred == 42.5

def test_queue_forecaster_negative_prediction_clamped():
    with patch("os.path.exists", return_value=True):
        with patch("xgboost.XGBRegressor") as mock_xgb:
            mock_model = MagicMock()
            mock_model.predict.return_value = [-5.0]
            mock_xgb.return_value = mock_model
            
            forecaster = QueueForecaster()
            
            features = {
                "queue_length_m": 10.0,
                "vehicle_count": 5,
                "avg_speed_kmh": 20.0,
                "queue_minus_5": 10.0,
                "queue_minus_10": 10.0,
                "queue_minus_15": 10.0,
                "queue_minus_20": 10.0,
                "queue_slope": 0.0
            }
            pred = forecaster.predict(features)
            assert pred == 0.0 # Clamped to 0
