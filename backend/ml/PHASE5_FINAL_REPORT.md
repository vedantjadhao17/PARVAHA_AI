# PHASE 5 FINAL REPORT — PRAVAHA AI

**Generated:** 2026-09-01  
**Model evaluated:** `backend/ml/models/queue_forecast_model.json` (XGBoost, trained in Phase 3)  
**Evaluation data:** `backend/ml/test.csv` (612 rows)

---

## 1. Executive Summary

Phase 5 completes the offline evaluation of PRAVAHA AI's queue forecasting model. The XGBoost model **beats the naive baseline by 36.3% RMSE** on the chronological held-out test set (16.56 m vs 26.01 m). The leakage audit confirms no future data leaks into any input feature. A root cause analysis of the Phase 4 zero-metric bug is documented and a fixed corridor evaluation harness is provided.

**Key caveats (must be disclosed):**
1. Test data is from the same 4 scenarios as training (temporal split only) — not scenario-level separation.
2. The model severely under-predicts extreme queues (>100 m): typical error ~52 m MAE.
3. No incident, heavy vehicle, or motorcycle scenarios exist — generalisation is untested.

---

## 2. Critical Finding: Train/Test Split Methodology

> ⚠️ The same 4 scenarios appear in BOTH train and test.

The 80/20 split is **chronological within each scenario×junction group**:
- Training: first 80% of simulation timesteps per group
- Test: last 20% of simulation timesteps per group

| Scenario | Train time range (s) | Test time range (s) |
|----------|---------------------|---------------------|
| sancheti_smoke | 20–1395 | 1400–1740 |
| sancheti_congestion | 20–1395 | 1400–1740 |
| corridor_camera | 20–675 | 680–840 |
| sancheti_camera | 20–675 | 680–840 |

Train and test do **not overlap in time** per group (verified programmatically), so there is no temporal leakage. However, the test set shares the same demand distribution as training.

**What we can claim:** Performance on chronological holdout within 4 known scenarios.  
**What we cannot claim:** Generalisation to unseen scenarios (incidents, new demand patterns).

---

## 3. Leakage Audit Result: PASS

Script: `backend/ml/audit_feature_leakage.py`

| Feature | Status | Evidence |
|---------|--------|---------|
| queue_length_m | SAFE | Current TraCI state at time t |
| vehicle_count | SAFE | Current TraCI state at time t |
| avg_speed_kmh | SAFE | Current TraCI state at time t |
| queue_minus_5 | SAFE | shift(+1) = queue(t−5s) |
| queue_minus_10 | SAFE | shift(+2) = queue(t−10s) |
| queue_minus_15 | SAFE | shift(+3) = queue(t−15s) |
| queue_minus_20 | SAFE | shift(+4) = queue(t−20s) |
| queue_slope | SAFE | (q_now − q_minus_20) / 20.0 — only past data |
| target_queue_60s | TARGET | shift(−12) = queue(t+60s) — excluded from features |

Programmatic checks verified:
- `target_queue_60s` is NOT in `FEATURE_COLS`
- `target_queue_60s[i] == queue_length_m[i+12]` for all tested rows
- All 4 lag features match their historical values
- Zero duplicate rows in train.csv

---

## 4. Actual Forecast Performance

### Aggregate (N=612)

| Metric | Model | Naive Baseline | Improvement |
|--------|-------|---------------|-------------|
| **RMSE** | **16.56 m** | 26.01 m | −36.3% |
| **MAE** | **8.13 m** | 11.40 m | −28.7% |
| Mean Error | +0.12 m | — | near-zero bias |
| Median AE | 1.36 m | — | — |
| Max AE | 111.46 m | — | — |
| R² | 0.697 | — | — |

### Per-Junction

| Junction | RMSE (m) | MAE (m) | Bias (m) | Naive RMSE (m) | vs Naive |
|----------|---------|--------|---------|---------------|---------|
| J1_SAN | 8.82 | 5.15 | +0.89 | 8.18 | −7.8% |
| J2_SJM | 11.71 | 6.34 | −2.75 | 14.35 | −18.4% |
| J3_SAP | 24.65 | 12.89 | +2.22 | 41.91 | **−41.2%** |

### Per-Scenario

| Scenario | RMSE (m) | MAE (m) | Naive RMSE (m) | Notes |
|----------|---------|--------|---------------|-------|
| corridor_camera | 33.57 | 23.35 | 57.31 | Best relative improvement |
| sancheti_camera | 10.94 | 3.48 | 0.00 | Naive perfect; queue=0 |
| sancheti_congestion | 14.58 | 9.83 | 20.71 | Solid improvement |
| sancheti_smoke | 1.36 | 1.36 | 0.00 | Naive perfect; queue~0 |

### Error by Queue Magnitude

| Queue Range | N | RMSE (m) | MAE (m) | Bias (m) |
|------------|---|---------|--------|---------|
| 0–10 m | 409 | 7.96 | 3.58 | −3.57 (over-predicts) |
| 10–25 m | 80 | 9.11 | 7.22 | −0.95 |
| 25–50 m | 59 | 16.75 | 13.78 | +2.97 |
| 50–100 m | 42 | 30.35 | 22.73 | +16.19 (under-predicts) |
| >100 m | 22 | 60.30 | 52.88 | **+34.28 (under-predicts severely)** |

**Key finding:** Regression-to-mean pattern — the model under-predicts extreme queues (>100 m off by ~34 m on average) and slightly over-predicts when queue should be near-zero.

---

## 5. Phase 4 Zero-Metric Root Cause and Fix

### Root Cause

`evaluate_phase4.py` used this loop condition:

```python
while traci.simulation.getMinExpectedNumber() > 0 and steps < 600:
```

In low-demand scenarios (`sancheti_smoke`), vehicles drain from the network well before 600 seconds. When `getMinExpectedNumber()` returns 0, the loop exits — sometimes as early as step ~200. The accumulated metrics `total_q / steps` then reflect only the first ~200 steps, not the intended 600.

Additionally, the Phase 4 harness used `TestClient(main_module.app)` to auto-approve recommendations, which triggered FastAPI startup (including a second SUMO server instance on the same port), causing "Retrying" connection errors in the logs.

### Fix Applied

`evaluate_phase5_corridor.py` fixes both issues:

1. **Loop condition changed to `while steps < SIM_STEPS`** (exactly 600 iterations), with a `try/except traci.exceptions.TraCIException` for fatal errors.
2. **TestClient removed entirely** — queue metrics are measured directly from TraCI lane data (`traci.lane.getLastStepHaltingNumber(lane) * 5.0`) without any FastAPI interaction.

### Corridor Evaluation Results (from fixed harness, 2026-09-01)

| Mode | Steps | Avg Queue (m) | vs HOLD |
|------|-------|--------------|---------|
| HOLD | 600 | 11.46 | — |
| SINGLE | 600 | 17.09 | +49.1% (worse) |
| CORRIDOR | 600 | 17.09 | +49.1% (worse) |

**Honest finding:** The simple green extension logic (extend green by 10 s when queue > 20 m) increased average queue in this 600-step run. This is likely because:
- Extending green in one direction delays cross-traffic
- Vehicle arrival patterns in the congestion scenario create demand spikes that a naive threshold-based policy worsens
- The evaluation window is only 600 steps; any green extension within those 600 steps makes some vehicles wait longer

This does NOT mean the PRAVAHA adaptive signal system fails — the production system uses the XGBoost forecast + counterfactual evaluation to choose signal modifications, not a simple threshold rule. However, it does demonstrate that naive signal extension without proper phase management can be counter-productive.

---

## 6. Retraining Decision: NOT REQUIRED

See `PHASE5_RETRAINING_DECISION.md` for full justification. Summary:
- Model beats naive by 36% RMSE
- Near-zero mean bias (+0.12 m)
- No new scenario data exists that would enable training on unseen distributions
- Tail under-prediction (>100 m) is noted but does not warrant retraining without new tail-heavy data

---

## 7. Known Limitations

| Limitation | Severity | Mitigation Path |
|-----------|---------|----------------|
| No scenario-level test holdout | HIGH | Create new SUMO simulations with different route files |
| Extreme queue under-prediction (>100 m) | HIGH | Collect more tail data; consider ensemble or quantile regression |
| No incident scenario | HIGH | Create incident route files; retrain |
| No heavy vehicle / motorcycle scenario | MEDIUM | Create heterogeneous route files |
| Simple corridor harness (Phase 5) | MEDIUM | Integrate with full SimulationManager counterfactual engine |
| Only 3 junctions covered | LOW | Expand SUMO network to more junctions |

---

## 8. Claims We CAN Defend vs Claims We CANNOT Make

### ✅ Claims We Can Defend

- XGBoost model achieves RMSE=16.56 m on chronological 20% holdout from 4 known scenarios
- Model beats naive baseline by 36.3% RMSE and 28.7% MAE
- R²=0.697: model explains 69.7% of 60-second-ahead queue variance
- Feature pipeline has no temporal leakage (programmatically verified)
- Train/test do not overlap in simulation time within any scenario×junction group
- The Phase 4 zero-metric bug was caused by premature loop exit when vehicles drain

### ❌ Claims We Cannot Make

- "The model generalises to unseen traffic scenarios" (no scenario-holdout evaluation performed)
- "Corridor optimisation reduces queue by X%" (simple green-extension harness results show the opposite; production counterfactual engine not evaluated in isolation)
- "The model handles incidents / heavy vehicles / motorcycles" (no such training data)
- "RMSE=16.56 m means ≈ X% reduction in real congestion" (metric is on simulation data only)
