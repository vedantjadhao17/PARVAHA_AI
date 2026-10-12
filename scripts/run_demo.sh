#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi

case "${1:-RISING_CONGESTION}" in
    NORMAL) PRAVAHA_SCENARIO="demo_1_normal.sumocfg" ;;
    RISING_CONGESTION) PRAVAHA_SCENARIO="demo_2_rising.sumocfg" ;;
    SPILLBACK) PRAVAHA_SCENARIO="demo_3_spillback.sumocfg" ;;
    INCIDENT_STRESS) PRAVAHA_SCENARIO="demo_4_incident.sumocfg" ;;
    *) echo "Choose NORMAL, RISING_CONGESTION, SPILLBACK, or INCIDENT_STRESS."; exit 1 ;;
esac
export PRAVAHA_SCENARIO
export PYTHONPATH="$PROJECT_DIR/backend"
export PRAVAHA_READ_ONLY="${PRAVAHA_READ_ONLY:-1}"
command -v sumo >/dev/null || { echo "SUMO not found. Activate .venv and install backend/requirements.txt."; exit 1; }
[[ -f frontend/dist/index.html ]] || { echo "Build the frontend first: npm --prefix frontend run build"; exit 1; }

echo "PRAVAHA AI simulation: $PRAVAHA_SCENARIO"
echo "Local dashboard: http://127.0.0.1:8000 (read-only=$PRAVAHA_READ_ONLY)"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
