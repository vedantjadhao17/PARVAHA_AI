import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
import os

TEST_PATH = "backend/ml/phase6/test.csv"
MODEL_PATH = "backend/ml/models/queue_forecast_model.json"
OUT_REPORT = "backend/ml/phase6/QUEUE_BIAS_ANALYSIS.md"
import xgboost as xgb

def analyze():
    if not os.path.exists(TEST_PATH): return
    df = pd.read_csv(TEST_PATH)
    model = xgb.XGBRegressor()
    model.load_model(MODEL_PATH)
    FEATURE_COLS = ["queue_length_m", "vehicle_count", "avg_speed_kmh", "queue_minus_5", "queue_minus_10", "queue_minus_15", "queue_minus_20", "queue_slope"]
    df = df.dropna(subset=FEATURE_COLS + ["target_queue_60s"])
    df['predicted'] = model.predict(df[FEATURE_COLS])
    df['error'] = df['predicted'] - df['target_queue_60s']
    df['abs_error'] = np.abs(df['error'])
    
    bins = [0, 25, 50, 75, 100, 150, np.inf]
    labels = ["0-25m", "25-50m", "50-75m", "75-100m", "100-150m", "150m+"]
    df['bin'] = pd.cut(df['target_queue_60s'], bins=bins, labels=labels, right=False)
    
    with open(OUT_REPORT, "w") as f:
        f.write("# LARGE QUEUE BIAS INVESTIGATION\n\n")
        f.write("| Bin | Count | RMSE | MAE | Mean Signed Error | Median Abs Error |\n")
        f.write("|-----|-------|------|-----|-------------------|------------------|\n")
        
        for b in labels:
            group = df[df['bin'] == b]
            if len(group) == 0: continue
            rmse = np.sqrt(mean_squared_error(group['target_queue_60s'], group['predicted']))
            mae = mean_absolute_error(group['target_queue_60s'], group['predicted'])
            mean_signed = np.mean(group['error'])
            med_abs = np.median(group['abs_error'])
            
            f.write(f"| {b} | {len(group)} | {rmse:.2f} | {mae:.2f} | {mean_signed:.2f} | {med_abs:.2f} |\n")
            
if __name__ == "__main__":
    analyze()
