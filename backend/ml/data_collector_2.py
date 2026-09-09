import sys
from pathlib import Path
import traci

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, TelemetryHistory
import json

project_dir = Path(__file__).resolve().parents[1]
config_dir = project_dir / "sumo_network" / "config"
junctions_cfg = config_dir / "corridor_junctions.json"

with open(junctions_cfg, "r") as f:
    j_config = json.load(f)

tls_ids = [j["tls_id"] for j in j_config.get("junctions", [])]

scenarios = [
    "sancheti_smoke.sumocfg",
    "sancheti_congestion.sumocfg",
    "corridor_camera.sumocfg",
    "sancheti_camera.sumocfg"
]

for scenario in scenarios:
    config_path = config_dir / scenario
    if not config_path.exists():
        continue
    
    print(f"Collecting {scenario}...")
    traci.start(["sumo", "-c", str(config_path), "--quit-on-end"])
    
    # We want 30 minutes of data -> 1800 seconds
    db = SessionLocal()
    for step in range(1800):
        try:
            traci.simulationStep()
            t = traci.simulation.getTime()
            
            # Save every 5s
            if t % 5 == 0:
                for tid in tls_ids:
                    # Get lanes for this tls
                    try:
                        lanes = traci.trafficlight.getControlledLanes(tid)
                        lanes = list(set(lanes))
                        q = sum([traci.lane.getLastStepHaltingNumber(l) * 5.0 for l in lanes])
                        v = sum([traci.lane.getLastStepVehicleNumber(l) for l in lanes])
                        
                        # average speed of vehicles on these lanes
                        speeds = []
                        for l in lanes:
                            veh_ids = traci.lane.getLastStepVehicleIDs(l)
                            for vid in veh_ids:
                                speeds.append(traci.vehicle.getSpeed(vid))
                        
                        avg_s = sum(speeds)/len(speeds) * 3.6 if speeds else 0.0
                        
                        record = TelemetryHistory(
                            scenario_id=scenario.replace('.sumocfg', ''),
                            simulation_time_s=t,
                            junction_id=tid,
                            queue_length_m=q,
                            vehicle_count=v,
                            avg_speed_kmh=avg_s
                        )
                        db.add(record)
                    except Exception as e:
                        pass
                
                db.commit()
                
        except traci.exceptions.FatalTraCIError:
            break
            
    db.close()
    try:
        traci.close()
    except:
        pass
    print(f"Done {scenario}")

print("Collection finished")
