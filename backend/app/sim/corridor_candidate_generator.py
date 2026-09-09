import itertools
import logging
from typing import List, Dict

from app.sim.candidate_generator import CandidateGenerator
from app.sim.corridor_state import CorridorState, CorridorPlanCandidate
from app.sim.signal_plan import SignalPlanCandidate, SourceState

logger = logging.getLogger(__name__)

class CorridorCandidateGenerator:
    def __init__(self, max_candidates: int = 20):
        self.single_generator = CandidateGenerator()
        self.max_candidates = max_candidates

    def generate_corridor_candidates(self, corridor_state: CorridorState) -> List[CorridorPlanCandidate]:
        """
        Generates bounded combinations of single-junction candidates for the corridor.
        Includes HOLD, single-junction variations, and combinations of the most critical.
        """
        junction_candidates: Dict[str, List[SignalPlanCandidate]] = {}
        
        # 1. Generate individual candidates for each junction
        for jid, j_state in corridor_state.junctions.items():
            # Translate to SourceState for single_generator
            s_state = SourceState(
                junction_id=jid,
                tls_id=j_state.tls_id,
                simulation_time_s=corridor_state.timestamp,
                queue_m=j_state.queue_length_m,
                vehicle_count=j_state.vehicle_count,
                avg_speed_kmh=j_state.avg_speed_kmh,
                predicted_queue_60s_m=j_state.predicted_queue_length_m,
                predicted_capacity_ratio=j_state.predicted_capacity_ratio
            )
            candidates = self.single_generator.generate_candidates(s_state)
            # Ensure HOLD is always first
            hold = [c for c in candidates if "HOLD" in c.rationale]
            others = [c for c in candidates if "HOLD" not in c.rationale]
            
            # Keep bounded single variations (e.g. max 3 variations per junction to prevent explosion)
            junction_candidates[jid] = hold + others[:3]

        if not junction_candidates:
            return []

        corridor_candidates = []
        j_ids = list(junction_candidates.keys())

        # 2. Add Baseline (All HOLD)
        hold_cand_map = {}
        for jid in j_ids:
            hold_cand_map[jid] = junction_candidates[jid][0]
            
        corridor_candidates.append(CorridorPlanCandidate(
            junction_candidates=hold_cand_map,
            changed_junctions=[],
            generation_reason="HOLD baseline"
        ))

        # 3. Add single-junction interventions (One junction changes, others HOLD)
        for jid in j_ids:
            for c in junction_candidates[jid][1:]:
                cand_map = dict(hold_cand_map)
                cand_map[jid] = c
                corridor_candidates.append(CorridorPlanCandidate(
                    junction_candidates=cand_map,
                    changed_junctions=[jid],
                    generation_reason=f"Single-junction intervention on {jid}"
                ))

        # 4. Add multi-junction interventions (combining changes along critical paths)
        # To limit explosion, we only combine 2 junctions at a time, unless it's a 3-junction corridor
        # In a 3 junction corridor, 3^3 = 27 combos, which is close to our 20 limit.
        # We'll just generate the cross product and prune to max_candidates.
        all_combinations = list(itertools.product(*[junction_candidates[jid] for jid in j_ids]))
        
        for combo in all_combinations:
            cand_map = {j_ids[i]: combo[i] for i in range(len(j_ids))}
            changed = [j_ids[i] for i in range(len(j_ids)) if "HOLD" not in combo[i].rationale]
            
            if len(changed) >= 2: # Only multi-junction (single junction & hold already added)
                corridor_candidates.append(CorridorPlanCandidate(
                    junction_candidates=cand_map,
                    changed_junctions=changed,
                    generation_reason=f"Coordinated intervention on {','.join(changed)}"
                ))
                
        # Limit the candidate pool
        if len(corridor_candidates) > self.max_candidates:
            logger.info(f"Pruning candidate explosion: {len(corridor_candidates)} -> {self.max_candidates}")
            # Ensure HOLD and single-junction interventions are prioritized
            # (they were added first)
            corridor_candidates = corridor_candidates[:self.max_candidates]

        return corridor_candidates
