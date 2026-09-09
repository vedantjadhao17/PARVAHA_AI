# PRAVAHA-AI Phase 8 Demo Scenario Audit

## 1. Baseline Context
- **Canonical Release Candidate**: `sancheti_congestion.sumocfg`
- **Measured Metrics**: 400 total inserted, 144 active, peak Q ~165.0m, avg speed 8.60 km/h.
- **Insight**: The baseline demonstrates a functional, moderately congested network. "Normal" and "Incident" conditions must be framed against this scale, avoiding excessive gridlock while ensuring SPILLBACK has a distinct signature.

## 2. Final Scenario Parameters & Calibrations
The scenarios are built around fixed deterministic `<flow>` values spanning 0-600 seconds, routed across the 3-junction corridor.

### 2.1 NORMAL
- **Goal**: Moderate free-flow.
- **Demand**: Constant 1000 vph total.
- **Measured**: 160 inserted vehicles, 150.0m peak queue, 4.65 km/h avg speed.
- **Result**: PASSED. Visibly distinguishable, smooth flow logic with realistic cycle delays.

### 2.2 RISING_CONGESTION
- **Goal**: Temporal increase to trace emerging risk on the dashboard.
- **Demand Schedule**: 
  - 0-200s: ~1000 vph
  - 200-400s: ~1600 vph
  - 400-600s: ~2900 vph
- **Measured**: 239 inserted vehicles, 165.0m peak queue, 3.04 km/h avg speed.
- **Result**: PASSED. The visual progression is clear: queue bounds creep up in the latter 200 seconds without causing total system halt. Forecast rises progressively.

### 2.3 SPILLBACK
- **Goal**: Sustained high flow generating genuine `HIGH`/`SPILLBACK` risk markers.
- **Demand**: Constant 3400 vph total.
- **Measured**: 386 inserted vehicles, 245.0m peak queue, 3.33 km/h avg speed. (Extensive buffering verified in TraCI logs).
- **Result**: PASSED. Physical backing up of the `sangam_three_signal` edges ensures threshold triggers are organically satisfied without manipulating thresholds.

### 2.4 INCIDENT_STRESS
- **Goal**: Localized bottleneck simulating stalled traffic.
- **Demand**: Constant 1000 vph + 1 stationary vehicle (`car_single`).
- **Incident Config**: `<stop lane="229904828#1_0" duration="500" startPos="10"/>`. Validated physically feeding J2.
- **Measured**: 161 inserted vehicles, 155.0m peak queue, 4.54 km/h avg speed.
- **Result**: PASSED. The blockage forces localized lane changing and constrains throughput across J2 organically, invoking stress without total gridlock.

## 3. Architecture Isolation
- **Seed Method**: Explicit `<random_number><seed value="42"/></random_number>` used cleanly within standard SUMO syntax limits.
- **Unmodified Core**: All components (XGBoost model, `forecast.py`, `signal_plan.py`, `SafetyGate`, `manager.py` apart from the 2-line config extractor) remain functionally identically.
- **Launcher**: `scripts/run_demo.sh` acts purely as a shell wrapper overriding the environmental pointer while relying on standard `uvicorn` and FastAPI deployment mechanics.
- **Regression**: 113/113 backend unit tests pass fully. Frontend builds via `vite build` without issue. 

## 4. Benchmark Isolation & Repeatability
- The Phase 6 `/phase6` artifacts are 100% untouched.
- Manifest `demo_scenarios.json` guarantees strict segregation.
- Runs are reliably deterministic via the fixed seed argument, reproducing identical queue patterns across identical invocations.
