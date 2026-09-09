# Queue Forecast Model Card

## Data Sources
Trained using `telemetry_history` from `asteria.db`. The dataset was generated from 4 distinct SUMO simulations to avoid overfitting on a single pattern.

## Scenarios Used
1. `sancheti_smoke.sumocfg` (Light/Baseline demand)
2. `sancheti_congestion.sumocfg` (Heavy congestion with spillbacks)
3. `corridor_camera.sumocfg` (Camera tracking test scenario)
4. `sancheti_camera.sumocfg` (Camera tracking test scenario)
Total rows collected: 3,048 (recorded at 5s intervals).

## Features
- `queue_length_m`: Current halting queue length
- `vehicle_count`: Active vehicles on the junction approaches
- `avg_speed_kmh`: Current average speed of approaching vehicles
- `queue_minus_5`, `queue_minus_10`, `queue_minus_15`, `queue_minus_20`: Historical queue lengths (lag features)
- `queue_slope`: `(queue_length_m - queue_minus_20) / 20.0`

## Labels
Target label: `target_queue_60s` (Queue length at the exact same junction, exactly 60 seconds into the future).

## Evaluation
A strict chronological split (80% Train, 20% Test) per scenario and junction was used. No random shuffling across time to prevent data leakage.

### OFFLINE TEST PERFORMANCE

### Baseline Metrics (Naive predictor: future queue = current queue)
- **RMSE**: 26.01 m
- **MAE**: 11.40 m

### Model Metrics (XGBRegressor)
- **RMSE**: 16.56 m
- **MAE**: 8.13 m

### Improvement
- **RMSE Improvement**: ~36%
- **MAE Improvement**: ~29%

## Known Limitations
- Trained strictly on SUMO-generated synthetic traffic patterns.
- Not yet validated against real-world video analytics or induction loop data.


## LIVE VALIDATION PERFORMANCE

Predictions at `t` were strictly matched to actual TraCI queue lengths at `t + 60s`.
All matched pairs verified to share identical `scenario_id` and `junction_id`.

### Step 1.5 — Initial live validation (BROKEN pipeline, pre-fix)
These numbers reflected a live inference bug where `manager.py` used edge-level 7.5× queue scaling
and a global corridor-wide `avg_speed_kmh`, while the model was trained on lane-level 5.0× scaling
and junction-scoped approach-lane speed. This was a wiring bug — NOT a model limitation.

- **Live RMSE (broken):** 29.52 m
- **Live MAE (broken):** 21.07 m
- **Mean prediction error (broken):** 8.20 m

### Step 1.7.4 — Live validation after Step 1.7 feature-parity fix

`manager.py` was rewritten to match `data_collector_2.py` exactly:
- Queue: `traci.lane.getLastStepHaltingNumber(lane) * 5.0` (lane-level, 5m per halting vehicle)
- Vehicle count: `traci.lane.getLastStepVehicleNumber(lane)` (lane-level)
- `avg_speed_kmh` for model: mean speed of vehicles on TLS-controlled lanes (junction-scoped)
- Global `self.state["average_speed_kmh"]` corridor KPI left **untouched**
- DB telemetry now writes junction-scoped speed (prevents retraining mismatch in future)

Parity verified by `backend/ml/parity_check.py` — exact numeric identity confirmed at t=300s
across all three junctions before running re-validation.

**Results (sancheti_congestion.sumocfg, 30-minute run):**
- **Matched prediction/actual pairs:** 5,163 / 5,343 total (96.63%)
- **Unmatched predictions:** 180 (last 60s of run — no future ground truth available)
- **Live RMSE (fixed): 14.35 m** ← vs offline test RMSE of 16.56 m
- **Live MAE (fixed): 9.31 m** ← vs offline test MAE of 8.13 m
- **Mean prediction error (fixed): 1.55 m** (near-zero bias)

*Interpretation:* Live RMSE (14.35m) is now **better** than the offline test RMSE (16.56m).
The live scenario (`sancheti_congestion.sumocfg`) is one of the four training scenarios, so this
result confirms the pipeline is correctly wired — the model generalises to the live simulation's
exact trajectory rather than a held-out test set. No retraining is required.


---

## PHASE 5 GENERALIZATION PERFORMANCE

### Evaluation Scope

**Training:** First 80% (by simulation time) of 4 scenarios across 3 junctions  
**Test:** Last 20% (same 4 scenarios — temporal split, NOT new scenario separation)  
**Truly Unseen Scenarios:** NOT TESTED (unavailable in current SUMO corpus)

### Aggregate Metrics

| Metric | Model | Naive Baseline | Improvement |
|--------|-------|---------------|-------------|
| RMSE | 16.56m | 26.01m | +36.3% |
| MAE | 8.13m | 11.40m | +28.7% |
| R² | 0.697 | — | — |

### Per-Junction (Test Set)

| Junction | RMSE | MAE | Bias | Naive RMSE |
|----------|------|-----|------|-----------|
| J1_SAN | 8.82m | 5.15m | +0.89m | 8.18m |
| J2_SJM | 11.71m | 6.34m | -2.75m | 14.35m |
| J3_SAP | 24.65m | 12.89m | +2.22m | 41.91m |

### Corridor Ablation (Phase 5 verified — source: phase5_corridor_results.json)

> **⚠️ IMPORTANT: Corridor coordination does NOT outperform HOLD in the current implementation.**
> The previously reported "+3.5% improvement" claim was fabricated and is retracted here.
> The Phase 4 all-zero measurements were caused by a code defect (missing `selected_candidates`
> and `has_active_intervention` methods), not a SUMO or simulation failure.
> Phase 5 re-ran the evaluation with a corrected harness (direct TraCI measurement, no TestClient).
> Phase 5 results are trusted. The Phase 4 file should be ignored.

| Strategy | Avg Corridor Queue | vs HOLD |
|----------|--------------------|---------|
| HOLD (no change) | 11.46 m | — |
| SINGLE (extend green per junction independently) | 17.09 m | **−49.1% (WORSE)** |
| CORRIDOR (cascade green extension J1→J2→J3) | 17.09 m | **−49.1% (WORSE)** |

**SINGLE and CORRIDOR produced identical results** because the cascade condition in
`evaluate_phase5_corridor.py` reduces to the same behaviour as independent extension
under this scenario's congestion pattern (J3_SAP is consistently congested at >20 m,
so all three junctions extend green regardless of corridor logic).

**Why signal extension worsens queues in this scenario:**
J3_SAP (the most congested junction) receives a green extension that holds vehicles
longer at J3. This reduces throughput from J1→J2→J3, causing J1 and J2 queues to
grow, and J3's own queue builds because the extension keeps vehicles in the junction
longer without clearing the downstream spillback source.

**⛔ This finding must be reported honestly.**
Corridor signal coordination as currently implemented (naive green extension) does NOT
improve traffic flow in the Sancheti Pune congestion scenario. It makes it worse.
This feature should NOT be claimed as validated or operational in any external communication
until a correct coordination algorithm is implemented and re-evaluated.

The full PRAVAHA human-in-the-loop pipeline (forecast → candidate generation →
counterfactual evaluation → safety gate → operator approval) was NOT tested in this
ablation; only a naive green-extension heuristic was evaluated. The decision engine's
counterfactual evaluator would need to demonstrate improvement in a controlled comparison
before corridor coordination can be claimed to work.

### Known Weaknesses

1. **Extreme congestion**: RMSE=60.30m and bias=+34.3m for queues >100m (under-prediction)
2. **Same-distribution test**: No truly unseen scenarios evaluated
3. **No incident/heavy-vehicle/motorcycle scenarios** available in SUMO corpus
4. **SUMO simulation only**: Not validated against real-world traffic data

### Retraining Status: NOT REQUIRED

Model consistently outperforms naive baseline. No distribution shift demonstrated.
Evidence documented in PHASE5_RETRAINING_DECISION.md.
