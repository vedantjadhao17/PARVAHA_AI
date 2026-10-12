# PRAVAHA AI

A traffic-simulation prototype for exploring congestion at three connected junctions in Pune. A React dashboard displays SUMO vehicles and signal states; an XGBoost model forecasts the queue estimate 60 seconds ahead.

**This is a simulation, not a deployed traffic-control system.** There is no live camera feed or connection to physical traffic lights. Real-world congestion reduction has not been validated.

## Public browser demo

[Explore the recorded simulation](https://vedantjadhao17.github.io/PARVAHA_AI/).

The free public demo replays 600 seconds of genuine SUMO telemetry, sampled every two simulation seconds. It starts around the middle of the scenario and plays at 2× speed. Pause or scrub the timeline to inspect vehicle movement, queues, and recorded forecasts. No model inference, live simulation, or signal control runs in the browser.

The local application below still runs the live SUMO simulation. See [the publishing workflow](docs/PUBLIC_DEMO.md) for how the two builds differ.

## What works

- Live simulated vehicle positions, junction queues, speeds, and signal phases.
- Queue forecasting from current traffic and the previous 20 seconds of history.
- Corridor candidate evaluation, safety constraints, and a minimum 5% simulated improvement before a proposal is offered.
- Local operator approval and rollback to the exact captured signal timings.
- Read-only showcase mode (the default), connection freshness, measured trend history, and an application audit log.

The dashboard uses React, TypeScript, Vite, Tailwind CSS, and Leaflet. The backend uses Python, FastAPI, WebSockets, SQLite, XGBoost, and SUMO/TraCI.

## Run locally

Use Python **3.12** and Node **24+**. Commands below run from the repository root.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/run_demo.sh
```

Open **http://127.0.0.1:8000**. The same server serves the dashboard and API. Keep the terminal running.

The Python requirements include the SUMO executable through `eclipse-sumo`; activate the virtual environment so `sumo` is on PATH. The simulation runs at roughly one simulated second per real second and restarts after 600 seconds. Allow a few minutes for congestion to develop. A missing recommendation is valid: the evaluator must find a safe improvement.

Scenarios:

```bash
bash scripts/run_demo.sh NORMAL
bash scripts/run_demo.sh RISING_CONGESTION
bash scripts/run_demo.sh SPILLBACK
bash scripts/run_demo.sh INCIDENT_STRESS
```

For frontend development, run the backend and use `npm --prefix frontend run dev` in another terminal. Vite proxies both API requests and WebSockets.

## Safe sharing and deployment

The default `PRAVAHA_READ_ONLY=1` rejects all approval, rejection, and rollback requests server-side. Leave it enabled for a public showcase.

A Docker deployment recipe is included:

```bash
docker build -t pravaha-prototype .
docker run --rm -p 8000:8000 -e PRAVAHA_READ_ONLY=1 pravaha-prototype
```

The image recipe has not been verified locally because Docker was unavailable. Validate it on your chosen host before publishing a link. A live host must support a long-running Python process, SUMO subprocesses, WebSockets, and one Uvicorn worker. This is not a static-site-only application. Bind a persistent volume to `/app/backend/runtime` if audit records must survive replacement of the container. Do not expose local operator mode publicly.

For local operator testing only:

```bash
PRAVAHA_READ_ONLY=0 bash scripts/run_demo.sh
```

Optional `PRAVAHA_OPERATOR_TOKEN` requires a Bearer token on write API requests. The dashboard does not provide a token login screen; use the API for token-protected tests. This is not production authentication.

## Verify it

```bash
source .venv/bin/activate
PYTHONPATH=backend pytest backend/tests -q
PYTHONPATH=backend python scripts/smoke_simulation.py
python scripts/benchmark.py
npm --prefix frontend run build
npm --prefix frontend audit
```

The smoke test runs a separate SUMO process and temporary database. It checks actual telemetry, signal-plan application, exact rollback, audit records, and a counterfactual simulation. It does not touch the running dashboard.

## Honest model results

The reproducible benchmark evaluates the checked-in model on `backend/ml/phase6/test.csv`, with the same non-negative prediction clipping used at runtime:

| Measurement | Result |
| --- | ---: |
| Test rows | 5,220 |
| Forecast horizon | 60 seconds |
| Model RMSE | 19.26 m |
| Persistence baseline RMSE | 22.05 m |
| Relative RMSE reduction | 12.65% |

These are errors on stored simulation data, **not a percentage reduction in traffic or travel time**. The benchmark does not independently establish data provenance or real-world generalization. Older reports are historical snapshots and can disagree with the currently checked-in model. Use the reproducible script for current claims.

## Limitations worth knowing

- Queue length is an estimate: halted vehicles × 5 m, summed across controlled incoming lanes. Mixed vehicle lengths mean it is not a measured physical tailback.
- “Halted share” is halted vehicles divided by active vehicles, not lane occupancy. Forecast/capacity is a ratio, not a calibrated probability of congestion.
- Cold-start lag features need 20 seconds of history.
- The 60-second counterfactual horizon is shorter than a full 90-second signal cycle. Longer-horizon intervention benefit needs further evaluation.
- The original training/test split is chronological within shared scenarios. Its scenario-separation test is deliberately marked expected-failure; it is not evidence of unseen-scenario performance.
- Recommendations are in memory and expire after 60 wall-clock seconds or when a simulation run resets.
- Audit records are append-only through the ORM, not tamper-proof against database administrators.
- Public hosting, mobile polish, production access control, operational monitoring, and physical-signal integration remain separate work.

## Project layout

- `frontend/src`: dashboard and data connection.
- `backend/app`: API, simulation, forecasting, safety checks.
- `backend/sumo_network`: road network, routes, detectors, scenarios.
- `backend/ml`: stored model, datasets, historical evaluation.
- `backend/tests`: regression tests.
- `scripts`: launcher, reproducible benchmark, real-SUMO smoke test.

The many `PHASE*` reports are retained as development history, not release guarantees. See [prototype validation](docs/PROTOTYPE_VALIDATION.md) for this revision.
