from typing import List, Dict
from app.sim.signal_plan import SafetyCheckResult
from app.sim.safety_gate import check_candidate
from app.sim.corridor_state import CorridorPlanCandidate
from app.models.recommendation_store import store

def check_corridor_candidate(corridor_candidate: CorridorPlanCandidate) -> SafetyCheckResult:
    """
    Validates a multi-junction corridor candidate.
    Applies the single-junction SafetyGate to every individual candidate,
    then applies corridor-level checks (e.g., concurrency).
    """
    all_reasons: List[str] = []
    
    # 1. Single Junction Safety Gates (SC-01 through SC-07)
    for jid, cand in corridor_candidate.junction_candidates.items():
        res = check_candidate(cand)
        if not res.passed:
            all_reasons.append(f"[{jid}] failed safety gate: {'; '.join(res.violations)}")
            
    # 2. Concurrency checks (no conflicting active intervention)
    for jid, cand in corridor_candidate.junction_candidates.items():
        if "HOLD" not in cand.rationale:
            if store.has_active_intervention(cand.tls_id):
                all_reasons.append(f"[{jid}] Conflict: Active intervention already applied on {cand.tls_id}")
                
    # 3. Completeness check
    # Ensure all junctions that should be in the corridor actually have a valid candidate
    # (Assuming 3 junctions for pravaha_shivajinagar_three_signal_corridor)
    if len(corridor_candidate.junction_candidates) != 3:
        all_reasons.append(f"Incomplete corridor candidate: expected 3 junction plans, got {len(corridor_candidate.junction_candidates)}")
                
    if all_reasons:
        return SafetyCheckResult(passed=False, violations=all_reasons)
        
    return SafetyCheckResult(passed=True, violations=[])

