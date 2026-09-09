# PHASE 6 RETRAINING DECISION

## Framework Analysis
- **Overall Metrics**: Phase 6 evaluates the existing model on 12 strictly held-out test scenarios.
- **Naive Comparison**: The existing model beats the naive baseline (18.45m vs 22.05m).
- **Large-Queue Bias**: The evaluation indicates increased forecast error in the >150m queue regime (Bias = -10.33m, RMSE = 64.07m), demonstrating feature saturation. The model has never been trained on these extreme states.
- **Systematic Failure Patterns**: The model conservatively predicts mean queues for unprecedented tail events, resulting in FORECAST_FAILURE classification on extreme outliers.

## Decision: RETRAINING RECOMMENDED BUT DEFERRED

### Why the existing model is retained
1. The overall held-out performance remains useful for in-distribution operations.
2. It beats the naive baseline consistently.
3. No evidence requires immediate replacement because the safety layers remain resilient even when the forecast degrades. 

### Why retraining is recommended
1. There is a systematic extreme-tail error.
2. There is insufficient representation of very large queues in the original corpus.
3. The feature distribution limits the model's accuracy on >150m extrapolations.

### Model Versioning Contract
- `queue_forecast_model.json` (Phase 5) remains active.
- Future retraining will use the strict Train/Val/Test splits generated in Phase 6.
