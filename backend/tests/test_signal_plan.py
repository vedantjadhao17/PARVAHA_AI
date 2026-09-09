"""
backend/tests/test_signal_plan.py
──────────────────────────────────
Phase 2.1 unit tests for the SignalPlan contract, SafetyGate, and
RecommendationStore.

All tests run without SUMO.  No TraCI imports in this file.
"""
import pytest
from datetime import datetime, timezone

# ─── signal_plan imports ───────────────────────────────────────────────────
from app.sim.signal_plan import (
    
    BASELINE_PHASES,
    MAX_GREEN_S,
    MIN_GREEN_S,
    AUDITED_TLS_CONFIG,
    ApprovalRequest,
    CandidateEvaluation,
    PhaseSpec,
    SafetyCheckResult,
    SignalPlanCandidate,
    SignalPlanProposal,
    SourceState,
)
from app.sim.safety_gate import check_candidate, check_proposal
from app.models.recommendation_store import RecommendationStore


# ─── helpers ──────────────────────────────────────────────────────────────

TLS_J1 = "cluster_13546492148_1838721956"
TLS_J2 = "cluster_2061304035_245647208"
TLS_J3 = "cluster_245647168_3238255150_3495323634"

def baseline_candidate(tls_id: str, junction_id: str = "J_TEST") -> SignalPlanCandidate:
    return SignalPlanCandidate.from_baseline(tls_id, junction_id, rationale="test-baseline")

def make_source_state(tls_id: str = TLS_J1) -> SourceState:
    return SourceState(
        junction_id="J1_SAN",
        tls_id=tls_id,
        simulation_time_s=100.0,
        queue_m=30.0,
        predicted_queue_60s_m=80.0,
        predicted_capacity_ratio=0.9,
        vehicle_count=12,
        avg_speed_kmh=15.0,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1.  PhaseSpec
# ═══════════════════════════════════════════════════════════════════════════

class TestPhaseSpec:
    def test_valid_phase(self):
        p = PhaseSpec(phase_idx=0, duration=39.0, state="GGGrrr", is_yellow=False)
        assert p.duration == 39.0

    def test_duration_zero_rejected(self):
        with pytest.raises(Exception):
            PhaseSpec(phase_idx=0, duration=0.0, state="GGGrrr", is_yellow=False)

    def test_negative_duration_rejected(self):
        with pytest.raises(Exception):
            PhaseSpec(phase_idx=0, duration=-5.0, state="GGGrrr", is_yellow=False)

    def test_duration_rounded_to_one_decimal(self):
        p = PhaseSpec(phase_idx=0, duration=39.123, state="GGGrrr", is_yellow=False)
        assert p.duration == 39.1


# ═══════════════════════════════════════════════════════════════════════════
# 2.  SignalPlanCandidate — from_baseline factory
# ═══════════════════════════════════════════════════════════════════════════

class TestFromBaseline:
    @pytest.mark.parametrize("tls_id", [TLS_J1, TLS_J2, TLS_J3])
    def test_baseline_candidate_is_valid(self, tls_id):
        c = baseline_candidate(tls_id)
        # Cycle must equal baseline
        total = sum(s.duration for s in c.phase_specs)
        assert abs(total - 90.0) < 0.5

    def test_baseline_candidate_j1_has_4_phases(self):
        c = baseline_candidate(TLS_J1)
        assert len(c.phase_specs) == 4

    def test_baseline_candidate_j3_has_8_phases(self):
        c = baseline_candidate(TLS_J3)
        assert len(c.phase_specs) == 8

    def test_baseline_green_phase_deltas_are_zero(self):
        c = baseline_candidate(TLS_J1)
        assert all(d == 0.0 for d in c.green_phase_deltas.values())

    def test_as_traci_phase_dict_empty_for_baseline(self):
        c = baseline_candidate(TLS_J1)
        assert c.as_traci_phase_dict() == {}

    def test_unknown_tls_id_rejected(self):
        with pytest.raises(Exception, match="cluster_BOGUS_999"):
            SignalPlanCandidate.from_baseline("cluster_BOGUS_999", "J_FAKE")


# ═══════════════════════════════════════════════════════════════════════════
# 3.  SignalPlanCandidate — with_green_shift factory
# ═══════════════════════════════════════════════════════════════════════════

class TestGreenShift:
    def test_valid_shift_j1_extend_phase0_shorten_phase2(self):
        c = SignalPlanCandidate.with_green_shift(
            tls_id=TLS_J1,
            junction_id="J1_SAN",
            extend_phase=0,
            shorten_phase=2,
            delta_s=10.0,
        )
        # Phase 0 should now be 49s, phase 2 should be 29s
        durations = {s.phase_idx: s.duration for s in c.phase_specs}
        assert durations[0] == 49.0
        assert durations[2] == 29.0
        # Cycle preserved
        total = sum(s.duration for s in c.phase_specs)
        assert abs(total - 90.0) < 0.5

    def test_shift_creates_nonzero_traci_dict(self):
        c = SignalPlanCandidate.with_green_shift(
            TLS_J1, "J1_SAN", extend_phase=0, shorten_phase=2, delta_s=10.0
        )
        d = c.as_traci_phase_dict()
        assert 0 in d and d[0] == 49.0
        assert 2 in d and d[2] == 29.0

    def test_shift_violates_min_green_rejected(self):
        # Shorten phase 2 below MIN_GREEN_S (39 - 30 = 9 < 10)
        with pytest.raises(Exception):
            SignalPlanCandidate.with_green_shift(
                TLS_J1, "J1_SAN", extend_phase=0, shorten_phase=2, delta_s=30.0
            )

    def test_shift_violates_max_green_rejected(self):
        # Extend phase 0 beyond MAX_GREEN_S (39 + 22 = 61 > 60)
        with pytest.raises(Exception):
            SignalPlanCandidate.with_green_shift(
                TLS_J1, "J1_SAN", extend_phase=0, shorten_phase=2, delta_s=22.0
            )

    def test_cannot_shift_yellow_phase(self):
        with pytest.raises(Exception, match="yellow"):
            SignalPlanCandidate.with_green_shift(
                TLS_J1, "J1_SAN", extend_phase=1, shorten_phase=2, delta_s=5.0
            )

    def test_broken_cycle_rejected_at_construction(self):
        """Manually build a candidate with broken cycle and confirm rejection."""
        baseline = BASELINE_PHASES[TLS_J1]
        yellow_idxs = set(AUDITED_TLS_CONFIG[TLS_J1]["immutable_phases"])
        bad_specs = []
        for b in baseline:
            dur = b["duration"]
            if b["phase_idx"] == 0:
                dur = 50.0  # +11, but phase 2 not shortened
            bad_specs.append(PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=dur,
                state=b["state"],
                is_yellow=(b["phase_idx"] in yellow_idxs),
            ))
        with pytest.raises(Exception, match="Cycle"):
            SignalPlanCandidate(
                tls_id=TLS_J1,
                junction_id="J1_SAN",
                phase_specs=bad_specs,
            )

    def test_mutated_state_string_rejected(self):
        """Changing a state string must be rejected (SC-07)."""
        baseline = BASELINE_PHASES[TLS_J1]
        yellow_idxs = set(AUDITED_TLS_CONFIG[TLS_J1]["immutable_phases"])
        bad_specs = []
        for b in baseline:
            state = b["state"]
            if b["phase_idx"] == 0:
                state = "GGGGrr"  # one extra G — movement change
            bad_specs.append(PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=b["duration"],
                state=state,
                is_yellow=(b["phase_idx"] in yellow_idxs),
            ))
        with pytest.raises(Exception, match="state"):
            SignalPlanCandidate(
                tls_id=TLS_J1,
                junction_id="J1_SAN",
                phase_specs=bad_specs,
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4.  SafetyCheckResult
# ═══════════════════════════════════════════════════════════════════════════

class TestSafetyCheckResult:
    def test_passing_result_requires_empty_violations(self):
        r = SafetyCheckResult(passed=True, violations=[])
        assert r.passed is True

    def test_passing_with_violations_rejected(self):
        with pytest.raises(Exception):
            SafetyCheckResult(passed=True, violations=["some violation"])

    def test_failing_result_with_violations(self):
        r = SafetyCheckResult(passed=False, violations=["SC-01: yellow modified"])
        assert not r.passed
        assert len(r.violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5.  SafetyGate — check_candidate
# ═══════════════════════════════════════════════════════════════════════════

class TestSafetyGate:
    def test_baseline_passes_all_constraints(self):
        for tls_id in [TLS_J1, TLS_J2, TLS_J3]:
            c = baseline_candidate(tls_id)
            result = check_candidate(c)
            assert result.passed, f"{tls_id}: {result.violations}"

    def test_valid_shift_passes(self):
        c = SignalPlanCandidate.with_green_shift(
            TLS_J1, "J1_SAN", extend_phase=0, shorten_phase=2, delta_s=10.0
        )
        result = check_candidate(c)
        assert result.passed, result.violations

    def test_sc01_yellow_duration_modified_fails(self):
        """SC-01: yellow phase duration changed."""
        baseline = BASELINE_PHASES[TLS_J1]
        yellow_idxs = set(AUDITED_TLS_CONFIG[TLS_J1]["immutable_phases"])
        specs = []
        for b in baseline:
            dur = b["duration"]
            if b["phase_idx"] == 1:
                dur = 10.0  # modify yellow
            specs.append(PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=dur,
                state=b["state"],
                is_yellow=(b["phase_idx"] in yellow_idxs),
            ))
        # Pydantic validator will catch this before we even call safety gate
        with pytest.raises(Exception):
            SignalPlanCandidate(tls_id=TLS_J1, junction_id="J1_SAN", phase_specs=specs)

    def test_sc05_unknown_tls_fails(self):
        """SC-05: unknown tls_id."""
        # Pydantic catches this at construction
        with pytest.raises(Exception, match="Unknown tls_id"):
            SignalPlanCandidate(
                tls_id="cluster_BOGUS",
                junction_id="J_FAKE",
                phase_specs=[],
            )


    def test_sc02_min_green_fails(self):
        # green = 9 must fail
        with pytest.raises(Exception, match="minimum"):
            SignalPlanCandidate.with_green_shift(
                TLS_J1, "J1_SAN", extend_phase=2, shorten_phase=0, delta_s=30.0
            )
            
    def test_sc03_max_green_fails(self):
        # green = 61 must fail
        with pytest.raises(ValueError, match="maximum"):
            SignalPlanCandidate.with_green_shift(
                TLS_J1, "J1_SAN", extend_phase=0, shorten_phase=2, delta_s=22.0
            )

    def test_phase_removal_fails(self):
        baseline = BASELINE_PHASES[TLS_J1]
        immutable_idxs = set(AUDITED_TLS_CONFIG[TLS_J1]["immutable_phases"])
        bad_specs = [
            PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=b["duration"],
                state=b["state"],
                is_yellow=(b["phase_idx"] in immutable_idxs),
            )
            for b in baseline[:-1] # Remove last phase
        ]
        with pytest.raises(ValueError, match="Expected"):
            SignalPlanCandidate(tls_id=TLS_J1, junction_id="J1_SAN", phase_specs=bad_specs)
            
    def test_phase_reordering_fails(self):
        baseline = BASELINE_PHASES[TLS_J1]
        immutable_idxs = set(AUDITED_TLS_CONFIG[TLS_J1]["immutable_phases"])
        specs = [
            PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=b["duration"],
                state=b["state"],
                is_yellow=(b["phase_idx"] in immutable_idxs),
            )
            for b in baseline
        ]
        # Swap phase 1 and 2
        specs[1], specs[2] = specs[2], specs[1]
        with pytest.raises(ValueError, match="must be in order"):
            SignalPlanCandidate(tls_id=TLS_J1, junction_id="J1_SAN", phase_specs=specs)

    def test_negative_duration_fails(self):
        with pytest.raises(ValueError, match="greater than 0"):
            PhaseSpec(phase_idx=0, duration=-1.0, state="GGGrrr", is_yellow=False)

    def test_floating_point_cycle_tolerance(self):
        # Test tolerance defined as CYCLE_TOLERANCE_S = 0.5
        # Total cycle should be 90.0. Let's make it 90.4
        c = baseline_candidate(TLS_J1, "J1_SAN")
        # Direct modification bypassing with_green_shift which balances
        baseline = BASELINE_PHASES[TLS_J1]
        immutable_idxs = set(AUDITED_TLS_CONFIG[TLS_J1]["immutable_phases"])
        specs = []
        for b in baseline:
            dur = b["duration"]
            if b["phase_idx"] == 0:
                dur = 39.4  # Cycle 90.4
            specs.append(PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=dur,
                state=b["state"],
                is_yellow=(b["phase_idx"] in immutable_idxs),
            ))
        c2 = SignalPlanCandidate(tls_id=TLS_J1, junction_id="J1_SAN", phase_specs=specs)
        res = check_candidate(c2)
        assert res.passed is True
        
        # 90.6 should fail (> 0.5 tolerance)
        specs[0].duration = 39.6
        with pytest.raises(ValueError, match="deviates from baseline"):
            c3 = SignalPlanCandidate(tls_id=TLS_J1, junction_id="J1_SAN", phase_specs=specs)

    def test_check_proposal_aggregates_violations(self):
        """A proposal with one valid and one that would fail if we could smuggle it in."""
        c_good = baseline_candidate(TLS_J1)
        c_good2 = baseline_candidate(TLS_J2)
        proposal = SignalPlanProposal(
            candidates=[c_good, c_good2],
            source_states=[make_source_state()],
            trigger_reason="test",
        )
        result = check_proposal(proposal)
        assert result.passed

    def test_duplicate_junction_in_proposal_rejected(self):
        c1 = baseline_candidate(TLS_J1, "J1_SAN")
        c2 = baseline_candidate(TLS_J1, "J1_SAN")  # same TLS twice
        with pytest.raises(Exception, match="Duplicate"):
            SignalPlanProposal(
                candidates=[c1, c2],
                source_states=[make_source_state()],
                trigger_reason="test",
            )


# ═══════════════════════════════════════════════════════════════════════════
# 6.  RecommendationStore
# ═══════════════════════════════════════════════════════════════════════════

def _make_approval_request(rec_id: str | None = None) -> ApprovalRequest:
    c = baseline_candidate(TLS_J1, "J1_SAN")
    safety_ok = SafetyCheckResult(passed=True, violations=[])
    eval_ = CandidateEvaluation(
        candidate_id=c.candidate_id,
        tls_id=TLS_J1,
        safety=safety_ok,
        avg_queue_m=30.0,
        max_queue_m=45.0,
        total_halting_vehicles=100,
        evaluation_horizon_s=60.0,
        score=0.5,
    )
    proposal = SignalPlanProposal(
        candidates=[c],
        source_states=[make_source_state()],
        trigger_reason="test",
    )
    kwargs: dict = dict(
        trigger_reason="test",
        source_states=[make_source_state()],
        proposal=proposal,
        evaluations=[eval_],
        selected_candidate_id=c.candidate_id,
        rollback_candidates=[baseline_candidate(TLS_J1, "J1_SAN")],
        safety=safety_ok,
        operator_rationale="Extend phase 0 to reduce predicted spillback at J3_SAP.",
    )
    if rec_id:
        kwargs["recommendation_id"] = rec_id
    return ApprovalRequest(**kwargs)


class TestRecommendationStore:
    def test_add_and_get(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        assert s.get(req.recommendation_id) is not None

    def test_get_nonexistent_returns_none(self):
        s = RecommendationStore()
        assert s.get("nonexistent-id") is None

    def test_get_or_raise_raises_on_missing(self):
        s = RecommendationStore()
        with pytest.raises(KeyError):
            s.get_or_raise("bogus")

    def test_duplicate_id_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request("fixed-id-abc")
        s.add(req)
        with pytest.raises(KeyError, match="already exists"):
            s.add(req)

    def test_valid_status_transition_pending_to_approved(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        updated = s.update_status(req.recommendation_id, "APPROVED")
        assert updated.status == "APPROVED"

    def test_valid_status_transition_approved_to_applied(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        updated = s.update_status(req.recommendation_id, "APPLIED")
        assert updated.status == "APPLIED"

    def test_invalid_transition_pending_to_applied_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        with pytest.raises(ValueError, match="Cannot transition"):
            s.update_status(req.recommendation_id, "APPLIED")

    def test_terminal_state_rejected_cannot_transition(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "REJECTED")
        with pytest.raises(ValueError, match="Cannot transition"):
            s.update_status(req.recommendation_id, "PENDING")


    def test_invalid_transition_pending_to_rollback_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "ROLLED_BACK")

    def test_invalid_transition_approved_to_pending_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "PENDING")

    def test_invalid_transition_approved_to_rollback_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "ROLLED_BACK")

    def test_invalid_transition_applied_to_pending_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        s.update_status(req.recommendation_id, "APPLIED")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "PENDING")

    def test_invalid_transition_applied_to_approved_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        s.update_status(req.recommendation_id, "APPLIED")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "APPROVED")

    def test_invalid_transition_rolled_back_to_pending_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        s.update_status(req.recommendation_id, "APPLIED")
        s.update_status(req.recommendation_id, "ROLLED_BACK")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "PENDING")

    def test_invalid_transition_rolled_back_to_approved_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        s.update_status(req.recommendation_id, "APPLIED")
        s.update_status(req.recommendation_id, "ROLLED_BACK")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "APPROVED")

    def test_invalid_transition_rolled_back_to_applied_rejected(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        s.update_status(req.recommendation_id, "APPLIED")
        s.update_status(req.recommendation_id, "ROLLED_BACK")
        with pytest.raises(ValueError):
            s.update_status(req.recommendation_id, "APPLIED")
            
    def test_valid_transition_applied_to_rollback(self):
        s = RecommendationStore()
        req = _make_approval_request()
        s.add(req)
        s.update_status(req.recommendation_id, "APPROVED")
        s.update_status(req.recommendation_id, "APPLIED")
        updated = s.update_status(req.recommendation_id, "ROLLED_BACK")
        assert updated.status == "ROLLED_BACK"

    def test_list_pending_filters_correctly(self):
        s = RecommendationStore()
        r1 = _make_approval_request()
        r2 = _make_approval_request()
        s.add(r1)
        s.add(r2)
        s.update_status(r1.recommendation_id, "APPROVED")
        pending = s.list_pending()
        assert len(pending) == 1
        assert pending[0].recommendation_id == r2.recommendation_id

    def test_count(self):
        s = RecommendationStore()
        assert s.count() == 0
        s.add(_make_approval_request())
        assert s.count() == 1
        s.add(_make_approval_request())
        assert s.count() == 2

    def test_selected_candidate_property(self):
        req = _make_approval_request()
        assert req.selected_candidate is not None
        assert req.selected_candidate.candidate_id == req.selected_candidate_id
