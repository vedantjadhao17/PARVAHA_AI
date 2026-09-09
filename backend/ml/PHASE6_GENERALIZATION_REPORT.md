# PHASE6_GENERALIZATION_REPORT.md

## Executive Summary
Evaluated existing XGBoost model on true unseen TEST scenarios (N=5220 rows).

## Overall Performance
| Metric | XGBoost | Naive Baseline |
|--------|---------|----------------|
| RMSE | 18.45 m | 22.05 m |
| MAE | 10.02 m | 11.16 m |
| R² | 0.595 | 0.421 |
| Mean Error | 1.91 m | -0.91 m |
| Median AE | 5.35 m | 5.00 m |
| Max AE | 156.68 m | 190.00 m |


## Per-Category Results
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

## Large-Queue Diagnostic Report
| Queue Bucket | N | MAE | RMSE | Bias (Mean Error) |
|--------------|---|-----|------|-------------------|
| 0–25 m | 4503 | 6.70 m | 10.62 m | 4.13 m |
| 25–50 m | 370 | 16.87 m | 20.14 m | -5.86 m |
| 50–100 m | 203 | 38.12 m | 46.80 m | -23.13 m |
| 100–150 m | 53 | 68.81 m | 75.26 m | -16.38 m |
| 150 m+ | 91 | 49.55 m | 64.07 m | -10.33 m |

## Per-Scenario Results
| Scenario | N | RMSE | Naive RMSE | MAE | Bias |
|----------|---|------|------------|-----|------|
| TEST_combined_extreme_hetero_14413 | 435 | 36.46 | 46.80 | 21.49 | 1.36 |
| TEST_combined_high_heavy_95114 | 435 | 17.00 | 21.30 | 10.37 | -2.26 |
| TEST_combined_high_incident_78709 | 435 | 16.33 | 20.07 | 10.45 | 3.10 |
| TEST_combined_high_moto_92913 | 435 | 14.62 | 19.10 | 9.45 | 3.01 |
| TEST_combined_incident_heavy_29105 | 435 | 10.43 | 11.94 | 6.66 | 3.20 |
| TEST_extreme_55400 | 435 | 33.21 | 39.39 | 19.61 | -3.04 |
| TEST_heavy_vehicle_87238 | 435 | 9.83 | 10.02 | 6.34 | 3.09 |
| TEST_high_12502 | 435 | 15.59 | 17.22 | 10.39 | 2.64 |
| TEST_incident_28431 | 435 | 11.20 | 10.05 | 7.00 | 2.98 |
| TEST_low_10925 | 435 | 8.61 | 6.82 | 5.22 | 2.72 |
| TEST_motorcycle_50334 | 435 | 11.32 | 10.74 | 6.88 | 3.09 |
| TEST_normal_82452 | 435 | 10.21 | 8.41 | 6.37 | 2.96 |
