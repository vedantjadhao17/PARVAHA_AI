import sys
import time
import asyncio
from pathlib import Path
import threading

sys.path.append(str(Path("backend").resolve()))
from app.main import sim_manager

def run_sim():
    # Start loop in a thread
    loop = asyncio.new_event_loop()
    def start_loop(l):
        asyncio.set_event_loop(l)
        l.run_forever()
    t = threading.Thread(target=start_loop, args=(loop,), daemon=True)
    t.start()
    
    # We must reset the sumocfg_path in case it's wrong
    sim_manager.sumocfg_path = Path("backend/sumo_network/config/phase6/TEST_normal_82452.sumocfg")
    
    sim_manager.start(loop)
    
    # Wait for sim to get running
    time.sleep(3.0)
    
    # Let it run a bit
    for i in range(15):
        time.sleep(0.5)
        
    # Read state
    with sim_manager.lock:
        state1 = sim_manager.state.copy()
        time1 = state1.get("time_s")
        
    for i in range(15):
        time.sleep(0.5)
        
    with sim_manager.lock:
        state2 = sim_manager.state.copy()
        time2 = state2.get("time_s")
        
    sim_manager.stop()
    loop.call_soon_threadsafe(loop.stop)
    
    print(f"\n--- TELEMETRY TEST RESULT ---")
    print(f"Time1: {time1}, Time2: {time2}")
    if "junctions" in state1:
        for jid in state1["junctions"]:
            j1 = state1["junctions"][jid]
            j2 = state2["junctions"][jid]
            print(f"[{jid}] T1: {j1.get('queue_m')}m, {j1.get('halting_vehicles')} halt, {j1.get('_junction_avg_speed_kmh')}km/h, Raw: {j1.get('raw_state')}")
            print(f"[{jid}] T2: {j2.get('queue_m')}m, {j2.get('halting_vehicles')} halt, {j2.get('_junction_avg_speed_kmh')}km/h, Raw: {j2.get('raw_state')}")

if __name__ == "__main__":
    run_sim()
