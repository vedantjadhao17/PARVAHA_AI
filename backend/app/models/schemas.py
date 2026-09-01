from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime

class JunctionAction(BaseModel):
    junction_id: str
    phase_id: int
    action_type: str
    target_timing: int
    timing_delta: int
    duration_horizon: int

class SignalPlan(BaseModel):
    plan_id: str
    generated_at_s: float
    junction_actions: List[JunctionAction]
    reason_code: str
    source_alert_ids: List[str]

class SafetyResult(BaseModel):
    passed: bool
    reasons: List[str]

class CandidateResult(BaseModel):
    candidate_id: str
    safety: SafetyResult
    simulation_start_state: str
    horizon_s: int
    person_delay: float
    spillback_events: int
    max_queue: float
    p95_travel_time: float
    reason_code: str
    ambulance_transit_time: Optional[float] = None
    recovery_cost: Optional[float] = None

class Recommendation(BaseModel):
    recommendation_id: str
    generated_at_s: float
    confidence: str
    selected_plan: SignalPlan
    reason_codes: List[str]
    predicted_delta: Dict[str, float]
    safety: SafetyResult
    fallback_plan: SignalPlan
    candidate_results: List[CandidateResult]
    rejected_candidate_reasons: Dict[str, str]
    state_version: str

# API Specific Models
class BaseAPIResponse(BaseModel):
    is_sample: bool = False

class AlertSchema(BaseAPIResponse):
    id: str
    incident_name: str
    severity: str
    location: str
    affected_approach: str
    detected_time: str
    status: str
    assignee: str
    confidence: float
    expected_in_s: int
    predicted_impact: str
    recommendation_text: str

class OperatorLogSchema(BaseAPIResponse):
    id: str
    timestamp: datetime
    operator_id: str
    action: str
    resource_id: str
    location: str
    reason: str
    outcome: str
    audit_hash: str
    note: str = ""
    recommendation_text: str = ""
    safety_validation: Dict[str, bool] = {}

class DeviceSchema(BaseAPIResponse):
    id: str
    type: str
    location: str
    status: str
    last_heartbeat: str
    data_quality: float
    uptime: float

class JunctionSchema(BaseAPIResponse):
    id: str
    name: str
    status: str
    active_vehicles: int
    queue: int
    avg_wait: int
    avg_speed: int
    signal_phase: str
    controller_online: bool
    last_update: str

