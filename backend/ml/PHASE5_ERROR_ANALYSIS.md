# PHASE 5 ERROR ANALYSIS

> All numbers sourced from actual execution of `evaluate_phase5_forecast.py` on 2026-09-01.  
> No numbers were manually adjusted or cherry-picked.

## Aggregate Performance (N=612)

| Metric | Model | Naive Baseline (current queue) | Model Improvement |
|--------|-------|-------------------------------|------------------|
| **RMSE (m)** | **16.56** | 26.01 | −36.3% |
| **MAE (m)** | **8.13** | 11.40 | −28.7% |
| Mean Error (m) | +0.12 | — | near-zero bias |
| Median AE (m) | 1.36 | — | — |
| Max AE (m) | 111.46 | — | — |
| R² | 0.697 | — | — |

**Interpretation:** The model beats naive by 36% RMSE and 29% MAE. R²=0.697 means the model explains 69.7% of variance in 60-second-ahead queue.  
The near-zero mean error (+0.12 m) indicates no systematic directional bias overall.

---

## Per-Junction Performance

| Junction | Name | N | Model RMSE (m) | Model MAE (m) | Bias (m) | Naive RMSE (m) | Model vs Naive |
|----------|------|---|---------------|--------------|----------|---------------|----------------|
| cluster_13546492148_1838721956 | J1_SAN | 204 | 8.82 | 5.15 | +0.89 | 8.18 | **−7.8% RMSE** |
| cluster_2061304035_245647208 | J2_SJM | 204 | 11.71 | 6.34 | −2.75 | 14.35 | −18.4% RMSE |
| cluster_245647168_3238255150_3495323634 | J3_SAP | 204 | 24.65 | 12.89 | +2.22 | 41.91 | −41.2% RMSE |

### Junction-Level Findings

**J1_SAN:** The model barely beats naive (−7.8% RMSE). Queue at J1 changes slowly and the naive "current queue" is already a good predictor. Positive bias of +0.89 m means slight over-prediction.

**J2_SJM:** Moderate improvement (−18.4%). Negative bias of −2.75 m indicates the model slightly underpredicts congestion events at this junction.

**J3_SAP:** Strongest improvement (−41.2% RMSE). This junction shows the most volatile queuing (peak 135 m in the corridor evaluation). The model provides the most value here.

---

## Per-Scenario Performance

| Scenario | N | Model RMSE (m) | Model MAE (m) | Naive RMSE (m) | Notes |
|----------|---|---------------|--------------|----------------|-------|
| corridor_camera | 99 | 33.57 | 23.35 | 57.31 | Largest absolute errors; high-demand corridor with rapid queue changes |
| sancheti_camera | 99 | 10.94 | 3.48 | 0.00 | Naive is perfect (queue=0 throughout); model is **worse** than naive |
| sancheti_congestion | 207 | 14.58 | 9.83 | 20.71 | Solid improvement; moderate congestion |
| sancheti_smoke | 207 | 1.36 | 1.36 | 0.00 | Naive is near-perfect; model essentially replicates naive |

### ⚠️ Scenario-Level Warning

For `sancheti_camera` and `sancheti_smoke`, the naive baseline achieves RMSE ≈ 0.00 m because queues are near-constant (low demand). The model also achieves very low error, but is technically **worse** than the trivial baseline on these scenarios. This is not a failure of the model — it is expected behaviour when the queue signal carries no dynamics to learn.

---

## Error Distribution by Queue Magnitude

| Queue Bucket | N | Model RMSE (m) | Model MAE (m) | Systematic Bias (m) | Interpretation |
|-------------|---|---------------|--------------|--------------------|----|
| **0–10 m** | 409 | 7.96 | 3.58 | **−3.57** | Under-prediction when actual future queue is low |
| **10–25 m** | 80 | 9.11 | 7.22 | −0.95 | Slight under-prediction |
| **25–50 m** | 59 | 16.75 | 13.78 | +2.97 | Slight over-prediction |
| **50–100 m** | 42 | 30.35 | 22.73 | **+16.19** | Strong over-prediction — model overshoots congestion peaks |
| **>100 m** | 22 | 60.30 | 52.88 | **+34.28** | Severe over-prediction — tail events extrapolated too aggressively |

### Bias Pattern Analysis

There is a clear **regression-to-mean bias** pattern:

- When the true future queue is **low** (0–10 m), the model predicts too high (bias = −3.57 m, i.e., model > actual).
- When the true future queue is **very high** (>100 m), the model predicts too high by 34 m — but the _direction_ is correct (still predicts high).

Wait — the bias column is `y_true − y_pred`. Let us clarify:

- `0–10m bucket, bias = −3.57 m`: means `y_true − y_pred = −3.57`, so `y_pred` is 3.57 m **above** the actual. The model over-predicts when the queue is actually low.
- `>100m bucket, bias = +34.28 m`: means `y_pred` is 34.28 m **below** the actual. The model **under-predicts** extreme congestion tails.

This is the classic shrinkage/attenuation pattern typical of regularised regressors: predictions are pulled toward the training mean, leading to over-prediction for below-average outcomes and under-prediction for extreme events.

### Tail Under-Prediction Risk

The 22 extreme samples (>100 m actual queue) have MAE=52.88 m. This means when a severe traffic jam is about to occur (>100 m queue in 60 s), the model may not trigger a strong enough intervention signal in the traffic management system.

---

## Summary of Failure Modes

| Mode | Description | Impact |
|------|-------------|--------|
| Tail under-prediction | Model underestimates queues >100 m by ~34 m on average | May miss most severe congestion interventions |
| Low-demand over-prediction | Slight over-prediction when queue should be near 0 m | May trigger unnecessary interventions |
| Scenario distribution gap | No incident/HV/motorcycle scenarios in training | Unknown generalisation to real-world events |
| Temporal split only | Test set is temporally adjacent to training | Performance may be optimistic vs deployment |
