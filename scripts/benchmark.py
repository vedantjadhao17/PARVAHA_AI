"""Reproduce forecast accuracy on the checked-in scenario test set.

This measures forecasting error in SUMO data, not traffic reduction.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [
    "queue_length_m", "vehicle_count", "avg_speed_kmh",
    "queue_minus_5", "queue_minus_10", "queue_minus_15",
    "queue_minus_20", "queue_slope",
]
data = pd.read_csv(ROOT / "backend/ml/phase6/test.csv").dropna(
    subset=FEATURES + ["target_queue_60s"]
)
model = xgb.XGBRegressor()
model.load_model(ROOT / "backend/ml/models/queue_forecast_model.json")
prediction = np.maximum(0, model.predict(data[FEATURES]))
target = data["target_queue_60s"].to_numpy()
rmse = float(np.sqrt(np.mean((prediction - target) ** 2)))
baseline = float(np.sqrt(np.mean((data["queue_length_m"] - target) ** 2)))
print(json.dumps({
    "dataset": "backend/ml/phase6/test.csv",
    "rows": len(data),
    "forecast_horizon_seconds": 60,
    "model_rmse_m": round(rmse, 4),
    "persistence_rmse_m": round(baseline, 4),
    "rmse_reduction_pct": round(100 * (baseline - rmse) / baseline, 2),
    "traffic_reduction_validated": False,
}, indent=2))
