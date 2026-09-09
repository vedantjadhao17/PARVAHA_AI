# Phase 2.2 Audit Report

## 1. Existing controller
- **File**: `backend/app/sim/controllers.py`
- **Class**: `BaselineController`
- **Initialization**: Reads the default logic from `.net.xml` to use as the baseline.
- **Phase Manipulation**: Provides `deploy_new_plan(phase_durations: Dict[int, float])`. Creates a new `traci.trafficlight.Logic` with `programID="AI_ADAPTIVE"` and pushes it via `traci.trafficlight.setProgramLogic`.
- **Reusable**: Yes, the `deploy_new_plan` logic can be perfectly adapted to apply candidate plans to the counterfactual evaluator instance.

## 2. Existing TLS interfaces
- **File**: `backend/app/sim/signal_plan.py`
- **Canonical Model**: Provides `SignalPlanCandidate` representing the timing plan.
- **Interface**: Uses `candidate.as_traci_phase_dict()` to map directly to `deploy_new_plan`.

## 3. Existing simulation startup
- **Live Startup**: Managed in `backend/app/sim/manager.py` using `SimulationManager._start_sumo`.
- **Method**: Calls `traci.start(cmd)` directly where `cmd = ["sumo", "-c", str(self.sumocfg_path), "--start", "--quit-on-end"]`.
- **Port Handling**: Uses default port selection mechanism in TraCI.
- **State Saving**: Missing from `manager.py`. Tested `traci.simulation.saveState("file.xml")` and it works seamlessly, allowing subsequent counterfactual processes to branch off using `--load-state file.xml`.

## 4. Existing phase manipulation
- `SignalPlanCandidate` validates all duration thresholds, immutable yellow phases, cycle preservation (90s limit). 

## 5. Existing candidate-related code
- Phase 2.1 created complete safety schemas and definitions (`SignalPlanProposal`, `ApprovalRequest`, `CandidateEvaluation`, `SafetyCheckResult`).
- They remain unintegrated with TraCI logic (no candidate generation exists).

## 6. Existing reusable components
- `QueueForecaster` in `backend/app/sim/forecast.py` predicts queues.
- `corridor_junctions.json` lists directional approaches and mapped green phases. This is the Rosetta stone linking directional queue pressure to signal phases.

## 7. Potential conflicts
- `manager.py` `_simulation_loop` is synchronous. If state snapshots take time, it may slightly pause the main TraCI loop. Saving state to RAMdisk or `/tmp` is recommended.
- TraCI isn't thread-safe for the same connection, but a separate `sumo` process via a new port for counterfactual evaluation solves this isolation issue.
- Need to ensure `manager.py` exposes a safe way to dump the current state file for counterfactual runs.
