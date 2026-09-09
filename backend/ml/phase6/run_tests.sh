#!/bin/bash
echo "Running Regression Suite..."
PYTHONPATH=backend pytest backend/tests/ -v > backend/ml/phase6/pytest_output.txt || true
echo "Tests complete."
