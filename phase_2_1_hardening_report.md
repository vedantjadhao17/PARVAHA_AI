# Phase 2.1 Hardening Report

## 1. Files Changed

**`backend/app/models/schemas.py`**
- **Lines:** 5-74 (removed)
- **What changed:** Removed all stale, conflicting SignalPlan schemas (`JunctionAction`, `SignalPlan`, `SafetyResult`, `CandidateResult`, `PredictedDelta`, `Recommendation`).
- **Why it changed:** To establish `backend/app/sim/signal_plan.py` as the single authoritative canonical contract for Phase 2 signal plans.

**`backend/app/main.py`**
- **Lines:** 11-16
- **What changed:** Removed the `from pravaha.contracts import Recommendation, SignalPlan, SafetyResult` import.
- **Why it changed:** The `pravaha.contracts` module was a stub and the imported objects were not actually used in the API endpoints.

**`backend/app/sim/signal_plan.py`**
- **Lines:** 39-61
- **What changed:** Added explicit configuration `AUDITED_TLS_CONFIG` detailing `cycle_seconds`, `adjustable_green_phases`, and `immutable_phases` for all three junctions.
- **Why it changed:** To make audited TLS classifications authoritative for the safety gate instead of relying on duration thresholds or state strings.
- **Lines:** 117-123 (SignalPlanProposal)
- **What changed:** Added `is_no_op: bool = False`.
- **Why it changed:** To allow explicit NO-OP capability ("NO SAFE CHANGE") without needing fake candidates.
- **Lines:** 142-205 (validate_phase_structure)
- **What changed:** Updated validation to explicitly enforce that only phases listed in `adjustable_green_phases` can be mutated. All other phases (yellow/intergreen or otherwise) must strictly maintain their baseline duration.
- **Why it changed:** Ensures non-adjustable phases cannot be tampered with.

**`backend/app/sim/safety_gate.py`**
- **Lines:** 25-104
- **What changed:** Modified `check_candidate` to use `AUDITED_TLS_CONFIG` instead of relying on `YELLOW_PHASES`. Validates that any phase not explicitly marked as `adjustable_green_phases` cannot be mutated.
- **Why it changed:** Aligns the safety gate with the newly defined authoritative `AUDITED_TLS_CONFIG`.

**`backend/app/models/recommendation_store.py`**
- **Lines:** 48-63
- **What changed:** Removed `"ROLLED_BACK"` from the set of allowed transitions out of `"APPROVED"`.
- **Why it changed:** The state machine requires the plan to be `APPLIED` before it can be `ROLLED_BACK`.

**`backend/tests/test_signal_plan.py`**
- **Lines:** Updated throughout the file (Lines 1-525)
- **What changed:** Added extensive state machine tests to verify rejection of illegal transitions (e.g., `APPROVED → ROLLED_BACK`). Added adversarial safety tests for `min_green`, `max_green`, `phase_removal`, `phase_reordering`, `negative_duration`, and verified `floating_point_cycle_tolerance`.
- **Why it changed:** To guarantee edge cases, illegal mutations, and invalid transitions strictly fail as required.

---

## 2. Audited TLS Configuration

The authoritative TLS configuration for the corridor:

### **J1_SAN**
- **TLS ID:** `cluster_13546492148_1838721956`
- **Cycle:** 90.0s
- **Adjustable Phases:** `[0, 2]`
- **Immutable Phases:** `[1, 3]`

### **J2_SJM**
- **TLS ID:** `cluster_2061304035_245647208`
- **Cycle:** 90.0s
- **Adjustable Phases:** `[0, 2]`
- **Immutable Phases:** `[1, 3]`

### **J3_SAP**
- **TLS ID:** `cluster_245647168_3238255150_3495323634`
- **Cycle:** 90.0s
- **Adjustable Phases:** `[0, 2, 4, 6]`
- **Immutable Phases:** `[1, 3, 5, 7]`

---

## 3. Safety Tests

Output of running the targeted Phase 2.1 tests:
```bash
$ PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_signal_plan.py -v
...
backend/tests/test_signal_plan.py::TestSafetyGate::test_sc01_yellow_duration_modified_fails PASSED [ 46%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_sc05_unknown_tls_fails PASSED [ 48%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_sc02_min_green_fails PASSED [ 50%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_sc03_max_green_fails PASSED [ 51%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_phase_removal_fails PASSED [ 53%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_phase_reordering_fails PASSED [ 55%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_negative_duration_fails PASSED [ 56%]
backend/tests/test_signal_plan.py::TestSafetyGate::test_floating_point_cycle_tolerance PASSED [ 58%]
...
======================== 54 passed in 0.08s ========================
```

---

## 4. Regression Testing

Output of running the entire backend test suite:
```bash
$ PYTHONPATH=backend backend/venv/bin/pytest backend/tests/ -v
...
backend/tests/test_integration.py::test_approve_apply_integration PASSED [  1%]
backend/tests/test_manager_smoke.py::test_manager_initialization PASSED  [  3%]
...
backend/tests/test_verification.py::test_operator_log_immutability PASSED [ 98%]
backend/tests/test_verification.py::test_safety_gate_rejection PASSED    [100%]
======================== 58 passed, 5 warnings in 3.59s ========================
```

**Verifications:**
- **Phase 0 approval endpoint remains 501:** Intact. `main.py` was not modified beyond import cleanup. The endpoint remains a stub.
- **Phase 0 TraCI reconnect behavior:** Intact. `manager.py` was not modified.
- **Phase 1 ML inference:** Intact. Tests involving offline inference passed successfully.

---

## 5. Schema Architecture

- **Canonical SignalPlan Contract:** `backend/app/sim/signal_plan.py` is now the single source of truth for the Signal Plan representation. It contains all schemas (`SignalPlanCandidate`, `SignalPlanProposal`, `ApprovalRequest`, `CandidateEvaluation`, etc.).
- **API Schemas:** `backend/app/models/schemas.py` holds ONLY API response schemas (`AlertSchema`, `OperatorLogSchema`, `DeviceSchema`, `JunctionSchema`).
- **Duplicate/Conflicting Models:** All conflicting models (`JunctionAction`, `SignalPlan`, `SafetyResult`, `CandidateResult`, `PredictedDelta`, `Recommendation`) have been successfully removed from `schemas.py`.

---

## 6. NO-OP Behavior

A "NO SAFE CHANGE" / "Keep current signal plan" recommendation is now cleanly represented directly on the `SignalPlanProposal` via the `is_no_op` boolean field.

**Example:**
If the Candidate Generator determines no configuration improves upon the baseline safely:
```python
proposal = SignalPlanProposal(
    candidates=[], # Empty or containing just the baseline 
    source_states=[current_state],
    trigger_reason="predicted_spillback:J3_SAP",
    is_no_op=True # Explicitly indicates NO SAFE CHANGE
)
```

---

## 7. Explicit Limitations

- All hardening verifies strictly through unit testing inside `pytest`. No front-end logic was actively impacted by removing backend Pydantic models as long as the endpoints were left untouched.
- Floating-point tolerance is explicitly checked inside the Pydantic validators (`CYCLE_TOLERANCE_S = 0.5s`).
- The Phase 2.3 `POST /api/recommendations/{id}/approve` currently returns a 501 HTTP exception. To wire this with `ApprovalRequest`, it will need future schema translations.
