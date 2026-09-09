# PHASE 5 DATA AUDIT

## Dataset Overview

| Attribute | Value |
|-----------|-------|
| **Train rows** | 2,436 |
| **Test rows** | 612 |
| **Total rows** | 3,048 |
| **Total features** | 8 input + 1 target + 5 metadata columns = 14 columns |
| **NaN values** | 0 (all NaN rows dropped by build_dataset.py) |
| **Scenarios** | 4 |
| **Junctions** | 3 |

## Column Schema

| Column | Type | Role |
|--------|------|------|
| id | int | DB row id (not used in training) |
| recorded_at | timestamp | Wall-clock time (not used) |
| scenario_id | string | Scenario label |
| simulation_time_s | float | Time within simulation (s) |
| junction_id | string | Junction identifier |
| queue_length_m | float | **Feature** — current queue (m) |
| vehicle_count | int | **Feature** — active vehicles near junction |
| avg_speed_kmh | float | **Feature** — average speed (km/h) |
| queue_minus_5 | float | **Feature** — queue 5 s ago |
| queue_minus_10 | float | **Feature** — queue 10 s ago |
| queue_minus_15 | float | **Feature** — queue 15 s ago |
| queue_minus_20 | float | **Feature** — queue 20 s ago |
| queue_slope | float | **Feature** — (q_now − q_minus_20) / 20.0 |
| target_queue_60s | float | **Target** — queue 60 s in future |

## Scenario Distribution

| Scenario | Category | Train Rows | Test Rows | Time Range Train (s) | Time Range Test (s) |
|----------|----------|-----------|----------|----------------------|---------------------|
| sancheti_smoke | LOW_DEMAND | 825 | 207 | 20–1395 | 1400–1740 |
| sancheti_congestion | HIGH_DEMAND | 825 | 207 | 20–1395 | 1400–1740 |
| corridor_camera | CAMERA/HIGH | 393 | 99 | 20–675 | 680–840 |
| sancheti_camera | CAMERA/LOW | 393 | 99 | 20–675 | 680–840 |

## ⚠️ CRITICAL FINDING: Train/Test Split Methodology

> **The same 4 scenarios appear in BOTH train and test sets.**

The split is **temporal within each scenario** (chronological 80/20 per scenario×junction group), NOT a scenario-level separation.

### What this means in practice

- **Test data is from the same demand distributions as training data** — just later timesteps in the same simulation.
- **Test performance is likely optimistic** — the model has seen the same route files, same junctions, same vehicle arrival patterns (just in earlier time windows).
- **True generalisation cannot be measured** from this dataset alone. A scenario-holdout evaluation would require running new simulations with entirely different route files.

### Why it happened

`build_dataset.py` groups by `(scenario_id, junction_id)`, sorts by `simulation_time_s`, and takes the last 20% of each group as test. This is a legitimate chronological split but does not prevent scenario overlap.

### Correct interpretation

Results should be stated as: *"The model achieves RMSE=16.56 m on the chronological held-out portion (last 20% of timesteps) of the same 4 scenarios used for training."*

Claims that CANNOT be made: "The model generalises to unseen scenarios."

## Missing Scenario Classes

The following scenario types would be required for true generalisation testing but no SUMO route files exist for them:

| Missing Scenario | Why It Matters |
|-----------------|---------------|
| Incident / blockage | Tests sudden queue spike — distribution shift from training |
| Heavy vehicle mix | Different stopping distances, different queue density |
| Motorcycle-dominant | Indian traffic reality — low gap acceptance |
| Combined stress | Incident + high demand simultaneously |

## Data Quality

- **No NaN values** in either split.
- **No duplicate (scenario, junction, simulation_time_s)** rows in train.
- **Temporal monotonicity preserved** per group (no time-order violations).
- **Train/test do not overlap in time** per scenario-junction group (confirmed: train_max < test_min for every group).
