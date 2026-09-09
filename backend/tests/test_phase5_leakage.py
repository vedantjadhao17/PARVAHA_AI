"""Phase 5: Feature leakage tests."""
import pandas as pd
import pytest

FEATURE_COLS = [
    'queue_length_m', 'vehicle_count', 'avg_speed_kmh',
    'queue_minus_5', 'queue_minus_10', 'queue_minus_15', 'queue_minus_20', 'queue_slope'
]
TARGET_COL = 'target_queue_60s'


def test_target_not_in_feature_cols():
    assert TARGET_COL not in FEATURE_COLS


def test_all_features_present_in_train():
    train = pd.read_csv('backend/ml/train.csv')
    for col in FEATURE_COLS:
        assert col in train.columns


def test_target_present_in_train():
    train = pd.read_csv('backend/ml/train.csv')
    assert TARGET_COL in train.columns


def test_target_temporal_alignment():
    train = pd.read_csv('backend/ml/train.csv')
    checked = 0
    for (scen, junc), grp in train.groupby(['scenario_id', 'junction_id']):
        grp = grp.sort_values('simulation_time_s').reset_index(drop=True)
        for i in range(min(5, len(grp) - 12)):
            t0 = grp.iloc[i]['simulation_time_s']
            t12 = grp.iloc[i + 12]['simulation_time_s']
            if abs(t12 - t0 - 60.0) < 1.0:
                tgt = grp.iloc[i][TARGET_COL]
                q12 = grp.iloc[i + 12]['queue_length_m']
                assert abs(tgt - q12) < 1e-6
                checked += 1
                break
    assert checked >= 3


def test_no_duplicate_rows():
    train = pd.read_csv('backend/ml/train.csv')
    dups = train.duplicated(subset=['scenario_id', 'junction_id', 'simulation_time_s']).sum()
    assert dups == 0


def test_lag_features_not_all_equal_target():
    train = pd.read_csv('backend/ml/train.csv')
    ratio = (train['queue_minus_20'] == train[TARGET_COL]).mean()
    assert ratio < 1.0
