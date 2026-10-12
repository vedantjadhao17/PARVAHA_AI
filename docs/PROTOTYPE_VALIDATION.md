# Prototype validation — 12 October 2026

This revision is a locally verified, simulation-only prototype. It is not a certification of production readiness.

## Verified locally

- Python 3.12, macOS, SUMO executable from eclipse-sumo 1.28.0.
- Full backend test collection: **127 passed, 1 expected failure**.
- The expected failure records the original dataset's shared-scenario temporal split. It has not been concealed or changed to a passing assertion.
- Real SUMO smoke test: telemetry from three junctions, complete signal-plan application through the API, rollback restoring original durations, two audit records, counterfactual execution.
- Frontend production TypeScript/Vite build passes.
- Frontend dependency audit reports zero known vulnerabilities at this check.
- Browser checks: dashboard, searchable junction list, measured analytics, system health, alerts, and operator log.
- Forecast benchmark: 5,220 stored test rows; model RMSE 19.2626 m; persistence RMSE 22.0532 m; relative error reduction 12.65%.

## Fixes

- Reentrant TraCI lock prevents nested simulation reads from deadlocking.
- SUMO stepping follows one-second simulated cadence; restart resets stale history and recommendations.
- Runtime files and geometry/config paths are repository-relative.
- Recommendation selection enforces the configured minimum improvement and rejects non-finite results.
- Counterfactual write/read failures discard a candidate instead of masquerading as zero-queue success.
- Approval submits the complete signal program, including unchanged yellow phases.
- Failed multi-junction application attempts to restore previous programs; explicit rollback uses captured timings.
- Read-only mode blocks write requests at the API, not just in the UI.
- Expired or previous-run requests cannot be offered as fresh pending plans.
- Operator-log queries use the actual timestamp field; duplicate route handlers removed.
- Same-origin API/WebSocket URLs support a single-server deployment.
- Synthetic analytics, occupancy labels, fixed “healthy” claims, and a 90-second forecast label were replaced with actual data or accurate wording.
- Demo traffic flows are sorted so SUMO does not silently ignore late-listed departures.
- Missing junction IDs and signal summaries no longer break search or leave the signal column blank.
- The legacy live-cycle script no longer executes network actions during pytest collection.

## Not verified or not delivered yet

- No public deployment URL has been created. The local URL works only while the server is running.
- Docker recipe and Linux CI are supplied but were not run locally; Docker was unavailable.
- Frontend lint has existing non-blocking React/unused-code warnings. The production build passes.
- Seven backend deprecation warnings remain.
- Real-world traffic reduction, independent dataset provenance, and unseen real-world generalization are not established.
- The simulation is desktop-first. Full mobile acceptance testing remains.
- Recommendation state is not durable. Signal writes and SQLite audit insertion are not a distributed transaction.
- A failure while restoring a partially written program still requires operator investigation; never connect this prototype to physical signals.

Use the commands in the README to reproduce checks. Historical phase reports are retained, but their old release and performance claims are not current validation.
