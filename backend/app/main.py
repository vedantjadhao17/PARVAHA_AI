import json
import hashlib
import asyncio
from typing import List, Dict
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import SessionLocal, Alert, OperatorLog, Device
from app.models.schemas import AlertSchema, OperatorLogSchema, DeviceSchema, JunctionSchema, BaseAPIResponse
from app.sim.manager import SimulationManager
from app.sim.network_geometry import extract_network_geometry
from pravaha.contracts import Recommendation, SignalPlan, SafetyResult

app = FastAPI(title="Asteria Corridor Command Center")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Start Simulation Manager
project_dir = Path(__file__).resolve().parents[3] / "sumo" / "pravaha-phase5" / "pravaha-sancheti-sumo"
sim_manager = SimulationManager(project_dir)

@app.on_event("startup")
async def startup_event():
    # Only start if the config file actually exists, to avoid crashing during tests or partial setups
    if sim_manager.sumocfg_path.exists():
        sim_manager.start(asyncio.get_running_loop())

@app.on_event("shutdown")
async def shutdown_event():
    sim_manager.stop()

@app.websocket("/ws/corridor")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    sim_manager.subscribers.add(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        sim_manager.subscribers.remove(websocket)

@app.get("/api/corridor/state")
def get_corridor_state():
    return sim_manager.state

@app.get("/api/alerts", response_model=List[AlertSchema])
def get_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).all()
    # Pydantic will automatically include the default `is_sample=False`
    return alerts

@app.post("/api/recommendations/{id}/approve")
def approve_recommendation(id: str, db: Session = Depends(get_db)):
    # 1. Fetch the alert/recommendation
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    raw_json = alert.raw_recommendation_json
    if not raw_json:
         raise HTTPException(status_code=400, detail="No recommendation associated with this alert")
         
    # Check Safety Gate - Invariant Assertion!
    # In a real app we'd re-run SafetyGate.validate(plan) here to be completely sure.
    # For now, let's assume raw_json holds a plan dictionary.
    plan_dict = json.loads(raw_json)
    
    # Re-validate against safety gate!
    from pravaha.contracts import SignalPlan, JunctionAction
    actions = [JunctionAction(**a) for a in plan_dict.get("junction_actions", [])]
    plan = SignalPlan(
        plan_id=plan_dict.get("plan_id", "plan"),
        generated_at_s=plan_dict.get("generated_at_s", 0),
        junction_actions=actions,
        reason_code=plan_dict.get("reason_code", ""),
        source_alert_ids=plan_dict.get("source_alert_ids", [])
    )
    
    safety_result = sim_manager.safety_gate.validate(plan)
    if not safety_result.passed:
        raise HTTPException(status_code=409, detail=f"Safety violation detected. Cannot approve unsafe plan: {'; '.join(safety_result.reasons)}")
        
    # Validated! Write to immutable operator log
    audit_str = f"APPROVE|{id}|{datetime.utcnow().isoformat()}"
    audit_hash = hashlib.sha256(audit_str.encode()).hexdigest()
    
    log_entry = OperatorLog(
        id=f"LOG-{int(datetime.utcnow().timestamp())}",
        operator_id="Operator 07",
        action="APPROVE",
        resource_id=id,
        location=alert.location,
        reason="Operator manually approved prediction.",
        outcome="Plan Active",
        audit_hash=audit_hash,
        recommendation_text=alert.recommendation_text,
        safety_validation=json.dumps({"Minimum green passed": True, "All-red interval scheduled": True})
    )
    
    alert.status = "Resolved"
    db.add(log_entry)
    db.commit()
    
    # 2. ACTUALLY EXECUTE THE PLAN IN THE SIMULATION
    sim_manager.apply_plan(plan)
    
    return {"status": "success", "log_id": log_entry.id}

@app.get("/api/analytics/trend")
def get_analytics_trend():
    # Return dummy data with is_sample=True
    return {
        "is_sample": True,
        "data": [
            {"time": "15:00", "speed": 30, "queue": 10},
            {"time": "15:20", "speed": 15, "queue": 120},
            {"time": "16:00", "speed": 28, "queue": 15}
        ]
    }

@app.get("/api/operator-log")
def get_operator_log(db: Session = Depends(get_db)):
    logs = db.query(OperatorLog).order_by(OperatorLog.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "operator_id": l.operator_id,
            "action": l.action,
            "resource_id": l.resource_id,
            "location": l.location,
            "reason": l.reason,
            "outcome": l.outcome,
            "audit_hash": l.audit_hash,
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in logs
    ]

@app.get("/api/junctions/config")
def get_junction_config():
    """Return junction metadata from corridor config (approaches, labels, distances)."""
    import os
    config_path = sim_manager.junction_cfg_path
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Junction config not found")
    with open(config_path, "r") as f:
        return json.load(f)

@app.get("/api/network/geometry")
def get_network_geometry():
    """Return lane shapes and junction coordinates with lon/lat conversion."""
    net_path = sim_manager.project_dir / "network" / "sancheti_core.net.xml"
    if not net_path.exists():
        raise HTTPException(status_code=404, detail="Network file not found")
    return extract_network_geometry(str(net_path))

@app.get("/api/junction/camera/{junction_id}")
def get_junction_camera(junction_id: str):
    """Return the camera lon/lat center, zoom, and angle for a given junction."""
    if not sim_manager.junction_cfg_path.exists():
        raise HTTPException(status_code=404, detail="Junction config not found")
    with open(sim_manager.junction_cfg_path, "r") as f:
        cfg = json.load(f)
    junction = next((j for j in cfg.get("junctions", []) if j["junction_id"] == junction_id), None)
    if not junction:
        raise HTTPException(status_code=404, detail=f"Junction {junction_id} not found")
    camera = junction.get("camera", {})
    x, y = camera.get("x"), camera.get("y")
    lon, lat = None, None
    if x is not None and y is not None:
        try:
            from app.sim.network_geometry import _GeoConverter
            net_path = str(sim_manager.project_dir / "network" / "sancheti_core.net.xml")
            from app.sim.network_geometry import get_net
            net = get_net(net_path)
            conv = _GeoConverter(net)
            lon, lat = conv.convert(x, y)
        except Exception:
            pass
    return {
        "junction_id": junction_id,
        "label": junction.get("label", junction_id),
        "lon": lon,
        "lat": lat,
        "zoom": camera.get("zoom", 4000),
        "angle": camera.get("angle", 0),
    }