# PHASE6_DATASET_AUDIT.md

## Corpus Expansion
- Scenarios Generated: 36
- Scenarios Validated (Passed physical checks): 36
- Scenarios Rejected (Re-generated): 0

## True Scenario-Level Split
The corpus was split strictly by scenario_id.
Phase 6 evaluates the existing model on 12 strictly held-out test scenarios.
- **TRAIN Scenarios**: 12
- **VALIDATION Scenarios**: 12
- **TEST Scenarios**: 12

## Leakage Audit
- train ∩ validation = ∅ (PASS)
- train ∩ test = ∅ (PASS)
- validation ∩ test = ∅ (PASS)

## Validated Scenarios
The TEST set (N=12) contains precisely:
- TEST_normal_82452 (Cat: normal, Seed: 82452)
- TEST_low_10925 (Cat: low, Seed: 10925)
- TEST_high_12502 (Cat: high, Seed: 12502)
- TEST_extreme_55400 (Cat: extreme, Seed: 55400)
- TEST_incident_28431 (Cat: incident, Seed: 28431)
- TEST_heavy_vehicle_87238 (Cat: heavy_vehicle, Seed: 87238)
- TEST_motorcycle_50334 (Cat: motorcycle, Seed: 50334)
- TEST_combined_high_incident_78709 (Cat: combined_high_incident, Seed: 78709)
- TEST_combined_high_heavy_95114 (Cat: combined_high_heavy, Seed: 95114)
- TEST_combined_high_moto_92913 (Cat: combined_high_moto, Seed: 92913)
- TEST_combined_incident_heavy_29105 (Cat: combined_incident_heavy, Seed: 29105)
- TEST_combined_extreme_hetero_14413 (Cat: combined_extreme_hetero, Seed: 14413)

These 12 scenarios were never used for training, feature selection, hyperparameter tuning, or model selection.
