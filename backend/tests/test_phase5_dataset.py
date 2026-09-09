"""
Phase 5 — Dataset Integrity Tests

Tests that train.csv and test.csv have the correct structure, no NaN values,
and honour the temporal split contract.

KNOWN FAILING TEST (documented honestly):
  test_scenarios_in_only_one_split — EXPECTED TO FAIL because the same 4
  scenarios appear in both train AND test (temporal split, not scenario-level).
  This test is included so the finding is explicitly visible in the test report.

Run with:
    PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_phase5_dataset.py -v
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
TRAIN_CSV = ROOT / "backend" / "ml" / "train.csv"
TEST_CSV  = ROOT / "backend" / "ml" / "test.csv"

EXPECTED_FEATURE_COLS = [
    "queue_length_m",
    "vehicle_count",
    "avg_speed_kmh",
    "queue_minus_5",
    "queue_minus_10",
    "queue_minus_15",
    "queue_minus_20",
    "queue_slope",
]
TARGET_COL = "target_queue_60s"
EXPECTED_SCENARIOS = {
    "sancheti_smoke",
    "sancheti_congestion",
    "corridor_camera",
    "sancheti_camera",
}
EXPECTED_JUNCTIONS = {
    "cluster_13546492148_1838721956",
    "cluster_2061304035_245647208",
    "cluster_245647168_3238255150_3495323634",
}


@pytest.fixture(scope="module")
def train():
    assert TRAIN_CSV.exists(), f"train.csv not found: {TRAIN_CSV}"
    return pd.read_csv(TRAIN_CSV)


@pytest.fixture(scope="module")
def test_df():
    assert TEST_CSV.exists(), f"test.csv not found: {TEST_CSV}"
    return pd.read_csv(TEST_CSV)


# ── Test 1: files exist and have expected row counts ─────────────────────────
def test_file_sizes(train, test_df):
    assert len(train) == 2436, f"Expected 2436 train rows, got {len(train)}"
    assert len(test_df) == 612,  f"Expected 612 test rows, got {len(test_df)}"


# ── Test 2: all required columns present ─────────────────────────────────────
def test_columns_present(train, test_df):
    required = EXPECTED_FEATURE_COLS + [TARGET_COL, "scenario_id", "junction_id", "simulation_time_s"]
    for col in required:
        assert col in train.columns,   f"Train missing column: {col}"
        assert col in test_df.columns, f"Test missing column: {col}"


# ── Test 3: no NaN values ────────────────────────────────────────────────────
def test_no_nan_in_train(train):
    nan_count = train.isnull().sum().sum()
    assert nan_count == 0, f"Train has {nan_count} NaN values"


def test_no_nan_in_test(test_df):
    nan_count = test_df.isnull().sum().sum()
    assert nan_count == 0, f"Test has {nan_count} NaN values"


# ── Test 4: correct scenario sets ─────────────────────────────────────────────
def test_train_scenarios(train):
    found = set(train["scenario_id"].unique())
    assert found == EXPECTED_SCENARIOS, f"Train scenarios mismatch: {found}"


def test_test_scenarios(test_df):
    found = set(test_df["scenario_id"].unique())
    assert found == EXPECTED_SCENARIOS, f"Test scenarios mismatch: {found}"


# ── Test 5: correct junction sets ─────────────────────────────────────────────
def test_train_junctions(train):
    found = set(train["junction_id"].unique())
    assert found == EXPECTED_JUNCTIONS, f"Train junctions mismatch: {found}"


# ── Test 6 (KNOWN FAIL): scenarios should appear in only one split ────────────
@pytest.mark.xfail(
    reason=(
        "KNOWN FINDING: The same 4 scenarios appear in both train and test. "
        "The split is temporal (chronological 80/20) within each scenario, "
        "NOT scenario-level separation. This is documented in PHASE5_DATA_AUDIT.md. "
        "Fixing this requires running new simulations with different route files."
    ),
    strict=True,  # If this somehow passes, that's also a surprise — raise it
)
def test_scenarios_in_only_one_split(train, test_df):
    """
    EXPECTED TO FAIL: checks that no scenario appears in both splits.
    Kept as xfail to make the split methodology visible in test output.
    """
    train_scens = set(train["scenario_id"].unique())
    test_scens  = set(test_df["scenario_id"].unique())
    overlap = train_scens & test_scens
    assert len(overlap) == 0, (
        f"Scenarios in both train and test (temporal split, not scenario-level): {overlap}"
    )


# ── Test 7: temporal split — no time overlap per scenario×junction ─────────────
def test_temporal_no_overlap(train, test_df):
    """
    For every (scenario_id, junction_id) group, the maximum simulation_time_s
    in train must be strictly less than the minimum in test.
    This confirms the 80/20 chronological split has no leakage through time.
    """
    groups = train.groupby(["scenario_id", "junction_id"])["simulation_time_s"].max()
    for (scen, junc), train_max in groups.items():
        test_grp = test_df[
            (test_df["scenario_id"] == scen) & (test_df["junction_id"] == junc)
        ]
        if test_grp.empty:
            continue
        test_min = test_grp["simulation_time_s"].min()
        assert train_max < test_min, (
            f"Temporal overlap at {scen}/{junc}: "
            f"train_max={train_max} >= test_min={test_min}"
        )


# ── Test 8: train/test size ratio ────────────────────────────────────────────
def test_train_test_ratio(train, test_df):
    total = len(train) + len(test_df)
    train_pct = len(train) / total * 100
    # Should be close to 80%
    assert 75 <= train_pct <= 85, (
        f"Train/test ratio {train_pct:.1f}% is outside expected 75–85% range"
    )


# ── Test 9: feature values are numeric and finite ─────────────────────────────
def test_feature_values_finite(train):
    for col in EXPECTED_FEATURE_COLS:
        inf_count = np.isinf(train[col]).sum()
        assert inf_count == 0, f"Feature '{col}' has {inf_count} infinite values"


# ── Test 10: queue_length_m is non-negative ───────────────────────────────────
def test_queue_length_non_negative(train, test_df):
    assert (train["queue_length_m"] >= 0).all(), "Train has negative queue_length_m"
    assert (test_df["queue_length_m"] >= 0).all(), "Test has negative queue_length_m"
