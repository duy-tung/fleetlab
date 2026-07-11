import pytest

from fleetlab.dynamics.cold_start import MEASURED_COLD_START


def test_measured_cold_start_basis_is_measured():
    assert MEASURED_COLD_START.basis == "measured"
    assert "llama-server" in MEASURED_COLD_START.source


def test_warm_load_seconds_matches_hand_computed_mean():
    # cross-check against docs/notes -- the six warm-regime samples
    # (fleetlab/dynamics/cold_start.py's own recorded log deltas)
    expected = sum(MEASURED_COLD_START.warm_samples_seconds) / 6
    assert MEASURED_COLD_START.warm_load_seconds == pytest.approx(expected)
    assert 1.5 < MEASURED_COLD_START.warm_load_seconds < 2.5


def test_cold_load_seconds_is_an_order_of_magnitude_larger_than_warm():
    ratio = MEASURED_COLD_START.cold_load_seconds / MEASURED_COLD_START.warm_load_seconds
    assert ratio > 30  # real measured gap is ~45x (88-95s cold vs ~2s warm)
    assert 80 < MEASURED_COLD_START.cold_load_seconds < 100
