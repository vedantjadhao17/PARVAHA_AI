# PRAVAHA-AI SIH 2026 DEMO RUNBOOK

Status: PRAVAHA-AI Phase 8 COMPLETE — RELEASE CANDIDATE FROZEN FOR CONTROLLED SIH 2026 DEMONSTRATION AND EVALUATION.

## 1. NORMAL SCENARIO
**Command**: `./scripts/run_demo.sh NORMAL`
**What to demonstrate**:
- Natural bidirectional heterogeneous urban traffic.
- Continuous, real-time Live Telemetry mapping via TraCI.
- Watch risk state remain firmly in **WATCH** (max 110m queue).
- Note that no intervention is generated because physical constraints are safely within bounds.

## 2. RISING_CONGESTION (PRIMARY DEMO)
**Command**: `./scripts/run_demo.sh RISING_CONGESTION`
**Demo Sequence**:
1. **Start**: Traffic begins balanced and smoothly clears intersections.
2. **When to wait**: The simulation gradually intensifies. Proceed to T=450s (Phase 3 of the scenario).
3. **What telemetry to watch**: Monitor the J3 (Shivaji Road-Apte Path) live queue and +60s XGBoost Forecast.
4. **When HIGH should appear**: Around T=450s, the forecast will breach 181.5m, bringing predicted capacity ratio > 0.75. The `HIGH` alert organically appears on the dashboard.
5. **Pending Recommendation**: The Corridor Decision Engine triggers, processing candidates through the SafetyGate and Counterfactual evaluator. A `PENDING` recommendation card appears.
6. **Approval**: Operator manually reviews the rationale, HOLD baseline, and Counterfactual projection. Operator clicks 'Approve'.
7. **Signal Change**: System transitions to `APPROVED` -> `APPLIED`. Observe the raw signal state array natively transition in the UI.
8. **Rollback**: Operator triggers a Rollback. System restores exact prior canonical signal plan seamlessly.

## 3. SPILLBACK (BACKUP STRESS SCENARIO)
**Command**: `./scripts/run_demo.sh SPILLBACK`
**Notes**: SPILLBACK generated 7 SUMO teleports under extreme sustained demand and is classified as an extreme stress/backup scenario rather than the primary live demonstration. Use only to prove the upper operational bounds of the SafetyGate under absolute gridlock.
