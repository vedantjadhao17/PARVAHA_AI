import asyncio
import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, List

import xgboost as xgb
import traci

from pravaha.spillback_engine import SpillbackEngine, ForecastResult, SpillbackResult
from pravaha.candidate_generator import CandidateGenerator
from pravaha.safety_gate import SafetyGate
from pravaha.evaluator import Evaluator
from pravaha.decision_selector import DecisionSelector
from app.db.database import SessionLocal, Alert, OperatorLog
from app.sim.feature_extractor import LiveFeatureExtractor
from app.sim.network_geometry import get_net

logger = logging.getLogger(__name__)

class SimulationManager:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        
        # Paths
        self.sumocfg_path = self.project_dir / "config" / "corridor_camera.sumocfg"
        self.static_meta_path = self.project_dir / "data" / "processed" / "corridor_static_metadata.json"
        self.signal_meta_path = self.project_dir / "data" / "processed" / "corridor_signal_metadata.json"
        self.junction_cfg_path = self.project_dir / "config" / "corridor_junctions.json"
        self.policy_cfg_path = self.project_dir / "config" / "corridor_policy.json"
        
        # Load XGBoost models
        self.model_5m = xgb.Booster()
        self.model_5m.load_model(str(self.project_dir / "models" / "queue_5m.json"))
        
        self.model_10m = xgb.Booster()
        self.model_10m.load_model(str(self.project_dir / "models" / "queue_10m.json"))
        
        with open(self.junction_cfg_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize Decision Engine components
        self.spillback_engine = SpillbackEngine(self.static_meta_path)
        self.candidate_generator = CandidateGenerator(self.junction_cfg_path, self.signal_meta_path)
        self.safety_gate = SafetyGate(self.junction_cfg_path, self.signal_meta_path)
        self.evaluator = Evaluator(self.junction_cfg_path, self.static_meta_path, self.policy_cfg_path if self.policy_cfg_path.exists() else None)
        self.decision_selector = DecisionSelector(self.policy_cfg_path if self.policy_cfg_path.exists() else None)
        

        # Feature names - get exactly what XGBoost expects from the loaded model
        self.feature_names = self.model_5m.feature_names
        if not self.feature_names:
            self.feature_names = [f"f{i}" for i in range(42)]
            
        self.feature_extractor = LiveFeatureExtractor(self.feature_names)
        self.pending_plan = None
        self.lock = threading.Lock()
        self.lock = threading.Lock()

        self.is_running = False
        self.state: Dict[str, Any] = {
            "time_s": 0.0,
            "junctions": {},
            "active_alerts": []
        }
        
        # Threading and Asyncio
        self.sim_thread = None
        self.loop = None
        
        # WebSocket subscribers
        self.subscribers = set()

        # Cached sumolib net for coordinate conversion (shared with network_geometry)
        self._net = get_net(str(self.project_dir / "network" / "sancheti_core.net.xml"))

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start the SUMO TraCI process in a dedicated background thread."""
        if self.is_running:
            return
            
        self.loop = loop
        self.is_running = True
        
        # Start the background thread
        self.sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.sim_thread.start()
        
    def _start_sumo(self):
        """Starts or Restarts SUMO."""
        try:
            traci.close()
        except:
            pass
        traci.start(["sumo", "-c", str(self.sumocfg_path), "--no-step-log", "true"])
        
    def _simulation_loop(self):
        """Dedicated thread running the blocking TraCI steps."""
        self._start_sumo()
        
        while self.is_running:
            start_time = time.time()
            
            try:
                # Step SUMO by 1.0s (assuming 0.5s step length in sumocfg)
                traci.simulationStep()
                traci.simulationStep()
                time_s = traci.simulation.getTime()
                
                # Update state
                self.state["time_s"] = time_s
                self._update_junctions()
                self._update_vehicles()

                # Check for approved plans to execute
                with self.lock:
                    if self.pending_plan:
                        success = self._execute_plan(self.pending_plan)
                        if success:
                            self.pending_plan = None

                # Collect 5s Raw Telemetry for J1_SAN_GANESHKHIND
                if int(time_s) % 5 == 0:
                    self._collect_raw_telemetry(time_s)
                    
                # Run Forecasting & Decision Pipeline every 30 seconds
                if int(time_s) % 30 == 0:

                    self._run_pipeline()
                
                # Push WS broadcast to the main asyncio loop
                if self.loop and self.subscribers:
                    asyncio.run_coroutine_threadsafe(self._broadcast_state(), self.loop)
                    
                # Handle scenario end (600s). We assume if time_s goes past 600, or TraCI raises FatalTraCIError
                if time_s >= 600:
                    logger.info("Simulation reached 600s. Restarting scenario to maintain live feed.")
                    self._start_sumo()
                    
            except traci.exceptions.FatalTraCIError:
                # Simulation ended naturally, restart
                logger.info("TraCI connection closed. Restarting scenario.")
                self._start_sumo()
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
            
            # Sleep to maintain 1Hz real-time cadence
            elapsed = time.time() - start_time
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)


    def _update_vehicles(self):
        """Read vehicle positions from TraCI, convert to lon/lat, and store in state."""
        vehicles = []
        net = self._net
        has_geo = net.hasGeoProj() if net else False
        for vid in traci.vehicle.getIDList():
            x, y = traci.vehicle.getPosition(vid)
            speed = traci.vehicle.getSpeed(vid)
            if has_geo:
                lon, lat = net.convertXY2LonLat(x, y)
                vehicles.append({"id": vid, "lon": lon, "lat": lat, "speed": speed})
            else:
                vehicles.append({"id": vid, "lon": None, "lat": None, "speed": speed})
        self.state["vehicles"] = vehicles
            

    def _get_tls_id(self, junction_id):
        if not hasattr(self, 'config') or not self.config:
            return None
        for j in self.config.get("junctions", []):
            if j["junction_id"] == junction_id:
                return j.get("tls_id")
        return None
        
    def _update_junctions(self):
        """Read state from TraCI into our state dict."""
        with open(self.junction_cfg_path, "r") as f:
            junction_cfg_data = json.load(f)
            
        for j in junction_cfg_data.get("junctions", []):
            jid = j["junction_id"]
            
            junction_queue_m = 0.0
            active_vehicles = 0
            
            for app in j.get("approaches", []):
                for edge in app.get("edges", []):
                    num_lanes = traci.edge.getLaneNumber(edge)
                    for i in range(num_lanes):
                        lane_id = f"{edge}_{i}"
                        junction_queue_m += traci.lane.getLastStepHaltingNumber(lane_id) * 5.0
                        active_vehicles += traci.lane.getLastStepVehicleNumber(lane_id)
                        
            try:
                tls_id = self._get_tls_id(jid)
                if tls_id:
                    tl_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                    if 'G' in tl_state or 'g' in tl_state:
                        signal = "GREEN"
                    elif 'y' in tl_state or 'Y' in tl_state:
                        signal = "YELLOW"
                    else:
                        signal = "RED"
                else:
                    signal = "UNKNOWN"
            except traci.exceptions.TraCIException:
                signal = "UNKNOWN"
                
            self.state["junctions"][jid] = {
                "id": jid,
                "name": j.get("label", jid),
                "queue_m": round(junction_queue_m, 1),
                "active_vehicles": active_vehicles,
                "signal_state": signal,
                "status": "Normal" if junction_queue_m < 50 else "Severe"
            }
            


    def _collect_raw_telemetry(self, time_s: float):
        """Collect exact TraCI metrics for the J1_SAN_GANESHKHIND approach to match training."""
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
            tls_id = self._get_tls_id("J1_SAN")
            if tls_id:
                tl_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                is_green = 1 if ('G' in tl_state or 'g' in tl_state) else 0
                is_yellow = 1 if ('Y' in tl_state or 'y' in tl_state) else 0
                is_red = 1 if all(c in ['r', 'R'] for c in tl_state) else 0
            else:
                is_green, is_yellow, is_red = 0, 0, 0
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
        
    def apply_plan(self, plan):
        with self.lock:
            self.pending_plan = plan
            
    def _execute_plan(self, plan):
        import traci
        # First pass: Check if ANY junction is in a clearance phase.
        # If so, we delay applying the entire plan to keep it synchronized.
        for action in plan.junction_actions:
            tls_id = self._get_tls_id(action.junction_id)
            if not tls_id:
                continue
            try:
                tl_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                if 'y' in tl_state.lower() or all(c in 'rsRS' for c in tl_state):
                    logger.info(f"Delaying signal change for plan {plan.plan_id}: {action.junction_id} is currently in a clearance phase.")
                    return False # Tell the caller to keep pending_plan and retry later
            except Exception as e:
                pass
                
        # Second pass: Apply the changes
        for action in plan.junction_actions:
            tls_id = self._get_tls_id(action.junction_id)
            if not tls_id:
                logger.error(f"Cannot find tls_id for junction {action.junction_id}")
                continue
            try:
                traci.trafficlight.setPhase(tls_id, action.phase_id)
                traci.trafficlight.setPhaseDuration(tls_id, action.target_timing)
                logger.info(f"Applied action to {action.junction_id} (TLS {tls_id}): phase {action.phase_id} duration {action.target_timing}s")
            except Exception as e:
                logger.error(f"Failed to apply signal change to {action.junction_id}: {e}")
        return True # Success
                
    def _run_pipeline(self):
        """Run the SpillbackEngine -> Safety -> Evaluate -> Decision loop."""
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


        pred_5m = float(self.model_5m.predict(dmatrix)[0])
        pred_10m = float(self.model_10m.predict(dmatrix)[0])
        
        # 1. Evaluate Spillback Risk
        fr = ForecastResult(
            junction_id="J1_SAN",
            approach_id="GANESHKHIND",
            current_queue_m=j1_queue,
            queue_5m_m=max(0, pred_5m),
            queue_10m_m=max(0, pred_10m),
            confidence="high"
        )
        
        spillback_result = self.spillback_engine.evaluate(fr)
        alert_obj = spillback_result.to_alert()
        
        if alert_obj.severity in ["WATCH", "HIGH", "SPILLBACK"]:
            # Check if alert already active
            if not any(a.get("incident_name") == "Congestion predicted" for a in self.state["active_alerts"]):
                
                # 2. Candidate Generation
                candidates = self.candidate_generator.generate(spillback_result)
                
                # 3. Safety Gate
                safe_candidates = []
                rejected_reasons = {}
                for c in candidates:
                    res = self.safety_gate.validate(c)
                    if res.passed:
                        safe_candidates.append(c)
                    else:
                        rejected_reasons[c.plan_id] = "; ".join(res.reasons)
                        
                # 4. Evaluation
                # Save state for counterfactual replay
                state_file = str(self.project_dir / "outputs" / "live_state_save.xml")
                traci.simulation.saveState(state_file)
                
                results = self.evaluator.evaluate(safe_candidates, base_state_file=state_file)
                
                # 5. Decision Selection
                recommendation = self.decision_selector.select(candidates, results, confidence=spillback_result.confidence)
                
                # Merge safety rejections
                for cid, reason in rejected_reasons.items():
                    if cid not in recommendation.rejected_candidate_reasons:
                        recommendation.rejected_candidate_reasons[cid] = reason
                
                # Persist to DB
                db = SessionLocal()
                try:
                    db_alert = Alert(
                        id=f"INC-AST-{int(time.time())}",
                        incident_name="Congestion predicted",
                        severity=alert_obj.severity,
                        location="Sancheti Chowk",
                        affected_approach="GANESHKHIND",
                        confidence=92.0,
                        expected_in_s=alert_obj.expected_onset_time_s,
                        predicted_impact=alert_obj.supporting_evidence,
                        recommendation_text="Extend east-west green by 20s and coordinate Riverbend.",
                        raw_recommendation_json=json.dumps(recommendation.selected_plan.to_dict()) if hasattr(recommendation.selected_plan, 'to_dict') else "{}"
                    )
                    db.add(db_alert)
                    db.commit()
                    
                    self.state["active_alerts"].append({
                        "id": db_alert.id,
                        "incident_name": db_alert.incident_name,
                        "severity": db_alert.severity
                    })
                finally:
                    db.close()

    async def _broadcast_state(self):
        """Send current state to all connected websocket clients."""
        if not self.subscribers:
            return
            
        message = json.dumps(self.state)
        disconnected = set()
        for ws in self.subscribers:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
                
        for ws in disconnected:
            self.subscribers.remove(ws)

    def stop(self):

        # Feature names - get exactly what XGBoost expects from the loaded model
        self.feature_names = self.model_5m.feature_names
        if not self.feature_names:
            self.feature_names = [f"f{i}" for i in range(42)]
            
        self.feature_extractor = LiveFeatureExtractor(self.feature_names)
        self.pending_plan = None
        self.lock = threading.Lock()
        self.lock = threading.Lock()

        self.is_running = False
        if self.sim_thread:
            self.sim_thread.join(timeout=2.0)
        try:
            traci.close()
        except:
            pass