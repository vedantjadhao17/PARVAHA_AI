import os
import subprocess
import xml.etree.ElementTree as ET
import random
import json
import sqlite3
import pandas as pd
import sys; import os; SUMO_HOME = os.environ.get("SUMO_HOME", "/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"); sys.path.append(os.path.join(SUMO_HOME, "tools")); import traci

SUMO_HOME = os.environ.get("SUMO_HOME", "/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo")
RANDOM_TRIPS = os.path.join(SUMO_HOME, "tools", "randomTrips.py")
NET_FILE = "backend/sumo_network/network/sancheti_core.net.xml"
ROUTES_DIR = "backend/sumo_network/routes/phase6"
CONFIG_DIR = "backend/sumo_network/config/phase6"

os.makedirs(ROUTES_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

CATEGORIES = {
    "normal": {"period": 3.0, "heavy": 0.0, "moto": 0.0, "incident": False},
    "low": {"period": 6.0, "heavy": 0.0, "moto": 0.0, "incident": False},
    "high": {"period": 1.5, "heavy": 0.0, "moto": 0.0, "incident": False},
    "extreme": {"period": 0.8, "heavy": 0.0, "moto": 0.0, "incident": False},
    "incident": {"period": 3.0, "heavy": 0.0, "moto": 0.0, "incident": True},
    "heavy_vehicle": {"period": 3.0, "heavy": 0.3, "moto": 0.0, "incident": False},
    "motorcycle": {"period": 3.0, "heavy": 0.0, "moto": 0.5, "incident": False},
    "combined_high_incident": {"period": 1.5, "heavy": 0.0, "moto": 0.0, "incident": True},
    "combined_high_heavy": {"period": 1.5, "heavy": 0.3, "moto": 0.0, "incident": False},
    "combined_high_moto": {"period": 1.5, "heavy": 0.0, "moto": 0.5, "incident": False},
    "combined_incident_heavy": {"period": 3.0, "heavy": 0.3, "moto": 0.0, "incident": True},
    "combined_extreme_hetero": {"period": 0.8, "heavy": 0.2, "moto": 0.3, "incident": True},
}

def generate_route_file(scenario_id, cat_name, seed):
    cat = CATEGORIES[cat_name]
    trips_file = os.path.join(ROUTES_DIR, f"{scenario_id}.trips.xml")
    rou_file = os.path.join(ROUTES_DIR, f"{scenario_id}.rou.xml")
    
    # 1. Generate random trips
    cmd = [
        "python3", RANDOM_TRIPS,
        "-n", NET_FILE,
        "-o", trips_file,
        "-r", rou_file,
        "--seed", str(seed),
        "--end", "600",
        "--period", str(cat["period"]),
        "--min-distance", "500",
        "--remove-loops",
        "--trip-attributes", 'departLane="best" departSpeed="max"'
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    # 2. Mutate route file (vTypes, incident)
    tree = ET.parse(rou_file)
    root = tree.getroot()
    
    # Add vTypes
    vtypes_added = False
    if cat["heavy"] > 0 or cat["moto"] > 0:
        root.insert(0, ET.Element("vType", id="passenger", vClass="passenger", length="5.0", accel="2.6", decel="4.5", maxSpeed="25.0"))
        if cat["heavy"] > 0:
            root.insert(0, ET.Element("vType", id="truck", vClass="truck", length="12.0", accel="1.0", decel="3.0", maxSpeed="15.0"))
        if cat["moto"] > 0:
            root.insert(0, ET.Element("vType", id="motorcycle", vClass="motorcycle", length="2.5", accel="4.0", decel="6.0", maxSpeed="30.0"))
        vtypes_added = True

    incident_placed = False
    
    random.seed(seed)
    for i, vehicle in enumerate(root.findall("vehicle")):
        if vtypes_added:
            r = random.random()
            if r < cat["heavy"]:
                vehicle.set("type", "truck")
            elif r < cat["heavy"] + cat["moto"]:
                vehicle.set("type", "motorcycle")
            else:
                vehicle.set("type", "passenger")
                
        if cat["incident"] and not incident_placed and i > 10:
            # Inject stop for incident
            # Find a vehicle's route and inject stop on 229904828#1 if it passes there
            route = vehicle.find("route")
            if route is not None and "229904828#1" in route.get("edges", ""):
                ET.SubElement(vehicle, "stop", lane="229904828#1_0", duration="300", startPos="10")
                incident_placed = True

    # If incident was required but not placed (no vehicle went there), force one
    if cat["incident"] and not incident_placed:
        veh = ET.SubElement(root, "vehicle", id=f"forced_incident_{seed}", depart="60.0", type="passenger" if vtypes_added else "")
        ET.SubElement(veh, "route", edges="195712757 661187151#0 229904828#0 229904828#1 342557170#0")
        ET.SubElement(veh, "stop", lane="229904828#1_0", duration="300", startPos="10")
        incident_placed = True

    tree.write(rou_file)
    return rou_file

def generate_sumocfg(scenario_id, rou_file):
    cfg_file = os.path.join(CONFIG_DIR, f"{scenario_id}.sumocfg")
    with open(cfg_file, 'w') as f:
        f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="../../network/sancheti_core.net.xml"/>
        <route-files value="../../routes/phase6/{scenario_id}.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="900"/>
    </time>
</configuration>
''')
    return cfg_file

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.app.sim.manager import SimulationManager
from backend.app.sim.corridor_state import CorridorState
import asyncio

def validate_and_collect(scenario_id, cfg_file, cat_name):
    print(f"Validating {scenario_id} ({cat_name})...")
    sumo_cmd = ["sumo", "-c", cfg_file, "--no-warnings", "--step-length", "1.0"]
    try:
        traci.start(sumo_cmd)
    except Exception as e:
        print(f"  ❌ Failed to start SUMO: {e}")
        return False, []

    # Validations
    cat = CATEGORIES[cat_name]
    heavy_seen = 0
    moto_seen = 0
    total_seen = 0
    max_q = 0
    incident_active = False

    # Collect data exactly as manager does
    history_buffers = {
        "cluster_13546492148_1838721956": [],
        "cluster_2061304035_245647208": [],
        "cluster_245647168_3238255150_3495323634": []
    }
    
    rows = []

    for step in range(800):
        try:
            traci.simulationStep()
        except:
            break
        t = traci.simulation.getTime()
        
        # Vehicle type validation
        for vid in traci.vehicle.getIDList():
            total_seen += 1
            vc = traci.vehicle.getVehicleClass(vid)
            if vc == "truck": heavy_seen += 1
            if vc == "motorcycle": moto_seen += 1
            if traci.vehicle.getSpeed(vid) < 0.1 and traci.vehicle.getRoadID(vid) == "229904828#1":
                incident_active = True

        # Every 5s collect telemetry (exactly matching data_collector_2.py semantics)
        if step % 5 == 0 and step > 10:
            for tid in history_buffers.keys():
                lanes = list(set(traci.trafficlight.getControlledLanes(tid)))
                q = sum(traci.lane.getLastStepHaltingNumber(l) * 5.0 for l in lanes)
                v = sum(traci.lane.getLastStepVehicleNumber(l) for l in lanes)
                speeds = []
                for l in lanes:
                    for vid in traci.lane.getLastStepVehicleIDs(l):
                        speeds.append(traci.vehicle.getSpeed(vid))
                avg_s = (sum(speeds) / len(speeds) * 3.6) if speeds else 0.0
                
                max_q = max(max_q, q)
                
                history = history_buffers[tid]
                history.append((q, t))
                q5 = q_10 = q_15 = q_20 = q
                for (hq, ht) in reversed(history):
                    dt = t - ht
                    if 4.5 <= dt <= 5.5:   q5 = hq
                    if 9.5 <= dt <= 10.5:  q_10 = hq
                    if 14.5 <= dt <= 15.5: q_15 = hq
                    if 19.5 <= dt <= 21.0: q_20 = hq
                
                q_slope = (q - q_20) / 20.0 if len(history) >= 20 else 0.0
                
                rows.append({
                    "scenario_id": scenario_id,
                    "junction_id": tid,
                    "simulation_time_s": t,
                    "queue_length_m": q,
                    "vehicle_count": v,
                    "avg_speed_kmh": avg_s,
                    "queue_minus_5": q5,
                    "queue_minus_10": q_10,
                    "queue_minus_15": q_15,
                    "queue_minus_20": q_20,
                    "queue_slope": q_slope
                })
                
                if len(history) > 25:
                    history.pop(0)

    traci.close()

    # Apply physical validity checks
    if total_seen < 10:
        print(f"  ❌ Failed: Too few vehicles ({total_seen})")
        return False, []
    
    if cat["heavy"] > 0 and heavy_seen == 0:
        print(f"  ❌ Failed: Requested heavy vehicles but none seen")
        return False, []
        
    if cat["moto"] > 0 and moto_seen == 0:
        print(f"  ❌ Failed: Requested motorcycles but none seen")
        return False, []
        
    if cat["incident"] and not incident_active:
        print(f"  ❌ Failed: Incident requested but no stationary vehicle on target edge")
        return False, []
        
    if cat["incident"] and max_q < 20:
        print(f"  ❌ Failed: Incident requested but max queue was only {max_q}m (no propagation)")
        return False, []

    print(f"  ✅ Validated. Max queue: {max_q}m, Total vehicles: {total_seen}")
    return True, rows

def main():
    print("Generating Phase 6 Scenarios...")
    
    scenarios = []
    all_rows = []
    
    # We want ~30 scenarios. We have 12 categories.
    # Let's generate 3 seeds per category = 36 scenarios.
    
    splits = ["TRAIN", "VAL", "TEST"]
    
    generated = 0
    validated = 0
    rejected = 0
    
    for cat_name in CATEGORIES.keys():
        for split in splits:
            success = False
            attempts = 0
            while not success and attempts < 3:
                seed = random.randint(10000, 99999)
                scenario_id = f"{split}_{cat_name}_{seed}"
                
                rou_file = generate_route_file(scenario_id, cat_name, seed)
                cfg_file = generate_sumocfg(scenario_id, rou_file)
                
                is_valid, telemetry_rows = validate_and_collect(scenario_id, cfg_file, cat_name)
                
                generated += 1
                if is_valid:
                    validated += 1
                    all_rows.extend(telemetry_rows)
                    scenarios.append({
                        "scenario_id": scenario_id,
                        "category": cat_name,
                        "split": split,
                        "seed": seed,
                        "heavy_requested": CATEGORIES[cat_name]["heavy"],
                        "moto_requested": CATEGORIES[cat_name]["moto"],
                        "incident": CATEGORIES[cat_name]["incident"]
                    })
                    success = True
                else:
                    rejected += 1
                    attempts += 1
                    # cleanup
                    os.remove(rou_file)
                    os.remove(cfg_file)
                    
    # Process target_queue_60s (shift by -12) per scenario/junction
    df = pd.DataFrame(all_rows)
    features = []
    for (scen, junc), group in df.groupby(['scenario_id', 'junction_id']):
        group = group.sort_values('simulation_time_s').reset_index(drop=True)
        group['target_queue_60s'] = group['queue_length_m'].shift(-12)
        features.append(group)
        
    df_feat = pd.concat(features, ignore_index=True)
    df_feat = df_feat.dropna()
    
    # Save datasets EXACTLY by split
    train_df = df_feat[df_feat['scenario_id'].str.startswith("TRAIN")]
    val_df = df_feat[df_feat['scenario_id'].str.startswith("VAL")]
    test_df = df_feat[df_feat['scenario_id'].str.startswith("TEST")]
    
    train_df.to_csv("backend/ml/phase6/train.csv", index=False)
    val_df.to_csv("backend/ml/phase6/val.csv", index=False)
    test_df.to_csv("backend/ml/phase6/test.csv", index=False)
    
    with open("backend/ml/phase6/scenario_manifest.json", "w") as f:
        json.dump({"scenarios": scenarios, "stats": {"generated": generated, "validated": validated, "rejected": rejected}}, f, indent=2)
        
    print(f"\nGeneration Complete. Gen: {generated}, Validated: {validated}, Rejected: {rejected}")
    print(f"Train rows: {len(train_df)}, Val rows: {len(val_df)}, Test rows: {len(test_df)}")

if __name__ == "__main__":
    main()
