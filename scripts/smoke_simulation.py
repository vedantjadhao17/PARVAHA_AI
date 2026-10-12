"""Exercise real SUMO programs without changing the running dashboard.

Run from the repo root: PYTHONPATH=backend .venv/bin/python scripts/smoke_simulation.py
"""
import os
import tempfile
from pathlib import Path

import traci
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="pravaha-smoke-") as scratch:
        os.environ["PRAVAHA_DATABASE_URL"] = f"sqlite:///{scratch}/smoke.db"
        os.environ["PRAVAHA_START_SIMULATION"] = "0"
        os.environ["PRAVAHA_READ_ONLY"] = "0"
        from app.main import app, sim_manager
        from app.models.recommendation_store import store
        from app.sim.signal_plan import ApprovalRequest, SignalPlanCandidate, SignalPlanProposal, SafetyCheckResult
        from app.sim.corridor_state import CorridorPlanCandidate
        from app.sim.corridor_counterfactual import CorridorCounterfactualEvaluator

        sim_manager._start_sumo()
        try:
            sim_manager.decision_engine = None
            for _ in range(150):
                traci.simulationStep(traci.simulation.getTime() + 1)
                sim_manager.state["time_s"] = traci.simulation.getTime()
                sim_manager._update_junctions()
            assert len(sim_manager.state["junctions"]) == 3
            assert sum(j["active_vehicles"] for j in sim_manager.state["junctions"].values()) > 0
            tls = sim_manager.config["junctions"][0]["tls_id"]
            def timings():
                program = traci.trafficlight.getProgram(tls)
                return [p.duration for item in traci.trafficlight.getAllProgramLogics(tls)
                        if item.programID == program for p in item.phases]
            before = timings()
            candidate = SignalPlanCandidate.with_green_shift(tls, "J1_SAN", 0, 2, 5)
            req = ApprovalRequest(
                trigger_reason="Smoke test", source_states=[],
                proposal=SignalPlanProposal(candidates=[candidate], source_states=[], trigger_reason="Smoke test"),
                evaluations=[], selected_candidate_id=candidate.candidate_id,
                rollback_candidates=[], safety=SafetyCheckResult(passed=True),
                operator_rationale="Isolated simulation smoke test",
            )
            store.add(req)
            client = TestClient(app)
            approved = client.post(f"/api/recommendations/{req.recommendation_id}/approve")
            assert approved.status_code == 200, approved.text
            assert timings() == [p.duration for p in candidate.phase_specs]
            rolled_back = client.post(f"/api/recommendations/{req.recommendation_id}/rollback")
            assert rolled_back.status_code == 200, rolled_back.text
            assert timings() == before
            assert len(client.get("/api/operator-log").json()) == 2

            state_file = str(Path(scratch) / "state.xml")
            traci.simulation.saveState(state_file)
            hold = SignalPlanCandidate.from_baseline(tls, "J1_SAN", rationale="HOLD")
            corridor = CorridorPlanCandidate(
                junction_candidates={"J1_SAN": hold}, changed_junctions=[], generation_reason="HOLD baseline"
            )
            results = CorridorCounterfactualEvaluator(str(sim_manager.sumocfg_path), 10).evaluate_candidates([corridor], state_file)
            assert len(results) == 1
            print("PASS: real telemetry, full signal program approval, exact rollback, audit log, counterfactual.")
        finally:
            sim_manager.stop()


if __name__ == "__main__":
    main()
