#!/bin/bash
set -e

# Default canonical scenario if no explicit demo is triggered
SCENARIO_FILE="sancheti_congestion.sumocfg"

if [ "$1" == "NORMAL" ]; then
    SCENARIO_FILE="demo_1_normal.sumocfg"
elif [ "$1" == "RISING_CONGESTION" ]; then
    SCENARIO_FILE="demo_2_rising.sumocfg"
elif [ "$1" == "SPILLBACK" ]; then
    SCENARIO_FILE="demo_3_spillback.sumocfg"
elif [ "$1" == "INCIDENT_STRESS" ]; then
    SCENARIO_FILE="demo_4_incident.sumocfg"
elif [ -n "$1" ]; then
    echo "ERROR: Invalid scenario name '$1'."
    echo "Supported: NORMAL, RISING_CONGESTION, SPILLBACK, INCIDENT_STRESS"
    echo "If no argument is provided, the canonical Release Candidate (sancheti_congestion) is loaded."
    exit 1
fi

echo "========================================================="
echo " PRAVAHA-AI SIH 2026 Demonstration Launcher"
echo "========================================================="
if [ -n "$1" ]; then
    echo " Scenario: $1"
else
    echo " Scenario: DEFAULT RELEASE CANDIDATE (sancheti_congestion)"
fi
echo " Target Config: $SCENARIO_FILE"
echo "========================================================="

# Export for backend/app/sim/manager.py to read safely
export PRAVAHA_SCENARIO="$SCENARIO_FILE"

# Pre-run database/backend reset if needed for clean start
cd backend || exit 1
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
