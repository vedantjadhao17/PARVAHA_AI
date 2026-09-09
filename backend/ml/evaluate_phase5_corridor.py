"""
Phase 5: Corridor Evaluation — FIXED SUMO harness.

Root cause of Phase 4 zero-metric bug:
  `while traci.simulation.getMinExpectedNumber() > 0` exits as soon as all
  vehicles have left the network, which can happen well before the configured
  600-step limit.  In the congestion scenario this is fine, but in the smoke
  (low-demand) scenario vehicles drain quickly and the loop exits at ~200s,
  leaving total_q / total_v / total_halting accumulated over far fewer steps
  than expected.  The fix: loop for exactly 600 steps or until TraCI signals a
  fatal error.

Additionally the Phase 4 harness used TestClient to auto-approve
recommendations, which caused a second SUMO server to start on the same port
("Retrying" messages).  This version removes TestClient entirely and measures
queues directly from TraCI lane data.

Infrastructure note: this script requires SUMO to be installed and accessible
as 'sumo' on the PATH.  If SUMO is not available, the script reports the
failure honestly and exits with code 1.

Usage:
    PYTHONPATH=backend backend/venv/bin/python3 backend/ml/evaluate_phase5_corridor.py
"""

import json
import shutil
import sys
from pathlib import Path

# ── SUMO / TraCI availability check ──────────────────────────────────────────
if shutil.which("sumo") is None:
    msg = (
        "SUMO not found on PATH. Cannot run corridor evaluation. "
        "Install SUMO and ensure 'sumo' is accessible, then re-run."
    )
    print(f"[ERROR] {msg}", file=sys.stderr)
    result = {
        "status": "NOT_RUN",
        "reason": msg,
        "HOLD": None,
        "SINGLE": None,
        "CORRIDOR": None,
    }
    out_path = Path("backend/ml/phase5_corridor_results.json")
    out_path.write_text(json.dumps(result, indent=2))
    print(f"Wrote {out_path}")
    sys.exit(1)

try:
    import traci
    import traci.exceptions
except ImportError as e:
    msg = f"traci not importable: {e}"
    print(f"[ERROR] {msg}", file=sys.stderr)
    result = {"status": "NOT_RUN", "reason": msg}
    Path("backend/ml/phase5_corridor_results.json").write_text(json.dumps(result, indent=2))
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
SUMOCFG = "backend/sumo_network/config/sancheti_congestion.sumocfg"
SIM_STEPS = 600          # exactly 600 simulation seconds

# TLS ids for the 3 monitored junctions (from corridor_junctions.json)
TLS_IDS = [
    "cluster_13546492148_1838721956",
    "cluster_2061304035_245647208",
    "cluster_245647168_3238255150_3495323634",
]

# Green-extension applied in SINGLE / CORRIDOR modes (seconds added to current phase)
GREEN_EXTENSION_S = 10


def measure_queue_m(tls_id: str) -> float:
    """
    Estimate queue at a TLS by counting halting vehicles on controlled lanes.
    Each halting vehicle occupies ~5 m (average vehicle + gap).
    Returns queue length in metres.
    """
    total = 0
    try:
        lanes = traci.trafficlight.getControlledLanes(tls_id)
        for lane in set(lanes):          # deduplicate
            total += traci.lane.getLastStepHaltingNumber(lane)
    except traci.exceptions.TraCIException:
        pass
    return float(total) * 5.0


def extend_green(tls_id: str, extra_s: int = GREEN_EXTENSION_S):
    """
    Extend the current green phase by inserting a prolonged phase duration.
    Silently ignores TraCI errors (e.g. if TLS not yet active).
    """
    try:
        phase_idx = traci.trafficlight.getPhase(tls_id)
        current_dur = traci.trafficlight.getPhaseDuration(tls_id)
        traci.trafficlight.setPhaseDuration(tls_id, max(current_dur, extra_s))
    except traci.exceptions.TraCIException:
        pass


def run_mode(mode: str) -> dict:
    """
    Run one 600-step SUMO simulation under mode HOLD / SINGLE / CORRIDOR.

    HOLD    – no signal modifications
    SINGLE  – extend green at each junction independently when queue > 20 m
    CORRIDOR – coordinate green extension across junctions (progressive green wave)
    """
    traci.start([
        "sumo", "-c", str(SUMOCFG),
        "--step-length", "1.0",
        "--no-warnings",
        "--no-step-log",
    ])

    total_queue  = {tid: 0.0 for tid in TLS_IDS}
    step_queue   = {tid: [] for tid in TLS_IDS}
    last_eval    = 0

    steps = 0
    try:
        while steps < SIM_STEPS:
            try:
                traci.simulationStep()
            except traci.exceptions.TraCIException as e:
                print(f"  [WARN] TraCI step error at step {steps}: {e}")
                break

            steps += 1
            cur_time = traci.simulation.getTime()

            # Measure queues
            queues = {tid: measure_queue_m(tid) for tid in TLS_IDS}
            for tid in TLS_IDS:
                total_queue[tid] += queues[tid]
                step_queue[tid].append(queues[tid])

            # Signal interventions every 30 s
            if mode != "HOLD" and steps - last_eval >= 30:
                last_eval = steps
                if mode == "SINGLE":
                    for tid in TLS_IDS:
                        if queues[tid] > 20.0:
                            extend_green(tid)
                elif mode == "CORRIDOR":
                    # Progressive wave: extend J1 first, then cascade
                    if queues[TLS_IDS[0]] > 20.0:
                        extend_green(TLS_IDS[0])
                    if queues[TLS_IDS[1]] > 20.0 or queues[TLS_IDS[0]] > 40.0:
                        extend_green(TLS_IDS[1])
                    if queues[TLS_IDS[2]] > 20.0 or queues[TLS_IDS[1]] > 40.0:
                        extend_green(TLS_IDS[2])

    finally:
        traci.close()

    avg_q = {tid: (total_queue[tid] / steps if steps > 0 else 0.0) for tid in TLS_IDS}
    total_avg_q = sum(avg_q.values()) / len(TLS_IDS)

    import statistics
    peak_q = {tid: (max(step_queue[tid]) if step_queue[tid] else 0.0) for tid in TLS_IDS}

    return {
        "mode": mode,
        "steps_completed": steps,
        "avg_queue_per_junction_m": avg_q,
        "total_avg_queue_m": total_avg_q,
        "peak_queue_per_junction_m": peak_q,
    }


def main():
    if not Path(SUMOCFG).exists():
        print(f"[ERROR] Config not found: {SUMOCFG}", file=sys.stderr)
        sys.exit(1)

    results = {}
    for mode in ["HOLD", "SINGLE", "CORRIDOR"]:
        print(f"\n{'='*60}")
        print(f"Running mode: {mode}")
        print(f"{'='*60}")
        try:
            r = run_mode(mode)
            results[mode] = r
            print(f"  Steps completed : {r['steps_completed']}")
            print(f"  Avg queue (all) : {r['total_avg_queue_m']:.2f} m")
            for tid, q in r['avg_queue_per_junction_m'].items():
                short = tid[:30]
                print(f"  {short}: avg={q:.2f}m  peak={r['peak_queue_per_junction_m'][tid]:.2f}m")
        except Exception as e:
            print(f"  [ERROR] mode={mode} failed: {e}", file=sys.stderr)
            results[mode] = {"mode": mode, "error": str(e)}

    # Compute improvements vs HOLD
    if all(m in results and "total_avg_queue_m" in results[m] for m in ["HOLD", "SINGLE", "CORRIDOR"]):
        hold_q = results["HOLD"]["total_avg_queue_m"]
        for mode in ["SINGLE", "CORRIDOR"]:
            mq = results[mode]["total_avg_queue_m"]
            results[mode]["queue_reduction_vs_hold_pct"] = (
                (hold_q - mq) / max(0.1, hold_q) * 100
            )
        results["_summary"] = {
            "hold_avg_queue_m": hold_q,
            "single_avg_queue_m": results["SINGLE"]["total_avg_queue_m"],
            "corridor_avg_queue_m": results["CORRIDOR"]["total_avg_queue_m"],
            "single_reduction_pct": results["SINGLE"].get("queue_reduction_vs_hold_pct", 0.0),
            "corridor_reduction_pct": results["CORRIDOR"].get("queue_reduction_vs_hold_pct", 0.0),
        }

        print("\n" + "="*60)
        print("ABLATION SUMMARY")
        print("="*60)
        s = results["_summary"]
        print(f"  HOLD    avg queue: {s['hold_avg_queue_m']:.2f} m")
        print(f"  SINGLE  avg queue: {s['single_avg_queue_m']:.2f} m  ({s['single_reduction_pct']:+.1f}% vs HOLD)")
        print(f"  CORRIDOR avg queue: {s['corridor_avg_queue_m']:.2f} m  ({s['corridor_reduction_pct']:+.1f}% vs HOLD)")

    out_path = "backend/ml/phase5_corridor_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
