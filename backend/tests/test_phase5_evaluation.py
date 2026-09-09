"""Phase 5: Model evaluation sanity tests."""
import json
import pytest


def test_forecast_results_exist():
    results = json.load(open('backend/ml/phase5_forecast_results.json'))
    assert 'aggregate' in results
    assert 'per_junction' in results
    assert 'per_scenario' in results


def test_model_outperforms_naive_rmse():
    """Model RMSE must be better than naive RMSE."""
    results = json.load(open('backend/ml/phase5_forecast_results.json'))
    agg = results['aggregate']
    assert agg['model_rmse'] < agg['naive_rmse'], \
        f"Model RMSE ({agg['model_rmse']:.2f}) not better than naive ({agg['naive_rmse']:.2f})"


def test_model_rmse_within_known_range():
    """Model RMSE should be within known Phase 1 range (sanity check)."""
    results = json.load(open('backend/ml/phase5_forecast_results.json'))
    rmse = results['aggregate']['model_rmse']
    assert 10 < rmse < 30, f"Model RMSE {rmse:.2f} outside expected range 10-30m"


def test_r2_positive():
    """R² must be positive (model explains variance better than mean)."""
    results = json.load(open('backend/ml/phase5_forecast_results.json'))
    r2 = results['aggregate']['model_r2']
    assert r2 > 0, f"R² is negative ({r2:.3f}) — model is worse than predicting mean"


def test_all_three_junctions_evaluated():
    results = json.load(open('backend/ml/phase5_forecast_results.json'))
    junctions = results['per_junction']
    assert len(junctions) == 3, f"Expected 3 junctions, got {len(junctions)}"
    for name in ['J1_SAN', 'J2_SJM', 'J3_SAP']:
        assert name in junctions, f"Junction {name} missing from results"


def test_corridor_ablation_results_exist():
    results = json.load(open('backend/ml/phase5_corridor_results.json'))
    assert 'HOLD' in results
    # Accept either SINGLE_JUNCTION or SINGLE key (different harness versions)
    assert 'SINGLE_JUNCTION' in results or 'SINGLE' in results, "No single-junction key found"
    assert 'CORRIDOR' in results


def test_hold_baseline_non_zero():
    """HOLD must show non-zero queue — proves simulation is running."""
    results = json.load(open('backend/ml/phase5_corridor_results.json'))
    hold = results['HOLD']
    # Support both formats
    q = hold.get('corridor_avg_queue_m', hold.get('total_avg_queue_m', 0.0))
    assert q > 5.0, \
        f"HOLD avg queue ({q:.2f}m) too low — simulation may not be running"
