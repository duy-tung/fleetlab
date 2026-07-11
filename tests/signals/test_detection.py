"""Known-answer tests for `fleetlab.signals.detection` (FL-T006)."""

from __future__ import annotations

import numpy as np
import pytest

from fleetlab.signals.detection import (
    count_events_in_window,
    detect_events,
    first_detection_lag_seconds,
    true_overload_windows,
    tune_threshold,
)


def test_tune_threshold_basic():
    baseline = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    tuning = tune_threshold(baseline, k=2.0)
    mean = baseline.mean()
    std = baseline.std(ddof=0)
    assert tuning.baseline_mean == pytest.approx(mean)
    assert tuning.baseline_std == pytest.approx(std)
    assert tuning.threshold == pytest.approx(mean + 2.0 * std)
    assert not tuning.degenerate_baseline


def test_tune_threshold_degenerate_baseline_is_floored_not_zero():
    baseline = np.zeros(10)
    tuning = tune_threshold(baseline, k=3.0, min_std=1e-6)
    assert tuning.degenerate_baseline
    assert tuning.threshold == pytest.approx(3e-6)
    assert tuning.threshold > 0.0  # never a literal 0 threshold that fires on any nonzero reading


def test_detect_events_requires_sustained_crossing_debounce():
    """A single-sample spike above threshold must NOT fire; sustained
    crossing for the full debounce window must fire, at the confirming
    instant (not the back-dated onset)."""
    dt = 1.0
    query_times = np.arange(0.0, 20.0, dt)
    values = np.zeros(20)
    values[5] = 10.0  # a lone spike -- should not, by itself, accumulate a debounce run
    values[10:16] = 10.0  # 6 continuous samples -- should trigger with debounce=5

    events = detect_events(query_times, values, threshold=5.0, dt=dt, debounce_seconds=5.0)
    # exactly one event: the isolated spike at idx 5 resets run_len at idx 6 and never
    # reaches 5 continuous samples, so it produces no event of its own.
    assert len(events) == 1
    # samples 10..15 are >= threshold; the 5th continuous sample (debounce=5) is index 14
    assert events[0].trigger_time == pytest.approx(14.0)


def test_detect_events_clears_with_hysteresis_band():
    dt = 1.0
    query_times = np.arange(0.0, 30.0, dt)
    values = np.zeros(30)
    values[5:20] = 10.0  # above threshold for a long stretch
    # after it ends, values go to exactly the threshold * clear_fraction band edge
    events = detect_events(
        query_times, values, threshold=5.0, dt=dt, debounce_seconds=3.0, clear_fraction=0.7
    )
    assert len(events) == 1
    assert events[0].trigger_time == pytest.approx(7.0)  # 3rd continuous sample >=5.0 starting at idx5
    assert events[0].clear_time is not None
    # clears 3 continuous samples after the value drops to 0 (<= 0.7*5=3.5), starting at idx 20
    assert events[0].clear_time == pytest.approx(22.0)


def test_detect_events_never_clears_stays_open():
    dt = 1.0
    query_times = np.arange(0.0, 10.0, dt)
    values = np.full(10, 10.0)
    events = detect_events(query_times, values, threshold=5.0, dt=dt, debounce_seconds=3.0)
    assert len(events) == 1
    assert events[0].clear_time is None


def test_true_overload_windows_only_includes_phases_above_capacity():
    phases = [(0.0, 60.0, 2.0), (60.0, 75.0, 20.0), (75.0, 135.0, 2.0), (135.0, 150.0, 40.0)]
    windows = true_overload_windows(phases, capacity_rps=26.0)
    assert windows == [(135.0, 150.0)]


def test_first_detection_lag_seconds_finds_first_within_horizon():
    from fleetlab.signals.detection import TriggerEvent

    events = [TriggerEvent(trigger_time=112.0, clear_time=120.0), TriggerEvent(trigger_time=200.0, clear_time=None)]
    lag = first_detection_lag_seconds(events, true_onset_seconds=100.0, horizon_seconds=30.0)
    assert lag == pytest.approx(12.0)


def test_first_detection_lag_seconds_returns_none_if_missed():
    from fleetlab.signals.detection import TriggerEvent

    events = [TriggerEvent(trigger_time=500.0, clear_time=None)]
    lag = first_detection_lag_seconds(events, true_onset_seconds=100.0, horizon_seconds=30.0)
    assert lag is None


def test_count_events_in_window():
    from fleetlab.signals.detection import TriggerEvent

    events = [
        TriggerEvent(trigger_time=10.0, clear_time=12.0),
        TriggerEvent(trigger_time=55.0, clear_time=60.0),
    ]
    assert count_events_in_window(events, 0.0, 50.0) == 1
    assert count_events_in_window(events, 50.0, 100.0) == 1
    assert count_events_in_window(events, 0.0, 100.0) == 2
