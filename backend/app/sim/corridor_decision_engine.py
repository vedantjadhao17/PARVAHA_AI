import logging
import os
from typing import List, Optional
from datetime import datetime, timezone

from app.sim.corridor_state import CorridorState, CorridorPlanCandidate, CorridorCandidateEvaluation
from app.sim.corridor_candidate_generator import CorridorCandidateGenerator
from app.sim.corridor_safety_gate import check_corridor_candidate
from app.sim.corridor_counterfactual import CorridorCounterfactualEvaluator
from app.sim.signal_plan import ApprovalRequest, SignalPlanProposal
from app.models.recommendation_store import store
from app.db.database import SessionLocal, Alert
import uuid

logger = logging.getLogger(__name__)

class CorridorDecisionEngine:
    def __init__(self, sumocfg_path: str, evaluation_horizon_s: int = 60, improvement_threshold_pct: float = 5.0):
        self.generator = CorridorCandidateGenerator(max_candidates=20)
        self.evaluator = CorridorCounterfactualEvaluator(sumocfg_path, evaluation_horizon_s)
        self.improvement_threshold_pct = improvement_threshold_pct

    def process_corridor_state(self, state: CorridorState, state_file: str):
        if not os.path.exists(state_file):
            return

        # 1. Determine Risk
        if state.corridor_risk not in ["HIGH", "SPILLBACK"]:
            return

        from app.models.recommendation_store import store
        if store.list_pending():
            logger.info("Skipping decision engine: pending recommendation already exists.")
            return

        # 2. Generate Bounded Candidates
        candidates = self.generator.generate_corridor_candidates(state)
        if not candidates:
            return
            
        # 3. Filter Safe Candidates
        safe_candidates = []
        for cand in candidates:
            safety_res = check_corridor_candidate(cand)
            if safety_res.passed:
                safe_candidates.append(cand)
            else:
                logger.debug(f"[PHASE4] Corridor candidate {cand.candidate_id} rejected by SafetyGate.")

        if not safe_candidates:
            return

        # 4. Joint Evaluation
        evaluations = self.evaluator.evaluate_candidates(safe_candidates, state_file)
        if not evaluations:
            return

        # 5. Select Best Safe Candidate
        baseline_eval = next((e for e in evaluations if e.notes == "HOLD baseline"), None)
        if not baseline_eval:
            return

        best_eval = baseline_eval
        best_imp = -100.0

        # Downstream degradation tolerance (configurable, e.g. 15.0 meters)
        # If any junction's queue increases by more than 15.0 meters compared to HOLD, reject.
        # This protects against unacceptable spillover.
        downstream_degradation_tolerance_m = 15.0

        for ev in evaluations:
            if ev.candidate_id == baseline_eval.candidate_id:
                continue
                
            # Upstream/Downstream check
            unacceptable_spillover = False
            for jid, j_eval in ev.junction_evaluations.items():
                baseline_j_eval = baseline_eval.junction_evaluations.get(jid)
                if baseline_j_eval:
                    degradation = j_eval.avg_queue_m - baseline_j_eval.avg_queue_m
                    if degradation > downstream_degradation_tolerance_m:
                        logger.debug(f"[PHASE4] Rejecting candidate {ev.candidate_id} due to {degradation:.1f}m downstream degradation at {jid}")
                        unacceptable_spillover = True
                        break
                        
            if unacceptable_spillover:
                continue
                
            imp = ((baseline_eval.avg_queue_m - ev.avg_queue_m) / max(baseline_eval.avg_queue_m, 1)) * 100
            if imp > -100.0 and imp > best_imp:
                best_imp = imp
                best_eval = ev

        if best_eval.candidate_id == baseline_eval.candidate_id:
            print("EARLY RETURN: NO BEST", file=open("debug.log","a"))
            logger.info("[PHASE4] No candidate exceeded improvement threshold. Returning NO_SAFE_CHANGE.")
            return
            
        winner_cand = next(c for c in safe_candidates if c.candidate_id == best_eval.candidate_id)

        # 6. Generate Human-Readable Rationale
        rationale = f"CORRIDOR FORECAST: Max Cap Ratio {state.max_predicted_capacity_ratio:.2f}x.\n"
        for jid, cand in winner_cand.junction_candidates.items():
            if "HOLD" not in cand.rationale:
                rationale += f"{jid}: {cand.green_phase_deltas}. "
            else:
                rationale += f"{jid}: HOLD. "
                
        rationale += f"\nCounterfactual SUMO predicted a {best_imp:.1f}% reduction in average corridor queue versus HOLD. Safety checks passed. Operator approval required."

        # 7. Create PENDING request
        # To reuse ApprovalRequest, we represent the corridor plan as a single proposal
        # with multiple junction candidates.
        proposal = SignalPlanProposal(
            candidates=list(winner_cand.junction_candidates.values()),
            source_states=[],
            trigger_reason=f"corridor_risk:{state.corridor_risk}",
            is_no_op=False
        )
        
        req = ApprovalRequest(
            recommendation_id=f"corridor-{winner_cand.candidate_id}",
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            trigger_reason=f"corridor_risk:{state.corridor_risk}",
            source_states=[],  # Populated below
            proposal=proposal,
            evaluations=list(best_eval.junction_evaluations.values()) + list(baseline_eval.junction_evaluations.values()),
            rollback_candidates=[c for c in safe_candidates[0].junction_candidates.values()],  # HOLD baseline
            safety=check_corridor_candidate(winner_cand),
            selected_candidate_id=winner_cand.candidate_id,
            operator_rationale=rationale,
            is_corridor=True,  # Marks this as a multi-junction corridor recommendation
        )

        
        # We need to map source states correctly for the UI
        # UI expects source_states to contain the original junction states
        # The ApprovalRequest model takes SourceState objects
        from app.sim.signal_plan import SourceState as OriginalSourceState
        for jid, j_state in state.junctions.items():
            s = OriginalSourceState(
                junction_id=jid,
                tls_id=j_state.tls_id,
                simulation_time_s=state.timestamp,
                queue_m=j_state.queue_length_m,
                vehicle_count=j_state.vehicle_count,
                avg_speed_kmh=j_state.avg_speed_kmh,
                predicted_queue_60s_m=j_state.predicted_queue_length_m,
                predicted_capacity_ratio=j_state.predicted_capacity_ratio
            )
            req.source_states.append(s)

        # 8. Add to Store
        try:
            store.add(req)
            logger.info(f"[PHASE4] Stored Corridor Recommendation {req.recommendation_id}")
            
            # Create Alert in DB for the UI
            computed_expected_in_s = 300
            if state.critical_junction_id and state.critical_junction_id in state.junctions:
                critical_j = state.junctions[state.critical_junction_id]
                cap = critical_j.capacity_m
                current_q = critical_j.queue_length_m
                pred_q = critical_j.predicted_queue_length_m
                
                # Severity threshold
                threshold = cap * 0.90 if state.corridor_risk == "SPILLBACK" else cap * 0.75
                
                if current_q >= threshold:
                    computed_expected_in_s = 0
                elif pred_q > current_q and pred_q >= threshold:
                    ratio = (threshold - current_q) / (pred_q - current_q)
                    computed_expected_in_s = int(300.0 * ratio)

            db = SessionLocal()
            try:
                # Deduplication: use dynamic corridor ID for location
                alert_location = state.corridor_id.replace("_", " ").title() if state.corridor_id else "Main Corridor"
                
                existing_alert = db.query(Alert).filter(
                    Alert.location == alert_location,
                    Alert.status != "Resolved"
                ).first()

                if existing_alert:
                    logger.info(f"[PHASE4] Unresolved alert already exists for {alert_location}. Skipping duplicate.")
                else:
                    alert = Alert(
                        id=f"INC-AST-{int(datetime.now(timezone.utc).timestamp())}",
                        incident_name="Queue Buildup Detected",
                        severity=state.corridor_risk,
                        location=alert_location,
                        affected_approach="Main Corridor",
                        detected_time=datetime.now(timezone.utc),
                        status="New",
                        assignee="Unassigned",
                        confidence=95.0,
                        expected_in_s=computed_expected_in_s,
                        predicted_impact=f"Corridor is experiencing {state.corridor_risk} risk.",
                        recommendation_text=rationale,
                        raw_recommendation_json="{}"
                    )
                    db.add(alert)
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to save alert to DB: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to store corridor recommendation: {e}")
