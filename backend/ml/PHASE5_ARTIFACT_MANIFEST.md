# PHASE 5 ARTIFACT MANIFEST

**Phase:** 5 — Model Evaluation & Audit  
**Generated:** 2026-09-01  
**Status:** All scripts executed; all outputs from actual execution (not fabricated)

---

## Core Data Artifacts

| File | Size | Source | Description |
|------|------|--------|-------------|
| `backend/ml/train.csv` | 2436 rows | `build_dataset.py` + SUMO/TraCI | Training set — first 80% per scenario×junction |
| `backend/ml/test.csv` | 612 rows | `build_dataset.py` + SUMO/TraCI | Test set — last 20% per scenario×junction |
| `backend/ml/models/queue_forecast_model.json` | — | `train_model.py` + XGBoost | Trained XGBoost regressor (Phase 3) |

## Phase 5 Scripts

| Script | Source | Description |
|--------|--------|-------------|
| `backend/ml/audit_feature_leakage.py` | Phase 5 | Leakage audit script; reads train.csv, verifies causal ordering |
| `backend/ml/evaluate_phase5_forecast.py` | Phase 5 | XGBoost evaluation on test.csv; computes RMSE/MAE/R² |
| `backend/ml/evaluate_phase5_corridor.py` | Phase 5 (fixed harness) | SUMO corridor ablation; loops 600 steps exactly; no TestClient |

## Phase 5 Output JSONs

| File | Source Script | Contents |
|------|--------------|---------|
| `backend/ml/phase5_forecast_results.json` | `evaluate_phase5_forecast.py` | Aggregate + per-junction + per-scenario + bucket metrics |
| `backend/ml/phase5_corridor_results.json` | `evaluate_phase5_corridor.py` | HOLD / SINGLE / CORRIDOR queue averages from 3 SUMO runs |
| `backend/ml/phase5_scenario_manifest.json` | Manual (Phase 5) | Scenario metadata + missing stress scenarios documented |

## Phase 5 Markdown Reports

| File | Source | Contents |
|------|--------|---------|
| `backend/ml/PHASE5_LEAKAGE_AUDIT.md` | `audit_feature_leakage.py` output | Feature classification table; PASS verdict |
| `backend/ml/PHASE5_DATA_AUDIT.md` | Analysis of train/test.csv | Dataset stats; critical temporal-split finding |
| `backend/ml/PHASE5_ERROR_ANALYSIS.md` | `evaluate_phase5_forecast.py` output | Per-junction, per-scenario, bucket error analysis |
| `backend/ml/PHASE5_RETRAINING_DECISION.md` | Manual + metrics | NOT REQUIRED decision with justification |
| `backend/ml/PHASE5_FINAL_REPORT.md` | All Phase 5 outputs | Comprehensive report with honest claims |
| `backend/ml/PHASE5_ARTIFACT_MANIFEST.md` | Manual (this file) | Index of all Phase 5 artifacts |

## Phase 5 Tests

| File | Test Count | Pass | XFail | Fail | Notes |
|------|-----------|------|-------|------|-------|
| `backend/tests/test_phase5_leakage.py` | 7 | 7 | 0 | 0 | All leakage checks pass |
| `backend/tests/test_phase5_dataset.py` | 11 | 10 | 1 | 0 | xfail: scenario-overlap (expected, documented) |

**Full suite:** `backend/tests/` — 93 passed, 1 xfailed, 0 failed (2026-09-01)

## Pre-existing Phase Reports Referenced

| File | Phase | Description |
|------|-------|-------------|
| `backend/ml/PHASE4_FINAL_REPORT.md` | 4 | Architecture audit; zero-metric issue noted |
| `backend/ml/MODEL_CARD.md` | 3 | XGBoost model card |
| `backend/ml/phase4_evaluation.json` | 4 | Previous (zero-metric) evaluation results |
| `backend/ml/phase3_evaluation.json` | 3 | Phase 3 cross-validation results |

---

## Execution Log (Phase 5, 2026-09-01)

| Script | Exit Code | Key Output |
|--------|-----------|-----------|
| `audit_feature_leakage.py` | 0 (PASS) | LEAKAGE AUDIT: PASS |
| `evaluate_phase5_forecast.py` | 0 | RMSE=16.56m, MAE=8.13m, R²=0.697 |
| `evaluate_phase5_corridor.py` | 0 | HOLD=11.46m, SINGLE=17.09m, CORRIDOR=17.09m |
| `pytest backend/tests/` | 0 | 93 passed, 1 xfailed |

---

## Data Integrity Checksums

| File | Rows | NaN Count | Verified |
|------|------|----------|---------|
| train.csv | 2436 | 0 | ✅ |
| test.csv | 612 | 0 | ✅ |
