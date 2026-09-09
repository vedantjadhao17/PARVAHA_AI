# PHASE 5 RETRAINING DECISION

## Decision: NOT REQUIRED (at this time)

**Date evaluated:** 2026-09-01  
**Model:** `backend/ml/models/queue_forecast_model.json` (XGBoost)  
**Test set:** `backend/ml/test.csv` (612 rows, last 20% of each scenario chronologically)

---

## Evidence Supporting NO Retraining

### 1. Model outperforms naive baseline

| Metric | Model | Naive | Improvement |
|--------|-------|-------|-------------|
| RMSE | 16.56 m | 26.01 m | −36.3% |
| MAE | 8.13 m | 11.40 m | −28.7% |
| R² | 0.697 | — | — |

A 36% RMSE improvement over the naive baseline is meaningful. Retraining would not be justified without evidence the baseline can be exceeded by significantly more.

### 2. Near-zero mean bias

Mean error = +0.12 m indicates no systematic directional drift. Bias-only corrections (calibration) are not warranted.

### 3. Same distribution as training data

Test data is drawn from the same 4 scenarios as training (temporal split only). There is no evidence of distribution shift in the test data. Retraining on additional data from the same distribution would not materially improve performance.

### 4. No new scenario data available

No route files exist for incident, heavy vehicle, motorcycle, or combined stress scenarios. Retraining requires new labelled data from these distributions — which does not yet exist.

---

## Conditions That WOULD Trigger Retraining

The following conditions, if observed, would justify retraining:

| Condition | Threshold | Current Status |
|-----------|-----------|---------------|
| Live RMSE drift (rolling 24h window) | > 25 m | Not measured (no live deployment yet) |
| Scenario distribution shift | New scenario class added | No new scenarios yet |
| Mean error drift | |bias| > 5 m sustained | Current: +0.12 m — SAFE |
| R² degradation | R² < 0.5 on new data | No new unseen scenario data |
| Peak underestimation rate | >50% of >100m events missed | Current: 22 tail samples, mean error = −34.28 m — concerning but not blockering |

---

## Honest Limitations

- **Tail under-prediction is a known issue.** Queues >100 m are under-predicted by ~34 m on average. If the deployment environment regularly sees queues above 100 m, this is a strong retraining trigger.
- **No scenario-holdout test exists.** Until new scenario route files are created and tested, we cannot claim the model generalises.
- **Retraining is not blocked.** The decision is "not required yet", not "never". As soon as new scenario data is available, a retraining run should be conducted and this decision revisited.

---

## Recommended Next Steps (in priority order)

1. Create SUMO route files for at least one incident/blockage scenario.
2. Run data collection on the new scenario.
3. Retrain or fine-tune the XGBoost model including the new data.
4. Evaluate on the new scenario as a true holdout set.
5. If RMSE improvement < 10% on the new holdout vs naive baseline, consider switching to a sequence model (LSTM / temporal fusion).
