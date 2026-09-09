# Phase 8 Correctness Audit: Live Telemetry Freeze

## 1. Root Cause
The live dashboard telemetry (queue, speed, raw signal state, and forecast) was frozen due to an `UnboundLocalError` inside the backend `SimulationManager._update_junctions()` method. 
Specifically, the Python `import traci` statement was improperly placed inside a conditional block at the very end of `_update_junctions()` (during the corridor decision engine trigger setup). In Python, importing a module inside a method shadows the global module reference and statically marks the variable as local for the *entire* scope of the method.
When the upper lines of the method attempted to execute `traci.trafficlight.getRedYellowGreenState(tls_id)`, it threw an `UnboundLocalError`, causing the `try/except` block to abort before any physical halting or speed data was queried.

## 2. Exact Defective File/Function
- **File**: `backend/app/sim/manager.py`
- **Function**: `SimulationManager._update_junctions()`

## 3. Why Values Were Frozen
Because the query aborted, the loop continuously injected `queue_m = 0.0`, `halting_vehicles = 0`, and `junction_speeds = []` into the WebSocket payload. 

## 4. Minimal Patch
Removed the localized `import traci`, `import tempfile`, and `import threading` lines from inside the method body. Restored them as standard module-level imports at the top of `backend/app/sim/manager.py`.

## 5. Data Provenance

### Current Queue
Derived natively using:
`traci.lane.getLastStepHaltingNumber(lane) * 5.0m`. Retained existing semantics. Label updated to `EST. QUEUE`.

### Average Speed
The backend extracts raw lane-level speeds via `traci.vehicle.getSpeed()`.
*Bug fixed*: The frontend previously contained a hardcoded fallback formula: `const speed = Math.max(5, 45 - queueM / 15);`. This was deleted. The dashboard now reads `_junction_avg_speed_kmh` natively from the WebSocket and gracefully falls back to `N/A` if no vehicles are actively moving.

### Forecast +60s
The pipeline retains the canonical 8-feature `QueueForecaster` XGBoost execution. Because the core `_update_junctions` loop is no longer crashing, the 20-second historical sliding window (`self.history_buffer`) now successfully populates with new queue data on every tick, proving live forecast adaptation. The `LiveFeatureExtractor` (42-features) remains unused and safely quarantined.

### Raw Signal State
Retrieved natively via `traci.trafficlight.getRedYellowGreenState(tls_id)`. With the `UnboundLocalError` fixed, this successfully pushes live strings (e.g., `GGGrrr`, `Gyyyy`) to the UI.

## 6. WebSocket and Frontend Update Mechanisms
The backend ticks TraCI at `step_length=1.0s`, constructs the `new_junctions` dict, applies the payload to `self.state`, and broadcasts dynamically via WebSocket `_broadcast_state()`.
On the frontend (`CommandMap.tsx` and `SimFeedPanel.tsx`), `useWebSocket()` strictly replaces its internal reference to `liveJunctions[selectedJunction]`. The selected-junction panel now re-renders accurately on every state transition.

## 7. Execution and Regression
- `backend/reports/phase8/test_live_telemetry.py` built and executed to prove TraCI ticks correctly synchronize to updated structural states.
- 113/113 backend regression tests successfully passed.
- Frontend React/Vite build successfully compiled (`tsc -b && vite build`) without warnings.

## 8. Limitations
Queue is an estimate calculated directly via `halting vehicles * 5.0m`. It does not factor in geometric gaps or real-world sensor occlusion.
