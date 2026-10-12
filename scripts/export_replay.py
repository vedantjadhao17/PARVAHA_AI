"""Export genuine SUMO telemetry for the read-only static showcase.

Run with the virtual environment active: PYTHONPATH=backend python scripts/export_replay.py
No signal interventions are performed or fabricated.
"""
import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import traci

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="pravaha-replay-") as scratch:
        os.environ["PRAVAHA_DATABASE_URL"] = f"sqlite:///{scratch}/replay.db"
        os.environ["PRAVAHA_START_SIMULATION"] = "0"
        from app.main import sim_manager, get_camera, get_network_geometry
        sim_manager._start_sumo()
        sim_manager.decision_engine = None
        frames, trend = [], []
        try:
            for second in range(1, 601):
                traci.simulationStep(second)
                sim_manager.state["time_s"] = float(second)
                sim_manager._update_junctions()
                if second % 2 == 0:
                    sim_manager._update_vehicles()
                    state = copy.deepcopy(sim_manager.state)
                    state["pending_recommendations"] = []
                    for vehicle in state["vehicles"]:
                        vehicle["lon"] = round(vehicle["lon"], 6)
                        vehicle["lat"] = round(vehicle["lat"], 6)
                        vehicle["speed"] = round(vehicle["speed"], 2)
                    frames.append(state)
                if second % 5 == 0:
                    junctions = list(sim_manager.state["junctions"].values())
                    trend.append({
                        "time": f"{second}s", "simulation_time_s": second,
                        "queue": round(sum(j["queue_m"] for j in junctions) / len(junctions), 1),
                        "speed": round(sum(j["_junction_avg_speed_kmh"] for j in junctions) / len(junctions), 1),
                    })
            bundle = {
                "metadata": {
                    "mode": "recorded_simulation", "scenario": sim_manager.sumocfg_path.name,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "sample_interval_s": 2, "duration_s": 600,
                    "note": "Recorded SUMO telemetry. Forecasts computed during export; no inference or signal control runs in the browser.",
                },
                "frames": frames, "trend": trend, "config": sim_manager.config,
                "geometry": get_network_geometry(),
                "cameras": {j["junction_id"]: get_camera(j["junction_id"]) for j in sim_manager.config["junctions"]},
            }
            output = ROOT / "frontend/public/replay.json"
            output.write_text(json.dumps(bundle, separators=(",", ":"), default=str))
            print(f"Exported {len(frames)} observed frames: {output.stat().st_size:,} bytes")
        finally:
            sim_manager.stop()


if __name__ == "__main__":
    main()
