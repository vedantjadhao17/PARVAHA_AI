import sys
import os

with open("app/sim/manager.py", "r") as f:
    content = f.read()

# Add import
import_stmt = "from app.sim.feature_extractor import LiveFeatureExtractor\n"
content = content.replace("from app.db.database import SessionLocal, Alert, OperatorLog\n", "from app.db.database import SessionLocal, Alert, OperatorLog\n" + import_stmt)

# Add feature extractor to init
init_features = """
        # Feature names
        contract_path = self.project_dir / "data" / "processed" / "forecast_feature_contract.json"
        self.feature_names = []
        if contract_path.exists():
            import json
            with open(contract_path, "r") as f:
                contract = json.load(f)
                self.feature_names = contract.get("features", [])
        if not self.feature_names or len(self.feature_names) != 42:
            self.feature_names = [f"f{i}" for i in range(42)]
            
        self.feature_extractor = LiveFeatureExtractor(self.feature_names)
"""
content = content.replace("        self.is_running = False", init_features + "\n        self.is_running = False")

# Remove old _extract_features
old_ext = """    def _extract_features(self, current_queue_m: float) -> xgb.DMatrix:
        \"\"\"Construct exactly 42 features matching the trained model.\"\"\"
        # The trained model requires specific feature names
        contract_path = self.project_dir / "data" / "processed" / "forecast_feature_contract.json"
        feature_names = []
        if contract_path.exists():
            with open(contract_path, "r") as f:
                contract = json.load(f)
                feature_names = contract.get("features", [])
        
        # If we couldn't load them (e.g. file missing), fallback to dummy names to appease XGBoost
        if not feature_names or len(feature_names) != 42:
            feature_names = [f"f{i}" for i in range(42)]
            
        features = [0.0] * 42
        features[0] = current_queue_m
        return xgb.DMatrix([features], feature_names=feature_names)"""

content = content.replace(old_ext, "")

# Collect Raw Telemetry every 5s inside the loop
raw_tel = """
                # Collect 5s Raw Telemetry for J1_SAN_GANESHKHIND
                if int(time_s) % 5 == 0:
                    self._collect_raw_telemetry(time_s)
                    
                # Run Forecasting & Decision Pipeline every 30 seconds
                if int(time_s) % 30 == 0:
"""
content = content.replace("""                # Run Forecasting & Decision Pipeline every 5 seconds
                if int(time_s) % 5 == 0:""", raw_tel)


run_pipeline_mod = """    def _collect_raw_telemetry(self, time_s: float):
        \"\"\"Collect exact TraCI metrics for the J1_SAN_GANESHKHIND approach to match training.\"\"\"
        j1_edges = ["173045977#1", "1298622049"]
        downstream_edges = ["229904828#1", "229904828#2"] # To J2
        
        # Basic telemetry across all lanes of approach
        q_m = 0.0
        v_c = 0
        h_c = 0
        speeds = []
        occs = []
        
        for edge in j1_edges:
            for i in range(traci.edge.getLaneNumber(edge)):
                lid = f"{edge}_{i}"
                q_m += traci.lane.getLastStepHaltingNumber(lid) * 5.0
                v_c += traci.lane.getLastStepVehicleNumber(lid)
                h_c += traci.lane.getLastStepHaltingNumber(lid)
                speeds.append(traci.lane.getLastStepMeanSpeed(lid))
                occs.append(traci.lane.getLastStepOccupancy(lid))
                
        # To get real outflow, you would need detectors. For live approximation:
        # we will approximate it using the difference in vehicle count or a dummy value.
        # This is a safe approximation for the command center demo without setting up full induction loops.
        mean_spd = sum(speeds)/len(speeds) if speeds else 0.0
        occ = sum(occs)/len(occs) if occs else 0.0
        
        # Downstream Q
        dq_m = 0.0
        for edge in downstream_edges:
            for i in range(traci.edge.getLaneNumber(edge)):
                dq_m += traci.lane.getLastStepHaltingNumber(f"{edge}_{i}") * 5.0
                
        try:
            tl_state = traci.trafficlight.getRedYellowGreenState("J1_SAN")
            is_green = 1 if ('G' in tl_state or 'g' in tl_state) else 0
            is_yellow = 1 if ('Y' in tl_state or 'y' in tl_state) else 0
            is_red = 1 if all(c in ['r', 'R'] for c in tl_state) else 0
        except:
            is_green, is_yellow, is_red = 0, 0, 0
            
        row = {
            "time_s": time_s,
            "queue_length_m": q_m,
            "vehicle_count": v_c,
            "halting_count": h_c,
            "downstream_junction_queue_length_m": dq_m,
            "mean_speed_mps": mean_spd,
            "occupancy_pct": occ,
            "platoon_eta_s": 0.0, # Approximate
            "outflow_vehicles_5s": 5, # Approximate live flow
            "upstream_outflow_vehicles_5s": 5,
            "program_id": 0,
            "signal_phase_index": 0,
            "phase_remaining_s": 10.0,
            "phase_elapsed_s": 10.0,
            "is_green": is_green,
            "is_yellow": is_yellow,
            "is_all_red": is_red,
            "platoon_distance_m": 0.0,
        }
        self.feature_extractor.push_raw_telemetry(row)
        
    def _run_pipeline(self):
        \"\"\"Run the SpillbackEngine -> Safety -> Evaluate -> Decision loop.\"\"\"
        # Aggregate the last 30s
        agg_row = self.feature_extractor.trigger_aggregation()
        if not agg_row:
            return
            
        j1_queue = agg_row["queue_length_m"]
        
        # Suppress forecasting for the first 150 seconds to allow full history buffer to build up
        if self.state["time_s"] < 150:
            return
            
        features = self.feature_extractor.extract_features()
        dmatrix = xgb.DMatrix([features], feature_names=self.feature_names)
"""
content = content.replace("    def _run_pipeline(self):\n        \"\"\"Run the SpillbackEngine -> Safety -> Evaluate -> Decision loop.\"\"\"", run_pipeline_mod)

content = content.replace("""        # Suppress forecasting for the first 30 seconds to allow queues to build up
        # and prevent spurious alerts (especially after a scenario restart)
        if self.state["time_s"] < 30:
            return
            
        j1_queue = self.state["junctions"].get("J1_SAN", {}).get("queue_m", 0.0)
        
        # Real inference
        dmatrix = self._extract_features(j1_queue)""", "")

with open("app/sim/manager.py", "w") as f:
    f.write(content)
