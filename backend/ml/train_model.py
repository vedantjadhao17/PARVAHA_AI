import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
import xgboost as xgb
import json
import os

train_df = pd.read_csv("backend/ml/train.csv")
test_df = pd.read_csv("backend/ml/test.csv")

# Baseline: future_queue = current_queue
baseline_preds = test_df['queue_length_m']
baseline_rmse = np.sqrt(mean_squared_error(test_df['target_queue_60s'], baseline_preds))
baseline_mae = mean_absolute_error(test_df['target_queue_60s'], baseline_preds)

print(f"Baseline RMSE: {baseline_rmse:.4f}")
print(f"Baseline MAE: {baseline_mae:.4f}")

# Features for model
features = ['queue_length_m', 'vehicle_count', 'avg_speed_kmh', 
            'queue_minus_5', 'queue_minus_10', 'queue_minus_15', 'queue_minus_20',
            'queue_slope']

X_train = train_df[features]
y_train = train_df['target_queue_60s']

X_test = test_df[features]
y_test = test_df['target_queue_60s']

# Train XGBoost model
model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
model.fit(X_train, y_train)

# Predict and evaluate
model_preds = model.predict(X_test)
model_preds = np.maximum(0, model_preds) # Queue length can't be negative

model_rmse = np.sqrt(mean_squared_error(y_test, model_preds))
model_mae = mean_absolute_error(y_test, model_preds)

print(f"Model RMSE: {model_rmse:.4f}")
print(f"Model MAE: {model_mae:.4f}")

if model_rmse >= baseline_rmse or model_mae >= baseline_mae:
    print("WARNING: Model did not beat baseline!")
    
# Save model
model_path = "backend/ml/models/queue_forecast_model.json"
model.save_model(model_path)

# Save metadata
metadata = {
  "model": "XGBRegressor",
  "forecast_horizon_s": 60,
  "training_samples": len(train_df),
  "test_samples": len(test_df),
  "baseline_rmse": float(baseline_rmse),
  "baseline_mae": float(baseline_mae),
  "model_rmse": float(model_rmse),
  "model_mae": float(model_mae),
  "rmse_improvement_pct": float((baseline_rmse - model_rmse) / baseline_rmse * 100 if baseline_rmse else 0),
  "mae_improvement_pct": float((baseline_mae - model_mae) / baseline_mae * 100 if baseline_mae else 0)
}

with open("backend/ml/models/model_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("Model saved.")
