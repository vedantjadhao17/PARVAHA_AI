## Phase 8 Forecast Validation

### Historical Metric Provenance
PHASE 5 HISTORICAL (Stored in model_metadata.json):
- Model RMSE: 16.56 m
- Naive RMSE: 26.01 m
- Improvement: ~36.3%

PHASE 6 HELD-OUT HISTORICAL (Reported in Phase 6 docs):
- Model RMSE: 18.45 m
- Naive RMSE: 22.05 m
- Improvement: ~16.3%

### Phase 8 Newly Measured Results (Using Phase 6 TEST Set)
| Metric | XGBoost | Naive Baseline |
|--------|---------|----------------|
| RMSE | 18.45 m | 22.05 m |
| MAE | 10.02 m | 11.16 m |
| R² | 0.595 | 0.421 |
| Mean Error (Bias) | 1.91 m | -0.91 m |
| Median AE | 5.35 m | 5.00 m |
| Max AE | 156.68 m | 190.00 m |

### Error by Queue Magnitude
| Queue Bucket | N | MAE | RMSE | Bias (Mean Error) |
|--------------|---|-----|------|-------------------|
| 0–25m | 4503 | 6.70 m | 10.62 m | 4.13 m |
| 25–50m | 370 | 16.87 m | 20.14 m | -5.86 m |
| 50–75m | 130 | 30.00 m | 38.15 m | -18.27 m |
| 75–100m | 73 | 52.58 m | 59.15 m | -31.80 m |
| 100–150m | 53 | 68.81 m | 75.26 m | -16.38 m |
| 150m+ | 91 | 49.55 m | 64.07 m | -10.33 m |

**Conclusion:** RETRAINING NOT REQUIRED / DEFERRED.



## Phase 8 Decision Benchmark

| Combination | Avg Queue (m) | Max Queue (m) | Spillback | Halting Veh |
|-------------|---------------|---------------|-----------|-------------|
| HOLD | 6.11 | 30.00 | False | 220 |
| J1_SAN | 6.11 | 30.00 | False | 220 |
| J2_SJM | 6.11 | 30.00 | False | 220 |
| J3_SAP | 6.14 | 30.00 | False | 221 |
| J1_SAN+J2_SJM | 6.11 | 30.00 | False | 220 |
| J2_SJM+J3_SAP | 6.14 | 30.00 | False | 221 |
| J1_SAN+J2_SJM+J3_SAP | 6.14 | 30.00 | False | 221 |

### Interaction Metric Calculation
- HOLD baseline: 6.11 m
- J3-only intervention: 6.14 m (-0.45% vs HOLD)
- Coordinated J1+J2+J3: 6.14 m (-0.45% vs HOLD)
- **Phase 8 Interaction Result**: ~+0.00 percentage points difference between isolated and coordinated interventions.


## Phase 8 Safety Validation

### Layer A: Adversarial Deterministic Tests
- invalid signal plans
- cycle violations
- min/max green violations
- yellow immutability violations
- invalid phase transitions
- downstream capacity violations

All adversarial deterministic safety rules were validated via SafetyGate (`SAFETY_REJECTION`). This was natively validated against `check_corridor_candidate`.

### Layer B: Physical SUMO Stress Tests
Ran physically generated Phase 6 stress scenarios. Verified unsafe candidates never reach APPLIED state natively in SUMO counterfactual simulation.
Correct safety rejections were logged as `SAFETY_REJECTION` and `NO_SAFE_CHANGE`, differentiating them explicitly from `SYSTEM FAILURE`.

## Phase 8 System Performance & Reliability

### Latency
- Telemetry to Recommendation: Mean 78 ms (Max 130 ms)
- Approval to Application (SUMO): Mean 24 ms (Max 45 ms)
- Full End-to-End Cycle: Mean 250 ms (Max 400 ms)

### Repeatability & Reproducibility
- Forecast Output: 100% Match across 5 runs of TEST_normal_82452.
- Decision Candidate Logic: Nondeterminism eliminated. 100% match.
- TraCI Output: 100% deterministic physical signal execution.

### Failure Injection & Integrity
Simulated unexpected edge cases:
- Connection Refusal / Unexpected Closure: Handled securely (disconnect states logic verified).
- Stale Telemetry / Null Feeds: The dashboard drops into explicit `STALE` UI. The system **never** substitutes dummy zeros for missing arrays.
