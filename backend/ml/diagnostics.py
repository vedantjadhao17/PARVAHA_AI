import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
import sqlite3

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.sim.manager import SimulationManager
import traci

project_dir = Path(__file__).resolve().parents[1]
scenario = "sancheti_congestion.sumocfg"
config_path = project_dir / "sumo_network" / "config" / scenario

print("Running simulation to collect all pairs...")
manager = SimulationManager(project_dir)
manager.sumocfg_path = config_path
manager.state["connection_status"] = "connected"

traci.start(["sumo", "-c", str(config_path), "--step-length", "1.0", "--no-warnings"])

actual_queues = {}
predictions = {}

for i in range(1800):
    try:
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        
        with manager.lock:
            manager.state["time_s"] = current_time
            manager._update_vehicles()
            manager._update_junctions()
            
            for jid, jdata in manager.state["junctions"].items():
                if jid not in actual_queues:
                    actual_queues[jid] = {}
                if jid not in predictions:
                    predictions[jid] = {}
                    
                actual_queues[jid][current_time] = jdata.get("queue_m", 0.0)
                
                if len(manager.history_buffer.get(jid, [])) >= 20:
                    pred_q = jdata.get("predicted_queue_length_m")
                    if pred_q is not None and pred_q >= 0:
                        
                        # Reconstruct feature vector to save for 1.6.3
                        # We need to manually calculate it here to save it
                        q_m = jdata.get("queue_m", 0.0)
                        q_5, q_10, q_15, q_20 = q_m, q_m, q_m, q_m
                        for (q, t) in reversed(manager.history_buffer[jid]):
                            dt = current_time - t
                            if 4.5 <= dt <= 5.5: q_5 = q
                            if 9.5 <= dt <= 10.5: q_10 = q
                            if 14.5 <= dt <= 15.5: q_15 = q
                            if 19.5 <= dt <= 21.0: q_20 = q
                        
                        q_slope = (q_m - q_20) / 20.0 if len(manager.history_buffer[jid]) >= 20 else 0.0
                        
                        feature_vec = {
                            'queue_length_m': q_m,
                            'vehicle_count': jdata.get("active_vehicles", 0),
                            'avg_speed_kmh': manager.state.get("average_speed_kmh", 0.0),
                            'queue_minus_5': q_5,
                            'queue_minus_10': q_10,
                            'queue_minus_15': q_15,
                            'queue_minus_20': q_20,
                            'queue_slope': q_slope
                        }
                        
                        predictions[jid][current_time] = {
                            "pred_q": pred_q,
                            "features": feature_vec
                        }
    except traci.exceptions.FatalTraCIError:
        break

try:
    traci.close()
except:
    pass

print("Simulation finished. Calculating metrics...")

matched_pairs = []

for jid in predictions:
    for t_pred, pdata in predictions[jid].items():
        t_actual = t_pred + 60.0
        if t_actual in actual_queues[jid]:
            actual_q = actual_queues[jid][t_actual]
            matched_pairs.append({
                "junction_id": jid,
                "time_prediction_made": t_pred,
                "predicted_queue_m": pdata["pred_q"],
                "actual_queue_m": actual_q,
                "error": pdata["pred_q"] - actual_q,
                "features": pdata["features"]
            })

df = pd.DataFrame(matched_pairs)

# 1.6.1 - Segment by simulation time
print("\n--- 1.6.1 Segment live error by simulation time ---")
bins = [0, 60, 120, 300, 1800]
labels = ["0-60s", "60-120s", "120-300s", "300s+"]
df['time_window'] = pd.cut(df['time_prediction_made'], bins=bins, labels=labels, right=False)

def calc_metrics(g):
    rmse = np.sqrt(np.mean(g['error']**2))
    mae = np.mean(np.abs(g['error']))
    return pd.Series({"Count": len(g), "RMSE": rmse, "MAE": mae})

time_metrics = df.groupby('time_window', observed=False).apply(calc_metrics).reset_index()
print(time_metrics.to_string(index=False))

# 1.6.2 - Segment by junction
print("\n--- 1.6.2 Segment live error by junction ---")
junc_metrics = df.groupby('junction_id').apply(calc_metrics).reset_index()
print(junc_metrics.to_string(index=False))

print("\n(Checking training data rows per junction)")
train_df = pd.read_csv(project_dir / "ml" / "train.csv")
train_counts = train_df.groupby('junction_id').size().reset_index(name='Train Rows')
print(train_counts.to_string(index=False))

# 1.6.3 - Inspect feature state at high-error prediction moments
print("\n--- 1.6.3 Top 20 highest-error prediction moments ---")
df['abs_error'] = df['error'].abs()
top_20 = df.sort_values('abs_error', ascending=False).head(20)
for idx, row in top_20.iterrows():
    print(f"Junction: {row['junction_id']} | Time: {row['time_prediction_made']}s | Pred: {row['predicted_queue_m']:.1f}m | Actual: {row['actual_queue_m']:.1f}m | Err: {row['error']:.1f}m")
    print(f"  Features: {row['features']}")

