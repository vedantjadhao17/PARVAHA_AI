"""
Phase 5: Forecast Performance Evaluation
Evaluates the EXISTING XGBoost model on the held-out test set.
Does NOT retrain the model.
"""
import pandas as pd
import numpy as np
import json
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

FEATURE_COLS = [
    'queue_length_m', 'vehicle_count', 'avg_speed_kmh',
    'queue_minus_5', 'queue_minus_10', 'queue_minus_15', 'queue_minus_20', 'queue_slope'
]
TARGET_COL = 'target_queue_60s'

MODEL_PATH = 'backend/ml/models/queue_forecast_model.json'
TEST_PATH  = 'backend/ml/test.csv'
TRAIN_PATH = 'backend/ml/train.csv'

# Junction display names
JUNCTION_NAMES = {
    'cluster_13546492148_1838721956': 'J1_SAN',
    'cluster_2061304035_245647208': 'J2_SJM',
    'cluster_245647168_3238255150_3495323634': 'J3_SAP',
}

def rmse(y_true, y_pred):
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))

def evaluate():
    model = xgb.XGBRegressor()
    model.load_model(MODEL_PATH)
    
    test = pd.read_csv(TEST_PATH)
    train = pd.read_csv(TRAIN_PATH)
    
    X_test = test[FEATURE_COLS]
    y_test = test[TARGET_COL]
    
    preds = model.predict(X_test)
    naive = test['queue_length_m'].values  # naive: predict current queue
    
    errors = y_test.values - preds
    
    # === Aggregate metrics ===
    agg = {
        'n': len(y_test),
        'model_rmse': rmse(y_test, preds),
        'model_mae': float(mean_absolute_error(y_test, preds)),
        'model_mean_error': float(np.mean(errors)),
        'model_median_ae': float(np.median(np.abs(errors))),
        'model_max_ae': float(np.max(np.abs(errors))),
        'model_r2': float(r2_score(y_test, preds)),
        'naive_rmse': rmse(y_test, naive),
        'naive_mae': float(mean_absolute_error(y_test, naive)),
        'rmse_improvement_pct': (1 - rmse(y_test, preds) / rmse(y_test, naive)) * 100,
        'mae_improvement_pct': (1 - mean_absolute_error(y_test, preds) / mean_absolute_error(y_test, naive)) * 100,
    }
    
    print("\n" + "="*70)
    print("PHASE 5 — FORECAST PERFORMANCE (TEST SET)")
    print("="*70)
    print(f"\nN = {agg['n']} rows")
    print(f"{'Metric':<30} {'Model':<15} {'Naive Baseline'}")
    print("-"*60)
    print(f"{'RMSE (m)':<30} {agg['model_rmse']:<15.2f} {agg['naive_rmse']:.2f}")
    print(f"{'MAE (m)':<30} {agg['model_mae']:<15.2f} {agg['naive_mae']:.2f}")
    print(f"{'Mean Error (m)':<30} {agg['model_mean_error']:<15.2f}")
    print(f"{'Median AE (m)':<30} {agg['model_median_ae']:<15.2f}")
    print(f"{'Max AE (m)':<30} {agg['model_max_ae']:<15.2f}")
    print(f"{'R²':<30} {agg['model_r2']:<15.3f}")
    print(f"{'RMSE improvement vs naive':<30} {agg['rmse_improvement_pct']:<15.1f}%")
    print(f"{'MAE improvement vs naive':<30} {agg['mae_improvement_pct']:.1f}%")
    
    # === Per-junction ===
    print("\n--- Per-Junction Performance ---")
    junc_results = {}
    for jid, grp in test.groupby('junction_id'):
        y_j = grp[TARGET_COL]
        p_j = model.predict(grp[FEATURE_COLS])
        n_j = grp['queue_length_m'].values
        name = JUNCTION_NAMES.get(jid, jid[:20])
        r = {
            'junction_id': jid,
            'name': name,
            'n': len(y_j),
            'model_rmse': rmse(y_j, p_j),
            'model_mae': float(mean_absolute_error(y_j, p_j)),
            'model_mean_error': float(np.mean(y_j.values - p_j)),
            'naive_rmse': rmse(y_j, n_j),
        }
        junc_results[name] = r
        print(f"  {name}: RMSE={r['model_rmse']:.2f}m  MAE={r['model_mae']:.2f}m  "
              f"Bias={r['model_mean_error']:+.2f}m  N={r['n']}  (naive RMSE={r['naive_rmse']:.2f}m)")
    
    # === Per-scenario ===
    print("\n--- Per-Scenario Performance ---")
    scen_results = {}
    for scen, grp in test.groupby('scenario_id'):
        y_s = grp[TARGET_COL]
        p_s = model.predict(grp[FEATURE_COLS])
        n_s = grp['queue_length_m'].values
        r = {
            'n': len(y_s),
            'model_rmse': rmse(y_s, p_s),
            'model_mae': float(mean_absolute_error(y_s, p_s)),
            'naive_rmse': rmse(y_s, n_s),
        }
        scen_results[scen] = r
        print(f"  {scen}: RMSE={r['model_rmse']:.2f}m  MAE={r['model_mae']:.2f}m  "
              f"N={r['n']}  (naive RMSE={r['naive_rmse']:.2f}m)")
    
    # === Error by queue magnitude ===
    print("\n--- Error Distribution by Queue Magnitude ---")
    buckets = [(0,10,'0-10m'), (10,25,'10-25m'), (25,50,'25-50m'), (50,100,'50-100m'), (100,1e6,'>100m')]
    bucket_results = {}
    for lo, hi, label in buckets:
        mask = (y_test >= lo) & (y_test < hi)
        if mask.sum() > 0:
            y_b = y_test[mask]
            p_b = preds[mask]
            r = {
                'n': int(mask.sum()),
                'rmse': rmse(y_b, p_b),
                'mae': float(mean_absolute_error(y_b, p_b)),
                'mean_error': float(np.mean(y_b.values - p_b)),
            }
            bucket_results[label] = r
            print(f"  {label:<10} N={r['n']:4d}  RMSE={r['rmse']:.2f}m  "
                  f"MAE={r['mae']:.2f}m  Bias={r['mean_error']:+.2f}m")
        else:
            bucket_results[label] = {'n': 0, 'note': 'no samples'}
            print(f"  {label:<10} N=0  (no samples in test set)")
    
    # === Save results ===
    results = {
        'aggregate': agg,
        'per_junction': junc_results,
        'per_scenario': scen_results,
        'error_by_magnitude': bucket_results,
        'note': 'IMPORTANT: test split is temporal (last 20% of each scenario), NOT scenario-level separation',
    }
    with open('backend/ml/phase5_forecast_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nSaved: backend/ml/phase5_forecast_results.json")
    return results

if __name__ == '__main__':
    evaluate()
