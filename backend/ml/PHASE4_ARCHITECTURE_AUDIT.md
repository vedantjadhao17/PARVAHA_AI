# PHASE 4 ARCHITECTURE AUDIT

## 1. Toplogy Context
The PRAVAHA AI system currently operates on the `pravaha_shivajinagar_three_signal_corridor` based on `corridor_junctions.json`.
The physical relationships dictated by SUMO network routes are:
- **J1 (Sancheti Chowk)** is the upstream-most junction.
  - Downstream edges: `["229904828#0", "229904828#1"]`
  - Feeds into **J2**.
- **J2 (Shivaji Road - JM Path)** is the middle junction.
  - Upstream approach: `FROM_SAN` receives traffic from J1.
  - Downstream edges: `["342557170#0", "342557171#0"]`
  - Feeds into **J3**.
- **J3 (Shivaji Road - Apte Path)** is the downstream-most junction.
  - Upstream approach: `FROM_J2` receives traffic from J2.

This forms a strict directional linear corridor: J1 → J2 → J3.

## 2. Current Junction-Independent Operations
Currently, `manager.py` fetches the states and `decision_engine.py` generates candidates using `CandidateGenerator.generate_candidates(state)`.
Each generated candidate is independently evaluated in a counterfactual SUMO sandbox.
Only single-junction recommendations (like J1 + 10s) are tested against HOLD.
If a J1 candidate is selected, its effect on J2 and J3 is ignored until the real simulation encounters the change.

## 3. Phase 4 Target Architecture
To coordinate decisions, we need:
1. **`CorridorState`**: A unified state object aggregating J1, J2, and J3.
2. **`CorridorCandidateGenerator`**: Combines single junction candidates (e.g., J1 +10s, J2 +5s, J3 HOLD) into bounded combinations.
3. **`CorridorSafetyGate`**: Re-evaluates each junction candidate against `SafetyGate`, plus enforcing corridor-level restrictions.
4. **`CorridorCounterfactual`**: Spawns a single background SUMO instance, deploys the *full* multi-junction configuration, steps 60/90s, and reads the combined performance of J1, J2, J3.
5. **`CorridorDecisionEngine`**: Evaluates all combined candidates, comparing `avg_queue` across the *entire* corridor vs the corridor-level HOLD baseline.

## 4. Tests
The current regression suite is intact (69 tests). The new features will extend existing classes or add parallel corridor-centric classes without breaking single-junction backwards compatibility.
