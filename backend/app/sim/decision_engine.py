import logging
import threading
from typing import List, Optional
from datetime import datetime, timezone

from app.sim.signal_plan import SourceState, CandidateEvaluation, ApprovalRequest, SignalPlanProposal
from app.sim.candidate_generator import CandidateGenerator
from app.sim.counterfactual import CounterfactualEvaluator
from app.models.recommendation_store import store

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, sumocfg_path):
        self.generator = CandidateGenerator()
        self.evaluator = CounterfactualEvaluator(sumocfg_path=sumocfg_path)
        self.last_evaluation_time_s = 0.0
        self.evaluation_interval_s = 30.0  # run every 30 seconds
        self.improvement_threshold = 0.05  # 5% improvement required

    def evaluate_forecast(self, state: SourceState, state_file: str):
        """
        Takes the current state snapshot and state file, runs candidate generation,
        evaluates them in SUMO, and publishes an ApprovalRequest if a safe, 
        meaningfully better candidate is found.
        """
        logger.info(f"[PHASE2.2] Forecast:\njunction={state.junction_id}\npredicted_queue={state.predicted_queue_60s_m}m\ncapacity_ratio={state.predicted_capacity_ratio}")

        # 1. Generate Candidates
        trigger_reason = f"predicted_spillback:{state.junction_id}" if state.predicted_capacity_ratio >= 1.0 else f"congestion:{state.junction_id}"
        candidates = self.generator.generate_candidates(state)
        
        if len(candidates) <= 1:
            logger.info("[PHASE2.2] Selection:\nNO_SAFE_CHANGE\nreason=no valid candidates could be generated")
            return

        for cand in candidates:
            deltas = cand.green_phase_deltas
            delta_str = ", ".join([f"{p}{'+' if d>0 else ''}{d}s" for p, d in deltas.items()])
            logger.info(f"[PHASE2.2] Candidate:\nid={cand.candidate_id}\nchanged={delta_str}")

        # 2. Counterfactual Evaluation
        evaluations = self.evaluator.evaluate_candidates(candidates, state_file)
        if not evaluations:
            logger.info("[PHASE2.2] Selection:\nNO_SAFE_CHANGE\nreason=Counterfactual evaluation unavailable or all failed")
            return
            
        for ev in evaluations:
            logger.info(f"[PHASE2.2] Safety:\ncandidate={ev.candidate_id}\nresult={'PASS' if ev.safety.passed else 'FAIL'}")
            if ev.safety.passed:
                logger.info(f"[PHASE2.2] Counterfactual:\ncandidate={ev.candidate_id}\nqueue={ev.avg_queue_m}m\nhalting={ev.total_halting_vehicles}")

        # 3. Select Best Safe Candidate
        winner_eval = self._select_best(evaluations)
        if winner_eval is None:
            logger.info("[PHASE2.2] Selection:\nNO_SAFE_CHANGE\nreason=no candidate exceeded improvement threshold")
            return
            
        baseline_eval = next((e for e in evaluations if e.candidate_id == candidates[0].candidate_id), None)
        
        if baseline_eval and winner_eval.candidate_id != baseline_eval.candidate_id:
            imp_queue = ((baseline_eval.avg_queue_m - winner_eval.avg_queue_m) / max(baseline_eval.avg_queue_m, 1)) * 100
            imp_halting = ((baseline_eval.total_halting_vehicles - winner_eval.total_halting_vehicles) / max(baseline_eval.total_halting_vehicles, 1)) * 100
            logger.info(f"[PHASE2.2] Selection:\nwinner={winner_eval.candidate_id}\nimprovement_queue={imp_queue:.1f}%\nimprovement_delay={imp_halting:.1f}%")
        else:
             logger.info(f"[PHASE2.2] Selection:\nwinner=HOLD\nimprovement=0.0%")
             # If HOLD won, no need to push a new request
             return

        # 4. Create Recommendation
        winner_cand = next(c for c in candidates if c.candidate_id == winner_eval.candidate_id)
        final_proposal = SignalPlanProposal(
            candidates=[winner_cand],
            source_states=[state],
            trigger_reason=trigger_reason,
            is_no_op=False
        )
        req = ApprovalRequest(
            proposal=final_proposal,
            trigger_reason=trigger_reason,
            source_states=[state],
            evaluations=evaluations,
            selected_candidate_id=winner_eval.candidate_id,
            rollback_candidates=[c for c in candidates if "HOLD" in c.rationale],
            safety=winner_eval.safety,
            operator_rationale=f"Forecast queue is expected to reach {state.predicted_queue_60s_m:.1f} m, exceeding {state.predicted_capacity_ratio:.2f}× the available approach capacity. Candidate modifies phases by {winner_cand.green_phase_deltas}, preserving the 90 s cycle. Counterfactual SUMO evaluation predicted a {imp_queue:.1f}% reduction in average queue versus HOLD. Safety checks passed. Operator approval required.",
            status="PENDING"
        )
        
        # Add to store
        try:
            store.add(req)
            logger.info(f"[PHASE2.2] Stored Recommendation {req.recommendation_id} as PENDING_APPROVAL")
        except Exception as e:
            logger.error(f"Failed to store recommendation: {e}")

    def _select_best(self, evaluations: List[CandidateEvaluation]) -> Optional[CandidateEvaluation]:
        # Rule 1: Only safe
        safe_evals = [e for e in evaluations if e.safety.passed]
        if not safe_evals:
            return None
            
        # Find HOLD baseline
        baseline = next((e for e in safe_evals if "HOLD" in (e.notes or "")), None)
        if not baseline:
            # If for some reason HOLD failed safety (impossible usually), return None
            return None
            
        # Rule 5: Tie-breaking is implicit in sort order
        # Score is our objective function (lower is better)
        safe_evals.sort(key=lambda x: (x.score, x.avg_queue_m, x.total_halting_vehicles, x.candidate_id))
        
        best = safe_evals[0]
        
        if best.candidate_id == baseline.candidate_id:
            return baseline
            
        # Rule 3: Must beat HOLD by threshold
        if baseline.score > 0:
            improvement = (baseline.score - best.score) / baseline.score
            if improvement >= self.improvement_threshold:
                return best
        elif best.score == 0 and baseline.score > 0:
             return best
             
        return None
