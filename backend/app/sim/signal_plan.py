"""
backend/app/sim/signal_plan.py
─────────────────────────────
Phase 2.1: Canonical SignalPlan contract.

Every piece of Phase 2 that touches signal timing goes through these
types.  No raw dicts are passed between components.

TLS ground truth (from live SUMO audit, t=1s, sancheti_congestion.sumocfg):

  J1_SAN / cluster_13546492148_1838721956
    Phase 0 — 39s  GGGrrr   (Sangam GREEN)
    Phase 1 —  6s  yyyrrr   (Sangam YELLOW — IMMUTABLE)
    Phase 2 — 39s  rrrGGG   (Ganeshkhind GREEN)
    Phase 3 —  6s  rrryyy   (Ganeshkhind YELLOW — IMMUTABLE)
    Cycle: 90s

  J2_SJM / cluster_2061304035_245647208
    Phase 0 — 39s  GGGrrrrGG  (From-Sancheti GREEN)
    Phase 1 —  6s  yyGrrrrGG  (YELLOW — IMMUTABLE)
    Phase 2 — 39s  rrGGGGGGG  (Side approach GREEN)
    Phase 3 —  6s  rrGyyyyGG  (YELLOW — IMMUTABLE)
    Cycle: 90s

  J3_SAP / cluster_245647168_3238255150_3495323634
    Phase 0 — 15s  (From-J2 GREEN)   Phase 1 — 6s  YELLOW
    Phase 2 — 17s  (Ranade GREEN)    Phase 3 — 6s  YELLOW
    Phase 4 — 17s  (Apte GREEN)      Phase 5 — 6s  YELLOW
    Phase 6 — 17s  (Bahirat GREEN)   Phase 7 — 6s  YELLOW
    Cycle: 90s
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS — derived from live TLS audit.  Change only with a new audit.
# ─────────────────────────────────────────────────────────────────────────────

# Absolute floor/ceiling for any adjustable green phase.
MIN_GREEN_S: float = 10.0
MAX_GREEN_S: float = 60.0

# Phase duration tolerance for cycle-preservation check (floating-point slack).
CYCLE_TOLERANCE_S: float = 0.5

# All three junctions share a 90-second cycle.
BASELINE_CYCLE_S: float = 90.0

# Explicit configuration of authoritative phase types.
AUDITED_TLS_CONFIG = {
    "cluster_13546492148_1838721956": {
        "junction_id": "J1_SAN",
        "cycle_seconds": 90.0,
        "adjustable_green_phases": [0, 2],
        "immutable_phases": [1, 3],
    },
    "cluster_2061304035_245647208": {
        "junction_id": "J2_SJM",
        "cycle_seconds": 90.0,
        "adjustable_green_phases": [0, 2],
        "immutable_phases": [1, 3],
    },
    "cluster_245647168_3238255150_3495323634": {
        "junction_id": "J3_SAP",
        "cycle_seconds": 90.0,
        "adjustable_green_phases": [0, 2, 4, 6],
        "immutable_phases": [1, 3, 5, 7],
    },
}


# Baseline green phase durations (from the live audit).
# Used as reference for delta calculations and rollback.
BASELINE_PHASES: Dict[str, List[Dict]] = {
    "cluster_13546492148_1838721956": [
        {"phase_idx": 0, "duration": 39.0, "state": "GGGrrr",    "is_yellow": False},
        {"phase_idx": 1, "duration":  6.0, "state": "yyyrrr",    "is_yellow": True},
        {"phase_idx": 2, "duration": 39.0, "state": "rrrGGG",    "is_yellow": False},
        {"phase_idx": 3, "duration":  6.0, "state": "rrryyy",    "is_yellow": True},
    ],
    "cluster_2061304035_245647208": [
        {"phase_idx": 0, "duration": 39.0, "state": "GGGrrrrGG",  "is_yellow": False},
        {"phase_idx": 1, "duration":  6.0, "state": "yyGrrrrGG",  "is_yellow": True},
        {"phase_idx": 2, "duration": 39.0, "state": "rrGGGGGGG",  "is_yellow": False},
        {"phase_idx": 3, "duration":  6.0, "state": "rrGyyyyGG",  "is_yellow": True},
    ],
    "cluster_245647168_3238255150_3495323634": [
        {"phase_idx": 0, "duration": 15.0, "state": "GGGGgrrrGGggrrrrrrr",  "is_yellow": False},
        {"phase_idx": 1, "duration":  6.0, "state": "Gyyyyrrryyyyrrrrrrr",  "is_yellow": True},
        {"phase_idx": 2, "duration": 17.0, "state": "GrrrrGGGrrrrrrrrrrr",  "is_yellow": False},
        {"phase_idx": 3, "duration":  6.0, "state": "Grrrryyyrrrrrrrrrrr",  "is_yellow": True},
        {"phase_idx": 4, "duration": 17.0, "state": "GrrrrrrrrrrrrrrGGGg",  "is_yellow": False},
        {"phase_idx": 5, "duration":  6.0, "state": "Grrrrrrrrrrrrrryyyy",  "is_yellow": True},
        {"phase_idx": 6, "duration": 17.0, "state": "GGrrrrrrrrrrGGgrrrr",  "is_yellow": False},
        {"phase_idx": 7, "duration":  6.0, "state": "GGrrrrrrrrrryyyrrrr",  "is_yellow": True},
    ],
}

KNOWN_TLS_IDS = set(AUDITED_TLS_CONFIG.keys())

# ─────────────────────────────────────────────────────────────────────────────
# LOW-LEVEL TYPES
# ─────────────────────────────────────────────────────────────────────────────

class PhaseSpec(BaseModel):
    """A single signal phase entry in a candidate plan."""
    phase_idx: int = Field(..., ge=0)
    duration: float = Field(..., gt=0.0)
    state: str = Field(..., min_length=1)
    is_yellow: bool  # True → this phase is an intergreen, never adjustable

    @field_validator("duration")
    @classmethod
    def duration_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"Phase duration must be > 0, got {v}")
        return round(v, 1)


class SourceState(BaseModel):
    """Snapshot of the corridor state that triggered plan generation."""
    junction_id: str
    tls_id: str
    simulation_time_s: float
    queue_m: float
    predicted_queue_60s_m: float
    predicted_capacity_ratio: float
    vehicle_count: int
    avg_speed_kmh: float


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL PLAN CANDIDATE  (one junction, one proposed program)
# ─────────────────────────────────────────────────────────────────────────────

class SignalPlanCandidate(BaseModel):
    """
    A complete proposed signal program for one TLS junction.

    Invariants enforced at construction time:
    - tls_id must be one of the three audited junctions.
    - phase_specs must list every phase present in the baseline (no additions,
      no deletions, same phase_idx ordering).
    - Yellow phases must retain their exact baseline duration.
    - All green phase durations must be within [MIN_GREEN_S, MAX_GREEN_S].
    - Total cycle duration must equal BASELINE_CYCLE_S ± CYCLE_TOLERANCE_S.
    """
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tls_id: str
    junction_id: str
    base_program_id: str = "0"          # programID of the source program
    new_program_id: str = "AI_ADAPTIVE" # programID that will be pushed to SUMO
    phase_specs: List[PhaseSpec]
    rationale: str = ""                 # Human-readable reason for this candidate

    @field_validator("tls_id")
    @classmethod
    def tls_must_be_known(cls, v: str) -> str:
        if v not in KNOWN_TLS_IDS:
            raise ValueError(
                f"Unknown tls_id {v!r}. Known IDs: {sorted(KNOWN_TLS_IDS)}"
            )
        return v

    @model_validator(mode="after")
    def validate_phase_structure(self) -> "SignalPlanCandidate":
        baseline = BASELINE_PHASES[self.tls_id]
        adjustable_idxs = set(AUDITED_TLS_CONFIG[self.tls_id]["adjustable_green_phases"])
        immutable_idxs = set(AUDITED_TLS_CONFIG[self.tls_id]["immutable_phases"])
        baseline_cycle = AUDITED_TLS_CONFIG[self.tls_id]["cycle_seconds"]

        # 1. Must have the same number of phases as baseline.
        if len(self.phase_specs) != len(baseline):
            raise ValueError(
                f"Expected {len(baseline)} phases for {self.tls_id}, "
                f"got {len(self.phase_specs)}"
            )

        # 2. Phase indexes must be contiguous 0..N-1, in order.
        for expected_idx, spec in enumerate(self.phase_specs):
            if spec.phase_idx != expected_idx:
                raise ValueError(
                    f"Phase at position {expected_idx} has phase_idx "
                    f"{spec.phase_idx} — must be in order 0..{len(baseline)-1}"
                )

        # 3. Signal state strings must match the baseline exactly (we never
        #    reorder movements — only adjust durations).
        for spec, base in zip(self.phase_specs, baseline):
            if spec.state != base["state"]:
                raise ValueError(
                    f"Phase {spec.phase_idx}: state {spec.state!r} differs "
                    f"from baseline {base['state']!r}. State strings are immutable."
                )

        # 4. Non-adjustable phases must retain their exact baseline duration.
        for spec, base in zip(self.phase_specs, baseline):
            if spec.phase_idx not in adjustable_idxs:
                if abs(spec.duration - base["duration"]) > 0.05:
                    reason = "yellow/intergreen" if spec.phase_idx in immutable_idxs else "non-adjustable"
                    raise ValueError(
                        f"Phase {spec.phase_idx} is a {reason} phase "
                        f"(immutable). Proposed {spec.duration}s ≠ baseline "
                        f"{base['duration']}s."
                    )

        # 5. Green phases must be within [MIN_GREEN_S, MAX_GREEN_S].
        for spec in self.phase_specs:
            if spec.phase_idx in adjustable_idxs:
                if spec.duration < MIN_GREEN_S:
                    raise ValueError(
                        f"Phase {spec.phase_idx} green duration {spec.duration}s "
                        f"< minimum {MIN_GREEN_S}s"
                    )
                if spec.duration > MAX_GREEN_S:
                    raise ValueError(
                        f"Phase {spec.phase_idx} green duration {spec.duration}s "
                        f"> maximum {MAX_GREEN_S}s"
                    )

        # 6. Cycle preservation.
        total = sum(s.duration for s in self.phase_specs)
        if abs(total - baseline_cycle) > CYCLE_TOLERANCE_S:
            raise ValueError(
                f"Cycle total {total:.1f}s deviates from baseline "
                f"{baseline_cycle}s by >{CYCLE_TOLERANCE_S}s. "
                "Extend one green and shorten another to compensate."
            )

        return self

    @property
    def green_phase_deltas(self) -> Dict[int, float]:
        """Returns {phase_idx: delta_seconds} for adjustable green phases only."""
        baseline = BASELINE_PHASES[self.tls_id]
        adjustable_idxs = set(AUDITED_TLS_CONFIG[self.tls_id]["adjustable_green_phases"])
        return {
            spec.phase_idx: round(spec.duration - base["duration"], 1)
            for spec, base in zip(self.phase_specs, baseline)
            if spec.phase_idx in adjustable_idxs
        }

    def as_traci_phase_dict(self) -> Dict[int, float]:
        """
        Returns {phase_idx: new_duration} for use with
        BaselineController.deploy_new_plan().  Only includes phases that
        differ from the baseline.
        """
        baseline = BASELINE_PHASES[self.tls_id]
        changed: Dict[int, float] = {}
        for spec, base in zip(self.phase_specs, baseline):
            if abs(spec.duration - base["duration"]) > 0.05:
                changed[spec.phase_idx] = spec.duration
        return changed

    @classmethod
    def from_baseline(cls, tls_id: str, junction_id: str,
                      rationale: str = "baseline") -> "SignalPlanCandidate":
        """Factory: produce a candidate that exactly replicates the baseline."""
        baseline = BASELINE_PHASES[tls_id]
        immutable_idxs = set(AUDITED_TLS_CONFIG[tls_id]["immutable_phases"])
        specs = [
            PhaseSpec(
                phase_idx=b["phase_idx"],
                duration=b["duration"],
                state=b["state"],
                is_yellow=(b["phase_idx"] in immutable_idxs),
            )
            for b in baseline
        ]
        return cls(
            tls_id=tls_id,
            junction_id=junction_id,
            phase_specs=specs,
            rationale=rationale,
        )

    @classmethod
    def with_green_shift(
        cls,
        tls_id: str,
        junction_id: str,
        extend_phase: int,
        shorten_phase: int,
        delta_s: float,
        rationale: str = "",
    ) -> "SignalPlanCandidate":
        """
        Factory: produce a candidate that extends one green phase by delta_s
        and compensates by shortening another green phase by the same amount.
        Raises ValueError if the resulting durations violate constraints.
        """
        baseline = BASELINE_PHASES[tls_id]
        adjustable_idxs = set(AUDITED_TLS_CONFIG[tls_id]["adjustable_green_phases"])
        immutable_idxs = set(AUDITED_TLS_CONFIG[tls_id]["immutable_phases"])

        if extend_phase not in adjustable_idxs or shorten_phase not in adjustable_idxs:
            raise ValueError("Cannot shift a non-adjustable or yellow phase duration.")

        specs = []
        for b in baseline:
            idx = b["phase_idx"]
            dur = b["duration"]
            if idx == extend_phase:
                dur = round(dur + delta_s, 1)
            elif idx == shorten_phase:
                dur = round(dur - delta_s, 1)
            specs.append(PhaseSpec(
                phase_idx=idx,
                duration=dur,
                state=b["state"],
                is_yellow=(idx in immutable_idxs),
            ))

        return cls(
            tls_id=tls_id,
            junction_id=junction_id,
            phase_specs=specs,
            rationale=rationale or
                f"Extend phase {extend_phase} +{delta_s}s, "
                f"shorten phase {shorten_phase} -{delta_s}s",
        )


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-JUNCTION PROPOSAL
# ─────────────────────────────────────────────────────────────────────────────

class SignalPlanProposal(BaseModel):
    """
    A named proposal containing one SignalPlanCandidate per junction.
    All candidates that are part of the same recommendation attempt are
    grouped here so they can be applied or rolled back atomically.
    """
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    candidates: List[SignalPlanCandidate]
    source_states: List[SourceState]
    trigger_reason: str  # e.g. "predicted_spillback:J3_SAP"
    is_no_op: bool = False  # True means NO SAFE CHANGE / Keep current signal plan

    @field_validator("candidates")
    @classmethod
    def no_duplicate_junctions(
        cls, v: List[SignalPlanCandidate]
    ) -> List[SignalPlanCandidate]:
        seen = set()
        for c in v:
            if c.tls_id in seen:
                raise ValueError(
                    f"Duplicate tls_id {c.tls_id!r} in proposal — "
                    "each junction may appear at most once per proposal."
                )
            seen.add(c.tls_id)
        return v


# ─────────────────────────────────────────────────────────────────────────────
# SAFETY CHECK RESULT
# ─────────────────────────────────────────────────────────────────────────────

class SafetyCheckResult(BaseModel):
    """
    Structured output of the SafetyGate.

    passed=True means every hard constraint was satisfied.
    violations is an ordered list of human-readable failure descriptions.
    An empty violations list is required when passed=True.
    """
    passed: bool
    violations: List[str] = Field(default_factory=list)
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode="after")
    def violations_only_when_failed(self) -> "SafetyCheckResult":
        if self.passed and self.violations:
            raise ValueError(
                "SafetyCheckResult.passed=True but violations list is non-empty. "
                "A passing check must have an empty violations list."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# APPROVAL REQUEST — what the operator sees and must explicitly approve
# ─────────────────────────────────────────────────────────────────────────────

class CandidateEvaluation(BaseModel):
    """
    Result of evaluating one SignalPlanCandidate in the SUMO digital twin.
    All metrics come from actual SUMO telemetry — never fabricated.
    """
    candidate_id: str
    tls_id: str
    safety: SafetyCheckResult
    # SUMO-measured metrics over the evaluation horizon
    avg_queue_m: float            # mean queue across evaluation steps
    max_queue_m: float            # peak queue during evaluation
    total_halting_vehicles: int   # sum of halting vehicle-seconds
    evaluation_horizon_s: float   # how many simulated seconds were run
    score: float                  # lower is better (composite)
    # Human-readable notes about why this candidate was chosen / rejected
    notes: str = ""


class ApprovalRequest(BaseModel):
    """
    The complete object a human operator must review and explicitly approve.

    Created by the recommendation engine, stored in the RecommendationStore,
    and returned verbatim by POST /api/recommendations/{id}/approve on success.
    """
    recommendation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: str = "PENDING"  # PENDING | APPROVED | REJECTED | APPLIED | ROLLED_BACK

    # What triggered this recommendation
    trigger_reason: str
    source_states: List[SourceState]

    # The proposal that was evaluated
    proposal: SignalPlanProposal

    # Evaluation results per candidate
    evaluations: List[CandidateEvaluation]

    # The single best candidate selected by the engine
    selected_candidate_id: str

    # Pre-built rollback: always the baseline for every junction in the proposal
    rollback_candidates: List[SignalPlanCandidate]

    # Overall safety check on the selected candidate
    safety: SafetyCheckResult

    # Explanation shown to operator
    operator_rationale: str

    # True when this recommendation spans multiple junctions (corridor-level).
    # Set by CorridorDecisionEngine at creation time. SingleJunction engine leaves False.
    is_corridor: bool = False

    # Live phase durations captured from TraCI at the moment the plan is applied.
    # For single-junction: Dict[int, float] (phase_idx -> duration_s).
    # For corridor: Dict[str, Dict[int, float]] (tls_id -> phase_idx -> duration_s).
    # Populated by the approve endpoint. Empty dict until deployment; required for rollback.
    previous_phase_durations: Dict = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def selected_candidates(self) -> List[SignalPlanCandidate]:
        """
        Return the SignalPlanCandidates to be deployed for this recommendation.

        Single-junction: returns the one candidate matching selected_candidate_id.
        Corridor: returns ALL non-HOLD candidates in the proposal (one per junction).
        HOLD-only candidates are excluded — they require no TraCI action.
        """
        if self.is_corridor:
            return [c for c in self.proposal.candidates if "HOLD" not in c.rationale]
        return [c for c in self.proposal.candidates
                if c.candidate_id == self.selected_candidate_id]

    @property
    def selected_candidate(self) -> Optional[SignalPlanCandidate]:
        for c in self.proposal.candidates:
            if c.candidate_id == self.selected_candidate_id:
                return c
        return None

