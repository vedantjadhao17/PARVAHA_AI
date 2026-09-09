import sys
from pathlib import Path
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.sim.manager import SimulationManager
import traci

project_dir = Path(__file__).resolve().parents[1]
scenario = "sancheti_congestion.sumocfg"
config_path = project_dir / "sumo_network" / "config" / scenario

manager = SimulationManager(project_dir)
manager.sumocfg_path = config_path

traci.start(["sumo", "-c", str(config_path), "--step-length", "1.0"])

print("Started traci")
step_count = 0
manager.state["connection_status"] = "connected"

for i in range(100):
    traci.simulationStep()
    manager.state["time_s"] = traci.simulation.getTime()
    manager._update_vehicles()
    manager._update_junctions()
    
    if i % 10 == 0:
        for jid, jdata in manager.state["junctions"].items():
            print(f"Step {i}: JID={jid}, queue_m={jdata.get('queue_m')}, pred={jdata.get('predicted_queue_length_m')}, history_len={len(manager.history_buffer.get(jid, []))}")
            
    step_count += 1
traci.close()
print(f"Ran {step_count} steps.")
