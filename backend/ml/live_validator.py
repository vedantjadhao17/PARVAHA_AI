import sys
import os
from pathlib import Path
import time
import json
import numpy as np

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.sim.manager import SimulationManager
import traci

project_dir = Path(__file__).resolve().parents[1]
scenario = "sancheti_congestion.sumocfg"
config_path = project_dir / "sumo_network" / "config" / scenario

print(f"Starting live validation on {scenario}...")

manager = SimulationManager(project_dir)
manager.sumocfg_path = config_path
manager.state["connection_status"] = "connected"

traci.start(["sumo", "-c", str(config_path), "--step-length", "1.0", "--no-warnings"])

# Data structures to hold our time series
actual_queues = {}      # dict of jid -> dict of time_s -> queue_m
predictions = {}        # dict of jid -> dict of time_s -> predicted_queue_m

for i in range(1800):  # 30 minutes
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
                    
                actual_q = jdata.get("queue_m", 0.0)
                actual_queues[jid][current_time] = actual_q
                
                # Only record prediction if we have history (model is outputting valid predictions)
                if len(manager.history_buffer.get(jid, [])) >= 20:
                    pred_q = jdata.get("predicted_queue_length_m")
                    if pred_q is not None and pred_q >= 0:
                        predictions[jid][current_time] = pred_q
    except traci.exceptions.FatalTraCIError:
        break

try:
    traci.close()
except:
    pass

print("Simulation finished. Processing metrics...")

matched_pairs = []
unmatched = 0

for jid in predictions:
    for t_pred, pred_q in predictions[jid].items():
        # Look for actual queue at t + 60
        t_actual = t_pred + 60.0
        
        # Exact match since step-length is 1.0
        if t_actual in actual_queues[jid]:
            actual_q = actual_queues[jid][t_actual]
            matched_pairs.append({
                "scenario_id": scenario,
                "junction_id": jid,
                "time_prediction_made": t_pred,
                "time_target": t_actual,
                "predicted_queue_m": pred_q,
                "actual_queue_m": actual_q,
                "error": pred_q - actual_q
            })
        else:
            unmatched += 1

total_predictions = len(matched_pairs) + unmatched
matched_pct = (len(matched_pairs) / total_predictions * 100) if total_predictions > 0 else 0

errors = [p["error"] for p in matched_pairs]
abs_errors = [abs(e) for e in errors]

mean_prediction_error = np.mean(errors) if errors else 0
mean_absolute_error = np.mean(abs_errors) if abs_errors else 0
rmse = np.sqrt(np.mean(np.square(errors))) if errors else 0

results = {
    "total_predictions": total_predictions,
    "matched_pairs_count": len(matched_pairs),
    "unmatched_predictions": unmatched,
    "matched_percentage": round(matched_pct, 2),
    "live_rmse": round(float(rmse), 4),
    "live_mae": round(float(mean_absolute_error), 4),
    "mean_prediction_error": round(float(mean_prediction_error), 4),
    "mean_absolute_error": round(float(mean_absolute_error), 4),
    "sample_pairs": matched_pairs[:5]  # Top 5 samples
}

with open(project_dir / "ml" / "live_validation.json", "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results, indent=2))
