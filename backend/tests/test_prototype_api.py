from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.db.database import Base, OperatorLog
from app.models.recommendation_store import store
from app.sim.signal_plan import SignalPlanCandidate, SignalPlanProposal, ApprovalRequest, SafetyCheckResult


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    main.app.dependency_overrides[main.get_db] = lambda: session
    store._records.clear()
    monkeypatch.setattr(main, "read_only", False)
    monkeypatch.delenv("PRAVAHA_OPERATOR_TOKEN", raising=False)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()
    store._records.clear()
    session.close()
    engine.dispose()


def request():
    candidate = SignalPlanCandidate.with_green_shift(
        "cluster_13546492148_1838721956", "J1_SAN", 0, 2, 5.0,
    )
    req = ApprovalRequest(
        trigger_reason="test", source_states=[],
        proposal=SignalPlanProposal(candidates=[candidate], source_states=[], trigger_reason="test"),
        evaluations=[], selected_candidate_id=candidate.candidate_id,
        rollback_candidates=[], safety=SafetyCheckResult(passed=True),
        operator_rationale="Simulation test",
    )
    store.add(req)
    return req


def test_log_endpoint_uses_timestamp(client):
    db = main.app.dependency_overrides[main.get_db]()
    db.add(OperatorLog(id="log-1", action="REJECT", timestamp=datetime(2026, 1, 1), resource_id="rec"))
    db.commit()
    result = client.get("/api/operator-log")
    assert result.status_code == 200
    assert result.json()[0]["created_at"] == "2026-01-01T00:00:00Z"


def test_routes_have_no_duplicates():
    routes = [(route.path, method) for route in main.app.routes for method in getattr(route, "methods", [])]
    assert len(routes) == len(set(routes))


def test_showcase_rejects_mutations(client, monkeypatch):
    monkeypatch.setattr(main, "read_only", True)
    for action in ("approve", "reject", "rollback"):
        assert client.post(f"/api/recommendations/example/{action}").status_code == 403


def test_config_geometry_and_camera_work_without_personal_paths(client):
    assert client.get("/api/junctions/config").json()["prediction_horizon_s"] == 60
    camera = client.get("/api/junction/camera/J1_SAN")
    assert camera.status_code == 200
    assert 18 < camera.json()["lat"] < 19
    assert client.get("/api/junction/camera/unknown").status_code == 404
    assert client.get("/api/network/geometry").status_code == 200


def test_analytics_uses_observed_history(client, monkeypatch):
    monkeypatch.setattr(main.sim_manager, "trend", [{"time": "5s", "speed": 12, "queue": 15}])
    payload = client.get("/api/analytics/trend").json()
    assert payload["is_sample"] is False
    assert payload["data"][0]["queue"] == 15


def test_approval_failure_does_not_claim_applied(client, monkeypatch):
    req = request()
    monkeypatch.setattr(main.traci, "switch", lambda _: None)
    monkeypatch.setattr(main, "apply_durations", MagicMock(side_effect=RuntimeError("Disconnected")))
    response = client.post(f"/api/recommendations/{req.recommendation_id}/approve")
    assert response.status_code == 503
    assert store.get(req.recommendation_id).status == "PENDING"


def test_approve_and_rollback_restore_captured_timings(client, monkeypatch):
    req = request()
    monkeypatch.setattr(main.traci, "switch", lambda _: None)
    previous = {req.selected_candidate.tls_id: {0: 37, 1: 6, 2: 41, 3: 6}}
    apply = MagicMock(return_value=previous)
    monkeypatch.setattr(main, "apply_durations", apply)
    assert client.post(f"/api/recommendations/{req.recommendation_id}/approve").json()["status"] == "APPLIED"
    # Green deltas alone omit yellow phases and cannot define a full program.
    candidate = req.selected_candidate
    assert apply.call_args.args[0][candidate.tls_id] == {
        phase.phase_idx: phase.duration for phase in candidate.phase_specs
    }
    assert client.post(f"/api/recommendations/{req.recommendation_id}/approve").status_code == 409
    assert client.post(f"/api/recommendations/{req.recommendation_id}/rollback").json()["status"] == "ROLLED_BACK"
    assert apply.call_args.args[0] == previous
    assert len(client.get("/api/operator-log").json()) == 2


def test_expired_requests_are_not_offered(client):
    req = request()
    req.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    assert client.post(f"/api/recommendations/{req.recommendation_id}/approve").status_code == 409
    assert store.list_pending() == []
    assert store.get(req.recommendation_id).status == "EXPIRED"


def test_reset_invalidates_old_run_requests(client):
    req = request()
    store.end_simulation_run()
    assert store.get(req.recommendation_id).status == "EXPIRED"


def test_partial_application_restores_written_programs(monkeypatch):
    logic = SimpleNamespace(programID="0", phases=[SimpleNamespace(duration=39)])
    tls = MagicMock()
    tls.getAllProgramLogics.return_value = [logic]
    tls.getProgram.return_value = "0"
    tls.setProgramLogic.side_effect = [None, RuntimeError("write failed"), None, None]
    monkeypatch.setattr(main.traci, "trafficlight", tls)
    with pytest.raises(RuntimeError):
        main.apply_durations({"first": {0: 44}, "second": {0: 34}})
    assert tls.setProgramLogic.call_count == 4
    assert tls.setProgramLogic.call_args_list[-1].args[1].phases[0].duration == 39
