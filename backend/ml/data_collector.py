import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import time
import asyncio
from app.sim.manager import SimulationManager
import traci

# Mock time.sleep to run fast
original_sleep = time.sleep
time.sleep = lambda x: None

scenarios = [
    "sancheti_smoke.sumocfg",
    "sancheti_congestion.sumocfg",
    "corridor_camera.sumocfg",
    "sancheti_camera.sumocfg"
]

project_dir = Path(__file__).resolve().parents[1]
config_dir = project_dir / "sumo_network" / "config"

for scenario in scenarios:
    config_path = config_dir / scenario
    if not config_path.exists():
        print(f"Skipping {scenario}, not found.")
        continue
    
    print(f"Running data collection for {scenario}...")
    
    # Init manager
    manager = SimulationManager(project_dir)
    manager.sumocfg_path = config_path
    
    # We don't start the thread, we just run the loop directly!
    # But wait, manager.start() starts a thread. We can just run the logic inline.
    
    traci.start(["sumo", "-c", str(config_path), "--step-length", "1.0", "--no-warnings"])
    
    # Initialize state manually
    manager.state["connection_status"] = "connected"
    
    # Run for 2000 steps (33 minutes simulated time)
    last_telemetry_save = 0
    from app.db.database import SessionLocal, TelemetryHistory
    
    for i in range(2000):
        try:
            traci.simulationStep()
            current_time = traci.simulation.getTime()
            
            with manager.lock:
                manager.state["time_s"] = current_time
                manager._update_vehicles()
                manager._update_junctions()
            
            if current_time - last_telemetry_save >= 5.0:
                try:
                    scenario_id = config_path.stem
                    db = SessionLocal()
                    for jid, jdata in manager.state["junctions"].items():
                        record = TelemetryHistory(
                            scenario_id=scenario_id,
                            simulation_time_s=current_time,
                            junction_id=jid,
                            queue_length_m=jdata.get("queue_m", 0.0),
                            vehicle_count=jdata.get("active_vehicles", 0),
                            avg_speed_kmh=manager.state.get("average_speed_kmh", 0.0)
                        )
                        db.add(record)
                    db.commit()
                    db.close()
                except Exception as e:
                    print(f"DB Write error: {e}")
                last_telemetry_save = current_time
                
        except Exception as e:
            print(f"Error: {e}")
            break
            
    traci.close()
    print(f"Finished {scenario}.")

print("Data collection complete.")
