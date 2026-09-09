import asyncio
import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, List

import xgboost as xgb
import traci
from app.sim.traci_lock import traci_lock

from app.sim.spillback import SpillbackEngine
from app.sim.corridor_decision_engine import CorridorDecisionEngine
from app.sim.corridor_state import CorridorState, CorridorJunctionState
from app.sim.forecast import QueueForecaster
from collections import deque
import threading
import tempfile
import traci




from app.db.database import SessionLocal, Alert, OperatorLog
from app.sim.feature_extractor import LiveFeatureExtractor
from app.sim.network_geometry import get_net

logger = logging.getLogger(__name__)

class SimulationManager:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

        # Paths
        self.sumocfg_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/config/demo_2_rising.sumocfg")
        self.static_meta_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/config/corridor_static_meta.json")
        self.signal_meta_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/config/corridor_signal_meta.json")
        self.junction_cfg_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/config/corridor_junctions.json")
        self.static_meta_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/config/corridor_static_meta.json")
        self.signal_meta_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/config/corridor_signal_meta.json")
        self.policy_cfg_path = self.project_dir / "config" / "corridor_policy.json"

        # Load XGBoost models



        self.forecast_model = xgb.Booster()
        self.forecast_model.load_model(str(self.project_dir / "ml" / "models" / "queue_forecast_model.json"))

        with open(self.junction_cfg_path, 'r') as f:
            self.config = json.load(f)

        # Initialize Decision Engine components
        self.spillback_engine = SpillbackEngine()
        self.decision_engine = CorridorDecisionEngine(sumocfg_path=self.sumocfg_path)
        self.forecaster = QueueForecaster()
        self.history_buffer = {}
        self.last_decision_eval_s = 0.0
        self.persistent_alerts = {}

        self.corridor_decision_running = False
        self.corridor_decision_lock = threading.Lock()






        # Feature names - get exactly what XGBoost expects from the loaded model
        self.feature_names = self.forecast_model.feature_names
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
        self.net_path = Path("/Users/vedantjadhao/Documents/veda/asteria-command-center/backend/sumo_network/network/sancheti_core.net.xml")
        self._net = get_net(str(self.net_path))

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
            with traci_lock:
                traci.switch("default")
                traci.close()
        except:
            pass
        with traci_lock:
            traci.start(["sumo", "-c", str(self.sumocfg_path), "--no-step-log", "true"], label="default")
            traci.switch("default")

    def _simulation_loop(self):
        """Dedicated thread running the blocking TraCI steps."""
        self._start_sumo()

        while self.is_running:
            start_time = time.time()

            try:
                with traci_lock:
                    traci.switch("default")
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
        from app.sim.network_geometry import _GeoConverter
        vehicles = []
        converter = _GeoConverter(self._net)
        for vid in traci.vehicle.getIDList():
            x, y = traci.vehicle.getPosition(vid)
            speed = traci.vehicle.getSpeed(vid)
            try:
                lon, lat = converter.convert(x, y)
                vehicles.append({"id": vid, "lon": lon, "lat": lat, "speed": speed})
            except Exception:
                pass
        self.state["vehicles"] = vehicles


    def _get_tls_id(self, junction_id):
        if not hasattr(self, 'config') or not self.config:
            return None
        for j in self.config.get("junctions", []):
            if j["junction_id"] == junction_id:
                return j.get("tls_id")
        return None

    def _update_junctions(self):
        try:
            new_junctions = {}
            new_junctions = {}
            current_alerts = []

            for j in self.config.get("junctions", []):
                jid = j["junction_id"]
                tls_id = j.get("tls_id")

                # --- Feature computation: must match data_collector_2.py EXACTLY ---
                # data_collector_2.py uses:
                #   lanes = traci.trafficlight.getControlledLanes(tls_id)  (lane-level, deduped)
                #   q     = sum(traci.lane.getLastStepHaltingNumber(l) * 5.0 for l in lanes)
                #   avg_speed_kmh = mean speed of all vehicles on those lanes (junction-scoped)
                # DO NOT use edge-level calls or the global corridor speed for model features.
                # The global self.state["average_speed_kmh"] is ONLY for the dashboard KPI.

                # Junction-scoped model features (lane-level, matching training pipeline)
                junction_q_m = 0.0    # queue_length_m fed to ML model
                junction_v_c = 0      # vehicle_count fed to ML model
                junction_speeds = []  # raw m/s speeds on this junction's lanes (for model feature)

                halting_vehicles = 0
                raw_state = ""
                current_phase = 0
                next_switch = 0.0

                if tls_id:
                    try:
                        raw_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                        current_phase = traci.trafficlight.getPhase(tls_id)
                        next_switch = traci.trafficlight.getNextSwitch(tls_id)

                        lanes = list(set(traci.trafficlight.getControlledLanes(tls_id)))
                        for lane in lanes:
                            try:
                                hn = traci.lane.getLastStepHaltingNumber(lane)
                                halting_vehicles += hn
                                junction_q_m += hn * 5.0
                                junction_v_c += traci.lane.getLastStepVehicleNumber(lane)
                                for vid in traci.lane.getLastStepVehicleIDs(lane):
                                    junction_speeds.append(traci.vehicle.getSpeed(vid))
                            except Exception:
                                pass
                        junction_avg_speed_kmh = (sum(junction_speeds) / len(junction_speeds) * 3.6
                                          if junction_speeds else 0.0)
                    except Exception as e:
                        pass

                q_m = junction_q_m
                v_c = junction_v_c

                # Maintain 20s history buffer (store state every 1s)
                if jid not in self.history_buffer:
                    self.history_buffer[jid] = deque(maxlen=25)

                cur_time = self.state.get("time_s", 0)
                self.history_buffer[jid].append((q_m, cur_time))

                # Compute lag features (same window logic as build_dataset.py)
                q_5 = q_m
                q_10 = q_m
                q_15 = q_m
                q_20 = q_m

                for (q, t) in reversed(self.history_buffer[jid]):
                    dt = cur_time - t
                    if 4.5 <= dt <= 5.5:  q_5  = q
                    elif 9.5 <= dt <= 10.5: q_10 = q
                    elif 14.5 <= dt <= 15.5: q_15 = q
                    elif 19.5 <= dt <= 20.5: q_20 = q
                    if 4.5 <= dt <= 5.5:  q_5  = q
                    if 9.5 <= dt <= 10.5: q_10 = q
                    if 14.5 <= dt <= 15.5: q_15 = q
                    if 19.5 <= dt <= 21.0: q_20 = q

                q_slope = (q_m - q_20) / 20.0 if len(self.history_buffer[jid]) >= 20 else 0.0

                # ML feature vector — all values are junction-scoped, matching training pipeline
                feature_dict = {
                    'queue_length_m':  q_m,
                    'vehicle_count':   v_c,
                    'avg_speed_kmh':   junction_avg_speed_kmh,   # junction-scoped, NOT corridor-wide
                    'queue_minus_5':   q_5,
                    'queue_minus_10':  q_10,
                    'queue_minus_15':  q_15,
                    'queue_minus_20':  q_20,
                    'queue_slope':     q_slope
                }

                predicted_queue = self.forecaster.predict(feature_dict)

                # Capacity ratio for forecast risk label
                capacity = self.spillback_engine.storage_capacities_m.get(jid, 200.0)
                predicted_ratio = predicted_queue / capacity if capacity > 0 else 0.0

                forecast_risk = "LOW"
                if predicted_ratio >= 1.0:  forecast_risk = "SPILLBACK"
                elif predicted_ratio >= 0.80: forecast_risk = "HIGH"
                elif predicted_ratio >= 0.40: forecast_risk = "MEDIUM"


                new_junctions[jid] = {
                    "name": j["label"],
                    "queue_m": round(q_m, 1),
                    "halting_vehicles": halting_vehicles,
                    "active_vehicles": v_c,
                    "status": "Online",
                    "predicted_queue_length_m": round(predicted_queue, 1),
                    "predicted_capacity_ratio": round(predicted_ratio, 2),
                    "forecast_risk": forecast_risk,
                    "_junction_avg_speed_kmh": round(junction_avg_speed_kmh, 2),
                    "tls_id": tls_id,
                    "raw_state": raw_state,
                    "current_phase": current_phase,
                    "next_switch": next_switch,
                    "remaining_time": max(0, next_switch - cur_time) if next_switch > cur_time else 0
                }

                # --- Phase 2.2 Decision Engine Trigger ---



                # --- Spillback Evaluation (unchanged) ---
                alert = self.spillback_engine.evaluate(jid, j["label"], round(q_m, 1))
                if alert:
                    if jid in self.persistent_alerts:
                        alert["id"] = self.persistent_alerts[jid]["id"]
                        alert["detected_time"] = self.persistent_alerts[jid]["detected_time"]
                    self.persistent_alerts[jid] = alert
                    current_alerts.append(alert)
                else:
                    if jid in self.persistent_alerts:
                        del self.persistent_alerts[jid]

            self.state["junctions"] = new_junctions
            self.state["active_alerts"] = current_alerts

            # --- Corridor Decision Engine ---
            if self.decision_engine:
                cur_time = self.state.get("time_s", 0)
                if cur_time - self.last_decision_eval_s >= 30.0:
                    corridor_risk = "LOW"
                    max_ratio = 0.0
                    critical_jid = ""
                    cj_states = {}

                    for jid, jd in new_junctions.items():
                        ratio = jd.get("predicted_capacity_ratio", 0.0)
                        if ratio > max_ratio:
                            max_ratio = ratio
                            critical_jid = jid

                        risk = jd.get("forecast_risk", "LOW")
                        if risk == "SPILLBACK":
                            corridor_risk = "SPILLBACK"
                        elif risk == "HIGH" and corridor_risk != "SPILLBACK":
                            corridor_risk = "HIGH"

                        # Find the corresponding tls_id from junction_config
                        tls_id = next((x.get("tls_id") for x in self.config.get("junctions", []) if x.get("junction_id") == jid), jid)

                        cj_states[jid] = CorridorJunctionState(
                            junction_id=jid,
                            tls_id=tls_id,
                            queue_length_m=jd.get("queue_m", 0.0),
                            predicted_queue_length_m=jd.get("predicted_queue_length_m", 0.0),
                            capacity_m=self.spillback_engine.storage_capacities_m.get(jid, 200.0),
                            predicted_capacity_ratio=ratio,
                            vehicle_count=jd.get("active_vehicles", 0),
                            avg_speed_kmh=jd.get("_junction_avg_speed_kmh", 0.0),
                            risk_level=risk,
                            timestamp=cur_time
                        )


                    has_high_live_alert = any(a.get("severity") in ["HIGH", "SPILLBACK"] for a in current_alerts)

                    if corridor_risk in ["HIGH", "SPILLBACK"] or has_high_live_alert:
                        if has_high_live_alert and corridor_risk not in ["HIGH", "SPILLBACK"]:
                            corridor_risk = "HIGH" # Force corridor risk up if live alert says so

                        self.last_decision_eval_s = cur_time


                        c_state = CorridorState(
                            corridor_id="pravaha_shivajinagar_three_signal_corridor",
                            timestamp=cur_time,
                            junctions=cj_states,
                            upstream_downstream_relationships={"J1_SAN": "J2_SJM", "J2_SJM": "J3_SAP"},
                            total_queue_m=sum(x.queue_length_m for x in cj_states.values()),
                            max_predicted_capacity_ratio=max_ratio,
                            critical_junction_id=critical_jid,
                            corridor_risk=corridor_risk,
                            active_interventions=[]
                        )


                        with self.corridor_decision_lock:
                            if self.corridor_decision_running:
                                logger.info("Skipping CorridorDecisionEngine run: already running.")
                            else:
                                self.corridor_decision_running = True
                                cf_state_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xml").name
                                try:
                                    with traci_lock:
                                        traci.switch("default")
                                        traci.simulation.saveState(cf_state_file)

                                    def run_corridor_de(st, f):
                                        import os
                                        try:
                                            self.decision_engine.process_corridor_state(st, f)
                                        except Exception as e:
                                            logger.error(f"Corridor Decision Engine failed: {e}")
                                        finally:
                                            try:
                                                os.remove(f)
                                            except Exception as e:
                                                logger.error(f"Failed to remove temp state file: {e}")
                                            with self.corridor_decision_lock:
                                                self.corridor_decision_running = False

                                    t = threading.Thread(target=run_corridor_de, args=(c_state, cf_state_file), daemon=True)
                                    t.start()
                                except Exception as e:
                                    logger.error(f"Failed to save state for corridor counterfactual: {e}")
                                    with self.corridor_decision_lock:
                                        self.corridor_decision_running = False
        except Exception as e:
            logger.error(f"Failed to update junctions: {e}", exc_info=True)

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



    async def _broadcast_state(self):
        """Send current state to all connected websocket clients."""
        from app.models.recommendation_store import store
        pending = store.list_pending()
        self.state["pending_recommendations"] = [req.model_dump() for req in pending]

        if not self.subscribers:
            return

        import json
        message = json.dumps(self.state, default=str)


        disconnected = set()
        for ws in self.subscribers:
            try:
                await ws.send_text(message)
            except Exception as e:
                print(f"[PRAVAHA WS] Broadcast failed, removing subscriber. Error: {e}")
                disconnected.add(ws)

        for ws in disconnected:
            self.subscribers.remove(ws)

    def stop(self):

        # Feature names - get exactly what XGBoost expects from the loaded model
        self.feature_names = self.forecast_model.feature_names
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