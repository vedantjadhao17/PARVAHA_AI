# Phase 3 Architecture Audit

## 1. Current Data Flow
- `backend/app/sim/manager.py` connects to TraCI, extracts lane-level metrics, and converts them to junction-level metrics via `LiveFeatureExtractor` (matches offline training methodology).
- Metrics are passed to `QueueForecaster` (loaded with XGBoost model) and `SpillbackEngine` for deterministic checks.
- If an anomaly is predicted, `DecisionEngine` triggers `CandidateGenerator` to create signal plan variations against `BASELINE_PHASES`.
- `CounterfactualEvaluator` spins up a parallel SUMO instance using `traci.simulation.saveState` from the live network and evaluates the candidates.
- Safe, winning candidates are packaged into an `ApprovalRequest` and saved into `RecommendationStore`.

## 2. Current Recommendation Lifecycle
- `PENDING`: Stored in memory by `DecisionEngine`.
- `APPROVED` / `REJECTED`: FastAPI endpoints trigger transition. Approval enforces SafetyGate checks and a 10-minute TTL.
- `APPLIED`: TraCI confirms deployment of the updated signal plan.

## 3. Current Signal Application Lifecycle
- When approved, `main.py` fetches the associated `BaselineController` from `sim_manager.controllers`.
- Calls `deploy_new_plan(green_phase_deltas)` mapping the candidate's changes into SUMO `traci.trafficlight.setCompleteRedYellowGreenDefinition`.

## 4. Current Rollback Capabilities
- Partial/Conceptual. `ApprovalRequest` has a `rollback_candidates` field (which stores the HOLD plan). `RecommendationStore` has a `ROLLED_BACK` state.
- **Gap:** No explicit rollback endpoint. No automatic rollback watchdog. No storage of what the EXACT previous TraCI state was at the moment of application (just relying on `BASELINE_PHASES`).

## 5. Current Telemetry Persistence
- `telemetry_history` SQLite table logs simulation metrics at 1Hz or configured intervals.
- `operator_log` records approvals/rejections immutably.
- **Gap:** No specific table or tracker directly correlates a recommendation application to its before/after performance (e.g. +30s, +60s, +120s snapshots).

## 6. Current Baseline Implementation
- `signal_plan.py` hardcodes `AUDITED_TLS_CONFIG` and `BASELINE_PHASES`.
- `CounterfactualEvaluator` always simulates a `HOLD` candidate for baseline scoring.
- **Gap:** Once applied, the live system stops comparing against HOLD (since HOLD is counterfactual, and we only see the live outcome of the intervention).

## 7. Current Gaps to Address in Phase 3
- **OutcomeTracker:** Needs to observe the real network for 120s post-application to gather real `queue_length_m`, `vehicle_count`, and `avg_speed_kmh`. Needs to compare against the expected/HOLD counterfactual scores.
- **Rollback API:** Needs a `/api/recommendations/{id}/rollback` endpoint and policy.
- **Stale Recommendation Protection:** Already partially implemented in Phase 2.3 (TTL check), but needs stricter checks (e.g. TLS program matches).
- **Concurrent Recommendation Protection:** Needs to prevent overlapping modifications.
- **Explainability:** Needs structured explanation fields in the `ApprovalRequest` to inform the frontend accurately instead of just string messages.
- **Experimental Harness:** Needs `evaluate_phase3.py` for automated scenario validation.

## 8. Exact Files Involved
- `backend/app/db/database.py` (needs `RecommendationOutcome` schema)
- `backend/app/sim/outcome_tracker.py` (New)
- `backend/app/sim/manager.py` (Integrate `OutcomeTracker`)
- `backend/app/models/recommendation_store.py` (Expand state protection)
- `backend/app/sim/decision_engine.py` (Enrich `ApprovalRequest` with explainability fields)
- `backend/app/sim/signal_plan.py` (Update `ApprovalRequest` schema)
- `backend/app/main.py` (Add `/rollback`, `evaluation/summary` endpoints)
- `backend/ml/evaluate_phase3.py` (New harness)
- `frontend/src/components/RecommendationPanel.tsx` (Display enriched explanation)
- `frontend/src/pages/CommandMap.tsx` (Add System Status banner)
