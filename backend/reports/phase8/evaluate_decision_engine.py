import json
import sys
import os
import pandas as pd
from pathlib import Path

sys.path.append(str(Path("backend").resolve()))

import traci
from app.sim.corridor_candidate_generator import CorridorCandidateGenerator
from app.sim.corridor_counterfactual import CorridorCounterfactualEvaluator
from app.sim.corridor_state import CorridorState, CorridorJunctionState

SUMO_CFG = "backend/sumo_network/config/phase6/TEST_normal_82452.sumocfg"

J1 = "J1_SAN"
J2 = "J2_SJM"
J3 = "J3_SAP"
TLS_MAP = {
    J1: "cluster_13546492148_1838721956",
    J2: "cluster_2061304035_245647208",
    J3: "cluster_245647168_3238255150_3495323634"
}

def main():
    if not Path(SUMO_CFG).exists():
        print(f"File not found: {SUMO_CFG}")
        sys.exit(1)

    traci.start([
        "sumo", "-c", SUMO_CFG,
        "--step-length", "1.0",
        "--no-warnings",
        "--no-step-log"
    ])

    for _ in range(150):
        traci.simulationStep()
        
    cand_gen = CorridorCandidateGenerator(max_candidates=100)
    counterfactual = CorridorCounterfactualEvaluator(SUMO_CFG)

    junction_states = {}
    for jid, tls_id in TLS_MAP.items():
        q = 0.0
        v = 0
        s = 0.0
        try:
            lanes = list(set(traci.trafficlight.getControlledLanes(tls_id)))
            for lane in lanes:
                q += traci.lane.getLastStepHaltingNumber(lane) * 5.0
                v += traci.lane.getLastStepVehicleNumber(lane)
                s += traci.lane.getLastStepMeanSpeed(lane) * 3.6
            if len(lanes) > 0:
                s /= len(lanes)
        except:
            pass

        pred_queue = q + 5.0
        
        junction_states[jid] = CorridorJunctionState(
            junction_id=jid,
            tls_id=tls_id,
            queue_length_m=q,
            vehicle_count=int(v),
            avg_speed_kmh=s,
            capacity_m=500.0,
            predicted_queue_length_m=pred_queue,
            predicted_capacity_ratio=min(1.0, pred_queue/500.0),
            risk_level="HIGH" if pred_queue > 200 else "LOW",
            timestamp=150.0
        )
        
    corridor_state = CorridorState(
        corridor_id="MAIN",
        timestamp=150.0,
        junctions=junction_states,
        upstream_downstream_relationships={J1: J2, J2: J3},
        total_queue_m=sum(js.queue_length_m for js in junction_states.values()),
        max_predicted_capacity_ratio=max(js.predicted_capacity_ratio for js in junction_states.values()),
        critical_junction_id=J3,
        corridor_risk="HIGH",
        active_interventions=[]
    )

    traci.simulation.saveState("tmp_state.xml")
    traci.close() 

    candidates = cand_gen.generate_corridor_candidates(corridor_state)
    
    target_combos = [
        [], [J1], [J2], [J3], [J1, J2], [J2, J3], [J1, J2, J3]
    ]
    
    selected_cands = {}
    for t in target_combos:
        t_set = set(t)
        for c in candidates:
            if set(c.changed_junctions) == t_set:
                name = "+".join(t) if t else "HOLD"
                selected_cands[name] = c
                break

    print(f"Evaluating {len(selected_cands)} candidates...")
    
    eval_cands_list = list(selected_cands.values())
    eval_names = list(selected_cands.keys())
    
    evaluations = counterfactual.evaluate_candidates(eval_cands_list, "tmp_state.xml")

    results = []
    for name, cf_result in zip(eval_names, evaluations):
        results.append({
            "combination": name,
            "avg_queue_m": cf_result.avg_queue_m,
            "max_queue_m": cf_result.max_queue_m,
            "spillback": cf_result.max_queue_m > 300,
            "halting_vehicles": cf_result.total_halting_vehicles
        })

    df = pd.DataFrame(results)
    
    try:
        hold_q = float(df[df['combination'] == 'HOLD']['avg_queue_m'].iloc[0])
        j3_q = float(df[df['combination'] == 'J3_SAP']['avg_queue_m'].iloc[0])
        j123_q = float(df[df['combination'] == 'J1_SAN+J2_SJM+J3_SAP']['avg_queue_m'].iloc[0])
        
        j3_imp = ((hold_q - j3_q) / hold_q) * 100 if hold_q else 0
        j123_imp = ((hold_q - j123_q) / hold_q) * 100 if hold_q else 0
        interaction = j123_imp - j3_imp
    except Exception as e:
        hold_q, j3_q, j123_q, j3_imp, j123_imp, interaction = (0,0,0,0,0,0)

    df.to_csv("backend/reports/phase8/PHASE8_DECISION_RESULTS.csv", index=False)
    
    report_content = "## Phase 8 Decision Benchmark\n\n"
    report_content += "| Combination | Avg Queue (m) | Max Queue (m) | Spillback | Halting Veh |\n"
    report_content += "|-------------|---------------|---------------|-----------|-------------|\n"
    for r in results:
        report_content += f"| {r['combination']} | {r['avg_queue_m']:.2f} | {r['max_queue_m']:.2f} | {r['spillback']} | {r['halting_vehicles']} |\n"

    report_content += f"\n### Interaction Metric Calculation\n"
    report_content += f"- HOLD baseline: {hold_q:.2f} m\n"
    report_content += f"- J3-only intervention: {j3_q:.2f} m ({j3_imp:+.2f}% vs HOLD)\n"
    report_content += f"- Coordinated J1+J2+J3: {j123_q:.2f} m ({j123_imp:+.2f}% vs HOLD)\n"
    report_content += f"- **Phase 8 Interaction Result**: ~{interaction:+.2f} percentage points difference between isolated and coordinated interventions.\n"
    
    with open("backend/reports/phase8/PHASE8_FINAL_REPORT.md", "a") as f:
        f.write("\n" + report_content + "\n")
        
    if os.path.exists("tmp_state.xml"):
        os.remove("tmp_state.xml")
        
    print("Decision Benchmark completed successfully.")

if __name__ == "__main__":
    main()
