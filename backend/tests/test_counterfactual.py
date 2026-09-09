import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.sim.counterfactual import CounterfactualEvaluator
from app.sim.signal_plan import SignalPlanCandidate, SafetyCheckResult

@pytest.fixture
def evaluator():
    return CounterfactualEvaluator(sumocfg_path=Path("dummy.sumocfg"))

@pytest.fixture
def dummy_candidate():
    return SignalPlanCandidate.from_baseline(
        tls_id="cluster_13546492148_1838721956",
        junction_id="J1_SAN",
        rationale="HOLD"
    )

def test_unsafe_candidate_skipped(evaluator, dummy_candidate):
    with patch("app.sim.counterfactual.check_candidate") as mock_check:
        mock_check.return_value = SafetyCheckResult(passed=False, violations=["test violation"])
        evaluations = evaluator.evaluate_candidates([dummy_candidate], "dummy.xml")
        assert len(evaluations) == 0

@patch("app.sim.counterfactual.traci")
@patch("app.sim.counterfactual.BaselineController")
def test_safe_candidate_evaluated(mock_controller_cls, mock_traci, evaluator, dummy_candidate):
    with patch("app.sim.counterfactual.check_candidate") as mock_check:
        mock_check.return_value = SafetyCheckResult(passed=True, violations=[])
        
        mock_conn = MagicMock()
        mock_traci.getConnection.return_value = mock_conn
        
        # Simulate time advancing to end the loop immediately
        mock_conn.simulation.getTime.side_effect = [0.0, 61.0]
        
        mock_conn.trafficlight.getControlledLanes.return_value = ["lane1"]
        mock_conn.lane.getLastStepHaltingNumber.return_value = 2
        
        evaluations = evaluator.evaluate_candidates([dummy_candidate], "dummy.xml")
        assert len(evaluations) == 1
        
        # Ensure we called traci.start with label
        assert mock_traci.start.called
        call_args = mock_traci.start.call_args[1]
        assert "label" in call_args
        assert call_args["label"].startswith("cf_")
        
        # Ensure we closed the connection
        assert mock_conn.close.called

@patch("app.sim.counterfactual.traci")
def test_evaluation_failure_handled(mock_traci, evaluator, dummy_candidate):
    with patch("app.sim.counterfactual.check_candidate") as mock_check:
        mock_check.return_value = SafetyCheckResult(passed=True, violations=[])
        
        mock_traci.start.side_effect = Exception("SUMO crashed")
        
        evaluations = evaluator.evaluate_candidates([dummy_candidate], "dummy.xml")
        assert len(evaluations) == 0
