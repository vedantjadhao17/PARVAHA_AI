import traci
import uuid
import time
import logging
from pathlib import Path
from typing import List, Optional

from app.sim.signal_plan import SignalPlanCandidate, CandidateEvaluation, SafetyCheckResult
from app.sim.controllers import BaselineController
from app.sim.safety_gate import check_candidate

logger = logging.getLogger(__name__)

class CounterfactualEvaluator:
    def __init__(self, sumocfg_path: Path):
        self.sumocfg_path = sumocfg_path
        self.horizon_s = 60.0
        # DESIGN NOTE — Evaluation horizon vs. signal cycle length:
        # The three monitored junctions all run a 90-second signal cycle.
        # A 60-second horizon captures less than one full cycle, meaning:
        #   - First-cycle green-phase effects are partially visible
        #   - Downstream queue effects at the next junction are NOT captured
        #     (free-flow travel time J1→J3 ≈ 60 s, so second-junction effects
        #      only begin to appear at the end of the horizon)
        # PROPOSED FIX (awaiting user approval): increase to 120 s to capture
        # at least one full cycle plus immediate downstream effects.
        # Trade-off: each candidate evaluation adds 60 extra simulated seconds,
        # increasing recommendation latency by ~(n_candidates × 1 s per sim-second).
        # For 3–5 candidates this is 180–300 additional ms per recommendation cycle.
        # This change must be applied atomically in both counterfactual.py and
        # corridor_counterfactual.py. DO NOT change until user confirms.


    def evaluate_candidates(self, candidates: List[SignalPlanCandidate], state_file: str) -> List[CandidateEvaluation]:
        evaluations = []
        for candidate in candidates:
            # 1. Safety Gate
            safety = check_candidate(candidate)
            if not safety.passed:
                logger.warning(f"Candidate {candidate.candidate_id} failed safety gate. Skipping SUMO eval.")
                # We can either not include it, or include it with an infinite score.
                # The decision engine will filter out unsafe ones anyway.
                continue

            # 2. SUMO Counterfactual Replay
            eval_result = self._run_counterfactual(candidate, state_file, safety)
            if eval_result:
                evaluations.append(eval_result)

        return evaluations

    def _run_counterfactual(self, candidate: SignalPlanCandidate, state_file: str, safety: SafetyCheckResult) -> Optional[CandidateEvaluation]:
        label = f"cf_{uuid.uuid4().hex[:8]}"
        cmd = [
            "sumo", 
            "-c", str(self.sumocfg_path), 
            "--load-state", str(state_file), 
            "--start", 
            "--quit-on-end",
            "--no-step-log",
            "--no-warnings"
        ]
        
        try:
            traci.start(cmd, label=label)
            conn = traci.getConnection(label)
            
            # Apply Candidate Plan
            controller = BaselineController(tls_id=candidate.tls_id, label=candidate.tls_id, traci_conn=conn)
            
            # We must override traci module methods inside BaselineController if it hardcodes traci.
            # BaselineController imports traci globally. That's a problem if there are multiple connections.
            # We must patch or use conn explicitly. 
            # Actually, BaselineController uses `traci.trafficlight...` which uses the default connection.
            
            changed_phases = candidate.as_traci_phase_dict()
            if changed_phases:
                controller.deploy_new_plan(changed_phases)
            
            total_queue = 0.0
            max_queue = 0.0
            total_halting = 0
            steps = 0
            
            end_time = conn.simulation.getTime() + self.horizon_s
            
            while conn.simulation.getTime() < end_time:
                conn.simulationStep()
                steps += 1
                
                # Collect metrics for this junction
                step_queue = 0.0
                lanes = list(set(conn.trafficlight.getControlledLanes(candidate.tls_id)))
                for lane in lanes:
                    halting = conn.lane.getLastStepHaltingNumber(lane)
                    step_queue += halting * 5.0
                    total_halting += halting
                
                total_queue += step_queue
                if step_queue > max_queue:
                    max_queue = step_queue

            avg_queue = total_queue / steps if steps > 0 else 0.0
            
            # Close connection
            conn.close()
            
            # Score calculation: Lower is better.
            # score = 0.7 * normalized_avg_queue + 0.3 * normalized_max_queue (simplified)
            # Actually we can just use total_halting as a proxy for delay and queue combined
            score = (avg_queue * 1.0) + (total_halting * 0.1)
            
            return CandidateEvaluation(
                candidate_id=candidate.candidate_id,
                tls_id=candidate.tls_id,
                safety=safety,
                avg_queue_m=round(avg_queue, 2),
                max_queue_m=round(max_queue, 2),
                total_halting_vehicles=total_halting,
                evaluation_horizon_s=self.horizon_s,
                score=round(score, 2),
                notes=candidate.rationale
            )
            
        except Exception as e:
            logger.error(f"Counterfactual evaluation failed for {candidate.candidate_id}: {e}")
            try:
                traci.getConnection(label).close()
            except:
                pass
            return None
