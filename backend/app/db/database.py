import json
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, Text, event
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import hashlib

DATABASE_URL = "sqlite:///./asteria.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, index=True)
    incident_name = Column(String)
    severity = Column(String)
    location = Column(String)
    affected_approach = Column(String)
    detected_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="New")
    assignee = Column(String, default="Unassigned")
    confidence = Column(Float)
    expected_in_s = Column(Integer)
    predicted_impact = Column(String)
    recommendation_text = Column(String)
    # Storing raw JSON string of the recommendation object
    raw_recommendation_json = Column(Text, nullable=True)

class OperatorLog(Base):
    __tablename__ = "operator_log"
    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    operator_id = Column(String)
    action = Column(String)
    resource_id = Column(String)
    location = Column(String)
    reason = Column(String)
    outcome = Column(String)
    audit_hash = Column(String)
    note = Column(Text, default="")
    recommendation_text = Column(Text, default="")
    # JSON string of safety checklist
    safety_validation = Column(Text, default="{}")

# SQLAlchemy event hooks to enforce immutability on operator_log
@event.listens_for(OperatorLog, 'before_update')
def receive_before_update(mapper, connection, target):
    raise Exception("OperatorLog table is append-only. UPDATE operations are forbidden.")

@event.listens_for(OperatorLog, 'before_delete')
def receive_before_delete(mapper, connection, target):
    raise Exception("OperatorLog table is append-only. DELETE operations are forbidden.")

class Device(Base):
    __tablename__ = "devices"
    id = Column(String, primary_key=True, index=True)
    type = Column(String)
    location = Column(String)
    status = Column(String)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    data_quality = Column(Float)
    uptime = Column(Float)

Base.metadata.create_all(bind=engine)
