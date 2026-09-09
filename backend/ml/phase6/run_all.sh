#!/bin/bash
set -e
echo "1. Evaluating Forecast Model..."
python3 backend/ml/phase6/evaluate_model.py
echo "2. Analyzing Large Queues..."
python3 backend/ml/phase6/analyze_queues.py
echo "3. Stress Testing Corridor..."
python3 backend/ml/phase6/stress_test_corridor.py
echo "4. Generating Reports & Dataset Audit..."
python3 backend/ml/phase6/generate_reports.py
echo "ALL PHASE 6 METRICS GENERATED."
