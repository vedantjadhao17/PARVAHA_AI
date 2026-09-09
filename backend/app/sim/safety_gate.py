"""
backend/app/sim/safety_gate.py
──────────────────────────────
Phase 2: Hard safety constraint checker for SignalPlanCandidates.

Rules enforced here are NON-NEGOTIABLE.  Any candidate that fails is
discarded before SUMO evaluation and before operator presentation.

The gate is:
  - Importable and testable without SUMO running.
  - Stateless (no side effects).
  - Returns SafetyCheckResult, never raises on a rule failure.

Constraint catalogue (each has a unique code):
  SC-01  Yellow phases must not be modified.
  SC-02  No green phase may be shorter than MIN_GREEN_S.
  SC-03  No green phase may be longer than MAX_GREEN_S.
  SC-04  Cycle total must equal baseline ± CYCLE_TOLERANCE_S.
  SC-05  Proposal must not contain an unknown tls_id.
  SC-06  Phase count must match the baseline exactly.
  SC-07  Signal state strings must be identical to baseline (no movement changes).
"""
from __future__ import annotations

from typing import List

from app.sim.signal_plan import (
    BASELINE_PHASES,
    
    CYCLE_TOLERANCE_S,
    KNOWN_TLS_IDS,
    MIN_GREEN_S,
    MAX_GREEN_S,
    AUDITED_TLS_CONFIG,
    SafetyCheckResult,
    SignalPlanCandidate,
    SignalPlanProposal,
)


def check_candidate(candidate: SignalPlanCandidate) -> SafetyCheckResult:
    """
    Run all hard safety constraints against a single SignalPlanCandidate.
    Returns SafetyCheckResult.passed=True only if every constraint is satisfied.
    """
    violations: List[str] = []
    tls_id = candidate.tls_id

    # SC-05 — Known TLS
    if tls_id not in KNOWN_TLS_IDS:
        violations.append(
            f"SC-05: Unknown tls_id {tls_id!r}. "
            f"Known IDs: {sorted(KNOWN_TLS_IDS)}"
        )
        # Can't validate further without baseline data
        return SafetyCheckResult(passed=False, violations=violations)

    baseline = BASELINE_PHASES[tls_id]
    adjustable_idxs = set(AUDITED_TLS_CONFIG[tls_id]["adjustable_green_phases"])
    immutable_idxs = set(AUDITED_TLS_CONFIG[tls_id]["immutable_phases"])
    baseline_cycle = AUDITED_TLS_CONFIG[tls_id]["cycle_seconds"]

    # SC-06 — Phase count
    if len(candidate.phase_specs) != len(baseline):
        violations.append(
            f"SC-06: Expected {len(baseline)} phases for {tls_id}, "
            f"got {len(candidate.phase_specs)}"
        )
        return SafetyCheckResult(passed=False, violations=violations)

    for spec, base in zip(candidate.phase_specs, baseline):
        idx = spec.phase_idx

        # SC-07 — Immutable state strings
        if spec.state != base["state"]:
            violations.append(
                f"SC-07: Phase {idx} state {spec.state!r} ≠ baseline "
                f"{base['state']!r}. Signal state strings may not change."
            )

        if idx not in adjustable_idxs:
            # SC-01 — Non-adjustable phases must not be modified
            if abs(spec.duration - base["duration"]) > 0.05:
                reason = "yellow/intergreen" if idx in immutable_idxs else "non-adjustable"
                violations.append(
                    f"SC-01: Phase {idx} is a {reason} phase. "
                    f"Proposed {spec.duration}s ≠ baseline {base['duration']}s. "
                    f"{reason.capitalize()} phase durations are immutable."
                )
        else:
            # SC-02 — Minimum green
            if spec.duration < MIN_GREEN_S:
                violations.append(
                    f"SC-02: Phase {idx} green {spec.duration}s < "
                    f"minimum {MIN_GREEN_S}s"
                )
            # SC-03 — Maximum green
            if spec.duration > MAX_GREEN_S:
                violations.append(
                    f"SC-03: Phase {idx} green {spec.duration}s > "
                    f"maximum {MAX_GREEN_S}s"
                )

    # SC-04 — Cycle preservation
    total = sum(s.duration for s in candidate.phase_specs)
    if abs(total - baseline_cycle) > CYCLE_TOLERANCE_S:
        violations.append(
            f"SC-04: Cycle total {total:.1f}s deviates from "
            f"baseline {baseline_cycle}s by "
            f"{abs(total - baseline_cycle):.1f}s > tolerance "
            f"{CYCLE_TOLERANCE_S}s. "
            "Extend one green and shorten another by the same amount."
        )

    return SafetyCheckResult(passed=len(violations) == 0, violations=violations)


def check_proposal(proposal: SignalPlanProposal) -> SafetyCheckResult:
    """
    Run all hard safety constraints against every candidate in a proposal.
    Returns a combined SafetyCheckResult.  All violations from all
    candidates are collected and returned together.
    """
    all_violations: List[str] = []
    for candidate in proposal.candidates:
        result = check_candidate(candidate)
        if not result.passed:
            prefix = f"[{candidate.tls_id} / {candidate.candidate_id[:8]}] "
            all_violations.extend(prefix + v for v in result.violations)

    return SafetyCheckResult(
        passed=len(all_violations) == 0,
        violations=all_violations,
    )
