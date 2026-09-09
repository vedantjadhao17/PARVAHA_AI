import pytest
from unittest.mock import patch, MagicMock

from app.sim.decision_engine import DecisionEngine
from app.sim.signal_plan import SourceState, CandidateEvaluation, SafetyCheckResult
from app.models.recommendation_store import store

@pytest.fixture
def engine():
    return DecisionEngine("dummy.sumocfg")

@pytest.fixture
def dummy_state():
    return SourceState(
        junction_id="J1_SAN",
        tls_id="cluster_13546492148_1838721956",
        simulation_time_s=100.0,
        queue_m=250.0,
        predicted_queue_60s_m=300.0,
        predicted_capacity_ratio=1.2,
        vehicle_count=50,
        avg_speed_kmh=5.0
    )

def test_no_improvement_results_in_noop(engine, dummy_state):
    fixed_cands = engine.generator.generate_candidates(dummy_state)
    with patch.object(engine.generator, "generate_candidates", return_value=fixed_cands), patch.object(engine.evaluator, "evaluate_candidates") as mock_eval:
        safety = SafetyCheckResult(passed=True, violations=[])
        evals = [
            CandidateEvaluation(
                candidate_id=fixed_cands[0].candidate_id, tls_id="j1", safety=safety,
                avg_queue_m=100, max_queue_m=150, total_halting_vehicles=20,
                evaluation_horizon_s=60, score=102, notes="HOLD"
            ),
            CandidateEvaluation(
                candidate_id=fixed_cands[1].candidate_id, tls_id="j1", safety=safety,
                avg_queue_m=110, max_queue_m=160, total_halting_vehicles=25,
                evaluation_horizon_s=60, score=112.5, notes="+10s"
            )
        ]
        mock_eval.return_value = evals
        
        initial_count = len(store.list_pending())
        engine.evaluate_forecast(dummy_state, "dummy.xml")
        
        assert len(store.list_pending()) == initial_count

def test_meaningful_improvement_creates_recommendation(engine, dummy_state):
    fixed_cands = engine.generator.generate_candidates(dummy_state)
    with patch.object(engine.generator, "generate_candidates", return_value=fixed_cands), patch.object(engine.evaluator, "evaluate_candidates") as mock_eval:
        safety = SafetyCheckResult(passed=True, violations=[])
        evals = [
            CandidateEvaluation(
                candidate_id=fixed_cands[0].candidate_id, tls_id="j1", safety=safety,
                avg_queue_m=100, max_queue_m=150, total_halting_vehicles=20,
                evaluation_horizon_s=60, score=102, notes="HOLD"
            ),
            CandidateEvaluation(
                candidate_id=fixed_cands[1].candidate_id, tls_id="j1", safety=safety,
                avg_queue_m=50, max_queue_m=75, total_halting_vehicles=10,
                evaluation_horizon_s=60, score=51, notes="+10s"
            )
        ]
        mock_eval.return_value = evals
        
        initial_count = len(store.list_pending())
        engine.evaluate_forecast(dummy_state, "dummy.xml")
        
        pending = store.list_pending()
        assert len(pending) == initial_count + 1
        new_req = pending[-1]
        assert new_req.selected_candidate_id == fixed_cands[1].candidate_id

def test_unsafe_evaluations_ignored(engine):
    safety_pass = SafetyCheckResult(passed=True, violations=[])
    safety_fail = SafetyCheckResult(passed=False, violations=["error"])
    
    evals = [
        CandidateEvaluation(
            candidate_id="hold", tls_id="j1", safety=safety_pass,
            avg_queue_m=100, max_queue_m=150, total_halting_vehicles=20,
            evaluation_horizon_s=60, score=102, notes="HOLD"
        ),
        CandidateEvaluation(
            candidate_id="cand1", tls_id="j1", safety=safety_fail,
            avg_queue_m=10, max_queue_m=15, total_halting_vehicles=2,
            evaluation_horizon_s=60, score=10, notes="+10s"
        )
    ]
    
    best = engine._select_best(evals)
    assert best.candidate_id == "hold"
