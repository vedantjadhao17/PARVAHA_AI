"""PRAVAHA AI API. All telemetry and actions belong to a SUMO simulation."""
import asyncio
import copy
import hashlib
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import traci
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, OperatorLog
from app.models.recommendation_store import store
from app.sim.corridor_safety_gate import check_corridor_candidate
from app.sim.corridor_state import CorridorPlanCandidate
from app.sim.manager import SimulationManager
from app.sim.network_geometry import _GeoConverter, extract_network_geometry
from app.sim.safety_gate import check_candidate
from app.sim.traci_lock import traci_lock

project_dir = Path(__file__).resolve().parents[1]
sim_manager = SimulationManager(project_dir)
started_at = time.monotonic()
read_only = os.getenv("PRAVAHA_READ_ONLY", "1") != "0"


@asynccontextmanager
async def lifespan(app):
    if os.getenv("PRAVAHA_START_SIMULATION", "1") == "1":
        sim_manager.start(asyncio.get_running_loop())
    yield
    sim_manager.stop()


app = FastAPI(title="PRAVAHA AI — Simulation Prototype", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("PRAVAHA_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def get_db():
    with SessionLocal() as db:
        yield db


def require_operator(authorization: str | None = Header(default=None)):
    if read_only:
        raise HTTPException(403, "This showcase is read-only. Use the local operator demo to change signals.")
    token = os.getenv("PRAVAHA_OPERATOR_TOKEN")
    if token and not secrets.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(401, "An operator token is required.")


@app.get("/api/health")
def health():
    age = None if sim_manager.last_update_monotonic is None else time.monotonic() - sim_manager.last_update_monotonic
    return {
        "mode": "simulation", "read_only": read_only,
        "simulation_connected": sim_manager.is_running and age is not None and age < 5,
        "telemetry_age_s": None if age is None else round(age, 1),
        "model_loaded": sim_manager.forecaster.model is not None,
        "forecast_horizon_s": 60, "uptime_s": round(time.monotonic() - started_at),
        "scenario": sim_manager.sumocfg_path.name, "error": sim_manager.last_error,
    }


@app.websocket("/ws/corridor")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    sim_manager.subscribers.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sim_manager.subscribers.discard(websocket)


@app.get("/api/corridor/state")
def get_corridor_state():
    return sim_manager.state


@app.get("/api/alerts")
def get_alerts():
    # Historical alerts must not be presented as current incidents.
    return sim_manager.state.get("active_alerts", [])


def write_audit(db, req, action):
    timestamp = datetime.now(timezone.utc)
    log_id = str(uuid.uuid4())
    db.add(OperatorLog(
        id=log_id, timestamp=timestamp, operator_id="demo-operator", action=action,
        resource_id=req.recommendation_id, location="Simulated corridor",
        reason=f"Operator requested {action.lower()}.", outcome=req.status,
        audit_hash=hashlib.sha256(f"{log_id}|{timestamp.isoformat()}|{action}".encode()).hexdigest(),
        recommendation_text=req.operator_rationale,
        safety_validation=req.safety.model_dump_json(),
    ))
    db.commit()
    return log_id


def get_request(id, expected_status):
    req = store.get(id)
    if req is None:
        raise HTTPException(404, "Recommendation not found")
    if req.status != expected_status:
        raise HTTPException(409, f"Cannot perform action while status is {req.status}")
    return req


def apply_durations(plans):
    """Validate all junctions first; restore previous programs if a write fails."""
    previous, updated = {}, {}
    for tls_id, durations in plans.items():
        definitions = traci.trafficlight.getAllProgramLogics(tls_id)
        program = traci.trafficlight.getProgram(tls_id)
        logic = next((item for item in definitions if item.programID == program), None)
        if logic is None or len(logic.phases) != len(durations):
            raise ValueError(f"Signal program unavailable or changed for {tls_id}")
        previous[tls_id] = copy.deepcopy(logic)
        updated[tls_id] = copy.deepcopy(logic)
        for index, duration in durations.items():
            updated[tls_id].phases[int(index)].duration = duration
    written = []
    try:
        for tls_id, logic in updated.items():
            written.append(tls_id)
            traci.trafficlight.setProgramLogic(tls_id, logic)
    except Exception:
        for tls_id in written:
            traci.trafficlight.setProgramLogic(tls_id, previous[tls_id])
        raise
    return {tls: {i: phase.duration for i, phase in enumerate(logic.phases)} for tls, logic in previous.items()}


@app.post("/api/recommendations/{id}/approve", dependencies=[Depends(require_operator)])
def approve_recommendation(id: str, db: Session = Depends(get_db)):
    with traci_lock:
        req = get_request(id, "PENDING")
        age = (datetime.now(timezone.utc) - req.created_at).total_seconds()
        if age > 60:
            raise HTTPException(409, "Recommendation expired; wait for a fresh evaluation.")
        if not req.selected_candidates:
            raise HTTPException(409, "Recommendation contains no signal changes")
        if req.is_corridor:
            candidate = CorridorPlanCandidate(
                candidate_id=req.selected_candidate_id,
                junction_candidates={c.junction_id: c for c in req.proposal.candidates},
                changed_junctions=[c.junction_id for c in req.selected_candidates],
                generation_reason=req.operator_rationale,
            )
            safety = check_corridor_candidate(candidate)
        else:
            safety = check_candidate(req.selected_candidates[0])
        if not safety.passed:
            raise HTTPException(409, "; ".join(safety.violations))
        if any(store.has_active_intervention(c.tls_id) for c in req.selected_candidates):
            raise HTTPException(409, "Roll back the active plan before applying another")
        try:
            traci.switch("default")
            req.previous_phase_durations = apply_durations({c.tls_id: {p.phase_idx: p.duration for p in c.phase_specs} for c in req.selected_candidates})
        except Exception as exc:
            raise HTTPException(503, f"Signal application failed: {exc}") from exc
        store.update_status(id, "APPROVED")
        applied = store.update_status(id, "APPLIED")
        return {"status": "APPLIED", "log_id": write_audit(db, applied, "APPROVE")}


@app.post("/api/recommendations/{id}/reject", dependencies=[Depends(require_operator)])
def reject_recommendation(id: str, db: Session = Depends(get_db)):
    with traci_lock:
        get_request(id, "PENDING")
        req = store.update_status(id, "REJECTED")
        return {"status": req.status, "log_id": write_audit(db, req, "REJECT")}


@app.post("/api/recommendations/{id}/rollback", dependencies=[Depends(require_operator)])
def rollback_recommendation(id: str, db: Session = Depends(get_db)):
    with traci_lock:
        req = get_request(id, "APPLIED")
        if not req.previous_phase_durations:
            raise HTTPException(409, "No saved signal timings to restore")
        try:
            traci.switch("default")
            apply_durations(req.previous_phase_durations)
        except Exception as exc:
            raise HTTPException(503, f"Rollback failed: {exc}") from exc
        req = store.update_status(id, "ROLLED_BACK")
        return {"status": req.status, "log_id": write_audit(db, req, "ROLLBACK")}


@app.get("/api/analytics/trend")
def get_analytics_trend():
    return {"is_sample": False, "source": "SUMO simulation", "data": list(sim_manager.trend)}


@app.get("/api/operator-log")
def get_operator_log(db: Session = Depends(get_db)):
    logs = db.query(OperatorLog).order_by(OperatorLog.timestamp.desc()).limit(100).all()
    return [{"id": log.id, "operator_id": log.operator_id, "action": log.action,
             "resource_id": log.resource_id, "location": log.location, "reason": log.reason,
             "outcome": log.outcome, "audit_hash": log.audit_hash,
             "created_at": log.timestamp.isoformat() + "Z" if log.timestamp else None} for log in logs]


@app.get("/api/junctions/config")
def get_junction_config():
    return sim_manager.config


@app.get("/api/junction/camera/{junction_id}")
def get_camera(junction_id: str):
    junction = next((j for j in sim_manager.config["junctions"] if j["junction_id"] == junction_id), None)
    if junction is None:
        raise HTTPException(404, "Unknown junction")
    camera = dict(junction["camera"])
    camera["lon"], camera["lat"] = _GeoConverter(sim_manager._net).convert(camera["x"], camera["y"])
    return camera


@app.get("/api/network/geometry")
def get_network_geometry():
    return extract_network_geometry(str(sim_manager.net_path))


@app.get("/api/evaluation/summary")
def get_evaluation_summary():
    metadata = json.loads((project_dir / "ml/models/model_metadata.json").read_text())
    return {"source": "Stored historical benchmark; not live traffic performance",
            "offline_model": metadata, "traffic_reduction_validated": False,
            "recommendations": {"total": store.count()}, "status": "simulation_only"}


frontend_dist = project_dir.parent / "frontend/dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def dashboard(path: str):
        if path.startswith(("api/", "ws/")):
            raise HTTPException(404, "Endpoint not found")
        return FileResponse(frontend_dist / "index.html")
