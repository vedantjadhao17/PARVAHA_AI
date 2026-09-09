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
