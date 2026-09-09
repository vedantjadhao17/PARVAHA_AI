import xgboost as xgb
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

class QueueForecaster:
    def __init__(self):
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "models", "queue_forecast_model.json")
        self.load_model()
        
    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = xgb.XGBRegressor()
            self.model.load_model(self.model_path)
            logger.info(f"Loaded QueueForecaster model from {self.model_path}")
        else:
            logger.error(f"Could not find model at {self.model_path}")
            
    def predict(self, feature_dict: dict) -> float:
        if self.model is None:
            return -1.0
            
        features = ['queue_length_m', 'vehicle_count', 'avg_speed_kmh', 
                    'queue_minus_5', 'queue_minus_10', 'queue_minus_15', 'queue_minus_20',
                    'queue_slope']
        
        df = pd.DataFrame([feature_dict])[features]
        pred = self.model.predict(df)[0]
        return max(0.0, float(pred))
