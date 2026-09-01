import pytest
import json
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.db.database import Base, OperatorLog, Alert
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app, get_db

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield session
    session.close()

def test_operator_log_immutability(db_session):
    # Insert a log
    log = OperatorLog(
        id="LOG-123",
        operator_id="Op1",
        action="APPROVE",
        resource_id="REC-1",
        location="Northgate",
        reason="Test",
        outcome="Test",
        audit_hash="hash",
        safety_validation="{}"
    )
    db_session.add(log)
    db_session.commit()

    # Attempt to UPDATE
    log_to_update = db_session.query(OperatorLog).first()
    log_to_update.reason = "Hacked"
    with pytest.raises(Exception):
        db_session.commit()
        
    db_session.rollback()

    # Attempt to DELETE
    with pytest.raises(Exception):
        db_session.delete(log_to_update)
        db_session.commit()

def test_safety_gate_rejection(db_session):
    client = TestClient(app)
    
    # Override get_db
    app.dependency_overrides[get_db] = lambda: db_session
    
    # Create an alert with an UNSAFE plan
    unsafe_plan = {
        "plan_id": "unsafe",
        "junction_actions": [
            {"junction_id": "J1_SAN", "phase_id": 0, "action_type": "hold", "target_timing": 1, "timing_delta": -20, "duration_horizon": 60}
        ]
    }
    
    alert = Alert(
        id="ALT-123",
        location="J1_SAN",
        severity="CRITICAL",
        recommendation_text="Test",
        raw_recommendation_json=json.dumps(unsafe_plan),
        status="New"
    )
    db_session.add(alert)
    db_session.commit()
    
    # Execute approve - should fail with 409
    response = client.post(f"/api/recommendations/{alert.id}/approve")
    
    assert response.status_code == 409
    assert "Safety violation detected" in response.json()["detail"]
