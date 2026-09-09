# PHASE 7 IMPLEMENTATION PLAN

## 1. Current Frontend Architecture
- The frontend is a React application (Vite) structured with a main layout (`App.tsx`), `Sidebar`, and `Topbar`.
- Real-time updates are handled via `WebSocketContext.tsx` which parses JSON from `ws://localhost:8000/ws/corridor`.
- The live dashboard uses `react-leaflet` to render a map in `LeafletLiveMap.tsx`. It natively binds to the `useWebSocket` state for vehicles and junction metrics.

## 2. Current Backend Architecture
- FastAPI serves API routes (`main.py`) and WebSockets.
- `SimulationManager` manages SUMO execution, reading telemetry continuously and writing it to `self.state`.
- `_GeoConverter` in `network_geometry.py` correctly maps SUMO coordinate frames (UTM Zone 43N) to Lat/Lon for the browser map.
- Machine learning models (XGBoost) and `CorridorDecisionEngine` plug synchronously into the simulation loop.

## 3. Existing API Endpoints
- `GET /api/corridor/state` (pollable backend state)
- `GET /api/alerts`
- `GET /api/corridor/recommendations` (Fetches pending corridor plans)
- `POST /api/recommendations/{id}/approve`
- `POST /api/recommendations/{id}/rollback`
- `GET /api/evaluation/summary` (Post-intervention OutcomeTracker stats)

## 4. Existing WebSocket/Live Telemetry Mechanisms
- `sim_manager._broadcast_state()` efficiently propagates real-time JSON dictionary over `ws://localhost:8000/ws/corridor` continuously.

## 5. Existing SUMO/TraCI Lifecycle
- Unchanged. SUMO runs effectively, steps gracefully, saves states dynamically for counterfactual generation, and manages traffic flow cleanly inside a background Thread.

## 6. Existing Dashboard Components
- Pre-built structural layout (`App.tsx`, `CommandMap.tsx`).
- Several empty or partially-wired components: `RecommendationPanel.tsx`, `SimFeedPanel.tsx`.
- The `LeafletLiveMap.tsx` component is partially written but depends on a non-existent `/api/network/geometry` endpoint.

## 7. Existing State Models / Contracts
- `sim_manager.state` correctly contains `vehicles` (id, x, y, speed), `junctions` (queue lengths, forecast, alerts), `time_s`.
- The state currently **misses real-time traffic signal states** (red, green, yellow).

## 8. Existing Recommendation Workflow
- Decision engine saves `SignalPlanCandidate` into `store.py`. The `/api/corridor/recommendations` retrieves them. Approval is fully protected by `SafetyGate`.

## 9. Existing Outcome/Rollback Workflow
- DB handles storage of outcomes `OutcomeTracker`, rollback endpoint exists and executes TraCI operations on previously applied plans.

## 10. Existing Phase 6 Artifacts Relevant to Dashboard
- ML Model (`queue_forecast_model.json`). We'll present its precise outputs (queue_m) as explicitly confirmed in Phase 6 without fake enhancements.

## 11. What can be reused
- We will reuse the complete Phase 1-6 architecture. The FastAPI, ML engines, and TraCI simulation manager will remain the exact source of truth. NO autonomous changes will be injected.

## 12. What must be modified
- `backend/app/sim/manager.py`:
  - Enhance `_update_junctions` to extract `signal_state` dynamically from TraCI.
  - Expose `NO_SAFE_CHANGE` and Safety Rejections explicitly so the dashboard can render them.
- `backend/app/main.py`:
  - Expose `GET /api/network/geometry` utilizing `backend/app/sim/network_geometry.py` so the `react-leaflet` map receives road shapes.
- `frontend/src/context/WebSocketContext.tsx`:
  - Ensure `CorridorState` strictly defines all UI-bound props matching Python's dict export.

## 13. What must be newly created
- Wire the React `SimFeedPanel.tsx` to read natively from the WebSocket context to populate Top KPIs (Corridor Queue, Halting, Speed, Risk).
- Complete `RecommendationPanel.tsx` and integrate the Counterfactual evidence view, NO_SAFE_CHANGE view, and Safety Rejection view exactly as requested by Phase 7 specs.
- Update `CommandMap.tsx` UI to ensure the requested Command Center dark aesthetic is maintained.
- Live Simulation Controls via safe API routes if necessary (`GET /api/status`).

## 14. Exact files expected to change
- `backend/app/main.py`
- `backend/app/sim/manager.py`
- `frontend/src/context/WebSocketContext.tsx`
- `frontend/src/components/LeafletLiveMap.tsx`
- `frontend/src/components/RecommendationPanel.tsx`
- `frontend/src/components/SimFeedPanel.tsx`
- `frontend/src/pages/CommandMap.tsx`
- `frontend/src/pages/Alerts.tsx`

## 15. Risks
- *Visualization Performance*: High vehicle counts might lag the Leaflet SVG/Canvas layer if rendered naively. We will use `useMemo` and rely on delta tracking for vehicle circle markers.
- *Coordinate Alignment*: Accurate alignment relies on UTM->WGS84. `_GeoConverter` relies on precise center points. We will map all vehicle X/Y coords inside Python to offload client execution if they aren't already.

## 16. Testing strategy
- **Launch Phase 7 Smoke Test**: Restart backend. Launch Vite frontend.
- **Visual Validation**: Watch `LeafletLiveMap` draw actual network geometry and properly place actual moving circle markers.
- **Stress Test**: Allow traffic to accumulate queue; observe `RecommendationPanel` populate.
- **Safety Test**: Click `Approve` and verify TraCI execution occurs without autonomous override, and rollback functions correctly. 
- **Resilience Test**: Test WebSocket reconnect logic (stop and restart backend). Ensure the UI displays "CONNECTION LOST" cleanly.

## 17. How live SUMO state will reach the browser
- `SUMO -> TraCI -> sim_manager._update_vehicles() + _update_junctions() -> Python Dictionary -> _broadcast_state (JSON) -> FastAPI WS -> ws://localhost:8000/ws/corridor -> React WebSocketContext -> Context Provider -> Leaflet components re-render`.
