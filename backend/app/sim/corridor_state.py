from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import uuid

from app.sim.signal_plan import SourceState, SignalPlanCandidate, CandidateEvaluation

class CorridorJunctionState(BaseModel):
    junction_id: str
    tls_id: str
    queue_length_m: float
    predicted_queue_length_m: float
    capacity_m: float
    predicted_capacity_ratio: float
    vehicle_count: int
    avg_speed_kmh: float
    risk_level: str
    current_phase: Optional[int] = None
    phase_remaining_s: Optional[float] = None
    timestamp: float

class CorridorState(BaseModel):
    corridor_id: str
    timestamp: float
    junctions: Dict[str, CorridorJunctionState]
    upstream_downstream_relationships: Dict[str, str] # e.g. {"J1": "J2", "J2": "J3"}
    total_queue_m: float
    max_predicted_capacity_ratio: float
    critical_junction_id: str
    corridor_risk: str
    active_interventions: List[str]

class CorridorPlanCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    junction_candidates: Dict[str, SignalPlanCandidate] # junction_id -> candidate
    changed_junctions: List[str]
    generation_reason: str
    
class CorridorCandidateEvaluation(BaseModel):
    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: str
    avg_queue_m: float
    max_queue_m: float
    total_halting_vehicles: int
    avg_speed_kmh: float
    junction_evaluations: Dict[str, CandidateEvaluation] # junction_id -> eval
    score: float
    notes: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    safety: Optional[Any] = None
    evaluation_horizon_s: int

