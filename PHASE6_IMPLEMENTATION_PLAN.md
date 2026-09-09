# PHASE 6 IMPLEMENTATION PLAN
## Scenario Generalization + Advanced Stress Validation

### A. Current Architecture Discovered
- **Traffic Engine:** SUMO with traci (v1.27.1).
- **Core Loop:** `SimulationManager` in `backend/app/sim/manager.py` loops over simulation steps, grabs features identically to offline training (`data_collector_2.py`).
- **Forecasting:** XGBoost regressor predicting queue 60s ahead based on 8 features (queue, speed, vehicle_count, and lag features).
- **Decision Engine:** `CorridorDecisionEngine` checks threshold (>5% improvement required). Relies on `CorridorSafetyGate` and `CorridorCounterfactualEvaluator`.
- **Safety Gate:** Hard constraints on min green, max green, cycle length preservation, yellow phase immutability.
- **Approval Flow:** Human-in-the-loop enforced via `RecommendationStore` holding PENDING recommendations before they can be APPLIED.

### B. Existing Phase 5 Evaluation Methodology
- **Leakage Check:** Programmatic verification of no target leak in lag features.
- **Model Evaluation:** Offline test set (RMSE, MAE).
- **Corridor Evaluation:** 600-step test comparing HOLD, SINGLE (J3), and CORRIDOR modes, measuring absolute TraCI queue length.

### C. Existing Scenario-Generation Capability
Currently relies on existing static route files:
- `congestion.rou.xml` (high demand)
- `smoke.rou.xml` (low demand)
- `corridor_demo.rou.xml`, `camera_demo.rou.xml`
There is no programmatic scenario generator that spins up randomized but deterministic permutations of traffic mixes or incidents.

### D. Existing Dataset Pipeline
`backend/ml/build_dataset.py` currently fetches data from sqlite (`telemetry_history`).
It uses a strictly **temporal** split (first 80% train, last 20% test) on the *same* 4 scenarios.

### E. Existing Feature Contract
8 features computed via `traci.lane.getLastStepHaltingNumber(l) * 5.0`, etc., maintaining perfect live/offline parity.

### F. Existing Model Training/Evaluation Flow
`train_model.py` trains XGBoost on `train.csv`.
`evaluate_phase5_forecast.py` evaluates on `test.csv`.

### G. Existing Corridor Evaluation Flow
`evaluate_phase5_corridor.py` runs 600 steps of SUMO, injecting +10/-10s green phase adjustments at t=60, comparing against HOLD.

### H. Existing Safety Architecture
`CorridorSafetyGate` calls `SafetyGate` for each junction. Rejected candidates return `NO_SAFE_CHANGE`.

---

### I. Proposed Phase 6 Changes
1. **Scenario Generator:** Create `backend/ml/generate_scenarios.py` to programmatically build sumocfg and route files from base networks using deterministic SUMO tools (`duarouter` or `randomTrips.py`, or explicit XML generation) for incidents, heavy vehicles, etc.
2. **True Dataset Split:** Modify dataset pipeline to split entirely by `scenario_id` (Train scenarios, Validation scenarios, Test scenarios) ensuring no overlap.
3. **Model Evaluation:** Re-evaluate existing XGBoost on the *true unseen* test set, heavily focusing on the large-queue bins (>100m).
4. **Stress Testing:** Use the new extreme demand and incident scenarios in `evaluate_phase6_stress.py` to test the decision engine and safety gate.
5. **Retraining Evidence:** Based on True Test Set metrics, determine if the model needs retraining.

### J. Proposed Scenario Matrix
We will generate at least the following explicit scenarios via a script:
1. `TRAIN_normal`: Baseline normal demand.
2. `TRAIN_high`: High demand (similar to congestion).
3. `VAL_high`: High demand for validation.
4. `TEST_extreme`: Extreme demand (>1500 vehicles/hr).
5. `TEST_incident`: Normal demand with lane blockage at J2.
6. `TEST_heavy`: Normal demand with 30% heavy vehicles.
7. `TEST_motorcycle`: Normal demand with 50% motorcycles.
8. `TEST_combined`: Extreme demand + incident.

### K. Proposed Train/Validation/Test Methodology
- Collect telemetry for all generated scenarios.
- Assign completely separate scenario names to Train, Val, Test.
- Measure existing model on TEST split to prove actual generalization.

### L. Proposed Stress Tests
- Test Corridor Decision Engine against `TEST_combined` (high demand + incident).
- Ensure safety gates reject unbalanced or overly aggressive phase changes during massive spillback.
- Ensure `NO_SAFE_CHANGE` is triggered when downstream links are full.

### M. Proposed Large-Queue Investigation
- Build a notebook/script `analyze_queue_bias.py` focusing on RMSE/MAE in bins (0-25m, 25-50m, 50-75m, 75-100m, 100-150m, 150m+).
- Investigate feature saturation (does queue_minus_20 just perfectly mirror current queue at max capacity?).

### N. Proposed Retraining Decision Methodology
- If the current model degrades severely on TEST scenarios (>30% worse than NAIVE), RETRAINING is justified.
- If retraining is performed, the old model is kept as `queue_forecast_model_v1.json`, new as `v2`.

### O. Files that would be added
- `backend/ml/phase6/scenario_generator.py`
- `backend/ml/phase6/build_phase6_dataset.py`
- `backend/ml/phase6/evaluate_model.py`
- `backend/ml/phase6/analyze_large_queue.py`
- `backend/ml/phase6/stress_test_corridor.py`
- `backend/ml/phase6/retrain_if_needed.py`
- `PHASE6_SCENARIO_CORPUS.md`
- `PHASE6_DATASET_AUDIT.md`
- `PHASE6_GENERALIZATION_REPORT.md`
- `PHASE6_STRESS_TEST_REPORT.md`
- `PHASE6_RETRAINING_DECISION.md`

### P. Files that would be modified
- `MODEL_CARD.md` (only if justified)

### Q. Files that must remain untouched
- `backend/app/sim/manager.py` (telemetry/loop)
- `backend/app/sim/safety_gate.py`
- `backend/app/main.py` (approval workflow)
- Existing tests from Phase 1-5.

### R. Expected Outputs/Reports
- A clear answer on whether the Phase 1-5 model generalizes to true unseen scenarios.
- Evidence of safety gate resilience under incident/extreme traffic.

### S. Risks
- SUMO might struggle to generate realistic heavy-vehicle or incident dynamics without complex configuration. (Will use standard TraCI/SUMO XML definitions for blockages/vehicle classes).

### T. Rollback Strategy
- All new Phase 6 code isolated to `backend/ml/phase6/`.
- Existing `queue_forecast_model.json` is never overwritten.

### U. Acceptance Criteria
- [ ] Scenario corpus expanded
- [ ] True scenario-level split exists
- [ ] Leakage audit passes
- [ ] Existing model evaluated on unseen scenarios
- [ ] Large queue error analysis completed
- [ ] Corridor coordination stress-tested
- [ ] Safety gates stress-tested
- [ ] Retraining decision is evidence-based
- [ ] Phase 6 reports generated
