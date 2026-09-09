import os
import uuid
import logging
from typing import List, Dict
import sumolib
import traci
from datetime import datetime, timezone

from app.sim.corridor_state import CorridorPlanCandidate, CorridorCandidateEvaluation
from app.sim.signal_plan import CandidateEvaluation, SafetyCheckResult

logger = logging.getLogger(__name__)

class CorridorCounterfactualEvaluator:
    def __init__(self, sumocfg_path: str, evaluation_horizon_s: int = 60):
        self.sumocfg_path = sumocfg_path
        self.evaluation_horizon_s = evaluation_horizon_s
        # DESIGN NOTE — Evaluation horizon vs. signal cycle length:
        # Default is 60 s. Signal cycles at J1/J2/J3 are all 90 s.
        # See counterfactual.py for the full assessment.
        # PROPOSED FIX (awaiting user approval): change default from 60 to 120.
        # Must be changed atomically in both this file and counterfactual.py.


    def evaluate_candidates(self, candidates: List[CorridorPlanCandidate], state_file: str) -> List[CorridorCandidateEvaluation]:
        if not os.path.exists(state_file):
            logger.error(f"Cannot evaluate: state file {state_file} does not exist.")
            return []

        evaluations = []
        for cand in candidates:
            ev = self._evaluate_single(cand, state_file)
            if ev:
                evaluations.append(ev)

        return evaluations

    def _evaluate_single(self, cand: CorridorPlanCandidate, state_file: str) -> CorridorCandidateEvaluation:
        # Generate unique connection label
        conn_label = f"eval_{cand.candidate_id}_{uuid.uuid4().hex[:6]}"
        
        try:
            sumo_cmd = [
                "sumo",
                "-c", self.sumocfg_path,
                "--load-state", state_file,
                "--step-length", "1.0",
                "--no-step-log", "true",
                "--no-warnings", "true",
                "--duration-log.disable", "true",
            ]
            
            from app.sim.traci_lock import traci_lock
            with traci_lock:
                traci.start(sumo_cmd, label=conn_label)
                try: traci.switch("default")
                except: pass
            conn = traci.getConnection(conn_label)
            
            # Apply all junction plans simultaneously
            for jid, j_cand in cand.junction_candidates.items():
                if "HOLD" not in j_cand.rationale:
                    traci_phases = j_cand.as_traci_phase_dict()
                    if traci_phases:
                        try:
                            logics = conn.trafficlight.getCompleteRedYellowGreenDefinition(j_cand.tls_id)
                            if logics:
                                logic = logics[0]
                                for idx, dur in traci_phases.items():
                                    if 0 <= idx < len(logic.phases):
                                        logic.phases[idx].duration = dur
                                conn.trafficlight.setProgramLogic(j_cand.tls_id, logic)
                        except Exception as e:
                            logger.error(f"Failed to apply counterfactual for {jid}: {e}")

            # Measurement structures
            junction_stats = {
                jid: {"queue_sum": 0.0, "max_queue": 0.0, "total_halting": 0, "speed_sum": 0.0, "speed_samples": 0}
                for jid in cand.junction_candidates.keys()
            }
            
            # Run simulation horizon
            for _ in range(self.evaluation_horizon_s):
                conn.simulationStep()
                
                for jid, j_cand in cand.junction_candidates.items():
                    try:
                        lanes = list(set(conn.trafficlight.getControlledLanes(j_cand.tls_id)))
                        q_m = sum(conn.lane.getLastStepHaltingNumber(l) * 5.0 for l in lanes)
                        halting = sum(conn.lane.getLastStepHaltingNumber(l) for l in lanes)
                        speeds = []
                        for l in lanes:
                            for vid in conn.lane.getLastStepVehicleIDs(l):
                                speeds.append(conn.vehicle.getSpeed(vid))
                        
                        v_avg = sum(speeds) / len(speeds) * 3.6 if speeds else 0.0
                        
                        junction_stats[jid]["queue_sum"] += q_m
                        if q_m > junction_stats[jid]["max_queue"]:
                            junction_stats[jid]["max_queue"] = q_m
                        junction_stats[jid]["total_halting"] += halting
                        if speeds:
                            junction_stats[jid]["speed_sum"] += v_avg
                            junction_stats[jid]["speed_samples"] += 1
                    except Exception:
                        pass
                        
            conn.close()
            
            # Aggregate results
            junction_evals = {}
            corridor_queue_sum = 0.0
            corridor_halting = 0
            corridor_speed_sum = 0.0
            corridor_speed_samples = 0
            
            for jid, stats in junction_stats.items():
                avg_q = stats["queue_sum"] / self.evaluation_horizon_s
                avg_v = stats["speed_sum"] / stats["speed_samples"] if stats["speed_samples"] > 0 else 0.0
                
                # Single-junction evaluation object
                junction_evals[jid] = CandidateEvaluation(
                    candidate_id=cand.junction_candidates[jid].candidate_id,
                    tls_id=cand.junction_candidates[jid].tls_id,
                    safety=SafetyCheckResult(passed=True, violations=[]),
                    avg_queue_m=avg_q,
                    max_queue_m=stats["max_queue"],
                    total_halting_vehicles=stats["total_halting"],
                    score=0,
                    notes=cand.junction_candidates[jid].rationale,
                    evaluation_horizon_s=self.evaluation_horizon_s
                )
                
                corridor_queue_sum += avg_q
                corridor_halting += stats["total_halting"]
                if stats["speed_samples"] > 0:
                    corridor_speed_sum += avg_v
                    corridor_speed_samples += 1
                    
            corridor_avg_q = corridor_queue_sum / len(junction_stats) if junction_stats else 0.0
            corridor_avg_v = corridor_speed_sum / corridor_speed_samples if corridor_speed_samples > 0 else 0.0
            corridor_max_q = max(stats["max_queue"] for stats in junction_stats.values()) if junction_stats else 0.0
            
            return CorridorCandidateEvaluation(
                candidate_id=cand.candidate_id,
                avg_queue_m=corridor_avg_q,
                max_queue_m=corridor_max_q,
                total_halting_vehicles=corridor_halting,
                avg_speed_kmh=corridor_avg_v,
                junction_evaluations=junction_evals,
                score=corridor_avg_q, # Score is just the average queue (lower is better)
                notes=cand.generation_reason,
                evaluation_horizon_s=self.evaluation_horizon_s
            )

        except Exception as e:
            logger.error(f"Counterfactual evaluation failed for candidate {cand.candidate_id}: {e}")
            try:
                traci.getConnection(conn_label).close()
            except:
                pass
            return None
