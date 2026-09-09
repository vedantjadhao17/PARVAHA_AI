import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.recommendation_store import store
from app.sim.signal_plan import ApprovalRequest, SignalPlanProposal
from datetime import datetime, timezone
import uuid
import os

client = TestClient(app)

def setup_function():
    store._records.clear()

def test_api_evaluation_summary():
    # Insert a dummy record to make sure len(store._records) works
    req = ApprovalRequest(
        recommendation_id="test1",
        trigger_reason="test",
        source_states=[],
        proposal=SignalPlanProposal(candidates=[], source_states=[], trigger_reason="test", is_no_op=False),
        evaluations=[],
        selected_candidate_id="cand1",
        rollback_candidates=[],
        safety={"passed": True, "reasons": []},
        operator_rationale="test"
    )
    store.add(req)
    response = client.get("/api/evaluation/summary")
    assert response.status_code == 200
    assert "status" in response.json() # Could be 'insufficient_data' but it shouldn't 500

def test_approve_reject_rollback_store_methods():
    req = ApprovalRequest(
        recommendation_id="test-req-1",
        trigger_reason="test",
        source_states=[],
        proposal=SignalPlanProposal(candidates=[], source_states=[], trigger_reason="test", is_no_op=False),
        evaluations=[],
        selected_candidate_id="cand1",
        rollback_candidates=[],
        safety={"passed": True, "reasons": []},
        operator_rationale="test",
        status="PENDING"
    )
    store.add(req)
    # Since we can't easily test the full endpoint due to SUMO/DB dependencies in this environment,
    # we'll verify the status updates work properly without raising AttributeError.
    store.update_status("test-req-1", "APPROVED")
    assert store.get("test-req-1").status == "APPROVED"
    
    store.update_status("test-req-1", "APPLIED")
    assert store.get("test-req-1").status == "APPLIED"

    store.update_status("test-req-1", "ROLLED_BACK")
    assert store.get("test-req-1").status == "ROLLED_BACK"
    
    store._records.clear()
    store.add(req.model_copy(update={"status": "PENDING"}))
    store.update_status("test-req-1", "REJECTED")
    assert store.get("test-req-1").status == "REJECTED"


from app.sim.corridor_decision_engine import CorridorDecisionEngine
from app.sim.corridor_state import CorridorState, CorridorJunctionState

def test_pending_guard_behavior(monkeypatch):
    import os
    engine = CorridorDecisionEngine("dummy.sumocfg")
    
    # Mock os.path.exists so it doesn't return early for state_file
    monkeypatch.setattr(os.path, "exists", lambda x: True)
    
    # Mock generator so we can spy on whether it gets called
    call_count = 0
    def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return [] # Return empty to abort early after generating
    engine.generator.generate_corridor_candidates = mock_generate
    
    store._records.clear()
    
    state = CorridorState(
        corridor_id="test",
        timestamp=0,
        junctions={},
        upstream_downstream_relationships={},
        total_queue_m=0,
        max_predicted_capacity_ratio=1.0,
        critical_junction_id="",
        corridor_risk="HIGH",
        active_interventions=[]
    )
    
    # 1. No PENDING recommendation exists, HIGH risk -> should call generate (call_count becomes 1)
    engine.process_corridor_state(state, "dummy.xml")
    assert call_count == 1, "Should generate candidates when no pending recommendations exist"
    
    # 2. Add a PENDING recommendation
    req = ApprovalRequest(
        recommendation_id="test2",
        trigger_reason="test",
        source_states=[],
        proposal=SignalPlanProposal(candidates=[], source_states=[], trigger_reason="test", is_no_op=False),
        evaluations=[],
        selected_candidate_id="cand1",
        rollback_candidates=[],
        safety={"passed": True, "reasons": []},
        operator_rationale="test",
        status="PENDING"
    )
    store.add(req)
    
    # 3. PENDING exists, HIGH risk -> should return early, call_count remains 1
    engine.process_corridor_state(state, "dummy.xml")
    assert call_count == 1, "Should skip generating candidates when a pending recommendation exists"

