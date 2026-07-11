"""Tests for `fleetlab.signals.build_signal_comparison` (FL-T006):
determinism (docs/testing.md §5 -- same seed + same inputs => byte-
identical result tables) plus a few structural sanity checks on the
committed scenario set.
"""

from __future__ import annotations

import json

from fleetlab.signals.build_signal_comparison import build_report


def test_build_report_is_deterministic():
    a = json.dumps(build_report(), sort_keys=True)
    b = json.dumps(build_report(), sort_keys=True)
    assert a == b


def test_four_scenarios_with_expected_names_and_basis():
    report = build_report()
    scenarios = {s["scenario"]: s for s in report["scenarios"]}
    assert set(scenarios) == {"chat-short", "mixed", "bursty", "bursty-illustrative-severe"}
    assert scenarios["chat-short"]["basis"] == "measured"
    assert scenarios["mixed"]["basis"] == "measured"
    assert scenarios["bursty"]["basis"] == "measured"
    assert scenarios["bursty-illustrative-severe"]["basis"] == "assumed"


def test_real_bursty_workload_never_exceeds_fitted_capacity():
    """The real bursty.json burst rate (20 rps) sits below the fitted
    ground-truth capacity (~26.16 rps) -- no phase should register as a
    true overload window for any signal."""
    report = build_report()
    bursty = next(s for s in report["scenarios"] if s["scenario"] == "bursty")
    for signal in bursty["signals"].values():
        assert signal["true_overload_windows"] == []
        assert signal["detection_lags_seconds"] == []


def test_illustrative_severe_scenario_exceeds_capacity_and_is_detected():
    """The illustrative amplified burst (32 rps) exceeds the fitted
    capacity in every one of its 8 repeating cycles, and every signal in
    this task detects every one of them within the detection horizon (no
    misses) -- the point of constructing this scenario at all."""
    report = build_report()
    severe = next(s for s in report["scenarios"] if s["scenario"] == "bursty-illustrative-severe")
    for name, signal in severe["signals"].items():
        assert len(signal["true_overload_windows"]) == 8, name
        assert signal["detection_misses"] == 0, name
        assert len(signal["detection_lags_seconds"]) == 8, name
        assert all(lag is not None and lag > 0 for lag in signal["detection_lags_seconds"]), name


def test_cpu_and_gpu_utilization_are_the_identical_proxy_series():
    """Documented, deliberate limitation (module docstrings): fleetlab's
    corpus has no separate CPU/GPU telemetry, so both signals use the same
    busy-fraction proxy in every scenario -- asserted structurally, not
    just claimed in prose."""
    report = build_report()
    for scenario in report["scenarios"]:
        cpu = scenario["signals"]["cpu_utilization"]
        gpu = scenario["signals"]["gpu_utilization"]
        assert cpu["threshold_tuning"] == gpu["threshold_tuning"]
        assert cpu["events"] == gpu["events"]


def test_ground_truth_profile_is_the_g8_within_error_sweep_profile():
    report = build_report()
    assert (
        report["ground_truth_system"]["profile_id"]
        == "mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2"
    )
    assert report["ground_truth_system"]["num_servers"] == 2
