# Public demo and publishing workflow

Public URL: https://vedantjadhao17.github.io/PARVAHA_AI/

## Two modes

- Local application: Python, SUMO, XGBoost, WebSockets, optional local operator actions.
- GitHub Pages: a static, read-only replay of captured SUMO output. No backend, inference, or signal writes. The banner and feed labels identify it as recorded.

The public bundle contains only generated simulation data and the already-public road network. No private account data, tokens, or operator logs are exported. No synthetic recommendations are inserted.

## Refresh the recording

From the repository root, with Python dependencies installed:

```bash
source .venv/bin/activate
PYTHONPATH=backend python scripts/export_replay.py
PYTHONPATH=backend pytest backend/tests -q
```

Review and commit `frontend/public/replay.json`. The export runs a separate SUMO instance, records 300 frames and 120 history samples, and computes forecasts during recording. It does not alter the running dashboard or control real signals.

## Deployment

The Prototype checks GitHub workflow:

1. Runs the Python regression suite and reproducible model benchmark.
2. Builds both the normal application and the static replay.
3. On a push to main only, uploads the replay build and deploys it to GitHub Pages.

Pull requests run validation but cannot publish. A failed test/build blocks deployment. Keep Pages configured to use GitHub Actions.

Local replay preview:

```bash
cd frontend
VITE_DEMO_MODE=replay VITE_BASE_PATH=/PARVAHA_AI/ npm run dev
```

Open the address Vite prints. Hash-based navigation supports directly opening individual pages on static hosting.

## LinkedIn release checklist

- Confirm the public URL loads in a browser and test Pause, timeline seeking, and navigation.
- Use a screenshot of the actual public demo with its replay banner visible.
- Say “simulation prototype” and “recorded interactive demo.” Do not describe it as deployed traffic control.
- Approve the exact post text and audience before publishing.
- LinkedIn posting is manual/approval-gated; this GitHub workflow never posts to social media.
