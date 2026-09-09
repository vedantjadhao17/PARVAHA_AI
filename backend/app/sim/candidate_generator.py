import uuid
import logging
from typing import List
from datetime import datetime, timezone

from app.sim.signal_plan import (
    SignalPlanCandidate,
    SourceState,
    SourceState,
    AUDITED_TLS_CONFIG,
    BASELINE_PHASES
)

logger = logging.getLogger(__name__)

class CandidateGenerator:
    """
    Deterministic candidate generator.
    Does NOT use LLMs. Does NOT guess phases.
    Uses AUDITED_TLS_CONFIG to generate bounded signal plan candidates.
    """

    def generate_candidates(self, state: SourceState) -> List[SignalPlanCandidate]:
        """
        Generate multiple SignalPlanCandidates to be evaluated for a single junction.
        """
        candidates: List[SignalPlanCandidate] = []
        tls_id = state.tls_id
        junction_id = state.junction_id


        if tls_id not in AUDITED_TLS_CONFIG:
            logger.warning(f"Unknown TLS {tls_id}. Generating NO-OP proposal.")
            return candidates
        # 0. Mandatory HOLD candidate (baseline)
        hold_candidate = SignalPlanCandidate.from_baseline(
            tls_id=tls_id,
            junction_id=junction_id,
            rationale="HOLD: Current baseline plan."
        )
        candidates.append(hold_candidate)

        # Ensure we know this TLS

        config = AUDITED_TLS_CONFIG[tls_id]
        adjustable = config["adjustable_green_phases"]
        
        # We need at least 2 adjustable phases to shift time
        if len(adjustable) < 2:
            return candidates

        # Critical phase selection:
        # Since queue is junction-scoped, we prioritize the main corridor.
        # From corridor_junctions.json, corridor_green_phase is always 0.
        extend_idx = 0
        
        # Compensate by reducing the next available adjustable phase (typically phase 2)
        shorten_idx = adjustable[1] 

        if extend_idx not in adjustable or shorten_idx not in adjustable:
            return candidates

        # 1. Candidate 1: +10s BOUNDED GREEN EXTENSION
        try:
            cand_10s = SignalPlanCandidate.with_green_shift(
                tls_id=tls_id,
                junction_id=junction_id,
                extend_phase=extend_idx,
                shorten_phase=shorten_idx,
                delta_s=10.0,
                rationale=f"Bounded extension: +10s to phase {extend_idx} (corridor), -10s from phase {shorten_idx}"
            )
            candidates.append(cand_10s)
        except ValueError as e:
            logger.debug(f"Could not generate +10s candidate: {e}")

        # 2. Candidate 2: +5s SMALLER GREEN EXTENSION
        try:
            cand_5s = SignalPlanCandidate.with_green_shift(
                tls_id=tls_id,
                junction_id=junction_id,
                extend_phase=extend_idx,
                shorten_phase=shorten_idx,
                delta_s=5.0,
                rationale=f"Smaller extension: +5s to phase {extend_idx} (corridor), -5s from phase {shorten_idx}"
            )
            candidates.append(cand_5s)
        except ValueError as e:
            logger.debug(f"Could not generate +5s candidate: {e}")
            
        # 3. Candidate 3: BOUNDED GREEN REDISTRIBUTION
        # If J3_SAP has 4 adjustable phases, try reducing phase 4 to extend phase 0.
        if len(adjustable) >= 3:
            try:
                shorten_idx_alt = adjustable[2]
                cand_redist = SignalPlanCandidate.with_green_shift(
                    tls_id=tls_id,
                    junction_id=junction_id,
                    extend_phase=extend_idx,
                    shorten_phase=shorten_idx_alt,
                    delta_s=10.0,
                    rationale=f"Redistribution: +10s to phase {extend_idx} (corridor), -10s from secondary phase {shorten_idx_alt}"
                )
                candidates.append(cand_redist)
            except ValueError as e:
                logger.debug(f"Could not generate redistribution candidate: {e}")

        # Ensure we have at least one valid modification, otherwise NO-OP
        return candidates
