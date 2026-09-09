import subprocess
import json
import time
import uuid
import sys
import os
from pathlib import Path
import datetime

import traci
from app.sim.manager import SimulationManager
from app.models.recommendation_store import store
from app.db.database import SessionLocal, RecommendationOutcome
import app.main as main_module
import asyncio
import threading

from fastapi.testclient import TestClient

def run_scenario(scenario_cfg_path, demand_label, enable_pravaha=True):
    # Setup test server for API overrides
    import uvicorn
    
    # We will just run the simulation headless using a mock manager loop
    project_dir = Path("backend").absolute()
    mgr = SimulationManager(project_dir)
    # Override sumocfg
    mgr.sumocfg_path = Path(scenario_cfg_path)
    
    # We don't start the FastAPI server, we just use TestClient or direct calls
    
    print(f"Starting scenario {demand_label} with PRAVAHA={enable_pravaha}")
    traci.start([
        "sumo", "-c", str(scenario_cfg_path),
        "--step-length", "1.0", "--no-warnings"
    ])
    
    mgr.is_running = True
    
    # Init controllers
    for j in mgr.junction_config.get("junctions", []):
        tid = j.get("tls_id")
        if tid:
            from app.sim.controllers import BaselineController
            mgr.controllers[tid] = BaselineController(tls_id=tid, label=j.get("label", tid))
            
    # Fake client to auto-approve recommendations
    client = TestClient(main_module.app)
    main_module.sim_manager = mgr
    
    total_q = 0.0
    total_v = 0.0
    steps = 0
    max_q = 0.0
    
    interventions_approved = 0
    
    while traci.simulation.getMinExpectedNumber() > 0 and steps < 600:
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        
        with mgr.lock:
            mgr.state["time_s"] = current_time
            mgr._update_vehicles()
            mgr._update_junctions()
            
            # Outcome observation
            junction_states_for_tracker = {
                jid: {
                    "queue_length_m": j.get("queue_m", 0.0),
                    "vehicle_count": j.get("active_vehicles", 0),
                    "avg_speed_kmh": j.get("_junction_avg_speed_kmh", 0.0),
                }
                for jid, j in mgr.state.get("junctions", {}).items()
            }
            mgr.outcome_tracker.observe(current_time, junction_states_for_tracker)
            
            # Accumulate metrics
            cur_q = sum(j.get("queue_m", 0.0) for j in mgr.state.get("junctions", {}).values())
            cur_v = sum(j.get("_junction_avg_speed_kmh", 0.0) for j in mgr.state.get("junctions", {}).values())
            num_j = max(1, len(mgr.state.get("junctions", [])))
            
            total_q += cur_q / num_j
            total_v += cur_v / num_j
            if (cur_q / num_j) > max_q: max_q = cur_q / num_j
            steps += 1
            
            # Auto-approve if enabled
            if enable_pravaha:
                pending = store.list_pending()
                for rec in pending:
                    # check concurrency
                    if not store.has_active_intervention(rec.selected_candidate.tls_id):
                        print(f"Auto-approving recommendation {rec.recommendation_id} at step {steps}")
                        res = client.post(f"/api/recommendations/{rec.recommendation_id}/approve")
                        if res.status_code == 200:
                            interventions_approved += 1

    traci.close()
    
    avg_q = total_q / steps if steps > 0 else 0
    avg_v = total_v / steps if steps > 0 else 0
    
    # Calculate completed outcomes from DB
    db = SessionLocal()
    outcomes = db.query(RecommendationOutcome).filter(RecommendationOutcome.status == "COMPLETED").all()
    q_imp = sum(o.queue_improvement_pct or 0.0 for o in outcomes) / len(outcomes) if outcomes else 0.0
    v_imp = sum(o.speed_improvement_pct or 0.0 for o in outcomes) / len(outcomes) if outcomes else 0.0
    
    # clear DB for next run
    db.query(RecommendationOutcome).delete()
    db.commit()
    db.close()
    
    # clear store
    store._records.clear()
    
    return {
        "demand": demand_label,
        "pravaha_enabled": enable_pravaha,
        "duration_s": steps,
        "interventions": interventions_approved,
        "avg_queue_m": avg_q,
        "max_queue_m": max_q,
        "avg_speed_kmh": avg_v,
        "queue_improvement_pct": q_imp,
        "speed_improvement_pct": v_imp
    }

if __name__ == "__main__":
    import shutil
    base_cfg = "backend/sumo_network/config/sancheti_congestion.sumocfg"
    
    # We will just run the congestion scenario twice: once with Pravaha, once without
    res_baseline = run_scenario(base_cfg, "congestion", enable_pravaha=False)
    res_pravaha = run_scenario(base_cfg, "congestion", enable_pravaha=True)
    
    report = {
        "baseline": res_baseline,
        "pravaha": res_pravaha
    }
    
    with open("backend/ml/phase3_evaluation.json", "w") as f:
        json.dump(report, f, indent=2)
        
    # Generate MD report
    md = f"""# PHASE 3 EVALUATION REPORT

## Scenario Results (Congestion)

### BASELINE (HOLD)
- Interventions: {res_baseline['interventions']}
- Avg Queue: {res_baseline['avg_queue_m']:.2f} m
- Max Queue: {res_baseline['max_queue_m']:.2f} m
- Avg Speed: {res_baseline['avg_speed_kmh']:.2f} km/h

### PRAVAHA AI
- Interventions: {res_pravaha['interventions']}
- Avg Queue: {res_pravaha['avg_queue_m']:.2f} m
- Max Queue: {res_pravaha['max_queue_m']:.2f} m
- Avg Speed: {res_pravaha['avg_speed_kmh']:.2f} km/h

## Aggregate Comparison
- Queue Improvement: {((res_baseline['avg_queue_m'] - res_pravaha['avg_queue_m']) / max(0.1, res_baseline['avg_queue_m']) * 100):.1f}%
- Speed Improvement: {((res_pravaha['avg_speed_kmh'] - res_baseline['avg_speed_kmh']) / max(0.1, res_baseline['avg_speed_kmh']) * 100):.1f}%
"""
    with open("backend/ml/PHASE3_EVALUATION_REPORT.md", "w") as f:
        f.write(md)
        
    print("Evaluation Complete.")
