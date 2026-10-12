from unittest.mock import MagicMock

import pytest
from app.sim import corridor_counterfactual as module
from app.sim.corridor_state import CorridorPlanCandidate
from app.sim.signal_plan import SignalPlanCandidate


@pytest.mark.parametrize("failure", ["program", "telemetry"])
def test_failed_counterfactual_never_becomes_zero_queue_success(monkeypatch, tmp_path, failure):
    candidate = SignalPlanCandidate.with_green_shift("cluster_13546492148_1838721956", "J1_SAN", 0, 2, 5)
    corridor = CorridorPlanCandidate(
        junction_candidates={"J1_SAN": candidate},
        changed_junctions=["J1_SAN"], generation_reason="Test",
    )
    connection = MagicMock()
    connection.trafficlight.getProgram.return_value = "0"
    logic = MagicMock(programID="0")
    logic.phases = [MagicMock(duration=p.duration) for p in candidate.phase_specs]
    connection.trafficlight.getAllProgramLogics.return_value = [logic]
    if failure == "program":
        connection.trafficlight.setProgramLogic.side_effect = RuntimeError("Write failed")
    else:
        connection.trafficlight.getControlledLanes.side_effect = RuntimeError("Telemetry failed")
    monkeypatch.setattr(module.traci, "start", lambda *a, **kw: None)
    monkeypatch.setattr(module.traci, "switch", lambda *a: None)
    monkeypatch.setattr(module.traci, "getConnection", lambda *a: connection)
    state = tmp_path / "state.xml"
    state.touch()
    results = module.CorridorCounterfactualEvaluator("test.sumocfg", 1).evaluate_candidates([corridor], str(state))
    assert results == []
    connection.close.assert_called()
