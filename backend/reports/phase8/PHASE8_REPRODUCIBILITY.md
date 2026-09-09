# PRAVAHA-AI Phase 8 Reproducibility Guide

## Environment
- **OS**: macOS (darwin-arm64)
- **Python**: 3.11.7
- **Node**: v22.23.1
- **SUMO**: 1.27.1
- **Git Commit**: 5fce1fbbf2013e493f6fa9fc0f9ad99d7342d12b

## Artifacts & Hashes
- **Model File**: `backend/ml/models/queue_forecast_model.json`
- **Model MD5**: 480c787eb04317a52aa4a5dd74789c00
- **Scenario Corpus**: `backend/sumo_network/routes/phase6/`
- **Configuration**: `backend/sumo_network/config/`

## Setup Instructions
1. Install Python dependencies: `pip install -r backend/requirements.txt`
2. Install Node dependencies: `cd frontend && npm install`
3. Export SUMO_HOME to your SUMO installation path.

## Run Commands
- **Regression Tests**: `PYTHONPATH=backend pytest backend/tests/ -v`
- **Dashboard Build**: `cd frontend && npm run build`
- **Live Smoke Test (Backend)**: `PYTHONPATH=backend uvicorn app.main:app --port 8000`
- **Live Smoke Test (Frontend)**: `cd frontend && npm run dev`
