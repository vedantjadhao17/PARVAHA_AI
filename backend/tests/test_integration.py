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
