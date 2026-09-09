import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import json
import os

MODEL_PATH = "backend/ml/models/queue_forecast_model.json"
TEST_PATH = "backend/ml/phase6/test.csv"
OUT_REPORT = "backend/ml/PHASE6_GENERALIZATION_REPORT.md"

def calc_metrics(y_true, y_pred):
    if len(y_true) < 2: return None
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    errors = y_pred - y_true
    mean_err = np.mean(errors)
    med_ae = np.median(np.abs(errors))
    max_ae = np.max(np.abs(errors))
    return {
        "rmse": rmse, "mae": mae, "r2": r2, 
        "mean_err": mean_err, "med_ae": med_ae, "max_ae": max_ae,
        "n": len(y_true)
    }

def main():
    if not os.path.exists(TEST_PATH):
        print(f"Error: {TEST_PATH} not found.")
        return

    df_test = pd.read_csv(TEST_PATH)
    model = xgb.XGBRegressor()
    model.load_model(MODEL_PATH)
    
    FEATURE_COLS = [
        "queue_length_m", "vehicle_count", "avg_speed_kmh",
        "queue_minus_5", "queue_minus_10", "queue_minus_15",
        "queue_minus_20", "queue_slope"
    ]
    TARGET_COL = "target_queue_60s"
    
    # Exclude rows with NaNs
    df_test = df_test.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = df_test[FEATURE_COLS]
    y = df_test[TARGET_COL]
    
    # Predict
    preds = model.predict(X)
    df_test['predicted'] = preds
    df_test['naive_pred'] = df_test['queue_length_m']
    
    # Aggregate Metrics
    overall = calc_metrics(y, preds)
    naive_overall = calc_metrics(y, df_test['naive_pred'])
    
    # Extract Category from scenario_id (e.g., TEST_normal_12345 -> normal)
    df_test['category'] = df_test['scenario_id'].apply(lambda x: x.split('_', 1)[1].rsplit('_', 1)[0])
    
    cat_metrics = {}
    for cat, group in df_test.groupby('category'):
        cat_metrics[cat] = calc_metrics(group[TARGET_COL], group['predicted'])
        cat_metrics[cat]['naive_rmse'] = calc_metrics(group[TARGET_COL], group['naive_pred'])['rmse']
        
    scen_metrics = {}
    for scen, group in df_test.groupby('scenario_id'):
        scen_metrics[scen] = calc_metrics(group[TARGET_COL], group['predicted'])
        scen_metrics[scen]['naive_rmse'] = calc_metrics(group[TARGET_COL], group['naive_pred'])['rmse']
        
    # Generate Report
    with open(OUT_REPORT, 'w') as f:
        f.write("# PHASE6_GENERALIZATION_REPORT.md\n\n")
        f.write("## Executive Summary\n")
        f.write(f"Evaluated existing XGBoost model on true unseen TEST scenarios (N={len(df_test)} rows).\n\n")
        
        f.write("## Overall Performance\n")
        f.write("| Metric | XGBoost | Naive Baseline |\n|--------|---------|----------------|\n")
        f.write(f"| RMSE | {overall['rmse']:.2f} m | {naive_overall['rmse']:.2f} m |\n")
        f.write(f"| MAE | {overall['mae']:.2f} m | {naive_overall['mae']:.2f} m |\n")
        f.write(f"| R² | {overall['r2']:.3f} | {naive_overall['r2']:.3f} |\n")
        f.write(f"| Mean Error | {overall['mean_err']:.2f} m | {naive_overall['mean_err']:.2f} m |\n")
        f.write(f"| Median AE | {overall['med_ae']:.2f} m | {naive_overall['med_ae']:.2f} m |\n")
        f.write(f"| Max AE | {overall['max_ae']:.2f} m | {naive_overall['max_ae']:.2f} m |\n\n")
        
        f.write("\n## Per-Category Results\n")
        f.write("| Category | N | RMSE | Naive RMSE | MAE | Bias |\n")
        f.write("|----------|---|------|------------|-----|------|\n")
        for cat, m in sorted(cat_metrics.items()):
            if m:
                f.write(f"| {cat} | {m['n']} | {m['rmse']:.2f} | {m['naive_rmse']:.2f} | {m['mae']:.2f} | {m['mean_err']:.2f} |\n")
                
        f.write("\n## Large-Queue Diagnostic Report\n")
        f.write("| Queue Bucket | N | MAE | RMSE | Bias (Mean Error) |\n")
        f.write("|--------------|---|-----|------|-------------------|\n")
        buckets = [(0,25,'0–25 m'),(25,50,'25–50 m'),(50,100,'50–100 m'),(100,150,'100–150 m'),(150,999,'150 m+')]
        for lo, hi, label in buckets:
            mask = (y >= lo) & (y < hi)
            n_bucket = mask.sum()
            if n_bucket > 0:
                y_bucket = y[mask]
                preds_bucket = df_test.loc[mask, 'predicted']
                mae_bucket = mean_absolute_error(y_bucket, preds_bucket)
                rmse_bucket = np.sqrt(mean_squared_error(y_bucket, preds_bucket))
                bias_bucket = np.mean(preds_bucket - y_bucket)
                f.write(f"| {label} | {n_bucket} | {mae_bucket:.2f} m | {rmse_bucket:.2f} m | {bias_bucket:.2f} m |\n")
            else:
                f.write(f"| {label} | 0 | N/A | N/A | N/A |\n")

        f.write("\n## Per-Scenario Results\n")
        f.write("| Scenario | N | RMSE | Naive RMSE | MAE | Bias |\n")
        f.write("|----------|---|------|------------|-----|------|\n")
        for scen, m in sorted(scen_metrics.items()):
            if m:
                f.write(f"| {scen} | {m['n']} | {m['rmse']:.2f} | {m['naive_rmse']:.2f} | {m['mae']:.2f} | {m['mean_err']:.2f} |\n")
                
    print(f"Generated {OUT_REPORT}")

    
if __name__ == "__main__":
    main()
