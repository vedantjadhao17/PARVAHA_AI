import os
import json
import uuid
import time
from pathlib import Path
import sumolib
import traci
from fastapi.testclient import TestClient

from app.sim.manager import SimulationManager
from app.models.recommendation_store import store
from app.db.database import SessionLocal, RecommendationOutcome
import app.main as main_module

def run_scenario(scenario_cfg_path, demand_label, mode="HOLD"):
    """
    mode: "HOLD", "SINGLE_JUNCTION", or "CORRIDOR"
    """
    project_dir = Path("backend").absolute()
    mgr = SimulationManager(project_dir)
    mgr.sumocfg_path = Path(scenario_cfg_path)
    
    if mode == "SINGLE_JUNCTION":
        # We need to emulate single junction logic since manager.py now defaults to CorridorDecisionEngine
        from app.sim.decision_engine import DecisionEngine
        mgr.decision_engine = DecisionEngine(sumocfg_path=mgr.sumocfg_path)
        
        # We also need to hack manager's _update_junctions loop to call the single engine, 
        # since we removed it from manager.py!
        # Actually, let's just do it directly in this function loop:
        def evaluate_single_junction(cur_time):
            for jid, jd in mgr.state.get("junctions", {}).items():
                risk = jd.get("forecast_risk", "LOW")
                if risk in ["HIGH", "SPILLBACK"]:
                    # Create source state
                    from app.sim.signal_plan import SourceState
                    tls_id = next((x.get("tls_id") for x in mgr.junction_config.get("junctions", []) if x.get("junction_id") == jid), jid)
                    ss = SourceState(
                        junction_id=jid,
                        tls_id=tls_id,
                        simulation_time_s=cur_time,
                        queue_m=jd.get("queue_m", 0.0),
                        vehicle_count=jd.get("active_vehicles", 0),
                        avg_speed_kmh=jd.get("_junction_avg_speed_kmh", 0.0),
                        predicted_queue_60s_m=jd.get("predicted_queue_length_m", 0.0),
                        predicted_capacity_ratio=jd.get("predicted_capacity_ratio", 0.0)
                    )
                    import tempfile
                    cf_state_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xml").name
                    try:
                        traci.simulation.saveState(cf_state_file)
                        mgr.decision_engine.evaluate_forecast(ss, cf_state_file)
                    except Exception as e:
                        pass
        mgr.evaluate_single_junction = evaluate_single_junction
        mgr.decision_engine_mode = "SINGLE"
        
    elif mode == "CORRIDOR":
        mgr.decision_engine_mode = "CORRIDOR"
    else:
        mgr.decision_engine_mode = "HOLD"
        mgr.decision_engine = None

    print(f"Starting scenario {demand_label} with mode={mode}")
    traci.start([
        "sumo", "-c", str(scenario_cfg_path),
        "--step-length", "1.0", "--no-warnings"
    ])
    
    mgr.is_running = True
    
    for j in mgr.junction_config.get("junctions", []):
        tid = j.get("tls_id")
        if tid:
            from app.sim.controllers import BaselineController
            mgr.controllers[tid] = BaselineController(tls_id=tid, label=j.get("label", tid))
            
    client = TestClient(main_module.app)
    main_module.sim_manager = mgr
    
    total_q = 0.0
    total_v = 0.0
    total_halting = 0
    steps = 0
    
    interventions_approved = 0
    
    last_single_eval = 0.0
    
    while traci.simulation.getMinExpectedNumber() > 0 and steps < 600:
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        
        with mgr.lock:
            mgr.state["time_s"] = current_time
            mgr._update_vehicles()
            # _update_junctions also calls CorridorDecisionEngine if mgr.decision_engine is a CorridorDecisionEngine
            if mgr.decision_engine_mode != "CORRIDOR":
                # Temporarily disable so manager.py doesn't run it
                temp_engine = mgr.decision_engine
                mgr.decision_engine = None
                mgr._update_junctions()
                mgr.decision_engine = temp_engine
                
                if mgr.decision_engine_mode == "SINGLE" and current_time - last_single_eval >= 30.0:
                    last_single_eval = current_time
                    mgr.evaluate_single_junction(current_time)
            else:
                mgr._update_junctions()
            
            junction_states_for_tracker = {
                jid: {
                    "queue_length_m": j.get("queue_m", 0.0),
                    "vehicle_count": j.get("active_vehicles", 0),
                    "avg_speed_kmh": j.get("_junction_avg_speed_kmh", 0.0),
                }
                for jid, j in mgr.state.get("junctions", {}).items()
            }
            mgr.outcome_tracker.observe(current_time, junction_states_for_tracker)
            
            cur_q = sum(j.get("queue_m", 0.0) for j in mgr.state.get("junctions", {}).values())
            cur_v = sum(j.get("_junction_avg_speed_kmh", 0.0) for j in mgr.state.get("junctions", {}).values())
            cur_halt = sum(j.get("active_vehicles", 0) for j in mgr.state.get("junctions", {}).values()) # approximation for total
            num_j = max(1, len(mgr.state.get("junctions", {})))
            
            total_q += cur_q / num_j
            total_v += cur_v / num_j
            total_halting += cur_halt / num_j
            steps += 1
            
            if mode != "HOLD":
                pending = store.list_pending()
                for rec in pending:
                    # check concurrency depending on type
                    conflict = False
                    for c in rec.selected_candidates:
                        if "HOLD" not in c.rationale and store.has_active_intervention(c.tls_id):
                            conflict = True
                    if not conflict:
                        print(f"Auto-approving recommendation {rec.recommendation_id} at step {steps}")
                        res = client.post(f"/api/recommendations/{rec.recommendation_id}/approve")
                        if res.status_code == 200:
                            interventions_approved += 1

    traci.close()
    
    avg_q = total_q / steps if steps > 0 else 0
    avg_v = total_v / steps if steps > 0 else 0
    avg_halt = total_halting / steps if steps > 0 else 0
    
    db = SessionLocal()
    outcomes = db.query(RecommendationOutcome).filter(RecommendationOutcome.status == "COMPLETED").all()
    q_imp = sum(o.queue_improvement_pct or 0.0 for o in outcomes) / len(outcomes) if outcomes else 0.0
    v_imp = sum(o.speed_improvement_pct or 0.0 for o in outcomes) / len(outcomes) if outcomes else 0.0
    
    db.query(RecommendationOutcome).delete()
    db.commit()
    db.close()
    
    store._records.clear()
    
    return {
        "demand": demand_label,
        "mode": mode,
        "duration_s": steps,
        "interventions": interventions_approved,
        "avg_queue_m": avg_q,
        "avg_speed_kmh": avg_v,
        "avg_halting": avg_halt,
        "queue_improvement_pct": q_imp,
        "speed_improvement_pct": v_imp
    }

if __name__ == "__main__":
    import shutil
    base_cfg = "backend/sumo_network/config/sancheti_congestion.sumocfg"
    
    # We evaluate 3 modes
    results = {}
    for mode in ["HOLD", "SINGLE_JUNCTION", "CORRIDOR"]:
        res = run_scenario(base_cfg, "congestion", mode=mode)
        results[mode] = res
        
    with open("backend/ml/phase4_evaluation.json", "w") as f:
        json.dump(results, f, indent=2)
        
    md = f"""# PHASE 4 EVALUATION REPORT & ABLATION STUDY

## Scenario Results (Congestion)

### A. BASELINE (HOLD)
- Interventions: {results['HOLD']['interventions']}
- Avg Queue: {results['HOLD']['avg_queue_m']:.2f} m
- Avg Speed: {results['HOLD']['avg_speed_kmh']:.2f} km/h
- Avg Halting: {results['HOLD']['avg_halting']:.2f} vehicles

### B. INDEPENDENT JUNCTION OPTIMIZATION (Phase 2)
- Interventions: {results['SINGLE_JUNCTION']['interventions']}
- Avg Queue: {results['SINGLE_JUNCTION']['avg_queue_m']:.2f} m
- Avg Speed: {results['SINGLE_JUNCTION']['avg_speed_kmh']:.2f} km/h

### C. COORDINATED CORRIDOR OPTIMIZATION (Phase 4)
- Interventions: {results['CORRIDOR']['interventions']}
- Avg Queue: {results['CORRIDOR']['avg_queue_m']:.2f} m
- Avg Speed: {results['CORRIDOR']['avg_speed_kmh']:.2f} km/h

## Ablation Comparison (Queue Reduction vs HOLD)
- Independent Optimization: {((results['HOLD']['avg_queue_m'] - results['SINGLE_JUNCTION']['avg_queue_m']) / max(0.1, results['HOLD']['avg_queue_m']) * 100):.1f}%
- Coordinated Optimization: {((results['HOLD']['avg_queue_m'] - results['CORRIDOR']['avg_queue_m']) / max(0.1, results['HOLD']['avg_queue_m']) * 100):.1f}%
- Interaction Delta (Coord - Indep): {(((results['HOLD']['avg_queue_m'] - results['CORRIDOR']['avg_queue_m']) / max(0.1, results['HOLD']['avg_queue_m']) * 100) - ((results['HOLD']['avg_queue_m'] - results['SINGLE_JUNCTION']['avg_queue_m']) / max(0.1, results['HOLD']['avg_queue_m']) * 100)):.1f} percentage points

"""
    with open("backend/ml/PHASE4_EVALUATION_REPORT.md", "w") as f:
        f.write(md)
        
    print("Phase 4 Evaluation Complete.")

