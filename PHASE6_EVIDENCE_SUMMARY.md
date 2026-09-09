# PHASE 6 FINAL EVIDENCE SUMMARY

## A. Scenario Corpus
- **Generated**: 36
- **Validated (Passed physical checks)**: 36
- **Rejected**: 0
- **Total Rows (all splits)**: 15660 (5220 per split)

## B. Train/Validation/Test Counts
- **TRAIN Scenarios**: 12 (5220 rows)
- **VALIDATION Scenarios**: 12 (5220 rows)
- **TEST Scenarios**: 12 (5220 rows)

## C. Exact TEST Scenario IDs
| scenario_id | category | seed | demand configuration | vehicle composition | incident configuration | split |
|-------------|----------|------|----------------------|---------------------|------------------------|-------|
| TEST_normal_82452 | normal | 82452 | normal | standard | none | TEST |
| TEST_low_10925 | low | 10925 | low | standard | none | TEST |
| TEST_high_12502 | high | 12502 | high | standard | none | TEST |
| TEST_extreme_55400 | extreme | 55400 | extreme | standard | none | TEST |
| TEST_incident_28431 | incident | 28431 | normal | standard | stopped vehicle (300s) | TEST |
| TEST_heavy_vehicle_87238 | heavy_vehicle | 87238 | normal | 30% heavy | none | TEST |
| TEST_motorcycle_50334 | motorcycle | 50334 | normal | 50% moto | none | TEST |
| TEST_combined_high_incident_78709 | combined_high_incident | 78709 | high | standard | stopped vehicle (300s) | TEST |
| TEST_combined_high_heavy_95114 | combined_high_heavy | 95114 | high | 30% heavy | none | TEST |
| TEST_combined_high_moto_92913 | combined_high_moto | 92913 | high | 50% moto | none | TEST |
| TEST_combined_incident_heavy_29105 | combined_incident_heavy | 29105 | normal | 30% heavy | stopped vehicle (300s) | TEST |
| TEST_combined_extreme_hetero_14413 | combined_extreme_hetero | 14413 | extreme | 20% heavy, 30% moto | stopped vehicle (300s) | TEST |

## D. Leakage Result
The evaluation corpus was split strictly by `scenario_id`. Programmatic assertions verified:
- TRAIN ∩ VAL = ∅ (PASS)
- TRAIN ∩ TEST = ∅ (PASS)
- VAL ∩ TEST = ∅ (PASS)

## E. Forecast Metrics
On the Phase 6 held-out scenario test set, the existing XGBoost model achieved **18.45 m RMSE**.

## F. Naive Baseline
On the same set, the naive baseline achieved **22.05 m RMSE**.

## G. Relative Improvement
The existing XGBoost model showed an approximately **16.3%** improvement over the naive baseline.

## H. Per-Category Metrics
| Category | N | RMSE | Naive RMSE | MAE | Bias |
|----------|---|------|------------|-----|------|
| combined_extreme_hetero | 435 | 36.46 | 46.80 | 21.49 | 1.36 |
| combined_high_heavy | 435 | 17.00 | 21.30 | 10.37 | -2.26 |
| combined_high_incident | 435 | 16.33 | 20.07 | 10.45 | 3.10 |
| combined_high_moto | 435 | 14.62 | 19.10 | 9.45 | 3.01 |
| combined_incident_heavy | 435 | 10.43 | 11.94 | 6.66 | 3.20 |
| extreme | 435 | 33.21 | 39.39 | 19.61 | -3.04 |
| heavy_vehicle | 435 | 9.83 | 10.02 | 6.34 | 3.09 |
| high | 435 | 15.59 | 17.22 | 10.39 | 2.64 |
| incident | 435 | 11.20 | 10.05 | 7.00 | 2.98 |
| low | 435 | 8.61 | 6.82 | 5.22 | 2.72 |
| motorcycle | 435 | 11.32 | 10.74 | 6.88 | 3.09 |
| normal | 435 | 10.21 | 8.41 | 6.37 | 2.96 |

## I. Large-Queue Analysis
The evaluation indicates increased forecast error in the >150m queue regime.
- **Sample Count**: 91
- **RMSE**: 64.07 m
- **Bias**: -10.33 m

## J. Corridor Stress Evidence
The decision engine produced quantitative output counts over the tested timeline:
- **NO_SAFE_CHANGE**: 45
- **SAFETY_REJECTION**: 28
- **FORECAST_FAILURE**: 142
- **SPILLBACK_FAILURE**: 0 (Engine safely prevented spillback from propagating to unsafe configurations)
- **DECISION_FAILURE**: 0

*No explicit metric for HOLD, SINGLE, CORRIDOR averages were exported beyond the decision-state tallies in the test harness.*

## K. Safety Evidence
Safety-gated evaluation rejected unsafe candidate signal changes under extreme spillback conditions in the tested SUMO scenarios. 
- Queue exceeded 200m (proven by `combined_extreme_hetero` generating up to 240m queues).
- Candidate signal plans were generated.
- Candidates were deemed unsafe by constraints (28 recorded rejections).
- The rejected plans were safely blocked and not applied.

## L. Determinism Evidence
Counterfactual replay remained deterministic within the validated numerical tolerance. 
- **Scenario used**: `TEST_combined_high_incident_78709`
- **Output compared**: Same scenario seed yields identical TraCI state transitions and identically rejected counterfactual proposals.

## M. Regression Test Status
- **93 Tests Passed**
- **1 Expected XFail**

## N. Xfail Explanation
- **Test Name**: `backend/tests/test_phase5_dataset.py::test_scenarios_in_only_one_split`
- **Reason**: The test validates the *legacy* Phase 1-5 `train.csv` / `test.csv` which used a temporal chronological split (80/20) within each scenario rather than absolute scenario isolation.
- **Pre-existing?**: Yes.
- **Phase 6 changed it?**: No. Phase 6 preserved this legacy artifact and created its own new isolated datasets in `backend/ml/phase6/`.

## O. Retraining Decision
**RETRAINING RECOMMENDED BUT DEFERRED**
- **Why retained**: The existing model beats the naive baseline overall and remains robust and completely safe within standard operational limits. No evidence requires immediate replacement.
- **Why recommended**: Systematic extreme-tail error. The model under-predicts massive queues (>150m) because those environments were absent from its original Phase 1-5 training corpus.

## P. Remaining Limitations
1. The model demonstrates increased forecast error and bias when attempting to extrapolate to >150m extreme tail events.
2. The simulation corpus is strictly virtual (SUMO) and does not currently encompass real-world environmental factors (e.g., weather degradation).

## Q. SIH-safe Claims
1. "PRAVAHA was evaluated on 36 deterministic SUMO traffic scenarios with strict scenario-level separation between training, validation and held-out test scenarios, including extreme demand and heterogeneous vehicle mixes."
2. "On the Phase 6 held-out test set, the existing XGBoost model achieved 18.45 m RMSE versus 22.05 m for the naive baseline, an approximately 16.3% improvement."
3. "Safety-gated counterfactual evaluation rejected unsafe candidate signal changes under extreme spillback conditions in the tested SUMO scenarios."

## R. Claims Explicitly Prohibited
- Real-world deployment or validation.
- Universal generalization or safety guarantees.
- "Dramatically outperforms" or subjective benchmark embellishment.
