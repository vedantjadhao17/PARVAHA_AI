import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.database import Base
from app.sim.outcome_tracker import OutcomeTracker
from app.sim.signal_plan import ApprovalRequest, SourceState, SignalPlanProposal, SignalPlanCandidate, CandidateEvaluation

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    from app.db.database import SessionLocal
    import app.db.database
    app.db.database.SessionLocal = lambda: Session(bind=engine)
    import app.sim.outcome_tracker
    app.sim.outcome_tracker.SessionLocal = app.db.database.SessionLocal
    yield engine
    
def test_outcome_tracker_lifecycle(test_db):
    tracker = OutcomeTracker()
    
    # Create fake request
    source_state = SourceState(
        junction_id="J1", tls_id="TLS1", simulation_time_s=100.0,
        queue_m=10.0, vehicle_count=5, avg_speed_kmh=15.0,
        predicted_queue_60s_m=50.0, predicted_capacity_ratio=0.5
    )
    
    cand = SignalPlanCandidate.construct(candidate_id="cand1", tls_id="TLS1", green_phase_deltas={})
    eval_hold = CandidateEvaluation.construct(evaluation_id="e1", candidate_id="cand0", tls_id="TLS1", avg_queue_m=45.0, max_queue_m=50.0, total_halting_vehicles=10, score=0, notes="HOLD", evaluated_at=datetime.datetime.now(datetime.timezone.utc), safety=None, evaluation_horizon_s=60)
    eval_cand = CandidateEvaluation.construct(evaluation_id="e2", candidate_id="cand1", tls_id="TLS1", avg_queue_m=30.0, max_queue_m=35.0, total_halting_vehicles=5, score=0, notes="Test", evaluated_at=datetime.datetime.now(datetime.timezone.utc), safety=None, evaluation_horizon_s=60)
    
    req = ApprovalRequest.construct(
        recommendation_id="rec1",
        status="PENDING",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        source_states=[source_state],
        candidates=[cand],
        evaluations=[eval_hold, eval_cand],
        selected_candidate_id="cand1"
    )
    
    # Register
    tracker.register_applied_recommendation(req, 100.0, source_state)
    
    assert "rec1" in tracker.active_trackers
    assert tracker.active_trackers["rec1"]["status"] == "ACTIVE"
    
    # Observe at +30s
    tracker.observe(130.0, {"J1": {"queue_length_m": 20.0, "vehicle_count": 10, "avg_speed_kmh": 12.0}})
    assert tracker.active_trackers["rec1"]["status"] == "OBSERVING"
    assert tracker.active_trackers["rec1"]["post_30s_queue_m"] == 20.0
    
    # Observe at +120s
    tracker.observe(220.0, {"J1": {"queue_length_m": 5.0, "vehicle_count": 2, "avg_speed_kmh": 25.0}})
    assert "rec1" not in tracker.active_trackers
    
    # Check DB
    db = Session(bind=test_db)
    from app.db.database import RecommendationOutcome
    outcomes = db.query(RecommendationOutcome).all()
    assert len(outcomes) == 1
    assert outcomes[0].status == "COMPLETED"
    assert outcomes[0].queue_delta_m == -5.0 # 5.0 - 10.0
    assert outcomes[0].speed_delta_kmh == 10.0 # 25.0 - 15.0
    db.close()
    
def test_outcome_tracker_interrupted(test_db):
    tracker = OutcomeTracker()
    
    source_state = SourceState(
        junction_id="J1", tls_id="TLS1", simulation_time_s=100.0,
        queue_m=10.0, vehicle_count=5, avg_speed_kmh=15.0,
        predicted_queue_60s_m=50.0, predicted_capacity_ratio=0.5
    )
    
    req = ApprovalRequest.construct(
        recommendation_id="rec2",
        status="PENDING",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        source_states=[source_state],
        candidates=[],
        evaluations=[],
        selected_candidate_id="cand1"
    )
    
    tracker.register_applied_recommendation(req, 100.0, source_state)
    tracker.handle_disconnect()
    
    assert "rec2" not in tracker.active_trackers
    
    db = Session(bind=test_db)
    from app.db.database import RecommendationOutcome
    outcomes = db.query(RecommendationOutcome).all()
    assert len(outcomes) == 1
    assert outcomes[0].status == "INTERRUPTED"
    db.close()

