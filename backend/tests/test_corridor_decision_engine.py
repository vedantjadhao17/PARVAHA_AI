import pytest
from unittest.mock import patch, MagicMock

from app.sim.corridor_decision_engine import CorridorDecisionEngine
from app.sim.corridor_state import CorridorState, CorridorPlanCandidate, CorridorCandidateEvaluation, CorridorJunctionState
from app.sim.signal_plan import SafetyCheckResult, SignalPlanCandidate
from app.models.recommendation_store import store

@pytest.fixture
def engine():
    return CorridorDecisionEngine("dummy.sumocfg")

@pytest.fixture
def dummy_corridor_state():
    j_state = CorridorJunctionState(
        junction_id="J1_SAN",
        tls_id="cluster_13546492148_1838721956",
        queue_length_m=250.0,
        predicted_queue_length_m=300.0,
        capacity_m=250.0,
        predicted_capacity_ratio=1.2,
        vehicle_count=50,
        avg_speed_kmh=5.0,
        risk_level="SPILLBACK",
        timestamp=100.0
    )
    return CorridorState(
        corridor_id="SANCHETI_CORRIDOR",
        simulation_time_s=100.0,
        junctions={"J1_SAN": j_state},
        upstream_downstream_relationships={"J1_SAN": "J2_SJM"},
        total_queue_m=250.0,
        max_predicted_capacity_ratio=1.2,
        critical_junction_id="J1_SAN",
        active_interventions=[],
        corridor_avg_speed_kmh=10.0,
        corridor_total_queue_m=250.0,
        corridor_risk="HIGH",
        timestamp=100.0
    )

def test_no_improvement_results_in_noop_corridor(engine, dummy_corridor_state):
    fixed_cands = engine.generator.generate_corridor_candidates(dummy_corridor_state)
    with patch.object(engine.generator, "generate_corridor_candidates", return_value=fixed_cands), patch.object(engine.evaluator, "evaluate_candidates") as mock_eval, patch("app.sim.corridor_decision_engine.check_corridor_candidate") as mock_check, patch("os.path.exists", return_value=True):
        mock_check.return_value = SafetyCheckResult(passed=True, violations=[])
        safety = SafetyCheckResult(passed=True, violations=[])
        evals = [
            CorridorCandidateEvaluation(
                candidate_id=fixed_cands[0].candidate_id,
                junction_evaluations={},
                avg_queue_m=100,
                max_queue_m=150,
                avg_speed_kmh=10,
                total_halting_vehicles=20,
                evaluation_horizon_s=60,
                score=100,
                safety=safety,
                notes="HOLD"
            ),
            CorridorCandidateEvaluation(
                candidate_id=fixed_cands[1].candidate_id,
                junction_evaluations={},
                avg_queue_m=110,
                max_queue_m=160,
                avg_speed_kmh=9,
                total_halting_vehicles=25,
                evaluation_horizon_s=60,
                score=110,
                safety=safety,
                notes="Cascade"
            )
        ]
        mock_eval.return_value = evals
        
        initial_count = len(store.list_pending())
        engine.process_corridor_state(dummy_corridor_state, "dummy.xml")
        
        # No recommendation should be added since "Cascade" is worse than "HOLD"
        assert len(store.list_pending()) == initial_count

def test_meaningful_improvement_creates_recommendation_corridor(engine, dummy_corridor_state):
    fixed_cands = engine.generator.generate_corridor_candidates(dummy_corridor_state)
    with patch.object(engine.generator, "generate_corridor_candidates", return_value=fixed_cands), patch.object(engine.evaluator, "evaluate_candidates") as mock_eval, patch("app.sim.corridor_decision_engine.check_corridor_candidate") as mock_check, patch("os.path.exists", return_value=True):
        mock_check.return_value = SafetyCheckResult(passed=True, violations=[])
        safety = SafetyCheckResult(passed=True, violations=[])
        evals = [
            CorridorCandidateEvaluation(
                candidate_id=fixed_cands[0].candidate_id,
                junction_evaluations={},
                avg_queue_m=100,
                max_queue_m=150,
                avg_speed_kmh=10,
                total_halting_vehicles=20,
                evaluation_horizon_s=60,
                score=100,
                safety=safety,
                notes="HOLD baseline"
            ),
            CorridorCandidateEvaluation(
                candidate_id=fixed_cands[1].candidate_id,
                junction_evaluations={},
                avg_queue_m=50,  # 50% improvement
                max_queue_m=75,
                avg_speed_kmh=15,
                total_halting_vehicles=10,
                evaluation_horizon_s=60,
                score=50,
                safety=safety,
                notes="Cascade"
            )
        ]
        mock_eval.return_value = evals
        
        initial_count = len(store.list_pending())
        engine.process_corridor_state(dummy_corridor_state, "dummy.xml")
        
        pending = store.list_pending()
        assert len(pending) == initial_count + 1
        new_req = pending[-1]
        assert new_req.selected_candidate_id == fixed_cands[1].candidate_id
        assert new_req.is_corridor is True

def test_unsafe_evaluations_ignored_corridor(engine, dummy_corridor_state):
    fixed_cands = engine.generator.generate_corridor_candidates(dummy_corridor_state)
    with patch.object(engine.generator, "generate_corridor_candidates", return_value=fixed_cands), patch.object(engine.evaluator, "evaluate_candidates") as mock_eval, patch("app.sim.corridor_decision_engine.check_corridor_candidate") as mock_check, patch("os.path.exists", return_value=True):
        # We want candidate 1 to fail the safety gate
        def side_effect(cand):
            if cand.candidate_id == fixed_cands[0].candidate_id:
                return SafetyCheckResult(passed=True, violations=[])
            return SafetyCheckResult(passed=False, violations=["error"])
        mock_check.side_effect = side_effect
        
        safety_pass = SafetyCheckResult(passed=True, violations=[])
        
        evals = [
            CorridorCandidateEvaluation(
                candidate_id=fixed_cands[0].candidate_id, junction_evaluations={}, safety=safety_pass,
                avg_queue_m=100, max_queue_m=150, avg_speed_kmh=10, total_halting_vehicles=20,
                evaluation_horizon_s=60, score=100, notes="HOLD baseline"
            )
        ]
        mock_eval.return_value = evals
        
        initial_count = len(store.list_pending())
        engine.process_corridor_state(dummy_corridor_state, "dummy.xml")
        
        # Since candidate 1 was unsafe, only baseline was evaluated, so no recommendation made.
        assert len(store.list_pending()) == initial_count
