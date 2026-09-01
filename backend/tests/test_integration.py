import pytest
import json
import time
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from app.db.database import Base, OperatorLog, Alert
from app.sim.manager import SimulationManager
from app.main import app, get_db, sim_manager
from fastapi.testclient import TestClient
import traci

@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield session
    session.close()

def test_approve_apply_integration(db_session):
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session
    
    traci.start([
        "sumo", "-c", str(sim_manager.sumocfg_path),
        "--step-length", "0.5", "--no-warnings"
    ])
    
    try:
        traci.simulationStep()
        tls_id = "cluster_13546492148_1838721956"
        initial_phase = traci.trafficlight.getPhase(tls_id)
        
        target_phase = 2 if initial_phase != 2 else 0
        safe_plan = {
            "plan_id": "safe_integration",
            "junction_actions": [
                {"junction_id": "J1_SAN", "phase_id": target_phase, "action_type": "hold", "target_timing": 40, "timing_delta": 0, "duration_horizon": 60}
            ]
        }
        
        alert = Alert(
            id="ALT-INT",
            location="J1_SAN",
            severity="CRITICAL",
            recommendation_text="Test",
            raw_recommendation_json=json.dumps(safe_plan),
            status="New"
        )
        db_session.add(alert)
        db_session.commit()
        
        # Approve
        response = client.post(f"/api/recommendations/{alert.id}/approve")
        assert response.status_code == 200, response.json()
        assert sim_manager.pending_plan is not None
        
        # Fast forward
        for _ in range(20):
            traci.simulationStep()
            sim_manager._execute_plan(sim_manager.pending_plan)
            if sim_manager.pending_plan is None:
                # Mock the clearing in real life (the loop normally clears it on success)
                # but wait, the loop clears it. Here we manually clear it if _execute_plan returned True.
                # Actually _execute_plan in my new patch returns True on success and doesn't clear it!
                # The caller in manager clears it! So I need to simulate that.
                pass
            
            # check the actual caller logic:
            success = sim_manager._execute_plan(sim_manager.pending_plan)
            if success:
                sim_manager.pending_plan = None
                break
                
        final_phase = traci.trafficlight.getPhase(tls_id)
        assert final_phase == target_phase, f"Phase {target_phase} not applied, current is {final_phase}"
    finally:
        traci.close()
