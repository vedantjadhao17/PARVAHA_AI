import logging
from typing import Dict, Optional
import uuid
import datetime
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, RecommendationOutcome
from app.sim.signal_plan import ApprovalRequest, SourceState

logger = logging.getLogger(__name__)

class OutcomeTracker:
    def __init__(self):
        # Maps recommendation_id -> active outcome dict
        self.active_trackers: Dict[str, dict] = {}

    def register_applied_recommendation(self, req: ApprovalRequest, current_sim_time: float, current_state: SourceState):
        """
        Registers an applied recommendation to be tracked over the next 120s.
        """
        # Find the counterfactual evaluations
        hold_score = 0.0
        candidate_score = 0.0
        if req.evaluations:
            # Look for hold
            hold_eval = next((e for e in req.evaluations if "HOLD" in (e.notes or "")), None)
            cand_eval = next((e for e in req.evaluations if e.candidate_id == req.selected_candidate_id), None)
            if hold_eval:
                hold_score = hold_eval.avg_queue_m
            if cand_eval:
                candidate_score = cand_eval.avg_queue_m

        outcome_id = str(uuid.uuid4())
        record = {
            "id": outcome_id,
            "recommendation_id": req.recommendation_id,
            "junction_id": current_state.junction_id,
            "tls_id": current_state.tls_id,
            "candidate_id": req.selected_candidate_id,
            "approval_timestamp": datetime.datetime.now(datetime.timezone.utc),
            "application_sim_time_s": current_sim_time,
            
            "pre_queue_m": current_state.queue_m,
            "pre_vehicle_count": current_state.vehicle_count,
            "pre_avg_speed_kmh": current_state.avg_speed_kmh,
            
            "predicted_queue_m": req.source_states[0].predicted_queue_60s_m,
            "predicted_capacity_ratio": req.source_states[0].predicted_capacity_ratio,
            "counterfactual_hold_score": hold_score,
            "counterfactual_candidate_score": candidate_score,
            
            "status": "ACTIVE"
        }
        
        self.active_trackers[req.recommendation_id] = record
        logger.info(f"[OUTCOME] Registered tracker {outcome_id} for recommendation {req.recommendation_id}")
        self._flush_to_db(record)

    def observe(self, current_sim_time: float, junction_states: Dict[str, dict]):
        """
        Called every simulation step to check if any active trackers hit their +30, +60, +90, +120s marks.
        junction_states: dict of junction_id -> { "queue_length_m", "vehicle_count", "avg_speed_kmh" }
        """
        completed = []
        for rec_id, record in self.active_trackers.items():
            if record["status"] in ["COMPLETED", "INTERRUPTED"]:
                continue
            
            elapsed = current_sim_time - record["application_sim_time_s"]
            jid = record["junction_id"]
            if jid not in junction_states:
                continue
                
            state = junction_states[jid]
            
            updated = False
            if elapsed >= 30.0 and "post_30s_queue_m" not in record:
                record["post_30s_queue_m"] = state["queue_length_m"]
                record["status"] = "OBSERVING"
                updated = True
            if elapsed >= 60.0 and "post_60s_queue_m" not in record:
                record["post_60s_queue_m"] = state["queue_length_m"]
                updated = True
            if elapsed >= 90.0 and "post_90s_queue_m" not in record:
                record["post_90s_queue_m"] = state["queue_length_m"]
                updated = True
            if elapsed >= 120.0 and "post_120s_queue_m" not in record:
                record["post_120s_queue_m"] = state["queue_length_m"]
                record["post_120s_avg_speed_kmh"] = state["avg_speed_kmh"]
                record["post_120s_vehicle_count"] = state["vehicle_count"]
                
                # Calculate improvements vs pre_application state
                pre_q = record["pre_queue_m"]
                post_q = state["queue_length_m"]
                record["queue_delta_m"] = post_q - pre_q
                record["queue_improvement_pct"] = -((post_q - pre_q) / pre_q * 100.0) if pre_q > 0 else 0.0
                
                pre_v = record["pre_avg_speed_kmh"]
                post_v = state["avg_speed_kmh"]
                record["speed_delta_kmh"] = post_v - pre_v
                record["speed_improvement_pct"] = ((post_v - pre_v) / pre_v * 100.0) if pre_v > 0 else 0.0
                
                pre_h = pre_q / 5.0
                post_h = post_q / 5.0
                record["halting_delta"] = post_h - pre_h
                record["halting_improvement_pct"] = record["queue_improvement_pct"]
                
                record["status"] = "COMPLETED"
                updated = True
                completed.append(rec_id)
            
            if updated:
                self._flush_to_db(record)
                if record["status"] == "COMPLETED":
                    logger.info(f"[OUTCOME] Tracker {record['id']} COMPLETED. Queue improvement: {record.get('queue_improvement_pct', 0):.1f}%")

        for c in completed:
            del self.active_trackers[c]

    def handle_disconnect(self):
        """Mark active trackers as INTERRUPTED."""
        for rec_id, record in self.active_trackers.items():
            if record["status"] in ["ACTIVE", "OBSERVING"]:
                record["status"] = "INTERRUPTED"
                self._flush_to_db(record)
                logger.warning(f"[OUTCOME] Tracker {record['id']} INTERRUPTED due to disconnect.")
        self.active_trackers.clear()

    def _flush_to_db(self, record: dict):
        db = SessionLocal()
        try:
            existing = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == record["id"]).first()
            if existing:
                for k, v in record.items():
                    setattr(existing, k, v)
            else:
                new_rec = RecommendationOutcome(**record)
                db.add(new_rec)
            db.commit()
        except Exception as e:
            logger.error(f"[OUTCOME] Failed to flush to DB: {e}")
        finally:
            db.close()

